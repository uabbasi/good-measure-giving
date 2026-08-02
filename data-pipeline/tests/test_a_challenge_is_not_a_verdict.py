"""One transient challenge must not cost a charity six months.

MedGlobal (82-2517347) and Islamic Services Foundation (75-2352043) both sat
frozen on the same record:

    CAPTCHA_BLOCKED: challenge page (HTTP 202)

seen ONCE each, on 2026-07-23 and 2026-07-30. classify_failure marks that
terminal and TERMINAL_FAILURE_TTL_DAYS is 180, so both were skipped until
roughly January 2027. On 2026-08-01 both sites answered a plain requests.get
with HTTP 200 — 401KB and 330KB of ordinary content. Neither was blocking us.
Nine days of a six-month sentence had already been served against a door that
was open.

The error is in what the marker list treats as equivalent:

    TERMINAL_FAILURE_MARKERS = ("captcha_blocked", "challenge page",
                                "not found", "not_found")

"not found" is a fact about the resource — it persists, and 180 days is right.
A challenge page is a DEFENCE, and defences lift: HTTP 202 with a challenge
body is Cloudflare's under-attack mode, which is triggered by load and
rate-limit heuristics as often as by any decision about us.

So a challenge is provisional until it repeats. Below CRAWL_MAX_RETRIES
sightings it is an ordinary transient failure and takes the ordinary backoff,
which re-checks within hours. Once it has been seen that many times it is a
settled fact about the publisher and earns the full 180 days — the politeness
guarantee is kept for every site that really is refusing us, and only for
those.

Everything else this session earned a corroboration requirement — cross-source
agreement, three-roll judge consensus, non-downgrade guards. This one fact,
with the largest blast radius of any of them, was trusted from a single sample.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.orchestrator import DataCollectionOrchestrator
from src.constants import CRAWL_MAX_RETRIES, TERMINAL_FAILURE_TTL_DAYS

CHALLENGE = "CAPTCHA_BLOCKED: challenge page (HTTP 202)"


def _orch(row, retry_failed_sources=False):
    o = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
    o.logger = MagicMock()
    o.retry_failed_sources = retry_failed_sources
    o.raw_data_repo = MagicMock()
    o.raw_data_repo.get_by_source.return_value = row
    return o


def _row(reason, retry_count, days_ago):
    return {
        "success": 0,
        "retry_count": retry_count,
        "last_attempt_at": datetime.now() - timedelta(days=days_ago),
        "last_failure_reason": reason,
        "error_message": reason,
    }


class TestAChallengeSeenOnceIsProvisional:
    def test_medglobal_is_retried_rather_than_frozen(self):
        """Its real stored state: seen twice, last attempt nine days ago."""
        skip, reason = _orch(_row(CHALLENGE, 2, 9))._should_skip_failed_source(
            "82-2517347", "website"
        )
        assert not skip, f"still frozen: {reason}"

    def test_a_first_sighting_is_not_terminal(self):
        skip, reason = _orch(_row(CHALLENGE, 1, 2))._should_skip_failed_source(
            "82-2517347", "website"
        )
        assert "terminal" not in reason

    def test_it_still_waits_out_its_ordinary_backoff(self):
        """Provisional does not mean impatient — a challenge seen an hour ago
        is not re-requested immediately. The politeness that matters at this
        timescale is kept."""
        skip, reason = _orch(_row(CHALLENGE, 2, 0))._should_skip_failed_source(
            "82-2517347", "website"
        )
        assert skip and "backoff" in reason


class TestAChallengeThatKeepsHappeningIsAVerdict:
    def test_it_becomes_terminal_once_corroborated(self):
        skip, reason = _orch(
            _row(CHALLENGE, CRAWL_MAX_RETRIES, 9)
        )._should_skip_failed_source("82-2517347", "website")
        assert skip and "terminal" in reason
        assert str(TERMINAL_FAILURE_TTL_DAYS) in reason

    def test_forcing_a_crawl_does_not_reopen_a_confirmed_block(self):
        """The guarantee that must survive: a site that has refused us
        repeatedly is never re-knocked, whatever the operator asks for."""
        skip, reason = _orch(
            _row(CHALLENGE, CRAWL_MAX_RETRIES, 9), retry_failed_sources=True
        )._should_skip_failed_source("75-2352043", "website")
        assert skip and "terminal" in reason


class TestAMissingResourceIsStillAFactNotADefence:
    def test_not_found_is_terminal_on_the_first_sighting(self):
        skip, reason = _orch(_row("HTTP 404 not found", 1, 2))._should_skip_failed_source(
            "12-3456789", "website"
        )
        assert skip and "terminal" in reason

    def test_and_keeps_the_full_ttl(self):
        skip, reason = _orch(_row("not_found", 1, 30))._should_skip_failed_source(
            "12-3456789", "website"
        )
        assert skip and str(TERMINAL_FAILURE_TTL_DAYS) in reason

    def test_an_expired_not_found_is_allowed_to_retry(self):
        o = _orch(_row("not_found", 1, TERMINAL_FAILURE_TTL_DAYS + 1))
        skip, _ = o._should_skip_failed_source("12-3456789", "website")
        assert not skip
        o.raw_data_repo.reset_retry_count.assert_called_once()

"""Source-granular crawl-cache freshness (Task 5) + soft-fail backoff (blocker 2A).

website_needs_recrawl is the pure helper that makes streaming_runner's
crawl-phase artifact check website-aware: a single fresh ProPublica row
must no longer mask a stale/failed/missing website row and cause the
crawl phase to skip wholesale. Its backoff_days param additionally stops a
stale-but-recently-reattempted website (soft-failed thin re-observation)
from forcing a full re-crawl on every single streaming run.
"""

from datetime import datetime, timedelta, timezone

import streaming_runner
from src.utils.freshness import source_freshness_state, website_needs_recrawl


def _row(source, success=True, days_old=0, attempted_days_ago=None):
    scraped_at = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat().replace("+00:00", "Z")
    row = {"source": source, "success": success, "scraped_at": scraped_at}
    if attempted_days_ago is not None:
        row["last_attempt_at"] = (
            (datetime.now(timezone.utc) - timedelta(days=attempted_days_ago)).isoformat().replace("+00:00", "Z")
        )
    return row


class TestWebsiteNeedsRecrawl:
    def test_fresh_propublica_and_stale_website_needs_recrawl(self):
        rows = [_row("propublica", success=True, days_old=5), _row("website", success=True, days_old=40)]
        assert website_needs_recrawl(rows, ttl_days=30) is True

    def test_fresh_propublica_and_fresh_website_does_not_need_recrawl(self):
        rows = [_row("propublica", success=True, days_old=5), _row("website", success=True, days_old=5)]
        assert website_needs_recrawl(rows, ttl_days=30) is False

    def test_missing_website_row_needs_recrawl(self):
        rows = [_row("propublica", success=True, days_old=5)]
        assert website_needs_recrawl(rows, ttl_days=30) is True

    def test_failed_website_row_needs_recrawl(self):
        rows = [_row("propublica", success=True, days_old=5), _row("website", success=False, days_old=1)]
        assert website_needs_recrawl(rows, ttl_days=30) is True

    def test_empty_rows_needs_recrawl(self):
        assert website_needs_recrawl([], ttl_days=30) is True

    def test_stale_but_just_attempted_is_backed_off(self):
        rows = [_row("website", success=True, days_old=40, attempted_days_ago=0)]
        assert website_needs_recrawl(rows, ttl_days=30, backoff_days=7) is False

    def test_stale_and_attempted_past_backoff_window_needs_recrawl(self):
        rows = [_row("website", success=True, days_old=40, attempted_days_ago=10)]
        assert website_needs_recrawl(rows, ttl_days=30, backoff_days=7) is True

    def test_stale_with_no_last_attempt_at_needs_recrawl(self):
        rows = [_row("website", success=True, days_old=40)]  # no attempted_days_ago -> no last_attempt_at
        assert website_needs_recrawl(rows, ttl_days=30, backoff_days=7) is True

    def test_missing_row_ignores_backoff(self):
        assert website_needs_recrawl([], ttl_days=30, backoff_days=7) is True

    def test_failed_row_ignores_backoff(self):
        rows = [_row("website", success=False, days_old=1, attempted_days_ago=0)]
        assert website_needs_recrawl(rows, ttl_days=30, backoff_days=7) is True

    def test_fresh_row_ignores_backoff(self):
        rows = [_row("website", success=True, days_old=5, attempted_days_ago=0)]
        assert website_needs_recrawl(rows, ttl_days=30, backoff_days=7) is False

    def test_zero_backoff_is_legacy_behavior(self):
        """backoff_days=0 (the default) must not change existing behavior."""
        rows = [_row("website", success=True, days_old=40, attempted_days_ago=0)]
        assert website_needs_recrawl(rows, ttl_days=30) is True
        assert website_needs_recrawl(rows, ttl_days=30, backoff_days=0) is True


class TestSourceFreshnessStateImportableFromNewLocation:
    def test_still_importable_and_functional(self):
        assert source_freshness_state(None, ttl_days=30) == "missing"
        row = {"source": "website", "success": True, "scraped_at": datetime.now(timezone.utc).isoformat()}
        assert source_freshness_state(row, ttl_days=30) == "fresh"


class TestStreamingCrawlPhaseBackoff:
    """streaming_runner._phase_artifacts_exist's crawl branch applies the
    soft-fail backoff so a stale-but-recently-reattempted website doesn't
    force a full re-crawl on every run."""

    class _RawRepo:
        def __init__(self, rows):
            self._rows = rows

        def get_for_charity(self, _ein):
            return self._rows

    def test_stale_recently_attempted_website_skips_recrawl(self):
        rows = [_row("website", success=True, days_old=40, attempted_days_ago=0)]
        ok, reason = streaming_runner._phase_artifacts_exist(
            "12-3456789", "crawl", self._RawRepo(rows), None, None
        )
        assert ok is True
        assert reason == ""

    def test_stale_attempted_past_backoff_window_forces_recrawl(self):
        rows = [_row("website", success=True, days_old=40, attempted_days_ago=10)]
        ok, reason = streaming_runner._phase_artifacts_exist(
            "12-3456789", "crawl", self._RawRepo(rows), None, None
        )
        assert ok is False
        assert "re-crawl" in reason

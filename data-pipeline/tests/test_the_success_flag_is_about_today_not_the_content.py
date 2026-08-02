"""Whether we hold usable content is not the same question as whether today's fetch worked.

`_has_usable_stored_data` was built so a charity holding a complete parsed
source would not fail its crawl on one bad re-fetch. It required
`row["success"]`, on the reasoning that "content stored by a failed crawl is
a challenge page, not a profile". That reasoning describes a row the raw
layer never writes.

RawDataRepository.upsert_raw_data is explicit about this: a failure write
records success/error_message/retry_count and deliberately preserves
parsed_json and scraped_at from the last good crawl, precisely because "a
PRIOR failure already flips success to False". So `success` is a fact about
the most recent ATTEMPT; `parsed_json` and `scraped_at` are facts about the
content in hand. Reading the first to decide the second re-broke the thing
the carry-forward existed to fix.

Measured on the 87-charity run of 2026-08-02, where four charities failed
their crawl outright while holding good March content well inside the
180-day window:

    20-4751162  Friends of Indus Hospital     success=0   4,926 B  2026-03-09
    47-1675693  Support Life Foundation       success=0  10,751 B  2026-03-08
    56-2500794  Givelight Foundation          success=0  30,357 B  2026-03-08
    75-2352043  Islamic Services Foundation   success=0  30,739 B  2026-03-07

Every one of them was blocked by a CAPTCHA challenge — the failure class
already ruled provisional rather than terminal, for exactly this reason.

The age test therefore has to run against scraped_at, the data-age clock,
which only advances when new content is actually written.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.orchestrator import STALE_SOURCE_GRACE_DAYS, DataCollectionOrchestrator  # noqa: E402

EIN = "75-2352043"


def _orchestrator(row):
    orch = object.__new__(DataCollectionOrchestrator)
    orch.raw_data_repo = Mock()
    orch.raw_data_repo.get_by_source.return_value = row
    orch.logger = Mock()
    return orch


def _row(**kw):
    base = {
        "success": 0,
        "parsed_json": {"website_profile": {"mission": "x"}},
        "scraped_at": datetime.now() - timedelta(days=30),
    }
    base.update(kw)
    return base


def test_a_failed_refetch_does_not_discard_content_we_still_hold():
    """The Islamic Services Foundation shape: success=0, 30KB parsed from March."""
    orch = _orchestrator(_row(scraped_at=datetime.now() - timedelta(days=148)))

    assert orch._has_usable_stored_data(EIN, "website") is True


def test_content_still_has_to_be_there():
    for empty in (None, {}, ""):
        orch = _orchestrator(_row(parsed_json=empty))
        assert orch._has_usable_stored_data(EIN, "website") is False, f"parsed_json={empty!r}"


def test_content_older_than_the_grace_window_is_not_carried():
    """Past the window a page stops being evidence of what the charity does now."""
    orch = _orchestrator(_row(scraped_at=datetime.now() - timedelta(days=STALE_SOURCE_GRACE_DAYS + 1)))

    assert orch._has_usable_stored_data(EIN, "website") is False


def test_an_undatable_row_fails_closed():
    for bad in (None, "", "not-a-date"):
        orch = _orchestrator(_row(scraped_at=bad))
        assert orch._has_usable_stored_data(EIN, "website") is False, f"scraped_at={bad!r}"


def test_no_row_at_all_is_not_usable():
    orch = _orchestrator(None)

    assert orch._has_usable_stored_data(EIN, "website") is False


def test_a_successful_row_is_still_usable():
    """Regression: the ordinary case must keep working."""
    orch = _orchestrator(_row(success=1))

    assert orch._has_usable_stored_data(EIN, "website") is True

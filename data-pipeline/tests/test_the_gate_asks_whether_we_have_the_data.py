"""A failed re-fetch must not erase data we already hold.

The crawl gate asks "did this run fetch every required source?" — a source
counts only if it lands in sources_succeeded. So a charity with a complete,
successfully-parsed source in the database fails its crawl outright when today's
re-fetch trips over a challenge page or a DNS blip, and the export gate then
drops the page it would otherwise have published unchanged.

EIN 75-2352043 is the case that made this visible: its website row carries
320KB of content parsed into 45 usable fields from a successful March crawl,
and every other source is fresh. It failed on a single re-fetch and was frozen.
82-2517347 sat in the identical state with 229KB.

The gate now asks whether we HAVE the source, not whether we just fetched it.
Two things keep that honest:

  It must be real. A row that never parsed into anything is not data, and a row
  whose last crawl failed WITHOUT leaving content behind is not either.

  It must not be ancient. Beyond STALE_SOURCE_GRACE_DAYS the content stops
  standing in for a fetch, because a page that old is no longer evidence of
  what the organisation is doing now.

Whenever it happens the source is reported as carried, not silently counted, so
"complete" never quietly means "complete as of March".
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.orchestrator import DataCollectionOrchestrator
from src.constants import STALE_SOURCE_GRACE_DAYS


def _orch(row):
    o = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
    o.logger = MagicMock()
    o.raw_data_repo = MagicMock()
    o.raw_data_repo.get_by_source.return_value = row
    return o


def _row(days_old, parsed=True, success=1):
    return {
        "success": success,
        "scraped_at": datetime.now() - timedelta(days=days_old),
        "parsed_json": {"website_profile": {"mission": "x"}} if parsed else None,
        "raw_content": "<html>...</html>" if parsed else "",
    }


class TestContentWeAlreadyHoldStandsInForAFetch:
    def test_a_recently_parsed_source_carries(self):
        assert _orch(_row(30))._has_usable_stored_data("75-2352043", "website")

    def test_the_islamic_services_case(self):
        """320KB parsed in March, re-fetch blocked in July."""
        assert _orch(_row(146))._has_usable_stored_data("75-2352043", "website")

    def test_content_past_the_grace_period_does_not(self):
        assert not _orch(
            _row(STALE_SOURCE_GRACE_DAYS + 1)
        )._has_usable_stored_data("75-2352043", "website")


class TestItMustActuallyBeData:
    def test_a_row_that_never_parsed_is_not_data(self):
        assert not _orch(_row(30, parsed=False))._has_usable_stored_data("x", "website")

    def test_no_row_at_all_is_not_data(self):
        assert not _orch(None)._has_usable_stored_data("x", "website")

    def test_a_row_with_no_timestamp_is_not_trusted(self):
        """Undatable content cannot be shown to be within the grace period."""
        row = _row(30)
        row["scraped_at"] = None
        assert not _orch(row)._has_usable_stored_data("x", "website")

    def test_a_never_successful_row_is_not_data(self):
        """A row that has only ever failed carries nothing to carry forward.

        What excludes it is the absent content, not the success flag. The
        flag cannot do this job: it reports the most recent ATTEMPT, so it
        reads 0 both for a row that never worked and for one holding good
        March content behind a failed re-fetch. Gating on it froze four real
        charities on 2026-08-02 — see
        test_the_success_flag_is_about_today_not_the_content.py.
        """
        assert not _orch(_row(30, success=0, parsed=False))._has_usable_stored_data("x", "website")

    def test_a_failed_refetch_over_good_content_is_still_data(self):
        """The real Islamic Services Foundation row: success=0, 30KB from March."""
        assert _orch(_row(146, success=0))._has_usable_stored_data("75-2352043", "website")

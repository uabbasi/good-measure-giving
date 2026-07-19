"""Source-granular crawl-cache freshness (Task 5).

website_needs_recrawl is the pure helper that makes streaming_runner's
crawl-phase artifact check website-aware: a single fresh ProPublica row
must no longer mask a stale/failed/missing website row and cause the
crawl phase to skip wholesale.
"""

from datetime import datetime, timedelta, timezone

from src.utils.freshness import source_freshness_state, website_needs_recrawl


def _row(source, success=True, days_old=0):
    scraped_at = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat().replace("+00:00", "Z")
    return {"source": source, "success": success, "scraped_at": scraped_at}


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


class TestSourceFreshnessStateImportableFromNewLocation:
    def test_still_importable_and_functional(self):
        assert source_freshness_state(None, ttl_days=30) == "missing"
        row = {"source": "website", "success": True, "scraped_at": datetime.now(timezone.utc).isoformat()}
        assert source_freshness_state(row, ttl_days=30) == "fresh"

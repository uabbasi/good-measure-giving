"""Per-source freshness report (Task 4).

source_freshness_state is the single shared pure helper for classifying a
raw_scraped_data row's freshness against a TTL; it mirrors
DataCollectionOrchestrator._is_data_fresh's tz-aware age math exactly, and
both select_stale_website_eins (Task 3) and crawl_freshness_summary
(Task 4) are built on top of it so the age math lives in one place.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from crawl import crawl_freshness_summary, source_freshness_state


def _row(success=True, days_old=None, scraped_at=None):
    """Fake raw_scraped_data row shape (success, scraped_at)."""
    if scraped_at is None and days_old is not None:
        scraped_at = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat().replace("+00:00", "Z")
    return {"success": success, "scraped_at": scraped_at}


class TestSourceFreshnessState:
    def test_missing_row_is_missing(self):
        assert source_freshness_state(None, ttl_days=30) == "missing"

    def test_falsy_success_is_failed(self):
        row = _row(success=False, days_old=5)
        assert source_freshness_state(row, ttl_days=30) == "failed"

    def test_success_and_recent_is_fresh(self):
        row = _row(success=True, days_old=5)
        assert source_freshness_state(row, ttl_days=30) == "fresh"

    def test_success_and_older_than_ttl_is_stale(self):
        row = _row(success=True, days_old=40)
        assert source_freshness_state(row, ttl_days=30) == "stale"

    def test_boundary_exactly_ttl_days_old_is_stale(self):
        # Mirrors _is_data_fresh: age < ttl_days is fresh, so age == ttl_days is stale.
        scraped_at = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
        row = _row(success=True, scraped_at=scraped_at)
        assert source_freshness_state(row, ttl_days=30) == "stale"

    def test_tz_naive_scraped_at_recent_is_fresh(self):
        scraped_at = (datetime.now() - timedelta(days=5)).isoformat()
        row = _row(success=True, scraped_at=scraped_at)
        assert source_freshness_state(row, ttl_days=30) == "fresh"

    def test_tz_naive_scraped_at_old_is_stale(self):
        scraped_at = (datetime.now() - timedelta(days=40)).isoformat()
        row = _row(success=True, scraped_at=scraped_at)
        assert source_freshness_state(row, ttl_days=30) == "stale"

    def test_missing_scraped_at_fails_closed_to_stale(self):
        row = _row(success=True, scraped_at=None)
        assert source_freshness_state(row, ttl_days=30) == "stale"

    def test_unparseable_scraped_at_fails_closed_to_stale(self):
        row = _row(success=True, scraped_at="not-a-timestamp")
        assert source_freshness_state(row, ttl_days=30) == "stale"


class TestCrawlFreshnessSummary:
    def _repo(self, rows_by_ein_source):
        raw_repo = MagicMock()
        raw_repo.get_by_source.side_effect = lambda ein, source: rows_by_ein_source.get((ein, source))
        return raw_repo

    def test_per_source_counts_across_mixed_states(self):
        eins = ["11-1111111", "22-2222222", "33-3333333", "44-4444444"]
        rows = {
            # propublica: all fresh
            ("11-1111111", "propublica"): _row(success=True, days_old=10),
            ("22-2222222", "propublica"): _row(success=True, days_old=10),
            ("33-3333333", "propublica"): _row(success=True, days_old=10),
            ("44-4444444", "propublica"): _row(success=True, days_old=10),
            # website: one of each state (missing for 44-4444444)
            ("11-1111111", "website"): _row(success=True, days_old=5),  # fresh
            ("22-2222222", "website"): _row(success=True, days_old=40),  # stale
            ("33-3333333", "website"): _row(success=False, days_old=1),  # failed
            # 44-4444444 has no website row -> missing
        }
        raw_repo = self._repo(rows)

        summary = crawl_freshness_summary(raw_repo, eins)

        assert summary["propublica"]["fresh"] == 4
        assert summary["propublica"]["stale"] == 0
        assert summary["propublica"]["failed"] == 0
        assert summary["propublica"]["missing"] == 0

        assert summary["website"]["fresh"] == 1
        assert summary["website"]["stale"] == 1
        assert summary["website"]["failed"] == 1
        assert summary["website"]["missing"] == 1

        # Other sources have no rows at all -> all missing.
        for source in ("charity_navigator", "candid", "form990_grants", "bbb"):
            assert summary[source]["missing"] == len(eins)
            assert summary[source]["fresh"] == 0
            assert summary[source]["stale"] == 0
            assert summary[source]["failed"] == 0

    def test_collects_failed_and_stale_website_eins(self):
        eins = ["11-1111111", "22-2222222", "33-3333333", "44-4444444"]
        rows = {
            ("11-1111111", "website"): _row(success=True, days_old=5),  # fresh
            ("22-2222222", "website"): _row(success=True, days_old=40),  # stale
            ("33-3333333", "website"): _row(success=False, days_old=1),  # failed
            # 44-4444444 missing -> not in the failed/stale list
        }
        raw_repo = self._repo(rows)

        summary = crawl_freshness_summary(raw_repo, eins)

        assert set(summary["website"]["stale_eins"]) == {"22-2222222", "33-3333333"}

    def test_all_six_sources_present_in_summary(self):
        raw_repo = self._repo({})
        summary = crawl_freshness_summary(raw_repo, [])
        assert set(summary.keys()) == {
            "propublica",
            "charity_navigator",
            "candid",
            "form990_grants",
            "website",
            "bbb",
        }

    def test_empty_eins_gives_zero_counts(self):
        raw_repo = self._repo({})
        summary = crawl_freshness_summary(raw_repo, [])
        for source, counts in summary.items():
            assert counts["fresh"] == 0
            assert counts["stale"] == 0
            assert counts["failed"] == 0
            assert counts["missing"] == 0

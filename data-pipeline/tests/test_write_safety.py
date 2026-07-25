"""Tests for the non-destructive-synthesize write-safety guards."""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestStalenessConstant:
    def test_constant_is_two_years(self):
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS

        assert DATA_FULL_CONFIDENCE_MAX_AGE_YEARS == 2

    def test_recency_factor_uses_constant(self):
        # Age exactly at the boundary keeps full weight; one past it decays.
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        from src.scorers.v2_scorers import AmalScorerV2

        boundary = DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        assert AmalScorerV2._recency_factor(boundary) == 1.0
        assert AmalScorerV2._recency_factor(boundary + 1) < 1.0


class TestRawLayerPredicates:
    def test_data_age_years_from_datetime(self):
        from src.collectors.orchestrator import data_age_years

        now = datetime(2026, 7, 19)
        assert data_age_years(datetime(2024, 7, 19), now=now) == 2
        assert data_age_years(datetime(2023, 1, 1), now=now) == 3
        assert data_age_years(None, now=now) is None

    def test_data_age_years_from_iso_string(self):
        from src.collectors.orchestrator import data_age_years

        now = datetime(2026, 7, 19)
        assert data_age_years("2024-07-19 00:00:00", now=now) == 2

    def test_grants_has_filings(self):
        from src.collectors.orchestrator import grants_has_filings

        empty = {"grants_profile": {"name": "Unknown (12-3456789)", "ein": "12-3456789"}}
        real = {"grants_profile": {"ein": "12-3456789", "filing_years": [2022], "total_grants": 5000}}
        assert grants_has_filings(empty) is False
        assert grants_has_filings(real) is True
        assert grants_has_filings(None) is False

    def test_website_downgrade_thin_replaces_rich(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 25}}
        thin = {"crawl_stats": {"pages_crawled": 1}}
        assert is_content_downgrade("website", thin, "x" * 600, prior) is True

    def test_website_no_downgrade_when_similar(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 8}}
        fresh = {"crawl_stats": {"pages_crawled": 9}}
        assert is_content_downgrade("website", fresh, "x" * 5000, prior) is False

    def test_website_downgrade_empty_raw(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 10}}
        assert is_content_downgrade("website", {"crawl_stats": {"pages_crawled": 2}}, "", prior) is True

    def test_grants_downgrade_empty_replaces_filings(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"grants_profile": {"filing_years": [2022], "total_grants": 9000}}
        empty = {"grants_profile": {"name": "Unknown", "ein": "12-3456789"}}
        assert is_content_downgrade("form990_grants", empty, None, prior) is True

    def test_no_downgrade_without_prior(self):
        from src.collectors.orchestrator import is_content_downgrade

        assert is_content_downgrade("website", {"crawl_stats": {"pages_crawled": 1}}, "x", {}) is False

    def test_website_downgrade_thin_by_length(self):
        from src.collectors.orchestrator import is_content_downgrade

        # Page count unchanged (no page-loss signal) but raw content is thin.
        prior = {"crawl_stats": {"pages_crawled": 10}}
        new = {"crawl_stats": {"pages_crawled": 10}}
        assert is_content_downgrade("website", new, "x" * 400, prior) is True

    def test_generic_source_downgrade(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"cn_profile": {"score": 90}}
        empty = {"cn_profile": {}}
        assert is_content_downgrade("charity_navigator", empty, None, prior) is True
        assert is_content_downgrade("charity_navigator", prior, None, prior) is False

    def test_more_pages_with_an_empty_homepage_is_not_a_downgrade(self):
        """new_raw_content is the homepage only; it can fail independently of the crawl."""
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 20}}
        richer = {"crawl_stats": {"pages_crawled": 25}}
        assert is_content_downgrade("website", richer, "", prior) is False
        assert is_content_downgrade("website", richer, "x" * 400, prior) is False

    def test_thin_homepage_with_no_page_improvement_is_still_a_downgrade(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 20}}
        fewer = {"crawl_stats": {"pages_crawled": 18}}
        assert is_content_downgrade("website", fewer, "", prior) is True

    def test_lost_pages_is_a_downgrade_regardless_of_homepage(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 20}}
        collapsed = {"crawl_stats": {"pages_crawled": 3}}
        assert is_content_downgrade("website", collapsed, "x" * 5000, prior) is True


class TestRawDataRepoSoftFail:
    def test_record_soft_fail_preserves_content_and_timestamp(self, monkeypatch):
        import src.db.repository as repo_mod

        captured = {}

        def fake_execute_query(sql, params=None, fetch="all"):
            if sql.strip().upper().startswith("SELECT"):
                return {"charity_ein": "12-3456789", "source": "website", "retry_count": 1, "success": 1}
            captured["sql"] = sql
            captured["params"] = params
            return None

        monkeypatch.setattr(repo_mod, "execute_query", fake_execute_query)
        repo_mod.RawDataRepository().record_soft_fail("12-3456789", "website", "thin re-crawl; preserved")

        assert "UPDATE raw_scraped_data" in captured["sql"]
        assert "retry_count" in captured["sql"]
        assert "last_failure_reason" in captured["sql"]
        # Must NOT touch content or the observation timestamp
        assert "parsed_json" not in captured["sql"]
        assert "raw_content" not in captured["sql"]
        assert "scraped_at" not in captured["sql"]
        assert captured["params"][0] == 2  # retry_count incremented from 1

    def test_c1_failure_write_no_longer_bumps_scraped_at(self, monkeypatch):
        import src.db.repository as repo_mod

        captured = {}

        def fake_execute_query(sql, params=None, fetch="all"):
            if sql.strip().upper().startswith("SELECT"):
                return {
                    "charity_ein": "12-3456789",
                    "source": "website",
                    "retry_count": 0,
                    "success": 1,
                    "parsed_json": '{"website_profile": {"mission": "Feed people"}}',
                    "raw_content": "<html>good</html>",
                }
            captured["sql"] = sql
            return None

        monkeypatch.setattr(repo_mod, "execute_query", fake_execute_query)
        # A failure write against a previously-successful row (C1 path)
        repo_mod.RawDataRepository().upsert(
            "12-3456789", "website", parsed_json={}, success=False, error_message="throttled"
        )
        assert "UPDATE raw_scraped_data" in captured["sql"]
        assert "scraped_at = CURRENT_TIMESTAMP" not in captured["sql"]


class TestStoreRawDataNonDowngrade:
    def _collector_with_fake_repo(self, existing_row):
        from src.collectors.orchestrator import DataCollectionOrchestrator

        calls = {"soft_fail": [], "upsert": []}

        class FakeRawRepo:
            def get_by_source(self, ein, source):
                return existing_row

            def record_soft_fail(self, ein, source, reason):
                calls["soft_fail"].append((ein, source, reason))

            def upsert(self, **kwargs):
                calls["upsert"].append(kwargs)

        col = object.__new__(DataCollectionOrchestrator)  # skip __init__
        col.raw_data_repo = FakeRawRepo()
        col.crawl_attempt_repo = MagicMock()
        col.crawled_page_repo = MagicMock()
        import logging

        col.logger = logging.getLogger("test")
        return col, calls

    def test_thin_recrawl_preserves_recent_last_good(self):
        from datetime import datetime

        recent = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        existing = {
            "success": 1,
            "scraped_at": recent,
            "parsed_json": {"website_profile": {"url": "x"}, "crawl_stats": {"pages_crawled": 25}},
        }
        col, calls = self._collector_with_fake_repo(existing)
        thin = {
            "raw_content": "x" * 100,  # below the 500 floor
            "website_profile": {"url": "x", "ein": "12-3456789"},
            "page_extractions": [],
            "crawl_stats": {"pages_crawled": 1},
        }
        result = col._store_raw_data("12-3456789", "website", thin)
        assert result is True
        assert len(calls["soft_fail"]) == 1     # preserved
        assert len(calls["upsert"]) == 0        # no overwrite
        # A preserve is still a real attempt -- logged as such (success=True,
        # since the source keeps counting as succeeded) with the preserve
        # reason, so the durable history shows this attempt happened even
        # though raw_scraped_data's current-state row didn't change.
        col.crawl_attempt_repo.record.assert_called_once()
        _, kwargs = col.crawl_attempt_repo.record.call_args
        assert kwargs["success"] is True
        assert "thinner than last-good" in kwargs["failure_reason"]

    def test_thin_recrawl_aged_out_is_written(self):
        existing = {
            "success": 1,
            "scraped_at": "2019-01-01 00:00:00",  # > 2 years old
            "parsed_json": {"website_profile": {"url": "x"}, "crawl_stats": {"pages_crawled": 25}},
        }
        col, calls = self._collector_with_fake_repo(existing)
        thin = {"raw_content": "x" * 100, "website_profile": {"url": "x"}, "crawl_stats": {"pages_crawled": 1}}
        col._store_raw_data("12-3456789", "website", thin)
        assert len(calls["soft_fail"]) == 0     # aged-out: allow the drop
        assert len(calls["upsert"]) == 1

    def test_website_crawl_records_page_history_on_success(self):
        col, calls = self._collector_with_fake_repo(existing_row=None)  # no prior -> writes normally
        data = {
            "raw_content": "x" * 1000,
            "website_profile": {"url": "x", "ein": "12-3456789"},
            "page_extractions": [],
            "crawl_stats": {"pages_crawled": 2},
            "crawled_urls": [
                {"url": "https://x.org/", "had_data": True},
                {"url": "https://x.org/about", "had_data": False},
            ],
        }
        col._store_raw_data("12-3456789", "website", data)
        col.crawled_page_repo.record_pages.assert_called_once_with("12-3456789", data["crawled_urls"])
        col.crawl_attempt_repo.record.assert_called_once()
        _, kwargs = col.crawl_attempt_repo.record.call_args
        assert kwargs["pages_found"] == 2
        assert kwargs["pages_with_data"] == 1

    def test_empty_grants_preserved_when_prior_has_filings(self):
        recent = "2026-01-01 00:00:00"
        existing = {
            "success": 1,
            "scraped_at": recent,
            "parsed_json": {"grants_profile": {"filing_years": [2022], "total_grants": 9000}},
        }
        col, calls = self._collector_with_fake_repo(existing)
        empty = {"grants_profile": {"name": "Unknown (12-3456789)", "ein": "12-3456789"}}
        result = col._store_raw_data("12-3456789", "form990_grants", empty)
        assert result is True
        assert len(calls["soft_fail"]) == 1
        assert len(calls["upsert"]) == 0
        # Non-website source: no page-level history, no page counts.
        col.crawled_page_repo.record_pages.assert_not_called()
        _, kwargs = col.crawl_attempt_repo.record.call_args
        assert kwargs["pages_found"] is None
        assert kwargs["pages_with_data"] is None


class TestStoreRawContentOnlyNonDowngrade:
    """Task C8: `_store_raw_content_only` is the only store used for
    propublica/charity_navigator/candid/form990_grants on the production
    fetch path (`fetch_charity_data`) -- unlike `_store_raw_data`, it never
    parses, so it has no `parsed_json` for the new observation to compare
    with `is_content_downgrade`. It guards on raw content substance instead
    (see `_has_content_substance`), which is the signal actually available
    at this phase.
    """

    def test_non_website_sources_are_downgrade_guarded_on_the_production_path(self):
        """Only `website` was guarded; propublica/CN/candid/form990_grants went
        through _store_raw_content_only unguarded (Spec B Vector 2)."""
        from unittest.mock import MagicMock

        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = {
            "source": "form990_grants",
            "success": 1,
            # Size is arbitrary and not exercised by this scenario: the new
            # fetch below is fully empty, which trips the guard on its own
            # regardless of what the prior looked like. See
            # test_thin_but_above_floor_json_does_not_overwrite_a_much_richer_prior
            # and test_grants_sentinel_does_not_overwrite_prior_real_filings for
            # cases where the prior's size/content is actually load-bearing.
            "raw_content": "x" * 10,
        }

        # A thin, empty-but-successful re-fetch must NOT overwrite the good row.
        orch._store_raw_content_only("12-3456789", "form990_grants", "", "xml")

        assert orch.raw_data_repo.record_soft_fail.called, "thin re-fetch must soft-fail, not overwrite"
        assert not orch.raw_data_repo.upsert.called

    def test_a_genuinely_richer_non_website_fetch_still_writes(self):
        from unittest.mock import MagicMock

        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = {
            "source": "propublica",
            "success": 1,
            "raw_content": "x" * 100,
        }

        orch._store_raw_content_only("12-3456789", "propublica", "y" * 50_000, "json")

        assert orch.raw_data_repo.upsert.called

    def test_thin_but_above_floor_content_does_not_overwrite_a_much_richer_prior(self):
        """FIX 1 (C8 review): `_has_content_substance`'s floor is fixed
        (500B for charity_navigator) and absolute -- it doesn't compare
        against the prior. A ~1KB Cloudflare interstitial clears that floor
        easily but is still a tiny fraction of an 80KB stored profile page,
        so it must be caught relative to the prior, not just against the
        floor."""
        from unittest.mock import MagicMock

        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = {
            "source": "charity_navigator",
            "success": 1,
            "raw_content": "x" * 80_000,
        }

        orch._store_raw_content_only("12-3456789", "charity_navigator", "y" * 1030, "html")

        assert orch.raw_data_repo.record_soft_fail.called, "thin-but-above-floor re-fetch must soft-fail, not overwrite"
        assert not orch.raw_data_repo.upsert.called

    def test_thin_but_above_floor_json_does_not_overwrite_a_much_richer_prior(self):
        """Same as above for propublica's JSON floor (50B) -- a ~98B 'no
        filings' stub clears the floor but is a tiny fraction of a 60KB
        stored response."""
        from unittest.mock import MagicMock

        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = {
            "source": "propublica",
            "success": 1,
            "raw_content": "x" * 60_000,
        }

        thin_stub = (
            '{"organization":{"ein":"12-3456789","name":"Example Org","city":"Anytown"},'
            '"filings_with_data":[]}'
        )
        assert 50 < len(thin_stub) < 60_000 // 3, "fixture must clear the substance floor but stay a thin fraction of the prior"
        orch._store_raw_content_only("12-3456789", "propublica", thin_stub, "json")

        assert orch.raw_data_repo.record_soft_fail.called, "thin-but-above-floor re-fetch must soft-fail, not overwrite"
        assert not orch.raw_data_repo.upsert.called

    def test_grants_sentinel_does_not_overwrite_prior_real_filings(self):
        """`_has_content_substance` explicitly waves the NO_XML_SENTINEL
        through as substance (it's a legitimately short body), so the
        generic floor/ratio check can't be what catches this. A sentinel
        replacing a prior real filing must still be preserved, matching
        `is_content_downgrade`'s `grants_has_filings` intent for the
        parsed-data path."""
        from unittest.mock import MagicMock

        from src.collectors.form990_grants import Form990GrantsCollector
        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = {
            "source": "form990_grants",
            "success": 1,
            "raw_content": "<real 990 xml with filings>" * 500,
        }

        orch._store_raw_content_only(
            "12-3456789", "form990_grants", Form990GrantsCollector.NO_XML_SENTINEL, "xml"
        )

        assert orch.raw_data_repo.record_soft_fail.called, "sentinel must not overwrite a real prior filing"
        assert not orch.raw_data_repo.upsert.called

    def test_first_observation_for_a_source_always_writes(self):
        """No prior row -> nothing to downgrade from, per the guard's contract."""
        from unittest.mock import MagicMock

        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = None

        orch._store_raw_content_only("12-3456789", "candid", "z" * 600, "html")

        assert orch.raw_data_repo.upsert.called
        assert not orch.raw_data_repo.record_soft_fail.called

    def test_crawl_attempt_recorded_on_the_content_only_path(self):
        """Step 4: this store was previously website-only in the crawl_attempts
        history despite its docstring; a plain successful write must record
        one too."""
        from unittest.mock import MagicMock

        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = None

        orch._store_raw_content_only("12-3456789", "propublica", "y" * 500, "json")

        orch.crawl_attempt_repo.record.assert_called_once()
        _, kwargs = orch.crawl_attempt_repo.record.call_args
        assert kwargs["success"] is True


class TestRegressionGuard:
    def test_guard_restores_nonnull_to_null(self):
        from src.db import CharityData
        from synthesize import apply_regression_guard

        prior = {"total_revenue": 1_000_000, "total_expenses": 800_000}
        synthesized = CharityData(charity_ein="12-3456789")
        synthesized.total_expenses = 800_000
        metrics = CharityData(charity_ein="12-3456789")
        metrics.total_expenses = 800_000
        # total_revenue recomputed to None this run (a genuine computation gap --
        # total_revenue is always present on a valid 990/990-EZ)
        flags = apply_regression_guard(synthesized, metrics, prior)

        assert metrics.total_revenue == 1_000_000  # restored into the object the scorer reads
        assert synthesized.total_revenue == 1_000_000  # restored
        assert flags == [{"charity_ein": "12-3456789", "field": "total_revenue", "prior_value": 1_000_000, "rejected": None}]

    def test_guard_restores_attribution_alongside_value(self):
        """Real incident: EIN 31-1267559's total_revenue was restored by the
        guard with no source_attribution entry, failing the synthesize
        quality gate (S-J-002, 'has value but no source attribution')."""
        from src.db import CharityData
        from synthesize import apply_regression_guard

        prior = {
            "total_revenue": 1_000_000,
            "source_attribution": {
                "total_revenue": {"source_name": "Charity Navigator", "value": 1_000_000},
            },
        }
        synthesized = CharityData(charity_ein="12-3456789")
        synthesized.source_attribution = {}
        metrics = CharityData(charity_ein="12-3456789")
        metrics.source_attribution = {}
        flags = apply_regression_guard(synthesized, metrics, prior)

        assert metrics.total_revenue == 1_000_000
        assert synthesized.total_revenue == 1_000_000
        assert synthesized.source_attribution["total_revenue"] == {
            "source_name": "Charity Navigator",
            "value": 1_000_000,
        }
        assert flags == [{"charity_ein": "12-3456789", "field": "total_revenue", "prior_value": 1_000_000, "rejected": None}]

    def test_guard_restores_value_when_prior_attribution_missing(self):
        """Prior row predates attribution tracking (or never had it) -- the
        guard must still restore the value; it just can't add attribution
        that was never there."""
        from src.db import CharityData
        from synthesize import apply_regression_guard

        prior = {"total_revenue": 1_000_000}  # no source_attribution key at all
        synthesized = CharityData(charity_ein="12-3456789")
        metrics = CharityData(charity_ein="12-3456789")
        flags = apply_regression_guard(synthesized, metrics, prior)

        assert metrics.total_revenue == 1_000_000
        assert synthesized.total_revenue == 1_000_000
        assert flags == [{"charity_ein": "12-3456789", "field": "total_revenue", "prior_value": 1_000_000, "rejected": None}]

    def test_guard_allows_observed_absent_and_unguarded_fields(self):
        from src.db import CharityData
        from synthesize import apply_regression_guard

        prior = {
            "total_revenue": 1_000_000,
            "theory_of_change": "old story",
            "program_expense_ratio": 0.85,
        }
        synthesized = CharityData(charity_ein="12-3456789")
        synthesized.total_revenue = 1_000_000  # unchanged
        metrics = CharityData(charity_ein="12-3456789")
        metrics.total_revenue = 1_000_000  # unchanged
        # theory_of_change is NOT in the guarded set (website-derived, may legitimately drop)
        # program_expense_ratio is conditionally present (990-EZ small filers don't
        # break it out) -- no longer guarded, so a non-null -> null transition here
        # is a legitimate drop, not a restore target
        flags = apply_regression_guard(synthesized, metrics, prior)

        assert flags == []
        assert synthesized.theory_of_change is None  # not restored
        assert synthesized.program_expense_ratio is None  # not restored -- legitimate drop

    def test_guard_no_prior_row_is_noop(self):
        from src.db import CharityData
        from synthesize import apply_regression_guard

        synthesized = CharityData(charity_ein="12-3456789")
        metrics = CharityData(charity_ein="12-3456789")
        assert apply_regression_guard(synthesized, metrics, None) == []

    def test_guarded_fields_are_required_source_derived(self):
        import synthesize

        # Only the always-present top-line/balance-sheet fields are guarded --
        # every valid 990/990-EZ filing reports these, so a non-null -> null
        # transition is unambiguously a computation bug, never a legitimate drop.
        for f in ("total_revenue", "total_expenses", "total_assets", "total_liabilities", "net_assets"):
            assert f in synthesize.REGRESSION_GUARDED_FIELDS
        assert len(synthesize.REGRESSION_GUARDED_FIELDS) == 5

        # Functional-expense breakdown + derived ratios are conditionally present
        # on 990-EZ / small filers (not broken out there), so their nulls can be
        # legitimate -- they must NOT be guarded.
        for f in (
            "program_expense_ratio",
            "program_expenses",
            "admin_expenses",
            "fundraising_expenses",
            "working_capital_months",
        ):
            assert f not in synthesize.REGRESSION_GUARDED_FIELDS

        # metrics_json-only ratios derive from OPTIONAL 990 data (foreign grants /
        # GIK) and can legitimately drop to null — they must NOT be guarded at all,
        # and the dedicated frozenset for them must no longer exist.
        for f in ("noncash_ratio", "cash_adjusted_program_ratio", "domestic_burn_rate", "reserves_months"):
            assert f not in synthesize.REGRESSION_GUARDED_FIELDS
        assert not hasattr(synthesize, "REGRESSION_GUARDED_METRICS_FIELDS")
        # website-derived text fields must NOT be guarded (legit drops)
        assert "theory_of_change" not in synthesize.REGRESSION_GUARDED_FIELDS
        assert "populations_served" not in synthesize.REGRESSION_GUARDED_FIELDS

    def test_guard_restores_into_metrics_so_metrics_json_agrees_with_column(self):
        """The guard must restore into `metrics`, not just the synthesized column.

        Regression: EIN 31-1267559 shipped total_revenue=11342603 on the column
        while metrics_json.total_revenue was None, so the scorer saw no revenue
        and the size tier was derived as small_nonprofit on $11.3M.
        """
        from types import SimpleNamespace

        from synthesize import apply_regression_guard

        metrics = SimpleNamespace(total_revenue=None, total_expenses=None,
                                  total_assets=None, total_liabilities=None,
                                  net_assets=None, source_attribution={})
        synthesized = SimpleNamespace(charity_ein="31-1267559", total_revenue=None,
                                      total_expenses=None, total_assets=None,
                                      total_liabilities=None, net_assets=None,
                                      source_attribution={})
        prior = {"charity_ein": "31-1267559", "total_revenue": 11342603,
                 "source_attribution": {"total_revenue": {"source_name": "Charity Navigator"}}}

        flags = apply_regression_guard(synthesized, metrics, prior)

        assert metrics.total_revenue == 11342603, "restore must reach metrics (drives metrics_json + size tier)"
        assert synthesized.total_revenue == 11342603, "restore must also reach the column"
        assert [f["field"] for f in flags] == ["total_revenue"]

    def test_guard_does_not_fire_on_a_genuine_zero_in_metrics(self):
        """A real 0 is a value, not a regression -- the guard must leave it alone."""
        from types import SimpleNamespace

        from synthesize import apply_regression_guard

        metrics = SimpleNamespace(total_revenue=None, total_expenses=None,
                                  total_assets=None, total_liabilities=0,
                                  net_assets=None, source_attribution={})
        synthesized = SimpleNamespace(charity_ein="26-3342933", total_liabilities=None,
                                      total_revenue=None, total_expenses=None,
                                      total_assets=None, net_assets=None,
                                      source_attribution={})
        prior = {"charity_ein": "26-3342933", "total_liabilities": 861467, "source_attribution": {}}

        flags = apply_regression_guard(synthesized, metrics, prior)

        assert metrics.total_liabilities == 0, "a genuine 0 must survive"
        assert flags == [], "0 is not a non-null -> null regression"

    def test_guard_report_field_order_is_deterministic(self):
        """REGRESSION_GUARDED_FIELDS is a frozenset; iterate sorted so the report doesn't churn."""
        from types import SimpleNamespace

        from synthesize import apply_regression_guard

        def run():
            metrics = SimpleNamespace(total_revenue=None, total_expenses=None, total_assets=None,
                                      total_liabilities=None, net_assets=None, source_attribution={})
            synthesized = SimpleNamespace(charity_ein="12-3456789", total_revenue=None,
                                          total_expenses=None, total_assets=None,
                                          total_liabilities=None, net_assets=None,
                                          source_attribution={})
            prior = {"charity_ein": "12-3456789", "total_revenue": 1, "total_expenses": 2,
                     "total_assets": 3, "total_liabilities": 4, "net_assets": 5,
                     "source_attribution": {}}
            return [f["field"] for f in apply_regression_guard(synthesized, metrics, prior)]

        assert run() == sorted(run()), "flag order must be sorted, not frozenset iteration order"


def test_zero_financials_persist_as_zero_not_null():
    """A real 0 must reach the column. `int(x) if x else None` turned a debt-free
    charity's total_liabilities=0 into NULL on 18 live EINs."""
    from synthesize import _coerce_financial_column

    assert _coerce_financial_column(0) == 0
    assert _coerce_financial_column(0.0) == 0
    assert _coerce_financial_column(None) is None
    assert _coerce_financial_column(1131154) == 1131154
    assert _coerce_financial_column(11342603.0) == 11342603


class TestFinancialCoherence:
    def test_net_assets_above_total_assets_is_a_violation(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(5638, None, 10796)

    def test_a_coherent_balance_sheet_has_no_violations(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(28413661, 1131154, 27282507) == []

    def test_unknown_values_cannot_violate(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(None, None, None) == []
        assert balance_sheet_violations(None, None, 10796) == []

    def test_zero_liabilities_is_evaluated_not_skipped(self):
        """A genuine 0 is a value — Task A2 made sure it survives."""
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(5638, 0, 10796)
        assert balance_sheet_violations(5638, 0, 5638) == []

    def test_identity_allows_small_rounding_slack(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(1_000_000, 400_000, 600_001) == []
        assert balance_sheet_violations(1_000_000, 400_000, 900_000)

    def test_liabilities_exceeding_assets_is_not_a_violation(self):
        """Ordinary insolvency (net assets negative), not an impossible
        filing. Three live rows are exactly this, each with a perfect
        accounting identity -- flagging them would make the reconcile tool
        report correctly-filed data as incoherent."""
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(551681, 575178, -23497) == []
        assert balance_sheet_violations(74521, 276759, -202238) == []
        assert balance_sheet_violations(306342, 548013, -241671) == []

    def test_slack_calc_does_not_raise_on_decimal(self):
        """DoltDB history rows (fed by the reconcile tool) can hand this a
        Decimal; max(abs(x), 1.0) * ratio raised TypeError on that today."""
        from decimal import Decimal

        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(Decimal("551681"), Decimal("575178"), Decimal("-23497")) == []


class TestGuardRejectsIncoherentRestores:
    def _run(self, prior, current_metrics, no_filings=0):
        from types import SimpleNamespace

        from synthesize import apply_regression_guard
        metrics = SimpleNamespace(source_attribution={}, **current_metrics)
        synthesized = SimpleNamespace(charity_ein="81-3451645", source_attribution={},
                                      no_filings=no_filings, **current_metrics)
        flags = apply_regression_guard(synthesized, metrics, prior)
        return metrics, flags

    def test_restore_that_would_exceed_total_assets_is_rejected(self):
        """EIN 81-3451645 publishes net_assets 10796 against total_assets 5638."""
        metrics, flags = self._run(
            prior={"charity_ein": "81-3451645", "net_assets": 10796, "source_attribution": {}},
            current_metrics={"total_assets": 5638, "total_liabilities": None,
                             "net_assets": None, "total_revenue": 32150,
                             "total_expenses": None},
        )
        assert metrics.net_assets is None, "an incoherent restore must be refused"
        assert any(f.get("rejected") for f in flags), "and must still be reported"

    def test_a_coherent_restore_still_happens(self):
        # total_liabilities=1638 makes this triple self-consistent with the
        # restored net_assets=4000 (5638 - 1638 == 4000); the brief's original
        # fixture used 1000, which doesn't satisfy the balance-sheet identity
        # implemented in Step 3 and would make this "coherent" case spuriously
        # rejected. Fixed to actually exercise the coherent path.
        metrics, flags = self._run(
            prior={"charity_ein": "x", "net_assets": 4000, "source_attribution": {}},
            current_metrics={"total_assets": 5638, "total_liabilities": 1638,
                             "net_assets": None, "total_revenue": 32150,
                             "total_expenses": None},
        )
        assert metrics.net_assets == 4000
        assert not any(f.get("rejected") for f in flags)

    def test_no_filings_org_gets_no_financial_restore(self):
        """31-1267559 and 88-2454707 carry financials with no_filings=1 today."""
        metrics, flags = self._run(
            prior={"charity_ein": "31-1267559", "total_revenue": 11342603,
                   "source_attribution": {}},
            current_metrics={"total_assets": None, "total_liabilities": None,
                             "net_assets": None, "total_revenue": None,
                             "total_expenses": None},
            no_filings=1,
        )
        assert metrics.total_revenue is None
        assert any(f.get("rejected") for f in flags)

    def test_no_filings_gate_fires_off_metrics_in_production_shape(self):
        """Real incident: guard call site reads `synthesized.no_filings`, but
        `synthesized` is a bare CharityData(charity_ein=ein) at guard time --
        the only assignment to synthesized.no_filings happens 55 lines later
        in synthesize_charity(). At guard time it is always None, so the old
        `getattr(synthesized, "no_filings", None)` branch was dead code in
        production: the guard still restored $11.3M onto EIN 31-1267559 (a
        no_filings=1 org), flagged `rejected: None`.

        metrics.no_filings IS populated at guard time (aggregated well before
        the guard call). This test builds `synthesized` as the real
        src.db.repository.CharityData production uses -- not a SimpleNamespace
        pre-seeded with no_filings, which is the shape production never
        produces and the shape the old test fixture used to paper over this."""
        from types import SimpleNamespace

        from src.db.repository import CharityData
        from synthesize import apply_regression_guard

        synthesized = CharityData(charity_ein="31-1267559")  # no_filings NOT set -- production shape
        metrics = SimpleNamespace(
            no_filings=1, source_attribution={}, total_revenue=None, total_expenses=None,
            total_assets=None, total_liabilities=None, net_assets=None,
        )
        prior = {"charity_ein": "31-1267559", "total_revenue": 11342603, "source_attribution": {}}

        flags = apply_regression_guard(synthesized, metrics, prior)

        assert metrics.total_revenue is None, "no_filings org must not get financials invented"
        assert synthesized.total_revenue is None
        assert any(f.get("rejected") == "no_filings" for f in flags)


class TestSynthesizeCharityOrdering:
    def test_regression_guard_runs_before_metrics_json_dump_and_size_tier(self):
        """apply_regression_guard() must run before metrics_json is dumped and
        before nonprofit_size_tier is derived, or the two disagree with each
        other and with the exported column.

        Real incident: EIN 31-1267559 published total_revenue=11342603 on the
        column while metrics_json.total_revenue was None (the guard restored
        the column but ran too late to affect the metrics_json blob), and the
        size tier was derived as small_nonprofit on $11.3M of revenue. Moving
        the guard call earlier fixed it (commit a41f032); this test pins the
        ordering so it can't silently drift back.
        """
        import inspect

        import synthesize

        source = inspect.getsource(synthesize.synthesize_charity)

        guard_marker = "apply_regression_guard("
        metrics_json_marker = "metrics_json = metrics.model_dump("
        size_tier_marker = "# Determine nonprofit size tier"

        for marker in (guard_marker, metrics_json_marker, size_tier_marker):
            assert source.count(marker) == 1, (
                f"expected exactly one occurrence of {marker!r} in synthesize_charity; "
                "found a different count -- update this test's markers if the code "
                "was intentionally restructured"
            )

        guard_pos = source.index(guard_marker)
        metrics_json_pos = source.index(metrics_json_marker)
        size_tier_pos = source.index(size_tier_marker)

        assert guard_pos < metrics_json_pos, (
            "apply_regression_guard() must run before metrics_json is dumped, "
            "or a restored value won't make it into the metrics_json blob"
        )
        assert guard_pos < size_tier_pos, (
            "apply_regression_guard() must run before nonprofit_size_tier is "
            "derived, or the tier is computed from a pre-restore (possibly None) "
            "total_revenue"
        )


class TestRegressionReport:
    def test_writes_regressions_json(self, tmp_path):
        import json

        from synthesize import write_synthesize_regressions

        rows = [{"charity_ein": "12-3456789", "field": "program_expense_ratio", "prior_value": 0.85}]
        path = write_synthesize_regressions(rows, reports_dir=tmp_path)
        assert path.name == "synthesize-regressions.json"
        written = json.loads(path.read_text())
        assert written["rows"] == rows

    def test_empty_regressions_writes_empty_rows(self, tmp_path):
        import json

        from synthesize import write_synthesize_regressions

        path = write_synthesize_regressions([], reports_dir=tmp_path)
        assert json.loads(path.read_text())["rows"] == []

    def test_report_is_stamped_with_run_provenance(self, tmp_path):
        """A bare list was indistinguishable from a stale or single-EIN run;
        run_at/scope let a reader tell a fleet run apart from a later,
        narrower one that would otherwise silently look like a replacement."""
        import json

        from synthesize import write_synthesize_regressions

        path = write_synthesize_regressions([], reports_dir=tmp_path, scope=["12-3456789"])
        written = json.loads(path.read_text())
        assert written["scope"] == ["12-3456789"]
        assert "run_at" in written

    def test_no_scope_writes_null(self, tmp_path):
        """scope is null (not the string "fleet") when absent, so a reader
        never has to branch on list-vs-str to know whether a scope was
        recorded."""
        import json

        from synthesize import write_synthesize_regressions

        path = write_synthesize_regressions([], reports_dir=tmp_path)
        assert json.loads(path.read_text())["scope"] is None

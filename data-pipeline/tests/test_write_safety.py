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
        assert flags == [{"charity_ein": "12-3456789", "field": "total_revenue", "prior_value": 1_000_000}]

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
        assert flags == [{"charity_ein": "12-3456789", "field": "total_revenue", "prior_value": 1_000_000}]

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
        assert flags == [{"charity_ein": "12-3456789", "field": "total_revenue", "prior_value": 1_000_000}]

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
        assert written == rows

    def test_empty_regressions_writes_empty_list(self, tmp_path):
        import json

        from synthesize import write_synthesize_regressions

        path = write_synthesize_regressions([], reports_dir=tmp_path)
        assert json.loads(path.read_text()) == []

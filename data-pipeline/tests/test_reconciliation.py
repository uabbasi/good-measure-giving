"""Tests for the adversarial reconciliation phase."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetrics
from src.reconciliation.checks import (
    check_ceo_comp_excessive,
    check_excessive_reserves_non_zakat,
    check_geographic_mismatch,
    check_gik_inflated_ratio,
    check_high_fundraising_ratio,
    check_implausible_cpb,
    check_revenue_expense_mismatch,
    get_all_checks,
)
from src.reconciliation.completeness import patch_completeness
from src.reconciliation.reconciler import reconcile
from src.reconciliation.signals import SignalSeverity


def _make_metrics(**kwargs) -> CharityMetrics:
    defaults = {"ein": "12-3456789", "name": "Test Charity"}
    defaults.update(kwargs)
    return CharityMetrics(**defaults)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_all_checks_registered(self):
        checks = get_all_checks()
        expected = {
            "gik_inflated_ratio",
            "ceo_comp_excessive",
            "geographic_mismatch",
            "excessive_reserves_non_zakat",
            "high_fundraising_ratio",
            "implausible_cpb",
            "revenue_expense_mismatch",
        }
        assert set(checks.keys()) == expected

    def test_registry_returns_callables(self):
        for name, fn in get_all_checks().items():
            assert callable(fn), f"{name} is not callable"


# ---------------------------------------------------------------------------
# GIK Inflated Ratio
# ---------------------------------------------------------------------------


class TestGIKInflatedRatio:
    def test_high_noncash_fires(self):
        m = _make_metrics(noncash_ratio=0.60, program_expense_ratio=0.95)
        signals = check_gik_inflated_ratio(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.HIGH
        assert signals[0].check_name == "gik_inflated_ratio"

    def test_medium_noncash_fires(self):
        m = _make_metrics(noncash_ratio=0.30, program_expense_ratio=0.85)
        signals = check_gik_inflated_ratio(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.MEDIUM

    def test_low_noncash_no_signal(self):
        m = _make_metrics(noncash_ratio=0.10)
        assert check_gik_inflated_ratio(m) == []

    def test_none_noncash_no_signal(self):
        m = _make_metrics()
        assert check_gik_inflated_ratio(m) == []


# ---------------------------------------------------------------------------
# CEO Compensation
# ---------------------------------------------------------------------------


class TestCEOComp:
    def test_small_org_excessive(self):
        # $250K on $2M = 12.5% > 5% threshold
        m = _make_metrics(ceo_compensation=250_000, total_revenue=2_000_000)
        signals = check_ceo_comp_excessive(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.HIGH  # 12.5% >= 10% (2x threshold)

    def test_medium_org_excessive(self):
        # $469K on $7.2M = 6.5% > 2% threshold
        m = _make_metrics(ceo_compensation=469_000, total_revenue=7_200_000)
        signals = check_ceo_comp_excessive(m)
        assert len(signals) == 1

    def test_large_org_within_threshold(self):
        # $400K on $100M = 0.4% < 1% threshold
        m = _make_metrics(ceo_compensation=400_000, total_revenue=100_000_000)
        assert check_ceo_comp_excessive(m) == []

    def test_no_comp_data(self):
        m = _make_metrics(total_revenue=5_000_000)
        assert check_ceo_comp_excessive(m) == []


# ---------------------------------------------------------------------------
# Geographic Mismatch
# ---------------------------------------------------------------------------


class TestGeographicMismatch:
    def test_many_countries_no_schedule_f(self):
        m = _make_metrics(
            geographic_coverage=["Syria", "Yemen", "Somalia", "Pakistan", "Bangladesh"],
            domestic_burn_rate=None,
            grants_made=[],
        )
        signals = check_geographic_mismatch(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.MEDIUM

    def test_international_with_schedule_f(self):
        m = _make_metrics(
            geographic_coverage=["Syria", "Yemen", "Somalia", "Pakistan", "Bangladesh"],
            domestic_burn_rate=0.60,
        )
        assert check_geographic_mismatch(m) == []

    def test_few_countries_no_signal(self):
        m = _make_metrics(geographic_coverage=["US", "Canada"])
        assert check_geographic_mismatch(m) == []


# ---------------------------------------------------------------------------
# Excessive Reserves (Non-Zakat)
# ---------------------------------------------------------------------------


class TestExcessiveReserves:
    def test_high_reserves_fires(self):
        m = _make_metrics(reserves_months=48.0, claims_zakat=False)
        signals = check_excessive_reserves_non_zakat(m)
        assert len(signals) == 1

    def test_zakat_org_skipped(self):
        m = _make_metrics(reserves_months=48.0, claims_zakat=True)
        assert check_excessive_reserves_non_zakat(m) == []

    def test_endowment_skipped(self):
        m = _make_metrics(
            name="Test Endowment Fund",
            reserves_months=60.0,
            claims_zakat=False,
        )
        assert check_excessive_reserves_non_zakat(m) == []

    def test_moderate_reserves_no_signal(self):
        m = _make_metrics(reserves_months=24.0, claims_zakat=False)
        assert check_excessive_reserves_non_zakat(m) == []


# ---------------------------------------------------------------------------
# High Fundraising Ratio
# ---------------------------------------------------------------------------


class TestHighFundraising:
    def test_high_ratio_fires(self):
        m = _make_metrics(fundraising_expense_ratio=0.38)
        signals = check_high_fundraising_ratio(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.HIGH

    def test_medium_ratio_fires(self):
        m = _make_metrics(fundraising_expense_ratio=0.28)
        signals = check_high_fundraising_ratio(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.MEDIUM

    def test_derived_from_raw(self):
        m = _make_metrics(
            fundraising_expenses=3_000_000,
            total_expenses=10_000_000,
        )
        signals = check_high_fundraising_ratio(m)
        assert len(signals) == 1  # 30% > 25%

    def test_low_ratio_no_signal(self):
        m = _make_metrics(fundraising_expense_ratio=0.15)
        assert check_high_fundraising_ratio(m) == []


# ---------------------------------------------------------------------------
# Implausible CPB
# ---------------------------------------------------------------------------


class TestImplausibleCPB:
    def test_sub_dollar_fires(self):
        m = _make_metrics(total_expenses=1_000_000, beneficiaries_served_annually=5_000_000)
        signals = check_implausible_cpb(m)
        assert len(signals) == 1
        assert signals[0].data_points["cost_per_beneficiary"] == 0.20

    def test_reasonable_cpb_no_signal(self):
        m = _make_metrics(total_expenses=1_000_000, beneficiaries_served_annually=10_000)
        assert check_implausible_cpb(m) == []

    def test_missing_data_no_signal(self):
        m = _make_metrics(total_expenses=1_000_000)
        assert check_implausible_cpb(m) == []


# ---------------------------------------------------------------------------
# Revenue-Expense Mismatch
# ---------------------------------------------------------------------------


class TestRevenueExpenseMismatch:
    def test_double_expenses_fires(self):
        m = _make_metrics(total_revenue=1_000_000, total_expenses=2_500_000)
        signals = check_revenue_expense_mismatch(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.HIGH

    def test_moderate_mismatch_medium(self):
        m = _make_metrics(total_revenue=1_000_000, total_expenses=1_600_000)
        signals = check_revenue_expense_mismatch(m)
        assert len(signals) == 1
        assert signals[0].severity == SignalSeverity.MEDIUM

    def test_normal_no_signal(self):
        m = _make_metrics(total_revenue=1_000_000, total_expenses=1_200_000)
        assert check_revenue_expense_mismatch(m) == []


# ---------------------------------------------------------------------------
# Completeness Patching
# ---------------------------------------------------------------------------


class TestCompleteness:
    def test_noncash_ratio_rederived(self):
        m = _make_metrics(noncash_contributions=500_000, total_contributions=1_000_000)
        patched, gaps = patch_completeness(m)
        assert "noncash_ratio" in patched
        assert m.noncash_ratio == 0.5

    def test_cash_adjusted_ratio_rederived(self):
        m = _make_metrics(
            noncash_ratio=0.50,
            noncash_contributions=500_000,
            program_expenses=800_000,
            total_expenses=1_000_000,
        )
        patched, gaps = patch_completeness(m)
        assert "cash_adjusted_program_ratio" in patched
        # (800K - 500K) / (1M - 500K) = 300K / 500K = 0.6
        assert abs(m.cash_adjusted_program_ratio - 0.6) < 0.01

    def test_reserves_months_rederived(self):
        m = _make_metrics(net_assets=2_000_000, total_expenses=1_000_000)
        patched, gaps = patch_completeness(m)
        assert "reserves_months" in patched
        assert abs(m.reserves_months - 24.0) < 0.01

    def test_fundraising_ratio_rederived(self):
        m = _make_metrics(fundraising_expenses=200_000, total_expenses=1_000_000)
        patched, gaps = patch_completeness(m)
        assert "fundraising_expense_ratio" in patched
        assert abs(m.fundraising_expense_ratio - 0.2) < 0.01

    def test_gap_reported_when_partial_data(self):
        m = _make_metrics(noncash_contributions=500_000, total_contributions=0)
        patched, gaps = patch_completeness(m)
        assert "noncash_ratio" not in patched
        # total_contributions is 0, so division fails
        assert any("noncash_ratio" in g for g in gaps)

    def test_no_patches_when_complete(self):
        m = _make_metrics(
            noncash_ratio=0.3,
            cash_adjusted_program_ratio=0.7,
            domestic_burn_rate=0.5,
            reserves_months=12.0,
            fundraising_expense_ratio=0.15,
        )
        patched, gaps = patch_completeness(m)
        assert patched == []
        assert gaps == []


# ---------------------------------------------------------------------------
# Reconciler Integration
# ---------------------------------------------------------------------------


class TestReconciler:
    def test_full_reconciliation(self):
        """Penny Appeal-like case: high GIK + excessive CEO comp."""
        m = _make_metrics(
            noncash_ratio=0.60,
            program_expense_ratio=0.95,
            ceo_compensation=469_000,
            total_revenue=7_200_000,
            total_expenses=6_800_000,
            net_assets=500_000,
        )
        result = reconcile(m)
        check_names = {s.check_name for s in result.signals}
        assert "gik_inflated_ratio" in check_names
        assert "ceo_comp_excessive" in check_names
        # reserves_months should have been patched
        assert "reserves_months" in result.patched_fields

    def test_clean_charity_no_signals(self):
        m = _make_metrics(
            total_revenue=5_000_000,
            total_expenses=4_500_000,
            program_expenses=3_800_000,
            program_expense_ratio=0.84,
            noncash_ratio=0.05,
            ceo_compensation=80_000,  # 1.6% of $5M — below 2% threshold
            fundraising_expense_ratio=0.10,
            reserves_months=12.0,
        )
        result = reconcile(m)
        assert len(result.signals) == 0

    def test_signals_sorted_by_severity(self):
        m = _make_metrics(
            noncash_ratio=0.60,  # HIGH
            fundraising_expense_ratio=0.28,  # MEDIUM
            program_expense_ratio=0.90,
        )
        result = reconcile(m)
        assert len(result.signals) >= 2
        severities = [s.severity for s in result.signals]
        # HIGH should come before MEDIUM
        if SignalSeverity.HIGH in severities and SignalSeverity.MEDIUM in severities:
            first_high = severities.index(SignalSeverity.HIGH)
            last_medium = len(severities) - 1 - severities[::-1].index(SignalSeverity.MEDIUM)
            assert first_high < last_medium

    def test_contradiction_signals_serializable(self):
        """Signals must serialize to dicts for metrics_json storage."""
        m = _make_metrics(noncash_ratio=0.60, program_expense_ratio=0.95)
        result = reconcile(m)
        for signal in result.signals:
            d = signal.model_dump()
            assert isinstance(d, dict)
            assert "check_name" in d
            assert "severity" in d

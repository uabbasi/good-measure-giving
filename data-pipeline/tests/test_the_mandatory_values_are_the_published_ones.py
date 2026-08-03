"""The figures the narrative is ORDERED to use must be the figures we publish.

The rich prompt carries a "MANDATORY VALUES (USE EXACTLY - DO NOT CALCULATE
OR INVENT)" block, the strongest instruction in it. Those values come from
`charity_bundle.financials`, built by ReconciliationEngine._reconcile_financials,
which runs its own election over the raw sources with a hardcoded priority:

    Priority: ProPublica > Candid > Charity Navigator

That is a THIRD election over the same charity, alongside
extract_financials() and CharityMetricsAggregator.aggregate(). It reads raw
source rows directly and never consults the one the pipeline actually
published, so when ProPublica loses the real election the model is still
ordered to use ProPublica's number "exactly".

Measured on 2026-08-02: 57 published charities state a total revenue that is
not the published figure; 54 of them trace to ProPublica.

    13-1685039  CARE USA  published $832,911,696
                          MANDATORY VALUES said $909,098,267 (ProPublica FY2024)
                          narrative duly wrote $909,098,267

Withholding ProPublica from the *context* blocks did not fix this — CARE was
regenerated with that guard live and still quoted the figure, because this
block is a separate and more forceful channel.

The elected income statement wins. Raw-source priority stays as the fallback
for charities where the pipeline elected nothing.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.parameter_mapper import ParameterMapper  # noqa: E402
from src.services.reconciliation_engine import ReconciliationEngine  # noqa: E402

EIN = "13-1685039"

RAW = {
    "propublica": {"total_revenue": 909098267, "total_expenses": 800000000, "program_expenses": 700000000},
    "charity_navigator": {"total_revenue": 700000000},
}
ELECTED = {
    "total_revenue": 832911696,
    "total_expenses": 836532086,
    "program_expenses": 751224764,
}


def _engine(elected):
    eng = object.__new__(ReconciliationEngine)
    eng.mapper = ParameterMapper()
    eng.charity_data_repo = Mock()
    eng.charity_data_repo.get.return_value = (
        {"metrics_json": dict(elected, financial_data_source="irs_990")} if elected else {}
    )
    return eng


def test_the_published_revenue_wins_over_propublica():
    fin = _engine(ELECTED)._reconcile_financials(RAW, EIN)

    assert fin.total_revenue == 832911696, "the model would be ordered to use a figure we do not publish"


def test_the_whole_income_statement_moves_together():
    """Half-elected figures would put one year's numerator over another's denominator."""
    fin = _engine(ELECTED)._reconcile_financials(RAW, EIN)

    assert fin.total_expenses == 836532086
    assert fin.program_expenses == 751224764


def test_raw_priority_still_applies_when_nothing_was_elected():
    """Charities the aggregator never elected for must keep working."""
    fin = _engine(None)._reconcile_financials(RAW, EIN)

    assert fin.total_revenue == 909098267


def test_fields_the_election_did_not_set_fall_back_to_raw():
    """total_assets is not an elected income-statement field."""
    raw = dict(RAW)
    raw["propublica"] = dict(raw["propublica"], total_assets=123456789)
    fin = _engine(ELECTED)._reconcile_financials(raw, EIN)

    assert fin.total_revenue == 832911696
    assert fin.total_assets == 123456789


def test_the_ratio_is_recomputed_from_the_elected_components():
    """Otherwise a stale quotient sits over fresh components."""
    fin = _engine(ELECTED)._reconcile_financials(RAW, EIN)

    assert abs(fin.program_expense_ratio - (751224764 / 836532086)) < 0.001

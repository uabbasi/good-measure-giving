"""Tests for the deterministic claim-currency check (B-J-012) in BaselineQualityJudge.

The check flags baseline narratives that cite stale fiscal years as current
financials — the shipped-bug class that once hit 132/160 charities ("FY2022
revenue grew..." when FY2024 data exists).

Two precision tiers:
- HIGH  -> ERROR   (FY20xx / "20xx revenue|expenses|fiscal year", older than latest)
- LOW   -> WARNING (any older 20xx near trend words: grew/increased/declined/revenue/expenses)
Founding/history contexts (founded/since/established...) are excluded.
Unknown fiscal_year is a no-op.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.baseline_quality_judge import BaselineQualityJudge
from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import Severity


def _judge() -> BaselineQualityJudge:
    return BaselineQualityJudge(JudgeConfig())


def _context(fiscal_year):
    # fiscal year lives inside metrics_json (financial_data_tax_year), like the live DB row.
    return {"charity_data": {"metrics_json": {"financial_data_tax_year": fiscal_year}}}


def _narr(**fields):
    return {"baseline_narrative": fields}


def _run(narrative_fields, fiscal_year):
    judge = _judge()
    evaluation = {"baseline_narrative": narrative_fields}
    return judge._check_claim_currency("00-0000000", evaluation, _context(fiscal_year))


class TestHighPrecisionError:
    def test_stale_fy_prefix_is_error(self):
        issues = _run({"summary": "In FY2022 revenue grew sharply to a record high."}, fiscal_year=2024)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "2022" in errors[0].message
        assert errors[0].issue_key == "claim_currency_stale_fy:2022"

    def test_stale_year_revenue_adjacency_is_error(self):
        issues = _run({"summary": "The charity's 2021 revenue was its largest ever."}, fiscal_year=2024)
        assert any(i.severity == Severity.ERROR for i in issues)

    def test_stale_year_expenses_adjacency_is_error(self):
        issues = _run({"strengths": ["Strong 2020 expenses discipline noted."]}, fiscal_year=2024)
        assert any(i.severity == Severity.ERROR for i in issues)


class TestFoundingExclusion:
    def test_founded_year_not_flagged(self):
        issues = _run({"summary": "Founded in 2003, the charity has grown its revenue steadily."}, fiscal_year=2024)
        # 'grew/revenue' near 2003 would tempt the LOW tier, but the founding guard excludes it.
        assert not any(i.severity == Severity.ERROR for i in issues)
        stale_2003 = [i for i in issues if "2003" in i.message]
        assert stale_2003 == []

    def test_since_year_history_not_flagged(self):
        issues = _run({"summary": "Since 2010, expenses have increased with program scale."}, fiscal_year=2024)
        assert not any("2010" in i.message for i in issues)

    def test_established_year_not_flagged(self):
        issues = _run({"summary": "Established in 2015; revenue reporting is transparent."}, fiscal_year=2024)
        assert not any("2015" in i.message for i in issues)


class TestCurrentFiscalYearSilent:
    def test_current_fy_no_issue(self):
        issues = _run({"summary": "In FY2024 revenue grew to a record high."}, fiscal_year=2024)
        assert issues == []

    def test_future_year_no_issue(self):
        issues = _run({"summary": "FY2025 revenue is projected to increase."}, fiscal_year=2024)
        assert issues == []


class TestUnknownFiscalYearNoOp:
    def test_none_fiscal_year_is_noop(self):
        issues = _run({"summary": "In FY2019 revenue grew sharply."}, fiscal_year=None)
        assert issues == []

    def test_missing_charity_data_is_noop(self):
        judge = _judge()
        evaluation = {"baseline_narrative": {"summary": "FY2019 revenue grew."}}
        assert judge._check_claim_currency("00-0000000", evaluation, {}) == []


class TestWarningTier:
    def test_trend_word_near_stale_year_is_warning(self):
        # "In 2019, ... revenue increased" -> no FY prefix, no "2019 revenue" adjacency,
        # but 2019 (< 2024) sits near trend words -> WARNING, not ERROR.
        issues = _run({"summary": "In 2019, program revenue increased across regions."}, fiscal_year=2024)
        assert not any(i.severity == Severity.ERROR for i in issues)
        warnings = [i for i in issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "2019" in warnings[0].message
        assert warnings[0].issue_key == "claim_currency_stale_fy:2019"

    def test_stale_year_without_trend_word_not_flagged(self):
        issues = _run({"summary": "A milestone conference was held in 2018 for volunteers."}, fiscal_year=2024)
        assert issues == []

    def test_citation_urls_not_scanned(self):
        # all_citations subtree (urls/source_name with year tokens) must be ignored.
        narrative = {
            "summary": "Operations are efficient.",
            "all_citations": [
                {"id": "[1]", "source_name": "2019 Annual Report", "source_url": "https://x.org/2018/report"}
            ],
        }
        assert _run(narrative, fiscal_year=2024) == []

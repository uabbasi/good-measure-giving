"""Income-statement citations must name the source that supplied the number.

synthesize runs two independent financial elections over the same charity:

  line 1630  CharityMetricsAggregator.aggregate(...)  -- fiscal-year aware:
             when PP and CN report different years and PP is thin, CN wins
             ALL income-statement fields.
  line 1683  extract_financials(...)                  -- PP-first, CN only as
             a fallback for fields PP left None.

The aggregator wins the columns (line 2141 overwrites them, with a comment
saying so). extract_financials keeps the attribution -- nothing ever revises
it. So the loser of the election supplies the citations.

Observed on EIN 87-2410117: charity_data.total_revenue held $35,399,389 (CN
FY2024) while source_attribution.total_revenue said "Form 990 (2023)" with
value $10,889,699 -- the column and its own provenance disagreeing inside one
row, the same shape as the metrics_json/scalar-column split.

Downstream, the narrative cites "Form 990 (2023)" for a Charity Navigator
FY2024 figure; the citation judge fetches the 990, finds $10.9M, and correctly
reports a contradiction. 24 such errors across 13 of the 19 charities blocked
from export.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthesize import realign_income_statement_attribution


def _pp_attribution(value):
    return {
        "source_name": "Form 990 (2023)",
        "source_url": "https://projects.propublica.org/nonprofits/organizations/872410117",
        "value": value,
    }


def _metrics(source, tax_year=2024):
    return SimpleNamespace(
        financial_data_source=source,
        financial_data_tax_year=tax_year,
        total_revenue=35399389,
        total_expenses=30075000,
        program_expenses=15127413,
        admin_expenses=4111574,
        fundraising_expenses=10836013,
    )


class TestCharityNavigatorWonTheElection:
    def _run(self):
        attr = {
            "total_revenue": _pp_attribution(10889699),
            "program_expenses": _pp_attribution(5000000),
            "mission": {"source_name": "Candid", "value": "x"},
        }
        realign_income_statement_attribution(attr, _metrics("charity_navigator"), "87-2410117")
        return attr

    def test_citation_names_charity_navigator(self):
        attr = self._run()
        assert "990" not in attr["total_revenue"]["source_name"]
        assert "Charity Navigator" in attr["total_revenue"]["source_name"]

    def test_attributed_value_matches_the_persisted_column(self):
        attr = self._run()
        assert attr["total_revenue"]["value"] == 35399389
        assert attr["program_expenses"]["value"] == 15127413

    def test_url_points_at_charity_navigator(self):
        attr = self._run()
        assert "charitynavigator.org" in attr["total_revenue"]["source_url"]

    def test_non_financial_attribution_is_untouched(self):
        attr = self._run()
        assert attr["mission"] == {"source_name": "Candid", "value": "x"}

    def test_fields_the_aggregator_left_none_are_not_invented(self):
        attr = {}
        m = _metrics("charity_navigator")
        m.admin_expenses = None
        realign_income_statement_attribution(attr, m, "87-2410117")
        assert "admin_expenses" not in attr


class TestOtherElectionsAreLeftAlone:
    """PP-first and mixed already agree with extract_financials' policy."""

    def test_propublica_win_keeps_the_990_citation(self):
        attr = {"total_revenue": _pp_attribution(10889699)}
        realign_income_statement_attribution(attr, _metrics("propublica"), "87-2410117")
        assert attr["total_revenue"]["source_name"] == "Form 990 (2023)"

    def test_mixed_is_left_alone(self):
        attr = {"total_revenue": _pp_attribution(10889699)}
        realign_income_statement_attribution(attr, _metrics("mixed"), "87-2410117")
        assert attr["total_revenue"]["source_name"] == "Form 990 (2023)"

    def test_unknown_source_is_left_alone(self):
        attr = {"total_revenue": _pp_attribution(10889699)}
        realign_income_statement_attribution(attr, _metrics(None), "87-2410117")
        assert attr["total_revenue"]["source_name"] == "Form 990 (2023)"

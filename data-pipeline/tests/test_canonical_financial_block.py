"""End-to-end guards for the canonical financial block, through aggregate().

test_canonical_financial_source.py covers the election in isolation. These run
the real aggregator over the four shapes that were actually publishing wrong
numbers, and assert on what a page would show.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator


def _aggregate(pp=None, cn=None, ein="00-0000000"):
    return CharityMetricsAggregator.aggregate(
        charity_id=1, ein=ein, propublica_990=pp, cn_profile=cn
    )


class TestSameYearDisagreement:
    """EIN 83-1171525 Link Outside — live with program_expenses 7.8x total."""

    PP = {
        "tax_year": 2023, "total_revenue": 129820, "total_expenses": 102250,
        "total_assets": 109085, "total_liabilities": 0,
    }
    CN = {
        "fiscal_year": 2023, "total_revenue": 129820, "total_expenses": 900000,
        "program_expenses": 800000,
    }

    def test_the_filing_wins_whole(self):
        m = _aggregate(self.PP, self.CN)
        assert m.financial_data_source == "propublica"
        assert m.total_expenses == 102250

    def test_the_disagreeing_breakdown_is_not_spliced_in(self):
        """This is the bug: CN's 800,000 program figure was published against
        PP's 102,250 total. A component may not exceed its own total."""
        m = _aggregate(self.PP, self.CN)
        assert m.program_expenses is None
        assert m.program_expenses is None or m.program_expenses <= m.total_expenses

    def test_the_disagreement_is_recorded_not_silently_dropped(self):
        m = _aggregate(self.PP, self.CN)
        reasons = {d["reason"] for d in m.financial_source_discrepancies}
        assert "same_fiscal_year_disagreement" in reasons
        entry = next(
            d for d in m.financial_source_discrepancies
            if d["reason"] == "same_fiscal_year_disagreement"
        )
        assert entry["canonical_value"] == 102250
        assert entry["other_value"] == 900000

    def test_a_field_the_sources_agree_on_is_not_reported_as_a_disagreement(self):
        m = _aggregate(self.PP, self.CN)
        assert not [
            d for d in m.financial_source_discrepancies if d.get("field") == "total_revenue"
        ]


class TestStaleAlternateSource:
    """EIN 83-1794093 Hikma Health — published Charity Navigator's FY2019."""

    PP = {"tax_year": 2023, "total_revenue": 273780, "total_expenses": 250000,
          "total_assets": 116544, "total_liabilities": 0}
    CN = {"fiscal_year": 2019, "total_revenue": 273780, "total_expenses": 79436,
          "program_expenses": 79436, "admin_expenses": 0, "fundraising_expenses": 0}

    def test_the_newer_filing_is_published(self):
        m = _aggregate(self.PP, self.CN)
        assert m.financial_data_tax_year == 2023
        assert m.total_expenses == 250000

    def test_the_missing_breakdown_explains_itself(self):
        """Declining CN costs the page its functional-expense split, so the
        reason is recorded rather than leaving a blank."""
        m = _aggregate(self.PP, self.CN)
        entry = next(
            d for d in m.financial_source_discrepancies
            if d["reason"] == "alternate_source_is_staler"
        )
        assert entry["other_fiscal_year"] == 2019
        assert entry["fiscal_year"] == 2023


class TestTheBalanceSheetStaysWithTheFiling:
    """Charity Navigator wins most income statements because ProPublica omits
    the functional-expense breakdown. Its balance sheet is a different matter:
    18 of the 123 it publishes are visibly corrupt against 2 of ProPublica's.
    """

    PP = {"tax_year": 2023, "total_revenue": 400000, "total_expenses": 474737,
          "total_assets": 306342, "total_liabilities": 548013}

    def test_a_corrupt_cn_balance_sheet_never_displaces_the_filing(self):
        """EIN 84-5191730 The Mecca Center: CN reports $13,034 of annual
        expenses against $7,038,771 of assets — 3,694 months of reserves."""
        cn = {"fiscal_year": 2024, "total_revenue": 500000, "total_expenses": 13034,
              "program_expenses": 10000, "admin_expenses": 2000,
              "fundraising_expenses": 1034, "total_assets": 7038771,
              "total_liabilities": 3026599}
        m = _aggregate(self.PP, cn)
        assert m.financial_data_source == "charity_navigator"
        assert m.total_assets == 306342
        assert m.total_liabilities == 548013
        assert m.balance_sheet_tax_year == 2023

    def test_the_year_gap_is_declared_so_nothing_derives_across_it(self):
        cn = {"fiscal_year": 2024, "total_revenue": 13000000, "total_expenses": 12707276,
              "program_expenses": 11000000, "admin_expenses": 1000000,
              "fundraising_expenses": 700000}
        m = _aggregate(self.PP, cn)
        assert m.financial_data_tax_year == 2024
        assert m.balance_sheet_tax_year == 2023
        assert m.balance_sheet_tax_year != m.financial_data_tax_year

    def test_a_single_source_charity_is_coherent_by_construction(self):
        m = _aggregate(self.PP, None)
        assert m.balance_sheet_tax_year == m.financial_data_tax_year == 2023

    def test_cn_is_used_only_when_the_filing_has_no_balance_sheet_at_all(self):
        pp = {"tax_year": 2023, "total_revenue": 400000, "total_expenses": 474737}
        cn = {"fiscal_year": 2024, "total_assets": 9999999, "total_liabilities": 1}
        m = _aggregate(pp, cn)
        assert m.total_assets == 9999999
        assert m.balance_sheet_tax_year == 2024

    def test_two_balance_sheets_are_never_spliced_field_by_field(self):
        """PP reports assets but not liabilities. Borrowing CN's liabilities
        would net one year's assets against another year's debts."""
        pp = {"tax_year": 2023, "total_revenue": 400000, "total_expenses": 474737,
              "total_assets": 306342}
        cn = {"fiscal_year": 2024, "total_assets": 7038771, "total_liabilities": 3026599}
        m = _aggregate(pp, cn)
        assert m.total_assets == 306342
        assert m.total_liabilities is None
        assert m.balance_sheet_tax_year == 2023


class TestTheOrdinaryCaseIsUnchanged:
    """134 of 168 charities: CN a year newer and complete. Still wins."""

    def test_cn_still_supplies_the_breakdown_pp_omits(self):
        pp = {"tax_year": 2023, "total_revenue": 1000000, "total_expenses": 900000,
              "total_assets": 500000, "total_liabilities": 100000}
        cn = {"fiscal_year": 2024, "total_revenue": 1200000, "total_expenses": 1100000,
              "program_expenses": 900000, "admin_expenses": 120000,
              "fundraising_expenses": 80000, "total_assets": 600000,
              "total_liabilities": 150000}
        m = _aggregate(pp, cn)
        assert m.financial_data_source == "charity_navigator"
        assert m.program_expenses == 900000
        assert m.total_expenses == 1100000
        assert m.financial_source_discrepancies == []

    def test_same_year_agreement_still_gap_fills(self):
        pp = {"tax_year": 2024, "total_revenue": 1200000, "total_expenses": 1100000,
              "total_assets": 600000, "total_liabilities": 150000}
        cn = {"fiscal_year": 2024, "total_revenue": 1200000, "total_expenses": 1100000,
              "program_expenses": 900000}
        m = _aggregate(pp, cn)
        assert m.financial_data_source == "mixed"
        assert m.program_expenses == 900000
        assert m.total_expenses == 1100000
        assert m.balance_sheet_tax_year == 2024

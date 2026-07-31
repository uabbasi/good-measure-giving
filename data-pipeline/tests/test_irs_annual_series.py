"""The trend behind the headline must reach the year in the headline.

Electing the filing moved EIN 81-2169685's income statement to FY2025
($3,851,438) while the revenue trend the rich narrative discusses still ended
at FY2024 ($4,243,273, and $3,387,088 before that). Both figures are true; the
page presented both as current, and the score judge read that as a
contradiction. The headline had moved a year ahead of the series behind it.

The series already exists in data we fetch. _irs_filings pulls up to three
filings and the parser reads each one's financials — then keeps the newest and
discards the rest, so three years of revenue were parsed and thrown away on
every charity.

The series is published only when the filing also won the income statement, so
the headline and the years behind it always come from one source. Where a
mirror won, emitting an IRS series would reintroduce exactly the split this
fixes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

IRS = {
    "tax_year": 2025,
    "total_revenue": 3851438,
    "total_expenses": 3402000,
    "program_expenses": 2900000,
    "admin_expenses": 300000,
    "fundraising_expenses": 202000,
    "annual_financials": [
        {"fiscal_year": 2025, "total_revenue": 3851438, "total_expenses": 3402000},
        {"fiscal_year": 2024, "total_revenue": 4243273, "total_expenses": 3900000},
        {"fiscal_year": 2023, "total_revenue": 4520145, "total_expenses": 4100000},
    ],
}
PP = {"tax_year": 2023, "total_revenue": 4520145, "total_expenses": 4100000}
CN = {"fiscal_year": 2023, "total_revenue": 4520145, "total_expenses": 4100000,
      "program_expenses": 3500000}


def _metrics(grants=IRS, pp=PP, cn=CN):
    return CharityMetricsAggregator.aggregate(
        charity_id=1, ein="81-2169685", propublica_990=pp, cn_profile=cn,
        grants_profile=grants,
    )


class TestTheSeriesReachesTheHeadline:
    def test_the_filing_won(self):
        assert _metrics().financial_data_tax_year == 2025

    def test_the_series_is_published(self):
        assert _metrics().annual_financials

    def test_it_contains_the_year_in_the_headline(self):
        m = _metrics()
        years = [row["fiscal_year"] for row in m.annual_financials]
        assert m.financial_data_tax_year in years

    def test_it_is_newest_first(self):
        years = [row["fiscal_year"] for row in _metrics().annual_financials]
        assert years == sorted(years, reverse=True)

    def test_the_headline_figure_agrees_with_its_own_row(self):
        """The invariant that failed: the trend disagreeing with the top line."""
        m = _metrics()
        row = next(r for r in m.annual_financials
                   if r["fiscal_year"] == m.financial_data_tax_year)
        assert row["total_revenue"] == m.total_revenue

    def test_the_older_years_are_carried_not_dropped(self):
        years = [row["fiscal_year"] for row in _metrics().annual_financials]
        assert 2024 in years and 2023 in years


class TestItIsNotPublishedWhenAMirrorWon:
    def test_a_series_from_the_losing_source_is_withheld(self):
        """CN wins on recency here; an IRS series would put FY2023 rows under
        an FY2024 headline — the same split, rebuilt."""
        cn_newer = {"fiscal_year": 2024, "total_revenue": 9000000,
                    "total_expenses": 8000000, "program_expenses": 7000000,
                    "admin_expenses": 600000, "fundraising_expenses": 400000}
        older_irs = {**IRS, "tax_year": 2023,
                     "annual_financials": [{"fiscal_year": 2023, "total_revenue": 4520145}]}
        m = _metrics(grants=older_irs, cn=cn_newer)
        assert m.financial_data_tax_year == 2024
        assert not m.annual_financials

    def test_no_filing_means_no_series(self):
        assert not _metrics(grants=None).annual_financials

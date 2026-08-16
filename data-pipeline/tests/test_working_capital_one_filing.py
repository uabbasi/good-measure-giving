"""Working capital must describe one filing, and say which.

The stored figure took net assets, liabilities AND expenses from ProPublica
regardless of which source won the published income statement. It was coherent
with itself and with nothing on the page: 103 of 169 charities showed a reserves
number that did not divide out against the expenses printed beside it.

  82-3547632 Humaniti     stored -6.10 months; the published figures give -0.2
  84-5191730 Mecca Center stored  124  months; the published figures give 3,149

The fix is not to drop the figure when the sources straddle two years. Net
assets and expenses from the same 990 are a correct statement about that year,
and 25 charities would otherwise lose all 7 points of Financial Health
(_score_financial_health returns UNKNOWN/0 on a null) over a gap in our sources
rather than in their finances. The figure is kept, pinned to the year it
actually describes, and the mismatch is recorded.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthesize import calculate_working_capital_months, resolve_working_capital


def _metrics(income_year, balance_year, assets, liabilities, expenses, source="charity_navigator"):
    return SimpleNamespace(
        financial_data_tax_year=income_year,
        balance_sheet_tax_year=balance_year,
        total_assets=assets,
        total_liabilities=liabilities,
        total_expenses=expenses,
        financial_data_source=source,
    )


class TestOneFilingOnBothSides:
    def test_the_ordinary_coherent_case(self):
        m = _metrics(2024, 2024, 2_000_000, 500_000, 12_000_000)
        months, year, off_year = resolve_working_capital(m)
        assert months == 1.5
        assert year == 2024
        assert not off_year

    def test_it_uses_the_published_expenses_not_propublicas(self):
        """The Humaniti shape. ProPublica's $474,737 is what the old code
        divided by; the page shows Charity Navigator's $12,707,276."""
        m = _metrics(2024, 2024, 306_342, 548_013, 12_707_276)
        months, _, off_year = resolve_working_capital(m, {"total_expenses": 474_737})
        assert not off_year
        assert months == calculate_working_capital_months(306_342, 548_013, 12_707_276)
        assert months != calculate_working_capital_months(306_342, 548_013, 474_737)


class TestStraddlingTwoYears:
    """CN won the FY2024 income statement but has no balance sheet; the one we
    hold is ProPublica's FY2023."""

    M = _metrics(2024, 2023, 306_342, 548_013, 12_707_276)

    def test_the_figure_is_kept_and_pinned_to_its_own_year(self):
        months, year, off_year = resolve_working_capital(self.M, {"total_expenses": 474_737})
        assert off_year
        assert year == 2023
        assert months == calculate_working_capital_months(306_342, 548_013, 474_737)

    def test_it_does_not_silently_divide_across_the_two_years(self):
        months, _, _ = resolve_working_capital(self.M, {"total_expenses": 474_737})
        assert months != calculate_working_capital_months(306_342, 548_013, 12_707_276)

    def test_no_expenses_in_the_balance_sheet_year_yields_nothing(self):
        """Better absent than invented."""
        months, year, off_year = resolve_working_capital(self.M, {"total_expenses": None})
        assert months is None and year is None and off_year


class TestDegenerateInputs:
    def test_a_missing_year_on_either_side_is_treated_as_coherent(self):
        months, _, off_year = resolve_working_capital(_metrics(None, 2023, 100, 0, 1200))
        assert not off_year and months == 1.0
        months, _, off_year = resolve_working_capital(_metrics(2023, None, 100, 0, 1200))
        assert not off_year and months == 1.0

    def test_zero_expenses_is_not_a_division(self):
        months, _, _ = resolve_working_capital(_metrics(2024, 2024, 100, 0, 0))
        assert months is None

    def test_no_balance_sheet_at_all_is_not_a_zero_balance(self):
        """Both assets and liabilities missing must not compute as $0 - $0."""
        assert calculate_working_capital_months(None, None, 1_200_000) is None

    def test_one_side_of_the_balance_sheet_present_still_computes(self):
        assert calculate_working_capital_months(100, None, 1200) == 1.0
        assert calculate_working_capital_months(None, 100, 1200) == -1.0

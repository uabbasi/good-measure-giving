"""A reported 0 for an expense component must be corroborated before we publish it.

Charity Navigator emits 0 both for a genuine zero and for a figure the filing
did not break out, and the value alone cannot tell them apart. Cross-source
resolution does not work here: all 35 affected charities have
fundraising_expenses=None in ProPublica, which does not expose the Part IX
functional-expense breakdown for these filings.

Arithmetic does tell them apart. If the component truly is 0, the remaining
components sum to total_expenses. If the 0 stands in for an unreported figure,
they fall short by exactly that figure. Measured over the 35: 25 close exactly,
5 leave a residual (26-3531888 leaves 94% of expenses unaccounted), 5 have no
component breakdown to test against.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import zero_expense_component_is_corroborated as ok


class TestZeroExpenseCorroboration:
    def test_components_closing_exactly_corroborate_the_zero(self):
        """11-3013369: program 2,947,147 + admin 0 + fundraising 0 = total."""
        c = {"program_expenses": 2947147, "admin_expenses": 0, "fundraising_expenses": 0}
        assert ok("fundraising_expenses", c, 2947147) is True

    def test_small_rounding_residual_still_corroborates(self):
        """20-3069841 closes to within -0.12%."""
        c = {"program_expenses": 119155737, "admin_expenses": 148326, "fundraising_expenses": 0}
        assert ok("fundraising_expenses", c, 119155737 + 148326 - 100) is True

    def test_large_shortfall_refuses_the_zero(self):
        """26-3531888: 94% of expenses unaccounted — the 0 hides a real figure."""
        c = {"program_expenses": 213084, "admin_expenses": 0, "fundraising_expenses": 0}
        assert ok("fundraising_expenses", c, 3773142) is False

    def test_components_exceeding_the_total_refuse_the_zero(self):
        """Overshoot is its own inconsistency — never read it as corroboration."""
        c = {"program_expenses": 3000000, "admin_expenses": 774779, "fundraising_expenses": 0}
        assert ok("fundraising_expenses", c, 2640174) is False

    def test_missing_sibling_component_refuses_the_zero(self):
        """No breakdown means nothing to check against."""
        c = {"program_expenses": None, "admin_expenses": None, "fundraising_expenses": 0}
        assert ok("fundraising_expenses", c, 1014590) is False

    def test_absent_total_refuses_the_zero(self):
        c = {"program_expenses": 100, "admin_expenses": 0, "fundraising_expenses": 0}
        assert ok("fundraising_expenses", c, None) is False
        assert ok("fundraising_expenses", c, 0) is False

    def test_a_nonzero_value_is_not_this_functions_business(self):
        """Only zeros are ambiguous; a real number needs no corroboration."""
        c = {"program_expenses": 100, "admin_expenses": 0, "fundraising_expenses": 50}
        assert ok("fundraising_expenses", c, 150) is False

    def test_works_for_program_and_admin_components_too(self):
        c = {"program_expenses": 0, "admin_expenses": 500, "fundraising_expenses": 500}
        assert ok("program_expenses", c, 1000) is True
        assert ok("program_expenses", c, 9999) is False

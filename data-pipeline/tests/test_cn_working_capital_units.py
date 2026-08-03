"""Charity Navigator states working capital in YEARS. We store MONTHS.

Two of the three extraction paths convert it (`years * 12`, charity_navigator.py
:826 and :953). The third — the LLM fallback — does not: its prompt asks for
`"working_capital_ratio": <decimal or null>` and names no unit, so the model
copies what the page shows. The field then means years for some charities and
months for the rest.

Six charities carry an unconverted value:

  23-7065716 Islamic Society of Greater Houston   3.25   ->  39.0 months
  90-0327815 The Morocco Foundation               2.82   ->  33.9 months
  83-0668931 Islamic Society of Southern Illinois 1      ->  12.0 months
  82-1670588 BASMAH                               0.11   ->   1.3 months
  88-3709826 Saylani Welfare Trust USA            0.04   ->   0.9 months
  20-3069841 Against Malaria Foundation           0      ->   0.0 months

It is not only a display problem. The aggregator gap-fills the field as if it
were months, so a charity with no computed working capital publishes a twelvefold
understatement of its reserves — and the figure is handed to the factual judge as
ground truth, which is how ISGH got blocked: the judge read our 39.0 months
against Charity Navigator's "3.25" and called it a contradiction, when 3.25 years
IS 39.0 months.

Prompt guidance alone is not the fix here; this file is full of precedents where
it did not hold. The value is normalized against arithmetic the page itself
supplies: net_assets / total_expenses is the ratio in years.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.charity_navigator import CharityNavigatorCollector


def _normalize(financials):
    return CharityNavigatorCollector.normalize_working_capital_units(dict(financials))


class TestAnUnconvertedValueIsFixed:
    def test_the_isgh_case(self):
        out = _normalize({
            "working_capital_ratio": 3.25,
            "net_assets": 43407000,
            "total_expenses": 13351984,
        })
        assert out["working_capital_ratio"] == 39.0

    def test_the_morocco_case(self):
        out = _normalize({
            "working_capital_ratio": 2.82,
            "net_assets": 282000,
            "total_expenses": 100000,
        })
        assert out["working_capital_ratio"] == 33.8

    def test_a_whole_year(self):
        out = _normalize({
            "working_capital_ratio": 1.0,
            "net_assets": 100000,
            "total_expenses": 100000,
        })
        assert out["working_capital_ratio"] == 12.0


class TestAnAlreadyConvertedValueIsLeftAlone:
    """The structured paths already multiply by 12. Doing it twice is the same
    bug pointed the other way."""

    def test_months_are_not_multiplied_again(self):
        out = _normalize({
            "working_capital_ratio": 39.0,
            "net_assets": 43407000,
            "total_expenses": 13351984,
        })
        assert out["working_capital_ratio"] == 39.0

    def test_a_small_but_genuine_month_count_survives(self):
        """1.3 months against a 0.108-year ratio: already months, leave it."""
        out = _normalize({
            "working_capital_ratio": 1.3,
            "net_assets": 10800,
            "total_expenses": 100000,
        })
        assert out["working_capital_ratio"] == 1.3


class TestItRefusesToGuess:
    def test_no_basis_means_no_change(self):
        """Without net assets and expenses the units are unknowable, and a
        silent 12x is worse than an inconsistent one."""
        out = _normalize({"working_capital_ratio": 3.25})
        assert out["working_capital_ratio"] == 3.25

    def test_a_value_between_the_two_readings_is_untouched(self):
        """Charity Navigator may count only unrestricted net assets, so a figure
        BELOW net assets is a methodology difference, not an error."""
        out = _normalize({
            "working_capital_ratio": 7.0,
            "net_assets": 43407000,
            "total_expenses": 13351984,
        })
        assert out["working_capital_ratio"] == 7.0


class TestAnImpossibleValueIsDropped:
    """Working capital is a subset of net assets, so it cannot buy more months
    than net assets do. EIN 20-1799252 came back with 39 against net assets
    worth 3.2 months — 12x its own ceiling, matching neither unit reading.

    It never reached the page (a computed figure won), but it is handed to the
    factual judge as ground truth, so a wrong number there blocks publication
    of a narrative that is right.
    """

    def test_the_mas_boston_value_is_refused(self):
        out = _normalize({
            "working_capital_ratio": 39,
            "net_assets": 814400,
            "total_expenses": 3083919,
        })
        assert out["working_capital_ratio"] is None

    def test_the_ceiling_itself_is_allowed(self):
        out = _normalize({
            "working_capital_ratio": 39.0,
            "net_assets": 43407000,
            "total_expenses": 13351984,
        })
        assert out["working_capital_ratio"] == 39.0

    def test_a_value_just_inside_the_ceiling_survives(self):
        """3.2 months of net assets, reported as 3.1 — plausible."""
        out = _normalize({
            "working_capital_ratio": 3.1,
            "net_assets": 814400,
            "total_expenses": 3083919,
        })
        assert out["working_capital_ratio"] == 3.1

    def test_negative_net_assets_are_left_to_the_unit_check(self):
        """No ceiling to apply when there are no net assets to exceed."""
        out = _normalize({
            "working_capital_ratio": -6.0,
            "net_assets": -50000,
            "total_expenses": 100000,
        })
        assert out["working_capital_ratio"] == -6.0

    def test_zero_expenses_is_not_a_division(self):
        out = _normalize({
            "working_capital_ratio": 3.25, "net_assets": 100, "total_expenses": 0
        })
        assert out["working_capital_ratio"] == 3.25

    def test_a_missing_ratio_is_not_invented(self):
        assert _normalize({"net_assets": 100, "total_expenses": 50}).get(
            "working_capital_ratio"
        ) is None

    def test_zero_is_ambiguous_and_stays_zero_either_way(self):
        out = _normalize({
            "working_capital_ratio": 0, "net_assets": 0, "total_expenses": 100000
        })
        assert out["working_capital_ratio"] == 0

    def test_a_negative_reserve_position_converts_too(self):
        out = _normalize({
            "working_capital_ratio": -0.5, "net_assets": -50000, "total_expenses": 100000
        })
        assert out["working_capital_ratio"] == -6.0

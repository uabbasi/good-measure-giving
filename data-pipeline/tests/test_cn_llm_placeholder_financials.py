"""An LLM that invents one round number for every money field is not data.

Yateem Foundation (EIN 99-3373484) published total_revenue == program_expenses ==
total_expenses == admin_expenses == fundraising_expenses == total_assets ==
total_liabilities == exactly $100,000, ratio 1.0000, while its Form 990 reports
$47,893. The narrative faithfully restated the placeholder, and the `factual`
judge correctly blocked publication.

Where it came from: CN changed its page format (the run logged
"[CN FORMAT CHANGE] High-severity markers missing ... Financial ratio slugs/keys"),
so the structured/regex extraction found nothing and `_extract_financials_with_llm`
ran as fallback. The CN page contains **zero** occurrences of "100000" -- the
figure is not on the page at all, it was invented.

`_validate_llm_financials` was written for exactly this risk ("C-004 fix: LLM can
hallucinate wildly implausible values") but only range-checks each field
independently (0 .. $100B), and $100,000 passes trivially. The hallucination
signature here is not the magnitude of any single field -- it's that every field
carries the SAME number, which no real filer produces (it implies zero admin,
zero fundraising, and revenue exactly equal to expenses simultaneously).

Project rule this restores: missing fields stay NULL rather than being fabricated.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.charity_navigator import CharityNavigatorCollector


def _collector():
    return CharityNavigatorCollector(use_llm_extraction=False)


class TestIdenticalMoneyFieldsAreRejected:
    def test_the_yateem_placeholder_is_rejected(self):
        """The real shape observed on EIN 99-3373484."""
        out = _collector()._validate_llm_financials({
            "total_revenue": 100000,
            "total_expenses": 100000,
            "program_expenses": 100000,
            "admin_expenses": 100000,
            "fundraising_expenses": 100000,
        })
        for field in ("total_revenue", "total_expenses", "program_expenses",
                      "admin_expenses", "fundraising_expenses"):
            assert out[field] is None, f"{field} must be dropped, not published as data"

    def test_three_identical_fields_is_enough_to_reject(self):
        out = _collector()._validate_llm_financials({
            "total_revenue": 250000,
            "total_expenses": 250000,
            "total_assets": 250000,
        })
        assert out["total_revenue"] is None
        assert out["total_expenses"] is None
        assert out["total_assets"] is None

    def test_non_financial_fields_survive_the_rejection(self):
        """Only the money fields are suspect; a fiscal year is still usable."""
        out = _collector()._validate_llm_financials({
            "total_revenue": 100000,
            "total_expenses": 100000,
            "program_expenses": 100000,
            "fiscal_year": 2025,
        })
        assert out["fiscal_year"] == 2025
        assert out["total_revenue"] is None


class TestLegitimateFinancialsAreUnaffected:
    def test_ordinary_distinct_financials_pass_through(self):
        out = _collector()._validate_llm_financials({
            "total_revenue": 5_000_000,
            "total_expenses": 4_500_000,
            "program_expenses": 3_800_000,
            "admin_expenses": 500_000,
            "fundraising_expenses": 200_000,
        })
        assert out["total_revenue"] == 5_000_000
        assert out["program_expenses"] == 3_800_000

    def test_two_coincidentally_equal_fields_are_not_enough_to_reject(self):
        """A real filing can have two equal figures by coincidence (e.g. a
        pass-through year where revenue == expenses). Two is not a placeholder
        signature; only 3+ collapsing to one value is."""
        out = _collector()._validate_llm_financials({
            "total_revenue": 900_000,
            "total_expenses": 900_000,
            "program_expenses": 750_000,
        })
        assert out["total_revenue"] == 900_000
        assert out["total_expenses"] == 900_000
        assert out["program_expenses"] == 750_000

    def test_all_zero_is_left_to_the_existing_zero_corroboration_logic(self):
        """The aggregator already resolves ambiguous CN zeros by arithmetic
        corroboration. This guard must not pre-empt that path, so it only fires
        on a shared NON-zero value."""
        out = _collector()._validate_llm_financials({
            "program_expenses": 0,
            "admin_expenses": 0,
            "fundraising_expenses": 0,
        })
        assert out["program_expenses"] == 0
        assert out["admin_expenses"] == 0
        assert out["fundraising_expenses"] == 0

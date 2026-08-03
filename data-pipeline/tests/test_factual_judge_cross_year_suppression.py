"""Comparing two fiscal years and calling the difference a contradiction must not block.

Prompt guidance was tried first (baseline of this run) and was not enough. The judge
now openly names the year gap in its own message and still returns ERROR:

  UMR (27-3175543): "The narrative states total revenue of $149,888,609, but the
  source data (Form 990 (2023)) reports $57,586,233 for FY2023. THE NARRATIVE'S
  FIGURE APPEARS TO BE FROM FY2024 DATA."

  Amoud (75-2882187): "narrative states $11,142,566 for FY2024, but the Form 990
  (2023) shows $9,535,194 for FY2023 and Charity Navigator shows $11,142,566 for
  FY2024."

  Rahima (77-0442850): "states $4,100,385 but the Form 990 (2023) reports $4,006,022"
  -- CN (FY2024) and form990_grants (tax_year 2024) both report $4,100,385.

Three different charities, three runs, same reasoning error. Consensus cannot filter
it because every roll makes it, and prompt text did not stop it. This is exactly the
situation the file already documents for the wallet-tag case: "the answer is not more
prompt text. Where a deterministic check owns the question, the model's copy does not
get to block."

ProPublica's latest filing routinely lags Charity Navigator by a year, so a charity
legitimately has different revenue in FY2023 and FY2024 and the narrative citing the
newer year is correct.

Downgraded to WARNING rather than dropped, matching every other rule in that chain:
the finding still reaches reports/editorial-queue.json for a human, it just stops
gating publication.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import _is_cross_fiscal_year_comparison


class TestTheObservedMessagesAreRecognized:
    def test_umr_revenue_across_two_years(self):
        assert _is_cross_fiscal_year_comparison(
            "total_revenue",
            "The narrative states total revenue of $149,888,609, but the source data "
            "(Form 990 (2023)) reports $57,586,233 for FY2023. The narrative's figure "
            "appears to be from FY2024 data.",
        )

    def test_amoud_revenue_across_two_years(self):
        assert _is_cross_fiscal_year_comparison(
            "total revenue",
            "The narrative states $11,142,566 in total revenue for FY2024, but the Form "
            "990 (2023) shows $9,535,194 for FY2023 and Charity Navigator shows "
            "$11,142,566 for FY2024.",
        )

    def test_a_year_followed_by_a_comma_still_counts(self):
        """Justice Defenders (36-4787320) exposed this: the first year is written
        "for FY2024, which matches Charity Navigator", and a lookahead meant to
        reject dollar amounts like "$52,024" was also rejecting a year followed by
        an ordinary prose comma -- so only one year was found and the comparison
        was not recognized as cross-year."""
        assert _is_cross_fiscal_year_comparison(
            "total_revenue",
            "The narrative states total revenue of $1,331,729 for FY2024, which matches "
            "Charity Navigator, but the 2023 Annual Report (Source [2]) indicates total "
            "revenue of $1,624,040.",
        )

    def test_yateem_fiscal_year_vs_tax_year(self):
        assert _is_cross_fiscal_year_comparison(
            "total_revenue",
            "The reported total revenue of $100,000 for fiscal year 2025 does not match "
            "the source data which indicates $47,893 for tax year 2024.",
        )


class TestGenuineSingleYearFindingsStillBlock:
    def test_one_year_mentioned_is_not_a_cross_year_comparison(self):
        """The narrative and source disagree about the SAME year -- a real fault."""
        assert not _is_cross_fiscal_year_comparison(
            "total_revenue",
            "The narrative states $5,000,000 for FY2024 but the source reports "
            "$3,200,000 for FY2024.",
        )

    def test_no_year_mentioned_is_not_a_cross_year_comparison(self):
        assert not _is_cross_fiscal_year_comparison(
            "program_expense_ratio",
            "The narrative claims a 95% program expense ratio but the source shows 61%.",
        )

    def test_a_repeated_single_year_is_not_two_years(self):
        assert not _is_cross_fiscal_year_comparison(
            "total_expenses",
            "For FY2024 the narrative says $2M; the FY2024 filing says $9M.",
        )

    def test_a_dollar_amount_that_looks_like_a_year_is_not_a_year(self):
        """$2,024 must not be read as the year 2024 and open an escape hatch."""
        assert not _is_cross_fiscal_year_comparison(
            "admin_expenses",
            "The narrative reports admin expenses of $2,024 but the source shows $9,310.",
        )

    def test_a_non_financial_field_is_not_suppressed(self):
        """Founding year requires an exact match; two years there is the whole point."""
        assert not _is_cross_fiscal_year_comparison(
            "founded_year",
            "The narrative says the charity was founded in 2003 but the IRS ruling year is 1998.",
        )

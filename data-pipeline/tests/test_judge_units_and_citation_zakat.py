"""Two remaining blockers, both category errors rather than data problems.

UMR (27-3175543), factual judge:
    field='program_expense_ratio'  claim='7.44'  source='47.5%'
    "The narrative claims a low cost per beneficiary of $7.44 for direct services,
     but the source data indicates that the cash-adjusted program expense ratio is
     only 47.5% in FY2024."
A dollar amount and a percentage are different quantities. The judge picked two
unrelated figures and called the difference a discrepancy. The prompt already
carries a "CRITICAL: Working Capital Units" section, so unit confusion is a known
failure here; this is the deterministic version of that rule.

MAS Boston (20-1799252), citation judge:
    claim='The organization is recognized as zakat-eligible.'  source=None
    "The citation states the organization is Zakat eligible, but the claim states
     it is recognized as zakat-eligible."
Those say the same thing. Whether the charity accepts zakat is already settled in
code -- _quick_checks compares wallet_tag against a tag derived independently from
claims_zakat_eligible -- and factual_judge already refuses to let the model's second
opinion on that question block (_is_wallet_tag_agreement). The citation judge had no
equivalent, so the same settled question could still withhold a page from a
different judge. A miscited zakat claim is a craft issue for the editorial queue,
not a publication blocker.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.citation_judge import is_zakat_eligibility_claim
from src.judges.factual_judge import _currency_claim_against_a_percentage


class TestCurrencyAgainstAPercentage:
    UMR_MESSAGE = (
        "The narrative claims a low cost per beneficiary of $7.44 for direct services, "
        "but the source data indicates that the cash-adjusted program expense ratio is "
        "only 47.5% in FY2024."
    )

    def test_the_umr_pair_is_recognized(self):
        assert _currency_claim_against_a_percentage(self.UMR_MESSAGE, "7.44", "47.5%")

    def test_a_dollar_sign_with_a_space_still_counts(self):
        assert _currency_claim_against_a_percentage(
            "cost per beneficiary of $ 907 but the ratio is 80%", "907", "80%"
        )

    def test_two_percentages_are_left_alone(self):
        """A real ratio disagreement must keep blocking."""
        assert not _currency_claim_against_a_percentage(
            "The narrative states 58.5% but the source reports 65.13%.", "58.5%", "65.13%"
        )

    def test_two_dollar_amounts_are_left_alone(self):
        assert not _currency_claim_against_a_percentage(
            "The narrative states $5,000,000 but the source reports $3,200,000.",
            "$5,000,000",
            "$3,200,000",
        )

    def test_a_claim_not_shown_as_currency_is_left_alone(self):
        """7.44 appearing without a dollar sign is just a number."""
        assert not _currency_claim_against_a_percentage(
            "The narrative states a ratio of 7.44 but the source reports 47.5%.",
            "7.44",
            "47.5%",
        )

    def test_a_non_percentage_source_is_left_alone(self):
        assert not _currency_claim_against_a_percentage(
            "cost per beneficiary of $7.44 but the source says $12.10", "7.44", "$12.10"
        )


class TestCitationZakatEligibility:
    def test_the_mas_boston_finding_is_recognized(self):
        assert is_zakat_eligibility_claim(
            "citation_1",
            "The citation states the organization is Zakat eligible, but the claim "
            "states it is recognized as zakat-eligible.",
        )

    def test_a_wallet_tag_phrasing_is_recognized(self):
        assert is_zakat_eligibility_claim(
            "zakat", "wallet tag says ZAKAT-ELIGIBLE but the citation does not"
        )

    def test_an_unrelated_citation_problem_still_blocks(self):
        """Narrowness guard: only the zakat-eligibility question is deferred."""
        assert not is_zakat_eligibility_claim(
            "citation_3", "Citation [3] is a homepage and does not mention the $2M grant."
        )

    def test_a_fabricated_zakat_figure_is_not_the_eligibility_question(self):
        """A dollar claim about zakat spending is a different assertion entirely."""
        assert not is_zakat_eligibility_claim(
            "zakat_narrative",
            "The narrative states $4.2M was distributed as zakat; the cited page "
            "reports no such program.",
        )

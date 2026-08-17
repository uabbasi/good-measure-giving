"""The narrative must not tout a program ratio the scorer refused to credit.

United Muslim Relief (EIN 27-3175543) is ~95% Gifts-in-Kind. Its filed program
expense ratio is 96.5%; its cash-adjusted ratio is 48%. The scorer deliberately
scores the cash-adjusted figure -- `_compute_cash_adjusted_ratio`'s docstring
names this EIN and says it "must keep scoring on its measured 48% cash-adjusted
ratio rather than falling back to its 96% filed ratio, which would swing its
published score" -- and gave the Program Ratio component 0/5.

The baseline prompt was handed the FILED 96.5% as a mandatory value ("use this
exact percentage everywhere"), so the narrative sold it as a strength. The `score`
judge then blocked publication on four fields (amal_score_rationale, strengths,
summary, dimension_explanations.impact) for exactly that contradiction. The judge
was right; the narrative was wrong.

Forcing baseline+rich+judge regeneration did NOT clear it (5 errors -> 4, same
defect), so this is systematic, not LLM sampling noise.

The reconciliation layer already detects the condition (`check_gik_inflated_ratio`,
HIGH severity at >=80% noncash) and the scorer already labels the component
"Cash-adjusted program ratio". Only the narrative path was never told.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline import _baseline_prompt_kwargs, sanitize_narrative_metrics


def _fake_scores():
    return SimpleNamespace(
        wallet_tag="ZAKAT-ELIGIBLE",
        amal_score=69,
        impact=SimpleNamespace(score=30, cost_per_beneficiary=None),
        alignment=SimpleNamespace(score=39, muslim_donor_fit_level="STRONG", cause_urgency_label="HIGH"),
        data_confidence=SimpleNamespace(overall=0.7, badge="MEDIUM"),
    )


class TestTheGikAdjustedRatioReachesTheNarrative:
    def test_prompt_gets_the_cash_adjusted_ratio_not_the_inflated_filed_one(
        self, sample_charity_metrics
    ):
        """The UMR shape: filed 96.5%, cash-adjusted 48%."""
        m = sample_charity_metrics.model_copy(
            update={"program_expense_ratio": 0.965, "cash_adjusted_program_ratio": 0.48}
        )
        kwargs = _baseline_prompt_kwargs(m, _fake_scores(), 3, "[1] CN")
        assert "48.0%" in kwargs["ratio"], (
            f"prompt must carry the scored cash-adjusted ratio, got {kwargs['ratio']!r}"
        )
        assert "96.5%" not in kwargs["ratio"], (
            "the inflated filed ratio must not be handed over as a mandatory value"
        )

    def test_the_substituted_ratio_is_labelled_cash_adjusted(self, sample_charity_metrics):
        """Swapping the VALUE without the LABEL just moves the lie.

        The first version of this fix handed over 47.5% still labelled "Program
        Expense Ratio", and the score judge caught it: "Presenting the
        cash-adjusted ratio as the general 'program expense ratio' without
        qualification is misleading." The label has to travel with the number,
        which is what v2_scorers already does for the score component.
        """
        m = sample_charity_metrics.model_copy(
            update={"program_expense_ratio": 0.965, "cash_adjusted_program_ratio": 0.48}
        )
        kwargs = _baseline_prompt_kwargs(m, _fake_scores(), 3, "[1] CN")
        assert "cash-adjusted" in kwargs["ratio_label"].lower(), (
            f"label must qualify the figure, got {kwargs['ratio_label']!r}"
        )

    def test_the_unadjusted_ratio_keeps_the_plain_label(self, sample_charity_metrics):
        m = sample_charity_metrics.model_copy(
            update={"program_expense_ratio": 0.83, "cash_adjusted_program_ratio": None}
        )
        kwargs = _baseline_prompt_kwargs(m, _fake_scores(), 3, "[1] CN")
        assert "cash-adjusted" not in kwargs["ratio_label"].lower()

    def test_filed_ratio_is_still_used_when_there_is_no_gik_adjustment(
        self, sample_charity_metrics
    ):
        """Regression: charities without material GIK are untouched."""
        m = sample_charity_metrics.model_copy(
            update={"program_expense_ratio": 0.83, "cash_adjusted_program_ratio": None}
        )
        kwargs = _baseline_prompt_kwargs(m, _fake_scores(), 3, "[1] CN")
        assert "83.0%" in kwargs["ratio"]


class TestTheNoncashSignalNamesTheRightDenominator:
    """noncash_ratio is noncash / total CONTRIBUTIONS, not / total revenue.

    The field is defined that way ("Noncash / total contributions") and computed
    that way (`noncash / total_contribs`, clamped to 1.0), but the GIK signal
    described it as a share "of reported revenue". For United Muslim Relief the
    ratio clamps to 100%, so the narrative asserted "100% of its revenue comes
    from non-cash gifts" while noncash is $143,021,451 of $149,888,609 revenue --
    95.4%. The factual judge flagged it twice, correctly: "the narrative states
    noncash contributions make up '100% of reported revenue', which is an
    overstatement."

    The ratio isn't wrong; the denominator it claims is.
    """

    def _headline(self, sample_charity_metrics, noncash_ratio):
        from src.reconciliation.checks import check_gik_inflated_ratio

        m = sample_charity_metrics.model_copy(update={
            "noncash_ratio": noncash_ratio,
            "program_expense_ratio": 0.965,
            "cash_adjusted_program_ratio": 0.48,
        })
        signals = check_gik_inflated_ratio(m)
        assert signals, "a high noncash ratio must still raise a signal"
        return signals[0].headline

    def test_the_high_band_does_not_claim_revenue(self, sample_charity_metrics):
        headline = self._headline(sample_charity_metrics, 1.0)
        assert "revenue" not in headline.lower(), (
            f"noncash_ratio is a share of contributions, not revenue: {headline!r}"
        )
        assert "contribution" in headline.lower()

    def test_the_medium_band_does_not_claim_revenue(self, sample_charity_metrics):
        headline = self._headline(sample_charity_metrics, 0.30)
        assert "revenue" not in headline.lower(), (
            f"noncash_ratio is a share of contributions, not revenue: {headline!r}"
        )


class TestTheSanitizerAgreesWithThePrompt:
    def test_sanitizer_does_not_rewrite_the_narrative_back_to_the_filed_ratio(
        self, sample_charity_metrics
    ):
        """The metric sanitizer normalizes "X% program expense" against metrics.
        If it kept using the filed ratio it would overwrite the cash-adjusted
        figure the prompt just asked for, re-introducing the contradiction after
        generation."""
        m = sample_charity_metrics.model_copy(
            update={"program_expense_ratio": 0.965, "cash_adjusted_program_ratio": 0.48}
        )
        text = "The charity reports a 12.3% program expense ratio."
        out = sanitize_narrative_metrics({"rationale": text}, m, None)["rationale"]
        assert "96.5%" not in out, "sanitizer must not restore the GIK-inflated ratio"

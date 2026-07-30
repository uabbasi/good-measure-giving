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
        impact=SimpleNamespace(score=30, directness_level="HIGH", cost_per_beneficiary=None),
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

    def test_filed_ratio_is_still_used_when_there_is_no_gik_adjustment(
        self, sample_charity_metrics
    ):
        """Regression: charities without material GIK are untouched."""
        m = sample_charity_metrics.model_copy(
            update={"program_expense_ratio": 0.83, "cash_adjusted_program_ratio": None}
        )
        kwargs = _baseline_prompt_kwargs(m, _fake_scores(), 3, "[1] CN")
        assert "83.0%" in kwargs["ratio"]


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

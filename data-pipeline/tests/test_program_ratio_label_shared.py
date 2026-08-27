"""One label per number, on every prompt path that names the program ratio.

baseline.py already solved this: when gifts-in-kind inflate the filed ratio the
scorer stands behind the cash-adjusted figure, so the prompt hands over that
number under the label "Cash-Adjusted Program Expense Ratio (gifts-in-kind
excluded)". The score judge forced that fix -- presenting the adjusted figure as
the plain "program expense ratio" is a misstatement of the headline financial
metric donors judge a charity on.

The rich generator never got it. It hardcoded the plain label and added "use
this exact percentage everywhere", while the baseline narrative in the same
context carried the adjusted figure under a nearly identical name. On United
Muslim Relief (27-3175543) those two numbers are 97.45% filed and 47.5%
cash-adjusted -- a 50-point gap -- and 20 of 169 published pages ended up
carrying both labels.

The label was computed inline inside _baseline_prompt_kwargs, which is exactly
why a second call site could drift. It is a shared function now.
"""

from types import SimpleNamespace

from baseline import program_ratio_and_label

PLAIN = "Program Expense Ratio"
ADJUSTED = "Cash-Adjusted Program Expense Ratio (gifts-in-kind excluded)"


def _metrics(filed, adjusted=None):
    return SimpleNamespace(program_expense_ratio=filed, cash_adjusted_program_ratio=adjusted)


class TestTheNumberAndItsNameTravelTogether:
    def test_a_material_gik_gap_yields_the_adjusted_number_under_the_adjusted_label(self):
        # United Muslim Relief's real figures.
        ratio, label = program_ratio_and_label(_metrics(0.9745, 0.4755))

        assert ratio == 0.4755
        assert label == ADJUSTED

    def test_no_adjustment_yields_the_filed_number_under_the_plain_label(self):
        ratio, label = program_ratio_and_label(_metrics(0.83))

        assert ratio == 0.83
        assert label == PLAIN

    def test_an_immaterial_gap_keeps_the_filed_figure_and_the_plain_label(self):
        """Swapping for a hair's difference would move published percentages for nothing."""
        ratio, label = program_ratio_and_label(_metrics(0.8300, 0.8299))

        assert ratio == 0.83
        assert label == PLAIN

    def test_a_missing_ratio_still_returns_a_usable_label(self):
        ratio, label = program_ratio_and_label(_metrics(None))

        assert ratio is None
        assert label == PLAIN

    def test_it_never_pairs_the_adjusted_number_with_the_plain_label(self):
        """The exact misstatement the score judge caught."""
        for filed, adjusted in ((0.9745, 0.4755), (0.965, 0.48), (0.90, 0.10)):
            ratio, label = program_ratio_and_label(_metrics(filed, adjusted))
            if ratio != filed:
                assert label == ADJUSTED, f"{ratio} shipped under the plain label"

    def test_it_tolerates_a_metric_like_without_the_adjusted_field(self):
        """Callers legitimately pass objects that predate cash_adjusted_program_ratio."""
        ratio, label = program_ratio_and_label(SimpleNamespace(program_expense_ratio=0.77))

        assert ratio == 0.77
        assert label == PLAIN


class TestBaselineStillUsesTheSharedHelper:
    def test_the_baseline_prompt_label_matches_the_helper(self, sample_charity_metrics):
        """Guards against the two drifting apart again."""
        from baseline import _baseline_prompt_kwargs

        scores = SimpleNamespace(
            wallet_tag="ZAKAT-ELIGIBLE",
            amal_score=81,
            impact=SimpleNamespace(score=37, cost_per_beneficiary=907),
            alignment=SimpleNamespace(
                score=44, muslim_donor_fit_level="STRONG", cause_urgency_label="HIGH"
            ),
            data_confidence=SimpleNamespace(overall=0.8, badge="HIGH"),
            case_against=None,
        )
        kwargs = _baseline_prompt_kwargs(sample_charity_metrics, scores, 1, "[1] CN")
        _, expected_label = program_ratio_and_label(sample_charity_metrics)

        assert kwargs["ratio_label"] == expected_label

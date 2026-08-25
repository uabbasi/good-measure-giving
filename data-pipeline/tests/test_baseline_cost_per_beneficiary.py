"""Cost per beneficiary is a quotable figure or it is absent -- never both.

The prompt used to invite the claim and withhold the means to make it truthfully:

  line 69  GOOD: "$907 cost per beneficiary"        <- invites the claim
  line 77  Impact: N/50 (Cost per beneficiary: X)   <- inside "do NOT quote these numbers"
  line 44  N/A means stay silent                    <- applied only to the 4 MANDATORY VALUES

For a charity with no cost_per_beneficiary the model was encouraged to state a
per-unit cost, forbidden from quoting the only one it had, and never told to
stay quiet. Yateem Foundation (99-3373484) invented "$353.70 for each person it
helps" and the factual judge withheld its page over it -- one of only five
blocking errors in the entire v6.0.0 run. cost_per_beneficiary is absent for 94
of 166 charities, so the exposure is most of the corpus on every run.

The fix makes it an ordinary mandatory value: quotable when present, covered by
the N/A silence rule when not.
"""

import re
from types import SimpleNamespace

import pytest
from baseline import build_baseline_prompt


def _scores(cost_per_beneficiary):
    """Mirrors _fake_scores in test_baseline_prompt.py, varying only the CPB."""
    return SimpleNamespace(
        wallet_tag="ZAKAT-ELIGIBLE",
        amal_score=81,
        impact=SimpleNamespace(score=37, cost_per_beneficiary=cost_per_beneficiary),
        alignment=SimpleNamespace(
            score=44, muslim_donor_fit_level="STRONG", cause_urgency_label="HIGH"
        ),
        data_confidence=SimpleNamespace(overall=0.8, badge="HIGH"),
    )


def _prompt(sample_charity_metrics, cost_per_beneficiary):
    prompt, _ = build_baseline_prompt(
        sample_charity_metrics, _scores(cost_per_beneficiary), 1, "[1] CN"
    )
    return prompt


def _mandatory_block(prompt: str) -> str:
    """The MANDATORY VALUES section, where the N/A silence rule applies."""
    start = prompt.index("## MANDATORY VALUES")
    end = prompt.index('If a value is "N/A"', start)
    return prompt[start:end]


class TestCostPerBeneficiaryIsAMandatoryValue:
    def test_it_appears_in_the_block_the_na_rule_governs(self, sample_charity_metrics):
        block = _mandatory_block(_prompt(sample_charity_metrics, 96.62))

        assert re.search(r"cost per beneficiary", block, re.IGNORECASE)

    def test_an_absent_value_reaches_that_block_as_na(self, sample_charity_metrics):
        """This is what makes the model stay silent instead of inventing."""
        block = _mandatory_block(_prompt(sample_charity_metrics, None))

        line = next(
            ln for ln in block.splitlines() if re.search(r"cost per beneficiary", ln, re.IGNORECASE)
        )
        assert "N/A" in line

    def test_a_present_value_is_formatted_as_currency(self, sample_charity_metrics):
        """A raw float would be quoted verbatim as '$96.61964 per person'."""
        block = _mandatory_block(_prompt(sample_charity_metrics, 96.61964))

        line = next(
            ln for ln in block.splitlines() if re.search(r"cost per beneficiary", ln, re.IGNORECASE)
        )
        assert "$96.62" in line
        assert "96.61964" not in line


class TestTheContradictionIsGone:
    def test_it_is_no_longer_inside_the_do_not_quote_block(self, sample_charity_metrics):
        """It was listed under 'context only - do NOT quote these numbers'."""
        prompt = _prompt(sample_charity_metrics, 96.62)
        start = prompt.index("## Pre-computed Scores")
        end = prompt.index("## TONE CONTRACT", start)

        assert not re.search(r"cost per beneficiary", prompt[start:end], re.IGNORECASE)

    def test_the_internal_score_is_still_withheld(self, sample_charity_metrics):
        """Moving CPB out must not drag the score numbers into quotable territory."""
        prompt = _prompt(sample_charity_metrics, 96.62)
        start = prompt.index("## Pre-computed Scores")

        assert "do NOT quote these numbers" in prompt[start : start + 120]


@pytest.mark.parametrize("cpb", [None, 0])
def test_a_missing_or_zero_value_is_never_presented_as_a_real_figure(
    sample_charity_metrics, cpb
):
    """0 is not a cost; it means we could not compute one."""
    block = _mandatory_block(_prompt(sample_charity_metrics, cpb))
    line = next(
        ln for ln in block.splitlines() if re.search(r"cost per beneficiary", ln, re.IGNORECASE)
    )

    assert "N/A" in line
    assert "$0" not in line

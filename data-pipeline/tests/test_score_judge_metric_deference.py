"""Numeric adjudication belongs to the factual judge, not the score judge.

Both judges see the same metric disagreements, but only one is equipped to
rule on them. FactualIssue carries claim_value and source_value, so the
factual judge can compare the numbers and apply a bounded tolerance
(_same_story: opposite signs and order-of-magnitude gaps still block).
ScoreIssue carries only prose -- recovering "$0.10" and "$0.05" from
"fundraising costs are $0.10 to raise every $1, but source data indicates
$0.05 to raise every $1" means guessing which of [0.10, 1, 0.05, 1] are the
operands, and "per $1" is indistinguishable from a real value of 1.

So the score judge defers on these fields rather than blocking blind.

Why this matters, measured: eb8ef36 moved fundraising efficiency onto a
contributions denominator, which widened the gap against Charity Navigator's
differently-computed figure. 205b206 added a tolerance to the factual judge
but not here, and five previously-publishable charities became blocked --
20-0942434, 31-1628040, 56-2392452, 88-2980325, 93-1556038 -- almost all on
fundraising efficiency, taking the cohort from 14 publishable down to 12.

Deferring is not going blind: 56-2392452's working capital sign flip (-2.7
vs 1.68 months) was caught by the factual judge in the same run.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import Severity
from src.judges.score_judge import ScoreJudge, ScoreVerificationResult


def _severity(field, message):
    payload = ScoreVerificationResult(
        issues=[{"field": field, "severity": "error", "message": message}],
    )
    judge = ScoreJudge(JudgeConfig())
    client = Mock()
    client.generate.return_value = Mock(text=payload.model_dump_json(), cost_usd=0.0)
    with patch.object(judge, "get_llm_client", return_value=client):
        res = judge._verify_rationales_with_llm({"evaluation": {}}, {})
    return res.issues[0].severity


class TestItDefersOnMetricValueDisagreements:
    def test_fundraising_efficiency_disagreement_does_not_block(self):
        assert _severity(
            "strengths",
            "The narrative states fundraising costs are $0.10 to raise every $1, "
            "but source data indicates $0.05 to raise every $1.",
        ) != Severity.ERROR

    def test_the_other_observed_fundraising_wording_also_defers(self):
        assert _severity(
            "strengths",
            "The narrative states the charity spent $0.29 for every $1 raised, but "
            "the source data (Charity Navigator) indicates a different figure.",
        ) != Severity.ERROR

    def test_working_capital_disagreement_does_not_block(self):
        assert _severity(
            "rationale",
            "The narrative states -2.7 months of working capital, but the source "
            "data indicates 1.68 months.",
        ) != Severity.ERROR


class TestItStillBlocksOnItsOwnJob:
    """Score-rationale coherence is what this judge is actually for."""

    def test_a_rationale_contradicting_its_own_score_still_blocks(self):
        assert _severity(
            "amal_score_rationale",
            "The rationale states 'average performance' which contradicts the "
            "ground truth amal_score of 66 (Above Average).",
        ) == Severity.ERROR

    def test_a_wrong_dimension_attribution_still_blocks(self):
        assert _severity(
            "dimension_explanations",
            "The rationale incorrectly attributes 'high level of cash reserves' as "
            "a factor for the Alignment dimension.",
        ) == Severity.ERROR

    def test_a_miscited_claim_still_blocks(self):
        assert _severity(
            "strengths",
            "Citation [6] does not support the claim 'manages funds according to "
            "Islamic principles'.",
        ) == Severity.ERROR

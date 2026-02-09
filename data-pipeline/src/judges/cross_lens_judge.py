"""Cross-Lens Consistency Judge - flags contradictions across narrative lenses.

LLM-based judge that takes all 3 narratives for a single charity and checks:
1. Factual contradictions between lenses
2. Score-narrative misalignment (low score + glowing narrative)
3. Wallet tag inconsistency across lenses

All issues are WARNINGs — inconsistencies are surfaced, not blocking.
"""

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from .base_judge import BaseJudge, JudgeType, SafeJSONEncoder
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Minimum number of narratives required to run cross-lens checks
MIN_NARRATIVES = 2


class CrossLensIssue(BaseModel):
    """Schema for a cross-lens consistency issue from LLM."""

    field: str = Field(description="The field(s) with the inconsistency")
    severity: str = Field(description="warning or info")
    message: str = Field(description="Description of the inconsistency")
    lens_a: str = Field(description="First lens involved (e.g., 'baseline')")
    lens_b: str = Field(description="Second lens involved (e.g., 'zakat')")
    evidence: Optional[str] = Field(None, description="Specific contradicting claims")


class CrossLensResult(BaseModel):
    """Schema for cross-lens consistency LLM response."""

    issues: list[CrossLensIssue] = Field(default_factory=list)
    factual_contradictions: int = Field(0, description="Count of factual contradictions")
    score_misalignments: int = Field(0, description="Count of score-narrative misalignments")
    wallet_tag_issues: int = Field(0, description="Count of wallet tag inconsistencies")
    summary: str = Field("", description="Brief consistency assessment")


class CrossLensJudge(BaseJudge):
    """Validates consistency across baseline, strategic, and zakat narratives.

    Checks that narratives don't contradict each other on facts, that scores
    align with narrative tone, and that wallet tags are consistent.
    """

    @property
    def name(self) -> str:
        return "cross_lens"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.LLM

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate cross-lens consistency.

        Args:
            output: Exported charity data with all narratives
            context: Source data context

        Returns:
            JudgeVerdict with any cross-lens consistency issues
        """
        issues: list[ValidationIssue] = []
        cost_usd = 0.0
        metadata: dict[str, Any] = {}

        evaluation = output.get("evaluation", {})
        if not evaluation:
            return self.create_verdict(
                passed=True,
                skipped=True,
                skip_reason="No evaluation data found",
            )

        # Collect narratives and scores
        narratives = {}
        scores = {}

        baseline_narr = evaluation.get("baseline_narrative")
        if baseline_narr and isinstance(baseline_narr, dict):
            narratives["baseline"] = baseline_narr
            scores["baseline"] = evaluation.get("amal_score")

        strategic_narr = evaluation.get("strategic_narrative")
        if strategic_narr and isinstance(strategic_narr, dict):
            narratives["strategic"] = strategic_narr
            scores["strategic"] = evaluation.get("strategic_score")

        zakat_narr = evaluation.get("zakat_narrative")
        if zakat_narr and isinstance(zakat_narr, dict):
            narratives["zakat"] = zakat_narr
            scores["zakat"] = evaluation.get("zakat_score")

        if len(narratives) < MIN_NARRATIVES:
            return self.create_verdict(
                passed=True,
                skipped=True,
                skip_reason=f"Only {len(narratives)} narrative(s) available, need {MIN_NARRATIVES}",
            )

        metadata["lenses_compared"] = list(narratives.keys())

        # Step 1: Deterministic score-narrative tone check
        issues.extend(self._score_tone_check(narratives, scores))

        # Step 2: Deterministic wallet tag consistency check
        issues.extend(self._wallet_tag_consistency(evaluation, narratives))

        # Step 3: LLM-based factual contradiction check
        try:
            llm_result = self._verify_consistency_with_llm(output, narratives, scores)
            if llm_result:
                issues.extend(llm_result.issues)
                cost_usd = llm_result.cost
                metadata["factual_contradictions"] = llm_result.factual_contradictions
                metadata["score_misalignments"] = llm_result.score_misalignments
        except Exception as e:
            logger.warning(f"LLM cross-lens consistency check failed: {e}")
            metadata["llm_failed"] = True

        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        passed = error_count == 0

        return self.create_verdict(
            passed=passed,
            issues=issues,
            cost_usd=cost_usd,
            metadata=metadata,
        )

    def _score_tone_check(self, narratives: dict[str, dict], scores: dict[str, Any]) -> list[ValidationIssue]:
        """Check for obvious score-narrative tone misalignment.

        A score below 30 with only glowing language, or a score above 80
        with predominantly negative language, suggests misalignment.
        """
        issues: list[ValidationIssue] = []

        negative_indicators = ["poor", "weak", "lacking", "insufficient", "fails", "no evidence"]
        positive_indicators = ["excellent", "outstanding", "exceptional", "strong", "impressive"]

        for lens, narrative in narratives.items():
            score = scores.get(lens)
            if score is None:
                continue

            # Get summary text
            summary = (narrative.get("summary") or "").lower()
            if not summary:
                continue

            neg_count = sum(1 for term in negative_indicators if term in summary)
            pos_count = sum(1 for term in positive_indicators if term in summary)

            # Low score + entirely positive summary
            if score < 30 and pos_count >= 2 and neg_count == 0:
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    f"{lens}_narrative.summary",
                    f"{lens.title()} score is {score}/100 but summary is entirely positive",
                    details={"lens": lens, "score": score},
                )

            # High score + entirely negative summary
            if score > 80 and neg_count >= 2 and pos_count == 0:
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    f"{lens}_narrative.summary",
                    f"{lens.title()} score is {score}/100 but summary is predominantly negative",
                    details={"lens": lens, "score": score},
                )

        return issues

    def _wallet_tag_consistency(self, evaluation: dict, narratives: dict[str, dict]) -> list[ValidationIssue]:
        """Check that wallet tag claims are consistent across lenses."""
        issues: list[ValidationIssue] = []

        wallet_tag = evaluation.get("wallet_tag", "")

        # If SADAQAH-ELIGIBLE, zakat narrative should not claim zakat eligibility
        if wallet_tag == "SADAQAH-ELIGIBLE" and "zakat" in narratives:
            zakat_text = json.dumps(narratives["zakat"]).lower()
            if "zakat-eligible" in zakat_text or "eligible for zakat" in zakat_text:
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    "zakat_narrative.wallet_tag",
                    "Zakat narrative claims zakat eligibility but wallet tag is SADAQAH-ELIGIBLE",
                    details={"wallet_tag": wallet_tag},
                )

        return issues

    def _verify_consistency_with_llm(
        self,
        output: dict[str, Any],
        narratives: dict[str, dict],
        scores: dict[str, Any],
    ) -> Optional["LLMCrossLensResult"]:
        """Use LLM to find factual contradictions between narratives."""
        prompt = self.load_prompt_template()
        if not prompt:
            return None

        prompt = prompt.replace("{charity_name}", output.get("name", "Unknown"))
        prompt = prompt.replace("{ein}", output.get("ein", "Unknown"))
        prompt = prompt.replace(
            "{narratives}",
            json.dumps(narratives, indent=2, cls=SafeJSONEncoder),
        )
        prompt = prompt.replace(
            "{scores}",
            json.dumps(scores, indent=2, cls=SafeJSONEncoder),
        )

        client = self.get_llm_client()
        response = client.generate(
            prompt=prompt,
            json_schema=CrossLensResult.model_json_schema(),
        )

        json_text = self.strip_markdown_json(response.text)
        result = CrossLensResult.model_validate_json(json_text)

        # Convert to ValidationIssues — all are WARNINGs
        issues = []
        for issue in result.issues:
            vi = ValidationIssue(
                severity=Severity.WARNING,
                field=issue.field,
                message=f"[{issue.lens_a} vs {issue.lens_b}] {issue.message}",
                evidence=issue.evidence,
            )
            issues.append(vi)

        return LLMCrossLensResult(
            issues=issues,
            factual_contradictions=result.factual_contradictions,
            score_misalignments=result.score_misalignments,
            cost=response.cost_usd or 0.0,
        )


class LLMCrossLensResult:
    """Result from LLM cross-lens consistency check."""

    def __init__(
        self,
        issues: list[ValidationIssue],
        factual_contradictions: int,
        score_misalignments: int,
        cost: float,
    ):
        self.issues = issues
        self.factual_contradictions = factual_contradictions
        self.score_misalignments = score_misalignments
        self.cost = cost

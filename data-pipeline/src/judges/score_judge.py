"""Score Judge - validates that rationales support assigned scores.

Scores are deterministic (calculated by v2_scorers.py).
This judge verifies that the narrative rationale correctly EXPLAINS the score.
"""

import logging
import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


class ScoreIssue(BaseModel):
    """Schema for a score-rationale mismatch from LLM."""

    field: str = Field(description="The field with the issue")
    severity: str = Field(description="error, warning, or info")
    message: str = Field(description="Description of the issue")
    score_name: Optional[str] = Field(None, description="Name of the score")
    score_value: Optional[int] = Field(None, description="The score value")
    evidence: Optional[str] = Field(None, description="Why the rationale doesn't match")


class ScoreVerificationResult(BaseModel):
    """Schema for score verification LLM response."""

    issues: list[ScoreIssue] = Field(default_factory=list)
    scores_checked: int = Field(0, description="Number of scores checked")
    rationales_valid: int = Field(0, description="Number of valid rationales")
    summary: str = Field("", description="Brief summary of results")


# Score interpretation thresholds
SCORE_TIERS = {
    "exceptional": (90, 100),
    "good": (70, 89),
    "average": (50, 69),
    "below_average": (30, 49),
    "poor": (0, 29),
}


class ScoreJudge(BaseJudge):
    """Validates that narrative rationale supports deterministic scores.

    Scores are pre-calculated by deterministic algorithms.
    This judge checks if the rationale correctly explains WHY the score was assigned.
    """

    @property
    def name(self) -> str:
        return "score"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.LLM

    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate score rationales.

        Args:
            output: Exported charity data with scores and narrative
            context: Source data for additional context

        Returns:
            JudgeVerdict with any score-rationale mismatches
        """
        issues: list[ValidationIssue] = []
        cost_usd = 0.0
        metadata: dict[str, Any] = {}

        evaluation = output.get("evaluation", {})
        narrative = output.get("narrative", {})

        if not evaluation:
            return self.create_verdict(
                passed=True,
                metadata={"note": "No scores to validate"},
            )

        # Step 1: Quick tone checks
        quick_issues = self._quick_tone_checks(evaluation, narrative)
        issues.extend(quick_issues)

        # Step 2: LLM verification of rationale quality (with retry for rate limits)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                llm_result = self._verify_rationales_with_llm(output, context)
                if llm_result:
                    issues.extend(llm_result.issues)
                    cost_usd = llm_result.cost
                    metadata["scores_checked"] = llm_result.scores_checked
                    metadata["rationales_valid"] = llm_result.rationales_valid
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "rate" in error_str or "429" in error_str or "quota" in error_str

                if is_rate_limit and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                logger.error(f"Score judge LLM verification failed: {e}")
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    "llm_verification",
                    f"Could not complete LLM verification: {str(e)[:100]}",
                )
                break

        # Determine pass/fail
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        passed = error_count == 0

        return self.create_verdict(
            passed=passed,
            issues=issues,
            cost_usd=cost_usd,
            metadata=metadata,
        )

    def _get_score_tier(self, score: int) -> str:
        """Get the tier name for a score."""
        for tier, (low, high) in SCORE_TIERS.items():
            if low <= score <= high:
                return tier
        return "unknown"

    def _quick_tone_checks(
        self, evaluation: dict[str, Any], narrative: dict[str, Any]
    ) -> list[ValidationIssue]:
        """Quick deterministic checks for obvious tone mismatches.

        Flags cases where score tier clearly conflicts with narrative tone.
        Handles both AMAL (amal_score) and strategic (total_score) evaluations.
        """
        issues: list[ValidationIssue] = []

        # Determine which score system we're validating
        # Strategic evaluations have total_score + dimensions; AMAL has amal_score
        score = evaluation.get("amal_score")
        score_field = "amal_score_rationale"
        if score is None:
            score = evaluation.get("total_score")
            score_field = "strategic_score_rationale"

        if score is None:
            return issues

        tier = self._get_score_tier(score)

        # Get rationale text — try multiple fields
        rationale = (
            narrative.get("trust_rationale", "")
            or narrative.get("score_rationale", "")
            or narrative.get("score_interpretation", "")
            or narrative.get("summary", "")
        )

        if not rationale:
            return issues

        rationale_lower = rationale.lower()

        # Check for obvious mismatches
        positive_words = ["excellent", "outstanding", "exceptional", "exemplary"]
        negative_words = ["poor", "concerning", "problematic", "lacking", "inadequate"]

        has_positive = any(word in rationale_lower for word in positive_words)
        has_negative = any(word in rationale_lower for word in negative_words)

        # Poor score with glowing language
        if tier == "poor" and has_positive and not has_negative:
            self.add_issue(
                issues,
                Severity.WARNING,
                score_field,
                f"Score is poor ({score}) but rationale uses positive language",
                details={"score": score, "tier": tier},
            )

        # Exceptional score with negative language
        if tier == "exceptional" and has_negative and not has_positive:
            self.add_issue(
                issues,
                Severity.WARNING,
                score_field,
                f"Score is exceptional ({score}) but rationale uses negative language",
                details={"score": score, "tier": tier},
            )

        return issues

    def _verify_rationales_with_llm(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> Optional["LLMScoreResult"]:
        """Use LLM to verify rationale-score alignment.

        Returns structured result with issues and cost.
        """
        try:
            prompt = self.format_prompt(output, context)

            client = self.get_llm_client()
            response = client.generate(
                prompt=prompt,
                json_schema=ScoreVerificationResult.model_json_schema(),
            )

            # Strip markdown if present
            json_text = self.strip_markdown_json(response.text)
            result = ScoreVerificationResult.model_validate_json(json_text)

            # Convert to ValidationIssues
            issues = []
            for issue in result.issues:
                severity = Severity(issue.severity.lower())
                details = {}
                if issue.score_name:
                    details["score_name"] = issue.score_name
                if issue.score_value is not None:
                    details["score_value"] = issue.score_value

                issues.append(
                    ValidationIssue(
                        severity=severity,
                        field=issue.field,
                        message=issue.message,
                        details=details if details else None,
                        evidence=issue.evidence,
                    )
                )

            return LLMScoreResult(
                issues=issues,
                scores_checked=result.scores_checked,
                rationales_valid=result.rationales_valid,
                cost=response.cost_usd or 0.0,
            )

        except Exception as e:
            logger.error(f"LLM score verification failed: {e}")
            raise


class LLMScoreResult:
    """Result from LLM score verification."""

    def __init__(
        self,
        issues: list[ValidationIssue],
        scores_checked: int,
        rationales_valid: int,
        cost: float,
    ):
        self.issues = issues
        self.scores_checked = scores_checked
        self.rationales_valid = rationales_valid
        self.cost = cost

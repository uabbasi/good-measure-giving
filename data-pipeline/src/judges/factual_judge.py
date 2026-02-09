"""Factual Judge - validates narrative claims match source data.

Uses span-level verification approach to:
1. Extract factual claims from narrative
2. Match claims to source data
3. Verify values are consistent
"""

import logging
import time
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


class FactualIssue(BaseModel):
    """Schema for a factual discrepancy from LLM."""

    field: str = Field(description="The field with the discrepancy")
    severity: str = Field(description="error, warning, or info")
    message: str = Field(description="Description of the discrepancy")
    claim_text: Optional[str] = Field(None, description="The narrative claim")
    claim_value: Optional[str] = Field(None, description="Value stated in claim")
    source_value: Optional[str] = Field(None, description="Value from source data")
    evidence: Optional[str] = Field(None, description="Why this is a problem")

    @field_validator("claim_value", "source_value", mode="before")
    @classmethod
    def convert_to_str(cls, v: Any) -> Optional[str]:
        """Convert numeric values to strings."""
        if v is None:
            return None
        return str(v)


class FactualVerificationResult(BaseModel):
    """Schema for factual verification LLM response."""

    issues: list[FactualIssue] = Field(default_factory=list)
    claims_checked: int = Field(0, description="Number of claims checked")
    claims_verified: int = Field(0, description="Number of claims verified as accurate")
    summary: str = Field("", description="Brief summary of results")


class FactualJudge(BaseJudge):
    """Validates that narrative claims match source data.

    Extracts factual claims (numbers, dates, names) from the narrative
    and verifies they match the provided source data.
    """

    @property
    def name(self) -> str:
        return "factual"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.LLM

    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate factual claims in the narrative.

        Args:
            output: Exported charity data with narrative
            context: Source data (Form 990, metrics, etc.)

        Returns:
            JudgeVerdict with any factual issues found
        """
        issues: list[ValidationIssue] = []
        cost_usd = 0.0
        metadata: dict[str, Any] = {}

        narrative = output.get("narrative", {})
        if not narrative:
            return self.create_verdict(
                passed=True,
                metadata={"note": "No narrative to validate"},
            )

        # Step 1: Quick deterministic checks for common issues
        quick_issues = self._quick_checks(output, context)
        issues.extend(quick_issues)

        # Step 2: LLM-based claim extraction and verification (with retry for rate limits)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                llm_result = self._verify_claims_with_llm(output, context)
                if llm_result:
                    issues.extend(llm_result.issues)
                    cost_usd = llm_result.cost
                    metadata["claims_checked"] = llm_result.claims_checked
                    metadata["claims_verified"] = llm_result.claims_verified
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "rate" in error_str or "429" in error_str or "quota" in error_str

                if is_rate_limit and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                logger.error(f"Factual judge LLM verification failed: {e}")
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

    def _quick_checks(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> list[ValidationIssue]:
        """Perform quick deterministic checks without LLM.

        Checks obvious mismatches between output and context.
        """
        issues: list[ValidationIssue] = []

        # Check key financial metrics if both exist
        evaluation = output.get("evaluation", {})
        financials = output.get("financials", {})
        source_metrics = context.get("metrics", {})

        # Check AMAL score consistency
        if "amal_score" in evaluation and "amal_score" in source_metrics:
            if evaluation["amal_score"] != source_metrics["amal_score"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "amal_score",
                    f"AMAL score mismatch: output={evaluation['amal_score']}, source={source_metrics['amal_score']}",
                )

        # Check wallet tag consistency
        if "wallet_tag" in evaluation and "wallet_tag" in source_metrics:
            if evaluation["wallet_tag"] != source_metrics["wallet_tag"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "wallet_tag",
                    f"Wallet tag mismatch: output={evaluation['wallet_tag']}, source={source_metrics['wallet_tag']}",
                )

        # Check program expense ratio bounds
        ratio = financials.get("program_expense_ratio")
        if ratio is not None:
            if ratio < 0 or ratio > 1.0:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "program_expense_ratio",
                    f"Program expense ratio out of bounds: {ratio}",
                )

        # Strategic evaluation consistency checks
        # (only run when evaluation contains strategic keys — i.e., strategic variant)
        if "total_score" in evaluation and "strategic_score" in source_metrics:
            if evaluation["total_score"] != source_metrics["strategic_score"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "strategic_score",
                    f"Strategic score mismatch: output={evaluation['total_score']}, "
                    f"source={source_metrics['strategic_score']}",
                )

        if "archetype" in evaluation and "archetype" in source_metrics:
            if evaluation["archetype"] != source_metrics["archetype"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "archetype",
                    f"Archetype mismatch: output={evaluation['archetype']}, "
                    f"source={source_metrics['archetype']}",
                )

        # Check strategic dimension score consistency
        if "dimensions" in evaluation and "strategic_dimensions" in source_metrics:
            output_dims = evaluation["dimensions"]
            source_dims = source_metrics["strategic_dimensions"]
            for dim_name in ["resilience", "leverage", "future_proofing", "competence"]:
                out_val = output_dims.get(dim_name)
                src_val = source_dims.get(dim_name)
                if out_val is not None and src_val is not None and out_val != src_val:
                    self.add_issue(
                        issues,
                        Severity.ERROR,
                        f"strategic_dimension_{dim_name}",
                        f"Strategic {dim_name} mismatch: output={out_val}, source={src_val}",
                    )

        return issues

    def _verify_claims_with_llm(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> Optional["LLMFactualResult"]:
        """Use LLM to extract and verify factual claims.

        Returns structured result with issues and cost.
        """
        try:
            prompt = self.format_prompt(output, context)

            client = self.get_llm_client()
            response = client.generate(
                prompt=prompt,
                json_schema=FactualVerificationResult.model_json_schema(),
            )

            # Strip markdown if present
            json_text = self.strip_markdown_json(response.text)
            result = FactualVerificationResult.model_validate_json(json_text)

            # Convert to ValidationIssues
            issues = []
            for issue in result.issues:
                severity = Severity(issue.severity.lower())
                details = {}
                if issue.claim_value:
                    details["claim_value"] = issue.claim_value
                if issue.source_value:
                    details["source_value"] = issue.source_value

                issues.append(
                    ValidationIssue(
                        severity=severity,
                        field=issue.field,
                        message=issue.message,
                        details=details if details else None,
                        evidence=issue.evidence,
                    )
                )

            return LLMFactualResult(
                issues=issues,
                claims_checked=result.claims_checked,
                claims_verified=result.claims_verified,
                cost=response.cost_usd or 0.0,
            )

        except Exception as e:
            logger.error(f"LLM factual verification failed: {e}")
            raise


class LLMFactualResult:
    """Result from LLM factual verification."""

    def __init__(
        self,
        issues: list[ValidationIssue],
        claims_checked: int,
        claims_verified: int,
        cost: float,
    ):
        self.issues = issues
        self.claims_checked = claims_checked
        self.claims_verified = claims_verified
        self.cost = cost

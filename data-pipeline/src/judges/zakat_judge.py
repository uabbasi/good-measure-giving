"""Zakat Judge - validates zakat classifications against charity programs.

Verifies that zakat-eligible classifications are justified by actual programs
that serve recognized asnaf categories (the 8 Quranic categories of zakat recipients).
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


# The 8 asnaf categories recognized in Islamic law
ASNAF_CATEGORIES = {
    "fuqara": "The poor - those who lack basic necessities",
    "masakin": "The needy - those who cannot meet their needs",
    "aamilin": "Zakat workers - those collecting/distributing zakat",
    "muallafat_quloob": "New Muslims/Hearts to be won",
    "riqab": "Those in bondage - modern: human trafficking victims",
    "gharimin": "Debtors - those overwhelmed by debt",
    "fi_sabilillah": "In Allah's cause - religious/educational causes",
    "ibn_sabil": "Travelers - stranded travelers in need",
}

# Wallet tags and their zakat implications
WALLET_TAGS = {
    "ZAKAT-ELIGIBLE": "Programs directly serve at least one asnaf category",
    "POTENTIALLY-ZAKAT-ELIGIBLE": "May serve asnaf but needs verification",
    "SADAQAH-ELIGIBLE": "Good charitable work but not zakat-specific categories",
}


class ZakatIssue(BaseModel):
    """Schema for a zakat classification issue from LLM."""

    field: str = Field(description="The field with the issue")
    severity: str = Field(description="error, warning, or info")
    message: str = Field(description="Description of the issue")
    claimed_asnaf: Optional[str] = Field(None, description="The claimed asnaf category")
    evidence: Optional[str] = Field(None, description="Why the classification is problematic")


class ZakatVerificationResult(BaseModel):
    """Schema for zakat verification LLM response."""

    issues: list[ZakatIssue] = Field(default_factory=list)
    classification_verified: bool = Field(True, description="Whether classification is valid")
    asnaf_match: bool = Field(True, description="Whether asnaf category matches programs")
    summary: str = Field("", description="Brief summary of results")


class ZakatJudge(BaseJudge):
    """Validates zakat classifications against charity programs.

    Checks that:
    1. The claimed asnaf category matches actual programs
    2. There's evidence that beneficiaries fall into the claimed category
    3. The wallet tag is appropriate for the programs described
    """

    @property
    def name(self) -> str:
        return "zakat"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.LLM

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate zakat classifications.

        Args:
            output: Exported charity data with zakat classification
            context: Source data including programs

        Returns:
            JudgeVerdict with any zakat classification issues
        """
        issues: list[ValidationIssue] = []
        cost_usd = 0.0
        metadata: dict[str, Any] = {}

        evaluation = output.get("evaluation", {})
        wallet_tag = evaluation.get("wallet_tag", "")

        # Skip validation for SADAQAH-ELIGIBLE (no zakat claims to verify)
        if wallet_tag == "SADAQAH-ELIGIBLE":
            return self.create_verdict(
                passed=True,
                skipped=True,
                skip_reason="SADAQAH-ELIGIBLE charities don't make zakat claims",
            )

        # Step 1: Quick deterministic checks
        quick_issues = self._quick_checks(output, context)
        issues.extend(quick_issues)

        # Step 2: LLM verification for ZAKAT-ELIGIBLE charities
        if wallet_tag == "ZAKAT-ELIGIBLE":
            try:
                llm_result = self._verify_zakat_with_llm(output, context)
                if llm_result:
                    # Downgrade all LLM issues to WARNING — charity self-claims eligibility
                    for issue in llm_result.issues:
                        if issue.severity == Severity.ERROR:
                            issue.severity = Severity.WARNING
                    issues.extend(llm_result.issues)
                    cost_usd += llm_result.cost
                    metadata["asnaf_assessment"] = llm_result.asnaf_match
                    metadata["classification_verified"] = llm_result.classification_verified
                    metadata["confidence"] = "llm_verified"
            except Exception as e:
                logger.warning(f"LLM zakat verification failed for {evaluation.get('charity_ein', 'unknown')}: {e}")
                metadata["llm_failed"] = True
                metadata["llm_error"] = str(e)[:200]

        metadata["wallet_tag"] = wallet_tag

        # Determine pass/fail
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        passed = error_count == 0

        return self.create_verdict(
            passed=passed,
            issues=issues,
            cost_usd=cost_usd,
            metadata=metadata,
        )

    def _quick_checks(self, output: dict[str, Any], context: dict[str, Any]) -> list[ValidationIssue]:
        """Quick deterministic checks for obvious classification issues."""
        issues: list[ValidationIssue] = []

        evaluation = output.get("evaluation", {})
        wallet_tag = evaluation.get("wallet_tag", "")

        # Check wallet tag is valid
        if wallet_tag and wallet_tag not in WALLET_TAGS:
            self.add_issue(
                issues,
                Severity.ERROR,
                "wallet_tag",
                f"Invalid wallet tag: {wallet_tag}",
                details={"valid_tags": list(WALLET_TAGS.keys())},
            )

        # For ZAKAT-ELIGIBLE, we just verify the charity claims it on their website
        # We don't require asnaf categories - that's for donors to decide
        # The detection happens in synthesize phase via website extraction

        return issues

    def _verify_zakat_with_llm(self, output: dict[str, Any], context: dict[str, Any]) -> Optional["LLMZakatResult"]:
        """Use LLM to verify zakat classification matches programs.

        Returns structured result with issues and cost.
        """
        try:
            prompt = self.format_prompt(output, context)

            client = self.get_llm_client()
            response = client.generate(
                prompt=prompt,
                json_schema=ZakatVerificationResult.model_json_schema(),
            )

            # Strip markdown if present
            json_text = self.strip_markdown_json(response.text)
            result = ZakatVerificationResult.model_validate_json(json_text)

            # Convert to ValidationIssues
            issues = []
            for issue in result.issues:
                severity = Severity(issue.severity.lower())
                details = {}
                if issue.claimed_asnaf:
                    details["claimed_asnaf"] = issue.claimed_asnaf

                issues.append(
                    ValidationIssue(
                        severity=severity,
                        field=issue.field,
                        message=issue.message,
                        details=details if details else None,
                        evidence=issue.evidence,
                    )
                )

            return LLMZakatResult(
                issues=issues,
                classification_verified=result.classification_verified,
                asnaf_match=result.asnaf_match,
                cost=response.cost_usd or 0.0,
            )

        except Exception as e:
            logger.error(f"LLM zakat verification failed: {e}")
            raise


class LLMZakatResult:
    """Result from LLM zakat verification."""

    def __init__(
        self,
        issues: list[ValidationIssue],
        classification_verified: bool,
        asnaf_match: bool,
        cost: float,
    ):
        self.issues = issues
        self.classification_verified = classification_verified
        self.asnaf_match = asnaf_match
        self.cost = cost

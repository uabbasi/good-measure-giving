"""Synthesize Quality Judge - validates data integrity from synthesize phase.

Deterministic validation rules that don't require LLM:
- S-J-001: Financial ratio sanity (expense ratios sum to ≤1.0)
- S-J-002: Source attribution completeness (key fields must have attribution)
- S-J-003: Derived field consistency (muslim_charity_fit matches truth table)
- S-J-004: Zakat corroboration required (zakat claims must pass corroboration)
- S-J-005: Working capital bounds (reasonable range 0-120 months)

These rules catch issues with aggregated/synthesized data before scoring phases.
"""

import logging
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Fields that must have source_attribution for traceability
REQUIRED_ATTRIBUTION_FIELDS = [
    "total_revenue",
    "transparency_score",
    "charity_navigator_score",
    "claims_zakat_eligible",
    "founded_year",
]


class SynthesizeQualityJudge(BaseJudge):
    """Judge that validates synthesize-phase data quality.

    Unlike LLM-based judges, this judge runs deterministic checks
    on the synthesized charity_data to catch aggregation issues.
    """

    @property
    def name(self) -> str:
        return "synthesize_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate synthesize-phase data quality.

        Args:
            output: The exported charity data
            context: Source data context (includes charity_data)

        Returns:
            JudgeVerdict with any data quality issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")

        # Get synthesized data from context
        # The charity_data is typically in context or output directly
        charity_data = context.get("charity_data", {})
        if not charity_data:
            # Try to get from output's raw evaluation data
            charity_data = output.get("charity_data", output)

        if not charity_data:
            # No synthesized data - skip validation
            return JudgeVerdict(
                judge_name=self.name,
                passed=True,
                issues=[],
                skipped=True,
                skip_reason="No charity_data found in context",
            )

        # S-J-001: Financial ratio sanity
        issues.extend(self._check_financial_ratio_sanity(ein, charity_data))

        # S-J-002: Source attribution completeness
        issues.extend(self._check_source_attribution(ein, charity_data))

        # S-J-003: Derived field consistency
        issues.extend(self._check_derived_field_consistency(ein, charity_data))

        # S-J-004: Zakat corroboration required
        issues.extend(self._check_zakat_corroboration(ein, charity_data))

        # S-J-005: Working capital bounds
        issues.extend(self._check_working_capital_bounds(ein, charity_data))

        # S-J-006: Hallucination denylist check
        issues.extend(self._check_hallucination_denylist(ein, charity_data))

        # Determine pass/fail - ERROR severity fails, WARNING doesn't
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return JudgeVerdict(
            judge_name=self.name,
            passed=not has_errors,
            issues=issues,
        )

    def _check_financial_ratio_sanity(
        self, ein: str, charity_data: dict
    ) -> list[ValidationIssue]:
        """S-J-001: Verify expense ratios sum to ≤1.0."""
        issues = []

        program_ratio = charity_data.get("program_expense_ratio")
        admin_ratio = charity_data.get("admin_expense_ratio")
        fundraising_ratio = charity_data.get("fundraising_expense_ratio")

        # Only check if we have at least two ratios
        ratios = [r for r in [program_ratio, admin_ratio, fundraising_ratio] if r is not None]
        if len(ratios) >= 2:
            total = sum(ratios)
            # Allow small tolerance for rounding (1.01 instead of 1.0)
            if total > 1.01:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,  # Mathematically impossible
                        field="expense_ratios",
                        message=f"Expense ratios sum to {total:.2f} (>1.0) - mathematically impossible",
                        details={
                            "program_expense_ratio": program_ratio,
                            "admin_expense_ratio": admin_ratio,
                            "fundraising_expense_ratio": fundraising_ratio,
                            "total": total,
                            "rule": "S-J-001",
                        },
                    )
                )

        # Also check individual ratios are in valid range
        for ratio_name, ratio_val in [
            ("program_expense_ratio", program_ratio),
            ("admin_expense_ratio", admin_ratio),
            ("fundraising_expense_ratio", fundraising_ratio),
        ]:
            if ratio_val is not None and (ratio_val < 0 or ratio_val > 1):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,  # Mathematically impossible
                        field=ratio_name,
                        message=f"{ratio_name}={ratio_val:.2f} outside valid range [0, 1]",
                        details={
                            "value": ratio_val,
                            "valid_range": [0, 1],
                            "rule": "S-J-001",
                        },
                    )
                )

        return issues

    def _check_source_attribution(
        self, ein: str, charity_data: dict
    ) -> list[ValidationIssue]:
        """S-J-002: Verify key fields have source attribution."""
        issues = []

        source_attribution = charity_data.get("source_attribution", {})

        for field in REQUIRED_ATTRIBUTION_FIELDS:
            field_value = charity_data.get(field)
            # Only require attribution if field has a truthy value
            # For boolean fields like claims_zakat_eligible, False/0 means
            # "no claim" and doesn't need attribution - only True does
            if field_value:
                attribution = source_attribution.get(field)
                if not attribution:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field=f"source_attribution.{field}",
                            message=f"Field '{field}' has value but no source attribution",
                            details={
                                "field": field,
                                "value": str(field_value)[:100],
                                "rule": "S-J-002",
                            },
                        )
                    )
                elif not attribution.get("source_name"):
                    issues.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            field=f"source_attribution.{field}",
                            message=f"Field '{field}' attribution missing source_name",
                            details={
                                "field": field,
                                "attribution": attribution,
                                "rule": "S-J-002",
                            },
                        )
                    )

        return issues

    def _check_derived_field_consistency(
        self, ein: str, charity_data: dict
    ) -> list[ValidationIssue]:
        """S-J-003: Verify muslim_charity_fit matches truth table."""
        issues = []

        has_islamic_identity = charity_data.get("has_islamic_identity")
        serves_muslim_populations = charity_data.get("serves_muslim_populations")
        muslim_charity_fit = charity_data.get("muslim_charity_fit")

        # Only check if all three fields are present
        if all(v is not None for v in [has_islamic_identity, serves_muslim_populations, muslim_charity_fit]):
            # Truth table from spec:
            # has_identity=True  -> 'high' (regardless of serves_muslims)
            # has_identity=False, serves_muslims=True  -> 'medium'
            # has_identity=False, serves_muslims=False -> 'low'
            expected_fit = None
            if has_islamic_identity:
                expected_fit = "high"
            elif serves_muslim_populations:
                expected_fit = "medium"
            else:
                expected_fit = "low"

            if muslim_charity_fit != expected_fit:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,  # Derived field bug
                        field="muslim_charity_fit",
                        message=f"muslim_charity_fit='{muslim_charity_fit}' doesn't match truth table (expected '{expected_fit}')",
                        details={
                            "has_islamic_identity": has_islamic_identity,
                            "serves_muslim_populations": serves_muslim_populations,
                            "expected_fit": expected_fit,
                            "actual_fit": muslim_charity_fit,
                            "rule": "S-J-003",
                        },
                    )
                )

        return issues

    def _check_zakat_corroboration(
        self, ein: str, charity_data: dict
    ) -> list[ValidationIssue]:
        """S-J-004: Verify zakat claims have passed corroboration."""
        issues = []

        claims_zakat_eligible = charity_data.get("claims_zakat_eligible")

        if claims_zakat_eligible:
            # Check for corroboration failure marker
            # The aggregator sets zakat_claim_evidence to "CORROBORATION FAILED: ..." when it fails
            zakat_evidence = charity_data.get("zakat_claim_evidence", "")
            if isinstance(zakat_evidence, str) and "CORROBORATION FAILED" in zakat_evidence:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="claims_zakat_eligible",
                        message="Zakat eligibility claim failed corroboration but is still True",
                        details={
                            "claims_zakat_eligible": True,
                            "evidence": zakat_evidence[:200],
                            "rule": "S-J-004",
                        },
                    )
                )

            # Also check for source - zakat claims MUST have discoverable source (critical)
            source_attribution = charity_data.get("source_attribution", {})
            zakat_attribution = source_attribution.get("claims_zakat_eligible", {})
            if not zakat_attribution.get("source_url"):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,  # Critical - zakat claims must be verifiable
                        field="claims_zakat_eligible.source_url",
                        message="Zakat eligibility claim has no source URL for verification",
                        details={
                            "claims_zakat_eligible": True,
                            "attribution": zakat_attribution,
                            "rule": "S-J-004",
                        },
                    )
                )

        return issues

    def _check_working_capital_bounds(
        self, ein: str, charity_data: dict
    ) -> list[ValidationIssue]:
        """S-J-005: Verify working capital is within reasonable bounds."""
        issues = []

        working_capital_months = charity_data.get("working_capital_months")

        if working_capital_months is not None:
            # Per bounds_validator.py, valid range is 0-120 months (10 years)
            if working_capital_months < 0:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field="working_capital_months",
                        message=f"Negative working capital ({working_capital_months:.1f} months) indicates financial stress",
                        details={
                            "value": working_capital_months,
                            "interpretation": "Organization has more liabilities than assets",
                            "rule": "S-J-005",
                        },
                    )
                )
            elif working_capital_months > 120:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field="working_capital_months",
                        message=f"Extremely high working capital ({working_capital_months:.1f} months) may indicate hoarding or data error",
                        details={
                            "value": working_capital_months,
                            "max_expected": 120,
                            "rule": "S-J-005",
                        },
                    )
                )

        return issues

    def _check_hallucination_denylist(
        self, ein: str, charity_data: dict
    ) -> list[ValidationIssue]:
        """S-J-006: Check that hallucination-prone fields have corroboration."""
        from src.validators.hallucination_denylist import HALLUCINATION_PRONE_FIELDS

        issues = []
        corroboration = charity_data.get("corroboration_status", {})

        for field_name in HALLUCINATION_PRONE_FIELDS:
            value = charity_data.get(field_name)
            if value is None:
                continue

            field_corroboration = corroboration.get(field_name, {})
            if not field_corroboration.get("passed", False):
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    f"hallucination_denylist.{field_name}",
                    f"Hallucination-prone field '{field_name}' lacks cross-source corroboration",
                    details={
                        "field": field_name,
                        "value": str(value)[:100],
                        "rule": "S-J-006",
                    },
                )

        return issues

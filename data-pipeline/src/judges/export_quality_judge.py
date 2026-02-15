"""Export Quality Judge - validates exported JSON data integrity.

Deterministic validation rules that don't require LLM:
- E-J-001: EIN format - must be XX-XXXXXXX (2 digits, hyphen, 7 digits)
- E-J-002: Name validity - must not be empty or just the EIN
- E-J-003: Tier validity - must be one of: baseline, rich, hidden
- E-J-004: Pillar scores completeness - if present, impact (0-50) and alignment (0-50) required
- E-J-005: Score consistency - pillar sum should match amal_score (with risk tolerance)
  - Default: impact + alignment
  - Legacy: impact + alignment + credibility (when present)
- E-J-006: Multi-lens score bounds - strategicScore/zakatScore in [0, 100]
- E-J-007: Multi-lens evaluation structure - if scores present, evaluations should exist

These rules catch issues in the export transformation before data reaches the frontend.
"""

import re
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

# Valid tier values for exported data
VALID_TIERS = {"baseline", "rich", "hidden"}

# EIN format regex: 2 digits, hyphen, 7 digits
EIN_PATTERN = re.compile(r"^\d{2}-\d{7}$")

# Maximum points per required pillar dimension (default framework)
MAX_PILLAR_SCORES = {"impact": 50, "alignment": 50}
OPTIONAL_PILLAR_SCORES = {"credibility": 50}


class ExportQualityJudge(BaseJudge):
    """Judge that validates export-phase data quality.

    Unlike LLM-based judges, this judge runs deterministic checks
    on the exported JSON to catch transformation errors.
    """

    @property
    def name(self) -> str:
        return "export_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate export-phase data quality.

        Args:
            output: The exported charity data (JSON structure)
            context: Source data context (evaluation, charity_data, etc.)

        Returns:
            JudgeVerdict with any export quality issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")

        # E-J-001: EIN format validation
        issues.extend(self._check_ein_format(ein, output))

        # E-J-002: Name validity
        issues.extend(self._check_name_validity(ein, output))

        # E-J-003: Tier validity
        issues.extend(self._check_tier_validity(ein, output))

        # E-J-004: Pillar scores completeness
        issues.extend(self._check_pillar_scores(ein, output))

        # E-J-005: Score consistency
        issues.extend(self._check_score_consistency(ein, output))

        # E-J-006: Multi-lens score bounds
        issues.extend(self._check_multi_lens_export_scores(ein, output))

        # E-J-007: Multi-lens evaluation structure
        issues.extend(self._check_multi_lens_export_structure(ein, output))

        # Determine pass/fail - ERROR severity fails
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return JudgeVerdict(
            judge_name=self.name,
            passed=not has_errors,
            issues=issues,
        )

    def _check_ein_format(self, ein: str, output: dict) -> list[ValidationIssue]:
        """E-J-001: Verify EIN matches format XX-XXXXXXX."""
        issues = []

        if not ein or ein == "unknown":
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="ein",
                    message="Missing or invalid EIN",
                    details={"value": ein, "rule": "E-J-001"},
                )
            )
        elif not EIN_PATTERN.match(ein):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="ein",
                    message=f"EIN '{ein}' doesn't match format XX-XXXXXXX",
                    details={
                        "value": ein,
                        "expected_format": "XX-XXXXXXX",
                        "rule": "E-J-001",
                    },
                )
            )

        return issues

    def _check_name_validity(self, ein: str, output: dict) -> list[ValidationIssue]:
        """E-J-002: Verify name is not empty or just the EIN."""
        issues = []

        name = output.get("name")

        if not name:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="name",
                    message="Charity name is missing",
                    details={"rule": "E-J-002"},
                )
            )
        elif not name.strip():
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="name",
                    message="Charity name is empty or whitespace-only",
                    details={"value": repr(name), "rule": "E-J-002"},
                )
            )
        elif name == ein or name.replace("-", "") == ein.replace("-", ""):
            # Name is just the EIN (possibly without hyphen)
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="name",
                    message="Charity name is identical to EIN (no actual name)",
                    details={"name": name, "ein": ein, "rule": "E-J-002"},
                )
            )

        return issues

    def _check_tier_validity(self, ein: str, output: dict) -> list[ValidationIssue]:
        """E-J-003: Verify tier is a valid value."""
        issues = []

        tier = output.get("tier")

        if tier is None:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="tier",
                    message="Missing tier field",
                    details={"rule": "E-J-003"},
                )
            )
        elif tier not in VALID_TIERS:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="tier",
                    message=f"Invalid tier '{tier}', must be one of: {', '.join(sorted(VALID_TIERS))}",
                    details={
                        "value": tier,
                        "valid_values": list(VALID_TIERS),
                        "rule": "E-J-003",
                    },
                )
            )

        return issues

    def _check_pillar_scores(self, ein: str, output: dict) -> list[ValidationIssue]:
        """E-J-004: Verify pillar scores completeness and bounds."""
        issues = []

        pillar_scores = output.get("pillarScores")

        # pillarScores is optional - only validate if present
        if pillar_scores is None:
            return issues

        if not isinstance(pillar_scores, dict):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="pillarScores",
                    message=f"pillarScores must be a dict, got {type(pillar_scores).__name__}",
                    details={"rule": "E-J-004"},
                )
            )
            return issues

        # Required dimensions in the default framework
        missing_dims = [d for d in MAX_PILLAR_SCORES if d not in pillar_scores]

        if missing_dims:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="pillarScores",
                    message=f"Missing pillar dimensions: {', '.join(missing_dims)}",
                    details={
                        "missing": missing_dims,
                        "present": list(pillar_scores.keys()),
                        "rule": "E-J-004",
                    },
                )
            )
            return issues

        # Validate required dimension ranges
        for dim, max_score in MAX_PILLAR_SCORES.items():
            score = pillar_scores.get(dim)
            if score is None:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"pillarScores.{dim}",
                        message=f"Pillar score '{dim}' is None",
                        details={"rule": "E-J-004"},
                    )
                )
            elif not isinstance(score, (int, float)):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"pillarScores.{dim}",
                        message=f"Pillar score '{dim}' must be numeric, got {type(score).__name__}",
                        details={"value": str(score), "rule": "E-J-004"},
                    )
                )
            elif score < 0 or score > max_score:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"pillarScores.{dim}",
                        message=f"Pillar score '{dim}'={score} outside valid range [0, {max_score}]",
                        details={
                            "value": score,
                            "valid_range": [0, max_score],
                            "rule": "E-J-004",
                        },
                    )
                )

        # Validate optional legacy dimensions if present
        for dim, max_score in OPTIONAL_PILLAR_SCORES.items():
            if dim not in pillar_scores:
                continue
            score = pillar_scores.get(dim)
            if score is None:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"pillarScores.{dim}",
                        message=f"Optional pillar score '{dim}' is None",
                        details={"rule": "E-J-004"},
                    )
                )
            elif not isinstance(score, (int, float)):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"pillarScores.{dim}",
                        message=f"Optional pillar score '{dim}' must be numeric, got {type(score).__name__}",
                        details={"value": str(score), "rule": "E-J-004"},
                    )
                )
            elif score < 0 or score > max_score:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"pillarScores.{dim}",
                        message=f"Optional pillar score '{dim}'={score} outside valid range [0, {max_score}]",
                        details={
                            "value": score,
                            "valid_range": [0, max_score],
                            "rule": "E-J-004",
                        },
                    )
                )

        return issues

    def _check_score_consistency(self, ein: str, output: dict) -> list[ValidationIssue]:
        """E-J-005: Verify pillar sum matches amal_score."""
        issues = []

        pillar_scores = output.get("pillarScores")
        amal_score = output.get("amalScore")

        # Only check if both are present
        if pillar_scores is None or amal_score is None:
            return issues

        if not isinstance(pillar_scores, dict):
            return issues  # Already caught by E-J-004

        if not isinstance(amal_score, (int, float)):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="amalScore",
                    message=f"amalScore must be numeric, got {type(amal_score).__name__}",
                    details={"value": str(amal_score), "rule": "E-J-005"},
                )
            )
            return issues

        # Calculate pillar sums
        try:
            impact = pillar_scores.get("impact", 0) or 0
            alignment = pillar_scores.get("alignment", 0) or 0
            credibility = pillar_scores.get("credibility")
            pillar_sum = impact + alignment
            pillar_sum_with_credibility = (
                pillar_sum + credibility if isinstance(credibility, (int, float)) else None
            )
        except (TypeError, ValueError):
            return issues  # Non-numeric values caught by E-J-004

        # amal_score = pillar_sum + risk_deduction (risk is negative, max -10)
        # So pillar_sum should be >= amal_score (within tolerance)
        min_expected = amal_score  # With max risk deduction
        max_expected = amal_score + 10  # With no risk deduction

        two_pillar_in_range = min_expected - 0.01 <= pillar_sum <= max_expected + 0.01
        three_pillar_in_range = (
            isinstance(pillar_sum_with_credibility, (int, float))
            and min_expected - 0.01 <= pillar_sum_with_credibility <= max_expected + 0.01
        )

        if not two_pillar_in_range and not three_pillar_in_range:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="amalScore",
                    message=f"Pillar sum ({pillar_sum}) inconsistent with amalScore ({amal_score})",
                    details={
                        "pillar_sum_impact_alignment": pillar_sum,
                        "pillar_sum_impact_alignment_credibility": pillar_sum_with_credibility,
                        "amal_score": amal_score,
                        "expected_range": f"[{min_expected}, {max_expected}]",
                        "pillar_breakdown": {
                            "impact": impact,
                            "alignment": alignment,
                            "credibility": credibility,
                        },
                        "rule": "E-J-005",
                    },
                )
            )

        return issues

    def _check_multi_lens_export_scores(
        self,
        ein: str,
        output: dict,  # noqa: ARG002
    ) -> list[ValidationIssue]:
        """E-J-006: Verify strategicScore and zakatScore are within [0, 100] if present."""
        issues = []

        for field, rule in [("strategicScore", "E-J-006a"), ("zakatScore", "E-J-006b")]:
            score = output.get(field)
            if score is None:
                continue

            if not isinstance(score, (int, float)):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=field,
                        message=f"{field} must be numeric, got {type(score).__name__}",
                        details={"value": str(score), "rule": rule},
                    )
                )
            elif score < 0 or score > 100:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=field,
                        message=f"{field}={score} outside valid range [0, 100]",
                        details={"value": score, "valid_range": [0, 100], "rule": rule},
                    )
                )

        return issues

    def _check_multi_lens_export_structure(
        self,
        ein: str,
        output: dict,  # noqa: ARG002
    ) -> list[ValidationIssue]:
        """E-J-007: Verify multi-lens evaluation structure consistency.

        If strategicScore is present, strategicEvaluation should also exist (and vice versa).
        Same for zakatScore / zakatEvaluation.
        """
        issues = []

        for score_field, eval_field, rule in [
            ("strategicScore", "strategicEvaluation", "E-J-007a"),
            ("zakatScore", "zakatEvaluation", "E-J-007b"),
        ]:
            score = output.get(score_field)
            evaluation = output.get(eval_field)

            # Score present but no evaluation detail
            if score is not None and evaluation is None:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field=eval_field,
                        message=f"{score_field}={score} but {eval_field} is missing",
                        details={"rule": rule},
                    )
                )

            # Evaluation present — check it has required structure
            if evaluation and isinstance(evaluation, dict):
                total = evaluation.get("total_score")
                dims = evaluation.get("dimensions")

                if total is None:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field=f"{eval_field}.total_score",
                            message=f"{eval_field} missing total_score",
                            details={"rule": rule},
                        )
                    )

                if not dims or not isinstance(dims, dict):
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field=f"{eval_field}.dimensions",
                            message=f"{eval_field} missing or invalid dimensions",
                            details={"rule": rule},
                        )
                    )

        return issues

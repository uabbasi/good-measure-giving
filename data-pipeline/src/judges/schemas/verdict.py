"""Verdict schemas for LLM judge results.

Defines the common result types used by all judges to report validation
issues, warnings, and overall pass/fail status.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Severity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Blocks approval, requires human review
    WARNING = "warning"  # Logged but doesn't block
    INFO = "info"  # Informational, for debugging


class ScoreChangeSeverity(str, Enum):
    """Severity level for score changes detected via diff validation.

    Used to categorize the significance of score changes between commits.
    """

    INFO = "info"  # 1-5 points - minor fluctuation
    WARNING = "warning"  # 6-15 points - notable change, may need review
    ERROR = "error"  # 16+ points - significant change, likely needs review


@dataclass
class ValidationIssue:
    """A specific validation issue found by a judge.

    Attributes:
        severity: How serious the issue is (error, warning, info)
        field: The field or component where the issue was found
        message: Human-readable description of the issue
        details: Optional structured data about the issue
        evidence: Supporting evidence for why this is an issue
    """

    severity: Severity
    field: str
    message: str
    details: Optional[dict[str, Any]] = None
    evidence: Optional[str] = None
    issue_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "severity": self.severity.value,
            "field": self.field,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.evidence:
            result["evidence"] = self.evidence
        if self.issue_key:
            result["issue_key"] = self.issue_key
        return result


@dataclass
class JudgeVerdict:
    """Result from a single judge's validation.

    Attributes:
        passed: Whether the validation passed (no errors)
        judge_name: Name of the judge that produced this verdict
        issues: List of validation issues found
        skipped: Whether this judge was skipped (e.g., not applicable)
        skip_reason: Why the judge was skipped
        cost_usd: Estimated cost of LLM calls for this validation
        metadata: Additional judge-specific metadata
    """

    passed: bool
    judge_name: str
    issues: list[ValidationIssue] = field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get only error-severity issues."""
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get only warning-severity issues."""
        return [i for i in self.issues if i.severity == Severity.WARNING]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "judge_name": self.judge_name,
            "issues": [i.to_dict() for i in self.issues],
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "cost_usd": self.cost_usd,
            "metadata": self.metadata,
        }


@dataclass
class CharityValidationResult:
    """Aggregated validation result for a single charity.

    Combines results from all judges that evaluated the charity.
    """

    ein: str
    name: str
    passed: bool
    verdicts: list[JudgeVerdict] = field(default_factory=list)
    total_cost_usd: float = 0.0

    @property
    def all_errors(self) -> list[ValidationIssue]:
        """Get all errors across all judges."""
        errors = []
        for verdict in self.verdicts:
            errors.extend(verdict.errors)
        return errors

    @property
    def all_warnings(self) -> list[ValidationIssue]:
        """Get all warnings across all judges."""
        warnings = []
        for verdict in self.verdicts:
            warnings.extend(verdict.warnings)
        return warnings

    @property
    def deduplicated_issues(self) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        """Get errors and warnings after deduplicating by issue_key.

        Issues sharing the same issue_key are deduplicated — only the
        highest-severity instance counts. Issues without an issue_key
        pass through unchanged.

        Returns:
            (errors, warnings) tuple with deduplicated issues.
        """
        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}

        keyed: dict[str, ValidationIssue] = {}
        unkeyed: list[ValidationIssue] = []

        for verdict in self.verdicts:
            for issue in verdict.issues:
                if issue.issue_key:
                    existing = keyed.get(issue.issue_key)
                    if existing is None or severity_order.get(issue.severity, 99) < severity_order.get(
                        existing.severity, 99
                    ):
                        keyed[issue.issue_key] = issue
                else:
                    unkeyed.append(issue)

        all_issues = list(keyed.values()) + unkeyed
        errors = [i for i in all_issues if i.severity == Severity.ERROR]
        warnings = [i for i in all_issues if i.severity == Severity.WARNING]
        return errors, warnings

    @property
    def flagged(self) -> bool:
        """Whether this charity should be flagged for human review."""
        return not self.passed or len(self.all_errors) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ein": self.ein,
            "name": self.name,
            "passed": self.passed,
            "flagged": self.flagged,
            "error_count": len(self.all_errors),
            "warning_count": len(self.all_warnings),
            "verdicts": [v.to_dict() for v in self.verdicts],
            "total_cost_usd": self.total_cost_usd,
        }

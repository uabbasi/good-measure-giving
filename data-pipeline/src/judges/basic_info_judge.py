"""Basic Info Judge - validates that charities have essential basic information.

Checks for:
1. Required fields that affect donor understanding (mission, city, state)
2. Recommended fields that improve credibility (address, founded_year)

Unlike other judges that validate generated content quality, this judge
checks data completeness at a basic level to identify charities that
may need manual data enrichment.
"""

import logging
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


class BasicInfoJudge(BaseJudge):
    """Judge that validates charities have essential basic information.

    This is a non-LLM judge that performs deterministic checks on
    the presence of key fields in the charities and charity_data tables.
    """

    # Required fields - WARNING severity if missing
    # These are essential for donor understanding
    REQUIRED_FIELDS = {
        "mission": "Mission statement needed for donor understanding",
        "city": "City needed for location verification",
        "state": "State needed for location verification",
    }

    # Recommended fields - INFO severity if missing
    # These improve credibility but aren't essential
    RECOMMENDED_FIELDS = {
        "address": "Street address improves credibility",
        "founded_year": "Founding year helps donors assess track record",
    }

    @property
    def name(self) -> str:
        return "basic_info"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate basic info completeness for a charity.

        Args:
            output: The exported charity data (from export.py)
            context: Source data context (includes charity and charity_data)

        Returns:
            JudgeVerdict with any data completeness issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", context.get("ein", "unknown"))
        charity_name = output.get("name", "Unknown")

        # Get charity data from context if available, otherwise use output
        charity = context.get("charity", output)
        charity_data = context.get("charity_data", {})

        # Check required fields (WARNING severity)
        for field, reason in self.REQUIRED_FIELDS.items():
            value = self._get_field_value(field, charity, charity_data, output)
            if not value:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field=field,
                        message=f"Missing {field}: {reason}",
                        details={
                            "ein": ein,
                            "charity_name": charity_name,
                            "field": field,
                        },
                    )
                )

        # Check recommended fields (INFO severity)
        for field, reason in self.RECOMMENDED_FIELDS.items():
            value = self._get_field_value(field, charity, charity_data, output)
            if not value:
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        field=field,
                        message=f"Missing {field}: {reason}",
                        details={
                            "ein": ein,
                            "charity_name": charity_name,
                            "field": field,
                        },
                    )
                )

        # This judge doesn't fail charities - it only warns
        # All issues are WARNING or INFO, no ERRORs
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return JudgeVerdict(
            passed=not has_errors,
            judge_name=self.name,
            issues=issues,
            metadata={
                "ein": ein,
                "charity_name": charity_name,
                "required_fields_missing": sum(
                    1 for i in issues
                    if i.severity == Severity.WARNING and i.field in self.REQUIRED_FIELDS
                ),
                "recommended_fields_missing": sum(
                    1 for i in issues
                    if i.severity == Severity.INFO and i.field in self.RECOMMENDED_FIELDS
                ),
            },
        )

    def _get_field_value(
        self,
        field: str,
        charity: dict,
        charity_data: dict,
        output: dict,
    ) -> Any:
        """Get field value from available sources.

        Priority: charity table > charity_data table > output

        Special handling for founded_year which is in charity_data.
        """
        # Some fields live in specific tables
        if field == "founded_year":
            return charity_data.get("founded_year")

        # Location fields from charity table, then output's location object
        if field in ("city", "state", "zip", "address"):
            value = charity.get(field)
            if value:
                return value
            # Check output's location object
            location = output.get("location", {})
            if location:
                return location.get(field)
            return None

        # Mission - try charity table first, then output
        if field == "mission":
            return charity.get("mission") or output.get("mission")

        # Generic fallback
        return charity.get(field) or charity_data.get(field) or output.get(field)

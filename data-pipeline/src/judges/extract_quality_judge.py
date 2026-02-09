"""Extract Quality Judge - validates data integrity from extract phase.

Deterministic validation rules that don't require LLM:
- E-J-001: Schema validation (Pydantic field type/format validation)
- E-J-002: Bounds validation (numeric fields within FIELD_BOUNDS)
- E-J-003: Cross-source EIN consistency (EIN matches across all sources)

These rules catch parsing and extraction issues before downstream phases.
"""

import logging
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


class ExtractQualityJudge(BaseJudge):
    """Judge that validates extract-phase data quality.

    Unlike LLM-based judges, this judge runs deterministic checks
    on the parsed_json data to catch extraction issues.
    """

    @property
    def name(self) -> str:
        return "extract_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate extract-phase data quality.

        Args:
            output: The exported charity data
            context: Source data context (includes raw_scraped_data with parsed_json)

        Returns:
            JudgeVerdict with any data quality issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")

        # Get source data from context
        source_data = context.get("source_data", {})

        # E-J-001: Schema validation
        issues.extend(self._check_schema_validation(ein, source_data))

        # E-J-002: Bounds validation
        issues.extend(self._check_bounds_validation(ein, source_data))

        # E-J-003: Cross-source EIN consistency
        issues.extend(self._check_ein_consistency(ein, source_data))

        # Determine pass/fail
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return JudgeVerdict(
            judge_name=self.name,
            passed=not has_errors,
            issues=issues,
        )

    def _check_schema_validation(self, ein: str, source_data: dict) -> list[ValidationIssue]:
        """E-J-001: Validate fields match expected types and formats."""
        issues = []

        # Define expected field types for each source
        schema_expectations = {
            "propublica": {
                "propublica_990": {
                    "total_revenue": (int, float, type(None)),
                    "total_expenses": (int, float, type(None)),
                    "total_assets": (int, float, type(None)),
                    "tax_year": (int, type(None)),
                    "irs_ruling_year": (int, type(None)),
                    "employees_count": (int, type(None)),
                    "ein": (str, type(None)),
                    "name": (str, type(None)),
                }
            },
            "charity_navigator": {
                "cn_profile": {
                    "total_revenue": (int, float, type(None)),
                    "total_expenses": (int, float, type(None)),
                    "program_expense_ratio": (int, float, type(None)),
                    "star_rating": (int, float, type(None)),
                    "overall_score": (int, float, type(None)),
                    "ein": (str, type(None)),
                    "name": (str, type(None)),
                }
            },
            "candid": {
                "candid_profile": {
                    "board_size": (int, type(None)),
                    "irs_ruling_year": (int, type(None)),
                    "metrics_count": (int, type(None)),
                    "ein": (str, type(None)),
                    "name": (str, type(None)),
                    "candid_seal": (str, type(None)),
                }
            },
        }

        # Authoritative sources where type mismatch indicates extraction bug
        authoritative_sources = {"propublica", "charity_navigator", "candid"}

        for source_name, schemas in schema_expectations.items():
            source = source_data.get(source_name, {})
            if not source:
                continue

            # Type mismatches in authoritative sources are ERRORs (extraction bug)
            is_authoritative = source_name in authoritative_sources

            for schema_key, fields in schemas.items():
                schema_data = source.get(schema_key, {})
                if not schema_data:
                    continue

                for field_name, expected_types in fields.items():
                    value = schema_data.get(field_name)
                    if value is not None and not isinstance(value, expected_types):
                        issues.append(
                            ValidationIssue(
                                severity=Severity.ERROR if is_authoritative else Severity.WARNING,
                                field=f"{source_name}.{schema_key}.{field_name}",
                                message=f"Type mismatch: expected {expected_types}, got {type(value).__name__}",
                                details={
                                    "expected_types": str(expected_types),
                                    "actual_type": type(value).__name__,
                                    "value": str(value)[:100],
                                    "is_authoritative": is_authoritative,
                                    "rule": "E-J-001",
                                },
                            )
                        )

        return issues

    def _check_bounds_validation(self, ein: str, source_data: dict) -> list[ValidationIssue]:
        """E-J-002: Validate numeric fields are within reasonable bounds."""
        issues = []

        # Import bounds from the validator module
        try:
            from src.validators.bounds_validator import FIELD_BOUNDS
        except ImportError:
            logger.warning("Could not import FIELD_BOUNDS, skipping bounds validation")
            return []

        # Fields to check across all sources
        numeric_fields = [
            "total_revenue",
            "total_expenses",
            "total_assets",
            "program_expenses",
            "admin_expenses",
            "fundraising_expenses",
            "program_expense_ratio",
            "admin_expense_ratio",
            "fundraising_expense_ratio",
            "employees_count",
            "volunteers_count",
            "board_size",
            "tax_year",
            "irs_ruling_year",
            "founded_year",
            "year_founded",
        ]

        # All these are authoritative sources - bounds violations are ERRORs
        sources_to_check = [
            ("propublica", "propublica_990"),
            ("charity_navigator", "cn_profile"),
            ("candid", "candid_profile"),
        ]

        for source_name, schema_key in sources_to_check:
            source = source_data.get(source_name, {})
            if not source:
                continue

            schema_data = source.get(schema_key, {})
            if not schema_data:
                continue

            for field_name in numeric_fields:
                value = schema_data.get(field_name)
                if value is None:
                    continue

                # Try to convert to float for comparison
                try:
                    float_val = float(value)
                except (ValueError, TypeError):
                    continue

                # Check against bounds if defined
                bounds = FIELD_BOUNDS.get(field_name)
                if bounds:
                    min_val, max_val = bounds
                    # Skip 0 values for count fields where 0 means "not found"
                    # E.g., board_size=0 means LLM couldn't find it, not that there's no board
                    # But financial fields (revenue, expenses) where 0 is meaningful still get checked
                    ZERO_MEANS_NOT_FOUND = {"board_size", "employees_count", "volunteers_count"}
                    if float_val == 0 and field_name in ZERO_MEANS_NOT_FOUND:
                        continue
                    if float_val < min_val or float_val > max_val:
                        issues.append(
                            ValidationIssue(
                                severity=Severity.WARNING,  # Bounds violations are warnings, not errors
                                field=f"{source_name}.{schema_key}.{field_name}",
                                message=f"Value {float_val:,.0f} outside bounds [{min_val:,.0f}, {max_val:,.0f}]",
                                details={
                                    "value": float_val,
                                    "min_bound": min_val,
                                    "max_bound": max_val,
                                    "rule": "E-J-002",
                                },
                            )
                        )

        return issues

    def _check_ein_consistency(self, expected_ein: str, source_data: dict) -> list[ValidationIssue]:
        """E-J-003: Verify EIN is consistent across all sources."""
        issues = []

        # Normalize expected EIN
        expected_clean = expected_ein.replace("-", "")

        # Sources and their schema keys that contain EIN
        # Only check authoritative sources here - website EIN is checked by crawl_quality_judge
        ein_sources = [
            ("propublica", "propublica_990", "ein", True),  # Authoritative
            ("charity_navigator", "cn_profile", "ein", True),  # Authoritative
            ("candid", "candid_profile", "ein", True),  # Authoritative
            ("bbb", "bbb_profile", "ein", True),  # Authoritative
            ("website", "website_profile", "ein", False),  # LLM-extracted, WARNING not ERROR
        ]

        eins_found = {}

        for source_name, schema_key, ein_field, is_authoritative in ein_sources:
            source = source_data.get(source_name, {})
            if not source:
                continue

            schema_data = source.get(schema_key, {})
            if not schema_data:
                continue

            source_ein = schema_data.get(ein_field)
            # Filter out None, empty strings, and the string "null" (LLM artifact)
            if source_ein and str(source_ein).lower() not in ("null", "none", ""):
                source_ein_clean = str(source_ein).replace("-", "")
                eins_found[source_name] = source_ein_clean

                # Check if it matches expected
                if source_ein_clean != expected_clean:
                    # Website is LLM-extracted, so only warn; others are authoritative, so error
                    severity = Severity.ERROR if is_authoritative else Severity.WARNING
                    # Website EIN mismatches share an issue_key with crawl_quality_judge's J-006
                    issue_key = "ein_website_mismatch" if source_name == "website" else None
                    issues.append(
                        ValidationIssue(
                            severity=severity,
                            field=f"{source_name}.{schema_key}.{ein_field}",
                            message=f"EIN mismatch: expected {expected_ein}, got {source_ein}",
                            details={
                                "expected_ein": expected_ein,
                                "source_ein": source_ein,
                                "source": source_name,
                                "is_authoritative": is_authoritative,
                                "rule": "E-J-003",
                            },
                            issue_key=issue_key,
                        )
                    )

        # Also check cross-source consistency (all extracted EINs should match each other)
        # ERROR only if authoritative sources disagree with EACH OTHER (not just with website)
        unique_eins = set(eins_found.values())
        if len(unique_eins) > 1:
            # Get EINs from authoritative sources only
            authoritative_sources = {"propublica", "charity_navigator", "candid", "bbb"}
            authoritative_eins = {eins_found[src] for src in eins_found if src in authoritative_sources}
            # ERROR only if authoritative sources disagree with each other
            has_authoritative_conflict = len(authoritative_eins) > 1

            # When only website disagrees with authoritative sources, deduplicate
            # with the website EIN mismatch issue from crawl_quality_judge
            issue_key = None if has_authoritative_conflict else "ein_website_mismatch"
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR if has_authoritative_conflict else Severity.WARNING,
                    field="multi_source.ein_consistency",
                    message=f"Multiple different EINs found across sources: {unique_eins}",
                    details={
                        "eins_by_source": eins_found,
                        "unique_eins": list(unique_eins),
                        "authoritative_eins": list(authoritative_eins),
                        "has_authoritative_conflict": has_authoritative_conflict,
                        "rule": "E-J-003",
                    },
                    issue_key=issue_key,
                )
            )

        return issues

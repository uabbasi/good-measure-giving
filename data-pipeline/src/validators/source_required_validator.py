"""
Source-Required Fields Validator.

Prevents LLM hallucination by ensuring certain fields are ONLY set when their
required source data actually exists. This validator acts as a guard against
LLMs fabricating values (scores, seals, beneficiary counts) when no underlying
data supports them.

Usage:
    validator = SourceRequiredValidator()
    value, is_valid = validator.validate("cn_overall_score", 85.0, source_data)
    if not is_valid:
        # value is None, field should not be set
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    """Defines a validation rule for a source-required field."""

    field_name: str
    description: str
    validator: Callable[[Any, Dict[str, Any]], bool]
    error_message: str


@dataclass
class ValidationResult:
    """Result of validating a source-required field."""

    field_name: str
    original_value: Any
    validated_value: Any  # None if source missing
    is_valid: bool
    error_message: Optional[str] = None


@dataclass
class BulkValidationResult:
    """Results from validating multiple fields."""

    results: List[ValidationResult] = field(default_factory=list)

    @property
    def all_valid(self) -> bool:
        """Check if all validations passed."""
        return all(r.is_valid for r in self.results)

    @property
    def nullified_fields(self) -> List[str]:
        """Get list of fields that were nullified due to missing sources."""
        return [r.field_name for r in self.results if not r.is_valid]

    def get_errors(self) -> Dict[str, str]:
        """Get mapping of field names to error messages."""
        return {r.field_name: r.error_message for r in self.results if not r.is_valid and r.error_message}


class SourceRequiredValidator:
    """
    Validates that fields are only set when their required source data exists.

    This validator prevents LLM hallucination by enforcing data provenance rules.
    If the required source data doesn't exist, the field value is nullified.

    Example:
        cn_overall_score requires cn_profile to exist
        candid_seal requires candid_profile to exist
        givewell_top_charity requires "givewell" in evaluation_sources
        beneficiaries_served_annually requires website or candid beneficiaries data
    """

    def __init__(self) -> None:
        """Initialize with default validation rules."""
        self._rules: Dict[str, ValidationRule] = {}
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register the default source-required validation rules."""

        # cn_overall_score requires cn_profile data
        self.register_rule(
            ValidationRule(
                field_name="cn_overall_score",
                description="Charity Navigator overall score requires CN profile data",
                validator=lambda value, sources: self._has_cn_profile(sources),
                error_message="cn_overall_score set but cn_profile is missing or empty",
            )
        )

        # cn_financial_score requires cn_profile data
        self.register_rule(
            ValidationRule(
                field_name="cn_financial_score",
                description="Charity Navigator financial score requires CN profile data",
                validator=lambda value, sources: self._has_cn_profile(sources),
                error_message="cn_financial_score set but cn_profile is missing or empty",
            )
        )

        # cn_accountability_score requires cn_profile data
        self.register_rule(
            ValidationRule(
                field_name="cn_accountability_score",
                description="Charity Navigator accountability score requires CN profile data",
                validator=lambda value, sources: self._has_cn_profile(sources),
                error_message="cn_accountability_score set but cn_profile is missing or empty",
            )
        )

        # candid_seal requires candid_profile data
        self.register_rule(
            ValidationRule(
                field_name="candid_seal",
                description="Candid seal requires Candid profile data",
                validator=lambda value, sources: self._has_candid_profile(sources),
                error_message="candid_seal set but candid_profile is missing or empty",
            )
        )

        # is_givewell_top_charity requires givewell source
        self.register_rule(
            ValidationRule(
                field_name="is_givewell_top_charity",
                description="GiveWell top charity status requires GiveWell data",
                validator=lambda value, sources: self._has_givewell_source(sources),
                error_message="is_givewell_top_charity set but no GiveWell source data",
            )
        )

        # givewell_* fields require givewell source
        for givewell_field in [
            "givewell_evidence_rating",
            "givewell_cost_per_life_saved",
            "givewell_cost_effectiveness_multiplier",
            "givewell_cause_area",
        ]:
            self.register_rule(
                ValidationRule(
                    field_name=givewell_field,
                    description=f"{givewell_field} requires GiveWell data",
                    validator=lambda value, sources: self._has_givewell_source(sources),
                    error_message=f"{givewell_field} set but no GiveWell source data",
                )
            )

        # beneficiaries_served_annually requires actual beneficiaries data
        self.register_rule(
            ValidationRule(
                field_name="beneficiaries_served_annually",
                description="Beneficiaries count requires website or Candid beneficiaries data",
                validator=lambda value, sources: self._has_beneficiaries_source(sources),
                error_message="beneficiaries_served_annually set but no beneficiaries data in website_profile or candid_profile",
            )
        )

    def register_rule(self, rule: ValidationRule) -> None:
        """
        Register a validation rule for a field.

        Args:
            rule: The validation rule to register
        """
        self._rules[rule.field_name] = rule
        logger.debug(f"Registered validation rule for field: {rule.field_name}")

    def get_protected_fields(self) -> List[str]:
        """Get list of all fields protected by validation rules."""
        return list(self._rules.keys())

    def validate(
        self,
        field_name: str,
        value: Any,
        source_data: Dict[str, Any],
    ) -> Tuple[Any, bool]:
        """
        Validate that a field's value should be set given the available sources.

        Args:
            field_name: Name of the field being validated
            value: The value to validate
            source_data: Dict containing source profiles (cn_profile, candid_profile, etc.)

        Returns:
            Tuple of (validated_value, is_valid)
            - If source exists: (original_value, True)
            - If source missing: (None, False) and logs a warning
        """
        # If value is None/empty, no validation needed
        if value is None:
            return (None, True)

        # If no rule exists for this field, pass through
        if field_name not in self._rules:
            return (value, True)

        rule = self._rules[field_name]

        # Run the validator
        is_valid = rule.validator(value, source_data)

        if is_valid:
            return (value, True)
        else:
            logger.warning(f"Source-required validation failed: {rule.error_message} (attempted value: {value})")
            return (None, False)

    def validate_result(
        self,
        field_name: str,
        value: Any,
        source_data: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate a field and return a detailed ValidationResult.

        Args:
            field_name: Name of the field being validated
            value: The value to validate
            source_data: Dict containing source profiles

        Returns:
            ValidationResult with full details
        """
        validated_value, is_valid = self.validate(field_name, value, source_data)

        error_message = None
        if not is_valid and field_name in self._rules:
            error_message = self._rules[field_name].error_message

        return ValidationResult(
            field_name=field_name,
            original_value=value,
            validated_value=validated_value,
            is_valid=is_valid,
            error_message=error_message,
        )

    def validate_dict(
        self,
        data: Dict[str, Any],
        source_data: Dict[str, Any],
    ) -> BulkValidationResult:
        """
        Validate all protected fields in a dictionary.

        Args:
            data: Dictionary containing field values
            source_data: Dict containing source profiles

        Returns:
            BulkValidationResult with validation results for all protected fields
        """
        result = BulkValidationResult()

        for field_name in self._rules:
            if field_name in data:
                validation = self.validate_result(field_name, data[field_name], source_data)
                result.results.append(validation)

        return result

    def apply_to_dict(
        self,
        data: Dict[str, Any],
        source_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply validation to a dictionary, nullifying invalid fields.

        This is a convenience method that modifies the dictionary in place
        and returns it.

        Args:
            data: Dictionary containing field values
            source_data: Dict containing source profiles

        Returns:
            The modified dictionary with invalid fields set to None
        """
        for field_name in self._rules:
            if field_name in data:
                validated_value, _ = self.validate(field_name, data[field_name], source_data)
                data[field_name] = validated_value

        return data

    # ========================================================================
    # Source Check Methods
    # ========================================================================

    @staticmethod
    def _has_cn_profile(sources: Dict[str, Any]) -> bool:
        """Check if Charity Navigator profile data exists."""
        cn_profile = sources.get("cn_profile")
        if not cn_profile:
            return False
        # Check for meaningful data (not just empty dict)
        return bool(cn_profile.get("overall_score") or cn_profile.get("name"))

    @staticmethod
    def _has_candid_profile(sources: Dict[str, Any]) -> bool:
        """Check if Candid profile data exists."""
        candid_profile = sources.get("candid_profile")
        if not candid_profile:
            return False
        # Check for meaningful data (not just empty dict)
        return bool(candid_profile.get("candid_seal") or candid_profile.get("name") or candid_profile.get("mission"))

    @staticmethod
    def _has_givewell_source(sources: Dict[str, Any]) -> bool:
        """Check if GiveWell source data exists."""
        # Check for givewell_profile
        givewell_profile = sources.get("givewell_profile")
        if givewell_profile:
            return True

        # Check evaluation_sources list
        evaluation_sources = sources.get("evaluation_sources", [])
        if isinstance(evaluation_sources, list):
            return any("givewell" in str(source).lower() for source in evaluation_sources)

        return False

    @staticmethod
    def _has_beneficiaries_source(sources: Dict[str, Any]) -> bool:
        """
        Check if beneficiaries data exists in website or Candid profile.

        Beneficiaries can come from:
        1. website_profile.beneficiaries_served
        2. website_profile.ummah_gap_data.beneficiary_count
        3. website_profile.impact_metrics.metrics (with beneficiary-like keys)
        4. candid_profile.beneficiaries_served
        """
        # Check Candid profile
        candid_profile = sources.get("candid_profile")
        if candid_profile and candid_profile.get("beneficiaries_served"):
            return True

        # Check website profile
        website_profile = sources.get("website_profile")
        if not website_profile:
            return False

        # Direct beneficiaries field
        if website_profile.get("beneficiaries_served"):
            return True

        # ummah_gap_data
        ummah_gap = website_profile.get("ummah_gap_data", {})
        if ummah_gap.get("beneficiary_count"):
            return True

        # impact_metrics.metrics (must include a numeric beneficiary-like value)
        impact = website_profile.get("impact_metrics", {})
        metrics_dict = impact.get("metrics", {})
        if metrics_dict:
            people_patterns = [
                "people",
                "beneficiar",
                "served",
                "impacted",
                "reached",
                "helped",
                "patient",
                "student",
                "household",
                "family",
                "client",
                "recipient",
                "individual",
                "participant",
                "refugee",
                "orphan",
            ]
            for key, value in metrics_dict.items():
                if not any(p in key.lower() for p in people_patterns):
                    continue
                if isinstance(value, (int, float)) and value > 0:
                    return True
                if isinstance(value, str):
                    # Look for at least one numeric token in string metrics.
                    import re

                    if re.search(r"\d", value):
                        return True

        return False


# Convenience function for single-field validation
def validate_source_required(
    field_name: str,
    value: Any,
    source_data: Dict[str, Any],
) -> Tuple[Any, bool]:
    """
    Convenience function to validate a single field.

    Args:
        field_name: Name of the field being validated
        value: The value to validate
        source_data: Dict containing source profiles

    Returns:
        Tuple of (validated_value, is_valid)
    """
    validator = SourceRequiredValidator()
    return validator.validate(field_name, value, source_data)

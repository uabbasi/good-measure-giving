"""
Tests for SourceRequiredValidator.

Tests the anti-hallucination validation that ensures fields are only set
when their required source data exists.
"""

import pytest

from src.validators.source_required_validator import (
    SourceRequiredValidator,
    ValidationRule,
    validate_source_required,
)


class TestSourceRequiredValidator:
    """Test the SourceRequiredValidator class."""

    @pytest.fixture
    def validator(self):
        return SourceRequiredValidator()

    # ========================================================================
    # CN Score Validation Tests
    # ========================================================================

    def test_cn_overall_score_valid_with_cn_profile(self, validator):
        """cn_overall_score should be valid when cn_profile exists with data."""
        source_data = {
            "cn_profile": {"overall_score": 85.0, "name": "Test Charity"},
        }
        value, is_valid = validator.validate("cn_overall_score", 85.0, source_data)
        assert is_valid is True
        assert value == 85.0

    def test_cn_overall_score_invalid_without_cn_profile(self, validator):
        """cn_overall_score should be nullified when cn_profile is missing."""
        source_data = {
            "cn_profile": None,
        }
        value, is_valid = validator.validate("cn_overall_score", 85.0, source_data)
        assert is_valid is False
        assert value is None

    def test_cn_overall_score_invalid_with_empty_cn_profile(self, validator):
        """cn_overall_score should be nullified when cn_profile is empty dict."""
        source_data = {
            "cn_profile": {},
        }
        value, is_valid = validator.validate("cn_overall_score", 85.0, source_data)
        assert is_valid is False
        assert value is None

    def test_cn_financial_score_invalid_without_cn_profile(self, validator):
        """cn_financial_score should be nullified when cn_profile is missing."""
        source_data = {}
        value, is_valid = validator.validate("cn_financial_score", 90.0, source_data)
        assert is_valid is False
        assert value is None

    def test_cn_accountability_score_valid_with_cn_profile(self, validator):
        """cn_accountability_score should be valid when cn_profile exists."""
        source_data = {
            "cn_profile": {"name": "Test Charity"},
        }
        value, is_valid = validator.validate("cn_accountability_score", 92.0, source_data)
        assert is_valid is True
        assert value == 92.0

    # ========================================================================
    # Candid Seal Validation Tests
    # ========================================================================

    def test_candid_seal_valid_with_candid_profile(self, validator):
        """candid_seal should be valid when candid_profile exists with seal."""
        source_data = {
            "candid_profile": {"candid_seal": "Platinum", "name": "Test Charity"},
        }
        value, is_valid = validator.validate("candid_seal", "Platinum", source_data)
        assert is_valid is True
        assert value == "Platinum"

    def test_candid_seal_invalid_without_candid_profile(self, validator):
        """candid_seal should be nullified when candid_profile is missing."""
        source_data = {
            "candid_profile": None,
        }
        value, is_valid = validator.validate("candid_seal", "Platinum", source_data)
        assert is_valid is False
        assert value is None

    def test_candid_seal_invalid_with_empty_candid_profile(self, validator):
        """candid_seal should be nullified when candid_profile is empty."""
        source_data = {
            "candid_profile": {},
        }
        value, is_valid = validator.validate("candid_seal", "Gold", source_data)
        assert is_valid is False
        assert value is None

    def test_candid_seal_valid_with_mission_only(self, validator):
        """candid_seal should be valid when candid_profile has mission."""
        source_data = {
            "candid_profile": {"mission": "Help people in need"},
        }
        value, is_valid = validator.validate("candid_seal", "Bronze", source_data)
        assert is_valid is True
        assert value == "Bronze"

    # ========================================================================
    # GiveWell Validation Tests
    # ========================================================================

    def test_givewell_top_charity_valid_with_givewell_profile(self, validator):
        """is_givewell_top_charity should be valid when givewell_profile exists."""
        source_data = {
            "givewell_profile": {"is_top_charity": True},
        }
        value, is_valid = validator.validate("is_givewell_top_charity", True, source_data)
        assert is_valid is True
        assert value is True

    def test_givewell_top_charity_valid_with_evaluation_sources(self, validator):
        """is_givewell_top_charity should be valid when GiveWell in evaluation_sources."""
        source_data = {
            "evaluation_sources": ["GiveWell", "J-PAL"],
        }
        value, is_valid = validator.validate("is_givewell_top_charity", True, source_data)
        assert is_valid is True
        assert value is True

    def test_givewell_top_charity_invalid_without_givewell_source(self, validator):
        """is_givewell_top_charity should be nullified without GiveWell source."""
        source_data = {
            "givewell_profile": None,
            "evaluation_sources": ["Charity Navigator", "BBB"],
        }
        value, is_valid = validator.validate("is_givewell_top_charity", True, source_data)
        assert is_valid is False
        assert value is None

    def test_givewell_cost_effectiveness_invalid_without_source(self, validator):
        """givewell_cost_effectiveness_multiplier should be nullified without source."""
        source_data = {}
        value, is_valid = validator.validate(
            "givewell_cost_effectiveness_multiplier", 12.5, source_data
        )
        assert is_valid is False
        assert value is None

    def test_givewell_evidence_rating_valid_with_profile(self, validator):
        """givewell_evidence_rating should be valid with givewell_profile."""
        source_data = {
            "givewell_profile": {"evidence_rating": "A"},
        }
        value, is_valid = validator.validate("givewell_evidence_rating", "A", source_data)
        assert is_valid is True
        assert value == "A"

    # ========================================================================
    # Beneficiaries Validation Tests
    # ========================================================================

    def test_beneficiaries_valid_with_candid_data(self, validator):
        """beneficiaries_served_annually should be valid with Candid beneficiaries."""
        source_data = {
            "candid_profile": {"beneficiaries_served": 50000},
        }
        value, is_valid = validator.validate(
            "beneficiaries_served_annually", 50000, source_data
        )
        assert is_valid is True
        assert value == 50000

    def test_beneficiaries_valid_with_website_direct(self, validator):
        """beneficiaries_served_annually should be valid with website beneficiaries."""
        source_data = {
            "website_profile": {"beneficiaries_served": 25000},
        }
        value, is_valid = validator.validate(
            "beneficiaries_served_annually", 25000, source_data
        )
        assert is_valid is True
        assert value == 25000

    def test_beneficiaries_valid_with_ummah_gap_data(self, validator):
        """beneficiaries_served_annually should be valid with ummah_gap_data."""
        source_data = {
            "website_profile": {
                "ummah_gap_data": {"beneficiary_count": 100000},
            },
        }
        value, is_valid = validator.validate(
            "beneficiaries_served_annually", 100000, source_data
        )
        assert is_valid is True
        assert value == 100000

    def test_beneficiaries_valid_with_impact_metrics(self, validator):
        """beneficiaries_served_annually should be valid with impact_metrics."""
        source_data = {
            "website_profile": {
                "impact_metrics": {
                    "metrics": {"people_served_annually": 75000},
                },
            },
        }
        value, is_valid = validator.validate(
            "beneficiaries_served_annually", 75000, source_data
        )
        assert is_valid is True
        assert value == 75000

    def test_beneficiaries_invalid_without_source_data(self, validator):
        """beneficiaries_served_annually should be nullified without source."""
        source_data = {
            "website_profile": {
                "name": "Test Charity",
                "mission": "Help people",
            },
        }
        value, is_valid = validator.validate(
            "beneficiaries_served_annually", 50000, source_data
        )
        assert is_valid is False
        assert value is None

    def test_beneficiaries_invalid_with_no_website_profile(self, validator):
        """beneficiaries_served_annually should be nullified without website_profile."""
        source_data = {}
        value, is_valid = validator.validate(
            "beneficiaries_served_annually", 50000, source_data
        )
        assert is_valid is False
        assert value is None

    # ========================================================================
    # None Value Tests
    # ========================================================================

    def test_none_value_always_valid(self, validator):
        """None values should always be valid (no validation needed)."""
        source_data = {}
        value, is_valid = validator.validate("cn_overall_score", None, source_data)
        assert is_valid is True
        assert value is None

    def test_unknown_field_passes_through(self, validator):
        """Fields without rules should pass through unchanged."""
        source_data = {}
        value, is_valid = validator.validate("some_random_field", "test_value", source_data)
        assert is_valid is True
        assert value == "test_value"

    # ========================================================================
    # Bulk Validation Tests
    # ========================================================================

    def test_validate_dict_returns_all_results(self, validator):
        """validate_dict should return results for all protected fields."""
        data = {
            "cn_overall_score": 85.0,
            "candid_seal": "Platinum",
            "is_givewell_top_charity": True,
            "some_other_field": "value",
        }
        source_data = {
            "cn_profile": {"overall_score": 85.0},
        }
        result = validator.validate_dict(data, source_data)

        # Should have results for protected fields in data
        field_names = [r.field_name for r in result.results]
        assert "cn_overall_score" in field_names
        assert "candid_seal" in field_names
        assert "is_givewell_top_charity" in field_names
        # Non-protected fields should not be in results
        assert "some_other_field" not in field_names

    def test_validate_dict_nullified_fields(self, validator):
        """validate_dict should report nullified fields."""
        data = {
            "cn_overall_score": 85.0,
            "candid_seal": "Platinum",
        }
        source_data = {
            "cn_profile": {"overall_score": 85.0},
            # candid_profile missing
        }
        result = validator.validate_dict(data, source_data)

        assert "candid_seal" in result.nullified_fields
        assert "cn_overall_score" not in result.nullified_fields

    def test_apply_to_dict_modifies_data(self, validator):
        """apply_to_dict should nullify invalid fields in place."""
        data = {
            "cn_overall_score": 85.0,
            "candid_seal": "Platinum",
            "some_other_field": "preserved",
        }
        source_data = {
            "cn_profile": {"overall_score": 85.0},
            # candid_profile missing
        }
        result = validator.apply_to_dict(data, source_data)

        assert result["cn_overall_score"] == 85.0
        assert result["candid_seal"] is None
        assert result["some_other_field"] == "preserved"

    # ========================================================================
    # Custom Rule Tests
    # ========================================================================

    def test_register_custom_rule(self, validator):
        """Should be able to register custom validation rules."""
        custom_rule = ValidationRule(
            field_name="custom_field",
            description="Custom field requires custom_source",
            validator=lambda value, sources: sources.get("custom_source") is not None,
            error_message="custom_field requires custom_source",
        )
        validator.register_rule(custom_rule)

        # Test with source present
        value, is_valid = validator.validate(
            "custom_field", "test", {"custom_source": {"data": True}}
        )
        assert is_valid is True

        # Test without source
        value, is_valid = validator.validate("custom_field", "test", {})
        assert is_valid is False
        assert value is None

    def test_get_protected_fields(self, validator):
        """get_protected_fields should return all registered field names."""
        fields = validator.get_protected_fields()
        assert "cn_overall_score" in fields
        assert "candid_seal" in fields
        assert "is_givewell_top_charity" in fields
        assert "beneficiaries_served_annually" in fields


class TestValidateSourceRequiredFunction:
    """Test the convenience function."""

    def test_validate_source_required_valid(self):
        """Convenience function should work for valid case."""
        source_data = {"cn_profile": {"overall_score": 90.0}}
        value, is_valid = validate_source_required(
            "cn_overall_score", 90.0, source_data
        )
        assert is_valid is True
        assert value == 90.0

    def test_validate_source_required_invalid(self):
        """Convenience function should work for invalid case."""
        source_data = {}
        value, is_valid = validate_source_required(
            "cn_overall_score", 90.0, source_data
        )
        assert is_valid is False
        assert value is None


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validate_result_includes_error_message(self):
        """validate_result should include error message for invalid fields."""
        validator = SourceRequiredValidator()
        source_data = {}

        result = validator.validate_result("cn_overall_score", 85.0, source_data)

        assert result.is_valid is False
        assert result.original_value == 85.0
        assert result.validated_value is None
        assert "cn_profile" in result.error_message


class TestBulkValidationResult:
    """Test BulkValidationResult dataclass."""

    def test_all_valid_true_when_all_pass(self):
        """all_valid should be True when all validations pass."""
        validator = SourceRequiredValidator()
        data = {"cn_overall_score": 85.0}
        source_data = {"cn_profile": {"overall_score": 85.0}}

        result = validator.validate_dict(data, source_data)
        assert result.all_valid is True

    def test_all_valid_false_when_any_fail(self):
        """all_valid should be False when any validation fails."""
        validator = SourceRequiredValidator()
        data = {"cn_overall_score": 85.0, "candid_seal": "Platinum"}
        source_data = {"cn_profile": {"overall_score": 85.0}}

        result = validator.validate_dict(data, source_data)
        assert result.all_valid is False

    def test_get_errors_returns_mapping(self):
        """get_errors should return field -> error_message mapping."""
        validator = SourceRequiredValidator()
        data = {"cn_overall_score": 85.0, "candid_seal": "Platinum"}
        source_data = {}

        result = validator.validate_dict(data, source_data)
        errors = result.get_errors()

        assert "cn_overall_score" in errors
        assert "candid_seal" in errors
        assert "cn_profile" in errors["cn_overall_score"]
        assert "candid_profile" in errors["candid_seal"]

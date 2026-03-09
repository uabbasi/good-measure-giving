"""
Tests for numeric bounds validation.

These tests verify that out-of-bounds values from LLM extraction are caught
and set to None with appropriate logging.
"""

from src.validators.bounds_validator import (
    FIELD_BOUNDS,
    get_bounds,
    get_validation_summary,
    validate_bounds,
    validate_dict_bounds,
)


class TestValidateBounds:
    """Tests for single field validation."""

    def test_valid_program_expense_ratio(self):
        """Valid program expense ratio should pass through."""
        assert validate_bounds("program_expense_ratio", 0.85) == 0.85
        assert validate_bounds("program_expense_ratio", 0.0) == 0.0
        assert validate_bounds("program_expense_ratio", 1.0) == 1.0

    def test_invalid_program_expense_ratio(self):
        """Invalid program expense ratio should return None."""
        # 500% is nonsense
        assert validate_bounds("program_expense_ratio", 5.0, log_warning=False) is None
        # Negative is nonsense
        assert validate_bounds("program_expense_ratio", -0.1, log_warning=False) is None
        # 150% is out of bounds
        assert validate_bounds("program_expense_ratio", 1.5, log_warning=False) is None

    def test_valid_beneficiaries(self):
        """Valid beneficiary counts should pass through."""
        assert validate_bounds("beneficiaries_served_annually", 1000) == 1000
        assert validate_bounds("beneficiaries_served_annually", 1) == 1
        assert validate_bounds("beneficiaries_served_annually", 100_000_000) == 100_000_000

    def test_invalid_beneficiaries(self):
        """Invalid beneficiary counts should return None."""
        # Negative beneficiaries
        assert validate_bounds("beneficiaries_served_annually", -100, log_warning=False) is None
        # Zero beneficiaries (min is 1)
        assert validate_bounds("beneficiaries_served_annually", 0, log_warning=False) is None
        # Impossible scale (more than world population)
        assert validate_bounds("beneficiaries_served_annually", 500_000_000, log_warning=False) is None

    def test_valid_founded_year(self):
        """Valid founding years should pass through."""
        assert validate_bounds("founded_year", 1950) == 1950
        assert validate_bounds("founded_year", 2020) == 2020
        assert validate_bounds("founded_year", 1800) == 1800  # Boundary

    def test_invalid_founded_year(self):
        """Invalid founding years should return None."""
        # Too old
        assert validate_bounds("founded_year", 1700, log_warning=False) is None
        # Future year
        assert validate_bounds("founded_year", 2030, log_warning=False) is None

    def test_valid_score(self):
        """Valid scores (0-100) should pass through."""
        assert validate_bounds("cn_overall_score", 95) == 95
        assert validate_bounds("cn_overall_score", 0) == 0
        assert validate_bounds("cn_overall_score", 100) == 100

    def test_invalid_score(self):
        """Invalid scores should return None."""
        assert validate_bounds("cn_overall_score", 105, log_warning=False) is None
        assert validate_bounds("cn_overall_score", -5, log_warning=False) is None

    def test_valid_revenue(self):
        """Valid revenue amounts should pass through."""
        assert validate_bounds("total_revenue", 0) == 0  # Zero is valid
        assert validate_bounds("total_revenue", 1_000_000) == 1_000_000
        assert validate_bounds("total_revenue", 50_000_000_000) == 50_000_000_000

    def test_invalid_revenue(self):
        """Invalid revenue should return None."""
        assert validate_bounds("total_revenue", -1000, log_warning=False) is None
        assert validate_bounds("total_revenue", 100_000_000_000, log_warning=False) is None

    def test_cost_per_beneficiary(self):
        """Test cost per beneficiary bounds."""
        # Valid range: $0.01 to $100k
        assert validate_bounds("cost_per_beneficiary", 25.50) == 25.50
        assert validate_bounds("cost_per_beneficiary", 0.01) == 0.01
        assert validate_bounds("cost_per_beneficiary", 100_000) == 100_000

        # Invalid
        assert validate_bounds("cost_per_beneficiary", 0.001, log_warning=False) is None
        assert validate_bounds("cost_per_beneficiary", 200_000, log_warning=False) is None

    def test_none_value_passes_through(self):
        """None values should pass through unchanged."""
        assert validate_bounds("program_expense_ratio", None) is None
        assert validate_bounds("founded_year", None) is None

    def test_unknown_field_passes_through(self):
        """Unknown fields should pass through unchanged."""
        assert validate_bounds("unknown_field", 12345) == 12345
        assert validate_bounds("custom_metric", -100) == -100


class TestGetBounds:
    """Tests for bounds lookup."""

    def test_direct_field_lookup(self):
        """Direct field names should return bounds."""
        bounds = get_bounds("program_expense_ratio")
        assert bounds == (0.0, 1.0)

    def test_alias_lookup(self):
        """Aliased field names should resolve to canonical bounds."""
        bounds = get_bounds("num_employees")
        assert bounds == (0, 100_000)

    def test_unknown_field_returns_none(self):
        """Unknown fields should return None."""
        assert get_bounds("random_field") is None


class TestValidateDictBounds:
    """Tests for dictionary validation."""

    def test_validates_all_numeric_fields(self):
        """Should validate all numeric fields in dict."""
        data = {
            "program_expense_ratio": 0.85,
            "founded_year": 1950,
            "mission": "Help people",  # String, ignored
            "beneficiaries_served_annually": 500_000_000,  # Out of bounds
        }

        result = validate_dict_bounds(data, log_warnings=False)

        assert result["program_expense_ratio"] == 0.85
        assert result["founded_year"] == 1950
        assert result["mission"] == "Help people"
        assert result["beneficiaries_served_annually"] is None  # Nullified

    def test_validates_nested_dicts(self):
        """Should recursively validate nested dicts."""
        data = {
            "at_a_glance": {
                "founded_year": 3000,  # Out of bounds (future)
                "employees": 500,  # Valid
            },
            "financials": {
                "program_expense_ratio": 1.5,  # Out of bounds
            },
        }

        result = validate_dict_bounds(data, log_warnings=False)

        assert result["at_a_glance"]["founded_year"] is None
        assert result["at_a_glance"]["employees"] == 500
        assert result["financials"]["program_expense_ratio"] is None

    def test_preserves_non_numeric_fields(self):
        """Should preserve non-numeric fields unchanged."""
        data = {
            "name": "Test Charity",
            "programs": ["Program 1", "Program 2"],
            "is_active": True,
            "metadata": None,
        }

        result = validate_dict_bounds(data)

        assert result == data

    def test_handles_empty_dict(self):
        """Should handle empty dict."""
        assert validate_dict_bounds({}) == {}

    def test_with_ein_context(self):
        """Should include EIN in log context."""
        data = {"program_expense_ratio": 5.0}
        # This would log with EIN context
        result = validate_dict_bounds(data, ein="12-3456789", log_warnings=False)
        assert result["program_expense_ratio"] is None


class TestValidationSummary:
    """Tests for validation summary generation."""

    def test_summary_with_nullified_fields(self):
        """Should report nullified fields in summary."""
        original = {
            "program_expense_ratio": 1.5,
            "founded_year": 3000,
            "employees": 500,
        }
        validated = validate_dict_bounds(original, log_warnings=False)
        summary = get_validation_summary(original, validated)

        assert summary["values_nullified"] == 2
        assert len(summary["nullified_fields"]) == 2

        nullified_names = {f["field"] for f in summary["nullified_fields"]}
        assert "program_expense_ratio" in nullified_names
        assert "founded_year" in nullified_names

    def test_summary_with_no_issues(self):
        """Should report no issues when all values valid."""
        original = {
            "program_expense_ratio": 0.85,
            "founded_year": 1950,
        }
        validated = validate_dict_bounds(original, log_warnings=False)
        summary = get_validation_summary(original, validated)

        assert summary["values_nullified"] == 0
        assert summary["nullified_fields"] == []

    def test_summary_includes_bounds(self):
        """Summary should include bounds for nullified fields."""
        original = {"program_expense_ratio": 5.0}
        validated = validate_dict_bounds(original, log_warnings=False)
        summary = get_validation_summary(original, validated)

        nullified = summary["nullified_fields"][0]
        assert nullified["original_value"] == 5.0
        assert nullified["bounds"] == (0.0, 1.0)


class TestFieldBoundsConfiguration:
    """Tests for the bounds configuration itself."""

    def test_all_ratio_fields_have_0_1_bounds(self):
        """All ratio fields should be bounded 0-1."""
        ratio_fields = [k for k in FIELD_BOUNDS if "ratio" in k or "pct" in k]
        for field in ratio_fields:
            bounds = FIELD_BOUNDS[field]
            assert bounds == (0.0, 1.0), f"{field} should have (0.0, 1.0) bounds"

    def test_all_score_fields_have_0_100_bounds(self):
        """All score fields should be bounded 0-100."""
        score_fields = [k for k in FIELD_BOUNDS if "score" in k]
        for field in score_fields:
            bounds = FIELD_BOUNDS[field]
            assert bounds == (0, 100), f"{field} should have (0, 100) bounds"

    def test_year_fields_have_reasonable_bounds(self):
        """Calendar year fields should have reasonable historical bounds."""
        # Only calendar year fields, not duration fields like "outcome_tracking_years"
        calendar_year_fields = [
            "founded_year", "year_founded", "irs_ruling_year",
            "tax_year", "fiscal_year", "last_verified_year", "source_year"
        ]
        for field in calendar_year_fields:
            if field in FIELD_BOUNDS:
                min_val, max_val = FIELD_BOUNDS[field]
                assert min_val >= 1800, f"{field} min should be >= 1800"
                assert max_val <= 2030, f"{field} max should be <= 2030"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_float_vs_int_bounds(self):
        """Should handle both float and int bounds correctly."""
        # Float field
        assert validate_bounds("program_expense_ratio", 0.85) == 0.85
        # Int field
        assert validate_bounds("employees_count", 100) == 100

    def test_boundary_values(self):
        """Should accept values exactly at boundaries."""
        # Minimum boundary
        assert validate_bounds("cost_per_beneficiary", 0.01) == 0.01
        # Maximum boundary
        assert validate_bounds("cost_per_beneficiary", 100_000) == 100_000

    def test_slightly_out_of_bounds(self):
        """Should reject values just outside boundaries."""
        assert validate_bounds("cost_per_beneficiary", 0.009, log_warning=False) is None
        assert validate_bounds("cost_per_beneficiary", 100_001, log_warning=False) is None

    def test_boolean_not_validated(self):
        """Booleans should not be validated as numeric."""
        data = {"is_active": True, "has_audit": False}
        result = validate_dict_bounds(data)
        assert result["is_active"] is True
        assert result["has_audit"] is False

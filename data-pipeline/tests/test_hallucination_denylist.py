"""
Tests for Hallucination-Prone Field Denylist.

Tests the documentation, detection, and flagging of fields that are
known to be unreliable when extracted by LLMs.
"""


from src.validators.hallucination_denylist import (
    HALLUCINATION_PRONE_FIELDS,
    VERIFICATION_REQUIRED_FIELDS,
    flag_unverified_fields,
    get_all_hallucination_prone_fields,
    get_hallucination_reason,
    get_verification_method,
    get_verification_report,
    is_hallucination_prone,
    unflag_verified_field,
)


class TestHallucinationProneFieldsRegistry:
    """Test the hallucination-prone fields registry."""

    def test_all_prone_fields_have_verification_methods(self):
        """Every hallucination-prone field should have a verification method."""
        for field_name in HALLUCINATION_PRONE_FIELDS:
            assert field_name in VERIFICATION_REQUIRED_FIELDS, (
                f"Field '{field_name}' is hallucination-prone but has no verification method"
            )

    def test_known_prone_fields_are_documented(self):
        """Verify the expected hallucination-prone fields are in the registry."""
        expected_fields = {
            "accepts_zakat",
            "populations_served",
            "external_evaluations",
            "scholarly_endorsements",
            "third_party_evaluated",
        }
        for field in expected_fields:
            assert field in HALLUCINATION_PRONE_FIELDS, (
                f"Expected '{field}' to be in HALLUCINATION_PRONE_FIELDS"
            )

    def test_reasons_are_non_empty_strings(self):
        """All reasons should be non-empty descriptive strings."""
        for field_name, reason in HALLUCINATION_PRONE_FIELDS.items():
            assert isinstance(reason, str), f"Reason for '{field_name}' should be a string"
            assert len(reason) > 20, f"Reason for '{field_name}' should be descriptive"

    def test_verification_methods_are_actionable(self):
        """Verification methods should provide actionable guidance."""
        for field_name, method in VERIFICATION_REQUIRED_FIELDS.items():
            assert isinstance(method, str), f"Method for '{field_name}' should be a string"
            assert len(method) > 20, f"Method for '{field_name}' should be actionable"


class TestIsHallucinationProne:
    """Test the is_hallucination_prone function."""

    def test_accepts_zakat_is_prone(self):
        """accepts_zakat should be flagged as hallucination-prone."""
        assert is_hallucination_prone("accepts_zakat") is True

    def test_populations_served_is_prone(self):
        """populations_served should be flagged as hallucination-prone."""
        assert is_hallucination_prone("populations_served") is True

    def test_external_evaluations_is_prone(self):
        """external_evaluations should be flagged as hallucination-prone."""
        assert is_hallucination_prone("external_evaluations") is True

    def test_scholarly_endorsements_is_prone(self):
        """scholarly_endorsements should be flagged as hallucination-prone."""
        assert is_hallucination_prone("scholarly_endorsements") is True

    def test_third_party_evaluated_is_prone(self):
        """third_party_evaluated should be flagged as hallucination-prone."""
        assert is_hallucination_prone("third_party_evaluated") is True

    def test_name_is_not_prone(self):
        """Standard fields like 'name' should not be prone."""
        assert is_hallucination_prone("name") is False

    def test_ein_is_not_prone(self):
        """Standard fields like 'ein' should not be prone."""
        assert is_hallucination_prone("ein") is False

    def test_mission_is_not_prone(self):
        """Standard fields like 'mission' should not be prone."""
        assert is_hallucination_prone("mission") is False


class TestGetHallucinationReason:
    """Test the get_hallucination_reason function."""

    def test_returns_reason_for_prone_field(self):
        """Should return reason string for hallucination-prone fields."""
        reason = get_hallucination_reason("accepts_zakat")
        assert reason is not None
        assert "donate" in reason.lower() or "zakat" in reason.lower()

    def test_returns_none_for_non_prone_field(self):
        """Should return None for fields not in the registry."""
        assert get_hallucination_reason("name") is None
        assert get_hallucination_reason("ein") is None


class TestGetVerificationMethod:
    """Test the get_verification_method function."""

    def test_returns_method_for_accepts_zakat(self):
        """Should return verification method for accepts_zakat."""
        method = get_verification_method("accepts_zakat")
        assert method is not None
        assert "zakat" in method.lower()

    def test_returns_method_for_populations_served(self):
        """Should return verification method for populations_served."""
        method = get_verification_method("populations_served")
        assert method is not None
        assert "specific" in method.lower() or "population" in method.lower()

    def test_returns_method_for_external_evaluations(self):
        """Should return verification method for external_evaluations."""
        method = get_verification_method("external_evaluations")
        assert method is not None
        # Should mention actual evaluator sources
        assert any(
            source in method.lower()
            for source in ["givewell", "charity navigator", "candid"]
        )

    def test_returns_none_for_unknown_field(self):
        """Should return None for fields without verification methods."""
        assert get_verification_method("name") is None
        assert get_verification_method("unknown_field") is None


class TestGetAllHallucinationProneFields:
    """Test the get_all_hallucination_prone_fields function."""

    def test_returns_list_of_field_names(self):
        """Should return a list of all hallucination-prone field names."""
        fields = get_all_hallucination_prone_fields()
        assert isinstance(fields, list)
        assert len(fields) > 0

    def test_includes_expected_fields(self):
        """Should include all known hallucination-prone fields."""
        fields = get_all_hallucination_prone_fields()
        assert "accepts_zakat" in fields
        assert "populations_served" in fields
        assert "external_evaluations" in fields


class TestFlagUnverifiedFields:
    """Test the flag_unverified_fields function."""

    def test_flags_single_prone_field(self):
        """Should add _unverified suffix to a single prone field."""
        data = {"accepts_zakat": True}
        result = flag_unverified_fields(data)
        assert "accepts_zakat_unverified" in result
        assert "accepts_zakat" not in result
        assert result["accepts_zakat_unverified"] is True

    def test_flags_multiple_prone_fields(self):
        """Should flag all prone fields in the data."""
        data = {
            "accepts_zakat": True,
            "populations_served": ["children", "elderly"],
            "scholarly_endorsements": ["Sheikh Ahmad"],
        }
        result = flag_unverified_fields(data)
        assert "accepts_zakat_unverified" in result
        assert "populations_served_unverified" in result
        assert "scholarly_endorsements_unverified" in result
        assert "accepts_zakat" not in result

    def test_preserves_non_prone_fields(self):
        """Should not modify fields that aren't hallucination-prone."""
        data = {
            "name": "Test Charity",
            "ein": "12-3456789",
            "accepts_zakat": True,
        }
        result = flag_unverified_fields(data)
        assert result["name"] == "Test Charity"
        assert result["ein"] == "12-3456789"
        assert "accepts_zakat_unverified" in result

    def test_skips_none_values(self):
        """Should not flag None values (no point flagging missing data)."""
        data = {
            "accepts_zakat": None,
            "name": "Test",
        }
        result = flag_unverified_fields(data)
        assert "accepts_zakat" in result
        assert result["accepts_zakat"] is None
        assert "accepts_zakat_unverified" not in result

    def test_respects_verified_fields_set(self):
        """Should not flag fields that have been verified."""
        data = {
            "accepts_zakat": True,
            "populations_served": ["refugees"],
        }
        verified = {"accepts_zakat"}
        result = flag_unverified_fields(data, verified_fields=verified)

        # accepts_zakat was verified, should not be flagged
        assert "accepts_zakat" in result
        assert "accepts_zakat_unverified" not in result

        # populations_served was not verified, should be flagged
        assert "populations_served_unverified" in result
        assert "populations_served" not in result

    def test_empty_data_returns_empty(self):
        """Should handle empty data gracefully."""
        result = flag_unverified_fields({})
        assert result == {}

    def test_no_prone_fields_returns_unchanged(self):
        """Should return unchanged data if no prone fields present."""
        data = {"name": "Test", "ein": "12-3456789", "mission": "Help people"}
        result = flag_unverified_fields(data)
        assert result == data


class TestUnflagVerifiedField:
    """Test the unflag_verified_field function."""

    def test_removes_unverified_suffix(self):
        """Should remove _unverified suffix after verification."""
        data = {"accepts_zakat_unverified": True, "name": "Test"}
        result = unflag_verified_field(data, "accepts_zakat")
        assert "accepts_zakat" in result
        assert "accepts_zakat_unverified" not in result
        assert result["accepts_zakat"] is True

    def test_preserves_other_fields(self):
        """Should not modify other fields when unverifying."""
        data = {
            "accepts_zakat_unverified": True,
            "populations_served_unverified": ["refugees"],
            "name": "Test",
        }
        result = unflag_verified_field(data, "accepts_zakat")
        assert result["populations_served_unverified"] == ["refugees"]
        assert result["name"] == "Test"

    def test_handles_missing_unverified_field(self):
        """Should return copy of data if unverified field doesn't exist."""
        data = {"name": "Test", "accepts_zakat": True}
        result = unflag_verified_field(data, "accepts_zakat")
        assert result == data
        # Should be a copy, not the same object
        assert result is not data


class TestGetVerificationReport:
    """Test the get_verification_report function."""

    def test_reports_verified_field(self):
        """Should report verified (unflagged) prone fields."""
        data = {"accepts_zakat": True, "name": "Test"}
        report = get_verification_report(data)

        assert "accepts_zakat" in report
        assert report["accepts_zakat"]["value"] is True
        assert report["accepts_zakat"]["status"] == "verified"
        assert report["accepts_zakat"]["reason"] is not None
        assert report["accepts_zakat"]["verification_method"] is not None

    def test_reports_unverified_field(self):
        """Should report unverified (flagged) prone fields."""
        data = {"accepts_zakat_unverified": True, "name": "Test"}
        report = get_verification_report(data)

        assert "accepts_zakat" in report
        assert report["accepts_zakat"]["value"] is True
        assert report["accepts_zakat"]["status"] == "unverified"

    def test_ignores_non_prone_fields(self):
        """Should not include non-prone fields in report."""
        data = {"name": "Test", "ein": "12-3456789", "mission": "Help"}
        report = get_verification_report(data)
        assert "name" not in report
        assert "ein" not in report

    def test_reports_multiple_fields(self):
        """Should report all prone fields present in data."""
        data = {
            "accepts_zakat": True,
            "populations_served_unverified": ["children"],
            "scholarly_endorsements_unverified": ["Sheikh Ahmad"],
            "name": "Test",
        }
        report = get_verification_report(data)

        assert "accepts_zakat" in report
        assert report["accepts_zakat"]["status"] == "verified"

        assert "populations_served" in report
        assert report["populations_served"]["status"] == "unverified"

        assert "scholarly_endorsements" in report
        assert report["scholarly_endorsements"]["status"] == "unverified"

    def test_empty_data_returns_empty_report(self):
        """Should return empty report for data without prone fields."""
        report = get_verification_report({"name": "Test"})
        assert report == {}


class TestIntegrationScenarios:
    """Integration tests for realistic usage scenarios."""

    def test_full_flagging_workflow(self):
        """Test the complete workflow: flag -> verify -> unflag."""
        # Initial extraction from LLM
        extracted_data = {
            "name": "Islamic Relief",
            "ein": "95-4453134",
            "accepts_zakat": True,
            "populations_served": ["refugees", "orphans"],
            "mission": "Humanitarian aid",
        }

        # Step 1: Flag unverified prone fields
        flagged_data = flag_unverified_fields(extracted_data)

        assert "accepts_zakat_unverified" in flagged_data
        assert "populations_served_unverified" in flagged_data
        assert flagged_data["name"] == "Islamic Relief"

        # Step 2: Generate verification report
        report = get_verification_report(flagged_data)

        assert report["accepts_zakat"]["status"] == "unverified"
        assert report["populations_served"]["status"] == "unverified"

        # Step 3: After corroboration, unflag verified field
        verified_data = unflag_verified_field(flagged_data, "accepts_zakat")

        assert "accepts_zakat" in verified_data
        assert "accepts_zakat_unverified" not in verified_data
        assert "populations_served_unverified" in verified_data

        # Step 4: Check final report
        final_report = get_verification_report(verified_data)

        assert final_report["accepts_zakat"]["status"] == "verified"
        assert final_report["populations_served"]["status"] == "unverified"

    def test_pre_verified_extraction(self):
        """Test flagging when some fields are already verified."""
        # Extraction with known corroboration
        extracted_data = {
            "accepts_zakat": True,  # Verified via zakat calculator on website
            "third_party_evaluated": True,  # Will be verified via API
            "scholarly_endorsements": ["Unknown Scholar"],  # Cannot verify
        }

        # Only flag fields that weren't corroborated
        verified_fields = {"accepts_zakat", "third_party_evaluated"}
        flagged_data = flag_unverified_fields(extracted_data, verified_fields)

        # Verified fields should not be flagged
        assert "accepts_zakat" in flagged_data
        assert "third_party_evaluated" in flagged_data

        # Unverified field should be flagged
        assert "scholarly_endorsements_unverified" in flagged_data
        assert "scholarly_endorsements" not in flagged_data

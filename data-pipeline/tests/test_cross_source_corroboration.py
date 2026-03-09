"""
Tests for Cross-Source Corroboration logic.

These tests verify that high-stakes fields (zakat_claim_detected, has_financial_audit,
third_party_evaluated) are only set when corroborated by 2+ independent sources.
"""

import pytest

from src.parsers.charity_metrics_aggregator import (
    CharityMetricsAggregator,
    CrossSourceCorroborator,
    CorroborationResult,
)


class TestCorroborationResult:
    """Test CorroborationResult dataclass."""

    def test_creation(self):
        result = CorroborationResult(
            passed=True,
            value=True,
            sources=["source1", "source2"],
            reason="Test reason",
        )
        assert result.passed is True
        assert result.value is True
        assert result.sources == ["source1", "source2"]
        assert result.reason == "Test reason"

    def test_default_values(self):
        result = CorroborationResult(passed=False, value=None)
        assert result.sources == []
        assert result.reason == ""


class TestCorroborateZakatClaim:
    """Test zakat claim corroboration logic."""

    def test_passes_with_multiple_sources(self):
        """Zakat claim should pass with 2+ independent sources."""
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="12-3456789",
            name="Test Charity",
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://example.org/zakat",
                    "zakat_verification_confidence": 0.8,
                }
            },
            website_profile={
                "donation_methods": ["Credit Card", "Zakat", "Sadaqah"],
            },
        )
        assert result.passed is True
        assert len(result.sources) >= 2
        assert "discovered_profile" in result.sources
        assert "url_pattern" in result.sources or "website_donation_methods" in result.sources

    def test_fails_with_single_source(self):
        """Zakat claim should fail with only 1 source."""
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="12-3456789",
            name="Test Charity",
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://example.org/donate",  # No 'zakat' in URL
                    "zakat_verification_confidence": 0.8,
                }
            },
            website_profile=None,
        )
        assert result.passed is False
        assert len(result.sources) == 1

    def test_passes_with_definitive_name(self):
        """Zakat claim should pass with definitive zakat name even without other sources."""
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="12-3456789",
            name="Zakat Foundation of America",
            discovered_profile=None,
            website_profile=None,
        )
        assert result.passed is True
        assert "organization_name" in result.sources

    def test_passes_with_baitulmaal_name(self):
        """Baitulmaal name implies zakat acceptance."""
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="12-3456789",
            name="Baitulmaal Inc.",
            discovered_profile=None,
            website_profile=None,
        )
        assert result.passed is True
        assert "organization_name" in result.sources

    def test_fails_with_low_confidence(self):
        """Zakat claim should fail if discovery confidence is below threshold."""
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="12-3456789",
            name="Test Charity",
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://example.org/donate",
                    "zakat_verification_confidence": 0.3,  # Below 0.5 threshold
                }
            },
            website_profile=None,
        )
        assert result.passed is False

    def test_website_content_provides_corroboration(self):
        """Zakat mentioned in mission/programs provides corroboration."""
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="12-3456789",
            name="Test Charity",
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://example.org/donate",
                    "zakat_verification_confidence": 0.8,
                }
            },
            website_profile={
                "mission": "We collect zakat to help the poor",
                "programs": ["Relief Program"],
            },
        )
        assert result.passed is True
        assert "website_content" in result.sources

    def test_direct_page_verified_provides_corroboration(self):
        """Direct HTTP page check (not LLM) provides corroboration.

        When ZakatVerificationService verifies zakat via direct HTTP request
        to /zakat or /donate pages (independent from LLM search), this should
        count as a second source for corroboration.
        """
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="33-0843213",
            name="DEVELOPMENTS IN LITERACY INC",
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://www.dil.org/donate",  # No 'zakat' in URL
                    "zakat_verification_confidence": 0.95,
                    "direct_page_verified": True,  # Verified via direct HTTP check
                }
            },
            website_profile=None,  # Website extraction didn't capture zakat
        )
        assert result.passed is True
        assert "discovered_profile" in result.sources
        assert "zakat_page_direct" in result.sources
        assert len(result.sources) >= 2

    def test_llm_only_without_direct_page_still_fails(self):
        """LLM search without direct page verification still needs 2 sources.

        When zakat is only detected via LLM search (not direct page check),
        corroboration should still require a second independent source.
        """
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="12-3456789",
            name="Test Charity",
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://example.org/donate",
                    "zakat_verification_confidence": 0.95,
                    "direct_page_verified": False,  # LLM only, no direct check
                }
            },
            website_profile=None,
        )
        assert result.passed is False
        assert "discovered_profile" in result.sources
        assert "zakat_page_direct" not in result.sources

    def test_explicit_discovered_zakat_language_passes(self):
        """Explicit zakat-eligible language from discovery should corroborate.

        This covers cases where website extraction misses the giving page but
        discovery captures direct first-party phrasing (e.g., "We are zakat eligible").
        """
        result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein="77-0411194",
            name="COUNCIL ON AMERICAN-ISLAMIC RELATIONS CALIFORNIA",
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc123",
                    "accepts_zakat_evidence": (
                        "We Are Zakat Eligible. Your Zakat contributions directly support our mission."
                    ),
                    "zakat_verification_confidence": 0.5,
                    "direct_page_verified": False,
                }
            },
            website_profile=None,
        )
        assert result.passed is True
        assert "discovered_profile" in result.sources
        assert "discovered_explicit_zakat_text" in result.sources


class TestCorroborateFinancialAudit:
    """Test financial audit corroboration logic."""

    def test_passes_with_cn_and_candid(self):
        """Audit should pass with CN + Candid Gold seal."""
        result = CrossSourceCorroborator.corroborate_financial_audit(
            ein="12-3456789",
            name="Test Charity",
            cn_profile={"has_financial_audit": True},
            candid_profile={"candid_seal": "Gold"},
            website_profile=None,
            propublica_990=None,
        )
        assert result.passed is True
        assert "charity_navigator" in result.sources
        assert "candid_seal" in result.sources

    def test_passes_with_cn_accountability_score(self):
        """High CN accountability score implies audit."""
        result = CrossSourceCorroborator.corroborate_financial_audit(
            ein="12-3456789",
            name="Test Charity",
            cn_profile={"accountability_score": 90},
            candid_profile={"candid_seal": "Platinum"},
            website_profile=None,
            propublica_990=None,
        )
        assert result.passed is True
        assert "cn_accountability_score" in result.sources

    def test_fails_with_revenue_only(self):
        """Revenue alone is not enough to confirm audit."""
        result = CrossSourceCorroborator.corroborate_financial_audit(
            ein="12-3456789",
            name="Test Charity",
            cn_profile=None,
            candid_profile=None,
            website_profile=None,
            propublica_990={"total_revenue": 5000000},
        )
        # Revenue alone is not enough
        assert result.passed is False or len(result.sources) >= 2

    def test_fails_with_website_claim_only(self):
        """Website audit claim alone fails corroboration."""
        result = CrossSourceCorroborator.corroborate_financial_audit(
            ein="12-3456789",
            name="Test Charity",
            cn_profile=None,
            candid_profile=None,
            website_profile={
                "absorptive_capacity_data": {"has_independent_audit": True}
            },
            propublica_990=None,
        )
        assert result.passed is False

    def test_pdf_audit_document_counts_as_source(self):
        """PDF audit document provides corroboration."""
        result = CrossSourceCorroborator.corroborate_financial_audit(
            ein="12-3456789",
            name="Test Charity",
            cn_profile={"has_financial_audit": True},
            candid_profile=None,
            website_profile={
                "llm_extracted_pdfs": [
                    {"type": "audit", "file": "2023-audit-report.pdf"}
                ]
            },
            propublica_990=None,
        )
        assert result.passed is True
        assert "pdf_audit_document" in result.sources


class TestCorroborateThirdPartyEvaluation:
    """Test third-party evaluation corroboration logic."""

    def test_passes_with_cn_score(self):
        """Having a CN score IS third-party evaluation."""
        result = CrossSourceCorroborator.corroborate_third_party_evaluation(
            ein="12-3456789",
            name="Test Charity",
            cn_profile={"overall_score": 85},
            candid_profile=None,
            website_profile=None,
            givewell_profile=None,
        )
        assert result.passed is True
        assert "charity_navigator_rated" in result.sources

    def test_passes_with_givewell(self):
        """GiveWell top charity IS third-party evaluation."""
        result = CrossSourceCorroborator.corroborate_third_party_evaluation(
            ein="12-3456789",
            name="Test Charity",
            cn_profile=None,
            candid_profile=None,
            website_profile=None,
            givewell_profile={"is_top_charity": True},
        )
        assert result.passed is True
        assert "givewell_top_charity" in result.sources

    def test_passes_with_candid_profile(self):
        """Candid profile with seal IS third-party evaluation."""
        result = CrossSourceCorroborator.corroborate_third_party_evaluation(
            ein="12-3456789",
            name="Test Charity",
            cn_profile=None,
            candid_profile={"candid_seal": "Gold"},
            website_profile=None,
            givewell_profile=None,
        )
        assert result.passed is True
        assert "candid_profile" in result.sources

    def test_fails_with_website_claim_only(self):
        """Website claiming evaluation without actual third-party data fails."""
        result = CrossSourceCorroborator.corroborate_third_party_evaluation(
            ein="12-3456789",
            name="Test Charity",
            cn_profile=None,
            candid_profile=None,
            website_profile={
                "evidence_of_impact_data": {
                    "third_party_evaluations": ["Harvard Study", "J-PAL"],
                    "has_rcts": True,
                }
            },
            givewell_profile=None,
        )
        assert result.passed is False
        assert "website_claims" in result.sources


class TestAggregatorCorroboration:
    """Test corroboration integration in CharityMetricsAggregator."""

    def test_corroboration_status_populated(self):
        """Corroboration status should be populated for all high-stakes fields."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            cn_profile={"name": "Test", "overall_score": 85},
            candid_profile={"name": "Test", "candid_seal": "Gold"},
            website_profile={"url": "https://test.org"},
            discovered_profile=None,
        )

        assert "zakat_claim_detected" in metrics.corroboration_status
        assert "has_financial_audit" in metrics.corroboration_status
        assert "third_party_evaluated" in metrics.corroboration_status

        for field, status in metrics.corroboration_status.items():
            assert "passed" in status
            assert "sources" in status
            assert "reason" in status

    def test_zakat_nullified_on_failed_corroboration(self):
        """Zakat claim should be None when corroboration fails."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            cn_profile=None,
            candid_profile=None,
            website_profile={"url": "https://test.org"},
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://test.org/donate",  # No 'zakat' in URL
                    "zakat_verification_confidence": 0.7,
                }
            },
        )

        assert metrics.zakat_claim_detected is None
        assert "CORROBORATION FAILED" in (metrics.zakat_claim_evidence or "")
        assert metrics.corroboration_status["zakat_claim_detected"]["passed"] is False

    def test_audit_unverified_on_failed_corroboration(self):
        """Audit status should be kept but marked unverified when corroboration fails."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            cn_profile=None,
            candid_profile=None,
            website_profile=None,
            propublica_990={"total_revenue": 3000000},  # Only revenue signal
            discovered_profile=None,
        )

        # FIX #9: Revenue alone should not pass corroboration, but value is kept
        assert metrics.has_financial_audit is True  # Value retained
        assert metrics.corroboration_status["has_financial_audit"]["passed"] is False
        # Source attribution should be marked unverified
        audit_attr = metrics.source_attribution.get("has_financial_audit", {})
        assert audit_attr.get("verification_status") == "unverified"

    def test_third_party_false_on_failed_corroboration(self):
        """Third-party evaluation should be False when corroboration fails."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            cn_profile=None,
            candid_profile=None,
            website_profile={
                "url": "https://test.org",
                "evidence_of_impact_data": {
                    "third_party_evaluations": ["Claimed Study"],
                }
            },
            discovered_profile=None,
        )

        assert metrics.third_party_evaluated is False
        assert metrics.corroboration_status["third_party_evaluated"]["passed"] is False
        # Evaluation sources should be marked as uncorroborated
        assert all("UNCORROBORATED" in s for s in metrics.evaluation_sources)

    def test_all_fields_pass_with_proper_data(self):
        """All fields should pass corroboration with proper multi-source data."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            cn_profile={
                "name": "Islamic Relief",
                "overall_score": 90,
                "accountability_score": 92,
            },
            candid_profile={
                "name": "Islamic Relief",
                "candid_seal": "Platinum",
            },
            website_profile={
                "url": "https://test.org",
                "donation_methods": ["Zakat", "Credit Card"],
                # Include evidence_of_impact_data to trigger third_party_evaluated
                "evidence_of_impact_data": {
                    "third_party_evaluations": ["Charity Navigator"],
                }
            },
            discovered_profile={
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_url": "https://test.org/zakat",
                    "zakat_verification_confidence": 0.9,
                }
            },
        )

        assert metrics.zakat_claim_detected is True
        assert metrics.has_financial_audit is True
        assert metrics.third_party_evaluated is True

        for field, status in metrics.corroboration_status.items():
            assert status["passed"] is True, f"{field} failed corroboration"
            assert len(status["sources"]) >= 1, f"{field} has no sources"

    def test_third_party_without_website_claim(self):
        """
        Corroboration verifies claims, doesn't create them.

        If third_party_evaluated was never claimed (no website evidence_of_impact_data),
        but actual third-party sources exist (CN, Candid), corroboration passes but
        the field remains unset because no claim was made to verify.

        This is correct behavior - corroboration is about verifying claims, not inferring
        new values from presence of third-party data.
        """
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            cn_profile={
                "name": "Test",
                "overall_score": 90,
            },
            candid_profile={
                "name": "Test",
                "candid_seal": "Gold",
            },
            website_profile={
                "url": "https://test.org",
                # No evidence_of_impact_data - no claim to verify
            },
            discovered_profile=None,
        )

        # Corroboration passes (third-party sources exist)
        assert metrics.corroboration_status["third_party_evaluated"]["passed"] is True
        # But the field is None because no claim was made to verify
        # (this is correct - corroboration verifies, doesn't infer)
        assert metrics.third_party_evaluated is None

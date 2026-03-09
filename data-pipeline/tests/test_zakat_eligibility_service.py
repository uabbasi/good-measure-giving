"""
Tests for ZakatEligibilityService - checking if charities claim to accept zakat.

Simple logic:
1. Name contains "zakat" or "baitulmaal" → claims zakat
2. Discover service found charity claims zakat (with min confidence) → claims zakat
3. Otherwise → sadaqah only

Being a Muslim charity is NOT sufficient - they must explicitly claim zakat.
"""

import pytest

from src.services.zakat_eligibility_service import (
    ZakatEligibilityResult,
    ZakatEligibilityService,
    determine_zakat_eligibility,
)


@pytest.fixture
def service():
    """Create a ZakatEligibilityService instance."""
    return ZakatEligibilityService()


class TestDefinitiveNames:
    """Test name-based zakat detection."""

    @pytest.mark.parametrize("name", [
        "Baitulmaal Inc",
        "National Zakat Foundation",
        "Local Zakat Fund",
        "ZAKAAT USA",
    ])
    def test_definitive_names_claim_zakat(self, service, name):
        """Orgs with zakat in the name are claiming zakat."""
        result = service.check_zakat_claim(
            name=name,
            discovered_zakat=None,  # No discover data needed
        )
        assert result.claims_zakat is True
        assert result.confidence == 1.0

    def test_definitive_name_case_insensitive(self, service):
        """Name matching should be case insensitive."""
        result = service.check_zakat_claim(
            name="BAITULMAAL FOUNDATION",
            discovered_zakat=None,
        )
        assert result.claims_zakat is True


class TestDiscoverServiceClaims:
    """Test when discover service finds zakat claims."""

    def test_charity_claims_zakat_accepted(self, service):
        """If discover finds charity claims zakat, accept it."""
        result = service.check_zakat_claim(
            name="Some Charity",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Give your zakat to help...",
                "zakat_verification_confidence": 0.8,
                "accepts_zakat_url": "https://example.org/zakat",
            },
        )
        assert result.claims_zakat is True
        assert "https://example.org/zakat" in result.evidence

    def test_low_confidence_rejected(self, service):
        """Low confidence results should be rejected (likely hallucination)."""
        result = service.check_zakat_claim(
            name="Random Charity",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Maybe accepts zakat",
                "zakat_verification_confidence": 0.3,  # Below 0.5 threshold
            },
        )
        assert result.claims_zakat is False

    def test_discover_says_no_zakat(self, service):
        """When discover explicitly says no zakat, return false."""
        result = service.check_zakat_claim(
            name="Islamic Relief USA",  # Even Islamic org
            discovered_zakat={
                "accepts_zakat": False,
                "accepts_zakat_evidence": "Does not explicitly claim zakat",
                "zakat_verification_confidence": 0.9,
            },
        )
        assert result.claims_zakat is False


class TestIslamicCharitiesNeedExplicitClaim:
    """Being a Muslim charity is NOT sufficient - must claim zakat."""

    def test_islamic_charity_without_zakat_claim(self, service):
        """Islamic charity without zakat claim → sadaqah only."""
        result = service.check_zakat_claim(
            name="Islamic Relief USA",
            discovered_zakat={
                "accepts_zakat": False,  # Doesn't claim zakat
                "zakat_verification_confidence": 0.9,
            },
        )
        assert result.claims_zakat is False

    def test_mosque_without_zakat_claim(self, service):
        """Mosque without zakat claim → sadaqah only."""
        result = service.check_zakat_claim(
            name="Local Masjid Foundation",
            discovered_zakat=None,  # No zakat claim found
        )
        assert result.claims_zakat is False

    def test_islamic_charity_with_zakat_claim(self, service):
        """Islamic charity WITH zakat claim → zakat eligible."""
        result = service.check_zakat_claim(
            name="Islamic Relief USA",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Your zakat saves lives",
                "zakat_verification_confidence": 0.85,
                "accepts_zakat_url": "https://irusa.org/zakat",
            },
        )
        assert result.claims_zakat is True


class TestNoDiscoverData:
    """Test handling when no discover data is available."""

    def test_no_discover_data_no_definitive_name(self, service):
        """Without discover data and no definitive name → sadaqah only."""
        result = service.check_zakat_claim(
            name="Some Charity",
            discovered_zakat=None,
        )
        assert result.claims_zakat is False

    def test_no_discover_data_definitive_name_still_works(self, service):
        """Definitive names work without discover data."""
        result = service.check_zakat_claim(
            name="Zakat Foundation USA",
            discovered_zakat=None,
        )
        assert result.claims_zakat is True


class TestConvenienceFunction:
    """Test the convenience function."""

    def test_returns_tuple(self):
        """Convenience function should return (bool, str) tuple."""
        claims, evidence = determine_zakat_eligibility(
            name="Zakat Foundation",
            mission=None,  # Not used
            discovered_zakat=None,
        )
        assert isinstance(claims, bool)
        assert claims is True
        assert evidence is not None

    def test_rejection_returns_none_evidence(self):
        """Rejection should return (False, None)."""
        claims, evidence = determine_zakat_eligibility(
            name="Random Charity",
            mission="Doing good",
            discovered_zakat=None,
        )
        assert claims is False


class TestEvidenceBuilding:
    """Test that evidence strings are built correctly."""

    def test_evidence_includes_source_url(self, service):
        """Evidence should include source URL when present."""
        result = service.check_zakat_claim(
            name="Some Charity",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Give your zakat",
                "zakat_verification_confidence": 0.8,
                "accepts_zakat_url": "https://example.org/zakat",
            },
        )
        assert result.claims_zakat is True
        assert "https://example.org/zakat" in result.evidence

    def test_evidence_from_definitive_name(self, service):
        """Definitive name evidence should mention the matched term."""
        result = service.check_zakat_claim(
            name="Baitulmaal Foundation",
            discovered_zakat=None,
        )
        assert "baitulmaal" in result.evidence.lower()


class TestZakatDenylist:
    """Test denylist for false positives (orgs that partner but don't collect)."""

    def test_denylisted_charity_rejected_despite_high_confidence(self, service):
        """Denylisted charity is rejected even with high confidence zakat claim."""
        result = service.check_zakat_claim(
            name="UNICEF USA",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Partners with Zakat Foundation",
                "zakat_verification_confidence": 0.9,
                "accepts_zakat_url": "https://unicefusa.org",
            },
            ein="13-1760110",  # UNICEF USA - in denylist
        )
        assert result.claims_zakat is False
        assert "denylist" in result.evidence.lower()
        assert result.confidence == 0.0

    def test_non_denylisted_charity_processed_normally(self, service):
        """Charity not in denylist is processed normally."""
        result = service.check_zakat_claim(
            name="Islamic Relief USA",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Your zakat saves lives",
                "zakat_verification_confidence": 0.85,
                "accepts_zakat_url": "https://irusa.org/zakat",
            },
            ein="95-4453134",  # Not in denylist
        )
        assert result.claims_zakat is True

    def test_denylist_without_ein_no_effect(self, service):
        """Without EIN, denylist check is skipped."""
        result = service.check_zakat_claim(
            name="UNICEF USA",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Partners with Zakat Foundation",
                "zakat_verification_confidence": 0.9,
            },
            ein=None,  # No EIN provided
        )
        # Would be accepted without EIN check
        assert result.claims_zakat is True

    def test_convenience_function_with_ein_denylist(self):
        """Convenience function passes EIN for denylist check."""
        claims, evidence = determine_zakat_eligibility(
            name="Action Against Hunger",
            mission=None,
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Thanks to your Zakat donations",
                "zakat_verification_confidence": 0.6,
            },
            ein="13-3327220",  # Action Against Hunger - in denylist
        )
        assert claims is False
        assert "denylist" in evidence.lower()

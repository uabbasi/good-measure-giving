"""Tests for synthesize.py - Phase 2 of the data pipeline.

Tests the deterministic Muslim charity classification, transparency scoring,
financial extraction, and error handling per specs/synthesize.md.
"""

import pytest

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from synthesize import (
    has_islamic_identity,
    serves_muslim_populations,
    compute_muslim_charity_fit,
    compute_transparency_score,
    extract_financials,
    ISLAMIC_IDENTITY_KEYWORDS,
    MUSLIM_REGION_KEYWORDS,
)


class TestHasIslamicIdentity:
    """Test has_islamic_identity() - deterministic keyword detection."""

    def test_explicit_islamic_name(self):
        """Charity with 'Islamic' in name should be detected."""
        assert has_islamic_identity("Islamic Relief USA", "humanitarian aid") is True

    def test_masjid_name(self):
        """Charity with 'Masjid' in name should be detected."""
        assert has_islamic_identity("Masjid Al-Rahman", None) is True

    def test_mosque_name(self):
        """Charity with 'Mosque' in name should be detected."""
        assert has_islamic_identity("Boston Mosque", "community services") is True

    def test_zakat_in_name(self):
        """Charity with 'Zakat' in name should be detected."""
        assert has_islamic_identity("Zakat Foundation of America", None) is True

    def test_islamic_giving_in_mission(self):
        """Islamic giving terms in mission should be detected."""
        assert has_islamic_identity("Local Charity", "We collect zakat and sadaqah") is True

    def test_religious_event_in_mission(self):
        """Religious events in mission should be detected."""
        assert has_islamic_identity("Community Center", "Ramadan food distribution and Eid celebrations") is True

    def test_no_keywords_secular(self):
        """Secular charity should not be detected."""
        assert has_islamic_identity("Red Cross", "disaster relief worldwide") is False

    def test_no_keywords_generic(self):
        """Generic charity should not be detected."""
        assert has_islamic_identity("Doctors Without Borders", "medical aid") is False

    def test_empty_values(self):
        """Empty name and mission should not cause errors."""
        assert has_islamic_identity("", "") is False
        assert has_islamic_identity("", None) is False

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert has_islamic_identity("ISLAMIC RELIEF", "ZAKAT DISTRIBUTION") is True
        assert has_islamic_identity("islamic relief", "zakat distribution") is True


class TestServesMuslimPopulations:
    """Test serves_muslim_populations() - region-based detection."""

    def test_gaza_in_mission(self):
        """Gaza in mission should be detected."""
        assert serves_muslim_populations("Helping families in Gaza", []) is True

    def test_syria_in_mission(self):
        """Syria in mission should be detected."""
        assert serves_muslim_populations("Syria relief efforts", []) is True

    def test_yemen_in_coverage(self):
        """Yemen in geographic coverage should be detected."""
        assert serves_muslim_populations("humanitarian aid", ["Yemen", "Somalia"]) is True

    def test_rohingya_in_mission(self):
        """Rohingya in mission should be detected."""
        assert serves_muslim_populations("Rohingya refugee support", []) is True

    def test_multiple_regions(self):
        """Multiple Muslim-majority regions should be detected."""
        assert serves_muslim_populations("", ["Pakistan", "Bangladesh", "Indonesia"]) is True

    def test_no_muslim_regions(self):
        """Non-Muslim regions should not be detected."""
        assert serves_muslim_populations("local food bank", ["New York", "California"]) is False

    def test_empty_values(self):
        """Empty values should not cause errors."""
        assert serves_muslim_populations("", []) is False
        assert serves_muslim_populations(None, None) is False

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert serves_muslim_populations("GAZA RELIEF", []) is True
        assert serves_muslim_populations("", ["AFGHANISTAN"]) is True


class TestComputeMuslimCharityFit:
    """Test compute_muslim_charity_fit() - truth table from spec."""

    def test_both_true(self):
        """has_islamic_identity=TRUE, serves_muslim_populations=TRUE -> 'high'"""
        assert compute_muslim_charity_fit(True, True) == "high"

    def test_identity_only(self):
        """has_islamic_identity=TRUE, serves_muslim_populations=FALSE -> 'high'"""
        assert compute_muslim_charity_fit(True, False) == "high"

    def test_serves_only(self):
        """has_islamic_identity=FALSE, serves_muslim_populations=TRUE -> 'medium'"""
        assert compute_muslim_charity_fit(False, True) == "medium"

    def test_neither(self):
        """has_islamic_identity=FALSE, serves_muslim_populations=FALSE -> 'low'"""
        assert compute_muslim_charity_fit(False, False) == "low"


class TestComputeTransparencyScore:
    """Test compute_transparency_score() - Candid seal mapping."""

    def test_platinum_seal(self):
        """Platinum seal should map to 100."""
        data = {"candid_profile": {"candid_seal": "platinum"}}
        assert compute_transparency_score(data) == 100

    def test_gold_seal(self):
        """Gold seal should map to 85."""
        data = {"candid_profile": {"candid_seal": "gold"}}
        assert compute_transparency_score(data) == 85

    def test_silver_seal(self):
        """Silver seal should map to 70."""
        data = {"candid_profile": {"candid_seal": "silver"}}
        assert compute_transparency_score(data) == 70

    def test_bronze_seal(self):
        """Bronze seal should map to 50."""
        data = {"candid_profile": {"candid_seal": "bronze"}}
        assert compute_transparency_score(data) == 50

    def test_no_seal(self):
        """No seal should return None."""
        data = {"candid_profile": {}}
        assert compute_transparency_score(data) is None

    def test_none_data(self):
        """None data should return None."""
        assert compute_transparency_score(None) is None

    def test_case_insensitive(self):
        """Seal detection should be case-insensitive."""
        data = {"candid_profile": {"candid_seal": "PLATINUM"}}
        assert compute_transparency_score(data) == 100

    def test_alternate_key(self):
        """Should also check seal_level key."""
        data = {"candid_profile": {"seal_level": "gold"}}
        assert compute_transparency_score(data) == 85


class TestExtractFinancials:
    """Test extract_financials() - source precedence and attribution."""

    def test_propublica_precedence(self):
        """ProPublica should take precedence over CN for financials."""
        pp_data = {"propublica_990": {"total_revenue": 1_000_000}}
        cn_data = {"cn_profile": {"total_revenue": 900_000}}
        financials, _ = extract_financials(cn_data, pp_data, "12-3456789")
        assert financials["total_revenue"] == 1_000_000

    def test_cn_fallback(self):
        """CN should be used when ProPublica is missing."""
        cn_data = {"cn_profile": {"total_revenue": 900_000}}
        financials, _ = extract_financials(cn_data, None, "12-3456789")
        assert financials["total_revenue"] == 900_000

    def test_program_expense_ratio_from_cn(self):
        """Program expense ratio should come from CN if available."""
        cn_data = {"cn_profile": {"program_expense_ratio": 0.85}}
        financials, _ = extract_financials(cn_data, None, "12-3456789")
        assert financials["program_expense_ratio"] == 0.85

    def test_calculated_ratio(self):
        """Ratio should be calculated if not from CN."""
        pp_data = {"propublica_990": {
            "program_expenses": 800_000,
            "total_revenue": 1_000_000,
        }}
        financials, _ = extract_financials(None, pp_data, "12-3456789")
        assert financials["program_expense_ratio"] == 0.8

    def test_attribution_created(self):
        """Source attribution should be created for each field."""
        pp_data = {"propublica_990": {"total_revenue": 1_000_000}}
        _, attribution = extract_financials(None, pp_data, "12-3456789")
        assert "total_revenue" in attribution
        assert attribution["total_revenue"]["source_name"] == "ProPublica Form 990"

    def test_int_conversion(self):
        """Financial values should be converted to int."""
        pp_data = {"propublica_990": {"total_revenue": 1_000_000.50}}
        financials, _ = extract_financials(None, pp_data, "12-3456789")
        assert isinstance(financials["total_revenue"], int)
        assert financials["total_revenue"] == 1_000_000


class TestClassificationExamples:
    """Test examples from spec - real charity classifications."""

    def test_islamic_relief_usa(self):
        """Islamic Relief USA: identity=TRUE, serves=TRUE -> high"""
        identity = has_islamic_identity("Islamic Relief USA", "Islamic humanitarian aid")
        serves = serves_muslim_populations("Islamic humanitarian aid", [])
        fit = compute_muslim_charity_fit(identity, serves)
        assert identity is True
        assert fit == "high"

    def test_local_masjid(self):
        """Local Masjid: identity=TRUE, serves=FALSE -> high"""
        identity = has_islamic_identity("Local Masjid", "community prayer services")
        serves = serves_muslim_populations("community prayer services", ["Chicago"])
        fit = compute_muslim_charity_fit(identity, serves)
        assert identity is True
        assert serves is False
        assert fit == "high"

    def test_syria_relief_network(self):
        """Syria Relief Network: identity=FALSE, serves=TRUE -> medium"""
        identity = has_islamic_identity("Syria Relief Network", "humanitarian aid in Syria")
        serves = serves_muslim_populations("humanitarian aid in Syria", ["Syria"])
        fit = compute_muslim_charity_fit(identity, serves)
        assert identity is False
        assert serves is True
        assert fit == "medium"

    def test_red_cross(self):
        """Red Cross: identity=FALSE, serves=FALSE -> low"""
        identity = has_islamic_identity("Red Cross", "disaster relief worldwide")
        serves = serves_muslim_populations("disaster relief worldwide", ["USA", "Europe"])
        fit = compute_muslim_charity_fit(identity, serves)
        assert identity is False
        assert serves is False
        assert fit == "low"


class TestKeywordCoverage:
    """Ensure keyword sets are comprehensive."""

    def test_islamic_identity_keywords_exist(self):
        """Verify Islamic identity keywords are defined."""
        assert len(ISLAMIC_IDENTITY_KEYWORDS) >= 15
        assert 'islamic' in ISLAMIC_IDENTITY_KEYWORDS
        assert 'zakat' in ISLAMIC_IDENTITY_KEYWORDS
        assert 'ramadan' in ISLAMIC_IDENTITY_KEYWORDS

    def test_muslim_region_keywords_exist(self):
        """Verify Muslim region keywords are defined."""
        assert len(MUSLIM_REGION_KEYWORDS) >= 10
        assert 'palestine' in MUSLIM_REGION_KEYWORDS
        assert 'gaza' in MUSLIM_REGION_KEYWORDS
        assert 'syria' in MUSLIM_REGION_KEYWORDS


class TestUpdateCharitiesTable:
    """Test update_charities_table() - field propagation from raw sources to charities table."""

    def test_city_state_zip_from_propublica(self):
        """ProPublica city/state/zip should be extracted."""
        from synthesize import update_charities_table
        from unittest.mock import MagicMock, patch

        # Mock charity repo
        mock_repo = MagicMock()

        pp_data = {
            "propublica_990": {
                "city": "Chicago",
                "state": "IL",
                "zipcode": "60606",
                "address": "123 Main St",
            }
        }

        with patch("src.db.client.execute_query") as mock_execute:
            count = update_charities_table(
                ein="12-3456789",
                pp_data=pp_data,
                candid_data=None,
                website_data=None,
                charity_repo=mock_repo,
            )

            # Should have updated 4 fields (city, state, zip, address)
            assert count == 4
            # Should have called execute_query with UPDATE statement
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            sql = call_args[0][0]
            values = call_args[0][1]
            assert "UPDATE charities SET" in sql
            assert "Chicago" in values
            assert "IL" in values
            assert "60606" in values
            assert "123 Main St" in values
            assert "12-3456789" in values  # EIN in WHERE clause

    def test_candid_fallback_for_location(self):
        """Candid should be used as fallback for location fields."""
        from synthesize import update_charities_table
        from unittest.mock import MagicMock, patch

        mock_repo = MagicMock()

        # ProPublica missing location
        pp_data = {"propublica_990": {"total_revenue": 1000000}}

        candid_data = {
            "candid_profile": {
                "city": "New York",
                "state": "NY",
                "zip": "10001",
            }
        }

        with patch("src.db.client.execute_query") as mock_execute:
            count = update_charities_table(
                ein="12-3456789",
                pp_data=pp_data,
                candid_data=candid_data,
                website_data=None,
                charity_repo=mock_repo,
            )

            # Should have updated 3 fields from Candid
            assert count == 3
            call_args = mock_execute.call_args
            values = call_args[0][1]
            assert "New York" in values
            assert "NY" in values
            assert "10001" in values

    def test_mission_from_candid_preferred(self):
        """Candid mission should be preferred over website."""
        from synthesize import update_charities_table
        from unittest.mock import MagicMock, patch

        mock_repo = MagicMock()

        candid_data = {
            "candid_profile": {
                "mission": "Candid mission statement",
            }
        }
        website_data = {
            "website_profile": {
                "mission": "Website mission statement",
            }
        }

        with patch("src.db.client.execute_query") as mock_execute:
            count = update_charities_table(
                ein="12-3456789",
                pp_data=None,
                candid_data=candid_data,
                website_data=website_data,
                charity_repo=mock_repo,
            )

            # Should have updated 1 field (mission from Candid)
            assert count == 1
            call_args = mock_execute.call_args
            values = call_args[0][1]
            assert "Candid mission statement" in values

    def test_mission_fallback_to_website(self):
        """Website mission should be used when Candid is missing."""
        from synthesize import update_charities_table
        from unittest.mock import MagicMock, patch

        mock_repo = MagicMock()

        website_data = {
            "website_profile": {
                "mission": "Website mission statement",
            }
        }

        with patch("src.db.client.execute_query") as mock_execute:
            count = update_charities_table(
                ein="12-3456789",
                pp_data=None,
                candid_data=None,
                website_data=website_data,
                charity_repo=mock_repo,
            )

            # Should have updated 1 field (mission from website)
            assert count == 1
            call_args = mock_execute.call_args
            values = call_args[0][1]
            assert "Website mission statement" in values

    def test_no_update_when_no_fields(self):
        """Should not call execute_query if no fields to update."""
        from synthesize import update_charities_table
        from unittest.mock import MagicMock, patch

        mock_repo = MagicMock()

        with patch("src.db.client.execute_query") as mock_execute:
            count = update_charities_table(
                ein="12-3456789",
                pp_data=None,
                candid_data=None,
                website_data=None,
                charity_repo=mock_repo,
            )

            # Should not have called execute_query
            assert count == 0
            mock_execute.assert_not_called()

    def test_zipcode_field_variation(self):
        """Should handle both 'zipcode' and 'zip' field names from ProPublica."""
        from synthesize import update_charities_table
        from unittest.mock import MagicMock, patch

        mock_repo = MagicMock()

        # ProPublica uses 'zip' instead of 'zipcode' in some cases
        pp_data = {
            "propublica_990": {
                "city": "Boston",
                "state": "MA",
                "zip": "02101",  # Using 'zip' not 'zipcode'
            }
        }

        with patch("src.db.client.execute_query") as mock_execute:
            update_charities_table(
                ein="12-3456789",
                pp_data=pp_data,
                candid_data=None,
                website_data=None,
                charity_repo=mock_repo,
            )

            call_args = mock_execute.call_args
            values = call_args[0][1]
            assert "02101" in values


class TestZakatDenylistInCorroboration:
    """Test that denylist is respected even when corroboration passes.

    Bug fix: Previously, if a denylisted charity had accepts_zakat=True in
    website_profile, the corroboration would pass and override the denylist.
    """

    def test_denylisted_charity_not_overridden_by_corroboration(self):
        """Charity in denylist should NOT be marked zakat-eligible even if website says so."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator
        from src.services.zakat_eligibility_service import ZAKAT_DENYLIST

        # UNICEF USA is in the denylist (partners with zakat orgs but doesn't collect directly)
        ein = "13-1760110"
        assert ein in ZAKAT_DENYLIST, "Test requires UNICEF USA to be in denylist"

        # Even if website claims zakat acceptance, denylist should win
        website_profile = {
            "accepts_zakat": True,
            "zakat_evidence": "Zakat donations accepted",
            "zakat_url": "https://example.org/zakat",
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein=ein,
            cn_profile={"name": "UNICEF USA"},
            website_profile=website_profile,
        )

        # Should be False because of denylist, not True from corroboration override
        assert metrics.zakat_claim_detected is False or metrics.zakat_claim_detected is None

    def test_non_denylisted_charity_can_be_corroborated(self):
        """Non-denylisted charity with website zakat claim SHOULD be marked eligible."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator
        from src.services.zakat_eligibility_service import ZAKAT_DENYLIST

        # A random EIN that's NOT in the denylist
        ein = "99-9999999"
        assert ein not in ZAKAT_DENYLIST

        # Website claims zakat acceptance with "zakat" keyword in evidence
        website_profile = {
            "accepts_zakat": True,
            "zakat_evidence": "Give your zakat to help the poor",
            "zakat_url": "https://example.org/zakat",
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein=ein,
            cn_profile={"name": "Example Islamic Charity"},
            website_profile=website_profile,
        )

        # Should be True - corroboration passes and no denylist block
        assert metrics.zakat_claim_detected is True


class TestBeneficiariesStringParsing:
    """Test beneficiaries extraction from impact_metrics handles various string formats."""

    def test_numeric_with_trailing_text(self):
        """'1,000,000 annually' should parse correctly."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        website_profile = {
            "impact_metrics": {
                "metrics": {
                    "people_served_annually": "1,000,000 annually",
                }
            }
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein="12-3456789",
            cn_profile={"name": "Test Charity"},
            website_profile=website_profile,
        )

        assert metrics.beneficiaries_served_annually == 1_000_000

    def test_million_multiplier(self):
        """'85 million' should be parsed as 85,000,000."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        website_profile = {
            "impact_metrics": {
                "metrics": {
                    "people_reached": "85 million",
                }
            }
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein="12-3456789",
            cn_profile={"name": "Test Charity"},
            website_profile=website_profile,
        )

        assert metrics.beneficiaries_served_annually == 85_000_000

    def test_thousand_multiplier(self):
        """'500 thousand' should be parsed as 500,000."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        website_profile = {
            "impact_metrics": {
                "metrics": {
                    "beneficiaries_helped": "500 thousand",
                }
            }
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein="12-3456789",
            cn_profile={"name": "Test Charity"},
            website_profile=website_profile,
        )

        assert metrics.beneficiaries_served_annually == 500_000

    def test_comma_separated_number(self):
        """'1,234,567' should parse correctly."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        website_profile = {
            "impact_metrics": {
                "metrics": {
                    "people_impacted": "1,234,567",
                }
            }
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein="12-3456789",
            cn_profile={"name": "Test Charity"},
            website_profile=website_profile,
        )

        assert metrics.beneficiaries_served_annually == 1_234_567


class TestProgramDeduplication:
    """Test program deduplication handles duplicates efficiently."""

    def test_exact_duplicates_removed(self):
        """Exact duplicate programs should be removed."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        candid_profile = {
            "programs": ["Food Distribution", "Medical Aid"],
        }
        website_profile = {
            "programs": ["food distribution", "Water Wells"],  # Case-insensitive dup
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein="12-3456789",
            cn_profile={"name": "Test Charity"},
            candid_profile=candid_profile,
            website_profile=website_profile,
        )

        # Should have 3 programs (Food Distribution deduplicated)
        assert len(metrics.programs) == 3
        # Original case from Candid should be preserved
        assert "Food Distribution" in metrics.programs

    def test_fuzzy_duplicates_removed(self):
        """Similar programs (>85% match) should be deduplicated."""
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        candid_profile = {
            "programs": ["Emergency Food Distribution Program"],
        }
        website_profile = {
            "programs": ["Emergency Food Distribution"],  # Very similar
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein="12-3456789",
            cn_profile={"name": "Test Charity"},
            candid_profile=candid_profile,
            website_profile=website_profile,
        )

        # Should have 1 program (fuzzy match removed duplicate)
        assert len(metrics.programs) == 1

    def test_substring_duplicates_removed(self):
        """Programs that are substrings of others should be deduplicated.

        Note: Deduplication keeps the first occurrence. So if "Food" comes before
        "Food Distribution", "Food" is kept and "Food Distribution" is removed.
        """
        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        candid_profile = {
            "programs": ["Food", "Food Distribution", "Medical"],
        }

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein="12-3456789",
            cn_profile={"name": "Test Charity"},
            candid_profile=candid_profile,
        )

        # "Food Distribution" contains "Food" - should be deduplicated (first wins)
        assert len(metrics.programs) == 2
        assert "Food" in metrics.programs  # First occurrence kept
        assert "Medical" in metrics.programs

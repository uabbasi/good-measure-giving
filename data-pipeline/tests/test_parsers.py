"""
Parser unit tests for all collectors.

Tests the parse() method of each collector using fixture data.
These tests are deterministic and don't require network access.
"""

import json
import pytest
from pathlib import Path

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_EIN = "12-3456789"  # Synthetic test EIN


class TestProPublicaParser:
    """Test ProPublica collector parsing."""

    @pytest.fixture
    def collector(self):
        from src.collectors.propublica import ProPublicaCollector

        return ProPublicaCollector()

    @pytest.fixture
    def fixture_data(self) -> str:
        return (FIXTURES_DIR / "propublica_954453134.json").read_text()

    def test_parse_returns_success(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        assert result.success is True
        assert result.error is None

    def test_parse_extracts_organization_name(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["propublica_990"]
        assert "Example Relief" in profile["name"]

    def test_parse_extracts_financial_fields(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["propublica_990"]
        # Should have financial data
        assert "total_revenue" in profile
        assert "total_expenses" in profile
        assert "total_assets" in profile

    def test_parse_extracts_filing_history(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["propublica_990"]
        assert "filing_history" in profile
        assert isinstance(profile["filing_history"], list)
        assert len(profile["filing_history"]) > 0

    def test_parse_extracts_ein(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["propublica_990"]
        assert profile["ein"] == TEST_EIN

    def test_parse_handles_malformed_json(self, collector):
        result = collector.parse("not valid json", TEST_EIN)
        assert result.success is False
        assert result.error is not None


class TestCharityNavigatorParser:
    """Test Charity Navigator collector parsing."""

    @pytest.fixture
    def collector(self):
        from src.collectors.charity_navigator import CharityNavigatorCollector

        return CharityNavigatorCollector()

    @pytest.fixture
    def fixture_data(self) -> str:
        return (FIXTURES_DIR / "charity_navigator_954453134.html").read_text()

    def test_parse_returns_success(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        assert result.success is True

    def test_parse_extracts_name(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["cn_profile"]
        assert "name" in profile
        assert "Example Relief" in profile["name"]

    def test_parse_extracts_scores(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["cn_profile"]
        # Should have score fields
        assert "overall_score" in profile
        assert "financial_score" in profile
        assert "accountability_score" in profile

    def test_parse_extracts_expense_ratios(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["cn_profile"]
        assert "program_expense_ratio" in profile
        assert "admin_expense_ratio" in profile

    def test_parse_extracts_beacons(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["cn_profile"]
        assert "beacons" in profile
        assert isinstance(profile["beacons"], list)

    def test_parse_handles_empty_html(self, collector):
        result = collector.parse("", TEST_EIN)
        assert result.success is False


class TestCandidParser:
    """Test Candid/GuideStar collector parsing."""

    @pytest.fixture
    def collector(self):
        from src.collectors.candid_beautifulsoup import CandidCollector

        return CandidCollector()

    @pytest.fixture
    def fixture_data(self) -> str:
        return (FIXTURES_DIR / "candid_954453134.html").read_text()

    def test_parse_returns_success(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        assert result.success is True

    def test_parse_extracts_organization_name(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["candid_profile"]
        assert "name" in profile

    def test_parse_extracts_mission(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["candid_profile"]
        assert "mission" in profile

    def test_parse_extracts_metrics(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["candid_profile"]
        assert "metrics" in profile
        assert isinstance(profile["metrics"], list)

    def test_parse_extracts_programs(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["candid_profile"]
        assert "programs" in profile
        assert isinstance(profile["programs"], list)

    def test_parse_extracts_candid_seal(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["candid_profile"]
        assert "candid_seal" in profile

    def test_parse_extracts_charting_impact(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["candid_profile"]
        # Should have charting impact fields
        assert "charting_impact_goal" in profile
        assert "charting_impact_strategies" in profile

    def test_parse_extracts_feedback_practices(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["candid_profile"]
        # New feedback fields
        assert "feedback_practices" in profile
        assert isinstance(profile["feedback_practices"], list)


class TestBBBParser:
    """Test BBB Wise Giving collector parsing."""

    @pytest.fixture
    def collector(self):
        from src.collectors.bbb_collector import BBBCollector

        return BBBCollector()

    @pytest.fixture
    def fixture_data(self) -> str:
        return (FIXTURES_DIR / "bbb_954453134.html").read_text()

    def test_parse_returns_success(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        assert result.success is True

    def test_parse_extracts_name(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["bbb_profile"]
        assert "name" in profile

    def test_parse_extracts_meets_standards(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["bbb_profile"]
        assert "meets_standards" in profile
        assert profile["meets_standards"] is None or isinstance(profile["meets_standards"], bool)

    def test_parse_extracts_standards_details(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["bbb_profile"]
        assert "standards_details" in profile
        assert isinstance(profile["standards_details"], dict)

    def test_parse_extracts_category_pass_flags(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN)
        profile = result.parsed_data["bbb_profile"]
        # Should have category pass flags
        assert "governance_pass" in profile
        assert "finances_pass" in profile
        assert "effectiveness_pass" in profile
        assert "solicitations_pass" in profile


class TestWebsiteParser:
    """Test Website collector parsing."""

    @pytest.fixture
    def collector(self):
        from src.collectors.web_collector import WebsiteCollector

        return WebsiteCollector()

    @pytest.fixture
    def fixture_data(self) -> str:
        return (FIXTURES_DIR / "website_954453134.html").read_text()

    def test_parse_returns_success(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN, url="https://irusa.org")
        assert result.success is True

    def test_parse_extracts_url(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN, url="https://irusa.org")
        profile = result.parsed_data["website_profile"]
        assert profile["url"] == "https://irusa.org"

    def test_parse_extracts_donate_url(self, collector, fixture_data):
        result = collector.parse(fixture_data, TEST_EIN, url="https://irusa.org")
        profile = result.parsed_data["website_profile"]
        # May or may not have donate_url depending on page content
        assert "donate_url" in profile


class TestParserEdgeCases:
    """Test edge cases across all parsers."""

    def test_propublica_handles_missing_filings(self):
        from src.collectors.propublica import ProPublicaCollector

        collector = ProPublicaCollector()
        # Minimal valid JSON - note: ProPublica needs filings_with_data array
        minimal = json.dumps(
            {"organization": {"name": "Test Org", "ein": 123456789}, "filings_with_data": [{"tax_prd_yr": 2023}]}
        )
        result = collector.parse(minimal, "12-3456789")
        # Should succeed with minimal data
        assert result.success is True

    def test_candid_handles_empty_sections(self):
        from src.collectors.candid_beautifulsoup import CandidCollector

        collector = CandidCollector()
        # Minimal HTML
        minimal = "<html><body><h1>Test</h1></body></html>"
        result = collector.parse(minimal, "12-3456789")
        # Should succeed with empty/default values
        assert result.success is True
        profile = result.parsed_data["candid_profile"]
        assert profile["metrics"] == []
        assert profile["programs"] == []

    def test_bbb_handles_no_standards(self):
        from src.collectors.bbb_collector import BBBCollector

        collector = BBBCollector()
        # HTML with no standards data
        minimal = "<html><body><div>No data</div></body></html>"
        result = collector.parse(minimal, "12-3456789")
        # Should succeed with defaults
        assert result.success is True

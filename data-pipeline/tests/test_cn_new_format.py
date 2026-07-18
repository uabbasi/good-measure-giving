"""Charity Navigator 2026-07 redesigned-page extraction tests.

CN redesigned their charity profile pages (2026-07). The old extraction read
flat ``"slug":"calc_fund_eff_ratio"`` fields out of the Next.js flight payload;
the new page embeds a single structured ``"nonprofit":{...}`` object instead.

These tests pin the new-format extraction against a trimmed real sample
(Islamic Relief USA, EIN 95-4453134 — a 4-star CN charity) and assert the
format-drift markers recognize the new layout. The old-format regex path is
still exercised by ``tests/test_parsers.py`` (and re-checked here) so
previously-scraped raw_content keeps re-extracting offline.
"""

import re
from pathlib import Path

import pytest
from src.collectors.charity_navigator import CharityNavigatorCollector

FIXTURES_DIR = Path(__file__).parent / "fixtures"
NEW_FIXTURE = FIXTURES_DIR / "charity_navigator_954453134_2026-07.html"
OLD_FIXTURE = FIXTURES_DIR / "charity_navigator_954453134.html"
EIN = "95-4453134"


@pytest.fixture
def collector():
    # LLM extraction off: parsing must recover data structurally, no network.
    return CharityNavigatorCollector(use_llm_extraction=False)


@pytest.fixture
def new_html():
    return NEW_FIXTURE.read_text()


class TestNewFormatExtraction:
    """The 2026-07 redesigned page must yield the same cn_profile contract."""

    def test_parse_succeeds(self, collector, new_html):
        result = collector.parse(new_html, EIN)
        assert result.success is True, result.error

    def test_recovers_name(self, collector, new_html):
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        assert profile["name"] == "Islamic Relief USA"

    def test_recovers_overall_score_near_100(self, collector, new_html):
        # Ground truth: pre-drift cn_overall_score was 100 for this 4-star org.
        # CN scores can drift slightly between March and July.
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        overall = profile["overall_score"]
        assert isinstance(overall, (int, float))
        assert 90 <= overall <= 100

    def test_recovers_financial_score(self, collector, new_html):
        # Ground truth: pre-drift cn_financial_score was 100.
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        assert isinstance(profile["financial_score"], (int, float))
        assert profile["financial_score"] == pytest.approx(100.0)
        # accountability_score mirrors financial_score in the legacy contract.
        assert profile["accountability_score"] == profile["financial_score"]

    def test_recovers_mission(self, collector, new_html):
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        assert profile["mission"]
        assert "Islamic Relief USA" in profile["mission"]

    def test_recovers_star_rating(self, collector, new_html):
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        assert profile["star_rating"] == 4.0

    def test_marks_charity_rated(self, collector, new_html):
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        assert profile["cn_is_rated"] is True
        assert profile["cn_beacon_count"] >= 2

    def test_recovers_financial_ratios(self, collector, new_html):
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        # Program expense ratio parsed from "80.33% of total expenses".
        assert profile["program_expense_ratio"] == pytest.approx(0.8033)
        # Working capital "1.67 years of reserves" -> months.
        assert profile["working_capital_ratio"] == pytest.approx(20.04)
        # Fundraising efficiency "$0.16 to raise a dollar".
        assert profile["fundraising_efficiency"] == pytest.approx(0.16)

    def test_recovers_financials(self, collector, new_html):
        profile = collector.parse(new_html, EIN).parsed_data["cn_profile"]
        assert profile["total_revenue"] == pytest.approx(147232658.0)
        assert profile["fiscal_year"] == 2024
        assert profile["irs_ruling_year"] == 1994


class TestFormatMarkers:
    """CN_FORMAT_MARKERS must recognize the new format (no drift warnings)."""

    def test_all_markers_present_in_new_fixture(self, new_html):
        missing = [
            name
            for name, info in CharityNavigatorCollector.CN_FORMAT_MARKERS.items()
            if not re.search(info["pattern"], new_html)
        ]
        assert missing == [], f"markers missing on new format: {missing}"

    def test_no_critical_markers_missing(self, collector, new_html):
        # New format must not trip the H11 fail-closed path.
        assert collector._check_format_integrity(new_html, EIN) == []


class TestOldFormatStillParses:
    """Old-format stored HTML must keep parsing (offline re-extraction)."""

    def test_old_fixture_parses(self, collector):
        html = OLD_FIXTURE.read_text()
        result = collector.parse(html, EIN)
        assert result.success is True
        profile = result.parsed_data["cn_profile"]
        # Legacy fixture: name + beacon progress bars, no structured object.
        assert "Example Relief" in profile["name"]
        assert profile["overall_score"] is not None

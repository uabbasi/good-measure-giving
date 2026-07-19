"""Tests for the non-destructive-synthesize write-safety guards."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestStalenessConstant:
    def test_constant_is_two_years(self):
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS

        assert DATA_FULL_CONFIDENCE_MAX_AGE_YEARS == 2

    def test_recency_factor_uses_constant(self):
        # Age exactly at the boundary keeps full weight; one past it decays.
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        from src.scorers.v2_scorers import AmalScorerV2

        boundary = DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        assert AmalScorerV2._recency_factor(boundary) == 1.0
        assert AmalScorerV2._recency_factor(boundary + 1) < 1.0


class TestRawLayerPredicates:
    def test_data_age_years_from_datetime(self):
        from src.collectors.orchestrator import data_age_years

        now = datetime(2026, 7, 19)
        assert data_age_years(datetime(2024, 7, 19), now=now) == 2
        assert data_age_years(datetime(2023, 1, 1), now=now) == 3
        assert data_age_years(None, now=now) is None

    def test_data_age_years_from_iso_string(self):
        from src.collectors.orchestrator import data_age_years

        now = datetime(2026, 7, 19)
        assert data_age_years("2024-07-19 00:00:00", now=now) == 2

    def test_grants_has_filings(self):
        from src.collectors.orchestrator import grants_has_filings

        empty = {"grants_profile": {"name": "Unknown (12-3456789)", "ein": "12-3456789"}}
        real = {"grants_profile": {"ein": "12-3456789", "filing_years": [2022], "total_grants": 5000}}
        assert grants_has_filings(empty) is False
        assert grants_has_filings(real) is True
        assert grants_has_filings(None) is False

    def test_website_downgrade_thin_replaces_rich(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 25}}
        thin = {"crawl_stats": {"pages_crawled": 1}}
        assert is_content_downgrade("website", thin, "x" * 600, prior) is True

    def test_website_no_downgrade_when_similar(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 8}}
        fresh = {"crawl_stats": {"pages_crawled": 9}}
        assert is_content_downgrade("website", fresh, "x" * 5000, prior) is False

    def test_website_downgrade_empty_raw(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 10}}
        assert is_content_downgrade("website", {"crawl_stats": {"pages_crawled": 2}}, "", prior) is True

    def test_grants_downgrade_empty_replaces_filings(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"grants_profile": {"filing_years": [2022], "total_grants": 9000}}
        empty = {"grants_profile": {"name": "Unknown", "ein": "12-3456789"}}
        assert is_content_downgrade("form990_grants", empty, None, prior) is True

    def test_no_downgrade_without_prior(self):
        from src.collectors.orchestrator import is_content_downgrade

        assert is_content_downgrade("website", {"crawl_stats": {"pages_crawled": 1}}, "x", {}) is False

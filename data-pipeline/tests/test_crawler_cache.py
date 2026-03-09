"""Tests for CrawlerCache cloudflare profile persistence."""

import json
import tempfile
from pathlib import Path

import pytest

from src.utils.crawler_cache import CrawlerCache


class TestCloudflareProfilePersistence:
    """Tests for cloudflare/bot protection profile persistence."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield CrawlerCache(cache_dir=Path(tmpdir), ttl_days=180)

    def test_set_and_get_profile(self, cache):
        """Test setting and retrieving a single profile."""
        cache.set_cloudflare_profile("example.org", "safari15_5")

        profile = cache.get_cloudflare_profile("example.org")
        assert profile == "safari15_5"

    def test_get_nonexistent_profile(self, cache):
        """Test retrieving a profile that doesn't exist."""
        profile = cache.get_cloudflare_profile("nonexistent.org")
        assert profile is None

    def test_overwrite_profile(self, cache):
        """Test that setting a profile for an existing domain overwrites it."""
        cache.set_cloudflare_profile("example.org", "safari15_5")
        cache.set_cloudflare_profile("example.org", "chrome120")

        profile = cache.get_cloudflare_profile("example.org")
        assert profile == "chrome120"

    def test_get_all_profiles(self, cache):
        """Test retrieving all profiles."""
        cache.set_cloudflare_profile("example.org", "safari15_5")
        cache.set_cloudflare_profile("test.com", "chrome120")
        cache.set_cloudflare_profile("another.net", "edge101")

        all_profiles = cache.get_all_cloudflare_profiles()

        assert all_profiles == {
            "example.org": "safari15_5",
            "test.com": "chrome120",
            "another.net": "edge101",
        }

    def test_get_all_profiles_empty(self, cache):
        """Test retrieving all profiles when none exist."""
        all_profiles = cache.get_all_cloudflare_profiles()
        assert all_profiles == {}

    def test_persistence_across_instances(self):
        """Test that profiles persist when creating a new cache instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # First instance - set profiles
            cache1 = CrawlerCache(cache_dir=cache_dir, ttl_days=180)
            cache1.set_cloudflare_profile("example.org", "safari15_5")
            cache1.set_cloudflare_profile("test.com", "chrome120")

            # Second instance - should load persisted profiles
            cache2 = CrawlerCache(cache_dir=cache_dir, ttl_days=180)
            all_profiles = cache2.get_all_cloudflare_profiles()

            assert all_profiles == {
                "example.org": "safari15_5",
                "test.com": "chrome120",
            }

    def test_profile_file_format(self, cache):
        """Test that the profile file has expected JSON structure."""
        cache.set_cloudflare_profile("example.org", "safari15_5")

        # Read the raw file
        profiles_path = cache._get_cloudflare_profiles_path()
        with open(profiles_path) as f:
            data = json.load(f)

        # Check structure
        assert "example.org" in data
        assert data["example.org"]["profile"] == "safari15_5"
        assert "updated_at" in data["example.org"]


class TestCaptchaDetectionStatusCodes:
    """Tests to verify captcha detection includes all expected status codes."""

    def test_sync_path_includes_503(self):
        """Verify sync _fetch_url handles 503 as potential captcha."""
        # This is a documentation test - the actual code has:
        # elif response.status_code in (403, 202, 503) and HAS_CURL_CFFI:
        from src.collectors.web_collector import WebsiteCollector
        import inspect

        source = inspect.getsource(WebsiteCollector._fetch_url)
        assert "503" in source, "503 should be in sync captcha detection"

    def test_async_path_includes_503(self):
        """Verify async _fetch_url_async handles 503 as potential captcha."""
        from src.collectors.web_collector import WebsiteCollector
        import inspect

        source = inspect.getsource(WebsiteCollector._fetch_url_async)
        assert "503" in source, "503 should be in async captcha detection"


class TestCurlCffiRetryDelay:
    """Tests to verify delay between curl_cffi retry attempts."""

    def test_sync_path_has_delay(self):
        """Verify sync path has sleep between profile attempts."""
        from src.collectors.web_collector import WebsiteCollector
        import inspect

        source = inspect.getsource(WebsiteCollector._fetch_url)
        assert "time.sleep" in source, "Sync path should have time.sleep between retries"

    def test_async_path_has_delay(self):
        """Verify async path has asyncio.sleep between profile attempts."""
        from src.collectors.web_collector import WebsiteCollector
        import inspect

        source = inspect.getsource(WebsiteCollector._try_curl_cffi_async)
        assert "asyncio.sleep" in source, "Async path should have asyncio.sleep between retries"

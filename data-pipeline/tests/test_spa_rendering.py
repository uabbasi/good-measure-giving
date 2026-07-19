"""Task 9: Playwright SPA recovery must actually fire on the production
async crawl path (collect_multi_page -> _crawl_specific_urls_async /
_crawl_with_bfs_async).

Root cause: js_rendering_needed was only ever computed inside
`_extract_page_data`'s `if use_llm and self.llm_extractor:` branch. The
async crawlers call `_extract_page_data` with use_llm=False for most pages
(_crawl_specific_urls_async always does), so the flag was never set on the
production path and the Playwright escalation -- which only existed on the
dead sync crawlers anyway -- could never fire. Client-rendered SPA sites
therefore returned {} -> "no data found".
"""

from unittest.mock import MagicMock, patch

from src.collectors.web_collector import WebsiteCollector
from src.constants import CRAWL_GLOBAL_MIN_INTERVAL_SECONDS
from src.extractors.deterministic import DeterministicExtractor
from src.extractors.page_classifier import PageClassifier
from src.extractors.structured_data import StructuredDataExtractor
from src.utils.text_cleaner import TextCleaner


class TestJsRenderingNeededHoistedOutOfUseLlm:
    """_extract_page_data must flag js_rendering_needed even when called
    with use_llm=False (the async production path's default)."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.use_llm = False
        c.llm_extractor = None
        c.structured_extractor = StructuredDataExtractor()
        c.deterministic_extractor = DeterministicExtractor()
        c.text_cleaner = TextCleaner()
        c.page_classifier = PageClassifier()
        c.pdf_downloader = MagicMock()
        c.pdf_downloader.identify_pdfs.return_value = []
        return c

    def test_empty_spa_shell_flags_js_rendering_needed_without_llm(self):
        c = self._collector()
        spa_html = "<html><body><div id=\"root\"></div><script src=\"/app.js\"></script></body></html>"

        page_data = c._extract_page_data(spa_html, "https://spa.org/", use_llm=False)

        assert page_data["js_rendering_needed"] is True
        assert page_data["extraction_failure_reason"] == "empty_content"

    def test_real_content_does_not_flag_js_rendering_needed(self):
        c = self._collector()
        real_html = "<html><body>" + ("<p>Real crawlable content about our mission and programs. </p>" * 10) + "</body></html>"

        page_data = c._extract_page_data(real_html, "https://real.org/", use_llm=False)

        assert page_data["js_rendering_needed"] is False


class TestPlaywrightAsyncEscalation:
    """collect_multi_page only ever called the async crawlers; Playwright
    was wired up solely in the (unused) sync crawlers. Verify the escalation
    added to collect_multi_page actually invokes the renderer for pages
    flagged js_rendering_needed and re-extracts from the rendered HTML."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.use_llm = False
        c.max_pdf_downloads = 0
        c.robots_checker = MagicMock()
        c.robots_checker.get_crawl_delay.return_value = None
        c._last_captcha_error = None
        c.cache = MagicMock()
        c._cleanup_playwright = MagicMock()
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://spa.org/"]))
        c._fetch_url = MagicMock(return_value=(True, "<html>homepage</html>", "https://spa.org/", None))
        c._rate_limit = MagicMock()
        return c

    @staticmethod
    def _thin_spa_page_data():
        # What _extract_page_data now returns (post-hoist) for a JS-only
        # shell on the no-LLM async path: no real fields, but flagged.
        return {
            "ein": None,
            "email": None,
            "phone": None,
            "address": None,
            "donate_url": None,
            "social_media": {},
            "tax_deductible": None,
            "structured_data": {},
            "extraction_results": [],
            "llm_data": None,
            "llm_cost": 0.0,
            "pdf_links": [],
            "had_data": False,
            "js_rendering_needed": True,
            "extraction_failure_reason": "empty_content",
            "zakat_detected": False,
            "zakat_keywords": [],
        }

    def test_flagged_page_is_rendered_and_reextracted(self):
        c = self._collector()
        url = "https://spa.org/"
        c._crawl_specific_urls_async = MagicMock(return_value={url: self._thin_spa_page_data()})

        rendered_html = "<html><body>EIN: 12-3456789</body></html>"
        renderer = MagicMock()
        renderer.render.return_value = rendered_html
        c._get_playwright_renderer = MagicMock(return_value=renderer)

        recovered = dict(self._thin_spa_page_data())
        recovered.update(
            {"ein": "12-3456789", "had_data": True, "js_rendering_needed": False, "extraction_failure_reason": None}
        )
        c._extract_page_data = MagicMock(return_value=recovered)

        with patch("src.collectors.web_collector.global_rate_limiter") as mock_limiter:
            mock_limiter.wait.return_value = 0.0
            ok, data, err = c.collect_multi_page(url, ein=None)

        renderer.render.assert_called_once_with(url)
        c._extract_page_data.assert_called_once_with(rendered_html, url, use_llm=False)
        assert ok is True
        assert data["website_profile"]["ein"] == "12-3456789"
        # FIX 1: the Playwright render must pass through the fleet-wide QPS
        # gate. No robots Crawl-delay here (None) -> only the "website" gate
        # fires, exactly once, no per-host gate.
        mock_limiter.wait.assert_called_once_with("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)
        # FIX 2: the per-URL cache is refreshed so it stops recording
        # had_data:false for the page we just recovered.
        c.cache.update_had_data.assert_called_once()
        cache_call = c.cache.update_had_data.call_args
        assert cache_call.args[0] == url
        assert cache_call.args[1] is True  # had_data
        assert "playwright" in cache_call.args[2]  # extraction methods

    def test_rendered_page_honors_per_host_crawl_delay(self):
        """FIX 1 (Task 8 politeness): when robots.txt advertises a Crawl-delay,
        the Playwright render must ALSO wait on the per-host gate, not just the
        fleet-wide 'website' gate."""
        c = self._collector()
        c.robots_checker.get_crawl_delay.return_value = 10.0  # advertised delay
        url = "https://spa.org/"
        c._crawl_specific_urls_async = MagicMock(return_value={url: self._thin_spa_page_data()})

        renderer = MagicMock()
        renderer.render.return_value = "<html><body>EIN: 12-3456789</body></html>"
        c._get_playwright_renderer = MagicMock(return_value=renderer)

        recovered = dict(self._thin_spa_page_data())
        recovered.update({"ein": "12-3456789", "had_data": True, "js_rendering_needed": False})
        c._extract_page_data = MagicMock(return_value=recovered)

        with patch("src.collectors.web_collector.global_rate_limiter") as mock_limiter:
            mock_limiter.wait.return_value = 0.0
            c.collect_multi_page(url, ein=None)

        # Both gates fire before the render: fleet-wide "website" + per-host.
        mock_limiter.wait.assert_any_call("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)
        mock_limiter.wait.assert_any_call("spa.org", 10.0)

    def test_no_renderer_available_is_a_graceful_noop(self):
        """_get_playwright_renderer() returning None (Playwright not
        installed, or use_playwright disabled) must not crash and must not
        attempt re-extraction."""
        c = self._collector()
        url = "https://spa.org/"
        c._crawl_specific_urls_async = MagicMock(return_value={url: self._thin_spa_page_data()})
        c._get_playwright_renderer = MagicMock(return_value=None)
        c._extract_page_data = MagicMock()

        ok, data, err = c.collect_multi_page(url, ein=None)

        c._extract_page_data.assert_not_called()
        assert ok is True  # crawl_results still non-empty (the flag itself is truthy) -- no crash
        assert data["website_profile"].get("ein") is None

    def test_page_without_js_flag_is_not_escalated(self):
        """A normal page with real data (js_rendering_needed=False) must
        not trigger a Playwright render at all."""
        c = self._collector()
        url = "https://normal.org/"
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, [url]))
        c._fetch_url = MagicMock(return_value=(True, "<html>homepage</html>", url, None))
        normal_page = dict(self._thin_spa_page_data())
        normal_page.update({"ein": "98-7654321", "had_data": True, "js_rendering_needed": False})
        c._crawl_specific_urls_async = MagicMock(return_value={url: normal_page})
        renderer = MagicMock()
        c._get_playwright_renderer = MagicMock(return_value=renderer)

        ok, data, err = c.collect_multi_page(url, ein=None)

        renderer.render.assert_not_called()
        assert ok is True
        assert data["website_profile"]["ein"] == "98-7654321"

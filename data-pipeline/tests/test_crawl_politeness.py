"""H5: crawl politeness + terminal failure classification (pure-function tests)."""

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.collectors.orchestrator import (
    DataCollectionOrchestrator,
    classify_failure,
    is_optional_website_failure,
)
from src.collectors.web_collector import WebsiteCollector
from src.constants import (
    CRAWL_GLOBAL_MIN_INTERVAL_SECONDS,
    PER_DOMAIN_CONCURRENCY,
    TERMINAL_FAILURE_TTL_DAYS,
)


class TestClassifyFailure:
    def test_captcha_is_terminal(self):
        assert classify_failure("CAPTCHA_BLOCKED: challenge page (HTTP 200)") == "captcha_blocked"

    def test_not_found_is_terminal(self):
        assert classify_failure("Organization not found for EIN 12-3456789") == "not found"

    def test_timeout_is_transient(self):
        assert classify_failure("Timeout") is None

    def test_none_and_empty(self):
        assert classify_failure(None) is None
        assert classify_failure("") is None

    def test_no_data_found_is_not_terminal(self):
        # "No data found on any pages" must NOT match the "not found" marker
        assert classify_failure("No data found on any pages") is None


class TestOptionalDemotion:
    def test_captcha_no_longer_demotes_website(self):
        assert is_optional_website_failure(["CAPTCHA_BLOCKED: challenge page (HTTP 200)"]) is False

    def test_http_429_no_longer_demotes(self):
        assert is_optional_website_failure(["CAPTCHA_BLOCKED: HTTP 429"]) is False

    def test_genuine_no_data_still_demotes(self):
        assert is_optional_website_failure(["No data found on any pages"]) is True

    def test_empty(self):
        assert is_optional_website_failure([]) is False


class TestPerDomainSemaphores:
    def test_same_domain_shares_semaphore(self):
        get_sem = WebsiteCollector._per_domain_semaphores(limit=2)
        a1 = get_sem("https://example.org/a")
        a2 = get_sem("https://example.org/b")
        b = get_sem("https://other.org/")
        assert a1 is a2
        assert a1 is not b
        assert a1._value == 2

    def test_default_limit_is_constant(self):
        assert PER_DOMAIN_CONCURRENCY == 2


def test_terminal_ttl_is_180_days():
    assert TERMINAL_FAILURE_TTL_DAYS == 180


class TestSingleRetryIncrementPerWebsiteFailure:
    """H5 follow-up: exactly ONE retry-count-advancing DB write per website failure.

    On the fetch path, _store_failed_crawl -> upsert(success=False) already
    increments retry_count (Task 1 semantics), so that path must NOT also call
    increment_retry_count — otherwise website backs off twice as fast as every
    other source.
    """

    def _make_orchestrator(self):
        orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
        orch.logger = MagicMock()
        # Skip every non-website source so only the website block runs
        orch.skip_sources = {"propublica", "charity_navigator", "candid", "form990_grants", "bbb"}
        orch.frozen_sources = set()  # H12: not testing the freeze label here
        orch.blocked_sites = []
        orch._blocked_sites_lock = threading.Lock()
        orch.raw_data_repo = MagicMock()
        # No prior row: not fresh, no backoff skip
        orch.raw_data_repo.get_by_source.return_value = None
        orch.charity_repo = MagicMock()
        orch.website = MagicMock()
        orch._get_or_create_charity = lambda ein, name=None, website=None: ein
        return orch

    @staticmethod
    def _retry_advancing_writes(repo) -> int:
        """Count DB writes that advance retry_count: failure upserts + explicit increments."""
        failure_upserts = sum(
            1 for c in repo.upsert.call_args_list if c.kwargs.get("success") is False
        )
        return failure_upserts + repo.increment_retry_count.call_count

    def test_fetch_path_failure_advances_retry_count_once(self):
        orch = self._make_orchestrator()
        orch.website.collect_multi_page.return_value = (
            False,
            None,
            "CAPTCHA_BLOCKED: challenge page (HTTP 200)",
        )
        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")
        assert success is False
        assert self._retry_advancing_writes(orch.raw_data_repo) == 1

    def test_fetch_path_exception_advances_retry_count_once(self):
        orch = self._make_orchestrator()
        orch.website.collect_multi_page.side_effect = RuntimeError("boom")
        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")
        assert success is False
        assert self._retry_advancing_writes(orch.raw_data_repo) == 1


class TestCrawlDelayAndEmptyRetry:
    """Throttle-sensitive hosts (Crawl-delay) get lowered concurrency + a serial
    retry when the batch comes back empty against a live homepage."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c._last_captcha_error = None
        return c

    def test_crawl_delay_lowers_concurrency(self):
        # Advertised Crawl-delay → initial concurrency 2; homepage not re-fetchable
        # here (dead) so no serial retry — isolates the delay-lowering decision.
        c = self._collector()
        c.robots_checker.get_crawl_delay.return_value = 10.0
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://x.org/a", "https://x.org/b"]))
        c._fetch_url = MagicMock(return_value=(False, None, None, "dead"))
        calls = []

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False):
            calls.append(max_concurrent)
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://x.org", "00-0000000")
        assert calls == [2]  # delay>=1 → concurrency 2; dead homepage → no retry
        assert ok is False

    def test_empty_batch_retries_serially_when_homepage_live(self):
        c = self._collector()
        c.robots_checker.get_crawl_delay.return_value = None
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://x.org/a"]))
        c._fetch_url = MagicMock(return_value=(True, "<html>ok</html>", "https://x.org", None))
        calls = []

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False):
            calls.append(max_concurrent)
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://x.org", "00-0000000")
        assert calls == [10, 1]  # default burst, then serial retry against a live homepage

    def test_empty_batch_no_retry_when_captcha(self):
        c = self._collector()
        c.robots_checker.get_crawl_delay.return_value = None
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://x.org/a"]))
        c._fetch_url = MagicMock(return_value=(True, "<html>ok</html>", "https://x.org", None))
        calls = []

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False):
            # Simulate a CAPTCHA detected during the crawl (the real signal path)
            c._last_captcha_error = "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
            calls.append(max_concurrent)
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://x.org", "00-0000000")
        assert calls == [10]  # terminal block → no serial retry
        assert ok is False
        assert "CAPTCHA" in err


class TestRateLimitNotTerminal:
    """H5 poison fix: transient 429/503 must never emit the CAPTCHA_BLOCKED
    string (which is a TERMINAL_FAILURE_MARKER -> 180d skip). They must emit
    RATE_LIMITED instead, which matches no terminal marker -> graduated
    RETRY_BACKOFF_HOURS backoff."""

    def test_rate_limited_string_is_transient(self):
        # 429/503 must NOT classify as terminal (no 180d skip)
        assert classify_failure("RATE_LIMITED: HTTP 429") is None
        assert classify_failure("RATE_LIMITED: HTTP 503") is None
        # genuine captcha stays terminal
        assert classify_failure("CAPTCHA_BLOCKED: challenge page (HTTP 200)") == "captcha_blocked"

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c.robots_checker.can_fetch.return_value = True
        c.cache = MagicMock()
        c.cache.get_cached_html.return_value = None
        # is_captcha stays True for 429/503 (curl_cffi bypass is still attempted,
        # per the brief) but it must fail here so the original RATE_LIMITED
        # error surfaces rather than a real network call.
        c._try_curl_cffi_async = self._failing_curl_cffi
        return c

    @staticmethod
    async def _failing_curl_cffi(url):
        return url, False, None, None, "curl_cffi fallback failed"

    def test_429_response_yields_rate_limited_error(self):
        c = self._collector()

        response = MagicMock()
        response.status_code = 429
        response.headers = {"cf-ray": "abc123"}  # present on ALL Cloudflare responses
        response.text = "Too Many Requests"

        client = MagicMock()

        async def fake_get(*args, **kwargs):
            return response

        client.get = fake_get

        semaphore = asyncio.Semaphore(1)

        async def run():
            return await c._fetch_url_async(client, "https://example.org", semaphore)

        url, success, html, final_url, error = asyncio.run(run())
        assert success is False
        assert error == "RATE_LIMITED: HTTP 429"
        # cf-ray header must NOT re-poison a 429 into CAPTCHA_BLOCKED
        assert "CAPTCHA_BLOCKED" not in error

    def test_503_response_yields_rate_limited_error(self):
        c = self._collector()

        response = MagicMock()
        response.status_code = 503
        response.headers = {}
        response.text = "Service Unavailable"

        client = MagicMock()

        async def fake_get(*args, **kwargs):
            return response

        client.get = fake_get

        semaphore = asyncio.Semaphore(1)

        async def run():
            return await c._fetch_url_async(client, "https://example.org", semaphore)

        url, success, html, final_url, error = asyncio.run(run())
        assert success is False
        assert error == "RATE_LIMITED: HTTP 503"


class TestGlobalFleetRateLimit:
    """Fleet-wide QPS ceiling (Task 7).

    A per-loop asyncio.Semaphore does NOT bound fleet concurrency: the
    streaming runner gives each charity its own asyncio.run() on its own
    ThreadPoolExecutor thread, so N workers each get their OWN semaphore
    instance (N workers x limit, not a shared ceiling). The only lever that
    bounds TOTAL website QPS across every worker thread is a process-wide,
    cross-thread gate -- global_rate_limiter already is one (per-domain
    threading.Lock + last-request timestamp), so _fetch_url_async must call
    it before every outbound website request.
    """

    def test_min_interval_constant_is_conservative(self):
        # ~5 req/s ceiling fleet-wide
        assert CRAWL_GLOBAL_MIN_INTERVAL_SECONDS == 0.2

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c.robots_checker.can_fetch.return_value = True
        c.cache = MagicMock()
        c.cache.get_cached_html.return_value = None
        return c

    def test_fetch_url_async_invokes_global_website_gate(self):
        c = self._collector()

        response = MagicMock()
        response.status_code = 200
        response.text = "<html>hi</html>"
        response.url = "https://example.org"

        client = MagicMock()

        async def fake_get(*args, **kwargs):
            return response

        client.get = fake_get

        semaphore = asyncio.Semaphore(1)

        async def run():
            return await c._fetch_url_async(client, "https://example.org", semaphore)

        with patch("src.collectors.web_collector.global_rate_limiter") as mock_limiter:
            mock_limiter.wait.return_value = 0.0
            url, success, html, final_url, error = asyncio.run(run())

        assert success is True
        # Called with the "website" domain key + the process-wide min interval,
        # matching how form990_grants and other collectors already use it.
        mock_limiter.wait.assert_called_once_with("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)

    def test_global_gate_still_invoked_on_non_200(self):
        """The gate must fire before the request lands, regardless of the
        response outcome -- a 429 must not have skipped past the throttle."""
        c = self._collector()

        response = MagicMock()
        response.status_code = 429
        response.headers = {}
        response.text = "Too Many Requests"

        client = MagicMock()

        async def fake_get(*args, **kwargs):
            return response

        client.get = fake_get

        c._try_curl_cffi_async = lambda url: _failing_curl_cffi(url)

        semaphore = asyncio.Semaphore(1)

        async def run():
            return await c._fetch_url_async(client, "https://example.org", semaphore)

        with patch("src.collectors.web_collector.global_rate_limiter") as mock_limiter:
            mock_limiter.wait.return_value = 0.0
            asyncio.run(run())

        mock_limiter.wait.assert_called_once_with("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)


async def _failing_curl_cffi(url):
    return url, False, None, None, "curl_cffi fallback failed"


class TestBfsEmptyRetry:
    """BFS-mode empty crawl (no sitemap) also retries serially — recovers AMF."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c._last_captcha_error = None
        return c

    def test_bfs_empty_retries_serially(self):
        c = self._collector()
        c.robots_checker.get_crawl_delay.return_value = 10.0  # AMF advertises a delay
        c._discover_urls_from_sitemap = MagicMock(return_value=(False, []))  # no sitemap → BFS
        c._fetch_url = MagicMock(return_value=(True, "<html>ok</html>", "https://amf.org", None))
        calls = []

        def fake_bfs(start_url, max_depth, max_pages, timeout_total, max_concurrent=10, force=False):
            calls.append(max_concurrent)
            return {}

        c._crawl_with_bfs_async = fake_bfs
        ok, data, err = c.collect_multi_page("https://amf.org", "00-0000000")
        assert calls == [2, 1]  # delay-lowered burst (2), then serial retry (1)


class TestForceSourcesOverride:
    """Task 2: `force_sources` bypasses BOTH `_is_data_fresh` and
    `_should_skip_failed_source` for the named sources only; every other
    source's gating is unaffected."""

    def _make_orchestrator(self):
        orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
        orch.logger = MagicMock()
        orch.skip_sources = {"propublica", "charity_navigator", "candid", "form990_grants", "bbb"}
        orch.frozen_sources = set()
        orch.blocked_sites = []
        orch._blocked_sites_lock = threading.Lock()
        orch.raw_data_repo = MagicMock()
        orch.charity_repo = MagicMock()
        orch.website = MagicMock()
        orch._get_or_create_charity = lambda ein, name=None, website=None: ein
        return orch

    @staticmethod
    def _fresh_success_row():
        return {
            "success": True,
            "scraped_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }

    @staticmethod
    def _terminal_failure_row():
        return {
            "success": False,
            "retry_count": 1,
            "last_failure_reason": "CAPTCHA_BLOCKED: challenge page (HTTP 200)",
            "scraped_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }

    def test_fresh_website_not_recrawled_without_force(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._fresh_success_row()
        orch.website.collect_multi_page.return_value = (False, None, "SIMULATED_FAILURE")

        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")

        orch.website.collect_multi_page.assert_not_called()
        assert "website" in report["sources_succeeded"]

    def test_fresh_website_recrawled_with_force(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._fresh_success_row()
        orch.website.collect_multi_page.return_value = (False, None, "SIMULATED_FAILURE")

        success, report = orch.fetch_charity_data(
            "12-3456789", website_url="https://example.org", force_sources={"website"}
        )

        orch.website.collect_multi_page.assert_called_once()

    def test_terminal_failed_website_skipped_without_force(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._terminal_failure_row()
        orch.website.collect_multi_page.return_value = (False, None, "SIMULATED_FAILURE")

        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")

        orch.website.collect_multi_page.assert_not_called()
        assert "website" in report["sources_failed"]

    def test_terminal_failed_website_recrawled_with_force(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._terminal_failure_row()
        orch.website.collect_multi_page.return_value = (False, None, "SIMULATED_FAILURE")

        success, report = orch.fetch_charity_data(
            "12-3456789", website_url="https://example.org", force_sources={"website"}
        )

        orch.website.collect_multi_page.assert_called_once()

    def test_non_website_force_bypasses_freshness_and_backoff(self):
        # Isolate propublica: skip every other source, including website, so
        # only the propublica gate under test can invoke a fetch.
        orch = self._make_orchestrator()
        orch.skip_sources = {"charity_navigator", "candid", "form990_grants", "bbb", "website"}
        orch.charity_repo.get.return_value = None
        orch.raw_data_repo.get_by_source.return_value = self._fresh_success_row()
        orch.propublica = MagicMock()
        orch.propublica.fetch.return_value = MagicMock(success=False, error="SIMULATED_FAILURE")

        success, report = orch.fetch_charity_data("12-3456789")
        orch.propublica.fetch.assert_not_called()

        success, report = orch.fetch_charity_data("12-3456789", force_sources={"propublica"})
        orch.propublica.fetch.assert_called_once()

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
        # Post poison-fix a 429 emits RATE_LIMITED (not CAPTCHA_BLOCKED); it is
        # transient, so it must not demote website to optional either.
        assert is_optional_website_failure(["RATE_LIMITED: HTTP 429"]) is False

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
        orch.crawl_attempt_repo = MagicMock()
        orch.crawled_page_repo = MagicMock()
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
        c._init_failure_latches()
        c.use_playwright = False
        c._playwright_local = threading.local()
        return c

    def test_crawl_delay_lowers_concurrency(self):
        # Advertised Crawl-delay → initial concurrency 2; homepage not re-fetchable
        # here (dead) so no serial retry — isolates the delay-lowering decision.
        c = self._collector()
        c.robots_checker.get_crawl_delay.return_value = 10.0
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://x.org/a", "https://x.org/b"]))
        c._fetch_url = MagicMock(return_value=(False, None, None, "dead"))
        calls = []

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
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

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
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

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            # Simulate a CAPTCHA detected during the crawl (the real signal path)
            c._record_fetch_error("CAPTCHA_BLOCKED: challenge page (HTTP 200)")
            calls.append(max_concurrent)
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://x.org", "00-0000000")
        assert calls == [10]  # terminal block → no serial retry
        assert ok is False
        assert "CAPTCHA" in err


class TestBotChallengeDetection:
    """_is_bot_challenge_html gates whether Playwright-rendered content gets
    accepted as real site content. Real incident: healpalestine.org's
    blocker is a ShieldSquare/Radware-style "sgcaptcha" puzzle page, not
    Cloudflare -- the check used to only recognize Cloudflare markers, so
    this real, well-formed HTML (title: "Robot Challenge Screen") was
    accepted as a successful Playwright rescue and would have been fed to
    the LLM extractor as the charity's actual website."""

    def _collector(self):
        return WebsiteCollector.__new__(WebsiteCollector)

    def test_detects_sgcaptcha_robot_challenge_screen(self):
        c = self._collector()
        html = (
            '<html><head><title>Robot Challenge Screen</title></head><body>'
            '<script>const sgchallenge="21:...";const sgsubmit_url="/.well-known/sgcaptcha/?r=%2F";</script>'
            '</body></html>'
        )
        assert c._is_bot_challenge_html(html) is True

    def test_detects_verify_you_are_human(self):
        c = self._collector()
        html = "<html><body>Please verify you are human to continue.</body></html>"
        assert c._is_bot_challenge_html(html) is True

    def test_still_detects_cloudflare_challenge(self):
        c = self._collector()
        html = '<html><body>Just a moment... Checking with Cloudflare</body></html>'
        assert c._is_bot_challenge_html(html) is True

    def test_real_content_is_not_flagged(self):
        c = self._collector()
        html = "<html><body><h1>Welcome to Our Charity</h1><p>We help people.</p></body></html>"
        assert c._is_bot_challenge_html(html) is False

    def test_empty_html_is_not_flagged(self):
        c = self._collector()
        assert c._is_bot_challenge_html("") is False
        assert c._is_bot_challenge_html(None) is False


class TestPlaywrightCaptchaRescue:
    """A site fully CAPTCHA-blocked to httpx + curl_cffi (both exhausted
    inside _fetch_url_async) gets one bounded, serial Playwright rescue
    attempt before giving up. Confirmed viable by manual testing against
    Sachse Muslim Society and Muslim Hands USA — both genuinely block the
    async clients (a Cloudflare JS challenge neither httpx nor curl_cffi's
    fingerprint impersonation can satisfy) but render cleanly under a real
    browser."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.use_llm = False
        c.max_pdf_downloads = 0
        c.robots_checker = MagicMock()
        c.robots_checker.get_crawl_delay.return_value = None
        c.cache = MagicMock()
        c._cleanup_playwright = MagicMock()
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://x.org/"]))
        c._fetch_url = MagicMock(return_value=(False, None, None, "dead"))  # no live-homepage retry
        # A single rescued page is below SITEMAP_MIN_PAGES_FOR_COVERAGE, so
        # the thin-sitemap coverage fix tries a BFS augmentation pass next —
        # a fully-blocked site fails that the same way (empty), not a crash.
        c._crawl_with_bfs_async = MagicMock(return_value={})
        c.use_playwright = True
        c._playwright_local = threading.local()
        c._init_failure_latches()
        return c

    def _captcha_crawl(self, c):
        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            c._record_fetch_error("CAPTCHA_BLOCKED: cf-ray (HTTP 403)")
            return {}

        c._crawl_specific_urls_async = fake_crawl

    def test_rescue_recovers_when_playwright_available(self):
        c = self._collector()
        self._captcha_crawl(c)

        renderer = MagicMock()
        renderer.render.return_value = "<html>real content</html>"
        c._get_playwright_renderer = MagicMock(return_value=renderer)
        c._is_bot_challenge_html = MagicMock(return_value=False)
        c._extract_page_data = MagicMock(return_value={"ein": "12-3456789", "had_data": True})

        with patch("src.collectors.web_collector.global_rate_limiter"):
            ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is True
        renderer.render.assert_called_once_with("https://x.org/")
        assert data["crawl_stats"]["pages_visited"] == 1

    def test_rescue_discovers_more_pages_from_rendered_links_when_sitemap_blocked(self):
        """Real Heal Palestine (88-2454707) shape: Cloudflare blocks the whole
        domain, so sitemap discovery (an httpx fetch) is 403'd right along
        with everything else, leaving target_urls empty. Without link
        discovery the rescue is stuck re-rendering only the homepage forever
        — this confirms it instead follows same-domain links found in the
        rendered homepage to reach more pages, up to the page cap."""
        c = self._collector()
        c._discover_urls_from_sitemap = MagicMock(return_value=(False, []))  # sitemap blocked too

        # Sitemap failure routes through the BFS crawl path, not
        # _crawl_specific_urls_async — CAPTCHA shows up there instead.
        def fake_bfs_crawl(start_url, max_depth, max_pages, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            c._record_fetch_error("CAPTCHA_BLOCKED: cf-ray (HTTP 403)")
            return {}

        c._crawl_with_bfs_async = fake_bfs_crawl

        homepage_html = (
            '<html><body>'
            '<a href="/about">About</a>'
            '<a href="/programs">Programs</a>'
            '<a href="https://external.org/other">External</a>'
            '</body></html>'
        )
        renderer = MagicMock()
        renderer.render.side_effect = [homepage_html, "<html>about page</html>", "<html>programs page</html>"]
        c._get_playwright_renderer = MagicMock(return_value=renderer)
        c._is_bot_challenge_html = MagicMock(return_value=False)
        c._extract_page_data = MagicMock(return_value={"ein": "12-3456789", "had_data": True})

        with patch("src.collectors.web_collector.global_rate_limiter"):
            ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is True
        rendered_urls = [call.args[0] for call in renderer.render.call_args_list]
        assert rendered_urls[0] == "https://x.org"
        # Same-domain links discovered from the rendered homepage got queued;
        # the external.org link must not have been followed.
        assert "https://x.org/about" in rendered_urls
        assert "https://x.org/programs" in rendered_urls
        assert not any("external.org" in u for u in rendered_urls)
        assert data["crawl_stats"]["pages_visited"] == 3

    def test_rescue_does_not_discover_links_when_sitemap_already_found_urls(self):
        """When the sitemap DID resolve (target_urls non-empty), the rescue
        must stick to that list — link-discovery is only a fallback for the
        fully-blocked-domain case, not a way to silently expand a working
        sitemap crawl."""
        c = self._collector()  # default fixture: sitemap succeeds with one URL
        self._captcha_crawl(c)

        homepage_html = '<html><body><a href="/about">About</a></body></html>'
        renderer = MagicMock()
        renderer.render.return_value = homepage_html
        c._get_playwright_renderer = MagicMock(return_value=renderer)
        c._is_bot_challenge_html = MagicMock(return_value=False)
        c._extract_page_data = MagicMock(return_value={"ein": "12-3456789", "had_data": True})

        with patch("src.collectors.web_collector.global_rate_limiter"):
            ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is True
        renderer.render.assert_called_once_with("https://x.org/")

    def test_rescue_gives_up_when_playwright_also_challenged(self):
        c = self._collector()
        self._captcha_crawl(c)

        renderer = MagicMock()
        renderer.render.return_value = "<html>still a challenge</html>"
        c._get_playwright_renderer = MagicMock(return_value=renderer)
        c._is_bot_challenge_html = MagicMock(return_value=True)  # rendered page is STILL a challenge

        with patch("src.collectors.web_collector.global_rate_limiter"):
            ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is False
        assert "CAPTCHA_BLOCKED" in err

    def test_rescue_skipped_when_playwright_unavailable(self):
        c = self._collector()
        c.use_playwright = False  # exercises the real _get_playwright_renderer guard
        self._captcha_crawl(c)

        with patch("src.collectors.web_collector.global_rate_limiter"):
            ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is False
        assert "CAPTCHA_BLOCKED" in err

    def test_rescue_not_attempted_for_non_captcha_empty_crawl(self):
        # Dead site, no captcha signal at all — must not spin up Playwright.
        c = self._collector()

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            return {}

        c._crawl_specific_urls_async = fake_crawl
        c._get_playwright_renderer = MagicMock()

        ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is False
        c._get_playwright_renderer.assert_not_called()

    def test_rescue_attempted_when_live_homepage_times_out_without_captcha(self):
        # Muslim Hands USA in practice: no CAPTCHA_BLOCKED signal at all,
        # just an async crawl that hangs until timeout against a confirmed-
        # live homepage (both the initial batch and the serial retry come
        # back empty). Must still trigger the rescue.
        c = self._collector()
        c._fetch_url = MagicMock(return_value=(True, "<html>homepage</html>", "https://x.org", None))

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            return {}  # empty on both the initial pass and the serial retry

        c._crawl_specific_urls_async = fake_crawl

        renderer = MagicMock()
        renderer.render.return_value = "<html>real content</html>"
        c._get_playwright_renderer = MagicMock(return_value=renderer)
        c._is_bot_challenge_html = MagicMock(return_value=False)
        c._extract_page_data = MagicMock(return_value={"ein": "12-3456789", "had_data": True})

        with patch("src.collectors.web_collector.global_rate_limiter"):
            ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is True
        assert c._captcha_error() is None  # confirms this is the non-captcha trigger path
        renderer.render.assert_called_once_with("https://x.org/")


class TestPlaywrightRendererThreadLocal:
    """The orchestrator holds ONE WebsiteCollector shared across all worker
    threads (src/collectors/orchestrator.py: self.website), but Playwright's
    sync API is thread-affine — a renderer created on thread A crashes with
    'Cannot switch to a different thread' if thread B ever touches it. This
    broke a real fleet run (Sachse + Muslim Hands USA crawled concurrently,
    one succeeded, the other hit the greenlet crash) before the fix.
    _get_playwright_renderer must hand each thread its own instance."""

    def test_each_thread_gets_its_own_renderer(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.use_playwright = True
        c._playwright_local = threading.local()
        renderers = {}

        with patch("src.utils.playwright_renderer.PlaywrightRenderer", side_effect=lambda **kw: MagicMock()):
            for name in ("a", "b"):
                t = threading.Thread(target=lambda n=name: renderers.__setitem__(n, c._get_playwright_renderer()))
                t.start()
                t.join()  # sequential on purpose — isolation doesn't require a real race to prove

        assert renderers["a"] is not None
        assert renderers["b"] is not None
        assert renderers["a"] is not renderers["b"]

    def test_same_thread_reuses_its_renderer(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.use_playwright = True
        c._playwright_local = threading.local()
        calls = []

        def worker():
            calls.append(c._get_playwright_renderer())
            calls.append(c._get_playwright_renderer())

        with patch("src.utils.playwright_renderer.PlaywrightRenderer", side_effect=lambda **kw: MagicMock()):
            t = threading.Thread(target=worker)
            t.start()
            t.join()

        assert calls[0] is calls[1]

    def test_cleanup_only_closes_calling_threads_renderer(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.use_playwright = True
        c._playwright_local = threading.local()
        thread_a_renderer = {}

        with patch("src.utils.playwright_renderer.PlaywrightRenderer", side_effect=lambda **kw: MagicMock()):
            t_a = threading.Thread(target=lambda: thread_a_renderer.__setitem__("r", c._get_playwright_renderer()))
            t_a.start()
            t_a.join()

            # Different thread cleans up — must not touch thread A's renderer.
            t_b = threading.Thread(target=c._cleanup_playwright)
            t_b.start()
            t_b.join()

        thread_a_renderer["r"].close.assert_not_called()


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


class TestRateLimitSurfacedInCollectMultiPage:
    """Blocker 2B: a transient rate-limit run must surface RATE_LIMITED
    instead of masquerading as the generic 'No data found on any pages'
    failure, so the orchestrator can tell it apart from a genuinely empty
    site and preserve last-good content instead of demoting it."""

    def test_rate_limit_capture_in_bfs_loop(self):
        # Exercises the real capture site (web_collector.py ~1689) rather
        # than faking the attribute directly.
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c._init_failure_latches()
        c.cache = MagicMock()
        c._is_priority_url = lambda u: False
        c._normalize_url = lambda u: u

        async def fake_crawl_urls_async(url_list, max_concurrent, timeout_total, force, crawl_delay):
            return {u: (False, None, None, "RATE_LIMITED: HTTP 429") for u in url_list}

        c._crawl_urls_async = fake_crawl_urls_async
        results = asyncio.run(c._crawl_bfs_async("https://x.org", max_depth=1, max_pages=5, timeout_total=30))

        assert results == {}
        assert c._rate_limit_error() == "RATE_LIMITED: HTTP 429"
        assert c._captcha_error() is None

    def test_rate_limit_capture_in_sitemap_loop(self):
        # Same signal, but exercised through the REAL _crawl_specific_urls_async
        # (the structurally-preferred sitemap path), not a full mock of it --
        # a fully-mocked _crawl_specific_urls_async gives false confidence
        # this path is covered.
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c._init_failure_latches()

        async def fake_crawl_urls_async(url_list, max_concurrent, timeout_total, force, crawl_delay):
            return {u: (False, None, None, "RATE_LIMITED: HTTP 429") for u in url_list}

        c._crawl_urls_async = fake_crawl_urls_async
        results = c._crawl_specific_urls_async(["https://x.org/a"], timeout_total=30)

        assert results == {}
        assert c._rate_limit_error() == "RATE_LIMITED: HTTP 429"
        assert c._captcha_error() is None

    def test_captcha_capture_in_sitemap_loop(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c._init_failure_latches()

        async def fake_crawl_urls_async(url_list, max_concurrent, timeout_total, force, crawl_delay):
            return {u: (False, None, None, "CAPTCHA_BLOCKED: challenge page (HTTP 200)") for u in url_list}

        c._crawl_urls_async = fake_crawl_urls_async
        results = c._crawl_specific_urls_async(["https://x.org/a"], timeout_total=30)

        assert results == {}
        assert c._captcha_error() == "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
        assert c._rate_limit_error() is None

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c.robots_checker.get_crawl_delay.return_value = None
        c._init_failure_latches()
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://x.org/a"]))
        c._fetch_url = MagicMock(return_value=(False, None, None, "dead"))  # no live-homepage retry
        c.use_playwright = False
        c._playwright_local = threading.local()
        return c

    def test_rate_limited_no_data_surfaces_rate_limited_error(self):
        c = self._collector()

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            c._record_fetch_error("RATE_LIMITED: HTTP 429")
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://x.org", "00-0000000")
        assert ok is False
        assert err == "RATE_LIMITED: HTTP 429"

    def test_captcha_still_takes_precedence_over_rate_limit(self):
        c = self._collector()

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            c._record_fetch_error("CAPTCHA_BLOCKED: challenge page (HTTP 200)")
            c._record_fetch_error("RATE_LIMITED: HTTP 429")
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://x.org", "00-0000000")
        assert ok is False
        assert "CAPTCHA_BLOCKED" in err

    def test_generic_message_when_neither_signal_present(self):
        c = self._collector()

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://x.org", "00-0000000")
        assert ok is False
        assert err == "No data found on any pages"


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

    def test_curl_cffi_fetch_invokes_global_website_gate(self):
        """The curl_cffi fallback issues its own outbound GET; it must pass
        through the same process-wide gate. This is the worst place to skip
        the throttle -- the fallback fires EXACTLY when a domain already
        returned 429/503. The gate lives at the top of the sync
        _curl_cffi_fetch (already on a worker thread), so it must fire before
        the curl request regardless of the response outcome."""
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.timeout = 10
        c.cache = MagicMock()

        curl_response = MagicMock()
        curl_response.status_code = 503  # fail: no cache write, no 200 handling

        with patch("src.collectors.web_collector.curl_requests") as mock_curl, patch(
            "src.collectors.web_collector.global_rate_limiter"
        ) as mock_limiter:
            mock_curl.get.return_value = curl_response
            mock_limiter.wait.return_value = 0.0
            c._curl_cffi_fetch("https://example.org", "chrome120")

        mock_limiter.wait.assert_called_once_with("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)

    def test_curl_fallback_path_is_gated_end_to_end(self):
        """Drive a real 429 -> curl_cffi fallback and prove the fallback GETs
        route through the gate too (not just the primary httpx GET). Counting
        the calls is what distinguishes this from
        test_global_gate_still_invoked_on_non_200 (which stubs the fallback):
        if the curl path were ungated, wait() would be called exactly once
        (primary only) and this assertion would fail."""
        c = self._collector()
        c.cloudflare_domains = {}  # no known profile -> multi-profile loop runs

        response = MagicMock()
        response.status_code = 429
        response.headers = {}
        response.text = "Too Many Requests"

        client = MagicMock()

        async def fake_get(*args, **kwargs):
            return response

        client.get = fake_get

        curl_response = MagicMock()
        curl_response.status_code = 503  # every profile fails

        semaphore = asyncio.Semaphore(1)

        async def run():
            return await c._fetch_url_async(client, "https://example.org", semaphore)

        with patch("src.collectors.web_collector.curl_requests") as mock_curl, patch(
            "src.collectors.web_collector.global_rate_limiter"
        ) as mock_limiter:
            mock_curl.get.return_value = curl_response
            mock_limiter.wait.return_value = 0.0
            url, success, html, final_url, error = asyncio.run(run())

        # primary GET + at least one curl_cffi profile attempt, all gated
        assert mock_limiter.wait.call_count >= 2
        for call in mock_limiter.wait.call_args_list:
            assert call.args == ("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)

    def test_score_content_async_invokes_global_website_gate(self):
        """The content-scoring fetch path (_score_content_async) opens its own
        httpx client and issues a second class of outbound website request. It
        must pass through the same gate."""
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.headers = {}
        c.cache = MagicMock()
        c.cache.get_cached_html.return_value = None  # force the network path
        c.page_classifier = MagicMock()
        c.page_classifier.apply_content_boost.side_effect = lambda ps, html: ps

        page_score = MagicMock()
        page_score.url = "https://example.org"

        response = MagicMock()
        response.status_code = 200
        response.text = "<html>hi</html>"
        response.url = "https://example.org"

        with patch(
            "src.collectors.web_collector.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response),
        ), patch("src.collectors.web_collector.global_rate_limiter") as mock_limiter:
            mock_limiter.wait.return_value = 0.0
            asyncio.run(c._score_content_async([page_score], timeout_total=5))

        mock_limiter.wait.assert_called_once_with("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)


class TestPerHostCrawlDelayGate:
    """Task 8: an advertised robots.txt Crawl-delay must be enforced as a REAL
    per-host inter-request delay, not just used to lower concurrency (the old
    `polite_concurrency` toggle was a no-op against the delay itself — the
    inner Semaphore(2) let requests through immediately). The delay is
    enforced via the SAME global_rate_limiter used for the fleet-wide
    "website" gate, keyed by the host domain instead of "website" — so a
    request effectively waits for max(global interval, host crawl_delay)."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c.robots_checker.can_fetch.return_value = True
        c.cache = MagicMock()
        c.cache.get_cached_html.return_value = None
        return c

    def test_fetch_url_async_invokes_per_host_gate_when_crawl_delay_set(self):
        c = self._collector()

        response = MagicMock()
        response.status_code = 200
        response.text = "<html>hi</html>"
        response.url = "https://slow.org/page"

        client = MagicMock()

        async def fake_get(*args, **kwargs):
            return response

        client.get = fake_get

        semaphore = asyncio.Semaphore(1)

        async def run():
            return await c._fetch_url_async(
                client, "https://slow.org/page", semaphore, crawl_delay=10.0
            )

        with patch("src.collectors.web_collector.global_rate_limiter") as mock_limiter:
            mock_limiter.wait.return_value = 0.0
            asyncio.run(run())

        # Both gates fire: the process-wide "website" QPS gate AND a distinct
        # per-host gate keyed by the domain, using the advertised delay.
        mock_limiter.wait.assert_any_call("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)
        mock_limiter.wait.assert_any_call("slow.org", 10.0)
        assert mock_limiter.wait.call_count == 2

    def test_fetch_url_async_skips_per_host_gate_when_no_crawl_delay(self):
        # No crawl_delay passed (default 0.0) -> only the global gate fires;
        # a host with no advertised Crawl-delay must not get an extra wait.
        c = self._collector()

        response = MagicMock()
        response.status_code = 200
        response.text = "<html>hi</html>"
        response.url = "https://example.org/page"

        client = MagicMock()

        async def fake_get(*args, **kwargs):
            return response

        client.get = fake_get

        semaphore = asyncio.Semaphore(1)

        async def run():
            return await c._fetch_url_async(client, "https://example.org/page", semaphore)

        with patch("src.collectors.web_collector.global_rate_limiter") as mock_limiter:
            mock_limiter.wait.return_value = 0.0
            asyncio.run(run())

        mock_limiter.wait.assert_called_once_with("website", CRAWL_GLOBAL_MIN_INTERVAL_SECONDS)

    def test_collect_multi_page_threads_crawl_delay_to_crawl_specific_urls(self):
        """The advertised Crawl-delay from robots.txt must reach the async
        crawler call (which forwards it to _fetch_url_async), not just gate
        concurrency via polite_concurrency."""
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c._init_failure_latches()
        c.robots_checker.get_crawl_delay.return_value = 10.0
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://slow.org/a"]))
        c._fetch_url = MagicMock(return_value=(False, None, None, "dead"))
        received = {}

        def fake_crawl(urls, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0):
            received["crawl_delay"] = crawl_delay
            return {}

        c._crawl_specific_urls_async = fake_crawl
        ok, data, err = c.collect_multi_page("https://slow.org", "00-0000000")
        assert received["crawl_delay"] == 10.0
        assert ok is False


class _FakeAsyncClient:
    """Minimal async-context-manager stand-in for httpx.AsyncClient whose
    .get() returns a canned response without touching the network."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *args, **kwargs):
        return self._response


async def _failing_curl_cffi(url):
    return url, False, None, None, "curl_cffi fallback failed"


class TestBfsEmptyRetry:
    """BFS-mode empty crawl (no sitemap) also retries serially — recovers AMF."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.robots_checker = MagicMock()
        c._init_failure_latches()
        c.use_playwright = False
        c._playwright_local = threading.local()
        return c

    def test_bfs_empty_retries_serially(self):
        c = self._collector()
        c.robots_checker.get_crawl_delay.return_value = 10.0  # AMF advertises a delay
        c._discover_urls_from_sitemap = MagicMock(return_value=(False, []))  # no sitemap → BFS
        c._fetch_url = MagicMock(return_value=(True, "<html>ok</html>", "https://amf.org", None))
        calls = []

        def fake_bfs(
            start_url, max_depth, max_pages, timeout_total, max_concurrent=10, force=False, crawl_delay=0.0
        ):
            calls.append(max_concurrent)
            return {}

        c._crawl_with_bfs_async = fake_bfs
        ok, data, err = c.collect_multi_page("https://amf.org", "00-0000000")
        assert calls == [2, 1]  # delay-lowered burst (2), then serial retry (1)


class TestBfsFallbackForThinSitemap:
    """A sitemap that only lists a homepage + dead links (KinderUSA:
    75-2999028) rides the crawl entirely on the homepage. Coverage fix:
    a sitemap-mode crawl yielding fewer than SITEMAP_MIN_PAGES_FOR_COVERAGE
    content pages gets augmented with a BFS pass from the homepage,
    merged in (sitemap pages retained, new BFS pages added)."""

    def _collector(self):
        c = WebsiteCollector.__new__(WebsiteCollector)
        c.logger = None
        c.use_llm = False
        c.max_pdf_downloads = 0
        c.robots_checker = MagicMock()
        c.robots_checker.get_crawl_delay.return_value = None
        c._init_failure_latches()
        c.cache = MagicMock()
        c._cleanup_playwright = MagicMock()
        c._fetch_url = MagicMock(return_value=(True, "<html>homepage</html>", "https://x.org", None))
        c._rate_limit = MagicMock()
        return c

    def test_thin_sitemap_augments_with_bfs(self):
        c = self._collector()
        c._discover_urls_from_sitemap = MagicMock(return_value=(True, ["https://x.org/", "https://x.org/cart"]))
        c._crawl_specific_urls_async = MagicMock(return_value={"https://x.org/": {"ein": "12-3456789", "had_data": True}})
        c._crawl_with_bfs_async = MagicMock(
            return_value={
                "https://x.org/about": {"mission": "Serving the community", "had_data": True},
                "https://x.org/donate": {"donate_url": "https://x.org/donate", "had_data": True},
            }
        )

        ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is True
        c._crawl_with_bfs_async.assert_called_once()
        # Sitemap page retained + both BFS-discovered pages added.
        assert data["crawl_stats"]["pages_visited"] == 3

    def test_rich_sitemap_does_not_augment(self):
        c = self._collector()
        c._discover_urls_from_sitemap = MagicMock(
            return_value=(True, ["https://x.org/a", "https://x.org/b", "https://x.org/c"])
        )
        c._crawl_specific_urls_async = MagicMock(
            return_value={
                "https://x.org/a": {"ein": "12-3456789", "had_data": True},
                "https://x.org/b": {"mission": "Serving the community", "had_data": True},
                "https://x.org/c": {"donate_url": "https://x.org/donate", "had_data": True},
            }
        )
        c._crawl_with_bfs_async = MagicMock(return_value={})

        ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is True
        assert c._crawl_with_bfs_async.call_count == 0
        assert data["crawl_stats"]["pages_visited"] == 3

    def test_no_sitemap_path_unchanged(self):
        # Sitemap discovery fails entirely -> BFS is the primary crawl, not
        # an augmentation -- it must run exactly once, never twice.
        c = self._collector()
        c._discover_urls_from_sitemap = MagicMock(return_value=(False, []))
        c._crawl_with_bfs_async = MagicMock(
            return_value={"https://x.org/": {"ein": "12-3456789", "had_data": True}}
        )

        ok, data, err = c.collect_multi_page("https://x.org", "12-3456789")

        assert ok is True
        assert c._crawl_with_bfs_async.call_count == 1


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
        orch.crawl_attempt_repo = MagicMock()
        orch.crawled_page_repo = MagicMock()
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


class TestTransientPreservesLastGoodWebsite:
    """Blocker 2B: a transient (RATE_LIMITED) re-crawl failure of a source
    that already has good content must be preserved via record_soft_fail,
    not demoted to success=False -- that flip excludes the still-valid
    last-good content from synthesize and cascades into a degraded live
    export within the same streaming_runner session. Terminal failures and
    first-time failures (no prior good row) keep today's demotion path."""

    def _make_orchestrator(self):
        orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
        orch.logger = MagicMock()
        orch.skip_sources = {"propublica", "charity_navigator", "candid", "form990_grants", "bbb"}
        orch.frozen_sources = set()
        orch.blocked_sites = []
        orch._blocked_sites_lock = threading.Lock()
        orch.raw_data_repo = MagicMock()
        orch.crawl_attempt_repo = MagicMock()
        orch.crawled_page_repo = MagicMock()
        orch.charity_repo = MagicMock()
        orch.website = MagicMock()
        orch._get_or_create_charity = lambda ein, name=None, website=None: ein
        return orch

    @staticmethod
    def _prior_good_row():
        return {
            "success": True,
            "scraped_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }

    def test_rate_limited_recrawl_of_good_source_preserves_via_soft_fail(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._prior_good_row()
        orch.website.collect_multi_page.return_value = (False, None, "RATE_LIMITED: HTTP 429")

        success, report = orch.fetch_charity_data(
            "12-3456789", website_url="https://example.org", force_sources={"website"}
        )

        orch.raw_data_repo.record_soft_fail.assert_called_once()
        args = orch.raw_data_repo.record_soft_fail.call_args.args
        assert args[0] == "12-3456789"
        assert args[1] == "website"
        # No demotion write: _store_failed_crawl (upsert(success=False)) must
        # not fire for the preserved source.
        assert not any(c.kwargs.get("success") is False for c in orch.raw_data_repo.upsert.call_args_list)
        assert "website" in report["sources_succeeded"]
        assert report.get("sources_soft_failed") == ["website (transient; last-good preserved)"]

    def test_rate_limited_recrawl_with_no_prior_good_row_still_demotes(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = None  # no prior row at all
        orch.website.collect_multi_page.return_value = (False, None, "RATE_LIMITED: HTTP 429")

        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")

        orch.raw_data_repo.record_soft_fail.assert_not_called()
        assert "website" in report["sources_failed"]
        assert "website" not in report["sources_succeeded"]
        assert any(c.kwargs.get("success") is False for c in orch.raw_data_repo.upsert.call_args_list)

    def test_terminal_captcha_recrawl_of_good_source_still_demotes(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._prior_good_row()
        orch.website.collect_multi_page.return_value = (
            False,
            None,
            "CAPTCHA_BLOCKED: challenge page (HTTP 200)",
        )

        success, report = orch.fetch_charity_data(
            "12-3456789", website_url="https://example.org", force_sources={"website"}
        )

        orch.raw_data_repo.record_soft_fail.assert_not_called()
        assert any(c.kwargs.get("success") is False for c in orch.raw_data_repo.upsert.call_args_list)
        assert "website" not in report["sources_succeeded"]

    def test_timeout_recrawl_of_good_source_preserves_via_soft_fail(self):
        # Non-RATE_LIMITED transient failure (network timeout) on a prior-good
        # row must ALSO preserve -- 2B named "a 429, OR a network error", and
        # classify_failure("Timeout") is None (not a terminal marker).
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._prior_good_row()
        orch.website.collect_multi_page.return_value = (False, None, "Timeout")

        success, report = orch.fetch_charity_data(
            "12-3456789", website_url="https://example.org", force_sources={"website"}
        )

        orch.raw_data_repo.record_soft_fail.assert_called_once()
        assert not any(c.kwargs.get("success") is False for c in orch.raw_data_repo.upsert.call_args_list)
        assert "website" in report["sources_succeeded"]
        assert report.get("sources_soft_failed") == ["website (transient; last-good preserved)"]

    def test_generic_no_data_recrawl_of_good_source_preserves_via_soft_fail(self):
        # "No data found on any pages" is also non-terminal.
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = self._prior_good_row()
        orch.website.collect_multi_page.return_value = (False, None, "No data found on any pages")

        success, report = orch.fetch_charity_data(
            "12-3456789", website_url="https://example.org", force_sources={"website"}
        )

        orch.raw_data_repo.record_soft_fail.assert_called_once()
        assert not any(c.kwargs.get("success") is False for c in orch.raw_data_repo.upsert.call_args_list)
        assert "website" in report["sources_succeeded"]

    def test_timeout_with_no_prior_good_row_still_demotes(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = None  # no prior row at all
        orch.website.collect_multi_page.return_value = (False, None, "Timeout")

        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")

        orch.raw_data_repo.record_soft_fail.assert_not_called()
        assert "website" in report["sources_failed"]
        assert "website" not in report["sources_succeeded"]
        assert any(c.kwargs.get("success") is False for c in orch.raw_data_repo.upsert.call_args_list)

    def test_generic_no_data_with_no_prior_good_row_still_demotes(self):
        orch = self._make_orchestrator()
        orch.raw_data_repo.get_by_source.return_value = None  # no prior row at all
        orch.website.collect_multi_page.return_value = (False, None, "No data found on any pages")

        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")

        orch.raw_data_repo.record_soft_fail.assert_not_called()
        assert "website" in report["sources_failed"]
        assert "website" not in report["sources_succeeded"]
        assert any(c.kwargs.get("success") is False for c in orch.raw_data_repo.upsert.call_args_list)


class TestFailureBackoffUsesAttemptClock:
    """scraped_at is frozen by the preservation path, so it cannot drive backoff."""

    def _orch(self, row):
        orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
        orch.raw_data_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = row
        orch.logger = MagicMock()
        return orch

    def test_recent_attempt_is_backed_off_even_when_scraped_at_is_ancient(self):
        row = {
            "source": "website", "success": 0, "retry_count": 1,
            "last_failure_reason": "RATE_LIMITED: HTTP 429",
            "scraped_at": datetime.now() - timedelta(days=45),   # frozen by preservation
            "last_attempt_at": datetime.now() - timedelta(minutes=5),
        }
        skip, reason = self._orch(row)._should_skip_failed_source("12-3456789", "website")
        assert skip is True and "backoff" in reason.lower()

    def test_terminal_block_measures_from_last_attempt_not_last_success(self):
        row = {
            "source": "website", "success": 0, "retry_count": 3,
            "last_failure_reason": "CAPTCHA_BLOCKED: challenge page (HTTP 200)",
            "scraped_at": datetime.now() - timedelta(days=200),  # last SUCCESS, long ago
            "last_attempt_at": datetime.now() - timedelta(days=2),
        }
        skip, reason = self._orch(row)._should_skip_failed_source("12-3456789", "website")
        assert skip is True, "a site captcha-blocked 2 days ago must not be re-hammered"

    def test_null_last_attempt_at_falls_back_to_scraped_at(self):
        """Pre-migration rows have last_attempt_at NULL — one re-crawl, then backed off."""
        row = {
            "source": "website", "success": 0, "retry_count": 1,
            "last_failure_reason": "RATE_LIMITED: HTTP 429",
            "scraped_at": datetime.now() - timedelta(minutes=5),
            "last_attempt_at": None,
        }
        skip, _ = self._orch(row)._should_skip_failed_source("12-3456789", "website")
        assert skip is True


class TestCaptchaLatchIsThreadLocal:
    def test_one_threads_captcha_does_not_leak_into_another(self):
        """Shared latch let charity B inherit A's CAPTCHA -> 180d terminal block."""
        collector = WebsiteCollector.__new__(WebsiteCollector)
        collector._init_failure_latches()

        seen = {}
        barrier = threading.Barrier(2)

        def worker_a():
            collector._reset_failure_latches()
            collector._record_fetch_error("CAPTCHA_BLOCKED: challenge page (HTTP 200)")
            barrier.wait()
            seen["a"] = collector._captcha_error()

        def worker_b():
            collector._reset_failure_latches()
            barrier.wait()
            seen["b"] = collector._captcha_error()

        ta, tb = threading.Thread(target=worker_a), threading.Thread(target=worker_b)
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        assert seen["a"] == "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
        assert seen["b"] is None, "B must not inherit A's captcha"

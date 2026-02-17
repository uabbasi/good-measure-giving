"""
Website collector - LLM-assisted extraction from charity websites.

This is a simplified collector that fetches website content and uses
LLM to extract structured information.

Now includes multi-page crawling to find EIN and other critical data
on secondary pages (about, contact, donate, etc.).
"""

import asyncio
import json
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
import requests
from bs4 import BeautifulSoup

from .base import BaseCollector, FetchResult, ParseResult

try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

from ..extractors.deterministic import DeterministicExtractor
from ..extractors.page_classifier import PageClassifier
from ..extractors.structured_data import StructuredDataExtractor
from ..llm.website_extractor import WebsiteExtractor
from ..parsers.annual_report_parser import AnnualReportParser
from ..parsers.form_990_parser import Form990Parser
from ..parsers.sitemap_parser import SitemapParser
from ..utils.crawler_cache import CrawlerCache
from ..utils.logger import PipelineLogger
from ..utils.merge_strategy import MergeStrategy
from ..utils.pdf_downloader import PDFDownloader
from ..utils.rate_limiter import global_rate_limiter
from ..utils.robots_checker import RobotsChecker
from ..utils.text_cleaner import TextCleaner
from ..validators.website_validator import WebsiteProfile


def _normalize_ein(ein: str) -> str:
    """Strip an EIN to its 9-digit core for comparison."""
    return ein.replace("-", "").replace(" ", "").strip()


# Crawler configuration - per spec: 50 pages max, 5 min timeout
CRAWLER_CONFIG = {
    "max_depth": 3,  # Deeper crawl to find evidence/impact pages
    "max_pages": 50,  # Per spec: max 50 pages per charity
    "timeout_total": 90,  # Reduced from 300s - 90s is enough for 50 pages
    "delay_between_requests": 0.5,  # Aggressive rate limit (50 pages = 25s max)
}

# Priority URL patterns aligned with V2 dimensions (check these first)
# Ordered by V2 dimension importance for data extraction
PRIORITY_PATTERNS = [
    # TRUST dimension - verification, transparency, governance
    r"/financials",
    r"/annual-report",
    r"/990",
    r"/form-990",
    r"/audit",
    r"/transparency",
    r"/accountability",
    r"/governance",
    r"/board",
    r"/leadership",
    # EVIDENCE dimension - outcomes, research, theory of change
    r"/impact",
    r"/results",
    r"/outcomes",
    r"/evaluation",
    r"/research",
    r"/evidence",
    r"/theory-of-change",
    r"/logic-model",
    r"/metrics",
    r"/reports",
    r"/annual-review",
    # EFFECTIVENESS dimension - programs, costs, efficiency
    r"/programs",
    r"/what-we-do",
    r"/our-work",
    r"/projects",
    r"/initiatives",
    r"/services",
    r"/cost",
    r"/efficiency",
    r"/where.*money",
    # FIT dimension - mission, beneficiaries, Islamic alignment
    r"/about",
    r"/mission",
    r"/who-we-are",
    r"/our-mission",
    r"/who-we-serve",
    r"/communities",
    r"/beneficiaries",
    r"/zakat",
    r"/sadaqah",
    r"/islamic",
    r"/shariah",
    r"/fiqh",
    # Donation mechanics (for zakat claim detection)
    r"/donate",
    r"/give",
    r"/giving",
    r"/stocks",
    r"/securities",
    r"/matching",
    r"/ways-to-give",
]

# URL patterns to skip (crawler traps)
SKIP_PATTERNS = [
    r"/calendar/",
    r"/events/\d{4}/",
    r"/blog/page/\d+",
    r"/page/\d+",
    r"/archive/",
    r"/\d{4}/\d{2}/",  # Date archives
    r"\?.*page=",
    r"/search",
    r"/tag/",
    r"/category/",
    r"/wp-admin/",
    r"/login",
]


class WebsiteCollector(BaseCollector):
    """
    Collect data from charity websites using simple scraping.

    Implements BaseCollector interface with fetch/parse split:
    - fetch(ein, url=...) -> FetchResult with raw HTML
    - parse(raw_data, ein, url=...) -> ParseResult with WebsiteProfile

    Primary entry point for full crawls is collect_multi_page(url, ein).

    Note: For v0.1, this is a basic implementation. Future versions may add:
    - JavaScript rendering
    - Multi-page crawling
    - More sophisticated LLM extraction
    """

    def __init__(
        self,
        logger: Optional[PipelineLogger] = None,
        rate_limit_delay: float = 2.0,
        timeout: int = 30,
        use_llm: bool = True,
        llm_provider: str = "gemini",
        llm_api_key: Optional[str] = None,
        max_pdf_downloads: int = 5,
        use_playwright: bool = True,
        content_scoring: bool = True,  # Fetch pages to check for zakat keywords
    ):
        """
        Initialize website collector.

        Args:
            logger: Logger instance
            rate_limit_delay: Seconds between requests (default 2.0)
            timeout: Request timeout
            use_llm: Use LLM for enhanced extraction (default True)
            llm_provider: LLM provider - "gemini" (cheapest), "claude", "openai" (default "gemini")
            llm_api_key: API key for LLM (if None, uses env vars)
            max_pdf_downloads: Max PDFs to download per site (0 = disabled, default 5)
            use_playwright: Use Playwright for JS-heavy pages (default True)
        """
        self.logger = logger
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time = 0
        self.use_llm = use_llm
        self.max_pdf_downloads = max_pdf_downloads
        self.content_scoring = content_scoring  # Fetch pages to check for zakat keywords

        # Track which domains require curl_cffi and which profile works
        # Will be populated from cache after cache is initialized
        self.cloudflare_domains: Dict[str, str] = {}  # domain -> profile
        self._cloudflare_lock = threading.Lock()  # Thread safety for cloudflare_domains

        # Track captcha/anti-bot errors for reporting
        self._last_captcha_error: Optional[str] = None

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Initialize smart extractors (004-smart-crawler)
        self.structured_extractor = StructuredDataExtractor()
        self.deterministic_extractor = DeterministicExtractor()
        self.text_cleaner = TextCleaner()
        self.merge_strategy = MergeStrategy()
        self.sitemap_parser = SitemapParser()
        self.page_classifier = PageClassifier()

        # Initialize PDF downloader (T074)
        from pathlib import Path

        pdf_storage = Path(__file__).parent.parent.parent.parent / "shared" / "pdfs"
        self.pdf_downloader = PDFDownloader(storage_dir=pdf_storage, logger=logger)

        # Initialize crawler cache for aggressive caching and state tracking.
        # FIX #21: Align with SOURCE_TTL_DAYS["website"] (30 days) so re-fetch
        # after orchestrator's TTL expiry actually returns fresh content.
        from ..constants import SOURCE_TTL_DAYS

        cache_storage = Path(__file__).parent.parent.parent.parent / "shared" / "crawler_cache"
        self.cache = CrawlerCache(
            cache_dir=cache_storage,
            ttl_days=SOURCE_TTL_DAYS.get("website", 30),
            logger=logger,
        )

        # Load persisted cloudflare profiles from previous runs
        self.cloudflare_domains = self.cache.get_all_cloudflare_profiles()
        if self.cloudflare_domains and logger:
            logger.debug(f"Loaded {len(self.cloudflare_domains)} persisted cloudflare profiles")

        # Initialize Form 990 parser for PDF extraction
        self.form_990_parser = Form990Parser(logger=logger)

        # Initialize annual report parser for LLM-based extraction
        self.annual_report_parser = AnnualReportParser(logger=logger)

        # Initialize robots.txt checker (T082)
        self.robots_checker = RobotsChecker(user_agent="GoodMeasureGivingBot/1.0", logger=logger)

        # Initialize LLM extractor if enabled
        self.llm_extractor = None
        if use_llm:
            try:
                self.llm_extractor = WebsiteExtractor(provider=llm_provider, api_key=llm_api_key, logger=logger)
                if logger:
                    logger.debug(f"LLM extraction enabled: {llm_provider}")
            except Exception as e:
                if logger:
                    logger.warning(f"Failed to initialize LLM extractor: {e}. Falling back to regex extraction.")
                self.use_llm = False

        # Initialize Playwright renderer for JS-heavy pages (lazy init on first use)
        self.use_playwright = use_playwright
        self._playwright_renderer = None

    def _get_playwright_renderer(self):
        """Get or create the Playwright renderer (lazy initialization)."""
        if not self.use_playwright:
            return None

        if self._playwright_renderer is None:
            try:
                from src.utils.playwright_renderer import PlaywrightRenderer

                self._playwright_renderer = PlaywrightRenderer(timeout_ms=15000)
                if self.logger:
                    self.logger.info("Playwright renderer initialized for JS fallback")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to initialize Playwright: {e}")
                self.use_playwright = False
                return None

        return self._playwright_renderer

    def _cleanup_playwright(self):
        """Cleanup Playwright resources."""
        if self._playwright_renderer:
            self._playwright_renderer.close()
            self._playwright_renderer = None

    def __enter__(self):
        """Context manager support for automatic cleanup."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup Playwright on exit."""
        self._cleanup_playwright()
        return False

    def __del__(self):
        """Ensure Playwright cleanup on garbage collection."""
        try:
            self._cleanup_playwright()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────────
    # BaseCollector interface
    # ─────────────────────────────────────────────────────────────────────────────

    @property
    def source_name(self) -> str:
        """Canonical source name."""
        return "website"

    @property
    def schema_key(self) -> str:
        """Key for parsed_json wrapper."""
        return "website_profile"

    def fetch(self, ein: str, **kwargs) -> FetchResult:
        """
        Fetch raw HTML from charity website (single page only).

        For multi-page crawling, use collect_multi_page() instead.

        Args:
            ein: Charity EIN (for metadata, may be empty string)
            url: Website URL (required in kwargs)

        Returns:
            FetchResult with raw HTML including metadata header
        """
        url = kwargs.get("url")
        if not url:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error="URL required for website fetch (pass url=... in kwargs)",
            )

        if self.logger:
            self.logger.debug(f"Fetching website: {url}")

        self._rate_limit()

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)

            if response.status_code != 200:
                return FetchResult(
                    success=False, raw_data=None, content_type="html", error=f"HTTP {response.status_code}"
                )

            # Include metadata in HTML comment for parse() to extract
            metadata = {"url": url, "ein": ein}
            raw_with_metadata = f"<!-- WEBSITE_METADATA: {json.dumps(metadata)} -->\n{response.text}"

            return FetchResult(success=True, raw_data=raw_with_metadata, content_type="html")

        except requests.Timeout:
            return FetchResult(
                success=False, raw_data=None, content_type="html", error=f"Request timeout after {self.timeout}s"
            )
        except requests.RequestException as e:
            return FetchResult(success=False, raw_data=None, content_type="html", error=f"Request failed: {str(e)}")
        except Exception as e:
            return FetchResult(success=False, raw_data=None, content_type="html", error=f"Unexpected error: {str(e)}")

    def parse(self, raw_data: str, ein: str, **kwargs) -> ParseResult:
        """
        Parse raw HTML into WebsiteProfile schema (single page only).

        Args:
            raw_data: HTML content (with optional metadata header from fetch)
            ein: Charity EIN
            url: Website URL (optional if metadata header present)

        Returns:
            ParseResult with {"website_profile": {...}}
        """
        url = kwargs.get("url")

        # Extract metadata if present
        metadata_match = re.match(r"<!-- WEBSITE_METADATA: ({.*?}) -->\n", raw_data)
        if metadata_match:
            metadata = json.loads(metadata_match.group(1))
            url = url or metadata.get("url")
            ein = ein or metadata.get("ein", "")
            raw_data = raw_data[metadata_match.end() :]  # Strip metadata header

        if not url:
            return ParseResult(success=False, parsed_data=None, error="URL required for parsing")

        try:
            soup = BeautifulSoup(raw_data, "html.parser")

            # Comprehensive extraction (same as old collect method)
            extracted_ein = self._extract_ein(soup)
            related_ein = None
            if extracted_ein and ein and _normalize_ein(extracted_ein) != _normalize_ein(ein):
                if self.logger:
                    self.logger.warning(
                        f"Website EIN {extracted_ein} doesn't match known EIN {ein} — storing as related_ein"
                    )
                related_ein = extracted_ein
                extracted_ein = None
            profile_data = {
                "url": url,
                "name": self._extract_org_name(soup),
                "mission": self._extract_mission(soup),
                "programs": self._extract_programs(soup),
                "contact_email": self._extract_email(soup),
                "contact_phone": self._extract_phone(soup),
                "address": self._extract_address(soup),
                "ein": extracted_ein or ein,
                "related_ein": related_ein,
                "donate_url": self._extract_donate_url(soup, url),
                "social_media": self._extract_social_media(soup),
                "tax_deductible": self._extract_tax_deductible(soup),
            }

            # Validate with Pydantic schema
            profile = WebsiteProfile(**profile_data)

            if self.logger:
                self.logger.debug("Successfully parsed website data")

            return ParseResult(success=True, parsed_data={self.schema_key: profile.model_dump()})

        except Exception as e:
            return ParseResult(success=False, parsed_data=None, error=f"Parse failed: {str(e)}")

    # Note: collect() from BaseCollector calls fetch() then parse() - provides single-page behavior.
    # For multi-page crawling, use collect_multi_page() below.

    # ─────────────────────────────────────────────────────────────────────────────
    # Internal methods
    # ─────────────────────────────────────────────────────────────────────────────

    def _run_async(self, coro):
        """
        Safely run async coroutine, handling nested event loop scenarios.

        Fixes C-002: asyncio.run() crashes if already in an async context
        (e.g., Jupyter notebooks, nested async calls).
        """
        try:
            asyncio.get_running_loop()
            # Already in an async context - run in thread pool to avoid blocking
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(coro)

    def _rate_limit(self):
        """Enforce rate limiting (global, thread-safe)."""
        global_rate_limiter.wait("website", self.rate_limit_delay)

    def _is_bot_challenge_html(self, html: str) -> bool:
        """Detect anti-bot challenge pages that are sometimes returned with HTTP 200."""
        if not html:
            return False

        body = html[:20000].lower()
        strong_markers = [
            "/cdn-cgi/challenge-platform/",
            "__cf$cv$params",
            "cf-chl-",
        ]
        if any(marker in body for marker in strong_markers):
            return True

        # Fallback marker combination seen on Cloudflare interstitial pages.
        if "just a moment" in body and "cloudflare" in body:
            return True

        return False

    def _fetch_url(
        self, url: str, force: bool = False, _recursion_depth: int = 0
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Fetch URL with aggressive caching, conditional requests, and curl_cffi fallback.

        Features:
        - Checks cache first (180-day TTL)
        - Uses conditional requests (If-Modified-Since, If-None-Match) for efficiency
        - Content hash comparison to detect actual changes
        - Falls back to curl_cffi for Cloudflare-protected domains
        - Caches successful responses with Last-Modified/ETag headers

        Args:
            url: URL to fetch
            force: If True, bypass cache and force fresh fetch
            _recursion_depth: Internal counter to prevent infinite recursion (max 1)

        Returns:
            Tuple of (success, html_content, final_url, error_message)
            final_url is the URL after redirects
        """
        # Prevent infinite recursion (C-010 fix)
        if _recursion_depth > 1:
            return False, None, None, "Max recursion depth reached in _fetch_url"
        # Check if we should refetch (based on age, schema version, etc.)
        if not force:
            should_fetch, reason = self.cache.should_refetch(url, force=False)
            if not should_fetch:
                # Use cached version
                cached = self.cache.get_cached_html(url)
                if cached:
                    if self._is_bot_challenge_html(cached.get("html", "")):
                        if self.logger:
                            self.logger.debug(f"Ignoring cached challenge page for {url}; refetching")
                    else:
                        if self.logger:
                            self.logger.debug(f"Cache hit ({reason}): {url}")
                        return True, cached["html"], cached["final_url"], None

        # Get stored HTTP headers for conditional request
        cached_headers = self.cache.get_http_headers(url)

        # Extract domain from URL
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.lower()

        # Build conditional request headers
        request_headers = self.headers.copy()
        if cached_headers.get("last_modified"):
            request_headers["If-Modified-Since"] = cached_headers["last_modified"]
        if cached_headers.get("etag"):
            request_headers["If-None-Match"] = cached_headers["etag"]

        # If we know this domain requires curl_cffi, use it directly with the known-good profile
        if domain in self.cloudflare_domains and HAS_CURL_CFFI:
            profile = self.cloudflare_domains[domain]
            try:
                # Don't pass custom headers - let curl_cffi use browser's exact headers
                response = curl_requests.get(url, timeout=self.timeout, impersonate=profile)

                if response.status_code == 200:
                    if self._is_bot_challenge_html(response.text):
                        return False, None, None, "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
                    # Get response headers
                    last_modified = response.headers.get("Last-Modified")
                    etag = response.headers.get("ETag")

                    # Cache the response with HTTP headers
                    self.cache.cache_html(
                        url, response.text, response.url, had_data=False, last_modified=last_modified, etag=etag
                    )
                    return True, response.text, response.url, None
                elif response.status_code == 304:
                    # Not Modified - use cached version
                    cached = self.cache.get_cached_html(url)
                    if cached:
                        if self.logger:
                            self.logger.debug(f"304 Not Modified (unchanged): {url}")
                        return True, cached["html"], cached["final_url"], None
                else:
                    return False, None, None, f"HTTP {response.status_code}"

            except Exception as e:
                return False, None, None, f"curl_cffi failed: {str(e)}"

        # Try regular requests first
        try:
            response = requests.get(url, headers=request_headers, timeout=self.timeout, allow_redirects=True)

            if response.status_code == 200:
                if self._is_bot_challenge_html(response.text):
                    return False, None, None, "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
                # Get response headers for caching
                last_modified = response.headers.get("Last-Modified")
                etag = response.headers.get("ETag")

                # Check if content actually changed (using hash)
                if not force and self.cache.has_content_changed(url, response.text) is False:
                    if self.logger:
                        self.logger.debug(f"Content unchanged (hash match): {url}")
                    # Return cached version — no need to re-cache identical content
                    return True, response.text, response.url, None

                # Cache the response with HTTP headers
                self.cache.cache_html(
                    url, response.text, response.url, had_data=False, last_modified=last_modified, etag=etag
                )
                return True, response.text, response.url, None
            elif response.status_code == 304:
                # Not Modified - use cached version
                cached = self.cache.get_cached_html(url)
                if cached:
                    if self.logger:
                        self.logger.debug(f"304 Not Modified: {url}")
                    return True, cached["html"], cached["final_url"], None
                else:
                    # No cache but got 304, fetch fresh (with recursion limit)
                    return self._fetch_url(url, force=True, _recursion_depth=_recursion_depth + 1)
            elif response.status_code in (403, 202, 503) and HAS_CURL_CFFI:
                # Bot protection detected (403 = blocked, 202 = JS challenge pending, 503 = challenge page)
                # Try curl_cffi with multiple browser profiles
                original_status = response.status_code
                if self.logger:
                    self.logger.debug(f"HTTP {original_status} detected, retrying with curl_cffi for {url}")

                # Try different browser profiles (some sites block Chrome but allow Safari)
                profiles_to_try = ["safari15_5", "chrome120", "edge101"]

                if self.logger:
                    self.logger.debug(f"Trying {len(profiles_to_try)} browser profiles: {profiles_to_try}")

                for profile in profiles_to_try:
                    if self.logger:
                        self.logger.debug(f"Attempting {profile} for {url}")
                    try:
                        # Don't pass custom headers - let curl_cffi use browser's exact headers
                        response = curl_requests.get(url, timeout=self.timeout, impersonate=profile)

                        if self.logger:
                            self.logger.debug(f"{profile} got status code: {response.status_code}")

                        if response.status_code == 200:
                            if self._is_bot_challenge_html(response.text):
                                if self.logger:
                                    self.logger.debug(f"{profile} returned challenge HTML for {url}")
                                continue
                            if self.logger:
                                self.logger.debug(
                                    f"curl_cffi bypass successful with {profile} - will use for all {domain} requests"
                                )
                            # Remember this domain requires curl_cffi and which profile works
                            with self._cloudflare_lock:
                                self.cloudflare_domains[domain] = profile
                                # Persist to cache for future runs (inside lock to avoid race)
                                self.cache.set_cloudflare_profile(domain, profile)
                            # Get response headers
                            last_modified = response.headers.get("Last-Modified")
                            etag = response.headers.get("ETag")
                            # Cache the response with HTTP headers
                            self.cache.cache_html(
                                url, response.text, response.url, had_data=False, last_modified=last_modified, etag=etag
                            )
                            return True, response.text, response.url, None
                    except Exception as e:
                        if self.logger:
                            self.logger.debug(f"{profile} failed for {url}: {e}")
                        # Brief delay before trying next profile to avoid triggering rate limits
                        time.sleep(0.5)
                        continue

                if self.logger:
                    self.logger.debug(f"All {len(profiles_to_try)} profiles failed for {url}")
                return False, None, None, f"HTTP {original_status} (even with curl_cffi)"
            else:
                return False, None, None, f"HTTP {response.status_code}"

        except requests.Timeout:
            return False, None, None, f"Request timeout after {self.timeout}s"
        except requests.RequestException as e:
            return False, None, None, f"Request failed: {str(e)}"
        except Exception as e:
            return False, None, None, f"Unexpected error: {str(e)}"

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for deduplication.

        Removes fragments, trailing slashes, and normalizes to lowercase.
        """
        parsed = urlparse(url)
        # Remove fragment and normalize
        normalized = urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/") or "/",
                parsed.params,
                parsed.query,
                "",  # Remove fragment
            )
        )
        return normalized

    def _should_skip_url(self, url: str) -> bool:
        """Check if URL matches skip patterns (crawler traps)."""
        for pattern in SKIP_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _is_priority_url(self, url: str) -> bool:
        """Check if URL matches priority patterns."""
        for pattern in PRIORITY_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are on the same domain (including subdomains)."""
        domain1 = urlparse(url1).netloc.lower()
        domain2 = urlparse(url2).netloc.lower()

        # Exact match
        if domain1 == domain2:
            return True

        # Extract root domain (last 2 parts) for subdomain matching
        # e.g., "www1.hhrd.org" -> "hhrd.org", "hhrd.org" -> "hhrd.org"
        def get_root_domain(domain: str) -> str:
            parts = domain.split(".")
            # Handle cases like co.uk, com.au etc. - keep last 2-3 parts
            if len(parts) >= 2:
                return ".".join(parts[-2:])
            return domain

        root1 = get_root_domain(domain1)
        root2 = get_root_domain(domain2)

        return root1 == root2

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all internal links from a page."""
        links = []

        for tag in soup.find_all("a", href=True):
            href = tag["href"]

            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)

            # Only include same-domain links
            if self._is_same_domain(absolute_url, base_url):
                # Skip if matches skip patterns
                if not self._should_skip_url(absolute_url):
                    # Skip file downloads
                    if not absolute_url.endswith((".pdf", ".doc", ".docx", ".zip", ".jpg", ".png", ".gif")):
                        links.append(self._normalize_url(absolute_url))

        return list(set(links))  # Deduplicate

    def _discover_urls_from_sitemap(self, base_url: str, max_pages: int = 25) -> Tuple[bool, List[str]]:
        """
        Discover URLs from sitemap.xml and score them for crawling priority (T043-T047).

        This method:
        1. Tries common sitemap locations (sitemap.xml, sitemap_index.xml)
        2. Scores all URLs using PageClassifier
        3. Returns top N highest-scoring URLs

        Args:
            base_url: Base URL of the website (e.g., https://charity.org)
            max_pages: Maximum number of pages to return (default 25)

        Returns:
            Tuple of (success, urls) where:
            - success: True if sitemap found and parsed, False otherwise
            - urls: List of top-scoring URLs to crawl
        """
        from urllib.parse import urljoin

        # Common sitemap locations
        sitemap_urls = [
            urljoin(base_url, "/sitemap.xml"),
            urljoin(base_url, "/sitemap_index.xml"),
            urljoin(base_url, "/sitemap-index.xml"),
        ]

        all_urls = []
        for sitemap_url in sitemap_urls:
            if self.logger:
                self.logger.debug(f"Trying sitemap: {sitemap_url}")

            urls = self.sitemap_parser.fetch_sitemap(sitemap_url)
            if urls:
                if self.logger:
                    self.logger.info(f"Found {len(urls)} URLs in sitemap: {sitemap_url}")
                all_urls = urls
                break

        if not all_urls:
            if self.logger:
                self.logger.debug("No sitemap found, will fallback to link-following mode")
            return False, []

        # Score all URLs (filter out obviously invalid URLs and respect robots.txt - T082)
        scored_pages = []
        for url in all_urls:
            # Basic URL validation - must start with http:// or https://
            if not url.startswith(("http://", "https://")):
                continue

            # Validate URL structure using urlparse
            from urllib.parse import urlparse

            try:
                parsed = urlparse(url)
                # Ensure all required components are present
                if not parsed.scheme or not parsed.netloc:
                    if self.logger:
                        self.logger.debug(f"Skipping invalid URL structure: {url[:100]}")
                    continue
                # Scheme must be http or https
                if parsed.scheme not in ("http", "https"):
                    continue
            except Exception:
                # urlparse raised an exception - invalid URL
                if self.logger:
                    self.logger.debug(f"Skipping malformed URL: {url[:100]}")
                continue

            # Skip if URL contains spaces or other invalid characters
            if " " in url or "%3A" in url or "%20" in url.split("://", 1)[1]:
                if self.logger:
                    self.logger.debug(f"Skipping URL with invalid characters: {url[:100]}")
                continue

            # Check robots.txt (T082)
            if not self.robots_checker.can_fetch(url):
                if self.logger:
                    self.logger.debug(f"Skipping URL disallowed by robots.txt: {url}")
                continue

            try:
                score = self.page_classifier.score_url(url)
                scored_pages.append(score)
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to score URL {url}: {e}")
                continue

        # Content-aware crawling: check more candidates for high-value content
        # This ensures pages like /dhul-hijjah-2022/ with "zakat eligible" are included
        # even if their URL doesn't match any patterns
        candidate_count = min(len(scored_pages), max_pages * 3)  # Check 3x more candidates

        # Sort by URL score first
        scored_pages.sort(key=lambda p: -p.raw_score)

        # Content scoring: optionally fetch pages to check for zakat keywords
        # This adds ~30s but can boost pages with zakat mentions
        if self.content_scoring:
            candidates = scored_pages[:candidate_count]

            if self.logger:
                self.logger.info(
                    f"Content-aware scoring: checking {len(candidates)} candidate pages for high-value content"
                )

            # Async content scoring for ~10x speedup
            content_score_timeout = 30  # Max 30s for content scoring phase
            content_boosted = self._score_content_parallel(candidates, timeout_total=content_score_timeout)

            # Log any significant boosts
            for i, boosted in enumerate(content_boosted):
                if i < len(candidates) and boosted.raw_score > candidates[i].raw_score:
                    boost_keywords = [k for k in boosted.matched_keywords if k not in candidates[i].matched_keywords]
                    if self.logger and boost_keywords:
                        self.logger.info(
                            f"Content boost: {candidates[i].url} score {candidates[i].raw_score} -> {boosted.raw_score} "
                            f"(found: {', '.join(boost_keywords[:3])})"
                        )

            # Add any remaining pages that weren't checked (beyond candidate_count)
            remaining_pages = scored_pages[candidate_count:]
            all_scored = content_boosted + remaining_pages
        else:
            # Skip content scoring - just use URL-based scores
            all_scored = scored_pages

        # Select top pages with content-aware scores
        top_pages = self.page_classifier.select_top_pages(all_scored, max_pages=max_pages)

        # Extract URLs with null check
        if not top_pages:
            if self.logger:
                self.logger.warning("No top pages selected from sitemap")
            return False, []

        top_urls = [str(page.url) for page in top_pages if page and page.url]

        if self.logger and top_pages:
            # Calculate average score with protection against division by zero
            avg_score = sum(p.raw_score for p in top_pages) / len(top_pages) if top_pages else 0.0
            content_boosted_count = sum(1 for p in top_pages if p.breakdown.get("content_boost", 0) > 0)
            self.logger.info(
                f"Selected {len(top_urls)} top-scoring pages from sitemap "
                f"(avg score: {avg_score:.1f}, {content_boosted_count} content-boosted)"
            )

        return True, top_urls

    def _crawl_specific_urls(self, urls: List[str], timeout_total: int) -> Dict[str, Dict[str, Any]]:
        """
        Crawl a specific list of URLs (from sitemap) without following links.

        This is used when we have a sitemap and know exactly which pages to crawl.

        Args:
            urls: List of URLs to crawl
            timeout_total: Total timeout in seconds for entire crawl

        Returns:
            Dictionary mapping URL -> extracted data for each page visited
        """
        start_time = time.time()
        results: Dict[str, Dict[str, Any]] = {}

        if self.logger:
            self.logger.debug(f"Crawling {len(urls)} specific URLs from sitemap")

        for i, url in enumerate(urls, 1):
            # Check timeout
            if time.time() - start_time > timeout_total:
                if self.logger:
                    self.logger.warning(f"Crawler timeout after {timeout_total}s, crawled {i - 1}/{len(urls)} pages")
                break

            if self.logger:
                self.logger.debug(f"Crawling [{i}/{len(urls)}]: {url}")

            # Rate limit
            self._rate_limit()

            # Fetch page
            success, html, final_url, error = self._fetch_url(url)

            if not success:
                if self.logger:
                    self.logger.warning(f"Failed to fetch {url}: {error}")
                continue

            try:
                # Extract data from this page using smart extractors
                # Use LLM only for high-value pages (T059)
                # Special case: always use LLM for zakat pages (critical for evidence extraction)
                is_zakat_page = any(kw in url.lower() for kw in ["zakat", "zakaat", "zakah"])
                use_llm_for_page = self.use_llm and (i <= 5 or is_zakat_page)
                page_data = self._extract_page_data(html, final_url or url, use_llm=use_llm_for_page)

                # Track which extraction methods were used
                extraction_methods = ["deterministic"]  # Always use deterministic
                if use_llm_for_page:
                    extraction_methods.append("llm")

                # Check if JS rendering is needed and try Playwright fallback
                js_needed = page_data.get("js_rendering_needed", False)
                if js_needed and self.use_playwright:
                    renderer = self._get_playwright_renderer()
                    if renderer:
                        rendered_html = renderer.render(final_url or url)
                        if rendered_html:
                            # Re-extract with Playwright-rendered HTML
                            page_data = self._extract_page_data(
                                rendered_html, final_url or url, use_llm=use_llm_for_page
                            )
                            extraction_methods.append("playwright")
                            js_needed = page_data.get("js_rendering_needed", False)
                            if self.logger:
                                self.logger.info(f"Playwright fallback successful: {url}")

                # Update cache with had_data flag, methods tried, and JS rendering status
                had_data = page_data.get("had_data", False)
                failure_reason = page_data.get("extraction_failure_reason")
                self.cache.update_had_data(
                    url,
                    had_data,
                    extraction_methods,
                    js_rendering_needed=js_needed,
                    extraction_failure_reason=failure_reason,
                )

                # Only store if we found something useful
                if any(v for v in page_data.values() if v):
                    results[url] = page_data

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Unexpected error processing {url}: {str(e)}")
                # Mark as tried with no data on error
                self.cache.update_had_data(url, False, ["deterministic"])
                continue

        if self.logger:
            self.logger.debug(f"Sitemap crawl complete: crawled {len(results)}/{len(urls)} pages successfully")

        return results

    async def _fetch_url_async(
        self,
        client: httpx.AsyncClient,
        url: str,
        semaphore: asyncio.Semaphore,
    ) -> Tuple[str, bool, Optional[str], Optional[str], Optional[str]]:
        """
        Async fetch a single URL with concurrency control.

        Args:
            client: httpx async client
            url: URL to fetch
            semaphore: Semaphore for concurrency limiting

        Returns:
            Tuple of (url, success, html_content, final_url, error_message)
        """
        async with semaphore:
            try:
                # Check cache first (sync operation but fast)
                cached = self.cache.get_cached_html(url)
                if cached:
                    if self._is_bot_challenge_html(cached.get("html", "")):
                        if self.logger:
                            self.logger.debug(f"Ignoring cached challenge page for {url}; refetching")
                    else:
                        return url, True, cached["html"], cached["final_url"], None

                response = await client.get(
                    url,
                    follow_redirects=True,
                    timeout=15.0,
                )

                if response.status_code == 200:
                    if self._is_bot_challenge_html(response.text):
                        return url, False, None, None, "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
                    html = response.text
                    final_url = str(response.url)
                    # Cache the result (sync but fast)
                    self.cache.cache_html(url, html, final_url, "", "")
                    return url, True, html, final_url, None
                else:
                    # Detect captcha/anti-bot blocking
                    error_msg = f"HTTP {response.status_code}"
                    is_captcha = False
                    if response.status_code in (202, 403, 429, 503):
                        # Treat these statuses as potential anti-bot blocks and try curl_cffi fallback.
                        is_captcha = True
                        error_msg = f"CAPTCHA_BLOCKED: HTTP {response.status_code}"
                        # Check for known captcha indicators
                        captcha_headers = ["sg-captcha", "cf-ray", "x-captcha"]
                        for header in captcha_headers:
                            if header in [h.lower() for h in response.headers.keys()]:
                                error_msg = f"CAPTCHA_BLOCKED: {header} (HTTP {response.status_code})"
                                is_captcha = True
                                break
                        # Check response body for captcha indicators
                        body_lower = (
                            response.text.lower() if len(response.text) < 5000 else response.text[:5000].lower()
                        )
                        if "captcha" in body_lower or "challenge" in body_lower or "verify you are human" in body_lower:
                            error_msg = f"CAPTCHA_BLOCKED: challenge page (HTTP {response.status_code})"
                            is_captcha = True

                    # Try curl_cffi fallback for captcha/bot protection
                    if is_captcha and HAS_CURL_CFFI:
                        if self.logger:
                            self.logger.debug(f"Captcha detected, trying curl_cffi fallback for {url}")

                        # Try curl_cffi with browser impersonation (run in thread pool)
                        curl_result = await self._try_curl_cffi_async(url)
                        if curl_result[1]:  # success
                            return curl_result
                        # curl_cffi also failed, return original captcha error

                    return url, False, None, None, error_msg

            except httpx.TimeoutException:
                return url, False, None, None, "Timeout"
            except Exception as e:
                return url, False, None, None, str(e)

    async def _try_curl_cffi_async(self, url: str) -> Tuple[str, bool, Optional[str], Optional[str], Optional[str]]:
        """
        Try fetching URL with curl_cffi browser impersonation (async wrapper).

        Runs curl_cffi in a thread pool since it doesn't support async natively.
        Tries multiple browser profiles to bypass anti-bot protection.

        Returns:
            Tuple of (url, success, html_content, final_url, error_message)
        """
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.lower()

        # Check if we already know a working profile for this domain
        if domain in self.cloudflare_domains:
            profile = self.cloudflare_domains[domain]
            result = await asyncio.to_thread(self._curl_cffi_fetch, url, profile)
            if result[1]:  # success
                return result

        # Try different browser profiles
        profiles_to_try = ["safari15_5", "chrome120", "edge101"]

        for profile in profiles_to_try:
            if self.logger:
                self.logger.debug(f"Trying curl_cffi {profile} for {url}")

            result = await asyncio.to_thread(self._curl_cffi_fetch, url, profile)

            if result[1]:  # success
                if self.logger:
                    self.logger.debug(f"curl_cffi {profile} succeeded for {url}")
                # Remember working profile for this domain (thread-safe)
                with self._cloudflare_lock:
                    self.cloudflare_domains[domain] = profile
                # Persist to cache for future runs
                self.cache.set_cloudflare_profile(domain, profile)
                return result

            # Brief delay before trying next profile to avoid triggering rate limits
            await asyncio.sleep(0.5)

        if self.logger:
            self.logger.debug(f"All curl_cffi profiles failed for {url}")
        return url, False, None, None, "curl_cffi fallback failed"

    def _curl_cffi_fetch(self, url: str, profile: str) -> Tuple[str, bool, Optional[str], Optional[str], Optional[str]]:
        """
        Synchronous curl_cffi fetch with browser impersonation.

        Called from thread pool by _try_curl_cffi_async.
        """
        try:
            response = curl_requests.get(url, timeout=self.timeout, impersonate=profile)

            if response.status_code == 200:
                if self._is_bot_challenge_html(response.text):
                    return url, False, None, None, "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
                html = response.text
                final_url = response.url
                # Cache the result
                last_modified = response.headers.get("Last-Modified")
                etag = response.headers.get("ETag")
                self.cache.cache_html(url, html, final_url, had_data=False, last_modified=last_modified, etag=etag)
                return url, True, html, final_url, None
            else:
                return url, False, None, None, f"HTTP {response.status_code}"
        except Exception as e:
            return url, False, None, None, f"curl_cffi error: {str(e)}"

    async def _crawl_urls_async(
        self,
        urls: List[str],
        max_concurrent: int = 10,
        timeout_total: int = 90,
    ) -> Dict[str, Tuple[bool, Optional[str], Optional[str], Optional[str]]]:
        """
        Crawl multiple URLs concurrently using async HTTP.

        Args:
            urls: List of URLs to crawl
            max_concurrent: Maximum concurrent requests (default 10)
            timeout_total: Total timeout for all requests

        Returns:
            Dict mapping URL -> (success, html, final_url, error)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results: Dict[str, Tuple[bool, Optional[str], Optional[str], Optional[str]]] = {}

        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=httpx.Timeout(15.0, connect=10.0),
        ) as client:
            tasks = [self._fetch_url_async(client, url, semaphore) for url in urls]

            # Use asyncio.wait_for for overall timeout
            try:
                completed = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout_total,
                )

                for result in completed:
                    if isinstance(result, Exception):
                        continue
                    url, success, html, final_url, error = result
                    results[url] = (success, html, final_url, error)

            except asyncio.TimeoutError:
                if self.logger:
                    self.logger.warning(
                        f"Async crawl timeout after {timeout_total}s, got {len(results)}/{len(urls)} pages"
                    )

        return results

    async def _score_content_async(
        self,
        candidates: List[Any],  # List of PageScore objects
        timeout_total: int = 30,
        max_concurrent: int = 15,
    ) -> List[Any]:
        """
        Async content scoring - fetch pages in parallel to check for keywords.

        Args:
            candidates: List of PageScore objects to check
            timeout_total: Total timeout for all fetches
            max_concurrent: Max concurrent requests

        Returns:
            List of PageScore objects with content boosts applied
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results: List[Any] = []

        async def fetch_and_score(page_score: Any) -> Any:
            async with semaphore:
                try:
                    # Check cache first
                    cached = self.cache.get_cached_html(str(page_score.url))
                    if cached:
                        html = cached["html"]
                    else:
                        async with httpx.AsyncClient(
                            headers=self.headers,
                            follow_redirects=True,
                            timeout=httpx.Timeout(10.0, connect=5.0),
                        ) as client:
                            response = await client.get(str(page_score.url))
                            if response.status_code == 200:
                                html = response.text
                                # Cache it
                                self.cache.cache_html(str(page_score.url), html, str(response.url), "", "")
                            else:
                                return page_score  # Keep original score

                    # Apply content boost
                    boosted = self.page_classifier.apply_content_boost(page_score, html)
                    return boosted

                except Exception:
                    return page_score  # Keep original on error

        try:
            tasks = [fetch_and_score(ps) for ps in candidates]
            completed = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_total,
            )

            for i, result in enumerate(completed):
                if isinstance(result, Exception):
                    results.append(candidates[i])
                else:
                    results.append(result)

        except asyncio.TimeoutError:
            if self.logger:
                self.logger.warning(f"Async content scoring timeout after {timeout_total}s")
            # Add remaining unprocessed candidates
            results.extend(candidates[len(results) :])

        return results

    def _score_content_parallel(
        self,
        candidates: List[Any],
        timeout_total: int = 30,
    ) -> List[Any]:
        """
        Parallel content scoring wrapper (calls async version).

        Args:
            candidates: List of PageScore objects
            timeout_total: Total timeout

        Returns:
            List of PageScore objects with content boosts applied
        """
        if self.logger:
            self.logger.info(f"Async content scoring: {len(candidates)} pages (max 15 concurrent)")

        start = time.time()
        results = self._run_async(self._score_content_async(candidates, timeout_total))

        if self.logger:
            elapsed = time.time() - start
            boosted = sum(1 for i, r in enumerate(results) if r.raw_score > candidates[i].raw_score)
            self.logger.info(f"Content scoring complete: {len(results)} pages in {elapsed:.1f}s ({boosted} boosted)")

        return results

    def _crawl_specific_urls_async(self, urls: List[str], timeout_total: int) -> Dict[str, Dict[str, Any]]:
        """
        Crawl URLs using async HTTP for ~5x speedup.

        This replaces the sequential _crawl_specific_urls with parallel fetching.

        Args:
            urls: List of URLs to crawl
            timeout_total: Total timeout in seconds

        Returns:
            Dictionary mapping URL -> extracted data for each page
        """
        start_time = time.time()
        results: Dict[str, Dict[str, Any]] = {}

        if self.logger:
            self.logger.info(f"Async crawling {len(urls)} URLs (max 10 concurrent)")

        # Run async crawl
        fetch_results = self._run_async(self._crawl_urls_async(urls, max_concurrent=10, timeout_total=timeout_total))

        fetch_time = time.time() - start_time
        if self.logger:
            self.logger.info(f"Async fetch complete: {len(fetch_results)}/{len(urls)} pages in {fetch_time:.1f}s")

        # Process fetched HTML (this part is still sequential but fast)
        process_start = time.time()
        for url, (success, html, final_url, error) in fetch_results.items():
            if not success or not html:
                if self.logger and error:
                    self.logger.debug(f"Failed to fetch {url}: {error}")
                continue

            try:
                # Extract data from HTML
                page_data = self._extract_page_data(html, final_url or url, use_llm=False)

                # Update cache metadata
                had_data = page_data.get("had_data", False)
                self.cache.update_had_data(url, had_data, ["deterministic", "async"])

                if any(v for v in page_data.values() if v):
                    results[url] = page_data

            except Exception as e:
                if self.logger:
                    self.logger.debug(f"Error processing {url}: {e}")
                continue

        process_time = time.time() - process_start
        if self.logger:
            self.logger.info(f"Processing complete: {len(results)} pages with data in {process_time:.1f}s")

        return results

    def _crawl_with_bfs(
        self, start_url: str, max_depth: int, max_pages: int, timeout_total: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Crawl website using priority-based depth-first search to find EIN and other data.

        Priority URLs (about, contact, donate, FAQ, stocks) are crawled depth-first,
        while other URLs are crawled breadth-first. This ensures we check the most
        likely pages for EIN/contact info first.

        Args:
            start_url: Starting URL (homepage)
            max_depth: Maximum depth to crawl (0 = homepage only, 1 = homepage + direct links, etc.)
            max_pages: Maximum total pages to visit
            timeout_total: Total timeout in seconds for entire crawl

        Returns:
            Dictionary mapping URL -> extracted data for each page visited
        """
        start_time = time.time()
        visited: Set[str] = set()
        # Use list as stack for DFS (append/pop from end)
        stack: List[Tuple[str, int]] = [(self._normalize_url(start_url), 0)]  # (url, depth)
        results: Dict[str, Dict[str, Any]] = {}

        if self.logger:
            self.logger.debug(
                f"Starting priority DFS crawl from {start_url} (max_depth={max_depth}, max_pages={max_pages})"
            )

        while stack and len(visited) < max_pages:
            # Check timeout
            if time.time() - start_time > timeout_total:
                if self.logger:
                    self.logger.warning(f"Crawler timeout after {timeout_total}s, visited {len(visited)} pages")
                break

            current_url, depth = stack.pop()  # DFS: pop from end

            # Skip if already visited
            if current_url in visited:
                continue

            # Skip if exceeded max depth
            if depth > max_depth:
                continue

            visited.add(current_url)

            if self.logger:
                self.logger.debug(f"Crawling [{len(visited)}/{max_pages}] depth={depth}: {current_url}")

            # Rate limit
            self._rate_limit()

            # Fetch page (with curl_cffi fallback for Cloudflare)
            success, html, final_url, error = self._fetch_url(current_url)

            if not success:
                if self.logger:
                    self.logger.warning(f"Failed to fetch {current_url}: {error}")
                continue

            try:
                soup = BeautifulSoup(html, "html.parser")

                # Extract data from this page using smart extractors (004-smart-crawler)
                # Use LLM only for high-value pages (T059)
                # Special case: always use LLM for zakat pages (critical for evidence extraction)
                is_zakat_page = any(kw in current_url.lower() for kw in ["zakat", "zakaat", "zakah"])
                use_llm_for_page = self.use_llm and (len(visited) <= 5 or is_zakat_page)
                page_data = self._extract_page_data(html, final_url or current_url, use_llm=use_llm_for_page)

                # Track which extraction methods were used
                extraction_methods = ["deterministic"]
                if use_llm_for_page:
                    extraction_methods.append("llm")

                # Check if JS rendering is needed and try Playwright fallback
                js_needed = page_data.get("js_rendering_needed", False)
                if js_needed and self.use_playwright:
                    renderer = self._get_playwright_renderer()
                    if renderer:
                        rendered_html = renderer.render(final_url or current_url)
                        if rendered_html:
                            # Re-extract with Playwright-rendered HTML
                            page_data = self._extract_page_data(
                                rendered_html, final_url or current_url, use_llm=use_llm_for_page
                            )
                            extraction_methods.append("playwright")
                            js_needed = page_data.get("js_rendering_needed", False)
                            if self.logger:
                                self.logger.info(f"Playwright fallback successful: {current_url}")

                # Update cache with had_data flag, methods tried, and JS rendering status
                had_data = page_data.get("had_data", False)
                failure_reason = page_data.get("extraction_failure_reason")
                self.cache.update_had_data(
                    current_url,
                    had_data,
                    extraction_methods,
                    js_rendering_needed=js_needed,
                    extraction_failure_reason=failure_reason,
                )

                # Only store if we found something useful
                if any(v for v in page_data.values() if v):
                    results[current_url] = page_data

                # Extract links for next level (if not at max depth)
                # IMPORTANT: Use final_url (after redirects) as base for link extraction
                if depth < max_depth:
                    links = self._extract_links(soup, final_url or current_url)

                    # Sort links: priority URLs first, then others
                    priority_links = [url for url in links if self._is_priority_url(url)]
                    other_links = [url for url in links if not self._is_priority_url(url)]

                    # Add other links first (to bottom of stack - visited last)
                    for link in other_links:
                        if link not in visited:
                            stack.append((link, depth + 1))

                    # Add priority links last (to top of stack - visited first for DFS)
                    for link in priority_links:
                        if link not in visited:
                            stack.append((link, depth + 1))

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Unexpected error processing {current_url}: {str(e)}")
                # Mark as tried with no data on error
                self.cache.update_had_data(current_url, False, ["deterministic"])
                continue

        if self.logger:
            self.logger.debug(f"Crawl complete: visited {len(visited)} pages, found data on {len(results)} pages")

        return results

    async def _crawl_bfs_async(
        self, start_url: str, max_depth: int, max_pages: int, timeout_total: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Async BFS crawl - fetches each depth level in parallel for ~5x speedup.

        Instead of sequential fetching with rate limits, this processes URLs
        level-by-level with parallel fetching within each level.

        Args:
            start_url: Starting URL (homepage)
            max_depth: Maximum depth to crawl
            max_pages: Maximum total pages to visit
            timeout_total: Total timeout in seconds

        Returns:
            Dictionary mapping URL -> extracted data for each page visited
        """
        start_time = time.time()
        visited: Set[str] = set()
        results: Dict[str, Dict[str, Any]] = {}

        # Start with homepage at depth 0
        current_level: List[Tuple[str, int]] = [(self._normalize_url(start_url), 0)]

        if self.logger:
            self.logger.debug(
                f"Starting async BFS crawl from {start_url} (max_depth={max_depth}, max_pages={max_pages})"
            )

        while current_level and len(visited) < max_pages:
            # Check timeout
            if time.time() - start_time > timeout_total:
                if self.logger:
                    self.logger.warning(f"Async BFS timeout after {timeout_total}s, visited {len(visited)} pages")
                break

            # Filter out already visited and respect max_pages
            urls_to_fetch = []
            for url, depth in current_level:
                if url not in visited and len(visited) + len(urls_to_fetch) < max_pages:
                    urls_to_fetch.append((url, depth))
                    visited.add(url)

            if not urls_to_fetch:
                break

            # Sort: priority URLs first within this level
            priority_urls = [(u, d) for u, d in urls_to_fetch if self._is_priority_url(u)]
            other_urls = [(u, d) for u, d in urls_to_fetch if not self._is_priority_url(u)]
            urls_to_fetch = priority_urls + other_urls

            current_depth = urls_to_fetch[0][1] if urls_to_fetch else 0
            if self.logger:
                self.logger.debug(f"Async fetching {len(urls_to_fetch)} URLs at depth {current_depth}")

            # Parallel fetch all URLs at this level
            url_list = [u for u, _ in urls_to_fetch]
            remaining_time = max(10, timeout_total - int(time.time() - start_time))
            fetch_results = await self._crawl_urls_async(url_list, max_concurrent=10, timeout_total=remaining_time)

            # Process fetched pages and collect links for next level
            next_level: List[Tuple[str, int]] = []

            for url, depth in urls_to_fetch:
                if url not in fetch_results:
                    continue

                success, html, final_url, error = fetch_results[url]
                if not success or not html:
                    if self.logger and error:
                        self.logger.debug(f"Failed to fetch {url}: {error}")
                    # Track captcha errors for reporting
                    if error and "CAPTCHA_BLOCKED" in error and not self._last_captcha_error:
                        self._last_captcha_error = error
                    continue

                try:
                    soup = BeautifulSoup(html, "html.parser")

                    # Extract data - use LLM only for first few pages or zakat pages
                    is_zakat_page = any(kw in url.lower() for kw in ["zakat", "zakaat", "zakah"])
                    use_llm_for_page = self.use_llm and (len(results) < 5 or is_zakat_page)
                    page_data = self._extract_page_data(html, final_url or url, use_llm=use_llm_for_page)

                    extraction_methods = ["deterministic", "async"]
                    if use_llm_for_page:
                        extraction_methods.append("llm")

                    # Update cache
                    had_data = page_data.get("had_data", False)
                    failure_reason = page_data.get("extraction_failure_reason")
                    self.cache.update_had_data(
                        url,
                        had_data,
                        extraction_methods,
                        js_rendering_needed=page_data.get("js_rendering_needed", False),
                        extraction_failure_reason=failure_reason,
                    )

                    # Store results
                    if any(v for v in page_data.values() if v):
                        results[url] = page_data

                    # Extract links for next level (if not at max depth)
                    if depth < max_depth:
                        links = self._extract_links(soup, final_url or url)
                        for link in links:
                            if link not in visited:
                                next_level.append((link, depth + 1))

                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error processing {url}: {str(e)}")
                    self.cache.update_had_data(url, False, ["deterministic", "async"])
                    continue

            # Move to next level
            current_level = next_level

        if self.logger:
            elapsed = time.time() - start_time
            self.logger.debug(
                f"Async BFS complete: visited {len(visited)} pages, found data on {len(results)} in {elapsed:.1f}s"
            )

        return results

    def _crawl_with_bfs_async(
        self, start_url: str, max_depth: int, max_pages: int, timeout_total: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Synchronous wrapper for async BFS crawl.

        This replaces the sequential _crawl_with_bfs with parallel level-by-level fetching.

        Args:
            start_url: Starting URL
            max_depth: Maximum depth to crawl
            max_pages: Maximum total pages
            timeout_total: Total timeout in seconds

        Returns:
            Dictionary mapping URL -> extracted data
        """
        return self._run_async(self._crawl_bfs_async(start_url, max_depth, max_pages, timeout_total))

    def _merge_llm_data(self, regex_data: Dict[str, Any], llm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge LLM extraction with regex extraction.

        Strategy:
        - Use LLM data for rich fields (mission, programs, impact, etc.)
        - Use regex data for simple fields if LLM didn't find them
        - Prefer LLM EIN if both found (more reliable)

        Args:
            regex_data: Data from regex extraction
            llm_data: Data from LLM extraction

        Returns:
            Merged data dict
        """
        merged = regex_data.copy()

        # Prefer LLM for these rich fields
        # Use field names that match WebsiteProfile validator (from website_extractor.py)
        rich_fields = [
            # Core org info
            "name",
            "mission",
            "vision_statement",
            "tagline",
            "values",
            # Programs and impact
            "programs",
            "program_descriptions",
            "geographic_coverage",
            "populations_served",
            "impact_metrics",
            "leadership",
            # Donation info
            "donation_methods",
            "volunteer_opportunities",
            "annual_revenue",
            "annual_expenses",
            # Note: Zakat fields handled by discover.py, not website extraction
            # Other
            "additional_info",
            "logo_url",
            "founded_year",
            "tax_deductible",
            "contact_email",
            "contact_phone",
            "address",
            # Scoring data fields (for AMAL evaluation)
            "systemic_leverage_data",
            "ummah_gap_data",
            "evidence_of_impact_data",
            "absorptive_capacity_data",
        ]

        for field in rich_fields:
            if field in llm_data and llm_data[field]:
                merged[field] = llm_data[field]

        # Merge contact info (prefer LLM if available, otherwise keep regex)
        if "contact" in llm_data and llm_data["contact"]:
            contact = llm_data["contact"]
            if contact.get("email"):
                merged["email"] = contact["email"]
            if contact.get("phone"):
                merged["phone"] = contact["phone"]
            if contact.get("address"):
                merged["address"] = contact["address"]

        # Merge social media (combine both sources)
        if "social_media" in llm_data and llm_data["social_media"]:
            if not merged.get("social_media"):
                merged["social_media"] = {}
            merged["social_media"].update(llm_data["social_media"])

        # Prefer LLM EIN if found (more reliable than regex)
        if llm_data.get("ein"):
            merged["ein"] = llm_data["ein"]

        # Use LLM donate_url if found
        if llm_data.get("donate_url"):
            merged["donate_url"] = llm_data["donate_url"]

        # Use LLM tax_deductible if found
        if llm_data.get("tax_deductible") is not None:
            merged["tax_deductible"] = llm_data["tax_deductible"]

        return merged

    def _aggregate_crawl_data(self, crawl_results: Dict[str, Dict[str, Any]], base_url: str) -> Dict[str, Any]:
        """
        Aggregate data from multiple pages into a single profile.

        Strategy:
        - EIN: Use first non-None EIN found (prioritize priority pages)
        - Contact: Use first non-None contact info found
        - Social media: Merge all social media links
        - Donate URL: Prefer dedicated donate pages
        - Tax deductible: True if found on any page
        - Extraction results: Collect all provenance data (T028, T029)

        Args:
            crawl_results: Dictionary of URL -> extracted data
            base_url: Base URL for the website

        Returns:
            Aggregated profile data with pages array (T029)
        """
        aggregated = {
            "ein": None,
            "email": None,
            "phone": None,
            "address": None,
            "donate_url": None,
            "social_media": {},
            "tax_deductible": None,
            # Zakat fields - extracted from content-aware crawling
            "accepts_zakat": None,
            "zakat_evidence": None,
            "zakat_url": None,
        }

        # Collect all extraction results, structured data, LLM data, and PDFs (T029, T060, T076)
        all_extraction_results = []
        all_pages_data = []
        all_llm_data = []
        all_pdf_links = []
        total_llm_cost = 0.0
        zakat_pages_found = []  # Track pages with zakat content

        # Sort URLs: priority pages first
        sorted_urls = sorted(crawl_results.keys(), key=lambda url: (0 if self._is_priority_url(url) else 1, url))

        for url in sorted_urls:
            data = crawl_results[url]

            # Collect extraction results with provenance (T028, T029)
            if data.get("extraction_results"):
                all_extraction_results.extend(data["extraction_results"])

            # Collect LLM data from semantic field extraction (T060)
            if data.get("llm_data"):
                all_llm_data.append({"url": url, "llm_data": data["llm_data"], "llm_cost": data.get("llm_cost", 0.0)})
                total_llm_cost += data.get("llm_cost", 0.0)

            # Collect PDF links from this page (T076)
            if data.get("pdf_links"):
                for pdf_info in data["pdf_links"]:
                    pdf_info["source_page_url"] = url  # Track which page had the PDF link
                    all_pdf_links.append(pdf_info)

            # Collect structured data per page (T029)
            if data.get("structured_data"):
                all_pages_data.append(
                    {
                        "url": url,
                        "structured_data": data["structured_data"],
                        "extraction_results": data.get("extraction_results", []),
                        "llm_data": data.get("llm_data"),  # Include LLM data in page tracking
                    }
                )

            # EIN: Take first found (priority pages checked first)
            if aggregated["ein"] is None and data.get("ein"):
                aggregated["ein"] = data["ein"]
                if self.logger:
                    self.logger.debug(f"Found EIN on {url}: {data['ein']}")

            # Contact info: Take first found
            if aggregated["email"] is None and data.get("email"):
                aggregated["email"] = data["email"]

            if aggregated["phone"] is None and data.get("phone"):
                aggregated["phone"] = data["phone"]

            if aggregated["address"] is None and data.get("address"):
                aggregated["address"] = data["address"]

            # Donate URL: Prefer URLs from priority pages or with 'donate' in path
            if data.get("donate_url"):
                if aggregated["donate_url"] is None:
                    aggregated["donate_url"] = data["donate_url"]
                elif "/donate" in data["donate_url"].lower() and "/donate" not in aggregated["donate_url"].lower():
                    # Prefer explicit /donate URLs
                    aggregated["donate_url"] = data["donate_url"]

            # Social media: Merge all (dict.update())
            if data.get("social_media"):
                aggregated["social_media"].update(data["social_media"])

            # Tax deductible: True if found on any page
            if data.get("tax_deductible") is True:
                aggregated["tax_deductible"] = True

        # Add provenance data to aggregated results (T029, T060, T076)
        aggregated["extraction_results"] = all_extraction_results
        aggregated["pages"] = all_pages_data
        aggregated["llm_extractions"] = all_llm_data
        aggregated["total_llm_cost"] = total_llm_cost
        aggregated["pdf_documents"] = all_pdf_links  # T076: All PDF links discovered
        aggregated["pdfs_downloaded"] = 0  # Track how many PDFs were downloaded

        # Aggregate beneficiaries_served from page-specific LLM extractions
        # Look for total_beneficiaries in ImpactResponse outcomes_summary
        for llm_entry in all_llm_data:
            llm_data = llm_entry.get("llm_data", {})
            if llm_data:
                # Check for outcomes_summary.total_beneficiaries (ImpactResponse schema)
                outcomes = llm_data.get("outcomes_summary", {})
                if outcomes and outcomes.get("total_beneficiaries"):
                    aggregated["beneficiaries_served"] = outcomes["total_beneficiaries"]
                    break  # Use first found value

        # Content-aware zakat detection: use zakat_detected flag from _extract_page_data
        # This detects zakat keywords during the crawl phase when we have access to HTML
        for url, data in crawl_results.items():
            if data.get("zakat_detected"):
                zakat_keywords_on_page = data.get("zakat_keywords", [])
                zakat_pages_found.append(
                    {
                        "url": url,
                        "keyword": zakat_keywords_on_page[0] if zakat_keywords_on_page else "zakat",
                    }
                )

        # Set zakat fields if we found evidence
        if zakat_pages_found:
            aggregated["accepts_zakat"] = True
            # Use first found as primary evidence
            first_match = zakat_pages_found[0]
            aggregated["zakat_url"] = first_match["url"]
            aggregated["zakat_evidence"] = f"Found '{first_match['keyword']}' on {first_match['url']}"
            if self.logger:
                self.logger.info(
                    f"Zakat eligibility detected: found '{first_match['keyword']}' on {len(zakat_pages_found)} page(s)"
                )

        # Discover volunteer_page_url from crawled URLs
        volunteer_patterns = ["volunteer", "get-involved", "join-us", "take-action"]
        for url in sorted_urls:
            url_lower = url.lower()
            if any(pattern in url_lower for pattern in volunteer_patterns):
                aggregated["volunteer_page_url"] = url
                break

        # Map donate_url to donation_page_url for schema consistency
        if aggregated.get("donate_url") and not aggregated.get("donation_page_url"):
            aggregated["donation_page_url"] = aggregated["donate_url"]

        return aggregated

    def _download_priority_pdfs(self, pdf_links: List[dict], charity_id: int = 0, max_downloads: int = 5) -> int:
        """
        Download priority PDF documents with V2 dimension-aligned selection (T068-T074).

        V2 Selection Criteria:
        - TRUST documents (990, audit, financial): Highest priority for verification
        - EVIDENCE documents (impact, evaluation, theory of change): High priority for outcomes
        - EFFECTIVENESS documents (annual, program reports): Medium priority for operations
        - FIT documents (strategic plan, governance): Lower priority but still valuable

        Args:
            pdf_links: List of PDF link dicts from discovery
            charity_id: Database ID of charity (0 if not saved yet)
            max_downloads: Maximum PDFs to download (default 5, 0 = disabled)

        Returns:
            Number of PDFs successfully downloaded
        """
        if max_downloads == 0 or not pdf_links:
            return 0

        # V2 dimension-aligned priority order
        # Lower number = higher priority
        # TRUST (verification): 1-3, EVIDENCE (outcomes): 4-6, EFFECTIVENESS (ops): 7-8, FIT (strategy): 9-10
        priority_order = {
            # TRUST dimension - verification, transparency
            "form_990": 1,  # IRS verification, gold standard
            "audit_report": 2,  # Independent audit, high trust
            "financial_statement": 3,  # Financial transparency
            # EVIDENCE dimension - outcomes, research
            "evaluation_report": 4,  # Third-party evaluation
            "impact_report": 5,  # Outcomes and metrics
            "theory_of_change": 6,  # Program theory documentation
            # EFFECTIVENESS dimension - operations
            "annual_report": 7,  # Comprehensive overview
            "program_report": 8,  # Program details
            # FIT dimension - strategy, governance
            "strategic_plan": 9,  # Organizational direction
            "governance": 10,  # Board oversight
            # Unclassified
            "other": 11,
        }

        # Classify, extract fiscal year, and prioritize PDFs
        prioritized_pdfs = []

        current_year = datetime.now().year

        for pdf_info in pdf_links:
            doc_type = self.pdf_downloader.classify_document_type(pdf_info)
            fiscal_year = self.pdf_downloader.extract_fiscal_year(pdf_info)

            if self.logger:
                self.logger.debug(f"PDF: {pdf_info['url'][:80]} - Type: {doc_type}, Year: {fiscal_year}")

            # Process ALL PDF types - any document could contain valuable structured data
            # (programs, outcomes, theory of change, etc.)

            # Calculate recency score (prefer recent years)
            # If no fiscal year found, assume it's recent (score 0)
            if fiscal_year:
                year_diff = current_year - fiscal_year
                # Only keep PDFs from last 5 years
                if year_diff > 5:
                    if self.logger:
                        self.logger.debug(
                            f"Skipping old PDF ({fiscal_year}, {year_diff} years old): {pdf_info['url'][:80]}"
                        )
                    continue
                recency_score = year_diff  # 0 = current year, 1 = last year, etc.
            else:
                recency_score = 0  # Assume recent if no year found

            priority = priority_order.get(doc_type, 11)  # Default to lowest priority

            # Combined score: (priority * 10) + recency_score
            # This ensures type priority matters more than recency
            # Example: 2024 Form 990 (score 10) beats 2023 Annual Report (score 70)
            combined_score = (priority * 10) + recency_score

            prioritized_pdfs.append((combined_score, fiscal_year or 9999, pdf_info, doc_type))

        # Sort by combined score (lower = better), then by fiscal year (higher = better)
        prioritized_pdfs.sort(key=lambda x: (x[0], -x[1]))

        if self.logger:
            self.logger.info(
                f"Prioritized {len(prioritized_pdfs)} PDFs for download (from {len(pdf_links)} total discovered)"
            )

        # Download top N
        downloaded = 0
        for combined_score, fiscal_year_from_sort, pdf_info, doc_type in prioritized_pdfs[:max_downloads]:
            try:
                # Use fiscal year from prioritization (already extracted)
                fiscal_year = fiscal_year_from_sort if fiscal_year_from_sort != 9999 else None

                # Skip if this URL previously returned 404 (unless already in download_error)
                if "download_error" in pdf_info and "HTTP 404" in pdf_info["download_error"]:
                    if self.logger:
                        self.logger.debug(f"Skipping PDF with previous 404 error: {pdf_info['url']}")
                    pdf_info["downloaded"] = False
                    continue

                # Get storage path
                storage_path = self.pdf_downloader.get_storage_path(
                    charity_id=charity_id or 0, document_type=doc_type, fiscal_year=fiscal_year, url=pdf_info["url"]
                )

                # Skip download if file already exists (cache)
                if storage_path.exists():
                    if self.logger:
                        self.logger.debug(f"PDF already exists, skipping download: {storage_path.name}")
                    success = True
                    error = None
                else:
                    # Download
                    success, error = self.pdf_downloader.download_pdf(
                        url=pdf_info["url"], output_path=storage_path, timeout=30
                    )

                if success:
                    downloaded += 1
                    if self.logger:
                        self.logger.info(f"Downloaded {doc_type} PDF: {storage_path.name}")

                    # Calculate hash for deduplication
                    file_hash = self.pdf_downloader.calculate_file_hash(storage_path)

                    # Update pdf_info with download metadata
                    pdf_info["downloaded"] = True
                    pdf_info["file_path"] = str(storage_path)
                    pdf_info["file_hash"] = file_hash
                    pdf_info["document_type"] = doc_type
                    pdf_info["fiscal_year"] = fiscal_year
                else:
                    # Only log 404s at debug level since they're common and expected
                    if self.logger:
                        if "HTTP 404" in error:
                            self.logger.debug(f"PDF not found (404): {pdf_info['url']}")
                        else:
                            self.logger.warning(f"Failed to download PDF {pdf_info['url']}: {error}")
                    pdf_info["downloaded"] = False
                    pdf_info["download_error"] = error

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error downloading PDF {pdf_info['url']}: {e}")
                pdf_info["downloaded"] = False
                pdf_info["download_error"] = str(e)

        return downloaded

    def _extract_pdf_data(self, pdf_documents: List[dict]) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Extract data from ALL downloaded PDFs using LLM extraction.

        ALL PDFs (Form 990s, annual reports, impact reports, financial statements)
        are processed through LLM for comprehensive data extraction, with a special
        focus on outcomes and impact metrics.

        Args:
            pdf_documents: List of PDF document dicts with downloaded files

        Returns:
            Tuple of (extracted data dict, LLM cost in USD)
        """
        from pathlib import Path

        pdf_data = {
            "address": None,
            "mission": None,
            "programs": [],
            "financial_data": None,
            "outcomes_data": [],  # Array of outcomes from ALL PDFs
            "llm_extracted_pdfs": [],  # Data from each PDF
            "pdf_extraction_sources": [],  # Track which PDFs were extracted
        }
        total_llm_cost = 0.0

        # Get ALL downloaded PDFs
        downloaded_pdfs = [p for p in pdf_documents if p.get("downloaded") and p.get("file_path")]

        if self.logger:
            self.logger.info(f"Running LLM extraction on {len(downloaded_pdfs)} PDFs for outcomes data")

        # Process PDFs through LLM extraction in parallel to speed up (T072)
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # We use a small number of workers per charity to avoid overwhelming API rate limits
        # since multiple charities may be running in parallel already.
        max_pdf_workers = 3

        # Initialize Form990Parser for deterministic extraction (no LLM cost)
        form_990_parser = Form990Parser()

        # Extract dict from report_data safely with consistent tuple returns
        def get_result_and_cost(pdf_info):
            pdf_path = Path(pdf_info["file_path"])
            if not pdf_path.exists():
                if self.logger:
                    self.logger.warning(f"PDF file not found: {pdf_info.get('file_path')}")
                return (None, 0.0, pdf_info)  # Return tuple consistently

            doc_type = pdf_info.get("document_type", "")

            # For Form 990 PDFs, try deterministic parser first (bullet-proof, no LLM cost)
            if doc_type == "form_990":
                try:
                    form_data = form_990_parser.parse_pdf(pdf_path)
                    if form_data and form_data.program_expense_ratio:
                        # Successfully extracted expense data - build result dict
                        result = {
                            "organization_name": form_data.organization_name,
                            "year": form_data.tax_year,
                            "financials": {
                                "total_revenue": form_data.total_revenue,
                                "total_expenses": form_data.total_expenses,
                                "program_expenses": form_data.program_expenses,
                                "management_expenses": form_data.management_expenses,
                                "fundraising_expenses": form_data.fundraising_expenses,
                                "program_expense_ratio": form_data.program_expense_ratio
                                / 100.0,  # Convert from % to decimal
                                "source": "form_990_deterministic",
                            },
                            "programs": [],  # Form990Parser doesn't extract programs
                            "outcomes_summary": {},  # Form990Parser doesn't extract outcomes
                        }
                        if self.logger:
                            self.logger.info(
                                f"Form990Parser extracted: ratio={form_data.program_expense_ratio}% "
                                f"(program=${form_data.program_expenses:,.0f})"
                            )
                        return (result, 0.0, pdf_info)  # No LLM cost
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Form990Parser failed for {pdf_path.name}: {e}, falling back to LLM")
                    # Fall through to LLM extraction

            # Use LLM extraction (for non-990s or when Form990Parser fails)
            report_data, cost = self.annual_report_parser.parse_pdf(pdf_path)

            if not report_data:
                return (None, cost, pdf_info)

            result = self.annual_report_parser.to_dict(report_data)
            return (result, cost, pdf_info)

        with ThreadPoolExecutor(max_workers=max_pdf_workers) as executor:
            future_to_pdf = {executor.submit(get_result_and_cost, pdf_info): pdf_info for pdf_info in downloaded_pdfs}

            for future in as_completed(future_to_pdf):
                try:
                    future_result = future.result()
                    # Defensive: handle unexpected return values
                    if future_result is None or not isinstance(future_result, tuple) or len(future_result) != 3:
                        if self.logger:
                            self.logger.warning(f"Unexpected return value from PDF extraction: {type(future_result)}")
                        continue
                    result, cost, pdf_info = future_result
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"PDF extraction future failed: {e}")
                    continue

                total_llm_cost += cost or 0.0

                if not result:
                    continue

                pdf_path = Path(pdf_info["file_path"])
                doc_type = pdf_info.get("document_type", "unknown")

                # Store full extraction result WITH source attribution for citations
                pdf_data["llm_extracted_pdfs"].append(
                    {
                        "document_type": doc_type,
                        "file_name": pdf_path.name,
                        "fiscal_year": pdf_info.get("fiscal_year"),
                        # Source attribution for proper citations in narratives
                        "source_url": pdf_info.get("url"),  # Original PDF URL
                        "anchor_text": pdf_info.get("anchor_text"),  # Link text (e.g., "2023 Annual Report")
                        "source_page_url": pdf_info.get("source_page"),  # Page where link was found
                        "title": (result.get("organization_name") or "")
                        + (" " + str(result.get("year")) if result.get("year") else ""),
                        "extracted_data": result,
                    }
                )

                # Aggregate outcomes from all PDFs with full source attribution
                if result.get("outcomes_summary"):
                    pdf_data["outcomes_data"].append(
                        {
                            "source": pdf_path.name,
                            "type": doc_type,
                            "fiscal_year": pdf_info.get("fiscal_year") or result.get("year"),
                            "source_url": pdf_info.get("url"),
                            "anchor_text": pdf_info.get("anchor_text"),
                            "organization_name": result.get("organization_name"),
                            "outcomes": result["outcomes_summary"],
                        }
                    )

                # Use first available data for top-level fields
                if not pdf_data["mission"] and result.get("mission"):
                    pdf_data["mission"] = result["mission"]

                if not pdf_data["programs"] and result.get("programs"):
                    pdf_data["programs"] = result["programs"]

                if not pdf_data["financial_data"] and result.get("financials"):
                    pdf_data["financial_data"] = result["financials"]

                pdf_data["pdf_extraction_sources"].append(
                    {
                        "type": doc_type,
                        "file": pdf_path.name,
                        "extraction_method": "llm",
                        "llm_cost_usd": cost,
                        "has_outcomes": bool(result.get("outcomes_summary", {}).get("key_outcomes")),
                    }
                )

                if self.logger:
                    outcomes_count = len(result.get("outcomes_summary", {}).get("key_outcomes", []))
                    programs_count = len(result.get("programs", []))
                    self.logger.info(
                        f"Extracted from {doc_type}: {programs_count} programs, "
                        f"{outcomes_count} outcomes (cost: ${cost:.4f})"
                    )

        # Log summary
        if self.logger and pdf_data["outcomes_data"]:
            total_outcomes = sum(
                len(od.get("outcomes", {}).get("key_outcomes", [])) for od in pdf_data["outcomes_data"]
            )
            self.logger.info(
                f"PDF extraction complete: {len(pdf_data['llm_extracted_pdfs'])} PDFs processed, "
                f"{total_outcomes} total outcomes found, cost: ${total_llm_cost:.4f}"
            )

        return pdf_data, total_llm_cost

    def collect_multi_page(
        self, url: str, ein: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Collect data from charity website using multi-page crawling.

        This method crawls multiple pages (homepage, about, contact, donate, etc.)
        to find EIN and other information that may not be on the homepage.

        Smart crawler (004-smart-crawler) integration:
        - Tries sitemap.xml first for URL discovery
        - Falls back to link-following (BFS) if sitemap unavailable
        - Enforces crawl budget (max 25 pages with sitemap, 40 without)

        Args:
            url: Website URL (starting point)
            ein: EIN for validation (optional)

        Returns:
            Tuple of (success, data, error_message)
            data contains:
                - website_profile: Validated WebsiteProfile dict
                - raw_html: Full HTML from homepage
                - fetch_timestamp: When fetched
                - crawl_stats: Statistics about the crawl
        """
        if self.logger:
            self.logger.debug(f"Starting multi-page crawl: {url}")

        # Reset captcha error tracking for this crawl
        self._last_captcha_error = None

        # Timing trackers
        timing = {
            "sitemap_discovery": 0.0,
            "content_scoring": 0.0,
            "page_crawling": 0.0,
            "llm_extraction": 0.0,
            "pdf_download": 0.0,
            "pdf_extraction": 0.0,
            "total": 0.0,
        }
        crawl_start = time.time()

        try:
            # Step 1: Try sitemap-based URL discovery first (T044)
            sitemap_used = False
            target_urls = []
            pages_scored = 0

            sitemap_start = time.time()
            sitemap_success, sitemap_urls = self._discover_urls_from_sitemap(url, max_pages=CRAWLER_CONFIG["max_pages"])
            timing["sitemap_discovery"] = round(time.time() - sitemap_start, 1)
            if sitemap_success and sitemap_urls:
                sitemap_used = True
                target_urls = sitemap_urls
                pages_scored = len(sitemap_urls)
                if self.logger:
                    self.logger.info(f"Using sitemap mode: {len(sitemap_urls)} URLs selected")
            else:
                # Fallback to link-following mode (T045)
                if self.logger:
                    self.logger.info("Using link-following mode (no sitemap found)")

            # Step 2: Crawl website (async for ~5x speedup)
            crawl_phase_start = time.time()
            if sitemap_used:
                # Async crawl specific URLs from sitemap (parallel fetching)
                crawl_results = self._crawl_specific_urls_async(
                    urls=target_urls, timeout_total=CRAWLER_CONFIG["timeout_total"]
                )
            else:
                # Fallback: Async BFS crawling (parallel level-by-level fetching)
                crawl_results = self._crawl_with_bfs_async(
                    start_url=url,
                    max_depth=CRAWLER_CONFIG["max_depth"],
                    max_pages=CRAWLER_CONFIG["max_pages"],
                    timeout_total=CRAWLER_CONFIG["timeout_total"],
                )
            timing["page_crawling"] = round(time.time() - crawl_phase_start, 1)

            if not crawl_results:
                # Return specific captcha error if detected, otherwise generic message
                error_msg = self._last_captcha_error or "No data found on any pages"
                return False, None, error_msg

            # Step 2: Aggregate data from all pages
            aggregated_data = self._aggregate_crawl_data(crawl_results, url)

            # Step 2.5: Enhance with LLM extraction if enabled
            llm_extraction_start = time.time()
            llm_cost = 0.0
            if self.use_llm and self.llm_extractor:
                try:
                    # Collect HTML pages for LLM
                    pages_for_llm = []
                    for page_url, page_data in list(crawl_results.items())[:10]:  # Max 10 pages
                        # Re-fetch to get HTML (crawl_results only has extracted data)
                        success, html, final_url, error = self._fetch_url(page_url)
                        if success and html:
                            pages_for_llm.append((page_url, html))

                    if pages_for_llm:
                        if self.logger:
                            self.logger.debug(f"Running LLM extraction on {len(pages_for_llm)} pages...")

                        global_rate_limiter.wait("gemini", 1 / 12)  # ~12 QPS limit
                        llm_data, llm_cost = self.llm_extractor.extract(pages_for_llm, url)

                        # Merge LLM data with aggregated data (LLM takes precedence for richer fields)
                        if "error" not in llm_data:
                            aggregated_data = self._merge_llm_data(aggregated_data, llm_data)
                        else:
                            if self.logger:
                                self.logger.warning(f"LLM extraction had errors: {llm_data.get('error')}")

                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"LLM extraction failed: {e}. Using regex-only data.")
            timing["llm_extraction"] = round(time.time() - llm_extraction_start, 1)

            # Step 3: Get homepage content for raw_html
            homepage_html = None
            try:
                self._rate_limit()
                success, homepage_html, final_url, error = self._fetch_url(url)
                if success and homepage_html:
                    soup = BeautifulSoup(homepage_html, "html.parser")

                    # Extract additional fields from homepage (name, mission, programs)
                    # Only extract if not already populated by LLM
                    if not aggregated_data.get("name"):
                        aggregated_data["name"] = self._extract_org_name(soup)
                    if not aggregated_data.get("mission"):
                        aggregated_data["mission"] = self._extract_mission(soup)
                    if not aggregated_data.get("programs"):
                        aggregated_data["programs"] = self._extract_programs(soup)
                elif error:
                    if self.logger:
                        self.logger.warning(f"Could not fetch homepage for additional data: {error}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not process homepage data: {e}")

            # Step 4: Build result (T047: add sitemap metadata, T063: add crawl_metadata, T076: add PDF stats)
            # Calculate LLM usage from aggregated data
            llm_calls_made = len(aggregated_data.get("llm_extractions", []))
            total_extraction_llm_cost = aggregated_data.get("total_llm_cost", 0.0)
            total_llm_cost = llm_cost + total_extraction_llm_cost  # Old LLM + new extraction LLM

            # Get PDF statistics and download priority PDFs
            pdf_documents = aggregated_data.get("pdf_documents", [])
            pdf_count = len(pdf_documents)

            # Download priority PDFs if enabled (T068-T074)
            pdf_download_start = time.time()
            pdfs_downloaded = 0
            pdf_data_extracted = {}
            if self.max_pdf_downloads > 0 and pdf_documents:
                pdfs_downloaded = self._download_priority_pdfs(
                    pdf_links=pdf_documents,
                    charity_id=0,  # We don't have DB ID yet at collection time
                    max_downloads=self.max_pdf_downloads,
                )
                timing["pdf_download"] = round(time.time() - pdf_download_start, 1)
                if self.logger and pdfs_downloaded > 0:
                    self.logger.info(f"Downloaded {pdfs_downloaded}/{pdf_count} priority PDFs")

                # Extract data from downloaded PDFs (Form 990s + annual reports via LLM)
                pdf_extraction_start = time.time()
                pdf_llm_cost = 0.0
                if pdfs_downloaded > 0:
                    pdf_data_extracted, pdf_llm_cost = self._extract_pdf_data(pdf_documents)
                    timing["pdf_extraction"] = round(time.time() - pdf_extraction_start, 1)
                    # Add PDF extraction cost to total
                    total_llm_cost += pdf_llm_cost

                    # Merge PDF data with website data (website data takes priority)
                    # Use PDF as fallback for missing fields
                    if not aggregated_data.get("address") and pdf_data_extracted.get("address"):
                        aggregated_data["address"] = pdf_data_extracted["address"]
                        if self.logger:
                            self.logger.info(f"Using address from PDF: {pdf_data_extracted['address'][:50]}")

                    if not aggregated_data.get("mission") and pdf_data_extracted.get("mission"):
                        aggregated_data["mission"] = pdf_data_extracted["mission"]
                        if self.logger:
                            self.logger.info("Using mission from PDF")

                    if not aggregated_data.get("programs") and pdf_data_extracted.get("programs"):
                        aggregated_data["programs"] = pdf_data_extracted["programs"]
                        if self.logger:
                            self.logger.info(f"Using {len(pdf_data_extracted['programs'])} programs from PDF")

                    # Add LLM-extracted PDF data (outcomes, programs, etc.)
                    if pdf_data_extracted.get("llm_extracted_pdfs"):
                        aggregated_data["llm_extracted_pdfs"] = pdf_data_extracted["llm_extracted_pdfs"]
                        if self.logger:
                            self.logger.info(
                                f"Added LLM-extracted data from {len(pdf_data_extracted['llm_extracted_pdfs'])} PDFs"
                            )

                    # Add aggregated outcomes data (critical for zakat evaluation)
                    if pdf_data_extracted.get("outcomes_data"):
                        aggregated_data["outcomes_data"] = pdf_data_extracted["outcomes_data"]
                        total_outcomes = sum(
                            len(od.get("outcomes", {}).get("key_outcomes", []))
                            for od in pdf_data_extracted["outcomes_data"]
                        )
                        if self.logger:
                            self.logger.info(f"Extracted {total_outcomes} outcomes from PDFs")

                    # Track PDF extraction sources
                    if pdf_data_extracted.get("pdf_extraction_sources"):
                        aggregated_data["pdf_extraction_sources"] = pdf_data_extracted["pdf_extraction_sources"]

                    # Derive transparency_info from PDF metadata
                    auditor_name = pdf_data_extracted.get("auditor_name")
                    if auditor_name or pdfs_downloaded > 0:
                        transparency_parts = []
                        transparency_parts.append(f"{pdfs_downloaded} financial documents available")
                        if auditor_name:
                            transparency_parts.append(f"audited by {auditor_name}")
                        aggregated_data["transparency_info"] = ", ".join(transparency_parts)

            # Rebuild profile data with PDF-enhanced data
            # Use ALL aggregated data instead of hardcoded subset
            extracted_ein = aggregated_data.get("ein")
            if extracted_ein and ein and _normalize_ein(extracted_ein) != _normalize_ein(ein):
                if self.logger:
                    self.logger.warning(
                        f"Website EIN {extracted_ein} doesn't match known EIN {ein} — storing as related_ein"
                    )
                aggregated_data["related_ein"] = extracted_ein
                aggregated_data["ein"] = None
                extracted_ein = None
            profile_data = {
                "url": url,
                "ein": extracted_ein or ein,
            }

            # Add all fields from aggregated_data
            for key, value in aggregated_data.items():
                if key not in profile_data:  # Don't overwrite url and ein
                    profile_data[key] = value

            # Clean social_media dict to remove None values (Pydantic validator issue)
            if "social_media" in profile_data and isinstance(profile_data["social_media"], dict):
                profile_data["social_media"] = {
                    k: v
                    for k, v in profile_data["social_media"].items()
                    if v is not None and isinstance(v, str) and v.strip()
                }

            # Re-validate with PDF-enhanced data
            try:
                profile = WebsiteProfile(**profile_data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Validation error after PDF enhancement: {e}")
                return False, None, f"Validation failed: {e}"

            # Collect JS rendering candidates for future Playwright processing
            js_candidates = []
            for page_url, page_data in crawl_results.items():
                if page_data.get("js_rendering_needed"):
                    js_candidates.append(
                        {
                            "url": page_url,
                            "failure_reason": page_data.get("extraction_failure_reason", "unknown"),
                        }
                    )

            # Build page-level extraction provenance for citations
            # Maps each fact type to the URL where it was found
            page_extractions = []
            for page_url, page_data in crawl_results.items():
                # Track what was extracted from each page
                extracted_fields = []
                for key, value in page_data.items():
                    if value and key not in ("js_rendering_needed", "extraction_failure_reason"):
                        extracted_fields.append(key)
                if extracted_fields:
                    page_extractions.append(
                        {
                            "url": page_url,
                            "extracted_fields": extracted_fields,
                        }
                    )

            # Calculate total timing
            timing["total"] = round(time.time() - crawl_start, 1)

            result = {
                "website_profile": profile.model_dump(),
                "raw_content": homepage_html or "",
                "fetch_timestamp": datetime.now().isoformat(),
                "pdf_documents": pdf_documents,  # T076: PDF links discovered
                "js_rendering_candidates": js_candidates,  # Pages needing Playwright
                "page_extractions": page_extractions,  # Maps URLs to extracted fields for citations
                "crawl_stats": {
                    "pages_visited": len(crawl_results),
                    "pages_with_data": len([r for r in crawl_results.values() if any(r.values())]),
                    "pages_needing_js": len(js_candidates),  # Pages likely needing Playwright
                    "ein_found": bool(aggregated_data.get("ein")),
                    "ein_source": [url for url, data in crawl_results.items() if data.get("ein")],
                    "llm_used": self.use_llm and self.llm_extractor is not None,
                    "llm_cost": total_llm_cost,  # Total LLM cost (old + new)
                    "llm_calls_made": llm_calls_made,  # Number of LLM extraction calls (T063)
                    "sitemap_used": sitemap_used,  # T047
                    "pages_scored": pages_scored,  # T047
                    "pages_crawled": len(crawl_results),  # T063
                    "pdfs_discovered": pdf_count,  # T076: Number of PDFs found
                    "pdfs_downloaded": pdfs_downloaded,  # T068-T074: Number of PDFs downloaded
                    "timing": timing,  # Latency breakdown for each step
                },
            }

            if self.logger:
                self.logger.debug(f"Multi-page crawl successful: {result['crawl_stats']}")
                if js_candidates:
                    self.logger.info(
                        f"Found {len(js_candidates)} pages needing JS rendering (Playwright): "
                        f"{[c['url'][:50] + '...' for c in js_candidates[:3]]}"
                    )

            # Save cache state for progressive exploration
            self.cache.save_state(url)

            # Cleanup Playwright browser
            self._cleanup_playwright()

            return True, result, None

        except Exception as e:
            if self.logger:
                self.logger.error(f"Multi-page crawl failed: {str(e)}")
            # Cleanup Playwright browser
            self._cleanup_playwright()
            # Save cache state even on failure
            try:
                self.cache.save_state(url)
            except Exception:
                pass  # Don't fail the entire crawl if state save fails
            return False, None, f"Crawl failed: {str(e)}"

    def collect_single_page(
        self, url: str, ein: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Collect data from charity website (single page only) - LEGACY method.

        Deprecated: Use BaseCollector's collect(ein, url=...) instead for standard interface.
        For multi-page crawling (to find EIN on secondary pages), use collect_multi_page().

        Args:
            url: Website URL
            ein: EIN for validation (optional)

        Returns:
            Tuple of (success, data, error_message)
            data contains:
                - website_profile: Validated WebsiteProfile dict
                - raw_content: Full HTML
                - fetch_timestamp: When fetched
        """
        if self.logger:
            self.logger.debug(f"Fetching website: {url}")

        self._rate_limit()

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)

            if response.status_code != 200:
                return False, None, f"HTTP {response.status_code}"

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            # Comprehensive extraction
            extracted_ein = self._extract_ein(soup)
            related_ein = None
            if extracted_ein and ein and _normalize_ein(extracted_ein) != _normalize_ein(ein):
                if self.logger:
                    self.logger.warning(
                        f"Website EIN {extracted_ein} doesn't match known EIN {ein} — storing as related_ein"
                    )
                related_ein = extracted_ein
                extracted_ein = None
            profile_data = {
                "url": url,
                "name": self._extract_org_name(soup),
                "mission": self._extract_mission(soup),
                "programs": self._extract_programs(soup),
                "contact_email": self._extract_email(soup),
                "contact_phone": self._extract_phone(soup),
                "address": self._extract_address(soup),
                "ein": extracted_ein or ein,
                "related_ein": related_ein,
                "donate_url": self._extract_donate_url(soup, url),
                "social_media": self._extract_social_media(soup),
                "tax_deductible": self._extract_tax_deductible(soup),
            }

            # Validate
            try:
                profile = WebsiteProfile(**profile_data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Validation error: {e}")
                return False, None, f"Validation failed: {e}"

            result = {
                "website_profile": profile.model_dump(),
                "raw_content": html,
                "fetch_timestamp": datetime.now().isoformat(),
            }

            if self.logger:
                self.logger.debug("Successfully collected website data")

            return True, result, None

        except requests.Timeout:
            return False, None, f"Request timeout after {self.timeout}s"
        except requests.RequestException as e:
            return False, None, f"Request failed: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"

    def _extract_page_data(self, html: str, url: str, use_llm: bool = False) -> Dict[str, Any]:
        """
        Extract all data from a page using smart extractors (004-smart-crawler).

        Uses structured data extraction, deterministic regex, and optionally LLM for semantic fields.
        Tracks provenance for each extracted field (T028).

        Args:
            html: HTML content
            url: Page URL
            use_llm: Whether to use LLM for semantic field extraction (T058-T059)

        Returns:
            Dict with extracted fields: ein, email, phone, address, donate_url, social_media, tax_deductible
            Plus extraction_results array with provenance tracking
            Plus llm_data if use_llm=True
        """
        # T056: Extract structured data (JSON-LD, Open Graph, microdata)
        structured_data = self.structured_extractor.extract(html, url)

        # Extract deterministic fields (regex-based)
        ein = self.deterministic_extractor.extract_ein(html)
        contact = self.deterministic_extractor.extract_contact_info(html)
        social = self.deterministic_extractor.extract_social_media(html)
        donate_urls = self.deterministic_extractor.extract_donate_urls(html, url)

        # Extract address from structured data
        address = self._extract_address_from_structured_data(structured_data)

        # Extract tax deductible from text
        soup = BeautifulSoup(html, "html.parser")
        tax_deductible = self._extract_tax_deductible(soup)

        # Build extraction results with provenance (T028)
        extraction_results = []

        if ein:
            extraction_results.append(
                {
                    "field_name": "ein",
                    "field_value": ein,
                    "extraction_source": "regex-ein",
                    "confidence_score": 1.0,
                    "page_url": url,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        if contact.get("email"):
            extraction_results.append(
                {
                    "field_name": "contact_email",
                    "field_value": contact["email"],
                    "extraction_source": "regex-contact",
                    "confidence_score": 0.95,
                    "page_url": url,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        if contact.get("phone"):
            extraction_results.append(
                {
                    "field_name": "contact_phone",
                    "field_value": contact["phone"],
                    "extraction_source": "regex-contact",
                    "confidence_score": 0.90,
                    "page_url": url,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        if social:
            extraction_results.append(
                {
                    "field_name": "social_media",
                    "field_value": social,
                    "extraction_source": "regex-social",
                    "confidence_score": 0.95,
                    "page_url": url,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        if donate_urls:
            extraction_results.append(
                {
                    "field_name": "donate_url",
                    "field_value": donate_urls[0],
                    "extraction_source": "regex-donate",
                    "confidence_score": 0.85,
                    "page_url": url,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        if tax_deductible is not None:
            extraction_results.append(
                {
                    "field_name": "tax_deductible",
                    "field_value": tax_deductible,
                    "extraction_source": "regex-tax",
                    "confidence_score": 0.80,
                    "page_url": url,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        if address:
            extraction_results.append(
                {
                    "field_name": "address",
                    "field_value": address,
                    "extraction_source": "structured-jsonld",
                    "confidence_score": 0.90,
                    "page_url": url,
                    "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # T058-T059: LLM extraction for semantic fields (only if requested)
        llm_data = None
        llm_cost = 0.0
        js_rendering_needed = False
        extraction_failure_reason = None

        if use_llm and self.llm_extractor:
            try:
                # T058: Clean text for LLM using TextCleaner
                # Try precision mode first, fallback to relaxed mode if empty
                cleaned_text = self.text_cleaner.clean_for_llm(html, favor_precision=True)

                if not cleaned_text or len(cleaned_text) <= 100:
                    # Precision mode too aggressive - try relaxed mode
                    cleaned_text = self.text_cleaner.clean_for_llm(html, favor_precision=False)

                if not cleaned_text:
                    # No extractable content - likely JS-rendered page
                    js_rendering_needed = True
                    extraction_failure_reason = "empty_content"
                    if self.logger:
                        self.logger.info(f"JS rendering needed (empty content): {url}")
                elif len(cleaned_text) <= 100:
                    # Too short - could be JS-heavy or minimal content page
                    js_rendering_needed = True
                    extraction_failure_reason = "too_short"
                    if self.logger:
                        self.logger.info(f"JS rendering needed (content too short: {len(cleaned_text)} chars): {url}")

                if cleaned_text and len(cleaned_text) > 100:
                    # Classify page type for appropriate prompt selection
                    from urllib.parse import urlparse

                    url_path = urlparse(url).path.lower()

                    # Determine page type
                    page_type = "homepage"  # default
                    if url_path in ["/", ""]:
                        page_type = "homepage"
                    elif any(kw in url_path for kw in ["zakat", "zakaat", "zakah"]):
                        page_type = "zakat"  # Zakat pages get special extraction
                    elif any(kw in url_path for kw in ["about", "mission", "who-we-are"]):
                        page_type = "about"
                    elif any(kw in url_path for kw in ["program", "what-we-do", "service"]):
                        page_type = "programs"
                    elif any(kw in url_path for kw in ["impact", "result", "outcome"]):
                        page_type = "impact"
                    elif any(kw in url_path for kw in ["donat", "give", "giving"]):
                        page_type = "donate"
                    elif any(kw in url_path for kw in ["contact", "reach-us", "team", "leadership", "board"]):
                        page_type = "contact"

                    # T059: Extract with page-specific prompt and schema
                    global_rate_limiter.wait("gemini", 1 / 12)  # ~12 QPS limit
                    llm_response, llm_cost = self.llm_extractor.extract_with_schema(
                        page_text=cleaned_text, page_type=page_type, page_url=url
                    )

                    if llm_response:
                        # Convert Pydantic model to dict for storage
                        llm_data = llm_response.model_dump()

                        # Add to extraction results
                        extraction_results.append(
                            {
                                "field_name": "llm_semantic_fields",
                                "field_value": llm_data,
                                "extraction_source": f"llm-{page_type}",
                                "confidence_score": 0.85,
                                "page_url": url,
                                "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                                "llm_cost": llm_cost,
                            }
                        )

                        if self.logger:
                            self.logger.debug(
                                f"LLM extracted {len(llm_data)} semantic fields from {page_type} page (cost: ${llm_cost:.4f})"
                            )

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"LLM extraction failed for {url}: {e}")

        # T075: Discover PDF documents on this page
        pdf_links = []
        try:
            pdf_links = self.pdf_downloader.identify_pdfs(html, url)
            if pdf_links and self.logger:
                self.logger.debug(f"Found {len(pdf_links)} PDF documents on {url}")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"PDF discovery failed on {url}: {e}")

        # Zakat detection: check for zakat keywords in page content
        zakat_detected = False
        zakat_keywords_found = []
        html_lower = html.lower()
        for keyword in self.page_classifier.CONTENT_BOOST_KEYWORDS:
            if keyword in html_lower:
                zakat_detected = True
                zakat_keywords_found.append(keyword)
        if zakat_detected and self.logger:
            self.logger.debug(f"Zakat keywords found on {url}: {zakat_keywords_found[:3]}")

        # Determine if this page had useful data
        # Consider data "useful" if we found: EIN, contact info, social media, donate URL, address, or PDFs
        had_data = bool(
            ein
            or contact.get("email")
            or contact.get("phone")
            or address
            or social
            or donate_urls
            or pdf_links
            or llm_data
        )

        # Build page data
        page_data = {
            "ein": ein,
            "email": contact.get("email"),
            "phone": contact.get("phone"),
            "address": address,  # Extracted from structured data
            "donate_url": donate_urls[0] if donate_urls else None,
            "social_media": social,
            "tax_deductible": tax_deductible,
            "structured_data": structured_data,  # Store for provenance
            "extraction_results": extraction_results,  # Provenance tracking (T028)
            "llm_data": llm_data,  # Semantic fields from LLM (T059)
            "llm_cost": llm_cost,  # Track LLM costs
            "pdf_links": pdf_links,  # PDF documents found on this page (T075)
            "had_data": had_data,  # Whether this page yielded useful data
            "js_rendering_needed": js_rendering_needed,  # Flag for Playwright processing
            "extraction_failure_reason": extraction_failure_reason,  # Why extraction failed
            "zakat_detected": zakat_detected,  # Whether zakat keywords found on this page
            "zakat_keywords": zakat_keywords_found,  # Which zakat keywords were found
        }

        return page_data

    def _extract_org_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract organization name from website."""
        # Try title tag
        if soup.title:
            return soup.title.string.split("|")[0].strip()
        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()
        return None

    def _extract_mission(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract mission statement."""
        # Look for mission-related headings
        mission_keywords = ["mission", "about", "who we are", "what we do"]
        for keyword in mission_keywords:
            heading = soup.find(["h1", "h2", "h3"], string=lambda x: x and keyword in x.lower())
            if heading:
                # Get next paragraph
                next_p = heading.find_next("p")
                if next_p:
                    return next_p.get_text().strip()
        return None

    def _extract_programs(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract program list with improved heuristics.

        Tries multiple strategies:
        1. Headings + lists (original)
        2. Card/grid layouts (common for programs)
        3. Navigation menus with program links
        4. Structured headings (h2/h3 under "programs" section)
        """
        programs = []

        # Strategy 1: Look for programs section with lists
        prog_keywords = ["programs", "services", "what we do", "our work", "initiatives", "projects"]
        for keyword in prog_keywords:
            heading = soup.find(["h1", "h2", "h3"], string=lambda x: x and keyword in x.lower())
            if heading:
                # Find next ul/ol
                list_elem = heading.find_next(["ul", "ol"])
                if list_elem:
                    programs = [li.get_text().strip() for li in list_elem.find_all("li")]
                    if len(programs) >= 2:  # At least 2 programs to be valid
                        return programs[:10]  # Cap at 10

        # Strategy 2: Look for card/grid layouts (divs with program-like classes)
        # Common patterns: program-card, service-item, initiative-box
        card_patterns = ["program", "service", "initiative", "project", "focus-area", "impact-area", "pillar", "cause"]

        for pattern in card_patterns:
            cards = soup.find_all(["div", "article", "section"], class_=lambda x: x and pattern in x.lower())
            if cards and len(cards) >= 2:
                # Extract title from each card (h2, h3, h4, or strong)
                for card in cards[:10]:  # Cap at 10
                    title_elem = card.find(["h2", "h3", "h4", "strong"])
                    if title_elem:
                        title = title_elem.get_text().strip()
                        if title and len(title) < 100:  # Reasonable title length
                            programs.append(title)
                if len(programs) >= 2:
                    return programs[:10]

        # Strategy 3: Look for section with multiple h2/h3 headings
        # (common pattern: programs section with each program as a heading)
        for keyword in prog_keywords:
            section = soup.find(["section", "div"], class_=lambda x: x and keyword in x.lower() if x else False)
            if section:
                # Find all h2/h3 within this section
                headings = section.find_all(["h2", "h3"], limit=10)
                if len(headings) >= 2:
                    programs = [h.get_text().strip() for h in headings]
                    programs = [p for p in programs if len(p) < 100]  # Filter out long text
                    if len(programs) >= 2:
                        return programs[:10]

        # Strategy 4: Navigation menu with program links
        # Look for nav with "programs" or "what we do"
        nav = soup.find("nav", class_=lambda x: x and any(kw in x.lower() for kw in prog_keywords) if x else False)
        if nav:
            links = nav.find_all("a", limit=10)
            programs = [a.get_text().strip() for a in links]
            programs = [p for p in programs if p and len(p) < 100]
            if len(programs) >= 2:
                return programs[:10]

        return programs

    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract contact email."""
        # Look for mailto links
        mailto = soup.find("a", href=lambda x: x and "mailto:" in x)
        if mailto:
            return mailto["href"].replace("mailto:", "").split("?")[0]
        return None

    def _extract_ein(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract EIN from website text."""
        import re

        # Get all text
        text = soup.get_text()

        # Pattern: EIN: XX-XXXXXXX or Tax ID: XX-XXXXXXX or just XX-XXXXXXX in context
        patterns = [
            r"EIN:?\s*([0-9]{2}-?[0-9]{7})",
            r"Tax\s*ID:?\s*([0-9]{2}-?[0-9]{7})",
            r"Federal\s*Tax\s*ID:?\s*([0-9]{2}-?[0-9]{7})",
            r"501\(c\)\(3\)[^\d]*([0-9]{2}-?[0-9]{7})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ein = match.group(1).replace("-", "")
                if len(ein) == 9 and ein.isdigit():
                    return f"{ein[:2]}-{ein[2:]}"

        return None

    def _extract_phone(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract phone number."""
        import re

        # Look for tel: links first
        tel_link = soup.find("a", href=lambda x: x and "tel:" in x)
        if tel_link:
            return tel_link.get_text().strip()

        # Pattern matching in text
        text = soup.get_text()
        phone_patterns = [
            r"(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})",
            r"\((\d{3})\)\s*\d{3}[-.\s]?\d{4}",
        ]

        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()

        return None

    def _extract_address_from_structured_data(self, structured_data: Dict) -> Optional[str]:
        """
        Extract address from JSON-LD Organization schema.

        Args:
            structured_data: Structured data dict with json_ld field

        Returns:
            Formatted address string or None
        """
        if not structured_data.get("json_ld"):
            return None

        for item in structured_data["json_ld"]:
            if item.get("@type") == "Organization":
                address = item.get("address", {})
                if isinstance(address, dict):
                    parts = []
                    if address.get("streetAddress"):
                        parts.append(address["streetAddress"])
                    if address.get("addressLocality"):
                        parts.append(address["addressLocality"])
                    if address.get("addressRegion"):
                        parts.append(address["addressRegion"])
                    if address.get("postalCode"):
                        parts.append(address["postalCode"])
                    if parts:
                        return ", ".join(parts)
        return None

    def _extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract physical address."""
        # Look for address tags or schema.org markup
        address = soup.find("address")
        if address:
            return address.get_text().strip().replace("\n", ", ")

        # Look for schema.org address
        address_schema = soup.find(attrs={"itemprop": "address"})
        if address_schema:
            return address_schema.get_text().strip().replace("\n", ", ")

        return None

    def _extract_donate_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract donation page URL."""
        # Look for links with donate-related text or URLs
        donate_keywords = ["donate", "give", "contribute", "support"]

        for keyword in donate_keywords:
            # Check link text
            link = soup.find("a", string=lambda x: x and keyword in x.lower())
            if link and link.get("href"):
                href = link["href"]
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    from urllib.parse import urljoin

                    return urljoin(base_url, href)

            # Check href attribute
            link = soup.find("a", href=lambda x: x and keyword in x.lower())
            if link:
                href = link["href"]
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    from urllib.parse import urljoin

                    return urljoin(base_url, href)

        return None

    def _extract_social_media(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media links."""
        social_media = {}

        platforms = {
            "facebook": r'facebook\.com/[^/"\s]+',
            "twitter": r'twitter\.com/[^/"\s]+',
            "instagram": r'instagram\.com/[^/"\s]+',
            "linkedin": r'linkedin\.com/(company|in)/[^/"\s]+',
            "youtube": r'youtube\.com/(c|channel|user)/[^/"\s]+',
        }

        import re

        page_html = str(soup)

        for platform, pattern in platforms.items():
            match = re.search(pattern, page_html, re.IGNORECASE)
            if match:
                social_media[platform] = f"https://{match.group(0)}"

        return social_media

    def _extract_tax_deductible(self, soup: BeautifulSoup) -> Optional[bool]:
        """Check if donations are tax-deductible."""
        import re

        text = soup.get_text()

        # Look for tax-deductible mentions
        patterns = [
            r"tax[- ]deductible",
            r"501\(c\)\(3\)",
            r"donations?\s+are\s+deductible",
        ]

        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return None

    def calculate_field_completion(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate field completion metrics for a charity profile.

        Used to determine when a charity is "complete" and can be skipped on future crawls.
        Zakat-specific fields are weighted 2x because they're priority for the platform.

        Returns:
            Dict with:
            - field_completion_pct: Overall completion percentage (0-100)
            - core_complete: True if core fields are filled (name, ein, mission)
            - contact_complete: True if contact info is filled (email or phone + address)
            - financial_complete: True if any financial data available
            - zakat_complete: True if zakat-specific fields are filled
            - fields_filled: List of filled field names
            - fields_missing: List of missing field names
        """
        # Define field groups and their weights
        # Core fields (required for basic profile)
        core_fields = ["name", "ein", "mission"]

        # Contact fields
        contact_fields = ["contact_email", "contact_phone", "address"]

        # Financial/donation fields
        financial_fields = ["donate_url", "annual_revenue", "annual_expenses", "tax_deductible"]

        # Note: Zakat fields handled by discover.py, not website extraction
        zakat_fields = []

        # Additional enrichment fields
        enrichment_fields = [
            "programs",
            "populations_served",
            "geographic_coverage",
            "impact_metrics",
            "leadership",
            "social_media",
            "volunteer_opportunities",
            "founded_year",
        ]

        def is_filled(value):
            """Check if a field value is considered 'filled'."""
            if value is None:
                return False
            if isinstance(value, str) and not value.strip():
                return False
            if isinstance(value, (list, dict)) and len(value) == 0:
                return False
            return True

        # Calculate completion for each group
        core_filled = [f for f in core_fields if is_filled(profile_data.get(f))]
        contact_filled = [f for f in contact_fields if is_filled(profile_data.get(f))]
        financial_filled = [f for f in financial_fields if is_filled(profile_data.get(f))]
        zakat_filled = [f for f in zakat_fields if is_filled(profile_data.get(f))]
        enrichment_filled = [f for f in enrichment_fields if is_filled(profile_data.get(f))]

        # Calculate weighted completion percentage
        # Weights: core=30%, contact=15%, financial=15%, zakat=25%, enrichment=15%
        core_pct = len(core_filled) / len(core_fields) if core_fields else 0
        contact_pct = len(contact_filled) / len(contact_fields) if contact_fields else 0
        financial_pct = len(financial_filled) / len(financial_fields) if financial_fields else 0
        zakat_pct = len(zakat_filled) / len(zakat_fields) if zakat_fields else 0
        enrichment_pct = len(enrichment_filled) / len(enrichment_fields) if enrichment_fields else 0

        weighted_pct = (
            core_pct * 0.30
            + contact_pct * 0.15
            + financial_pct * 0.15
            + zakat_pct * 0.25  # Zakat fields weighted higher
            + enrichment_pct * 0.15
        ) * 100

        # Determine group completeness
        # Core: at least name and ein
        core_complete = is_filled(profile_data.get("name")) and is_filled(profile_data.get("ein"))

        # Contact: either email or phone, plus address preferred
        contact_complete = is_filled(profile_data.get("contact_email")) or is_filled(profile_data.get("contact_phone"))

        # Financial: donate URL is the key indicator
        financial_complete = is_filled(profile_data.get("donate_url"))

        # Zakat: handled by discover.py, always False for website extraction
        zakat_complete = False

        # Collect all fields
        all_fields = core_fields + contact_fields + financial_fields + zakat_fields + enrichment_fields
        fields_filled = [f for f in all_fields if is_filled(profile_data.get(f))]
        fields_missing = [f for f in all_fields if not is_filled(profile_data.get(f))]

        return {
            "field_completion_pct": round(weighted_pct, 1),
            "core_complete": core_complete,
            "contact_complete": contact_complete,
            "financial_complete": financial_complete,
            "zakat_complete": zakat_complete,
            "fields_filled": fields_filled,
            "fields_missing": fields_missing,
            "total_filled": len(fields_filled),
            "total_fields": len(all_fields),
        }

    def should_mark_complete(self, profile_data: Dict[str, Any], crawls_without_new_data: int = 0) -> Tuple[bool, str]:
        """
        Determine if a charity should be marked as 'complete' and skipped in future crawls.

        Completion criteria (both must be met):
        1. 2+ crawls with no new data found, OR
        2. 90%+ field completion

        Args:
            profile_data: Extracted charity profile data
            crawls_without_new_data: Number of consecutive crawls with no new data

        Returns:
            Tuple of (should_mark_complete, reason)
        """
        completion = self.calculate_field_completion(profile_data)
        field_pct = completion["field_completion_pct"]

        # Criterion 1: High field completion (90%+)
        if field_pct >= 90.0:
            return True, f"Field completion {field_pct}% >= 90% threshold"

        # Criterion 2: Multiple crawls with no new data (2+)
        if crawls_without_new_data >= 2:
            return True, f"No new data after {crawls_without_new_data} crawls"

        # Not complete yet
        return False, f"Field completion {field_pct}%, crawls without new data: {crawls_without_new_data}"

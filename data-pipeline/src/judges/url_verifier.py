"""URL verification with caching for citation validation.

Fetches URLs and extracts text content for LLM verification.
Caches results to avoid redundant requests across charities.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# URLs that don't need verification (trusted sources)
SKIP_DOMAINS = {
    "irs.gov",  # Form 990 always valid
    "propublica.org",  # ProPublica nonprofit explorer
    "charitynavigator.org",  # Official CN profiles
}

# Maximum content to cache per URL
MAX_CONTENT_CHARS = 10000


@dataclass
class FetchResult:
    """Result of fetching a URL.

    Attributes:
        success: Whether the fetch succeeded
        content: Extracted text content (if success)
        error: Error message (if not success)
        status_code: HTTP status code (if request was made)
        content_type: Content-Type header from response
        cached: Whether this result was from cache
        fetch_time_ms: Time taken to fetch (0 if cached)
    """

    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    cached: bool = False
    fetch_time_ms: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dict for caching."""
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "status_code": self.status_code,
            "content_type": self.content_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FetchResult":
        """Restore from cached dict."""
        return cls(
            success=data["success"],
            content=data.get("content"),
            error=data.get("error"),
            status_code=data.get("status_code"),
            content_type=data.get("content_type"),
            cached=True,
        )


@dataclass
class URLCache:
    """Simple file-based cache for URL fetch results.

    Caches results as JSON files keyed by URL hash.
    TTL-based expiration to avoid stale content.
    """

    cache_dir: Path
    ttl_days: int = 7
    _stats: dict = field(default_factory=lambda: {"hits": 0, "misses": 0})

    def __post_init__(self):
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for a URL."""
        key = self._get_cache_key(url)
        return self.cache_dir / f"{key}.json"

    def get(self, url: str) -> Optional[FetchResult]:
        """Get cached result for URL, or None if not cached/expired."""
        cache_path = self._get_cache_path(url)

        if not cache_path.exists():
            self._stats["misses"] += 1
            return None

        try:
            data = json.loads(cache_path.read_text())
            cached_at = datetime.fromisoformat(data["cached_at"])
            # Ensure timezone-aware (old cache entries may lack tzinfo)
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            expires_at = cached_at + timedelta(days=self.ttl_days)

            if datetime.now(timezone.utc) > expires_at:
                # Expired - delete and return None
                cache_path.unlink()
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            return FetchResult.from_dict(data["result"])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.debug(f"Cache read error for {url}: {e}")
            self._stats["misses"] += 1
            return None

    def set(self, url: str, result: FetchResult) -> None:
        """Cache a fetch result."""
        cache_path = self._get_cache_path(url)
        data = {
            "url": url,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "result": result.to_dict(),
        }
        cache_path.write_text(json.dumps(data))

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._stats["hits"] + self._stats["misses"]
        return self._stats["hits"] / total if total > 0 else 0.0


class URLVerifier:
    """Fetches and caches URL content for citation verification.

    Extracts text from HTML pages for LLM verification.
    Handles common errors gracefully with informative messages.
    """

    def __init__(
        self,
        cache_dir: Path,
        timeout: int = 10,
        ttl_days: int = 7,
        max_content_chars: int = MAX_CONTENT_CHARS,
    ):
        """Initialize the URL verifier.

        Args:
            cache_dir: Directory for caching fetch results
            timeout: HTTP request timeout in seconds
            ttl_days: Cache TTL in days
            max_content_chars: Max chars to keep from fetched content
        """
        self.cache = URLCache(cache_dir, ttl_days=ttl_days)
        self.timeout = timeout
        self.max_content_chars = max_content_chars
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "AmalMetric-CitationVerifier/1.0 (+https://amalmetric.org)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
        return self._client

    def should_skip(self, url: str) -> tuple[bool, Optional[str]]:
        """Check if URL should be skipped (trusted source).

        Returns:
            (should_skip, skip_reason) tuple
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]

            for skip_domain in SKIP_DOMAINS:
                if domain.endswith(skip_domain):
                    return True, f"Trusted source: {skip_domain}"

            return False, None
        except Exception:
            return False, None

    def fetch(self, url: str, skip_cache: bool = False) -> FetchResult:
        """Fetch URL content for verification.

        Args:
            url: URL to fetch
            skip_cache: If True, bypass cache

        Returns:
            FetchResult with content or error
        """
        # Check cache first
        if not skip_cache:
            cached = self.cache.get(url)
            if cached is not None:
                return cached

        start_time = time.time()

        try:
            client = self._get_client()
            response = client.get(url)
            fetch_time_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                content = self._extract_text(response)
                result = FetchResult(
                    success=True,
                    content=content[: self.max_content_chars],
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    fetch_time_ms=fetch_time_ms,
                )
            else:
                result = FetchResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    fetch_time_ms=fetch_time_ms,
                )
        except httpx.TimeoutException:
            result = FetchResult(
                success=False,
                error=f"Timeout after {self.timeout}s",
                fetch_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.ConnectError as e:
            result = FetchResult(
                success=False,
                error=f"Connection error: {str(e)[:100]}",
                fetch_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            result = FetchResult(
                success=False,
                error=f"Fetch error: {type(e).__name__}: {str(e)[:100]}",
                fetch_time_ms=(time.time() - start_time) * 1000,
            )

        # Cache result (including failures to avoid repeated attempts)
        self.cache.set(url, result)

        return result

    def _extract_text(self, response: httpx.Response) -> str:
        """Extract readable text from HTTP response.

        Handles HTML and plain text. Uses BeautifulSoup for HTML parsing.
        """
        content_type = response.headers.get("content-type", "").lower()

        if "text/html" in content_type or "application/xhtml" in content_type:
            return self._extract_html_text(response.text)
        elif "text/plain" in content_type:
            return response.text
        elif "application/json" in content_type:
            # Return formatted JSON for API responses
            try:
                data = response.json()
                return json.dumps(data, indent=2)
            except json.JSONDecodeError:
                return response.text
        else:
            # Try HTML parsing as fallback
            return self._extract_html_text(response.text)

    def _extract_html_text(self, html: str) -> str:
        """Extract readable text from HTML.

        Removes scripts, styles, and extracts main content.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        # Get text with whitespace normalization
        text = soup.get_text(separator=" ", strip=True)

        # Collapse multiple whitespace
        import re

        text = re.sub(r"\s+", " ", text)

        return text

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cache_hit_rate": self.cache.hit_rate,
            "cache_hits": self.cache._stats["hits"],
            "cache_misses": self.cache._stats["misses"],
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

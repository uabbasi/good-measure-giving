"""
Crawler cache and state tracking for smart web crawler.

Features:
- Aggressive HTTP response caching to avoid re-downloading pages
- Track pages that yielded no results (for progressive exploration)
- Persist cache across runs for efficiency
- TTL-based expiration for stale data (default 180 days)
- HTTP Last-Modified and ETag header storage for conditional fetching
- Content hashing (SHA256) for detecting actual page changes
- Schema version tracking for auto re-extraction
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

# Current extraction schema version - increment when adding new fields
CURRENT_SCHEMA_VERSION = "2.0"


class CrawlerCache:
    """
    Cache for web crawler with aggressive caching and state tracking.

    Features:
    1. HTTP response caching with TTL
    2. Track "empty" pages (crawled but no useful data)
    3. Track "tried" URLs to avoid duplicate work
    4. Persist state across runs
    """

    def __init__(self, cache_dir: Path, ttl_days: int = 180, logger=None):
        """
        Initialize crawler cache.

        Args:
            cache_dir: Directory for cache storage
            ttl_days: Time-to-live for cached responses in days (default 180)
            logger: Logger instance
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_days = ttl_days
        self.logger = logger

        # Create cache directory structure
        self.html_cache_dir = self.cache_dir / "html"
        self.state_dir = self.cache_dir / "state"
        self.html_cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # In-memory tracking for current session
        self.pages_with_no_data: Set[str] = set()  # Tried but found nothing useful
        self.pages_with_data: Set[str] = set()  # Tried and found useful data
        self.tried_urls: Set[str] = set()  # All URLs attempted
        self.pages_needing_js: Set[str] = set()  # Pages that likely need JS rendering

    def _url_to_cache_key(self, url: str) -> str:
        """Convert URL to cache filename."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        cache_key = self._url_to_cache_key(url)
        return self.html_cache_dir / f"{cache_key}.json"

    def get_cached_html(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get cached HTML response for URL.

        Args:
            url: URL to look up

        Returns:
            Dict with {html, final_url, cached_at} or None if not cached/expired
        """
        cache_path = self._get_cache_path(url)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            # Check TTL
            cached_at = datetime.fromisoformat(cached_data["cached_at"])
            # Handle old cache entries without timezone info
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - cached_at

            if age.days > self.ttl_days:
                if self.logger:
                    self.logger.debug(f"Cache expired for {url} (age: {age.days} days)")
                return None

            if self.logger:
                self.logger.debug(f"Cache hit for {url} (age: {age.days} days)")

            return cached_data

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to read cache for {url}: {e}")
            return None

    def cache_html(
        self,
        url: str,
        html: str,
        final_url: str,
        had_data: bool = False,
        extraction_methods_tried: list = None,
        last_modified: str = None,
        etag: str = None,
        fields_extracted: list = None,
        schema_version: str = None,
        js_rendering_needed: bool = False,
        extraction_failure_reason: str = None,
    ):
        """
        Cache HTML response for URL.

        Args:
            url: Original URL
            html: HTML content
            final_url: Final URL after redirects
            had_data: Whether this page yielded useful data (EIN, contact, etc.)
            extraction_methods_tried: List of extraction methods used (e.g., ['deterministic', 'llm'])
            last_modified: HTTP Last-Modified header value
            etag: HTTP ETag header value
            fields_extracted: List of field names extracted from this page
            schema_version: Version of extraction schema used
            js_rendering_needed: Whether page likely needs JavaScript rendering (Playwright)
            extraction_failure_reason: Why extraction failed (e.g., 'empty_content', 'too_short', 'js_heavy')
        """
        cache_path = self._get_cache_path(url)

        # Calculate content hash for change detection
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

        cache_data = {
            "url": url,
            "html": html,
            "final_url": final_url,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "had_data": had_data,
            "extraction_methods_tried": extraction_methods_tried or [],
            # New fields for smart caching
            "content_hash": content_hash,
            "last_modified": last_modified,
            "etag": etag,
            "fields_extracted": fields_extracted or [],
            "schema_version": schema_version or CURRENT_SCHEMA_VERSION,
            # JS rendering tracking for future Playwright processing
            "js_rendering_needed": js_rendering_needed,
            "extraction_failure_reason": extraction_failure_reason,
        }

        try:
            with open(cache_path, "w") as f:
                json.dump(cache_data, f)

            # Track based on whether we found data
            if had_data:
                self.pages_with_data.add(url)
                # Remove from no_data if it was there
                self.pages_with_no_data.discard(url)
            else:
                self.pages_with_no_data.add(url)
                # Remove from with_data if it was there
                self.pages_with_data.discard(url)

            # Track pages needing JS rendering
            if js_rendering_needed:
                self.pages_needing_js.add(url)

            # Track that we tried this URL
            self.tried_urls.add(url)

            if self.logger:
                self.logger.debug(f"Cached response for {url} (had_data={had_data}, js_needed={js_rendering_needed})")

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to cache {url}: {e}")

    def update_had_data(
        self,
        url: str,
        had_data: bool,
        extraction_methods_tried: list = None,
        js_rendering_needed: bool = False,
        extraction_failure_reason: str = None,
    ):
        """
        Update the had_data flag and extraction methods for a cached URL without re-caching HTML.

        This is useful when we cache during fetch but only know if data was found
        after extraction.

        Args:
            url: URL to update
            had_data: Whether this page yielded useful data
            extraction_methods_tried: List of methods tried (e.g., ['deterministic', 'llm'])
            js_rendering_needed: Whether page likely needs JavaScript rendering
            extraction_failure_reason: Why extraction failed (e.g., 'empty_content', 'js_heavy')
        """
        cache_path = self._get_cache_path(url)

        if not cache_path.exists():
            # No cache entry exists, just track in memory
            if had_data:
                self.pages_with_data.add(url)
                self.pages_with_no_data.discard(url)
            else:
                self.pages_with_no_data.add(url)
                self.pages_with_data.discard(url)
            if js_rendering_needed:
                self.pages_needing_js.add(url)
            self.tried_urls.add(url)
            return

        try:
            # Read existing cache
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            # Update had_data flag and extraction methods
            cached_data["had_data"] = had_data
            if extraction_methods_tried:
                cached_data["extraction_methods_tried"] = extraction_methods_tried

            # Update JS rendering tracking
            if js_rendering_needed:
                cached_data["js_rendering_needed"] = True
            if extraction_failure_reason:
                cached_data["extraction_failure_reason"] = extraction_failure_reason

            # Write back
            with open(cache_path, "w") as f:
                json.dump(cached_data, f)

            # Update in-memory tracking
            if had_data:
                self.pages_with_data.add(url)
                self.pages_with_no_data.discard(url)
            else:
                self.pages_with_no_data.add(url)
                self.pages_with_data.discard(url)

            if js_rendering_needed:
                self.pages_needing_js.add(url)

            self.tried_urls.add(url)

            if self.logger:
                self.logger.debug(f"Updated had_data={had_data}, js_needed={js_rendering_needed} for {url}")

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to update had_data for {url}: {e}")

    def should_retry_with_llm(self, url: str) -> bool:
        """
        Check if a URL should be retried with LLM extraction.

        Returns True if the URL was previously crawled with only deterministic methods
        and we haven't tried LLM yet.

        Args:
            url: URL to check

        Returns:
            bool: True if should retry with LLM
        """
        cached = self.get_cached_html(url)
        if not cached:
            return False

        methods_tried = cached.get("extraction_methods_tried", [])

        # Retry with LLM if we only tried deterministic before
        return "deterministic" in methods_tried and "llm" not in methods_tried

    def get_pages_with_no_data(self, charity_url: str) -> Set[str]:
        """
        Get set of URLs that were crawled but yielded no useful data.

        This enables progressive exploration - on next run, we can skip these
        and try different pages for breadth.

        Args:
            charity_url: Base charity URL

        Returns:
            Set of URLs that were tried but found nothing useful
        """
        state_file = self._get_state_file(charity_url)

        if not state_file.exists():
            return set()

        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                return set(state.get("pages_with_no_data", []))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to read state for {charity_url}: {e}")
            return set()

    def get_pages_with_data(self, charity_url: str) -> Set[str]:
        """
        Get set of URLs that yielded useful data.

        We can skip these on future runs since we already got data.

        Args:
            charity_url: Base charity URL

        Returns:
            Set of URLs that had useful data
        """
        state_file = self._get_state_file(charity_url)

        if not state_file.exists():
            return set()

        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                return set(state.get("pages_with_data", []))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to read state for {charity_url}: {e}")
            return set()

    def get_tried_urls(self, charity_url: str) -> Set[str]:
        """
        Get set of all URLs tried for this charity.

        Args:
            charity_url: Base charity URL

        Returns:
            Set of URLs that have been crawled
        """
        state_file = self._get_state_file(charity_url)

        if not state_file.exists():
            return set()

        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                return set(state.get("tried_urls", []))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to read state for {charity_url}: {e}")
            return set()

    def get_pages_needing_js(self, charity_url: str) -> Set[str]:
        """
        Get set of URLs that likely need JavaScript rendering (Playwright).

        These are pages where content extraction failed due to:
        - Empty content (JS-rendered)
        - Very short content (< 100 chars)

        Args:
            charity_url: Base charity URL

        Returns:
            Set of URLs that need JS rendering for proper extraction
        """
        state_file = self._get_state_file(charity_url)

        if not state_file.exists():
            return set()

        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                return set(state.get("pages_needing_js", []))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to read state for {charity_url}: {e}")
            return set()

    def save_state(self, charity_url: str):
        """
        Save crawl state for charity (pages with/without data, tried URLs, JS candidates).

        Args:
            charity_url: Base charity URL
        """
        state_file = self._get_state_file(charity_url)

        state = {
            "charity_url": charity_url,
            "pages_with_no_data": list(self.pages_with_no_data),
            "pages_with_data": list(self.pages_with_data),
            "tried_urls": list(self.tried_urls),
            "pages_needing_js": list(self.pages_needing_js),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

            if self.logger:
                self.logger.info(
                    f"Saved state: {len(self.pages_with_data)} pages with data, "
                    f"{len(self.pages_with_no_data)} pages with no data, "
                    f"{len(self.pages_needing_js)} pages needing JS, "
                    f"{len(self.tried_urls)} total tried"
                )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save state for {charity_url}: {e}")

    def _get_state_file(self, charity_url: str) -> Path:
        """Get state file path for charity."""
        state_key = hashlib.md5(charity_url.encode()).hexdigest()
        return self.state_dir / f"{state_key}.json"

    def clear_expired_cache(self):
        """
        Clear expired cache entries.

        Returns number of entries cleared.
        """
        cleared = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)

        for cache_file in self.html_cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)

                cached_at = datetime.fromisoformat(cached_data["cached_at"])
                # Handle old cache entries without timezone info
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)

                if cached_at < cutoff:
                    cache_file.unlink()
                    cleared += 1

            except Exception:
                # If we can't read it, delete it
                cache_file.unlink()
                cleared += 1

        if self.logger and cleared > 0:
            self.logger.info(f"Cleared {cleared} expired cache entries")

        return cleared

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        html_cache_files = list(self.html_cache_dir.glob("*.json"))
        state_files = list(self.state_dir.glob("*.json"))

        total_size = sum(f.stat().st_size for f in html_cache_files)

        return {
            "cached_pages": len(html_cache_files),
            "tracked_charities": len(state_files),
            "total_cache_size_mb": total_size / (1024 * 1024),
            "pages_with_data_current": len(self.pages_with_data),
            "pages_with_no_data_current": len(self.pages_with_no_data),
            "pages_needing_js_current": len(self.pages_needing_js),
            "tried_urls_current": len(self.tried_urls),
        }

    # =========================================================================
    # Smart caching methods (180-day TTL with conditional fetching)
    # =========================================================================

    def get_http_headers(self, url: str) -> Dict[str, str]:
        """
        Get stored HTTP headers (Last-Modified, ETag) for conditional requests.

        Args:
            url: URL to look up

        Returns:
            Dict with 'last_modified' and/or 'etag' if available
        """
        cached = self.get_cached_html(url)
        if not cached:
            return {}

        headers = {}
        if cached.get("last_modified"):
            headers["last_modified"] = cached["last_modified"]
        if cached.get("etag"):
            headers["etag"] = cached["etag"]

        return headers

    def has_content_changed(self, url: str, new_html: str) -> bool:
        """
        Check if content has actually changed by comparing content hashes.

        Args:
            url: URL to check
            new_html: New HTML content to compare

        Returns:
            True if content has changed, False if identical
        """
        cached = self.get_cached_html(url)
        if not cached:
            return True  # No cache = consider it changed

        cached_hash = cached.get("content_hash")
        if not cached_hash:
            return True  # No hash stored = consider it changed

        new_hash = hashlib.sha256(new_html.encode("utf-8")).hexdigest()
        return new_hash != cached_hash

    def should_refetch(self, url: str, force: bool = False) -> Tuple[bool, str]:
        """
        Check if page needs refetching based on age, content, and headers.

        Args:
            url: URL to check
            force: Force refetch regardless of cache

        Returns:
            Tuple of (should_refetch: bool, reason: str)
        """
        if force:
            return True, "force flag set"

        cached = self.get_cached_html(url)
        if not cached:
            return True, "not in cache"

        # Check TTL
        cached_at = datetime.fromisoformat(cached["cached_at"])
        # Handle old cache entries without timezone info
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - cached_at

        if age.days > self.ttl_days:
            return True, f"cache expired (age: {age.days} days > {self.ttl_days} days)"

        # If we have Last-Modified or ETag, we should still check with server
        # But return False here - actual conditional GET happens in web_collector
        if cached.get("last_modified") or cached.get("etag"):
            return False, "cache valid, has headers for conditional GET"

        return False, f"cache valid (age: {age.days} days)"

    def needs_llm_reprocessing(self, url: str) -> Tuple[bool, str]:
        """
        Check if cached data needs LLM re-extraction due to schema changes.

        This is called automatically during crawl to detect outdated extractions.

        Args:
            url: URL to check

        Returns:
            Tuple of (needs_reprocessing: bool, reason: str)
        """
        cached = self.get_cached_html(url)
        if not cached:
            return True, "not in cache"

        cached_version = cached.get("schema_version", "1.0")

        if cached_version < CURRENT_SCHEMA_VERSION:
            if self.logger:
                self.logger.info(
                    f"Schema outdated ({cached_version} < {CURRENT_SCHEMA_VERSION}) for {url}, will re-extract"
                )
            return True, f"schema outdated ({cached_version} < {CURRENT_SCHEMA_VERSION})"

        return False, f"schema current ({cached_version})"

    def get_fields_extracted(self, url: str) -> list:
        """
        Get list of fields that were extracted from this URL.

        Useful for tracking which pages contribute which data.

        Args:
            url: URL to look up

        Returns:
            List of field names extracted from this URL
        """
        cached = self.get_cached_html(url)
        if not cached:
            return []

        return cached.get("fields_extracted", [])

    def update_fields_extracted(self, url: str, fields: list):
        """
        Update the list of fields extracted from a URL.

        Args:
            url: URL to update
            fields: List of field names extracted
        """
        cache_path = self._get_cache_path(url)

        if not cache_path.exists():
            return

        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            cached_data["fields_extracted"] = fields

            with open(cache_path, "w") as f:
                json.dump(cached_data, f)

            if self.logger:
                self.logger.debug(f"Updated fields_extracted for {url}: {fields}")

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to update fields for {url}: {e}")

    def get_content_hash(self, url: str) -> Optional[str]:
        """
        Get the content hash for a cached URL.

        Args:
            url: URL to look up

        Returns:
            SHA256 hash of cached content, or None
        """
        cached = self.get_cached_html(url)
        if not cached:
            return None
        return cached.get("content_hash")

    def get_schema_version(self, url: str) -> Optional[str]:
        """
        Get the schema version used when extracting this URL.

        Args:
            url: URL to look up

        Returns:
            Schema version string, or None
        """
        cached = self.get_cached_html(url)
        if not cached:
            return None
        return cached.get("schema_version", "1.0")

    # ─────────────────────────────────────────────────────────────────────────────
    # Cloudflare/bot protection profile persistence
    # ─────────────────────────────────────────────────────────────────────────────

    def _get_cloudflare_profiles_path(self) -> Path:
        """Get path to cloudflare profiles file."""
        return self.state_dir / "cloudflare_profiles.json"

    def set_cloudflare_profile(self, domain: str, profile: str) -> None:
        """
        Persist a working curl_cffi profile for a domain.

        Args:
            domain: Domain name (e.g., 'example.org')
            profile: curl_cffi browser profile that works (e.g., 'safari15_5')
        """
        profiles_path = self._get_cloudflare_profiles_path()

        # Load existing profiles
        profiles = {}
        if profiles_path.exists():
            try:
                with open(profiles_path, "r") as f:
                    profiles = json.load(f)
            except Exception:
                profiles = {}

        # Update and save
        profiles[domain] = {
            "profile": profile,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(profiles_path, "w") as f:
                json.dump(profiles, f, indent=2)
            if self.logger:
                self.logger.debug(f"Persisted cloudflare profile for {domain}: {profile}")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to persist cloudflare profile for {domain}: {e}")

    def get_cloudflare_profile(self, domain: str) -> Optional[str]:
        """
        Get the persisted curl_cffi profile for a domain.

        Args:
            domain: Domain name

        Returns:
            Profile name or None if not found
        """
        profiles_path = self._get_cloudflare_profiles_path()

        if not profiles_path.exists():
            return None

        try:
            with open(profiles_path, "r") as f:
                profiles = json.load(f)

            entry = profiles.get(domain)
            if entry:
                return entry.get("profile")
            return None
        except Exception:
            return None

    def get_all_cloudflare_profiles(self) -> Dict[str, str]:
        """
        Get all persisted cloudflare profiles.

        Returns:
            Dict mapping domain -> profile name
        """
        profiles_path = self._get_cloudflare_profiles_path()

        if not profiles_path.exists():
            return {}

        try:
            with open(profiles_path, "r") as f:
                profiles = json.load(f)

            # Extract just domain -> profile mapping
            return {domain: entry.get("profile") for domain, entry in profiles.items() if entry.get("profile")}
        except Exception:
            return {}

"""
Data collection orchestrator - coordinates all 6 data sources.

Manages the complete data collection pipeline and stores results in DoltDB.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from ..constants import (
    CRAWL_INITIAL_BACKOFF_SECONDS,
    CRAWL_MAX_RETRIES,
    DATA_FULL_CONFIDENCE_MAX_AGE_YEARS,
    FAILURE_TTL_DAYS,
    RETRY_BACKOFF_HOURS,
    SOURCE_TTL_DAYS,
    TERMINAL_FAILURE_MARKERS,
    TERMINAL_FAILURE_TTL_DAYS,
)
from ..db import CharityRepository, CrawlAttemptRepository, CrawledPageRepository, RawDataRepository
from ..db.dolt_client import execute_query
from ..db.repository import Charity
from ..parsers.charity_metrics_aggregator import CharityMetrics, CharityMetricsAggregator
from ..utils.charity_loader import normalize_website_url
from ..utils.logger import PipelineLogger
from .bbb_collector import BBBCollector
from .candid_beautifulsoup import CandidCollector
from .charity_navigator import CharityNavigatorCollector
from .form990_grants import Form990GrantsCollector
from .propublica import ProPublicaCollector
from .web_collector import WebsiteCollector


def count_filled_fields(data: Dict[str, Any], prefix: str = "") -> Tuple[Set[str], int]:
    """
    Recursively count filled fields in a nested dictionary.

    Returns:
        Tuple of (set of filled field paths, total count)
    """
    filled = set()

    def is_filled(value) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True

    def recurse(obj: Any, path: str):
        if isinstance(obj, dict):
            for key, value in obj.items():
                field_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    recurse(value, field_path)
                elif isinstance(value, list) and value:
                    # Count list as filled if non-empty
                    filled.add(field_path)
                    # Also recurse into list items if they're dicts
                    for i, item in enumerate(value[:3]):  # Sample first 3
                        if isinstance(item, dict):
                            recurse(item, f"{field_path}[{i}]")
                elif is_filled(value):
                    filled.add(field_path)

    recurse(data, prefix)
    return filled, len(filled)


def compute_field_delta(old_data: Optional[Dict], new_data: Dict) -> Dict[str, Any]:
    """
    Compute the difference between old and new data.

    Returns:
        Dict with:
        - new_fields: List of fields that are new (not in old data)
        - updated_fields: List of fields with different values
        - total_new: Count of new fields
        - total_updated: Count of updated fields
        - found_new_data: Boolean if any new meaningful data was found
    """
    if not old_data:
        new_fields, count = count_filled_fields(new_data)
        return {
            "new_fields": list(new_fields),
            "updated_fields": [],
            "total_new": count,
            "total_updated": 0,
            "found_new_data": count > 0,
        }

    old_fields, _ = count_filled_fields(old_data)
    new_fields, _ = count_filled_fields(new_data)

    # Fields in new but not in old
    added = new_fields - old_fields
    # Fields that exist in both (potential updates)
    common = new_fields & old_fields

    # For common fields, check if values changed
    updated = []
    for field in common:
        # Extract value by path
        def get_value(data: Dict, path: str) -> Any:
            parts = path.replace("[", ".").replace("]", "").split(".")
            val = data
            for part in parts:
                if part.isdigit():
                    val = val[int(part)] if isinstance(val, list) else None
                elif isinstance(val, dict):
                    val = val.get(part)
                else:
                    return None
                if val is None:
                    break
            return val

        old_val = get_value(old_data, field)
        new_val = get_value(new_data, field)
        if old_val != new_val:
            updated.append(field)

    return {
        "new_fields": list(added),
        "updated_fields": updated,
        "total_new": len(added),
        "total_updated": len(updated),
        "found_new_data": len(added) > 0 or len(updated) > 0,
    }


WEBSITE_OPTIONAL_DEMOTION_MARKERS = ("no data found on any pages",)


def classify_failure(error: Optional[str]) -> Optional[str]:
    """Return the terminal-failure marker contained in error, or None if transient (H5)."""
    if not error:
        return None
    lower = error.lower()
    for marker in TERMINAL_FAILURE_MARKERS:
        if marker in lower:
            return marker
    return None


def is_optional_website_failure(candidates: List[str]) -> bool:
    """True only for genuinely-optional no-data failures. CAPTCHA no longer demotes (H5)."""
    for candidate in candidates:
        if any(marker in candidate.lower() for marker in WEBSITE_OPTIONAL_DEMOTION_MARKERS):
            return True
    return False


def data_age_years(scraped_at, now=None) -> int | None:
    """Whole years since a raw source was last successfully observed.

    Accepts a datetime or an ISO-ish string (as the DB driver returns
    `scraped_at`). Returns None when the timestamp is missing/unparseable so
    callers treat unknown age as "not aged out" (absence is penalized elsewhere).
    """
    from datetime import datetime

    if scraped_at is None:
        return None
    if now is None:
        now = datetime.now()
    if isinstance(scraped_at, str):
        try:
            scraped_at = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        except ValueError:
            try:
                scraped_at = datetime.strptime(scraped_at[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if scraped_at.tzinfo is not None:
        scraped_at = scraped_at.replace(tzinfo=None)
    return (now - scraped_at).days // 365


def parsed_json_is_meaningful(parsed_json: dict | None) -> bool:
    """True if any top-level value is a non-empty dict/list (mirrors
    DataCollectionOrchestrator._is_meaningful_data as a module-level pure fn)."""
    if not parsed_json:
        return False
    for value in parsed_json.values():
        if isinstance(value, dict) and len(value) > 0:
            return True
        if isinstance(value, list) and len(value) > 0:
            return True
    return False


def grants_has_filings(parsed_json: dict | None) -> bool:
    """True if a grants observation carries real filing/financial data (not the
    empty NO_XML sentinel profile that only has name+ein)."""
    gp = (parsed_json or {}).get("grants_profile") or {}
    return bool(
        gp.get("filing_years")
        or gp.get("domestic_grants")
        or gp.get("foreign_grants")
        or gp.get("total_grants")
        or gp.get("total_revenue")
        or gp.get("total_expenses")
    )


def is_content_downgrade(
    source: str,
    new_parsed_json: dict | None,
    new_raw_content: str | None,
    prior_parsed_json: dict | None,
) -> bool:
    """True when the new observation is materially thinner than stored prior
    content — the signal to preserve last-good instead of overwriting.

    Only meaningful when a substantive prior exists; returns False otherwise
    (a first/no-prior observation is never a downgrade).
    """
    new_parsed_json = new_parsed_json or {}
    prior_parsed_json = prior_parsed_json or {}

    if source == "website":
        prior_pages = (prior_parsed_json.get("crawl_stats") or {}).get("pages_crawled") or 0
        new_pages = (new_parsed_json.get("crawl_stats") or {}).get("pages_crawled") or 0
        if prior_pages <= 0:
            return False
        # raw_content is the HOMEPAGE only, fetched separately from the multi-page
        # crawl — a Cloudflare-fronted site can serve pages fine via curl_cffi while
        # the sync homepage fetch 403s. Thin homepage HTML is only a downgrade
        # signal when the crawl did not otherwise improve; a crawl that found MORE
        # pages than last time is strictly richer no matter what the homepage did.
        thin_raw = not new_raw_content or len(new_raw_content.strip()) < 500
        lost_pages = prior_pages >= 3 and new_pages <= max(1, prior_pages // 3)
        return lost_pages or (thin_raw and new_pages <= prior_pages)

    if source == "form990_grants":
        return grants_has_filings(prior_parsed_json) and not grants_has_filings(new_parsed_json)

    return parsed_json_is_meaningful(prior_parsed_json) and not parsed_json_is_meaningful(new_parsed_json)


# H12: sources frozen out of the default crawl. Existing DB rows are kept as-is;
# re-enable per-run with crawl.py --sources bbb.
FROZEN_SOURCES = {"bbb"}


def resolve_skip_sources(
    skip_sources: Optional[List[str]], include_sources: Optional[List[str]] = None
) -> Set[str]:
    """Effective skip set: explicit skips + frozen sources not explicitly included."""
    return set(skip_sources or []) | (FROZEN_SOURCES - set(include_sources or []))


class DataCollectionOrchestrator:
    """
    Orchestrate data collection from all 6 sources.

    Coordinates:
    - ProPublica (IRS 990 API)
    - Charity Navigator (web scraping)
    - Candid (BeautifulSoup parsing - deterministic)
    - Form 990 Grants (IRS 990 XML via ProPublica - Schedule I/F grants)
    - Website (multi-page crawl + LLM extraction)
    - BBB Wise Giving Alliance (web scraping with AJAX)

    Stores raw data and aggregated CharityMetrics.
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        cn_api_key: Optional[str] = None,
        logger: Optional[PipelineLogger] = None,
        max_pdf_downloads: int = 0,
        skip_sources: Optional[List[str]] = None,
        include_sources: Optional[List[str]] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            anthropic_api_key: For Website LLM extraction (Candid no longer uses LLM)
            cn_api_key: For Charity Navigator
            logger: Logger instance
            max_pdf_downloads: Max PDFs to download per charity (default 0 = disabled)
            skip_sources: List of source names to skip (e.g., ['causeiq', 'website'])
            include_sources: Frozen sources to re-enable for this run (e.g. ['bbb'])
        """
        self.logger = logger or PipelineLogger(name="orchestrator")
        self.skip_sources = resolve_skip_sources(skip_sources, include_sources)
        self.frozen_sources = FROZEN_SOURCES - set(include_sources or [])

        # H5: CAPTCHA/anti-bot blocked sites collected for the run-end report
        self.blocked_sites: List[Dict[str, Any]] = []
        self._blocked_sites_lock = threading.Lock()

        # Initialize collectors (6 sources per spec)
        self.candid = CandidCollector(logger=self.logger)  # Uses BeautifulSoup, no API key needed
        self.form990_grants = Form990GrantsCollector(logger=self.logger)  # 990 XML grants from ProPublica
        self.propublica = ProPublicaCollector(logger=self.logger)
        self.charity_navigator = CharityNavigatorCollector(api_key=cn_api_key, logger=self.logger)
        self.bbb = BBBCollector(logger=self.logger)  # BBB Wise Giving Alliance
        self.website = WebsiteCollector(
            logger=self.logger,
            max_pdf_downloads=max_pdf_downloads,  # Enable PDF downloads if configured
            # Uses default LLM provider (gemini) unless configured otherwise
        )

        # DoltDB repositories
        self.charity_repo = CharityRepository()
        self.raw_data_repo = RawDataRepository()
        self.crawl_attempt_repo = CrawlAttemptRepository()
        self.crawled_page_repo = CrawledPageRepository()

    def _load_cached_data(self, ein: str, source: str) -> Optional[Dict[str, Any]]:
        """
        Load cached data from DoltDB for a given source.

        Args:
            ein: Charity EIN
            source: Source name

        Returns:
            Cached data in the format expected by aggregation, or None if not found
        """
        row = self.raw_data_repo.get_by_source(ein, source)

        if not row or not row.get("success"):
            return None

        parsed_data = row.get("parsed_json", {}) or {}
        timestamp = row.get("scraped_at") or "unknown"

        # Format data according to source type (matching collector output format)
        if source == "candid":
            return {
                "candid_profile": parsed_data.get("candid_profile", {}),
                "fetch_timestamp": timestamp,
                "cached": True,
            }
        elif source == "propublica":
            return {
                "propublica_990": parsed_data.get("propublica_990", {}),
                "fetch_timestamp": timestamp,
                "cached": True,
            }
        elif source == "charity_navigator":
            return {"cn_profile": parsed_data.get("cn_profile", {}), "fetch_timestamp": timestamp, "cached": True}
        elif source == "form990_grants":
            return {
                "grants_profile": parsed_data.get("grants_profile", {}),
                "fetch_timestamp": timestamp,
                "cached": True,
            }
        elif source == "website":
            return {
                "website_profile": parsed_data.get("website_profile", {}),
                "fetch_timestamp": timestamp,
                "cached": True,
            }
        elif source == "bbb":
            return {
                "bbb_profile": parsed_data.get("bbb_profile", {}),
                "fetch_timestamp": timestamp,
                "cached": True,
            }
        else:
            return parsed_data

    def _is_data_fresh(self, ein: str, source: str) -> bool:
        """
        Check if cached data is fresh (within TTL).

        Args:
            ein: Charity EIN
            source: Source name

        Returns:
            True if data exists and is within TTL, False otherwise
        """
        row = self.raw_data_repo.get_by_source(ein, source)
        if not row or not row.get("success"):
            return False

        scraped_at = row.get("scraped_at")
        if not scraped_at:
            return False

        # Parse timestamp
        try:
            if isinstance(scraped_at, str):
                scraped_dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
            else:
                scraped_dt = scraped_at
        except (ValueError, TypeError):
            return False

        # Get TTL for this source
        ttl_days = SOURCE_TTL_DAYS.get(source, 30)  # Default 30 days
        age = datetime.now(scraped_dt.tzinfo) - scraped_dt

        return age < timedelta(days=ttl_days)

    @staticmethod
    def _attempt_clock(row: dict) -> Optional[datetime]:
        """When this source was last ATTEMPTED, as a datetime (or None).

        Prefers last_attempt_at over scraped_at. scraped_at is the DATA clock
        and is deliberately frozen when a failed re-crawl preserves last-good
        content, so using it for backoff meant the retry clock never advanced
        for exactly the rows preservation protects — and made the 180d terminal
        TTL measure time since last SUCCESS, so long-blocked sites read as
        expired and were re-hammered every run. Falls back to scraped_at for
        pre-migration rows where last_attempt_at is NULL.
        """
        raw = row.get("last_attempt_at") or row.get("scraped_at")
        if not raw:
            return None
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        return raw

    def _should_skip_failed_source(self, ein: str, source: str) -> Tuple[bool, str]:
        """
        Check if a failed source should be skipped due to backoff or permanent failure.

        Args:
            ein: Charity EIN
            source: Source name

        Returns:
            Tuple of (should_skip, reason)
        """
        row = self.raw_data_repo.get_by_source(ein, source)
        if not row:
            return False, ""

        # If previous attempt succeeded, no need to skip
        if row.get("success"):
            return False, ""

        retry_count = row.get("retry_count", 0)
        attempted_dt = self._attempt_clock(row)

        # H5: terminal failure classes (CAPTCHA, not-found) — long TTL, don't re-hammer
        failure_text = " | ".join(
            str(row.get(f) or "") for f in ("last_failure_reason", "error_message")
        )
        terminal_marker = classify_failure(failure_text)
        if terminal_marker:
            if attempted_dt:
                failure_age = datetime.now(attempted_dt.tzinfo) - attempted_dt
                if failure_age < timedelta(days=TERMINAL_FAILURE_TTL_DAYS):
                    return True, f"terminal failure ({terminal_marker}), TTL {TERMINAL_FAILURE_TTL_DAYS}d"
                self.raw_data_repo.reset_retry_count(ein, source)
                return False, ""

        # FIX #10: Permanent failure with TTL — after FAILURE_TTL_DAYS, reset and allow retry
        if retry_count >= CRAWL_MAX_RETRIES:
            if attempted_dt:
                failure_age = datetime.now(attempted_dt.tzinfo) - attempted_dt
                if failure_age >= timedelta(days=FAILURE_TTL_DAYS):
                    # Failure is stale — reset retry_count so source can be re-fetched
                    self.raw_data_repo.reset_retry_count(ein, source)
                    self.logger.info(
                        f"Reset permanent failure for {source} (age: {failure_age.days}d, TTL: {FAILURE_TTL_DAYS}d)"
                    )
                    return False, ""
            return True, f"permanent failure (retry_count={retry_count})"

        # Check backoff window
        if not attempted_dt:
            return False, ""

        # Get backoff hours for this retry count
        backoff_hours = RETRY_BACKOFF_HOURS.get(retry_count, 24)
        age = datetime.now(attempted_dt.tzinfo) - attempted_dt

        if age < timedelta(hours=backoff_hours):
            remaining = timedelta(hours=backoff_hours) - age
            return True, f"within backoff window ({remaining.total_seconds() / 3600:.1f}h remaining)"

        return False, ""

    def _load_previous_aggregated_data(self, ein: str) -> Optional[Dict[str, Any]]:
        """
        Load the most recent aggregated profile data for a charity.

        This is used to compute field deltas between crawls.

        Args:
            ein: Charity EIN

        Returns:
            Previous aggregated data dict or None if no previous data
        """
        if not ein:
            return None

        # Get all raw data for this charity
        all_data = self.raw_data_repo.get_for_charity(ein)
        if not all_data:
            return None

        previous_data = {}

        sources_map = {
            "candid": "candid_profile",
            "propublica": "propublica_990",
            "charity_navigator": "cn_profile",
            "form990_grants": "grants_profile",
            "website": "website_profile",
            "bbb": "bbb_profile",
        }

        for row in all_data:
            if not row.get("success"):
                continue
            source = row.get("source")
            if source not in sources_map:
                continue

            profile_key = sources_map[source]
            parsed = row.get("parsed_json", {}) or {}

            # Get the nested profile data
            for key in [profile_key, f"{source}_profile"]:
                if key in parsed:
                    previous_data[profile_key] = parsed[key]
                    break

        return previous_data if previous_data else None

    def _get_cached_candid_data(self, ein: str, max_age_days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Check for cached Candid data and return it if fresh enough.

        Args:
            ein: Charity EIN
            max_age_days: Maximum age of cached data in days (default: 30)

        Returns:
            Cached Candid data if available and fresh, None otherwise
        """
        if not ein:
            return None

        row = self.raw_data_repo.get_by_source(ein, "candid")

        if not row or not row.get("success"):
            return None

        timestamp_str = row.get("scraped_at")
        if not timestamp_str:
            return None

        # Parse timestamp
        try:
            # Handle both string and datetime objects
            if isinstance(timestamp_str, str):
                scrape_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                scrape_time = timestamp_str

            # Make comparison timezone-naive
            if hasattr(scrape_time, "tzinfo") and scrape_time.tzinfo is not None:
                scrape_time = scrape_time.replace(tzinfo=None)

            age_days = (datetime.now() - scrape_time).days

            if age_days <= max_age_days:
                # Cache is fresh, return data
                parsed_json = row.get("parsed_json", {}) or {}
                candid_profile = parsed_json.get("candid_profile", {})

                self.logger.info(f"Using cached Candid data (age: {age_days} days, threshold: {max_age_days} days)")

                return {
                    "candid_profile": candid_profile,
                    "raw_content": None,  # Content not stored for cached data
                    "fetch_timestamp": str(timestamp_str),
                    "cached": True,
                }
            else:
                self.logger.info(f"Cached Candid data too old (age: {age_days} days, threshold: {max_age_days} days)")
                return None

        except Exception as e:
            self.logger.warning(f"Failed to parse cached Candid data: {e}")
            return None

    def _has_content_substance(self, raw_content: str | None, source: str) -> bool:
        """
        FIX #2: Check if raw content has meaningful substance (not empty/shell HTML).

        A collector can return HTTP 200 with an empty page or boilerplate shell.
        This check catches that before we mark the source as succeeded.

        Args:
            raw_content: Raw fetched content
            source: Source name (for source-specific thresholds)

        Returns:
            True if content has substance, False if empty/shell
        """
        if not raw_content:
            return False

        content = raw_content.strip()
        if not content:
            return False

        if source == "form990_grants" and content == Form990GrantsCollector.NO_XML_SENTINEL:
            return True

        # Minimum content length thresholds by type
        # JSON API responses are compact; HTML pages have markup overhead
        min_lengths = {
            "propublica": 50,       # JSON API — even a "not found" is ~50 chars
            "charity_navigator": 500,  # HTML page — real profiles are 10K+
            "candid": 500,          # HTML page
            "website": 500,         # HTML page
            "bbb": 200,             # HTML/JSON
            "form990_grants": 50,   # JSON/XML
        }
        min_len = min_lengths.get(source, 100)
        if len(content) < min_len:
            return False

        return True

    def _store_raw_content_only(self, ein: str, source: str, raw_content: str, content_type: str) -> bool:
        """
        Store raw HTML/JSON/XML without parsing (for fetch-only mode).

        FIX #2: Checks content substance before storing.
        FIX #14: Returns success/failure so caller can confirm write.

        Args:
            ein: Charity EIN
            source: Source name
            raw_content: Raw content from fetch
            content_type: Type of content (json, html, xml)

        Returns:
            True if content was stored successfully, False otherwise
        """
        if not ein:
            return False

        # FIX #2: Reject empty/shell content
        if not self._has_content_substance(raw_content, source):
            self.logger.warning(f"Empty/shell content from {source} for {ein} — not marking as succeeded")
            return False

        # FIX #14: Wrap DB write in try/except to confirm success
        try:
            self.raw_data_repo.upsert(
                charity_ein=ein,
                source=source,
                raw_content=raw_content,
                parsed_json=None,  # Will be populated by extract.py
                success=True,  # Fetch succeeded
                error_message=None,
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to store raw content for {source}/{ein}: {e}")
            return False

    def fetch_charity_data(
        self,
        ein: str,
        website_url: Optional[str] = None,
        charity_name: Optional[str] = None,
        force_sources: Optional[set[str]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Fetch raw data from all sources WITHOUT parsing.

        This is Phase 1 of the pipeline - fetch only. Parsing happens in extract.py.

        Args:
            ein: EIN in format XX-XXXXXXX (required)
            website_url: Optional website URL for website source
            charity_name: Optional charity name (for BBB lookup)
            force_sources: Optional set of source names for which BOTH the
                freshness (TTL) gate and the failure-backoff gate are
                bypassed, forcing a re-fetch regardless of cached/failed
                state. Sources not in this set are gated as normal.

        Returns:
            Tuple of (success, report)
            report contains:
                - sources_attempted: List of sources
                - sources_succeeded: List of successful sources
                - sources_failed: Dict of failed sources with errors
        """
        if not ein:
            raise ValueError("EIN is required for fetch_charity_data")

        # C-007: Validate EIN format before making API calls
        # EIN should be 9 digits, optionally with hyphen (XX-XXXXXXX)
        ein_clean = ein.replace("-", "")
        if len(ein_clean) != 9 or not ein_clean.isdigit():
            raise ValueError(f"Invalid EIN format: {ein}. Expected 9 digits (XX-XXXXXXX)")

        force_sources = set(force_sources or ())

        website_url = normalize_website_url(website_url)

        self.logger.log_evaluation_start(0, ein)

        report = {
            "ein": ein,
            "sources_attempted": [],
            "sources_succeeded": [],
            "sources_failed": {},
            "timestamps": {},
            "raw_data": {},  # Holds raw data for cost tracking and aggregation
        }

        # Get or create charity in database (returns normalized EIN)
        ein = self._get_or_create_charity(ein, charity_name, website_url)
        report["ein"] = ein

        # Define sources with their fetch functions
        # Note: Website uses collect_multi_page (combined) - see docstring
        sources = [
            ("propublica", lambda: self.propublica.fetch(ein)),
            ("charity_navigator", lambda: self.charity_navigator.fetch(ein)),
            ("candid", lambda: self.candid.fetch(ein)),
            ("form990_grants", lambda: self.form990_grants.fetch(ein)),
            ("bbb", lambda: self.bbb.fetch(ein, charity_name=charity_name)),
        ]

        for source_name, fetch_func in sources:
            # Skip if source is in skip list
            if source_name in self.skip_sources:
                label = "frozen" if source_name in self.frozen_sources else "--skip flag"
                self.logger.info(f"Skipping {source_name} ({label})")
                report["sources_skipped"] = report.get("sources_skipped", [])
                report["sources_skipped"].append(source_name)
                continue

            # Check TTL - skip if data is fresh (unless force-refreshing this source)
            if source_name not in force_sources and self._is_data_fresh(ein, source_name):
                self.logger.debug(f"Skipping {source_name} - data is fresh (within TTL)")
                report["sources_skipped"] = report.get("sources_skipped", [])
                report["sources_skipped"].append(f"{source_name} (cached)")
                report["sources_succeeded"].append(source_name)
                continue

            # Check backoff for failed sources (unless force-refreshing this source)
            should_skip, skip_reason = (
                (False, "") if source_name in force_sources else self._should_skip_failed_source(ein, source_name)
            )
            if should_skip:
                self.logger.debug(f"Skipping {source_name}: {skip_reason}")
                report["sources_failed"][source_name] = skip_reason
                continue

            report["sources_attempted"].append(source_name)

            # Retry loop with exponential backoff
            max_retries = CRAWL_MAX_RETRIES
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    fetch_result = fetch_func()

                    if fetch_result.success:
                        # FIX #2 + #14: Store raw_content only if it has substance and DB write succeeds
                        stored = self._store_raw_content_only(ein, source_name, fetch_result.raw_data, fetch_result.content_type)
                        if stored:
                            report["sources_succeeded"].append(source_name)
                            report["timestamps"][source_name] = datetime.now().isoformat()
                            self.logger.log_data_source_fetch(0, ein, source_name, success=True)
                        else:
                            report["sources_failed"][source_name] = "empty or failed to store content"
                            self.logger.log_data_source_fetch(0, ein, source_name, success=False, error="empty/shell content or DB write failed")
                        break

                    # Failed - check if retryable
                    last_error = fetch_result.error
                    if self._is_retryable_error(last_error) and attempt < max_retries:
                        backoff = CRAWL_INITIAL_BACKOFF_SECONDS * (2**attempt)
                        self.logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {source_name} "
                            f"after {backoff:.1f}s (error: {last_error})"
                        )
                        time.sleep(backoff)
                        continue

                    # Non-retryable or exhausted retries
                    report["sources_failed"][source_name] = last_error
                    self.raw_data_repo.increment_retry_count(ein, source_name, last_error)
                    self.logger.log_data_source_fetch(0, ein, source_name, success=False, error=last_error)
                    break

                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        backoff = CRAWL_INITIAL_BACKOFF_SECONDS * (2**attempt)
                        self.logger.warning(f"Retry {attempt + 1}/{max_retries} for {source_name}: {e}")
                        time.sleep(backoff)
                        continue

                    report["sources_failed"][source_name] = last_error
                    self.raw_data_repo.increment_retry_count(ein, source_name, last_error)
                    self.logger.error(f"Source {source_name} failed", exception=e, ein=ein)

        # Website: Use combined collect_multi_page (LLM extraction is expensive, do once)
        # TODO: Add fetch_multi_page() for proper separation in Phase 2
        # If website_url not provided, look it up from the charities table
        if not website_url:
            charity = self.charity_repo.get(ein)
            if charity:
                # charity_repo.get() returns a dict
                charity_website = (
                    charity.get("website") if isinstance(charity, dict) else getattr(charity, "website", None)
                )
                if charity_website:
                    website_url = normalize_website_url(charity_website)
                    self.logger.debug(f"Using website URL from charities table: {website_url}")

        website_url = normalize_website_url(website_url)
        if website_url and "website" not in self.skip_sources:
            force_site = "website" in force_sources
            should_skip_site, site_skip_reason = (
                (False, "") if force_site else self._should_skip_failed_source(ein, "website")
            )
            if should_skip_site:
                report["sources_failed"]["website"] = site_skip_reason
                report.setdefault("sources_skipped", []).append(f"website ({site_skip_reason})")
            elif force_site or not self._is_data_fresh(ein, "website"):
                report["sources_attempted"].append("website")
                try:
                    # Reaching here means the current website data is stale or a
                    # prior failure — force-bypass the HTTP cache so the re-crawl
                    # actually hits the network (fingerprint-block fallback / fresh
                    # content take effect instead of re-serving the stale shell).
                    success, data, error = self.website.collect_multi_page(website_url, ein, force=True)
                    if success:
                        # FIX #14: Only mark as succeeded if DB write confirms
                        stored = self._store_raw_data(ein, "website", data)
                        if stored:
                            report["raw_data"]["website"] = data
                            report["sources_succeeded"].append("website")
                            report["timestamps"]["website"] = datetime.now().isoformat()
                            self.logger.log_data_source_fetch(0, ein, "website", success=True)
                        else:
                            report["sources_failed"]["website"] = "empty data or DB write failed"
                            self.logger.log_data_source_fetch(0, ein, "website", success=False, error="empty data or DB write failed")
                    else:
                        report["sources_failed"]["website"] = error
                        self.logger.log_data_source_fetch(0, ein, "website", success=False, error=error)
                        # Blocker 2B: ANY non-terminal re-crawl failure (rate
                        # limit, timeout, generic no-data, ...) of a source
                        # that already has good content must not demote it
                        # to success=False -- that flip excludes the
                        # still-valid last-good content from synthesize and
                        # cascades into a degraded live export within the
                        # same run. Preserve instead; TERMINAL failures
                        # (captcha/not-found -> classify_failure non-None)
                        # and first-time (no prior good row) failures fall
                        # through to the existing demotion path unchanged.
                        is_non_terminal = classify_failure(error) is None
                        if (
                            is_non_terminal
                            and (existing := self.raw_data_repo.get_by_source(ein, "website"))
                            and existing.get("success")
                        ):
                            reason = f"website re-crawl transient ({error}); last-good preserved"
                            self.logger.warning(f"{ein}: {reason}")
                            self.raw_data_repo.record_soft_fail(ein, "website", reason)
                            report["sources_succeeded"].append("website")
                            report.setdefault("sources_soft_failed", []).append(
                                "website (transient; last-good preserved)"
                            )
                        else:
                            # Store failed attempt in DB to track captcha blocking.
                            # upsert(success=False) already increments retry_count and
                            # records last_failure_reason (Task 1) — no explicit
                            # increment_retry_count here or retry_count advances twice.
                            self._store_failed_crawl(ein, "website", error or "Unknown error")
                            self._record_blocked_site(ein, website_url, error)
                except Exception as e:
                    report["sources_failed"]["website"] = str(e)
                    self.logger.error("Website fetch failed", exception=e, ein=ein)
                    # Store failed attempt in DB (upsert increments retry_count once)
                    self._store_failed_crawl(ein, "website", str(e))
                    self._record_blocked_site(ein, website_url, str(e))
            else:
                report["sources_skipped"] = report.get("sources_skipped", [])
                report["sources_skipped"].append("website (cached)")
                report["sources_succeeded"].append("website")

        # Strict completeness requirement:
        # crawl is successful only when all required sources succeed.
        required_sources = {"propublica", "charity_navigator", "candid", "form990_grants", "bbb"}
        required_sources -= self.skip_sources
        if "website" not in self.skip_sources and website_url:
            required_sources.add("website")

        if "bbb" in required_sources and self._is_bbb_not_found(ein, report):
            required_sources.remove("bbb")
            report.setdefault("sources_optional_missing", []).append("bbb:not_found")
        if "website" in required_sources and self._is_website_infra_failure(ein, report):
            website_error = (report.get("sources_failed", {}) or {}).get("website")
            required_sources.remove("website")
            report.setdefault("sources_optional_missing", []).append(f"website:infra:{website_error}")
        missing_sources = sorted(src for src in required_sources if src not in report["sources_succeeded"])
        if missing_sources:
            details = {src: report.get("sources_failed", {}).get(src, "missing/unsuccessful") for src in missing_sources}
            self.logger.error(f"Crawl incomplete for {ein}: required sources failed/missing: {details}")
            report["required_sources"] = sorted(required_sources)
            report["missing_required_sources"] = missing_sources
            return False, report

        report["data_quality"] = "complete"
        return True, report

    def _get_or_create_charity(self, ein: str, name: Optional[str] = None, website: Optional[str] = None) -> str:
        """
        Get or create charity record in database.

        Args:
            ein: EIN in format XX-XXXXXXX
            name: Optional charity name
            website: Optional website URL

        Returns:
            Normalized EIN (database uses EIN as primary key)
        """
        # Normalize EIN to XX-XXXXXXX format
        ein_clean = ein.replace("-", "")
        if len(ein_clean) == 9 and ein_clean.isdigit():
            ein_formatted = f"{ein_clean[:2]}-{ein_clean[2:]}"
        else:
            ein_formatted = ein

        website = normalize_website_url(website)

        # Check if charity exists
        existing = self.charity_repo.get(ein_formatted)
        if existing:
            self.logger.info(f"Found existing charity record: EIN {ein_formatted}")
            updates = []
            values = []
            # Update website if we have one and existing doesn't
            existing_website = existing.get("website")
            existing_has_scheme = isinstance(existing_website, str) and existing_website.lower().startswith(
                ("http://", "https://")
            )
            if website and (not existing_website or not existing_has_scheme):
                updates.append("website = %s")
                values.append(website)
                self.logger.info(f"Updated charity website: {website}")
            # Update name if existing name is missing or is just the EIN
            existing_name = existing.get("name", "")
            if (
                name
                and name != ein_formatted
                and (not existing_name or existing_name == ein_formatted or existing_name == "Unknown")
            ):
                updates.append("name = %s")
                values.append(name)
                self.logger.info(f"Updated charity name: {name}")
            if updates:
                values.append(ein_formatted)
                execute_query(f"UPDATE charities SET {', '.join(updates)} WHERE ein = %s", tuple(values), fetch="none")
            return ein_formatted

        # Create new charity record via upsert
        charity = Charity(
            ein=ein_formatted,
            name=name or "Unknown",
            website=website,
        )
        self.charity_repo.upsert(charity)
        self.logger.info(f"Created new charity record: EIN {ein_formatted}")

        return ein_formatted

    def collect_charity_data(
        self,
        ein: Optional[str] = None,
        website_url: Optional[str] = None,
        charity_name: Optional[str] = None,
        charity_id: Optional[int] = None,  # Deprecated, kept for backwards compatibility
    ) -> Tuple[bool, Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Collect data from all sources for a charity.

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX (optional if website_url or charity_name provided)
            website_url: Optional website URL (will use multi-page crawler to find EIN if not provided)
            charity_name: Optional charity name (used to find EIN via Charity Navigator if needed)
            charity_id: Deprecated - EIN is the primary key

        Returns:
            Tuple of (success, aggregated_metrics, collection_report)
            collection_report contains:
                - sources_attempted: List of sources
                - sources_succeeded: List of successful sources
                - sources_failed: Dict of failed sources with errors
                - raw_data: Raw data from each source
                - aggregated_metrics: CharityMetrics if successful
        """
        # Validate inputs
        if not ein and not website_url and not charity_name:
            raise ValueError("Must provide at least one of: ein, website_url, or charity_name")

        self.logger.log_evaluation_start(0, ein or "unknown")

        report = {
            "ein": ein,
            "sources_attempted": [],
            "sources_succeeded": [],
            "sources_failed": {},
            "raw_data": {},
            "timestamps": {},
            "ein_discovery": None,  # Track how EIN was found
        }

        # EIN Discovery Strategy:
        # 1. If EIN provided, use it
        # 2. If website_url provided, try multi-page crawler to find EIN
        # 3. If still no EIN and charity_name provided, use Charity Navigator search

        if not ein and website_url:
            self.logger.info(f"EIN not provided, attempting to find via website crawler: {website_url}")
            try:
                success, data, error = self.website.collect_multi_page(website_url)
                if success and data.get("website_profile", {}).get("ein"):
                    ein = data["website_profile"]["ein"]
                    report["ein_discovery"] = "website_crawler"
                    report["raw_data"]["website"] = data
                    report["sources_succeeded"].append("website")
                    report["timestamps"]["website"] = datetime.now().isoformat()
                    self.logger.info(f"Found EIN via website crawler: {ein}")

                    # Store website data (defer until we have the EIN normalized)
                else:
                    self.logger.warning(f"Website crawler did not find EIN: {error}")
            except Exception as e:
                self.logger.warning(f"Website crawler failed: {str(e)}")

        if not ein and charity_name:
            self.logger.info(f"EIN not found on website, attempting Charity Navigator search for: {charity_name}")
            # Note: This would require implementing a search method in CharityNavigatorCollector
            # For now, we'll skip this and require EIN to be provided
            self.logger.warning("Charity Navigator search not yet implemented - EIN required")

        if not ein:
            self.logger.error("Could not find EIN from any source")
            return False, None, report

        # Update report with discovered EIN
        report["ein"] = ein

        # Get or create charity in database (returns normalized EIN)
        ein = self._get_or_create_charity(ein, charity_name, website_url)
        report["ein"] = ein

        # Store website data if it was collected during EIN discovery
        if "website" in report["sources_succeeded"] and report["raw_data"].get("website"):
            self._store_raw_data(ein, "website", report["raw_data"]["website"])

        # Collect from each source (6 total per spec)
        sources = [
            ("propublica", lambda: self.propublica.collect(ein)),  # Required - must succeed
            ("charity_navigator", lambda: self.charity_navigator.collect(ein)),
            ("candid", lambda: self.candid.collect(ein)),
            ("bbb", lambda: self.bbb.collect(ein, charity_name)),
        ]

        # Add Form 990 Grants collector - extracts Schedule I/F grants from 990 XML
        sources.append(("form990_grants", lambda: self.form990_grants.collect(ein)))

        # Only add website if we haven't already collected it during EIN discovery
        if website_url and "website" not in report["sources_succeeded"]:
            sources.append(("website", lambda: self.website.collect_multi_page(website_url, ein)))

        for source_name, collector_func in sources:
            # Skip if source is in skip list
            if source_name in self.skip_sources:
                if self.logger:
                    label = "frozen" if source_name in self.frozen_sources else "--skip flag"
                    self.logger.info(f"Skipping {source_name} ({label})")
                report["sources_skipped"] = report.get("sources_skipped", [])
                report["sources_skipped"].append(source_name)
                continue

            # "Do The Right Thing" checks per spec:
            # 1. Check if data is fresh (within TTL) → use cached
            if self._is_data_fresh(ein, source_name):
                cached_data = self._load_cached_data(ein, source_name)
                if cached_data:
                    self.logger.debug(f"Using cached {source_name} data (within TTL)")
                    report["sources_succeeded"].append(source_name)
                    report["raw_data"][source_name] = cached_data
                    report["sources_skipped"] = report.get("sources_skipped", [])
                    report["sources_skipped"].append(f"{source_name} (cached)")
                    continue

            # 2. Check if failed source is within backoff window → skip
            should_skip, skip_reason = self._should_skip_failed_source(ein, source_name)
            if should_skip:
                self.logger.debug(f"Skipping {source_name}: {skip_reason}")
                report["sources_failed"][source_name] = skip_reason
                report["sources_skipped"] = report.get("sources_skipped", [])
                report["sources_skipped"].append(f"{source_name} ({skip_reason})")
                continue

            report["sources_attempted"].append(source_name)

            # Retry loop with exponential backoff (within single run)
            max_retries = CRAWL_MAX_RETRIES
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    # Fetch from collector
                    success, data, error = collector_func()

                    if success:
                        # FIX #14: Only mark as succeeded if DB write confirms
                        stored = self._store_raw_data(ein, source_name, data)
                        if stored:
                            report["sources_succeeded"].append(source_name)
                            report["raw_data"][source_name] = data
                            report["timestamps"][source_name] = datetime.now().isoformat()
                            self.logger.log_data_source_fetch(0, ein, source_name, success=True)
                        else:
                            report["sources_failed"][source_name] = "empty data or DB write failed"
                            self.logger.log_data_source_fetch(0, ein, source_name, success=False, error="empty data or DB write failed")
                        break

                    # Failed - check if we should retry within this run
                    last_error = error
                    is_retryable = self._is_retryable_error(error)

                    if is_retryable and attempt < max_retries:
                        # Retry with exponential backoff
                        backoff = CRAWL_INITIAL_BACKOFF_SECONDS * (2**attempt)
                        self.logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {source_name} after {backoff:.1f}s (error: {error})"
                        )
                        time.sleep(backoff)
                        continue

                    # Non-retryable or exhausted retries - increment retry_count for cross-run backoff
                    report["sources_failed"][source_name] = error
                    new_retry_count = self.raw_data_repo.increment_retry_count(ein, source_name, error)
                    self.logger.log_data_source_fetch(0, ein, source_name, success=False, error=error)
                    self.logger.debug(f"Incremented retry_count for {source_name} to {new_retry_count}")
                    break

                except Exception as e:
                    last_error = str(e)

                    if attempt < max_retries:
                        # Retry on exception with backoff
                        backoff = CRAWL_INITIAL_BACKOFF_SECONDS * (2**attempt)
                        self.logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {source_name} after {backoff:.1f}s (exception: {e})"
                        )
                        time.sleep(backoff)
                        continue

                    # Exhausted retries - increment retry_count for cross-run backoff
                    report["sources_failed"][source_name] = last_error
                    new_retry_count = self.raw_data_repo.increment_retry_count(ein, source_name, last_error)
                    self.logger.error(
                        f"Source {source_name} failed after {max_retries} retries (retry_count now {new_retry_count})",
                        exception=e,
                        ein=ein,
                    )

        # Website collection: Extract URL from collected data if not already collected
        if "website" not in report["sources_succeeded"] and "website" not in self.skip_sources:
            # Try to get website URL from collected sources
            discovered_url = None

            # Check CN data for website_url
            cn_data = report["raw_data"].get("charity_navigator", {})
            cn_profile = cn_data.get("cn_profile", cn_data)
            if cn_profile.get("website_url"):
                discovered_url = cn_profile["website_url"]
                self.logger.debug(f"Discovered website URL from CN: {discovered_url}")

            # Fallback to Candid
            if not discovered_url:
                candid_data = report["raw_data"].get("candid", {})
                candid_profile = candid_data.get("candid_profile", candid_data)
                if candid_profile.get("website"):
                    discovered_url = candid_profile["website"]
                    self.logger.debug(f"Discovered website URL from Candid: {discovered_url}")

            # Collect website data if we found a URL
            if discovered_url:
                self.logger.info(f"Collecting website data from discovered URL: {discovered_url}")
                report["sources_attempted"].append("website")
                try:
                    success, data, error = self.website.collect_multi_page(discovered_url, ein)
                    if success:
                        report["sources_succeeded"].append("website")
                        report["raw_data"]["website"] = data
                        report["timestamps"]["website"] = datetime.now().isoformat()
                        self._store_raw_data(ein, "website", data)
                        self.logger.log_data_source_fetch(0, ein, "website", success=True)
                    else:
                        report["sources_failed"]["website"] = error
                        self.logger.log_data_source_fetch(0, ein, "website", success=False, error=error)
                        self.raw_data_repo.increment_retry_count(ein, "website", error or "Unknown error")
                        self._record_blocked_site(ein, discovered_url, error)
                except Exception as e:
                    report["sources_failed"]["website"] = str(e)
                    self.logger.error("Website collection failed", exception=e, ein=ein)
                    self.raw_data_repo.increment_retry_count(ein, "website", str(e))
                    self._record_blocked_site(ein, discovered_url, str(e))

        # Strict completeness requirement:
        # collection is successful only when all required sources succeed.
        required_sources = {"propublica", "charity_navigator", "candid", "form990_grants", "bbb"}
        required_sources -= self.skip_sources
        website_required = "website" not in self.skip_sources and (
            bool(website_url)
            or "website" in report.get("sources_attempted", [])
            or "website" in report.get("sources_failed", {})
            or "website" in report.get("sources_succeeded", [])
        )
        if website_required:
            required_sources.add("website")

        if "bbb" in required_sources and self._is_bbb_not_found(ein, report):
            required_sources.remove("bbb")
            report.setdefault("sources_optional_missing", []).append("bbb:not_found")
        if "website" in required_sources and self._is_website_infra_failure(ein, report):
            website_error = (report.get("sources_failed", {}) or {}).get("website")
            required_sources.remove("website")
            report.setdefault("sources_optional_missing", []).append(f"website:infra:{website_error}")

        missing_sources = sorted(src for src in required_sources if src not in report["sources_succeeded"])
        if missing_sources:
            details = {src: report.get("sources_failed", {}).get(src, "missing/unsuccessful") for src in missing_sources}
            self.logger.error(f"Collection incomplete for {ein}: required sources failed/missing: {details}")
            report["required_sources"] = sorted(required_sources)
            report["missing_required_sources"] = missing_sources
            return False, None, report

        report["data_quality"] = "complete"

        # Aggregate data into CharityMetrics
        try:
            metrics = self._aggregate_metrics(ein, report["raw_data"])
            report["aggregated_metrics"] = metrics.model_dump()

            self.logger.info(f"Successfully aggregated data from {len(report['sources_succeeded'])} sources")

            # Update charity record with aggregated data (name, mission, website, etc.)
            charity_update = {"ein": ein}
            if metrics.name and metrics.name != "Unknown":
                charity_update["name"] = metrics.name
            if metrics.mission:
                charity_update["mission"] = metrics.mission
            if metrics.website_url:
                charity_update["website"] = metrics.website_url
            if metrics.address:
                charity_update["address"] = metrics.address

            if len(charity_update) > 1:  # More than just EIN
                self.charity_repo.upsert(charity_update)
                self.logger.debug("Updated charity record with aggregated data")

            # Build combined profile data for field delta calculation
            # Note: Zakat verification is handled by discover.py, not crawl
            website_profile = report["raw_data"].get("website", {}).get("website_profile", {})
            combined_profile = {**metrics.model_dump(), **website_profile}

            # Compute field delta to detect new data found
            previous_data = self._load_previous_aggregated_data(ein)
            field_delta = compute_field_delta(previous_data, combined_profile)

            report["field_delta"] = field_delta

            # Log field delta summary
            if field_delta["total_new"] > 0 or field_delta["total_updated"] > 0:
                self.logger.info(
                    f"Field delta: {field_delta['total_new']} new fields, {field_delta['total_updated']} updated fields"
                )
                if field_delta["new_fields"] and len(field_delta["new_fields"]) <= 10:
                    self.logger.debug(f"New fields: {field_delta['new_fields']}")
            else:
                self.logger.info("Field delta: No new data found in this crawl")

            return True, metrics, report

        except Exception as e:
            self.logger.error("Aggregation failed", exception=e)
            return False, None, report

    def _is_meaningful_data(self, parsed_json: Dict[str, Any]) -> bool:
        """
        Check if the scraped data is meaningful (not empty/failed).

        Args:
            parsed_json: Parsed data dictionary

        Returns:
            True if data is meaningful, False if empty/failed
        """
        if not parsed_json:
            return False

        # Check if any top-level value is a non-empty dict/list
        for key, value in parsed_json.items():
            if isinstance(value, dict) and len(value) > 0:
                return True
            if isinstance(value, list) and len(value) > 0:
                return True

        return False

    def _store_raw_data(self, ein: str, source: str, data: Dict[str, Any]) -> bool:
        """
        Store raw scraped data in DoltDB.

        FIX #14: Returns success/failure so caller can confirm write.

        Args:
            ein: Charity EIN
            source: Source name
            data: Data from collector

        Returns:
            True if data was stored successfully, False otherwise
        """
        if not ein:
            return False

        # Extract components based on source
        raw_content = data.get("raw_content")
        parsed_json = {}

        if source == "candid":
            parsed_json = {"candid_profile": data.get("candid_profile", {})}
        elif source == "form990_grants":
            parsed_json = {"grants_profile": data.get("grants_profile", {})}
        elif source == "charity_navigator":
            parsed_json = {"cn_profile": data.get("cn_profile", {})}
        elif source == "propublica":
            parsed_json = {"propublica_990": data.get("propublica_990", {})}
        elif source == "website":
            parsed_json = {
                "website_profile": data.get("website_profile", {}),
                "page_extractions": data.get("page_extractions", []),  # Maps URLs to extracted fields
                "crawl_stats": data.get("crawl_stats", {}),
            }
        elif source == "bbb":
            parsed_json = {"bbb_profile": data.get("bbb_profile", {})}
        elif source == "reconciled":
            parsed_json = {"reconciled_profile": data.get("reconciled_profile", {})}

        # Website uses combined fetch+parse, so apply the same numeric bounds
        # validation here that extract.py applies for the other sources.
        if source == "website":
            from src.validators.bounds_validator import validate_dict_bounds

            parsed_json = validate_dict_bounds(parsed_json, ein=ein, log_warnings=True)

        crawled_urls = data.get("crawled_urls", []) if source == "website" else []
        pages_found = len(crawled_urls) if source == "website" else None
        pages_with_data = sum(1 for p in crawled_urls if p.get("had_data")) if source == "website" else None
        # Durable per-page history, independent of the attempt outcome below
        # -- so a page disappearing between crawls is visible even when the
        # overall attempt is a soft-fail/preserve or a hard failure. Bookkeeping
        # must never be able to change the crawl's outcome, so a write failure
        # here (e.g. a URL too long for the column) is swallowed, not raised.
        if crawled_urls:
            try:
                self.crawled_page_repo.record_pages(ein, crawled_urls)
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"crawl history write failed for {ein}: {e}")

        # Non-downgrade guard: never replace stored substantive content with a
        # materially thinner/empty re-observation while the stored content is
        # still within the freshness window. Preserves last-good (source keeps
        # counting as succeeded) so the aggregator recomputes from it. Beyond
        # the window, or with no prior, fall through and write normally.
        existing = self.raw_data_repo.get_by_source(ein, source)
        if existing and existing.get("success"):
            age = data_age_years(existing.get("scraped_at"))
            within_window = age is None or age <= DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
            if within_window and is_content_downgrade(source, parsed_json, raw_content, existing.get("parsed_json")):
                reason = f"{source} re-observation thinner than last-good; preserved (age={age}y)"
                self.logger.warning(f"{ein}: {reason}")
                self.raw_data_repo.record_soft_fail(ein, source, reason)
                # Bookkeeping must never be able to undo the preserve it's
                # recording: a raise here must not fall through to the
                # demotion path below.
                try:
                    self.crawl_attempt_repo.record(ein, source, success=True, failure_reason=reason,
                                                    pages_found=pages_found, pages_with_data=pages_with_data)
                except Exception as e:
                    if self.logger:
                        self.logger.debug(f"crawl history write failed for {ein}: {e}")
                return True

        # Check if data is meaningful
        is_meaningful = self._is_meaningful_data(parsed_json)

        # FIX #14: Wrap DB write in try/except to confirm success
        try:
            self.raw_data_repo.upsert(
                charity_ein=ein,
                source=source,
                parsed_json=parsed_json,
                success=is_meaningful,
                error_message=None if is_meaningful else "Empty or failed data",
                raw_content=raw_content,
            )
            # The upsert already succeeded; a raise from this bookkeeping call
            # must not be mistaken for a failed store (would demote a good
            # write to failure via the except block below).
            try:
                self.crawl_attempt_repo.record(
                    ein, source, success=is_meaningful,
                    failure_reason=None if is_meaningful else "Empty or failed data",
                    pages_found=pages_found, pages_with_data=pages_with_data,
                )
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"crawl history write failed for {ein}: {e}")
            return is_meaningful
        except Exception as e:
            self.logger.error(f"Failed to store raw data for {source}/{ein}: {e}")
            try:
                self.crawl_attempt_repo.record(ein, source, success=False, failure_reason=str(e),
                                                pages_found=pages_found, pages_with_data=pages_with_data)
            except Exception as e2:
                if self.logger:
                    self.logger.debug(f"crawl history write failed for {ein}: {e2}")
            return False

    def _store_failed_crawl(self, ein: str, source: str, error: str):
        """
        Store failed crawl attempt for debugging.

        This allows us to track which sources failed and why, enabling
        better debugging and retry strategies.

        Args:
            ein: Charity EIN
            source: Source name that failed
            error: Error message describing the failure
        """
        if not ein:
            return

        self.raw_data_repo.upsert(
            charity_ein=ein,
            source=source,
            parsed_json={},
            success=False,
            error_message=error,
            raw_content=None,
        )
        self.crawl_attempt_repo.record(ein, source, success=False, failure_reason=error)

    def _record_blocked_site(self, ein: str, url: Optional[str], error: Optional[str]) -> None:
        """Track CAPTCHA/anti-bot blocked sites for the run-end report (H5)."""
        if not error or "captcha_blocked" not in error.lower():
            return
        with self._blocked_sites_lock:
            self.blocked_sites.append({"ein": ein, "url": url, "reason": error})

    def get_blocked_sites(self) -> List[Dict[str, Any]]:
        with self._blocked_sites_lock:
            return list(self.blocked_sites)

    def _is_retryable_error(self, error: str) -> bool:
        """
        Check if an error is transient and worth retrying.

        Retryable errors include network issues, rate limits, and temporary
        server errors. Non-retryable errors include auth failures, not found,
        and validation errors.

        Args:
            error: Error message string

        Returns:
            True if the error is transient and should be retried
        """
        if not error:
            return False

        # Non-retryable: validation errors are permanent failures
        if error.startswith("VALIDATION_ERROR:"):
            return False

        retryable_indicators = [
            "timeout",
            "connection",
            "rate limit",
            "429",
            "503",
            "502",
            "504",
            "temporary",
            "overloaded",
            "too many requests",
            "network",
            "ssl",
            "reset by peer",
        ]
        error_lower = error.lower()
        return any(indicator in error_lower for indicator in retryable_indicators)

    def _is_propublica_missing_record(self, report: Dict[str, Any]) -> bool:
        """Return True when ProPublica explicitly reports EIN not found."""
        error = (report.get("sources_failed", {}) or {}).get("propublica")
        if not isinstance(error, str):
            return False
        return "organization not found for ein" in error.lower()

    def _is_bbb_not_found(self, ein: str, report: Dict[str, Any]) -> bool:
        """Return True when BBB explicitly reports charity not found."""
        error = (report.get("sources_failed", {}) or {}).get("bbb")
        candidates: list[str] = []
        if isinstance(error, str):
            candidates.append(error)

        # Backoff/permanent-failure skip paths may hide the original BBB error text.
        row = self.raw_data_repo.get_by_source(ein, "bbb")
        if isinstance(row, dict):
            for field in ("last_failure_reason", "error_message"):
                value = row.get(field)
                if isinstance(value, str):
                    candidates.append(value)

        for candidate in candidates:
            lower = candidate.lower()
            if "not found" in lower and "bbb" in lower:
                return True
        return False

    def _is_website_infra_failure(self, ein: str, report: Dict[str, Any]) -> bool:
        """Return True when website failed due to anti-bot/infra issues."""
        error = (report.get("sources_failed", {}) or {}).get("website")
        candidates: list[str] = []
        if isinstance(error, str):
            candidates.append(error)

        # Backoff/permanent-failure skip paths may hide the original website error text.
        row = self.raw_data_repo.get_by_source(ein, "website")
        if isinstance(row, dict):
            for field in ("last_failure_reason", "error_message"):
                value = row.get(field)
                if isinstance(value, str):
                    candidates.append(value)

        # H5: only genuine no-data cases demote website to optional; CAPTCHA fails loudly
        return is_optional_website_failure(candidates)

    def _aggregate_metrics(self, ein: str, raw_data: Dict[str, Any]) -> CharityMetrics:
        """
        Aggregate data from all sources into CharityMetrics.

        Args:
            ein: EIN
            raw_data: Raw data from all sources

        Returns:
            CharityMetrics instance
        """
        # Extract profiles from raw data
        cn_profile = raw_data.get("charity_navigator", {}).get("cn_profile")
        propublica_990 = raw_data.get("propublica", {}).get("propublica_990")
        candid_profile = raw_data.get("candid", {}).get("candid_profile")
        grants_profile = raw_data.get("form990_grants", {}).get("grants_profile")
        website_profile = raw_data.get("website", {}).get("website_profile")
        discovered_profile = raw_data.get("discovered", {}).get("discovered_profile")
        bbb_profile = raw_data.get("bbb", {}).get("bbb_profile")

        # NOTE: Full data reconciliation (conflict resolution, priority-based selection)
        # is handled by the separate synthesize.py phase which stores
        # reconciled data in the charity_data table.

        # Aggregate data from all sources into CharityMetrics
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,  # Not used (EIN is the key)
            ein=ein,
            cn_profile=cn_profile,
            propublica_990=propublica_990,
            candid_profile=candid_profile,
            grants_profile=grants_profile,
            website_profile=website_profile,
            discovered_profile=discovered_profile,
            bbb_profile=bbb_profile,
        )

        return metrics

    def close(self):
        """Release collector resources (DoltDB connections are per-query,
        nothing to do there). crawl.py calls this once the worker pool has
        been shut down, so this is the only chance to reach any Playwright
        renderer a worker thread created and didn't already close itself."""
        website = getattr(self, "website", None)
        if website is not None and hasattr(website, "close_all_renderers"):
            website.close_all_renderers()

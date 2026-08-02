"""
Global constants for data pipeline configuration.

Centralizes magic numbers and configuration values used throughout
the pipeline for easier maintenance and tuning.
"""

# Cache and Data Management
CACHE_MAX_AGE_DAYS = 180  # Maximum age for cached data before re-fetching
DATA_TOLERANCE_PERCENT = 0.05  # 5% tolerance for numeric data comparison

# Data freshness — the window during which data keeps full confidence and a
# missing/thin re-observation is carried forward from last-good rather than
# dropped. Beyond this, unobserved data is aged-out to null. Matches the
# 990 annual filing cycle plus one year of leeway; the -2 in _recency_factor
# and the raw-layer carry-forward guard both key off this single value.
DATA_FULL_CONFIDENCE_MAX_AGE_YEARS = 2

# Thread and Concurrency
WRITE_QUEUE_MAX_RETRIES = 5  # Maximum retries for database write operations
WRITE_QUEUE_INITIAL_BACKOFF_SECONDS = 0.5  # Initial backoff for retry logic
SHUTDOWN_TIMEOUT_SECONDS = 10  # Thread shutdown timeout
EXTENDED_SHUTDOWN_TIMEOUT_SECONDS = 5  # Extended shutdown timeout

# Network and Timeouts
CONNECTION_TIMEOUT_SECONDS = 30  # Network connection timeout
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120  # Default HTTP request timeout

# Crawl Retry Configuration
CRAWL_MAX_RETRIES = 3  # Maximum retries for failed source crawls
CRAWL_INITIAL_BACKOFF_SECONDS = 1.0  # Initial backoff (doubles each retry: 1s, 2s, 4s)

# Per-source TTL (days) - how long before checking for updates
# 6 sources per spec: propublica, charity_navigator, candid, form990_grants, website, bbb
SOURCE_TTL_DAYS = {
    "propublica": 365,       # 990s filed annually
    "charity_navigator": 90, # Scores update quarterly
    "candid": 90,            # Profile updates quarterly
    "form990_grants": 0,     # TEMP: Force re-fetch for multi-year grant support (#22)
    "website": 30,           # Content changes frequently
    "bbb": 90,               # Updates quarterly
}

# Cross-run retry backoff (hours) - for failed sources
# After each failure, wait this long before retrying on next run
RETRY_BACKOFF_HOURS = {
    1: 1,   # First failure: wait 1 hour
    2: 4,   # Second failure: wait 4 hours
    3: 24,  # Third failure: wait 24 hours
    # After 3 failures: permanent failure (skip until failure TTL expires)
}

# FIX #10: Permanent failure TTL (days) - after this many days, reset retry_count and allow re-fetch
# This prevents a transient outage from permanently blocking a charity/source pair.
FAILURE_TTL_DAYS = 30

# H5: Crawl politeness
PER_DOMAIN_CONCURRENCY = 2  # Max simultaneous requests per website domain
CRAWL_JITTER_RANGE_SECONDS = (0.5, 1.5)  # Random pre-request delay for uncached fetches

# Fleet-wide crawl politeness: the per-domain semaphore above is scoped to a
# single asyncio event loop, but the streaming runner fans charities out
# across a ThreadPoolExecutor — each charity gets its OWN loop, so N workers
# each running their own Semaphore(2) still allows N*2 concurrent sockets
# fleet-wide (this is what earned the 429s). This constant is the minimum
# seconds between outbound website requests enforced through the process-wide
# (cross-thread) global_rate_limiter, giving a real ceiling of ~5 req/s
# across the whole fleet regardless of worker count.
CRAWL_GLOBAL_MIN_INTERVAL_SECONDS = 0.2  # ~5 req/s ceiling, process-wide

# Playwright SPA-escalation bounds: a sitemap-driven SPA can flag dozens of
# pages js_rendering_needed, each rendered serially in collect_multi_page's
# escalation loop.
PLAYWRIGHT_MAX_RENDER_PAGES = 8  # Max pages to Playwright-render per charity — bounds worker occupancy on SPA-heavy sites
PLAYWRIGHT_RENDER_BUDGET_SECONDS = 60  # Aggregate wall-clock budget for the whole escalation loop — bounds worker occupancy on SPA-heavy sites

# A sitemap crawl that yields fewer than this many content pages is treated
# as thin/broken (e.g. a sitemap listing only the homepage + dead links) and
# augmented with a BFS pass from the homepage.
SITEMAP_MIN_PAGES_FOR_COVERAGE = 3

# H5: Terminal failure classes — CAPTCHA walls and hard 404s don't heal in days.
# Skip retries for TERMINAL_FAILURE_TTL_DAYS instead of the normal FAILURE_TTL_DAYS.
TERMINAL_FAILURE_TTL_DAYS = 180
TERMINAL_FAILURE_MARKERS = ("captcha_blocked", "challenge page", "not found", "not_found")

# Of those, the ones that describe a DEFENCE rather than a fact about the
# resource. "not found" persists; a challenge lifts. HTTP 202 with a challenge
# body is Cloudflare's under-attack mode, triggered by load and rate-limit
# heuristics as often as by any decision about us -- MedGlobal and Islamic
# Services Foundation were each frozen for 180 days by ONE such sighting, and
# both sites answered a plain GET with HTTP 200 nine days later.
#
# A defensive failure is therefore provisional until it has been seen
# CRAWL_MAX_RETRIES times. Below that it takes the ordinary backoff and gets
# re-checked within hours; at or above it, it is a settled fact about the
# publisher and earns the full terminal TTL. The politeness guarantee is kept
# for every site that really is refusing us, and only for those.
DEFENSIVE_FAILURE_MARKERS = ("captcha_blocked", "challenge page")

# Blocker 2A: the streaming runner's implicit re-crawl trigger skips a
# stale-but-successful website re-attempted within this many days, so a
# soft-failed (thin-content) re-observation doesn't force a full re-crawl on
# every single run. Explicit `crawl.py --refresh-stale` ignores this and
# always retries (operator intent).
WEBSITE_RECRAWL_BACKOFF_DAYS = 7

# Validation Thresholds
MIN_DATA_COMPLETENESS_THRESHOLD = 0.5  # Minimum 50% data completeness required

# Database
DEFAULT_TABLE_NAME_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"  # Valid table name regex

# Quality Thresholds
AUTO_APPROVE_SCORE_THRESHOLD = 85  # Min score for auto-approval
AUTO_REJECT_SCORE_THRESHOLD = 60  # Max score for auto-rejection
INFORMATION_DENSITY_THRESHOLD = 0.80  # Min density for narratives
HIGH_FINANCIAL_SCORE_THRESHOLD = 90  # "Excellent" financial rating

# Scoring
MAX_AMAL_SCORE = 95  # Max possible score (90 base + 5 zakat)
BASE_AMAL_SCORE = 90  # Max base score without zakat bonus
ZAKAT_BONUS = 5  # Bonus for zakat eligibility

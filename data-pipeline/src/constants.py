"""
Global constants for data pipeline configuration.

Centralizes magic numbers and configuration values used throughout
the pipeline for easier maintenance and tuning.
"""

# Cache and Data Management
CACHE_MAX_AGE_DAYS = 180  # Maximum age for cached data before re-fetching
DATA_TOLERANCE_PERCENT = 0.05  # 5% tolerance for numeric data comparison

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
    "form990_grants": 365,   # Extracted from 990 XML (immutable once filed)
    "website": 30,           # Content changes frequently
    "bbb": 90,               # Updates quarterly
}

# Cross-run retry backoff (hours) - for failed sources
# After each failure, wait this long before retrying on next run
RETRY_BACKOFF_HOURS = {
    1: 1,   # First failure: wait 1 hour
    2: 4,   # Second failure: wait 4 hours
    3: 24,  # Third failure: wait 24 hours
    # After 3 failures: permanent failure (skip until row deleted)
}

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

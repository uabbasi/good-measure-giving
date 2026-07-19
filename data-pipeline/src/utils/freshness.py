"""Shared per-source freshness helpers (age math + rollups).

source_freshness_state is the single shared pure helper for classifying a
raw_scraped_data row's freshness against a TTL; it mirrors
DataCollectionOrchestrator._is_data_fresh's tz-aware age math exactly.
crawl.py's select_stale_website_eins/crawl_freshness_summary and
streaming_runner.py's crawl-artifact check are both built on top of it so
the age math lives in one place.
"""

from datetime import datetime, timedelta


def source_freshness_state(row: dict | None, ttl_days: int) -> str:
    """
    Classify a single raw_scraped_data row's freshness against a TTL.

    Args:
        row: raw_scraped_data row dict (or None if no row exists)
        ttl_days: TTL in days for this source

    Returns:
        One of "missing" (no row), "failed" (row.success is falsy),
        "stale" (succeeded but scraped_at is older than ttl_days, missing,
        or unparseable — fail closed), "fresh" (succeeded and within TTL).
    """
    if row is None:
        return "missing"
    if not row.get("success"):
        return "failed"

    scraped_at = row.get("scraped_at")
    if not scraped_at:
        return "stale"

    try:
        if isinstance(scraped_at, str):
            scraped_dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        else:
            scraped_dt = scraped_at
        age = datetime.now(scraped_dt.tzinfo) - scraped_dt
    except (ValueError, TypeError):
        return "stale"

    return "stale" if age >= timedelta(days=ttl_days) else "fresh"


def website_needs_recrawl(rows: list[dict], ttl_days: int) -> bool:
    """
    Whether the 'website' source among `rows` needs a re-crawl.

    Pure/testable on a raw_scraped_data rows list (e.g. from
    RawDataRepository.get_for_charity): finds the row with source ==
    "website" (None if absent) and returns True when its freshness state
    is "missing", "failed", or "stale".

    Args:
        rows: raw_scraped_data rows for a single charity (any/all sources)
        ttl_days: TTL in days for the website source

    Returns:
        True if the website row is missing, failed, or stale.
    """
    website_row = next((row for row in rows if row.get("source") == "website"), None)
    return source_freshness_state(website_row, ttl_days) in {"missing", "failed", "stale"}

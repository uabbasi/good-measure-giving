"""Shared per-source freshness helpers (age math + rollups).

source_freshness_state is the single shared pure helper for classifying a
raw_scraped_data row's freshness against a TTL; it mirrors
DataCollectionOrchestrator._is_data_fresh's tz-aware age math exactly.
crawl.py's select_stale_website_eins/crawl_freshness_summary and
streaming_runner.py's crawl-artifact check are both built on top of it so
the age math lives in one place.
"""

from datetime import datetime, timedelta


def _age(ts) -> timedelta | None:
    """Tz-aware age (now - ts) for a scraped_at/last_attempt_at-style timestamp.

    Returns None if ts is missing or unparseable — callers fail closed.
    """
    if not ts:
        return None
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = ts
        return datetime.now(dt.tzinfo) - dt
    except (ValueError, TypeError):
        return None


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

    age = _age(row.get("scraped_at"))
    if age is None:
        return "stale"

    return "stale" if age >= timedelta(days=ttl_days) else "fresh"


def website_needs_recrawl(rows: list[dict], ttl_days: int, backoff_days: int = 0) -> bool:
    """
    Whether the 'website' source among `rows` needs a re-crawl.

    Pure/testable on a raw_scraped_data rows list (e.g. from
    RawDataRepository.get_for_charity): finds the row with source ==
    "website" (None if absent) and returns True when its freshness state
    is "missing" or "failed", or "stale" and not backed off (see below).

    Args:
        rows: raw_scraped_data rows for a single charity (any/all sources)
        ttl_days: TTL in days for the website source
        backoff_days: if > 0, a "stale" website row whose last_attempt_at is
            younger than this many days is treated as NOT needing a re-crawl
            — this is the soft-fail re-crawl-loop guard (blocker 2A): a
            thin/soft-failed re-observation leaves the row stale forever, so
            without backoff every streaming run would force-recrawl it.
            0 (default) disables backoff — identical to legacy behavior.

    Returns:
        True if the website row needs a (non-backed-off) re-crawl.
    """
    website_row = next((row for row in rows if row.get("source") == "website"), None)
    state = source_freshness_state(website_row, ttl_days)
    if state == "fresh":
        return False
    if state == "stale" and backoff_days:
        attempt_age = _age(website_row.get("last_attempt_at"))
        if attempt_age is not None and attempt_age < timedelta(days=backoff_days):
            return False
    return True

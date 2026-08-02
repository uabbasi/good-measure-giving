"""Shared per-source freshness helpers (age math + rollups).

source_freshness_state is the single shared pure helper for classifying a
raw_scraped_data row's freshness against a TTL; it mirrors
DataCollectionOrchestrator._is_data_fresh's tz-aware age math exactly.
crawl.py's select_stale_website_eins/crawl_freshness_summary and
streaming_runner.py's crawl-artifact check are both built on top of it so
the age math lives in one place.
"""

from datetime import datetime, timedelta

_SERVER_OFFSET: timedelta | None = None


def _reset_server_offset() -> None:
    """Forget the cached offset. For tests, and after a connection change."""
    global _SERVER_OFFSET
    _SERVER_OFFSET = None


def _server_offset() -> timedelta:
    """How far the database's clock sits from this host's, measured once.

    scraped_at and last_attempt_at are written as CURRENT_TIMESTAMP: naive,
    in the SERVER's timezone. Comparing them against datetime.now() applies
    whatever gap exists between that zone and this host's — a 23-minute-old
    failure measured as 1h23m on 2026-07-31, and a 4-hour backoff reporting
    2.7h left instead of 3.6h. The gap is not a constant to correct for; it is
    whatever the two clocks disagree by at that moment, and from a UTC host it
    would be seven hours, defeating the 1h and 4h windows outright.

    Falls back to zero — the old behaviour — if the database cannot be reached.
    Age math must never depend on the database being up.
    """
    global _SERVER_OFFSET
    if _SERVER_OFFSET is None:
        try:
            from src.db.client import execute_query

            row = execute_query("SELECT NOW() AS now", fetch="one")
            server = row["now"] if isinstance(row, dict) else None
            if isinstance(server, str):
                server = datetime.fromisoformat(server)
            _SERVER_OFFSET = (server - datetime.now()) if server else timedelta(0)
        except Exception:
            _SERVER_OFFSET = timedelta(0)
    return _SERVER_OFFSET


def _age(ts) -> timedelta | None:
    """Age (now - ts) measured on the clock that wrote ts.

    A naive timestamp came from the database and is in the SERVER's zone, so
    "now" for it is this host's clock shifted by _server_offset(). A timestamp
    that carries its own zone needs no correction.

    Returns None if ts is missing or unparseable — callers fail closed.
    """
    if not ts:
        return None
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = ts
        if dt.tzinfo is not None:
            return datetime.now(dt.tzinfo) - dt
        return (datetime.now() + _server_offset()) - dt
    except (ValueError, TypeError, AttributeError):
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
    if state == "stale" and backoff_days and website_row is not None:
        attempt_age = _age(website_row.get("last_attempt_at"))
        if attempt_age is not None and attempt_age < timedelta(days=backoff_days):
            return False
    return True

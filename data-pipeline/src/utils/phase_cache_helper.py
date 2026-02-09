"""Shared phase cache helpers for standalone scripts and streaming runner.

Provides check/update logic so both standalone scripts (crawl.py, baseline.py, etc.)
and the streaming_runner can use the same caching behavior.

Key difference:
- streaming_runner tracks cascade in-memory via `phases_ran` set
- standalone scripts use `delete_downstream()` to persist cascade to DB
"""

from src.db.repository import PhaseCacheRepository
from src.utils.phase_fingerprint import compute_code_fingerprint, get_ttl_days

# Precompute code fingerprints at startup (shared across all callers)
_fingerprint_cache: dict[str, str] = {}


def get_phase_fingerprint(phase: str) -> str:
    """Get cached code fingerprint for a phase."""
    if phase not in _fingerprint_cache:
        _fingerprint_cache[phase] = compute_code_fingerprint(phase)
    return _fingerprint_cache[phase]


def check_phase_cache(
    ein: str,
    phase: str,
    cache_repo: PhaseCacheRepository,
    force: bool = False,
) -> tuple[bool, str]:
    """Check if a phase needs to run for a charity.

    Args:
        ein: Charity EIN
        phase: Phase name (crawl, extract, synthesize, baseline, rich, judge)
        cache_repo: Phase cache repository
        force: If True, always run

    Returns:
        Tuple of (should_run, reason)
    """
    if force:
        return True, "Forced"

    current_fingerprint = get_phase_fingerprint(phase)
    ttl_days = get_ttl_days(phase)
    is_valid, reason = cache_repo.is_valid(ein, phase, current_fingerprint, ttl_days)

    if is_valid:
        return False, reason  # Skip
    else:
        return True, reason  # Run


def update_phase_cache(
    ein: str,
    phase: str,
    cache_repo: PhaseCacheRepository,
    cost_usd: float = 0.0,
) -> list[str]:
    """Record a phase completion and invalidate downstream phases.

    This is critical for standalone scripts: since they don't track cascade
    in-memory like streaming_runner does, we must delete downstream cache
    entries so the next script (or streaming_runner) knows to re-run them.

    Args:
        ein: Charity EIN
        phase: Phase that completed
        cache_repo: Phase cache repository
        cost_usd: LLM cost for this run

    Returns:
        List of downstream phases that were invalidated
    """
    fingerprint = get_phase_fingerprint(phase)
    cache_repo.upsert(ein, phase, fingerprint, cost_usd)
    invalidated = cache_repo.delete_downstream(ein, phase)
    return invalidated

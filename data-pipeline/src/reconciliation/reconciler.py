"""Single entry point for adversarial reconciliation.

Runs completeness patching then all contradiction checks.
Non-blocking: exceptions are caught and logged, never raised.
"""

import logging

from src.parsers.charity_metrics_aggregator import CharityMetrics

from .checks import get_all_checks
from .completeness import patch_completeness
from .signals import ReconciliationResult, SignalSeverity

logger = logging.getLogger(__name__)


def reconcile(metrics: CharityMetrics) -> ReconciliationResult:
    """Run completeness patching + all contradiction checks.

    Mutates metrics in-place (patching null fields).
    Returns ReconciliationResult with signals sorted by severity.
    """
    result = ReconciliationResult()

    # Phase 1: Completeness — re-derive null metrics
    try:
        patched, gaps = patch_completeness(metrics)
        result.patched_fields = patched
        result.completeness_gaps = gaps
        if patched:
            logger.info(f"[{metrics.ein}] Patched {len(patched)} fields: {', '.join(patched)}")
        if gaps:
            logger.info(f"[{metrics.ein}] {len(gaps)} completeness gaps remain")
    except Exception:
        logger.exception(f"[{metrics.ein}] Completeness patching failed")

    # Phase 2: Contradiction checks
    for check_name, check_fn in get_all_checks().items():
        try:
            signals = check_fn(metrics)
            result.signals.extend(signals)
        except Exception:
            logger.exception(f"[{metrics.ein}] Check '{check_name}' failed")

    # Sort: HIGH first, then MEDIUM, then LOW
    _severity_order = {SignalSeverity.HIGH: 0, SignalSeverity.MEDIUM: 1, SignalSeverity.LOW: 2}
    result.signals.sort(key=lambda s: _severity_order.get(s.severity, 9))

    return result

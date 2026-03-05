"""Re-derive null metrics when source data exists.

Patches CharityMetrics in-place and returns gap descriptions for fields
that remain null despite source data being available.
"""

import logging

from src.parsers.charity_metrics_aggregator import CharityMetrics

logger = logging.getLogger(__name__)

def patch_completeness(metrics: CharityMetrics) -> tuple[list[str], list[str]]:
    """Re-derive null computed fields from available source data.

    Returns (patched_fields, completeness_gaps).
    Mutates metrics in-place via model_copy is not used — we return a dict
    of patches to apply.
    """
    patched: list[str] = []
    gaps: list[str] = []

    # --- noncash_ratio ---
    if metrics.noncash_ratio is None:
        noncash = metrics.noncash_contributions
        contribs = metrics.total_contributions
        if noncash is not None and contribs and contribs > 0:
            metrics.noncash_ratio = min(noncash / contribs, 1.0)
            patched.append("noncash_ratio")
            logger.debug(f"Re-derived noncash_ratio={metrics.noncash_ratio:.3f}")
        elif noncash is not None:
            gaps.append("noncash_ratio: noncash_contributions present but total_contributions missing/zero")
        # else: no noncash data at all — not a gap, just absent

    # --- cash_adjusted_program_ratio ---
    if metrics.cash_adjusted_program_ratio is None:
        noncash_ratio = metrics.noncash_ratio
        if noncash_ratio is not None and noncash_ratio > 0.10:
            program_exp = metrics.program_expenses
            total_exp = metrics.total_expenses
            noncash = metrics.noncash_contributions
            if program_exp is not None and total_exp and total_exp > 0 and noncash is not None:
                adjusted = (program_exp - noncash) / (total_exp - noncash) if total_exp > noncash else 0.0
                metrics.cash_adjusted_program_ratio = max(0.0, adjusted)
                patched.append("cash_adjusted_program_ratio")
                logger.debug(f"Re-derived cash_adjusted_program_ratio={metrics.cash_adjusted_program_ratio:.3f}")
            else:
                gaps.append(
                    "cash_adjusted_program_ratio: noncash_ratio significant but missing expenses data"
                )

    # --- domestic_burn_rate ---
    if metrics.domestic_burn_rate is None:
        # Check if we have grants_made with foreign grants
        total_exp = metrics.total_expenses
        foreign_grants = [g for g in (metrics.grants_made or []) if g.get("country") and g["country"] != "US"]
        if foreign_grants and total_exp and total_exp > 0:
            total_foreign = sum(g.get("amount", 0) or 0 for g in foreign_grants)
            if total_foreign > 0:
                metrics.domestic_burn_rate = max(0.0, min(1.0, 1.0 - (total_foreign / total_exp)))
                patched.append("domestic_burn_rate")
                logger.debug(f"Re-derived domestic_burn_rate={metrics.domestic_burn_rate:.3f}")

    # --- reserves_months ---
    if metrics.reserves_months is None:
        net_assets = metrics.net_assets
        total_exp = metrics.total_expenses
        if net_assets is not None and total_exp and total_exp > 0:
            monthly = total_exp / 12.0
            metrics.reserves_months = net_assets / monthly
            patched.append("reserves_months")
            logger.debug(f"Re-derived reserves_months={metrics.reserves_months:.1f}")
        elif net_assets is not None:
            gaps.append("reserves_months: net_assets present but total_expenses missing/zero")

    # --- fundraising_expense_ratio ---
    if metrics.fundraising_expense_ratio is None:
        fund_exp = metrics.fundraising_expenses
        total_exp = metrics.total_expenses
        if fund_exp is not None and total_exp and total_exp > 0:
            metrics.fundraising_expense_ratio = min(fund_exp / total_exp, 1.0)
            patched.append("fundraising_expense_ratio")
            logger.debug(f"Re-derived fundraising_expense_ratio={metrics.fundraising_expense_ratio:.3f}")
        elif fund_exp is not None:
            gaps.append("fundraising_expense_ratio: fundraising_expenses present but total_expenses missing/zero")

    return patched, gaps

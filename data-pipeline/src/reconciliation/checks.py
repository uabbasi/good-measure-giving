"""Registry of deterministic contradiction checks.

Each check is a pure function: (CharityMetrics) -> list[ContradictionSignal].
Zero LLM cost. Decorator-based registration.
"""

import logging
from typing import Callable

from src.parsers.charity_metrics_aggregator import CharityMetrics

from .signals import ContradictionSignal, SignalCategory, SignalSeverity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, Callable[[CharityMetrics], list[ContradictionSignal]]] = {}


def contradiction_check(name: str):
    """Decorator to register a contradiction check function."""

    def decorator(fn: Callable[[CharityMetrics], list[ContradictionSignal]]):
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_all_checks() -> dict[str, Callable[[CharityMetrics], list[ContradictionSignal]]]:
    return dict(_REGISTRY)


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------


@contradiction_check("gik_inflated_ratio")
def check_gik_inflated_ratio(metrics: CharityMetrics) -> list[ContradictionSignal]:
    """High program ratio + high noncash → inflated efficiency."""
    signals: list[ContradictionSignal] = []
    ratio = metrics.noncash_ratio
    if ratio is None:
        return signals
    program_ratio = metrics.program_expense_ratio
    cash_adj = metrics.cash_adjusted_program_ratio

    if ratio >= 0.80:
        severity = SignalSeverity.HIGH
    elif ratio >= 0.50:
        severity = SignalSeverity.HIGH
    elif ratio >= 0.25:
        severity = SignalSeverity.MEDIUM
    else:
        return signals

    if ratio >= 0.80:
        headline = f"{ratio:.0%} of reported revenue appears to be phantom noncash contributions"
        detail_parts = [
            f"Noncash ratio: {ratio:.0%}",
            "At this level, reported program ratios are likely meaningless — "
            "inflated by noncash valuations rather than actual cash spending on programs",
        ]
    else:
        headline = f"{ratio:.0%} of reported revenue is noncash (gifts-in-kind)"
        detail_parts = [f"Noncash ratio: {ratio:.0%}"]
    if program_ratio is not None:
        detail_parts.append(f"Reported program ratio: {program_ratio:.0%}")
    if cash_adj is not None:
        detail_parts.append(f"Cash-adjusted program ratio: {cash_adj:.0%}")

    data = {"noncash_ratio": round(ratio, 3)}
    if program_ratio is not None:
        data["program_expense_ratio"] = round(program_ratio, 3)
    if cash_adj is not None:
        data["cash_adjusted_program_ratio"] = round(cash_adj, 3)

    signals.append(
        ContradictionSignal(
            check_name="gik_inflated_ratio",
            severity=severity,
            category=SignalCategory.FINANCIAL,
            headline=headline,
            detail="; ".join(detail_parts),
            data_points=data,
        )
    )
    return signals


@contradiction_check("ceo_comp_excessive")
def check_ceo_comp_excessive(metrics: CharityMetrics) -> list[ContradictionSignal]:
    """CEO pay / revenue exceeds tier threshold."""
    signals: list[ContradictionSignal] = []
    comp = metrics.ceo_compensation
    rev = metrics.total_revenue
    if comp is None or rev is None or rev <= 0:
        return signals

    ratio = comp / rev

    # Tier thresholds
    if rev < 5_000_000:
        threshold = 0.05
        tier_label = "<$5M"
    elif rev < 50_000_000:
        threshold = 0.02
        tier_label = "$5-50M"
    else:
        threshold = 0.01
        tier_label = ">$50M"

    if ratio < threshold:
        return signals

    severity = SignalSeverity.HIGH if ratio >= threshold * 2 else SignalSeverity.MEDIUM

    signals.append(
        ContradictionSignal(
            check_name="ceo_comp_excessive",
            severity=severity,
            category=SignalCategory.GOVERNANCE,
            headline=f"CEO compensation is {ratio:.1%} of revenue (${comp:,.0f} on ${rev:,.0f})",
            detail=f"For orgs with revenue {tier_label}, CEO pay above {threshold:.0%} of revenue warrants scrutiny.",
            data_points={
                "ceo_compensation": comp,
                "total_revenue": rev,
                "comp_ratio": round(ratio, 4),
                "threshold": threshold,
            },
        )
    )
    return signals


@contradiction_check("geographic_mismatch")
def check_geographic_mismatch(metrics: CharityMetrics) -> list[ContradictionSignal]:
    """Claims N countries on website, Schedule F shows 0 foreign grants."""
    signals: list[ContradictionSignal] = []

    # Count foreign countries claimed in geographic_coverage
    geo = metrics.geographic_coverage or []
    # Heuristic: entries with country-level names (not US states/cities) suggest international ops.
    # domestic_burn_rate being None means no Schedule F data (no foreign grants filed).
    countries_claimed = len(geo)
    if countries_claimed < 5:
        return signals

    # If domestic_burn_rate is None, it means no foreign grants were found on Schedule F
    burn = metrics.domestic_burn_rate
    if burn is not None:
        # Schedule F data exists — not a mismatch
        return signals

    # Also check if grants_made has any foreign grants
    has_foreign_grants = any(g.get("country") and g["country"] != "US" for g in (metrics.grants_made or []))
    if has_foreign_grants:
        return signals

    signals.append(
        ContradictionSignal(
            check_name="geographic_mismatch",
            severity=SignalSeverity.MEDIUM,
            category=SignalCategory.OPERATIONAL,
            headline=f"Claims {countries_claimed} geographic areas but no foreign grants on Schedule F",
            detail="Organization lists international operations but IRS filings show no foreign grant activity.",
            data_points={
                "geographic_areas_claimed": countries_claimed,
                "has_schedule_f_data": False,
            },
        )
    )
    return signals


@contradiction_check("excessive_reserves_non_zakat")
def check_excessive_reserves_non_zakat(metrics: CharityMetrics) -> list[ContradictionSignal]:
    """Non-zakat, non-endowment org with >36 months reserves."""
    signals: list[ContradictionSignal] = []

    # Skip zakat-collecting orgs (handled by zakat_hoarding in RiskScorer)
    if metrics.claims_zakat:
        return signals

    # Skip endowment/waqf models
    text = " ".join([metrics.name, metrics.mission or "", " ".join(metrics.programs)]).lower()
    endowment_signals = ["scholarship", "endowment", "waqf", "grant-making", "grantmaking"]
    if any(s in text for s in endowment_signals):
        return signals

    wc = metrics.working_capital_ratio or 0
    rm = metrics.reserves_months or 0
    months = max(wc, rm)

    if months < 36:
        return signals

    signals.append(
        ContradictionSignal(
            check_name="excessive_reserves_non_zakat",
            severity=SignalSeverity.MEDIUM,
            category=SignalCategory.FINANCIAL,
            headline=f"Holds {months:.0f} months of reserves without clear endowment model",
            detail="Organizations holding >36 months of reserves should publish deployment plans.",
            data_points={"reserves_months": round(months, 1)},
        )
    )
    return signals


@contradiction_check("high_fundraising_ratio")
def check_high_fundraising_ratio(metrics: CharityMetrics) -> list[ContradictionSignal]:
    """Fundraising >25% of expenses."""
    signals: list[ContradictionSignal] = []

    ratio = metrics.fundraising_expense_ratio
    if ratio is None:
        # Try to derive from raw values
        if metrics.fundraising_expenses and metrics.total_expenses and metrics.total_expenses > 0:
            ratio = metrics.fundraising_expenses / metrics.total_expenses
        else:
            return signals

    if ratio < 0.25:
        return signals

    severity = SignalSeverity.HIGH if ratio >= 0.35 else SignalSeverity.MEDIUM

    data: dict = {"fundraising_expense_ratio": round(ratio, 3)}
    if metrics.fundraising_expenses:
        data["fundraising_expenses"] = metrics.fundraising_expenses
    if metrics.total_expenses:
        data["total_expenses"] = metrics.total_expenses

    signals.append(
        ContradictionSignal(
            check_name="high_fundraising_ratio",
            severity=severity,
            category=SignalCategory.FINANCIAL,
            headline=f"Fundraising costs are {ratio:.0%} of total expenses",
            detail="High fundraising spend reduces funds available for programs.",
            data_points=data,
        )
    )
    return signals


@contradiction_check("implausible_cpb")
def check_implausible_cpb(metrics: CharityMetrics) -> list[ContradictionSignal]:
    """Cost per beneficiary <$1 suggests inflated counts."""
    signals: list[ContradictionSignal] = []

    if not metrics.total_expenses or not metrics.beneficiaries_served_annually:
        return signals
    if metrics.beneficiaries_served_annually <= 0:
        return signals

    cpb = metrics.total_expenses / metrics.beneficiaries_served_annually
    if cpb >= 1.0:
        return signals

    signals.append(
        ContradictionSignal(
            check_name="implausible_cpb",
            severity=SignalSeverity.MEDIUM,
            category=SignalCategory.IMPACT,
            headline=f"Cost per beneficiary is ${cpb:.2f} — implausibly low",
            detail="A cost below $1/beneficiary usually means beneficiary counts are inflated or double-counted.",
            data_points={
                "cost_per_beneficiary": round(cpb, 2),
                "total_expenses": metrics.total_expenses,
                "beneficiaries_served_annually": metrics.beneficiaries_served_annually,
            },
        )
    )
    return signals


@contradiction_check("revenue_expense_mismatch")
def check_revenue_expense_mismatch(metrics: CharityMetrics) -> list[ContradictionSignal]:
    """Expenses >= 2x revenue — unsustainable."""
    signals: list[ContradictionSignal] = []

    rev = metrics.total_revenue
    exp = metrics.total_expenses
    if not rev or not exp or rev <= 0:
        return signals

    ratio = exp / rev
    if ratio < 1.5:
        return signals

    if ratio >= 2.0:
        severity = SignalSeverity.HIGH
    else:
        severity = SignalSeverity.MEDIUM

    signals.append(
        ContradictionSignal(
            check_name="revenue_expense_mismatch",
            severity=severity,
            category=SignalCategory.FINANCIAL,
            headline=f"Expenses are {ratio:.1f}x revenue (${exp:,.0f} vs ${rev:,.0f})",
            detail="Spending significantly exceeding revenue is unsustainable without reserves drawdown.",
            data_points={
                "total_expenses": exp,
                "total_revenue": rev,
                "expense_to_revenue_ratio": round(ratio, 2),
            },
        )
    )
    return signals

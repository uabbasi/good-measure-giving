"""
Compare current scoring rubric vs EA-aligned rubric.
Shows before/after for key charities.
"""

import json
from dataclasses import dataclass

from src.db.client import execute_query


@dataclass
class CurrentScores:
    """Current scoring breakdown."""
    trust: int
    evidence: int
    effectiveness: int
    fit: int
    risk: int
    amal_score: int


@dataclass
class EffectivenessDetails:
    """Effectiveness sub-scores."""
    cost_efficiency: str  # EXCEPTIONAL, ABOVE_AVERAGE, etc.
    cost_efficiency_pts: int
    scale_efficiency: str
    scale_efficiency_pts: int
    room_for_funding: str
    room_for_funding_pts: int


@dataclass
class GovernanceData:
    """Governance signals."""
    board_size: int | None
    independent_board_pct: float | None
    has_audit: bool
    has_conflict_policy: bool
    ceo_compensation: int | None
    total_revenue: int | None


# ==== CURRENT RUBRIC ====
CURRENT_EFFECTIVENESS = {
    "cost_efficiency": 10,  # max
    "scale_efficiency": 10,  # max
    "room_for_funding": 5,  # max
}

CURRENT_ROOM_FOR_FUNDING = {
    "HEALTHY": 5,
    "COMFORTABLE": 4,
    "TIGHT": 3,
    "EXCESSIVE": 2,
    "UNKNOWN": 0,
}

# ==== EA-ALIGNED RUBRIC ====
EA_EFFECTIVENESS = {
    "cost_efficiency": 4,   # DOWN from 10 - overhead doesn't matter
    "scale_efficiency": 14,  # UP from 10 - core EA metric
    "room_for_funding": 7,   # UP from 5, but INVERTED logic
}

# Inverted: reward reasonable reserves, don't penalize
EA_ROOM_FOR_FUNDING = {
    "HEALTHY": 7,       # 1-6 months - good
    "COMFORTABLE": 7,   # 6-12 months - also good
    "PRUDENT": 6,       # 12-24 months - large orgs may need this
    "EXCESSIVE": 4,     # 24+ months - too much
    "TIGHT": 3,         # <1 month - sustainability risk
    "UNKNOWN": 0,
}

# Scale down cost efficiency points (10 max -> 4 max)
# EA doesn't weight overhead, so compress the range
EA_COST_EFFICIENCY_SCALE = {
    10: 4,  # EXCEPTIONAL -> 4
    8: 3,   # ABOVE_AVERAGE -> 3
    5: 2,   # AVERAGE -> 2
    3: 1,   # BELOW_AVERAGE -> 1
    0: 0,   # POOR -> 0
}

# Scale up scale efficiency points (10 max -> 14 max)
# Must map ALL possible values from all 3 calculation methods:
# - Method 1 (cause-adjusted): 10, 8, 5, 2
# - Method 2 (general benchmarks): 8, 6, 4, 2
# - Method 3 (efficiency proxy): 6, 5, 4, 3, 2
EA_SCALE_EFFICIENCY_SCALE = {
    10: 14,  # EXCELLENT (cause-adjusted best)
    8: 11,   # GOOD (cause-adjusted) or best general
    7: 10,   # Good general benchmark
    6: 8,    # Efficiency proxy best, or average general
    5: 7,    # AVERAGE (cause-adjusted)
    4: 5,    # Below average proxy or general
    3: 4,    # Low efficiency proxy
    2: 3,    # BELOW_AVERAGE
    1: 1,    # Edge case
    0: 0,    # UNKNOWN/POOR
}

# ==== GOVERNANCE PENALTIES ====
GOVERNANCE_PENALTIES = {
    "board_under_3": -5,          # Critical
    "board_independence_under_50": -3,  # Family/insider control
    "no_conflict_policy": -2,     # No guardrails
    "no_audit": -2,               # No oversight
    "ceo_comp_excessive": -2,     # Self-dealing flag
}


def calculate_ea_effectiveness(eff: EffectivenessDetails, working_capital_months: float | None) -> int:
    """Calculate EA-aligned effectiveness score."""
    # Scale down cost efficiency
    ce_pts = EA_COST_EFFICIENCY_SCALE.get(eff.cost_efficiency_pts, 0)

    # Scale up scale efficiency
    se_pts = EA_SCALE_EFFICIENCY_SCALE.get(eff.scale_efficiency_pts, 0)

    # Invert room for funding logic
    if working_capital_months is not None:
        if working_capital_months < 1:
            rf_pts = 3  # TIGHT - risky
        elif working_capital_months < 6:
            rf_pts = 7  # HEALTHY
        elif working_capital_months < 12:
            rf_pts = 7  # COMFORTABLE - also good
        elif working_capital_months < 24:
            rf_pts = 6  # PRUDENT - acceptable for large orgs
        else:
            rf_pts = 4  # EXCESSIVE - truly hoarding
    else:
        # Use current label as fallback
        rf_pts = EA_ROOM_FOR_FUNDING.get(eff.room_for_funding, 0)

    return ce_pts + se_pts + rf_pts


def calculate_governance_penalty(gov: GovernanceData) -> tuple[int, list[str]]:
    """Calculate governance risk deduction and flags."""
    penalty = 0
    flags = []

    # Board size
    if gov.board_size is not None and gov.board_size < 3:
        penalty += GOVERNANCE_PENALTIES["board_under_3"]
        flags.append(f"Board size {gov.board_size} < 3")

    # Board independence
    if gov.independent_board_pct is not None and gov.independent_board_pct < 0.5:
        penalty += GOVERNANCE_PENALTIES["board_independence_under_50"]
        flags.append(f"Board independence {gov.independent_board_pct:.0%} < 50%")

    # Conflict policy
    if not gov.has_conflict_policy:
        penalty += GOVERNANCE_PENALTIES["no_conflict_policy"]
        flags.append("No conflict of interest policy")

    # Audit
    if not gov.has_audit:
        penalty += GOVERNANCE_PENALTIES["no_audit"]
        flags.append("No independent audit")

    # CEO compensation (scale by revenue)
    if gov.ceo_compensation and gov.total_revenue:
        ceo_pct = gov.ceo_compensation / gov.total_revenue
        threshold = 0.05 if gov.total_revenue < 5_000_000 else 0.02 if gov.total_revenue < 50_000_000 else 0.01
        if ceo_pct > threshold:
            penalty += GOVERNANCE_PENALTIES["ceo_comp_excessive"]
            flags.append(f"CEO comp {ceo_pct:.1%} > {threshold:.0%} threshold")

    return penalty, flags


def check_governance_disqualifier(flags: list[str]) -> bool:
    """Check if org has 3+ governance failures."""
    return len(flags) >= 3


def main():
    # Get top 30 charities with full data
    sql = '''
    SELECT e.charity_ein, c.name, e.amal_score, e.confidence_scores, e.score_details,
           cd.board_size, cd.has_audited_financials, cd.total_revenue
    FROM evaluations e
    JOIN charities c ON e.charity_ein = c.ein
    LEFT JOIN charity_data cd ON e.charity_ein = cd.charity_ein
    ORDER BY e.amal_score DESC
    LIMIT 30
    '''
    rows = execute_query(sql)

    print("=" * 130)
    print("BEFORE vs AFTER: EA-Aligned Scoring Rubric")
    print("=" * 130)
    print()
    print(f"{'Name':<32} | {'BEFORE':>6} | {'AFTER':>6} | {'DIFF':>5} | {'Eff(B)':>6} | {'Eff(A)':>6} | {'Gov':>4} | Flags")
    print("-" * 130)

    for r in rows:
        name = (r['name'] or r['charity_ein'])[:32]

        scores = r.get('confidence_scores') or {}
        if isinstance(scores, str):
            scores = json.loads(scores)

        details = r.get('score_details') or {}
        if isinstance(details, str):
            details = json.loads(details)

        eff = details.get('effectiveness', {})
        risk = details.get('risks', {})

        # Current scores
        current = CurrentScores(
            trust=scores.get('trust', 0),
            evidence=scores.get('evidence', 0),
            effectiveness=scores.get('effectiveness', 0),
            fit=scores.get('fit', 0),
            risk=risk.get('total_deduction', 0),
            amal_score=r['amal_score'],
        )

        # Effectiveness details
        eff_details = EffectivenessDetails(
            cost_efficiency=eff.get('cost_efficiency', 'UNKNOWN'),
            cost_efficiency_pts=eff.get('cost_efficiency_points', 0),
            scale_efficiency=eff.get('scale_efficiency', 'UNKNOWN'),
            scale_efficiency_pts=eff.get('scale_efficiency_points', 0),
            room_for_funding=eff.get('room_for_funding', 'UNKNOWN'),
            room_for_funding_pts=eff.get('room_for_funding_points', 0),
        )

        # Governance data (limited - using what we have)
        gov = GovernanceData(
            board_size=r.get('board_size'),
            independent_board_pct=None,  # Not in DB yet
            has_audit=bool(r.get('has_audited_financials')),
            has_conflict_policy=True,  # Assume true if audited
            ceo_compensation=None,  # Not in DB yet
            total_revenue=r.get('total_revenue'),
        )

        # Calculate EA-aligned effectiveness
        ea_effectiveness = calculate_ea_effectiveness(eff_details, None)

        # Calculate governance penalty
        gov_penalty, gov_flags = calculate_governance_penalty(gov)

        # Governance disqualifier
        disqualified = check_governance_disqualifier(gov_flags)

        # Calculate new AMAL score
        # Keep Trust, Evidence, Fit same; replace Effectiveness; add governance to Risk
        ea_score = (
            current.trust +
            current.evidence +
            ea_effectiveness +
            current.fit +
            current.risk +
            gov_penalty
        )
        ea_score = max(0, min(100, ea_score))  # Clamp

        diff = ea_score - current.amal_score
        diff_str = f"+{diff}" if diff > 0 else str(diff)

        flags_str = "; ".join(gov_flags) if gov_flags else "-"
        if disqualified:
            flags_str = "⚠️ GOVERNANCE CONCERNS: " + flags_str

        print(f"{name:<32} | {current.amal_score:>6} | {ea_score:>6} | {diff_str:>5} | {current.effectiveness:>6} | {ea_effectiveness:>6} | {gov_penalty:>4} | {flags_str}")

    print()
    print("=" * 130)
    print("KEY CHANGES:")
    print("  - Cost Efficiency (overhead): 10 pts → 4 pts (EA doesn't weight overhead)")
    print("  - Scale Efficiency ($/beneficiary): 10 pts → 14 pts (core EA metric)")
    print("  - Room for Funding: 5 pts → 7 pts, INVERTED (reserves are good, not bad)")
    print("  - Governance penalties: Board <3 (-5), Independence <50% (-3), No audit (-2)")
    print("  - Governance Disqualifier: 3+ flags = ⚠️ warning")
    print("=" * 130)


if __name__ == "__main__":
    main()

"""
V2 Scorers - GMG Score 2-Dimension Framework (100 points)

2 scored dimensions + risk deductions + data confidence signal:
1. ImpactScorer - How much good per dollar, and can they prove it? (50 pts)
2. AlignmentScorer - Right fit for Muslim donors? (50 pts)
3. RiskScorer - What could go wrong? (-10 pts max)
4. DataConfidence - How much data do we have? (0.0-1.0, outside score)

Zakat eligibility determines wallet tag only, NOT score.

Max score: 100 points

Smooth scoring: continuous inputs use piecewise-linear interpolation
between expert-defined knots instead of step-function thresholds.

CRITICAL: All calculations are deterministic Python functions.
LLM must NEVER do math or guess data.
"""

from typing import Optional

from src.llm.schemas.baseline import (
    AlignmentAssessment,
    AmalScoresV2,
    CredibilityAssessment,
    DataConfidence,
    EffectivenessAssessment,
    EvidenceAssessment,
    FitAssessment,
    ImpactAssessment,
    TrustAssessment,
    ZakatBonusAssessment,
)
from src.llm.schemas.common import (
    CaseAgainst,
    ComponentStatus,
    EvidenceGrade,
    RiskCategory,
    RiskFactor,
    RiskSeverity,
    ScoreComponent,
)
from src.parsers.charity_metrics_aggregator import CharityMetrics
from src.scorers.strategic_evidence import (  # noqa: F401
    StrategicEvidence,
    compute_strategic_evidence,
)
from src.utils.scoring_audit import (
    ScoreImpact,
    ScoringAuditLog,
    get_audit_log,
)

# =============================================================================
# Rubric Version (semver)
# =============================================================================
# Major: structural break (dimensions change, scores not comparable)
# Minor: component reweight within same structure (scores shift)
# Patch: bug fix / data plumbing (scores shouldn't change)
#
# History:
#   1.0.0 — 4-dimension (Trust/Evidence/Effectiveness/Fit, each /25)
#   2.0.0 — 4-dimension revised (reweighted, new components)
#   3.0.0 — 3-dimension (Credibility/33 + Impact/33 + Alignment/34)
#   4.0.0 — 2-dimension (Impact/50 + Alignment/50 + DataConfidence signal)
RUBRIC_VERSION = "4.0.0"

# =============================================================================
# Constants - 2-Dimension GMG Score
# =============================================================================

# --- Revenue Tiers (size-adjusted expectations) ---
# Emerging: pass on formal rigor, reward hustle
# Growing: standard expectations, building systems
# Established: with big power comes big responsibility
REVENUE_TIER_THRESHOLDS = [
    (0, 1_000_000, "EMERGING"),
    (1_000_000, 10_000_000, "GROWING"),
    (10_000_000, float("inf"), "ESTABLISHED"),
]


def determine_revenue_tier(revenue: Optional[float]) -> str:
    """Determine revenue tier for size-adjusted expectations."""
    if revenue is None or revenue <= 0:
        return "EMERGING"  # Benefit of the doubt
    for lo, hi, tier in REVENUE_TIER_THRESHOLDS:
        if lo <= revenue < hi:
            return tier
    return "ESTABLISHED"


# =============================================================================
# Smooth Scoring Helper
# =============================================================================


def interpolate_score(value: float, knots: list) -> float:
    """Piecewise-linear interpolation between (value, score) knots.

    Replaces step-function thresholds with smooth interpolation.
    Knots must be sorted by the first element (value).

    Example:
        knots = [(0.0, 0), (0.50, 0), (0.65, 2), (0.75, 4), (0.85, 6), (1.0, 6)]
        interpolate_score(0.70, knots) → 3.0  (halfway between 2 and 4)
    """
    if value <= knots[0][0]:
        return knots[0][1]
    if value >= knots[-1][0]:
        return knots[-1][1]
    for i in range(len(knots) - 1):
        x0, y0 = knots[i]
        x1, y1 = knots[i + 1]
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return knots[-1][1]


# =============================================================================
# Data Confidence Weights (outside score, 0.0-1.0)
# =============================================================================

# Verification Tier → confidence value
VERIFICATION_CONFIDENCE = {
    "HIGH": 1.0,
    "MODERATE": 0.7,
    "BASIC": 0.4,
    "NONE": 0.0,
}

# Transparency → confidence value
TRANSPARENCY_CONFIDENCE = {
    "PLATINUM": 1.0,
    "GOLD": 0.86,
    "SILVER": 0.57,
    "BRONZE": 0.29,
    "NONE": 0.0,
}

# Data Quality → confidence value
DATA_QUALITY_CONFIDENCE = {
    "HIGH": 1.0,
    "MODERATE": 0.67,
    "LOW": 0.33,
    "CONFLICTING": 0.0,
}

# Weights for data confidence formula
DC_VERIFICATION_WEIGHT = 0.50
DC_TRANSPARENCY_WEIGHT = 0.35
DC_DATA_QUALITY_WEIGHT = 0.15

# --- Credibility (internal — feeds Impact quality-practice + DataConfidence) ---

# Verification Tier (used for DataConfidence, not scored directly)
VERIFICATION_TIER_POINTS = {
    "HIGH": 10,
    "MODERATE": 7,
    "BASIC": 4,
    "NONE": 0,
}

# Transparency (used for DataConfidence)
TRANSPARENCY_POINTS = {
    "PLATINUM": 7,
    "GOLD": 6,
    "SILVER": 4,
    "BRONZE": 2,
    "NONE": 0,
}

# Data Quality (used for DataConfidence)
DATA_QUALITY_POINTS = {
    "HIGH": 3,
    "MODERATE": 2,
    "LOW": 1,
    "CONFLICTING": 0,
}

# Theory of Change (3 pts in Impact, compressed from 5)
TOC_POINTS = {
    "STRONG": 3,
    "CLEAR": 3,
    "DEVELOPING": 2,
    "BASIC": 1,
    "ABSENT": 0,
}

# Evidence & Outcomes (5 pts in Impact)
EVIDENCE_OUTCOMES_POINTS = {
    "VERIFIED": 5,
    "TRACKED": 4,
    "MEASURED": 3,
    "REPORTED": 1,
    "UNVERIFIED": 0,
}

# Governance (2 pts in Impact, minimum 5 members is the standard)
GOVERNANCE_POINTS = {
    "STRONG": 2,  # Board of 7+ members
    "ADEQUATE": 2,  # Board of 5-6 members (standard)
    "MINIMAL": 1,  # Board of 3-4 members
    "WEAK": 0,  # Board < 3 or unknown
}

# --- Impact (50 pts) ---

# Cost Per Beneficiary (20 pts) - cause-adjusted benchmarks with interpolation
# Format: {cause_area: [(cpb_value, score), ...]} — interpolate between knots
CAUSE_BENCHMARKS = {
    "FOOD_HUNGER": [
        (0, 20),
        (0.25, 20),
        (0.50, 15),
        (1.00, 10),
        (5.00, 5),
        (float("inf"), 3),
    ],
    "EDUCATION_GLOBAL": [
        (0, 20),
        (100, 20),
        (300, 15),
        (750, 10),
        (2000, 5),
        (float("inf"), 3),
    ],
    "GLOBAL_HEALTH": [
        (0, 20),
        (25, 20),
        (75, 15),
        (150, 10),
        (500, 5),
        (float("inf"), 3),
    ],
    "HEALTHCARE_COMPLEX": [
        (0, 20),
        (500, 20),
        (1500, 15),
        (4000, 10),
        (10000, 5),
        (float("inf"), 3),
    ],
    "HUMANITARIAN": [
        (0, 20),
        (25, 20),
        (75, 15),
        (200, 10),
        (500, 5),
        (float("inf"), 3),
    ],
    "DOMESTIC_POVERTY": [
        (0, 20),
        (200, 20),
        (500, 15),
        (1200, 10),
        (3000, 5),
        (float("inf"), 3),
    ],
    "EXTREME_POVERTY": [
        (0, 20),
        (50, 20),
        (150, 15),
        (400, 10),
        (1000, 5),
        (float("inf"), 3),
    ],
    "RELIGIOUS_CULTURAL": [
        (0, 20),
        (50, 20),
        (125, 15),
        (300, 10),
        (800, 5),
        (float("inf"), 3),
    ],
    # Advocacy: systemic change, scholarships, fellowships — high CPB is structural
    "ADVOCACY": [
        (0, 20),
        (200, 20),
        (750, 15),
        (2000, 10),
        (5000, 5),
        (float("inf"), 3),
    ],
}

# General benchmarks when cause area unknown (max 15 pts)
GENERAL_CPB_KNOTS = [
    (0, 15),
    (50, 15),
    (100, 11),
    (250, 7),
    (1000, 3),
    (float("inf"), 3),
]

# Active conflict zones for 1.5x threshold adjustment
CONFLICT_ZONES = {
    "syria",
    "yemen",
    "sudan",
    "gaza",
    "palestine",
    "afghanistan",
    "drc",
    "congo",
    "somalia",
    "myanmar",
    "ukraine",
}

# Directness (7 pts, rescaled from 6)
DIRECTNESS_POINTS = {
    "DIRECT_SERVICE": 7,
    "DIRECT_PROVISION": 6,
    "CAPACITY_BUILDING": 5,
    "INSTITUTIONAL": 4,
    "SYSTEMIC_CHANGE": 2,
    "INDIRECT": 1,
}

# Directness keyword patterns for auto-detection
DIRECTNESS_KEYWORDS = {
    "DIRECT_SERVICE": [
        "surgery",
        "surgeries",
        "emergency medical",
        "food distribution",
        "cash transfer",
        "direct cash",
        "meals served",
        "feeding program",
        "medical care",
    ],
    "DIRECT_PROVISION": [
        "humanitarian aid",
        "primary healthcare",
        "housing",
        "shelter",
        "relief",
        "clean water",
        "aid distribution",
        "provision",
    ],
    "CAPACITY_BUILDING": [
        "education",
        "job training",
        "vocational",
        "agricultural program",
        "scholarship",
        "workforce development",
        "literacy",
    ],
    "INSTITUTIONAL": [
        "mosque construction",
        "school building",
        "community center",
        "water infrastructure",
        "well drilling",
        "borehole",
        "hospital construction",
        "clinic building",
    ],
    "SYSTEMIC_CHANGE": [
        "policy advocacy",
        "legal aid",
        "research",
        "legislative",
        "lobbying",
        "systemic reform",
        "policy change",
    ],
    "INDIRECT": [
        "awareness campaign",
        "fundraising",
        "public education campaign",
        "dawah",
    ],
}

# Financial Health (7 pts) - smooth interpolation with peak at 2 months
FINANCIAL_HEALTH_KNOTS = [
    (0, 0),
    (1, 3),
    (2, 7),
    (4, 5),
    (8, 3),
]
# Revenue-adjusted high/excessive floors appended dynamically

# Program Ratio (6 pts) - smooth interpolation
PROGRAM_RATIO_KNOTS = [
    (0.0, 0),
    (0.50, 0),
    (0.65, 2),
    (0.75, 4),
    (0.85, 6),
    (1.0, 6),
]

# --- Alignment (50 pts) ---

# Cause Urgency (13 pts, rescaled from 9)
CAUSE_URGENCY_POINTS = {
    "GLOBAL_HEALTH": 13,
    "HUMANITARIAN": 13,
    "EXTREME_POVERTY": 13,
    "EDUCATION_GLOBAL": 10,
    "DOMESTIC_POVERTY": 7,
    "ADVOCACY": 6,
    "RELIGIOUS_CULTURAL": 4,
    "UNKNOWN": 6,
}

# Funding Gap (5 pts, rescaled from 3)
FUNDING_GAP_THRESHOLDS = [
    (0, 1_000_000, 5),  # <$1M
    (1_000_000, 10_000_000, 5),  # $1-10M
    (10_000_000, 50_000_000, 3),  # $10-50M
    (50_000_000, float("inf"), 3),  # >$50M
]
FUNDING_GAP_UNKNOWN = 3  # Unknown revenue

# Track Record (6 pts) - smooth interpolation over years since founding
TRACK_RECORD_KNOTS = [
    (0, 1),
    (5, 2),
    (10, 4),
    (20, 6),
    (50, 6),
]

# Risk deductions (max -10) per spec
RISK_DEDUCTIONS = {
    "program_ratio_under_50": -5,
    "board_under_3": -5,
    "related_party_transactions": -3,
    "working_capital_under_1mo": -2,
    "no_outcome_measurement": -2,
    "no_toc": -1,
    "cn_advisory_flag": -3,
}

# Legacy constants for backward compatibility
EVIDENCE_GRADE_POINTS = {
    "A": 10,
    "B": 8,
    "C": 6,
    "D": 4,
    "F": 2,
}
OUTCOME_MEASUREMENT_POINTS = {
    "COMPREHENSIVE": 10,
    "STRONG": 8,
    "MODERATE": 6,
    "BASIC": 4,
    "WEAK": 2,
}
THEORY_OF_CHANGE_POINTS = {
    "PUBLISHED": 5,
    "DOCUMENTED": 4,
    "IMPLICIT": 2,
    "NONE": 0,
}
COUNTERFACTUAL_POINTS = {
    "HIGH": 10,
    "MEDIUM": 6,
    "LOW": 2,
}
CAUSE_IMPORTANCE_POINTS = {
    "GLOBAL_HEALTH": 9,
    "HUMANITARIAN": 9,
    "EXTREME_POVERTY": 9,
    "EDUCATION_GLOBAL": 7,
    "DOMESTIC_POVERTY": 5,
    "ADVOCACY": 4,
    "RELIGIOUS_CULTURAL": 2,
    "UNKNOWN": 3,
}
NEGLECTEDNESS_POINTS = {
    "MUSLIM_FOCUSED": 6,
    "NICHE": 4,
    "MAINSTREAM": 2,
}
# Legacy: old TRACK_RECORD_POINTS (categorical, kept for back-compat)
TRACK_RECORD_POINTS = {
    "VETERAN": 6,
    "ESTABLISHED": 4,
    "GROWING": 2,
    "NEW": 1,
}


# =============================================================================
# CredibilityScorer (INTERNAL — feeds DataConfidence + Impact quality-practice)
# =============================================================================


class CredibilityScorer:
    """Internal helper — evaluates data-availability signals.

    No longer a scored dimension. Its outputs feed:
    1. DataConfidence (verification, transparency, data quality)
    2. ImpactScorer quality-practice components (evidence, TOC, governance)

    Still returns CredibilityAssessment for internal use and legacy compatibility.
    """

    def __init__(self, audit_log: Optional[ScoringAuditLog] = None):
        self._audit_log = audit_log

    @property
    def audit_log(self) -> ScoringAuditLog:
        if self._audit_log is None:
            self._audit_log = get_audit_log()
        return self._audit_log

    def evaluate(self, metrics: CharityMetrics) -> CredibilityAssessment:
        """Evaluate credibility from charity metrics.

        Size-adjusted: Emerging orgs (<$1M) get baseline credit for TOC,
        Evidence, and Governance gaps. Established orgs (>$10M) get no passes.
        """
        components: list[ScoreComponent] = []
        tier = determine_revenue_tier(metrics.total_revenue)

        # 1. Verification Tier (10 pts)
        ver_tier, ver_reason = self._determine_verification_tier(metrics)
        ver_pts = VERIFICATION_TIER_POINTS[ver_tier]
        components.append(
            ScoreComponent(
                name="Verification Tier",
                scored=ver_pts,
                possible=10,
                evidence=ver_reason,
                status=ComponentStatus.FULL if ver_tier != "NONE" else ComponentStatus.MISSING,
                improvement_suggestion="Submit for Charity Navigator evaluation or update Candid profile"
                if ver_pts < 7
                else None,
                improvement_value=min(10 - ver_pts, 5) if ver_pts < 7 else 0,
            )
        )

        # 2. Transparency (7 pts) — Candid seal + non-Candid signals
        transparency, trans_pts = self._determine_transparency(metrics)
        if transparency.startswith("PARTIAL"):
            trans_evidence = f"No Candid seal; partial credit from other signals ({trans_pts}/7)"
        elif transparency == "NONE":
            trans_evidence = "No transparency signals found"
        else:
            trans_evidence = f"Candid seal: {transparency}"
        components.append(
            ScoreComponent(
                name="Transparency",
                scored=trans_pts,
                possible=7,
                evidence=trans_evidence,
                status=ComponentStatus.FULL
                if trans_pts >= 6
                else ComponentStatus.PARTIAL
                if trans_pts >= 1
                else ComponentStatus.MISSING,
                improvement_suggestion="Work toward Candid Gold/Platinum seal" if trans_pts < 6 else None,
                improvement_value=min(7 - trans_pts, 4) if trans_pts < 6 else 0,
            )
        )

        # 3. Data Quality (3 pts)
        dq_level, dq_pts = self._determine_data_quality(metrics)
        components.append(
            ScoreComponent(
                name="Data Quality",
                scored=dq_pts,
                possible=3,
                evidence=f"Data quality: {dq_level} ({self._count_sources(metrics)} corroborating sources)",
                status=ComponentStatus.FULL if dq_level == "HIGH" else ComponentStatus.PARTIAL,
            )
        )

        # 4. Theory of Change (5 pts internal) — tier-adjusted
        toc_level, toc_pts = self._determine_toc(metrics, tier)
        toc_evidence = f"Theory of change: {toc_level}"
        if tier == "EMERGING" and toc_pts > 0 and toc_level in ("ABSENT", "BASIC"):
            toc_evidence += " (emerging org baseline)"
        components.append(
            ScoreComponent(
                name="Theory of Change",
                scored=toc_pts,
                possible=5,
                evidence=toc_evidence,
                status=ComponentStatus.FULL
                if toc_level in ("STRONG", "CLEAR")
                else ComponentStatus.PARTIAL
                if toc_pts >= 2
                else ComponentStatus.MISSING,
                improvement_suggestion="Document a clear theory of change with causal pathway" if toc_pts < 4 else None,
                improvement_value=min(5 - toc_pts, 3) if toc_pts < 4 else 0,
            )
        )

        # 5. Evidence & Outcomes (5 pts internal) — tier-adjusted
        eq_level, eq_pts = self._determine_evidence_outcomes(metrics, tier)
        eq_evidence = f"Evidence & outcomes: {eq_level}"
        if tier == "EMERGING" and eq_pts > 0 and eq_level in ("UNVERIFIED", "REPORTED"):
            eq_evidence += " (emerging org baseline)"
        components.append(
            ScoreComponent(
                name="Evidence & Outcomes",
                scored=eq_pts,
                possible=5,
                evidence=eq_evidence,
                status=ComponentStatus.FULL
                if eq_level in ("VERIFIED", "TRACKED")
                else ComponentStatus.PARTIAL
                if eq_pts >= 2
                else ComponentStatus.MISSING,
                improvement_suggestion="Seek external evaluation or track outcomes for 3+ years"
                if eq_pts < 4
                else None,
                improvement_value=min(5 - eq_pts, 3) if eq_pts < 4 else 0,
            )
        )

        # 6. Governance (3 pts internal) — tier-adjusted
        gov_level, gov_pts = self._determine_governance(metrics, tier)
        gov_evidence = f"Board governance: {gov_level} ({metrics.board_size or 'unknown'} members)"
        if tier == "EMERGING" and gov_pts > 0 and gov_level == "WEAK":
            gov_evidence = f"Board governance: baseline ({metrics.board_size or 'unknown'} members, emerging org)"
        components.append(
            ScoreComponent(
                name="Governance",
                scored=gov_pts,
                possible=3,
                evidence=gov_evidence,
                status=ComponentStatus.FULL
                if gov_level in ("STRONG", "ADEQUATE")
                else ComponentStatus.PARTIAL
                if gov_pts >= 1
                else ComponentStatus.MISSING,
                improvement_suggestion="Expand board to 5+ members for stronger governance" if gov_pts < 2 else None,
                improvement_value=max(0, 2 - gov_pts) if gov_pts < 2 else 0,
            )
        )

        total = sum(c.scored for c in components)
        total = min(33, total)

        # Determine capacity-limited flag
        capacity_limited = self._is_capacity_limited(metrics, eq_level, toc_level)

        rationale = self._build_rationale(metrics, ver_tier, toc_level, eq_level, total)

        return CredibilityAssessment(
            score=total,
            components=components,
            rationale=rationale,
            verification_tier=ver_tier,
            theory_of_change_level=toc_level,
            evidence_quality_level=eq_level,
            confidence_notes=self._build_confidence_notes(metrics),
            corroboration_notes=self._build_corroboration_notes(metrics),
            capacity_limited_evidence=capacity_limited,
        )

    def _determine_verification_tier(self, metrics: CharityMetrics) -> tuple[str, str]:
        """Determine verification tier using multi-signal approach."""
        signals = []
        reasons = []

        # Check each third-party signal
        if metrics.cn_overall_score is not None and metrics.cn_overall_score >= 90:
            signals.append("cn_high")
            reasons.append(f"CN score {metrics.cn_overall_score:.0f}")
        elif metrics.cn_overall_score is not None and metrics.cn_overall_score >= 75:
            signals.append("cn_moderate")
            reasons.append(f"CN score {metrics.cn_overall_score:.0f}")

        candid_seal = (metrics.candid_seal or "").upper()
        if candid_seal in ("GOLD", "PLATINUM"):
            signals.append("candid_gold_plus")
            reasons.append(f"Candid {candid_seal} seal")
        elif candid_seal in ("SILVER",):
            signals.append("candid_silver")
            reasons.append(f"Candid {candid_seal} seal")

        if metrics.has_financial_audit:
            signals.append("audited")
            reasons.append("Independent financial audit")

        if metrics.irs_990_available and metrics.total_revenue and metrics.total_revenue > 0:
            signals.append("990_available")

        high_signals = [s for s in signals if s in ("cn_high", "candid_gold_plus", "audited")]
        moderate_signals = [s for s in signals if s in ("cn_moderate", "candid_silver", "cn_high", "candid_gold_plus")]

        if len(high_signals) >= 2:
            return "HIGH", "; ".join(reasons[:3])
        if metrics.has_financial_audit:
            return "HIGH", "Independent financial audit"
        if len(moderate_signals) >= 1:
            return "MODERATE", "; ".join(reasons[:3])
        if signals:
            return "BASIC", "; ".join(reasons[:3]) or "Has third-party profile"
        return "NONE", "No third-party verification"

    def _determine_transparency(self, metrics: CharityMetrics) -> tuple[str, int]:
        """Determine transparency from Candid seal + non-Candid signals.

        Candid seal remains the gold standard, but charities without a seal
        can earn partial credit from audited financials, CN rating, or 990 filing.
        """
        seal = (metrics.candid_seal or "").upper()
        if seal == "PLATINUM":
            return "PLATINUM", TRANSPARENCY_POINTS["PLATINUM"]
        elif seal == "GOLD":
            return "GOLD", TRANSPARENCY_POINTS["GOLD"]
        elif seal == "SILVER":
            return "SILVER", TRANSPARENCY_POINTS["SILVER"]
        elif seal == "BRONZE":
            return "BRONZE", TRANSPARENCY_POINTS["BRONZE"]

        # No Candid seal — check non-Candid transparency signals
        signals = 0
        if metrics.has_financial_audit:
            signals += 2
        if metrics.cn_overall_score is not None:
            signals += 1
        if metrics.irs_990_available:
            signals += 1

        if signals >= 3:
            return "PARTIAL_HIGH", 3
        elif signals >= 2:
            return "PARTIAL", 2
        elif signals >= 1:
            return "PARTIAL_LOW", 1
        return "NONE", 0

    def _determine_data_quality(self, metrics: CharityMetrics) -> tuple[str, int]:
        """Determine data quality from source count."""
        count = self._count_sources(metrics)
        if count >= 4:
            return "HIGH", DATA_QUALITY_POINTS["HIGH"]
        elif count >= 2:
            return "MODERATE", DATA_QUALITY_POINTS["MODERATE"]
        elif count >= 1:
            return "LOW", DATA_QUALITY_POINTS["LOW"]
        return "CONFLICTING", 0

    def _count_sources(self, metrics: CharityMetrics) -> int:
        """Count corroborating data sources."""
        count = 0
        if metrics.cn_overall_score is not None:
            count += 1
        if metrics.candid_seal is not None:
            count += 1
        if metrics.irs_990_available:
            count += 1
        if metrics.mission and len(metrics.programs) > 0:
            count += 1  # Website data available
        return count

    def _determine_toc(self, metrics: CharityMetrics, tier: str = "GROWING") -> tuple[str, int]:
        """Determine Theory of Change level.

        Tier-adjusted: Emerging orgs get 2pt baseline if they have a mission
        statement (their programs ARE their theory of change).
        """
        toc = metrics.has_theory_of_change or False
        toc_text = metrics.theory_of_change or ""

        if toc and len(toc_text) > 200:
            if metrics.third_party_evaluated:
                return "STRONG", TOC_POINTS["STRONG"]
            return "CLEAR", TOC_POINTS["CLEAR"]
        elif toc and toc_text:
            return "DEVELOPING", TOC_POINTS["DEVELOPING"]
        elif toc:
            return "BASIC", TOC_POINTS["BASIC"]

        # No TOC — tier-adjusted baseline
        if tier == "EMERGING" and metrics.mission:
            return "BASIC", 2  # Mission serves as implicit TOC for small orgs
        return "ABSENT", TOC_POINTS["ABSENT"]

    def _determine_evidence_outcomes(self, metrics: CharityMetrics, tier: str = "GROWING") -> tuple[str, int]:
        """Determine evidence & outcomes level (merged evidence quality + outcome tracking).

        Tier-adjusted: Emerging orgs get 2pt baseline — they often lack
        formal M&E systems but are doing the work.
        """
        if metrics.third_party_evaluated:
            return "VERIFIED", EVIDENCE_OUTCOMES_POINTS["VERIFIED"]

        years = metrics.candid_max_years_tracked or 0
        has_methodology = metrics.has_outcome_methodology or False

        if years >= 3 and has_methodology:
            return "TRACKED", EVIDENCE_OUTCOMES_POINTS["TRACKED"]
        elif years >= 1 or metrics.candid_metrics_count:
            return "MEASURED", EVIDENCE_OUTCOMES_POINTS["MEASURED"]
        elif metrics.reports_outcomes:
            return "REPORTED", EVIDENCE_OUTCOMES_POINTS["REPORTED"]

        # No evidence — tier-adjusted baseline
        if tier == "EMERGING":
            return "UNVERIFIED", 2  # Capacity pass for small orgs
        return "UNVERIFIED", EVIDENCE_OUTCOMES_POINTS["UNVERIFIED"]

    def _determine_governance(self, metrics: CharityMetrics, tier: str = "GROWING") -> tuple[str, int]:
        """Determine governance quality from board size.

        Standard: 5+ members is the baseline expectation.
        Tier-adjusted: Emerging orgs get 1pt baseline — small orgs often
        have informal governance that works fine at their scale.
        """
        board = metrics.board_size
        if board is not None and board >= 7:
            return "STRONG", GOVERNANCE_POINTS["STRONG"]
        elif board is not None and board >= 5:
            return "ADEQUATE", GOVERNANCE_POINTS["ADEQUATE"]
        elif board is not None and board >= 3:
            return "MINIMAL", GOVERNANCE_POINTS["MINIMAL"]

        # Weak/unknown governance — tier-adjusted baseline
        if tier == "EMERGING":
            return "WEAK", 1  # Capacity pass for small orgs
        return "WEAK", GOVERNANCE_POINTS["WEAK"]

    def _is_capacity_limited(self, metrics: CharityMetrics, eq_level: str, toc_level: str) -> bool:  # noqa: ARG002
        """Check if low evidence likely reflects limited M&E capacity."""
        if eq_level in ("VERIFIED", "TRACKED"):
            return False
        if metrics.total_revenue and metrics.total_revenue < 1_000_000:
            return True
        if metrics.employees_count and metrics.employees_count < 10:
            return True
        return False

    def _build_rationale(
        self, _metrics: CharityMetrics, ver_tier: str, toc_level: str, eq_level: str, total: int
    ) -> str:
        parts = []
        if ver_tier == "HIGH":
            parts.append("Strong third-party verification")
        elif ver_tier == "MODERATE":
            parts.append("Some third-party verification")
        else:
            parts.append("Limited verification")

        parts.append(f"TOC: {toc_level.lower()}")
        parts.append(f"Evidence: {eq_level.lower()}")
        parts.append(f"Credibility {total}/33")
        return "; ".join(parts)

    def _build_confidence_notes(self, metrics: CharityMetrics) -> list[str]:
        notes = []
        if not metrics.irs_990_available:
            notes.append("Form 990 not available")
        if not metrics.has_financial_audit:
            notes.append("No independent audit")
        if not metrics.candid_seal:
            notes.append("No Candid transparency seal")
        return notes

    def _build_corroboration_notes(self, metrics: CharityMetrics) -> list[str]:
        notes = []
        if hasattr(metrics, "corroboration_status"):
            for field, status in metrics.corroboration_status.items():
                if status.get("passed"):
                    notes.append(f"{field}: corroborated by {', '.join(status.get('sources', []))}")
        return notes


# =============================================================================
# ImpactScorer (50 pts max)
# =============================================================================


class ImpactScorer:
    """Evaluates impact dimension (50 points max).

    "How much good per dollar, and can they prove it?"

    Components:
    - Cost Per Beneficiary (20 pts): Cause-adjusted benchmarks with smooth interpolation
    - Directness (7 pts): How directly funds reach people
    - Financial Health (7 pts): Smooth interpolation with peak at 2 months
    - Program Ratio (6 pts): Smooth interpolation over 0.0-1.0
    - Evidence & Outcomes (5 pts): Grade-based (absorbed from Credibility)
    - Theory of Change (3 pts): Categorical (absorbed from Credibility)
    - Governance (2 pts): Board size (absorbed from Credibility)
    """

    def __init__(self, credibility_scorer: Optional[CredibilityScorer] = None):
        self._credibility = credibility_scorer or CredibilityScorer()

    def evaluate(self, metrics: CharityMetrics, cause_area: str = "DEFAULT") -> ImpactAssessment:
        """Evaluate impact from charity metrics."""
        components: list[ScoreComponent] = []
        tier = determine_revenue_tier(metrics.total_revenue)

        # Run internal credibility assessment to get quality-practice levels
        cred = self._credibility.evaluate(metrics)

        # 1. Cost Per Beneficiary (20 pts)
        cpb, cpb_pts, cpb_evidence = self._score_cost_per_beneficiary(metrics, cause_area)
        components.append(
            ScoreComponent(
                name="Cost Per Beneficiary",
                scored=cpb_pts,
                possible=20,
                evidence=cpb_evidence,
                status=ComponentStatus.FULL if cpb is not None else ComponentStatus.MISSING,
                improvement_suggestion="Track and report beneficiary counts to enable cost analysis"
                if cpb is None
                else None,
                improvement_value=min(20 - cpb_pts, 10) if cpb_pts < 10 else 0,
            )
        )

        # 2. Directness (7 pts)
        dir_level, dir_pts = self._score_directness(metrics)
        components.append(
            ScoreComponent(
                name="Directness",
                scored=dir_pts,
                possible=7,
                evidence=f"Delivery model: {dir_level.replace('_', ' ').title()}",
                status=ComponentStatus.FULL,
            )
        )

        # 3. Financial Health (7 pts) — smooth interpolation
        fh_label, fh_pts = self._score_financial_health(metrics)
        wc = metrics.working_capital_ratio
        fh_evidence = (
            f"Working capital: {wc:.1f} months ({fh_label})"
            if wc is not None and wc >= 0.1
            else f"Working capital: unknown ({fh_label})"
        )
        components.append(
            ScoreComponent(
                name="Financial Health",
                scored=fh_pts,
                possible=7,
                evidence=fh_evidence,
                status=ComponentStatus.FULL if wc is not None and wc >= 0.1 else ComponentStatus.MISSING,
                improvement_suggestion="Build working capital reserves to 1-3 months of operating expenses"
                if fh_pts < 5
                else None,
                improvement_value=min(7 - fh_pts, 4) if fh_pts < 5 else 0,
            )
        )

        # 4. Program Ratio (6 pts) — smooth interpolation
        pr_pts, pr_evidence = self._score_program_ratio(metrics)
        components.append(
            ScoreComponent(
                name="Program Ratio",
                scored=pr_pts,
                possible=6,
                evidence=pr_evidence,
                status=ComponentStatus.FULL
                if metrics.program_expense_ratio is not None and metrics.program_expense_ratio >= 0.01
                else ComponentStatus.MISSING,
            )
        )

        # 5. Evidence & Outcomes (5 pts) — absorbed from Credibility
        eq_level = cred.evidence_quality_level
        eq_pts = self._score_evidence_outcomes(eq_level, tier)
        eq_evidence = f"Evidence & outcomes: {eq_level}"
        if tier == "EMERGING" and eq_pts > 0 and eq_level in ("UNVERIFIED", "REPORTED"):
            eq_evidence += " (emerging org baseline)"
        components.append(
            ScoreComponent(
                name="Evidence & Outcomes",
                scored=eq_pts,
                possible=5,
                evidence=eq_evidence,
                status=ComponentStatus.FULL
                if eq_level in ("VERIFIED", "TRACKED")
                else ComponentStatus.PARTIAL
                if eq_pts >= 2
                else ComponentStatus.MISSING,
                improvement_suggestion="Seek external evaluation or track outcomes for 3+ years"
                if eq_pts < 4
                else None,
                improvement_value=min(5 - eq_pts, 3) if eq_pts < 4 else 0,
            )
        )

        # 6. Theory of Change (3 pts) — absorbed from Credibility, compressed
        toc_level = cred.theory_of_change_level
        toc_pts = TOC_POINTS.get(toc_level, 0)
        # Tier-adjusted: emerging orgs get baseline
        if tier == "EMERGING" and toc_pts == 0 and metrics.mission:
            toc_pts = 1
        toc_evidence = f"Theory of change: {toc_level}"
        if tier == "EMERGING" and toc_level in ("ABSENT", "BASIC"):
            toc_evidence += " (emerging org baseline)"
        components.append(
            ScoreComponent(
                name="Theory of Change",
                scored=toc_pts,
                possible=3,
                evidence=toc_evidence,
                status=ComponentStatus.FULL
                if toc_level in ("STRONG", "CLEAR")
                else ComponentStatus.PARTIAL
                if toc_pts >= 1
                else ComponentStatus.MISSING,
                improvement_suggestion="Document a clear theory of change with causal pathway" if toc_pts < 3 else None,
                improvement_value=min(3 - toc_pts, 2) if toc_pts < 3 else 0,
            )
        )

        # 7. Governance (2 pts) — absorbed from Credibility
        gov_level, gov_pts = self._score_governance(metrics, tier)
        gov_evidence = f"Board governance: {gov_level} ({metrics.board_size or 'unknown'} members)"
        if tier == "EMERGING" and gov_pts > 0 and gov_level == "WEAK":
            gov_evidence = f"Board governance: baseline ({metrics.board_size or 'unknown'} members, emerging org)"
        components.append(
            ScoreComponent(
                name="Governance",
                scored=gov_pts,
                possible=2,
                evidence=gov_evidence,
                status=ComponentStatus.FULL
                if gov_level in ("STRONG", "ADEQUATE")
                else ComponentStatus.PARTIAL
                if gov_pts >= 1
                else ComponentStatus.MISSING,
            )
        )

        total = min(50, sum(c.scored for c in components))
        rationale = self._build_rationale(metrics, cpb, dir_level, total)

        return ImpactAssessment(
            score=total,
            components=components,
            rationale=rationale,
            cost_per_beneficiary=cpb,
            directness_level=dir_level,
            impact_design_categories=[],
        )

    def _score_evidence_outcomes(self, eq_level: str, tier: str) -> int:
        """Score Evidence & Outcomes (5 pts) using categorical levels."""
        pts = EVIDENCE_OUTCOMES_POINTS.get(eq_level, 0)
        # Tier-adjusted: emerging orgs get 2pt baseline
        if tier == "EMERGING" and pts == 0:
            pts = 2
        return pts

    def _score_governance(self, metrics: CharityMetrics, tier: str) -> tuple[str, int]:
        """Score governance (2 pts). Standard: 5+ members."""
        board = metrics.board_size
        if board is not None and board >= 7:
            return "STRONG", GOVERNANCE_POINTS["STRONG"]
        elif board is not None and board >= 5:
            return "ADEQUATE", GOVERNANCE_POINTS["ADEQUATE"]
        elif board is not None and board >= 3:
            return "MINIMAL", GOVERNANCE_POINTS["MINIMAL"]
        if tier == "EMERGING":
            return "WEAK", 1
        return "WEAK", GOVERNANCE_POINTS["WEAK"]

    def _score_cost_per_beneficiary(self, metrics: CharityMetrics, cause_area: str) -> tuple[Optional[float], int, str]:
        """Score cost per beneficiary against cause-adjusted benchmarks (20 pts max).

        Uses smooth interpolation between knots instead of step functions.
        """
        cpb = self._calculate_cpb(metrics)

        # Method 1: GiveWell data (highest fidelity)
        gw_multiplier = metrics.givewell_cost_effectiveness_multiplier
        if gw_multiplier is not None and gw_multiplier > 0:
            if gw_multiplier >= 10:
                return cpb, 20, f"GiveWell: {gw_multiplier:.0f}x cash benchmark"
            elif gw_multiplier >= 3:
                return cpb, 15, f"GiveWell: {gw_multiplier:.0f}x cash benchmark"
            elif gw_multiplier >= 1:
                return cpb, 10, f"GiveWell: {gw_multiplier:.0f}x cash benchmark"
            else:
                return cpb, 5, f"GiveWell: {gw_multiplier:.1f}x cash benchmark (below cash)"

        if metrics.is_givewell_top_charity:
            return cpb, 15, "GiveWell top charity"

        if cpb is None or cpb <= 0:
            # Partial credit based on program ratio when CPB data is unavailable
            pr = metrics.program_expense_ratio
            if pr is not None and pr >= 0.85:
                return None, 9, "No beneficiary data; high program ratio (≥85%) suggests efficient delivery"
            elif pr is not None and pr >= 0.75:
                return None, 6, "No beneficiary data; good program ratio (≥75%) suggests reasonable delivery"
            elif pr is not None and pr >= 0.65:
                return None, 3, "No beneficiary data; moderate program ratio (≥65%)"
            return None, 0, "Insufficient data for cost-per-beneficiary calculation"

        # Method 2: Cause-adjusted benchmark with interpolation
        effective_cause = cause_area if cause_area != "DEFAULT" else (metrics.detected_cause_area or "DEFAULT")

        # Adjust for conflict zones
        multiplier = 1.0
        if self._operates_in_conflict_zone(metrics):
            multiplier = 1.5

        knots = CAUSE_BENCHMARKS.get(effective_cause)
        if knots:
            # Scale CPB by conflict multiplier (effectively shifts thresholds)
            adjusted_cpb = cpb / multiplier if multiplier > 1.0 else cpb
            score = round(interpolate_score(adjusted_cpb, knots))
            label = self._cpb_label(score)
            return cpb, score, f"${cpb:.2f}/beneficiary ({label} for {effective_cause})"

        # Method 3: General benchmark with interpolation (max 15 pts)
        adjusted_cpb = cpb / multiplier if multiplier > 1.0 else cpb
        score = round(interpolate_score(adjusted_cpb, GENERAL_CPB_KNOTS))
        return cpb, score, f"${cpb:.2f}/beneficiary (general benchmark)"

    def _calculate_cpb(self, metrics: CharityMetrics) -> Optional[float]:
        """Calculate cost per beneficiary."""
        if metrics.beneficiaries_served_annually and metrics.beneficiaries_served_annually > 0:
            expenses = metrics.program_expenses or metrics.total_expenses
            if expenses and expenses > 0:
                return expenses / metrics.beneficiaries_served_annually
        return None

    def _cpb_label(self, points: int) -> str:
        if points >= 18:
            return "exceptional"
        elif points >= 14:
            return "excellent"
        elif points >= 10:
            return "good"
        elif points >= 5:
            return "average"
        return "below average"

    def _score_directness(self, metrics: CharityMetrics) -> tuple[str, int]:
        """Score how directly funds reach beneficiaries (7 pts)."""
        text = " ".join(
            [
                metrics.mission or "",
                " ".join(metrics.program_descriptions or []),
                " ".join(metrics.programs or []),
            ]
        ).lower()

        # Check from most direct to least
        for level in [
            "DIRECT_SERVICE",
            "DIRECT_PROVISION",
            "CAPACITY_BUILDING",
            "INSTITUTIONAL",
            "SYSTEMIC_CHANGE",
            "INDIRECT",
        ]:
            keywords = DIRECTNESS_KEYWORDS[level]
            if any(kw in text for kw in keywords):
                return level, DIRECTNESS_POINTS[level]

        # Default: capacity building (middle ground)
        return "CAPACITY_BUILDING", DIRECTNESS_POINTS["CAPACITY_BUILDING"]

    def _is_endowment_model(self, metrics: CharityMetrics) -> bool:
        """Detect endowment/waqf/scholarship fund models where high reserves are expected."""
        text = " ".join(
            [
                metrics.name,
                metrics.mission or "",
                " ".join(metrics.programs),
            ]
        ).lower()
        endowment_signals = ["scholarship", "endowment", "waqf", "grant-making", "grantmaking"]
        return any(s in text for s in endowment_signals)

    def _score_financial_health(self, metrics: CharityMetrics) -> tuple[str, int]:
        """Score financial health from working capital ratio (7 pts).

        Uses smooth piecewise-linear interpolation with peak at 2 months.
        Revenue-adjusted high/excessive floors.
        Endowment/scholarship models get a neutral score — high reserves are
        the business model, not a red flag.
        """
        ratio = metrics.working_capital_ratio
        if ratio is None or ratio < 0.1:
            return "UNKNOWN", 0

        # Endowment models: high reserves are expected, score as HEALTHY (4/7)
        if self._is_endowment_model(metrics) and ratio > 6:
            return "ENDOWMENT", 4

        # Revenue-adjusted thresholds for tail knots
        revenue = metrics.total_revenue or 0
        if revenue > 0 and revenue < 500_000:
            high_floor = 18
            excessive_floor = 36
        elif revenue >= 5_000_000:
            high_floor = 9
            excessive_floor = 18
        else:
            high_floor = 12
            excessive_floor = 24

        # Build full knot set with revenue-adjusted tail
        knots = list(FINANCIAL_HEALTH_KNOTS) + [
            (high_floor, 1),
            (excessive_floor, 0),
        ]

        score = round(interpolate_score(ratio, knots))

        # Determine label for evidence string
        if ratio < 1:
            label = "TIGHT"
        elif ratio < 3:
            label = "OPTIMAL"
        elif ratio < 6:
            label = "HEALTHY"
        elif ratio < high_floor:
            label = "COMFORTABLE"
        elif ratio < excessive_floor:
            label = "HIGH"
        else:
            label = "EXCESSIVE"

        return label, score

    def _score_program_ratio(self, metrics: CharityMetrics) -> tuple[int, str]:
        """Score program expense ratio with smooth interpolation (6 pts)."""
        ratio = metrics.program_expense_ratio
        if ratio is None or ratio < 0.01:
            return 0, "Program expense ratio: unknown"

        score = round(interpolate_score(ratio, PROGRAM_RATIO_KNOTS))
        return score, f"Program expense ratio: {ratio:.0%}"

    def _operates_in_conflict_zone(self, metrics: CharityMetrics) -> bool:
        """Check if charity operates in conflict zones."""
        geo = " ".join(metrics.geographic_coverage).lower()
        return any(zone in geo for zone in CONFLICT_ZONES)

    def _build_rationale(self, metrics: CharityMetrics, cpb: Optional[float], dir_level: str, total: int) -> str:
        parts = []
        if metrics.is_givewell_top_charity:
            parts.append("GiveWell top charity")
        if cpb is not None:
            parts.append(f"${cpb:.2f}/beneficiary")
        parts.append(f"Delivery: {dir_level.replace('_', ' ').lower()}")
        parts.append(f"Impact {total}/50")
        return "; ".join(parts)


# =============================================================================
# AlignmentScorer (50 pts max)
# =============================================================================


class AlignmentScorer:
    """Evaluates alignment dimension (50 points max).

    "Is this the right charity for me as a Muslim donor?"

    Components:
    - Muslim Donor Fit (19 pts): Layered additive (rescaled from 13)
    - Cause Urgency (13 pts): Cause map (rescaled from 9)
    - Underserved Space (7 pts): Niche cause + underserved populations (rescaled from 5)
    - Track Record (6 pts): Smooth interpolation over years since founding (rescaled from 4)
    - Funding Gap (5 pts): Compressed revenue tiers (rescaled from 3)
    """

    def __init__(self, audit_log: Optional[ScoringAuditLog] = None):
        self._audit_log = audit_log

    @property
    def audit_log(self) -> ScoringAuditLog:
        if self._audit_log is None:
            self._audit_log = get_audit_log()
        return self._audit_log

    def evaluate(self, metrics: CharityMetrics) -> AlignmentAssessment:
        """Evaluate alignment from charity metrics."""
        components: list[ScoreComponent] = []

        # 1. Muslim Donor Fit (19 pts)
        mdf_pts, mdf_level, mdf_evidence = self._score_muslim_donor_fit(metrics)
        components.append(
            ScoreComponent(
                name="Muslim Donor Fit",
                scored=mdf_pts,
                possible=19,
                evidence=mdf_evidence,
                status=ComponentStatus.FULL if mdf_pts >= 12 else ComponentStatus.PARTIAL,
            )
        )

        # 2. Cause Urgency (13 pts)
        cause_area = metrics.detected_cause_area or "UNKNOWN"
        cu_pts = CAUSE_URGENCY_POINTS.get(cause_area, 6)
        components.append(
            ScoreComponent(
                name="Cause Urgency",
                scored=cu_pts,
                possible=13,
                evidence=f"Cause area: {cause_area.replace('_', ' ').title()} ({cu_pts}/13)",
                status=ComponentStatus.FULL if cause_area != "UNKNOWN" else ComponentStatus.PARTIAL,
            )
        )

        # 3. Underserved Space (7 pts)
        us_pts, us_evidence = self._score_underserved_space(metrics)
        components.append(
            ScoreComponent(
                name="Underserved Space",
                scored=us_pts,
                possible=7,
                evidence=us_evidence,
                status=ComponentStatus.FULL if us_pts >= 4 else ComponentStatus.PARTIAL,
            )
        )

        # 4. Track Record (6 pts) — smooth interpolation
        tr_pts, tr_evidence = self._score_track_record(metrics)
        components.append(
            ScoreComponent(
                name="Track Record",
                scored=tr_pts,
                possible=6,
                evidence=tr_evidence,
                status=ComponentStatus.FULL if tr_pts >= 4 else ComponentStatus.PARTIAL,
            )
        )

        # 5. Funding Gap (5 pts)
        fg_pts, fg_evidence = self._score_funding_gap(metrics)
        components.append(
            ScoreComponent(
                name="Funding Gap",
                scored=fg_pts,
                possible=5,
                evidence=fg_evidence,
                status=ComponentStatus.FULL if metrics.total_revenue is not None else ComponentStatus.PARTIAL,
            )
        )

        total = min(50, sum(c.scored for c in components))
        rationale = (
            f"Alignment {total}/50: {mdf_level} Muslim donor fit, {cause_area.replace('_', ' ').lower()} cause area"
        )

        return AlignmentAssessment(
            score=total,
            components=components,
            rationale=rationale,
            muslim_donor_fit_level=mdf_level,
            cause_urgency_label=cause_area,
        )

    def _score_muslim_donor_fit(self, metrics: CharityMetrics) -> tuple[int, str, str]:
        """Score Muslim Donor Fit using layered additive approach (19 pts max).

        Muslim-exclusive layers (7 pts ceiling):
        - Zakat clarity: +4 (explicit zakat program) or +2 (zakat accepted)
        - Muslim-focused org: +2
        - Islamic identity markers: +1

        Universal layers (12 pts ceiling):
        - Asnaf alignment: +5 (serves specific asnaf category)
        - Muslim-majority regions: +3
        - Humanitarian service: +4 (work that directly helps vulnerable populations)
        Cap at 19.
        """
        pts = 0
        layers = []

        claims_zakat = metrics.zakat_claim_detected or False
        is_muslim = metrics.is_muslim_focused or False

        # --- Muslim-exclusive layers (7 pts) ---

        # Zakat clarity (+4 or +2)
        if claims_zakat:
            zakat_evidence = metrics.zakat_claim_evidence or ""
            zakat_lower = zakat_evidence.lower()
            if (
                "100%" in zakat_evidence
                or "zakat fund" in zakat_lower
                or "zakat policy" in zakat_lower
                or "dedicated zakat page" in zakat_lower
                or "zakat calculator" in zakat_lower
            ):
                pts += 4
                layers.append("Explicit zakat program (+4)")
            else:
                pts += 2
                layers.append("Accepts zakat (+2)")

            # Log audit
            corroboration = metrics.corroboration_status.get("zakat_claim_detected", {})
            is_corroborated = corroboration.get("passed", False)
            self.audit_log.log_field_usage(
                ein=metrics.ein,
                field_name="zakat_claim_detected",
                value=True,
                sources=corroboration.get("sources", ["website_claims"]),
                corroborated=is_corroborated,
                impact=ScoreImpact.HIGH,
                scorer="AlignmentScorer",
                component="muslim_donor_fit",
                points=pts,
            )

        # Muslim-focused org (+2)
        if is_muslim:
            pts += 2
            layers.append("Muslim-focused organization (+2)")

        # Islamic identity (+1)
        name_lower = metrics.name.lower()
        mission_lower = (metrics.mission or "").lower()
        islamic_markers = ["islamic", "muslim", "zakat", "sadaqah", "waqf", "masjid", "mosque", "ummah"]
        if any(m in name_lower or m in mission_lower for m in islamic_markers):
            pts += 1
            layers.append("Islamic identity (+1)")

        # --- Universal layers (12 pts) ---

        # Asnaf alignment (+5)
        asnaf = self._detect_asnaf(metrics)
        if asnaf:
            pts += 5
            layers.append(f"Asnaf: {asnaf} (+5)")

        # Muslim-majority regions (+3)
        populations = " ".join(metrics.populations_served).lower()
        geo = " ".join(metrics.geographic_coverage).lower()
        muslim_regions = [
            # Broad Candid-style continent/region labels
            "africa",
            "asia",
            "middle east",
            # Sub-regions
            "north africa",
            "west africa",
            "east africa",
            "south asia",
            "southeast asia",
            "central asia",
            # Countries with large Muslim populations
            "syria",
            "yemen",
            "somalia",
            "afghanistan",
            "iraq",
            "palestine",
            "gaza",
            "sudan",
            "bangladesh",
            "pakistan",
            "niger",
            "mali",
            "chad",
            "libya",
            "lebanon",
            "jordan",
            "turkey",
            "indonesia",
            "myanmar",
            "rohingya",
            "sahel",
            "egypt",
            "iran",
            "morocco",
            "tunisia",
            "senegal",
            "nigeria",
        ]
        if "muslim" in populations or "ummah" in populations:
            pts += 3
            layers.append("Serves Muslim populations (+3)")
        elif any(r in geo for r in muslim_regions):
            pts += 3
            layers.append("Operates in Muslim-majority regions (+3)")

        # Humanitarian service (+4)
        # Work that directly helps vulnerable populations — relevant to Muslim
        # donors even without Islamic identity
        humanitarian_signals = [
            "humanitarian",
            "emergency",
            "medical",
            "health",
            "refugee",
            "displaced",
            "hunger",
            "malnutrition",
            "famine",
            "poverty",
            "clean water",
            "sanitation",
            "shelter",
            "disaster relief",
            "food security",
            "maternal",
            "child health",
            "epidemic",
        ]
        text = " ".join(
            [
                metrics.mission or "",
                " ".join(metrics.programs),
                " ".join(metrics.program_descriptions),
            ]
        ).lower()
        matched = [s for s in humanitarian_signals if s in text]
        if len(matched) >= 3:
            pts += 4
            layers.append("Strong humanitarian service (+4)")
        elif len(matched) >= 1:
            pts += 2
            layers.append("Humanitarian service (+2)")

        pts = min(19, pts)

        # Determine level (rescaled thresholds)
        if pts >= 12:
            level = "HIGH"
        elif pts >= 6:
            level = "MEDIUM"
        else:
            level = "LOW"

        evidence = "; ".join(layers) if layers else "No Muslim donor alignment signals"
        return pts, level, evidence

    def _detect_asnaf(self, metrics: CharityMetrics) -> Optional[str]:
        """Detect asnaf category from mission and programs."""
        text = " ".join(
            [
                metrics.mission or "",
                " ".join(metrics.programs),
                " ".join(metrics.program_descriptions),
                " ".join(metrics.populations_served),
            ]
        ).lower()

        asnaf_patterns = {
            "fuqara": ["fuqara", "poor", "impoverished", "poverty", "low-income", "hunger", "malnutrition", "famine"],
            "masakin": ["masakin", "needy", "destitute", "indigent", "humanitarian", "crisis", "disaster"],
            "ibn_sabil": ["ibn sabil", "wayfarer", "refugee", "displaced", "conflict", "asylum", "migrant"],
            "gharimin": ["gharimin", "debt relief", "indebted"],
            "fi_sabilillah": [
                "fi sabil",
                "cause of allah",
                "dawah",
                "islamic education",
                "scholarship",
                "fellowship",
                "muslim student",
                "muslim youth",
            ],
        }
        for category, patterns in asnaf_patterns.items():
            if any(p in text for p in patterns):
                return category
        return None

    def _score_funding_gap(self, metrics: CharityMetrics) -> tuple[int, str]:
        """Score funding gap from revenue tiers (5 pts).

        Compressed range: size no longer drives a big swing.
        Small and medium orgs get 5/5, large orgs get 3/5.
        """
        revenue = metrics.total_revenue
        if revenue is None:
            return FUNDING_GAP_UNKNOWN, "Revenue: unknown (moderate gap assumed)"

        for min_rev, max_rev, pts in FUNDING_GAP_THRESHOLDS:
            if min_rev <= revenue < max_rev:
                if revenue >= 1_000_000:
                    label = f"${revenue / 1_000_000:.1f}M"
                else:
                    label = f"${revenue:,.0f}"
                return pts, f"Revenue: {label} ({pts}/5 funding gap)"
        return 3, f"Revenue: ${revenue:,.0f}"

    def _score_underserved_space(self, metrics: CharityMetrics) -> tuple[int, str]:
        """Score underserved space — layered additive (7 pts max).

        +4: niche cause area (religious/cultural, advocacy, unknown)
        +3: serves underserved populations (refugees, conflict zones, etc.)
        Cap at 7.

        Size removed from this component — Track Record handles longevity,
        Funding Gap handles revenue. No double-counting.
        """
        pts = 0
        reasons = []

        # Niche cause (+4)
        cause = metrics.detected_cause_area or "UNKNOWN"
        niche_causes = {"RELIGIOUS_CULTURAL", "UNKNOWN", "ADVOCACY"}
        if cause in niche_causes:
            pts += 4
            reasons.append(f"Niche cause: {cause} (+4)")

        # Underserved populations (+3)
        if self._serves_underserved_populations(metrics):
            pts += 3
            reasons.append("Serves underserved populations (+3)")

        pts = min(7, pts)
        evidence = "; ".join(reasons) if reasons else "Well-covered space with mainstream reach"
        return pts, evidence

    def _serves_underserved_populations(self, metrics: CharityMetrics) -> bool:
        """Check if charity serves populations with limited alternative charities."""
        text = " ".join(
            [
                metrics.mission or "",
                " ".join(metrics.programs),
                " ".join(metrics.program_descriptions),
                " ".join(metrics.populations_served),
                " ".join(metrics.geographic_coverage),
            ]
        ).lower()

        underserved_signals = [
            "refugee",
            "displaced",
            "stateless",
            "asylum",
            "conflict zone",
            "war-affected",
            "post-conflict",
            "rural",
            "remote village",
            "hard-to-reach",
            "orphan",
            "widow",
            "disabled",
            "disability",
            "incarcerated",
            "formerly incarcerated",
            "reentry",
            "indigenous",
            "tribal",
            "marginalized",
            "rohingya",
            "uyghur",
            "internally displaced",
            "underrepresented",
            "representation",
            "minority",
        ]
        return any(signal in text for signal in underserved_signals)

    def _score_track_record(self, metrics: CharityMetrics) -> tuple[int, str]:
        """Score track record from founded year (6 pts, smooth interpolation).

        Uses TRACK_RECORD_KNOTS: [(0,1), (5,2), (10,4), (20,6), (50,6)]
        Pure factual signal — longevity correlates with sustainability.
        Not a size proxy (a 25-year-old $500K org scores the same as
        a 25-year-old $50M org).
        """
        import datetime

        current_year = datetime.date.today().year
        founded = metrics.founded_year

        if founded is None or founded <= 0:
            return 1, "Founded year unknown (1/6)"

        age = current_year - founded
        raw = interpolate_score(float(age), TRACK_RECORD_KNOTS)
        pts = round(raw)
        return pts, f"Founded {founded} ({age} years — {pts}/6)"


# =============================================================================
# ZakatScorer (Wallet Tag Only - NOT in score)
# =============================================================================


class ZakatScorer:
    """Determines zakat eligibility for wallet tag assignment.

    IMPORTANT: Zakat eligibility determines wallet tag ONLY.
    It does NOT contribute to the 100-point score.
    """

    ASNAF_PATTERNS = {
        "fuqara": ["fuqara", "poor", "impoverished", "poverty", "low-income"],
        "masakin": ["masakin", "needy", "destitute", "indigent"],
        "amil": ["amil", "zakat administrator", "zakat collector", "zakat worker"],
        "muallaf": ["muallaf", "new muslim", "convert", "revert", "reconciling hearts"],
        "riqab": ["riqab", "captive", "bondage", "enslaved", "incarcerated", "prisoner", "detained"],
        "gharimin": ["gharimin", "debt", "indebted", "debt relief", "debtor"],
        "ibn_sabil": ["ibn sabil", "wayfarer", "traveler", "refugee", "displaced", "stranded"],
        "fi_sabilillah": ["fi sabil", "cause of allah", "dawah", "islamic education", "in allah's cause"],
    }

    def evaluate(self, metrics: CharityMetrics) -> ZakatBonusAssessment:
        """Evaluate zakat eligibility from charity metrics."""
        charity_claims_zakat = metrics.zakat_claim_detected or False
        claim_evidence = metrics.zakat_claim_evidence

        asnaf_category = None
        if charity_claims_zakat:
            asnaf_category = self._determine_asnaf(metrics)

        return ZakatBonusAssessment(
            bonus_points=0,
            charity_claims_zakat=charity_claims_zakat,
            claim_evidence=claim_evidence,
            asnaf_category=asnaf_category,
        )

    def _determine_asnaf(self, metrics: CharityMetrics) -> Optional[str]:
        text = " ".join(
            [
                metrics.mission or "",
                " ".join(metrics.programs),
                " ".join(metrics.program_descriptions),
                " ".join(metrics.populations_served),
            ]
        ).lower()

        for category, patterns in self.ASNAF_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    return category
        return None


# =============================================================================
# RiskScorer (-10 pts max deduction)
# =============================================================================


class RiskScorer:
    """Evaluates risks for deduction (-10 points max).

    Size-adjusted: Emerging orgs (<$1M) get no deduction for missing
    TOC or outcomes (already penalized in Credibility). Established
    orgs (>$10M) get full deductions — no excuses at that scale.

    Risk deductions (capped at -10 total):
    - program_ratio_under_50: -5 (ProPublica 990)
    - board_under_3: -5 (ProPublica 990)
    - working_capital_under_1mo: -2 (ProPublica 990)
    - no_outcome_measurement: -2 Established, -1 Growing, 0 Emerging
    - no_toc: -1 Growing/Established, 0 Emerging
    - cn_advisory_flag: -3 (Charity Navigator)

    Conflict zone operations never penalized.
    """

    def evaluate(self, metrics: CharityMetrics) -> tuple[CaseAgainst, int]:
        """Evaluate risk assessment from charity metrics."""
        tier = determine_revenue_tier(metrics.total_revenue)
        risks = []
        risks.extend(self._check_financial_risks(metrics))
        risks.extend(self._check_operational_risks(metrics))
        risks.extend(self._check_impact_risks(metrics, tier))
        risks.extend(self._check_governance_risks(metrics))

        total_deduction = self._calculate_deduction(risks, metrics, tier)
        overall_risk_level = self._determine_risk_level(total_deduction)
        risk_summary = self._build_summary(risks)

        case_against = CaseAgainst(
            risks=risks,
            overall_risk_level=overall_risk_level,
            risk_summary=risk_summary,
            total_deduction=total_deduction,
        )
        return case_against, total_deduction

    def _check_financial_risks(self, metrics: CharityMetrics) -> list[RiskFactor]:
        risks = []
        ratio = metrics.program_expense_ratio
        if ratio is not None and ratio >= 0.01:
            if ratio < 0.50:
                risks.append(
                    RiskFactor(
                        category=RiskCategory.FINANCIAL,
                        description=f"Program expense ratio critically low: {ratio:.0%}",
                        severity=RiskSeverity.HIGH,
                        data_source="Form 990",
                    )
                )

        wc = metrics.working_capital_ratio
        if wc is not None and wc >= 0.1 and wc < 1:
            risks.append(
                RiskFactor(
                    category=RiskCategory.FINANCIAL,
                    description=f"Critically low working capital: {wc:.1f} months",
                    severity=RiskSeverity.MEDIUM,
                    data_source="Form 990",
                )
            )
        return risks

    def _check_operational_risks(self, metrics: CharityMetrics) -> list[RiskFactor]:
        risks = []
        if metrics.board_size is not None and metrics.board_size < 3:
            risks.append(
                RiskFactor(
                    category=RiskCategory.OPERATIONAL,
                    description=f"Board too small: {metrics.board_size} members",
                    severity=RiskSeverity.HIGH,
                    data_source="Candid profile",
                )
            )
        return risks

    def _check_impact_risks(self, metrics: CharityMetrics, tier: str = "GROWING") -> list[RiskFactor]:
        risks = []
        # Emerging orgs get a pass on missing outcomes/TOC
        if tier != "EMERGING":
            if not metrics.reports_outcomes and not metrics.candid_metrics_count:
                severity = RiskSeverity.MEDIUM if tier == "ESTABLISHED" else RiskSeverity.LOW
                risks.append(
                    RiskFactor(
                        category=RiskCategory.IMPACT,
                        description="No outcome measurement or metrics tracking",
                        severity=severity,
                        data_source="Website/Candid",
                    )
                )
            if not metrics.has_theory_of_change:
                risks.append(
                    RiskFactor(
                        category=RiskCategory.IMPACT,
                        description="No documented theory of change",
                        severity=RiskSeverity.LOW,
                        data_source="Website",
                    )
                )
        return risks

    def _check_governance_risks(self, metrics: CharityMetrics) -> list[RiskFactor]:
        """Check governance-specific risks (new in 3-dimension framework)."""
        risks = []

        # CN advisory or governance flag
        cn_beacons = [b.lower() for b in (metrics.cn_beacons or [])]
        if any("advisory" in b or "concern" in b for b in cn_beacons):
            risks.append(
                RiskFactor(
                    category=RiskCategory.OPERATIONAL,
                    description="Charity Navigator advisory or governance flag",
                    severity=RiskSeverity.MEDIUM,
                    data_source="Charity Navigator",
                )
            )

        return risks

    def _calculate_deduction(self, risks: list[RiskFactor], metrics: CharityMetrics, tier: str = "GROWING") -> int:  # noqa: ARG002
        """Calculate total risk deduction, tier-adjusted.

        Emerging orgs get no deduction for missing TOC/outcomes (already
        penalized via lower Credibility baseline). Established orgs get
        full deductions — with big power comes big responsibility.
        """
        total = 0

        ratio = metrics.program_expense_ratio
        if ratio is not None and ratio >= 0.01 and ratio < 0.50:
            total += RISK_DEDUCTIONS["program_ratio_under_50"]

        wc = metrics.working_capital_ratio
        if wc is not None and wc >= 0.1 and wc < 1:
            total += RISK_DEDUCTIONS["working_capital_under_1mo"]

        if metrics.board_size is not None and metrics.board_size < 3:
            total += RISK_DEDUCTIONS["board_under_3"]

        # Tier-adjusted: Emerging=0, Growing=-1, Established=-2
        if not metrics.reports_outcomes and not metrics.candid_metrics_count:
            if tier == "ESTABLISHED":
                total += RISK_DEDUCTIONS["no_outcome_measurement"]  # -2
            elif tier == "GROWING":
                total += -1

        # Tier-adjusted: Emerging=0, Growing/Established=-1
        if not metrics.has_theory_of_change:
            if tier != "EMERGING":
                total += RISK_DEDUCTIONS["no_toc"]  # -1

        # CN advisory flag
        cn_beacons = [b.lower() for b in (metrics.cn_beacons or [])]
        if any("advisory" in b or "concern" in b for b in cn_beacons):
            total += RISK_DEDUCTIONS["cn_advisory_flag"]

        return max(-10, total)

    def _determine_risk_level(self, deduction: int) -> str:
        if deduction <= -8:
            return "HIGH"
        elif deduction <= -5:
            return "ELEVATED"
        elif deduction <= -2:
            return "MODERATE"
        return "LOW"

    def _build_summary(self, risks: list[RiskFactor]) -> str:
        if not risks:
            return "No significant risks identified."
        high_risks = [r for r in risks if r.severity == RiskSeverity.HIGH]
        if high_risks:
            return f"Key concern: {high_risks[0].description}"
        return f"{len(risks)} risk(s) identified."


# =============================================================================
# Legacy Scorer Classes (backward compatibility)
# =============================================================================
# These are kept so that any code importing TrustScorer, EvidenceScorer, etc.
# still works. They delegate to the new 3-dimension scorers internally.


class TrustScorer:
    """Legacy wrapper — delegates to CredibilityScorer."""

    def __init__(self, audit_log: Optional[ScoringAuditLog] = None):
        self._credibility = CredibilityScorer(audit_log=audit_log)

    def evaluate(self, metrics: CharityMetrics) -> TrustAssessment:
        cred = self._credibility.evaluate(metrics)
        # Map credibility components to legacy TrustAssessment
        ver_pts = next((c.scored for c in cred.components if c.name == "Verification Tier"), 0)
        dq_pts = next((c.scored for c in cred.components if c.name == "Data Quality"), 0)
        trans_pts = next((c.scored for c in cred.components if c.name == "Transparency"), 0)
        # Legacy trust is 25 pts max — scale from 33
        legacy_score = min(25, round(cred.score * 25 / 33))
        return TrustAssessment(
            score=legacy_score,
            verification_tier=cred.verification_tier,
            verification_tier_points=ver_pts,
            data_quality="HIGH" if dq_pts >= 3 else "MODERATE" if dq_pts >= 2 else "LOW",
            data_quality_points=dq_pts,
            transparency=next(
                (
                    c.evidence.split(": ")[1] if ": " in c.evidence else "NONE"
                    for c in cred.components
                    if c.name == "Transparency"
                ),
                "NONE",
            ),
            transparency_points=trans_pts,
            rationale=cred.rationale,
            confidence_notes=cred.confidence_notes,
            corroboration_notes=cred.corroboration_notes,
            improvement_suggestions=[],
        )


class EvidenceScorer:
    """Legacy wrapper — delegates to CredibilityScorer."""

    def __init__(self, audit_log: Optional[ScoringAuditLog] = None):
        self._credibility = CredibilityScorer(audit_log=audit_log)

    def evaluate(self, metrics: CharityMetrics, evaluation_track: str = "STANDARD") -> EvidenceAssessment:  # noqa: ARG002
        cred = self._credibility.evaluate(metrics)
        toc_pts = next((c.scored for c in cred.components if c.name == "Theory of Change"), 0)
        eq_pts = next((c.scored for c in cred.components if c.name == "Evidence & Outcomes"), 0)
        legacy_score = min(25, round(cred.score * 25 / 33))
        return EvidenceAssessment(
            score=legacy_score,
            evidence_grade=EvidenceGrade.C,
            evidence_grade_points=eq_pts,
            evidence_grade_rationale=cred.rationale,
            outcome_measurement="MODERATE",
            outcome_measurement_points=6,
            theory_of_change=cred.theory_of_change_level,
            theory_of_change_points=toc_pts,
            rationale=cred.rationale,
            improvement_suggestions=[],
        )


class EffectivenessScorer:
    """Legacy wrapper — delegates to ImpactScorer."""

    def __init__(self):
        self._impact = ImpactScorer()

    def evaluate(self, metrics: CharityMetrics, cause_area: str = "DEFAULT") -> EffectivenessAssessment:
        impact = self._impact.evaluate(metrics, cause_area)
        legacy_score = min(25, round(impact.score * 25 / 50))
        pr_pts = next((c.scored for c in impact.components if c.name == "Program Ratio"), 0)
        cpb_pts = next((c.scored for c in impact.components if c.name == "Cost Per Beneficiary"), 0)
        return EffectivenessAssessment(
            score=legacy_score,
            cost_efficiency="AVERAGE",
            cost_efficiency_points=pr_pts,
            cost_per_beneficiary=impact.cost_per_beneficiary,
            scale_efficiency="AVERAGE",
            scale_efficiency_points=cpb_pts,
            room_for_funding="UNKNOWN",
            room_for_funding_points=0,
            rationale=impact.rationale,
            improvement_suggestions=[],
        )


class FitScorer:
    """Legacy wrapper — delegates to AlignmentScorer."""

    def __init__(self, audit_log: Optional[ScoringAuditLog] = None):
        self._alignment = AlignmentScorer(audit_log=audit_log)

    def evaluate(self, metrics: CharityMetrics) -> FitAssessment:
        align = self._alignment.evaluate(metrics)
        legacy_score = min(25, round(align.score * 25 / 50))
        mdf_pts = next((c.scored for c in align.components if c.name == "Muslim Donor Fit"), 0)
        cu_pts = next((c.scored for c in align.components if c.name == "Cause Urgency"), 0)
        return FitAssessment(
            score=legacy_score,
            counterfactual=align.muslim_donor_fit_level,
            counterfactual_points=mdf_pts,
            counterfactual_rationale=align.rationale,
            cause_importance=align.cause_urgency_label,
            cause_importance_points=cu_pts,
            cause_neglectedness="MAINSTREAM",
            cause_neglectedness_points=2,
            rationale=align.rationale,
            improvement_suggestions=[],
        )


# =============================================================================
# Main V2 Scorer (100 pts — 2 Dimensions + Risk + Data Confidence)
# =============================================================================


class AmalScorerV2:
    """Main scorer combining 2 dimensions + risk + data confidence signal.

    Produces AmalScoresV2 with:
    - Impact (50 pts): How much good per dollar, and can they prove it?
    - Alignment (50 pts): Right fit for Muslim donors?
    - Risk (-10 pts max): What could go wrong?
    - Data Confidence (0.0-1.0): How much data do we have? (outside score)

    Zakat eligibility determines wallet tag ONLY.
    Max score: 100
    """

    def __init__(self, audit_log: Optional[ScoringAuditLog] = None):
        self._audit_log = audit_log
        self.credibility_scorer = CredibilityScorer(audit_log=audit_log)
        self.impact_scorer = ImpactScorer()
        self.alignment_scorer = AlignmentScorer(audit_log=audit_log)
        self.zakat_scorer = ZakatScorer()
        self.risk_scorer = RiskScorer()

        # Legacy scorer references (for backward compatibility)
        self.trust_scorer = TrustScorer(audit_log=audit_log)
        self.evidence_scorer = EvidenceScorer(audit_log=audit_log)
        self.effectiveness_scorer = EffectivenessScorer()
        self.fit_scorer = FitScorer(audit_log=audit_log)

    @property
    def audit_log(self) -> ScoringAuditLog:
        if self._audit_log is None:
            self._audit_log = get_audit_log()
        return self._audit_log

    def evaluate(
        self, metrics: CharityMetrics, cause_area: str = "DEFAULT", evaluation_track: str = "STANDARD"
    ) -> AmalScoresV2:
        """Evaluate all dimensions and produce AmalScoresV2."""
        # Credibility is internal — feeds DataConfidence + Impact quality-practice
        credibility = self.credibility_scorer.evaluate(metrics)
        impact = self.impact_scorer.evaluate(metrics, cause_area)
        alignment = self.alignment_scorer.evaluate(metrics)
        zakat_bonus = self.zakat_scorer.evaluate(metrics)
        case_against, risk_deduction = self.risk_scorer.evaluate(metrics)

        # 2-dimension formula: impact + alignment + risk
        total_score = impact.score + alignment.score + risk_deduction
        total_score = max(0, min(100, total_score))

        # Data confidence signal (outside score)
        data_confidence = self._compute_data_confidence(credibility)

        wallet_tag = "ZAKAT-ELIGIBLE" if zakat_bonus.charity_claims_zakat else "SADAQAH-ELIGIBLE"

        score_summary = self._build_score_summary(
            metrics.name,
            total_score,
            impact,
            alignment,
            risk_deduction,
            wallet_tag,
            credibility.capacity_limited_evidence,
        )

        return AmalScoresV2(
            amal_score=total_score,
            credibility=credibility,
            impact=impact,
            alignment=alignment,
            data_confidence=data_confidence,
            zakat_bonus=zakat_bonus,
            case_against=case_against,
            risk_deduction=risk_deduction,
            wallet_tag=wallet_tag,
            score_summary=score_summary,
        )

    def _compute_data_confidence(self, credibility: CredibilityAssessment) -> DataConfidence:
        """Compute data confidence from credibility data-availability signals.

        Formula: confidence = ver*0.50 + trans*0.35 + dq*0.15
        Returns DataConfidence with overall float + component breakdown.
        """
        ver_value = VERIFICATION_CONFIDENCE.get(credibility.verification_tier, 0.0)
        trans_label = self._extract_transparency_label(credibility)
        trans_value = TRANSPARENCY_CONFIDENCE.get(trans_label, 0.0)
        dq_label = self._extract_data_quality_label(credibility)
        dq_value = DATA_QUALITY_CONFIDENCE.get(dq_label, 0.0)

        overall = (
            ver_value * DC_VERIFICATION_WEIGHT
            + trans_value * DC_TRANSPARENCY_WEIGHT
            + dq_value * DC_DATA_QUALITY_WEIGHT
        )
        overall = round(overall, 2)

        # Determine badge level
        if overall >= 0.7:
            badge = "HIGH"
        elif overall >= 0.4:
            badge = "MEDIUM"
        else:
            badge = "LOW"

        return DataConfidence(
            overall=overall,
            badge=badge,
            verification_tier=credibility.verification_tier,
            verification_value=ver_value,
            transparency_label=trans_label,
            transparency_value=trans_value,
            data_quality_label=dq_label,
            data_quality_value=dq_value,
        )

    def _extract_transparency_label(self, credibility: CredibilityAssessment) -> str:
        """Extract transparency label from credibility components."""
        for c in credibility.components:
            if c.name == "Transparency":
                # Evidence format: "Seal: GOLD" or similar
                if ": " in c.evidence:
                    return c.evidence.split(": ")[1].split(" ")[0].upper()
        return "NONE"

    def _extract_data_quality_label(self, credibility: CredibilityAssessment) -> str:
        """Extract data quality label from credibility components."""
        for c in credibility.components:
            if c.name == "Data Quality":
                if ": " in c.evidence:
                    return c.evidence.split(": ")[1].split(" ")[0].upper()
                pts = c.scored
                if pts >= 3:
                    return "HIGH"
                elif pts >= 2:
                    return "MODERATE"
                elif pts >= 1:
                    return "LOW"
        return "LOW"

    def _build_score_summary(
        self,
        name: str,
        total_score: int,
        impact: ImpactAssessment,
        alignment: AlignmentAssessment,
        risk_deduction: int,
        wallet_tag: str,
        capacity_limited: bool = False,
    ) -> str:
        """Build deterministic plain-English score summary."""
        dimensions = [
            (impact.score, 50, self._describe_dimension(impact.score, 50, "impact")),
            (alignment.score, 50, self._describe_dimension(alignment.score, 50, "alignment")),
        ]
        dimensions.sort(key=lambda x: x[0], reverse=True)
        top = dimensions[0][2]
        second = dimensions[1][2]

        zakat_note = ", with zakat compliance" if wallet_tag == "ZAKAT-ELIGIBLE" else ""
        caveat = ""
        if risk_deduction < -5:
            caveat = " (significant risk deductions applied)"
        elif risk_deduction < 0:
            caveat = " (minor risk deductions applied)"

        if capacity_limited:
            caveat += ". Evidence score may reflect limited reporting capacity, not program weakness"

        return f"{name} earns {total_score}/100 due to {top} and {second}{zakat_note}{caveat}."

    @staticmethod
    def _describe_dimension(score: int, max_pts: int, label: str) -> str:
        pct = score / max_pts
        if pct >= 0.85:
            return f"exceptional {label}"
        elif pct >= 0.70:
            return f"strong {label}"
        elif pct >= 0.55:
            return f"good {label}"
        elif pct >= 0.40:
            return f"moderate {label}"
        return f"limited {label}"

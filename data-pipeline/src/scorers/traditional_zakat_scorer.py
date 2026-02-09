"""Traditional Zakat Scorer - 100-Point Scoring Framework.

Evaluates charities through the lens of traditional Islamic giving (fiqh-first).
Designed for donors who prioritize Shariah compliance, direct relief, Islamic
organizational identity, and speed of impact delivery.

Dimensions (100 pts total):
1. Fiqh Compliance (up to 35 pts): wallet_tag + asnaf clarity (base + multi-asnaf bonus)
2. Directness (25 pts): program_expense_ratio + beneficiary proximity
3. Community Identity (25 pts): muslim_charity_fit + islamic identity signals
4. Speed of Delivery (20 pts): cause area mapping to delivery speed

All calculations are deterministic Python functions.
Inputs: CharityMetrics + AmalScoresV2
"""

from pydantic import BaseModel, Field
from src.llm.schemas.baseline import AmalScoresV2
from src.parsers.charity_metrics_aggregator import CharityMetrics

# =============================================================================
# Pydantic Assessment Models
# =============================================================================


class FiqhComplianceAssessment(BaseModel):
    """Fiqh Compliance dimension (30 pts max).

    Does this charity align with traditional zakat fiqh requirements?
    """

    score: int = Field(ge=0, le=35, description="Total fiqh compliance score (max 35)")
    wallet_tag_points: int = Field(ge=0, le=20, description="ZAKAT-ELIGIBLE=20, SADAQAH-ELIGIBLE=5")
    asnaf_clarity_points: int = Field(
        ge=0, le=15, description="Base 10 for 1+ asnaf categories, +2 per additional (max 5 bonus)"
    )
    wallet_tag: str = Field(description="The charity's wallet tag")
    asnaf_category: str | None = Field(default=None, description="Asnaf category if claimed")
    rationale: str = Field(description="1-2 sentence explanation")


class DirectnessAssessment(BaseModel):
    """Directness dimension (25 pts max).

    How directly do funds reach beneficiaries?
    """

    score: int = Field(ge=0, le=25, description="Total directness score (max 25)")
    program_ratio_points: int = Field(ge=0, le=15, description="Based on program_expense_ratio")
    beneficiary_proximity_points: int = Field(ge=0, le=10, description="Based on cause area proximity")
    program_expense_ratio: float | None = Field(default=None, description="The actual ratio")
    rationale: str = Field(description="1-2 sentence explanation")


class CommunityIdentityAssessment(BaseModel):
    """Community Identity dimension (25 pts max).

    Does the charity have strong Islamic identity and Muslim community connection?
    """

    score: int = Field(ge=0, le=25, description="Total community identity score (max 25)")
    muslim_fit_points: int = Field(ge=0, le=20, description="high=20, medium=12, low=5")
    islamic_identity_bonus: int = Field(ge=0, le=5, description="Bonus for explicit Islamic identity signals")
    muslim_charity_fit: str | None = Field(default=None, description="high/medium/low")
    rationale: str = Field(description="1-2 sentence explanation")


class SpeedOfDeliveryAssessment(BaseModel):
    """Speed of Delivery dimension (20 pts max).

    How quickly does the charity deliver impact to beneficiaries?
    Includes a necessity-urgency bonus for conflict zones (where need is
    acute even though logistics may be slower).
    """

    score: int = Field(ge=0, le=20, description="Total speed score (max 20)")
    cause_speed_points: int = Field(ge=0, le=18, description="Based on cause area speed mapping")
    urgency_bonus: int = Field(
        ge=0, le=2, description="Bonus for acute need in conflict zones (urgency, not delivery speed)"
    )
    cause_area: str | None = Field(default=None, description="Detected cause area")
    rationale: str = Field(description="1-2 sentence explanation")


class TraditionalZakatScores(BaseModel):
    """Complete Traditional Zakat evaluation (100-point scale)."""

    zakat_score: int = Field(ge=0, le=100, description="Total Traditional Zakat score")

    fiqh_compliance: FiqhComplianceAssessment = Field(description="Fiqh Compliance dimension (max 30)")
    directness: DirectnessAssessment = Field(description="Directness dimension (max 25)")
    community_identity: CommunityIdentityAssessment = Field(description="Community Identity dimension (max 25)")
    speed_of_delivery: SpeedOfDeliveryAssessment = Field(description="Speed of Delivery dimension (max 20)")


# =============================================================================
# Constants
# =============================================================================

# Wallet tag → Fiqh Compliance points
WALLET_TAG_POINTS = {
    "ZAKAT-ELIGIBLE": 20,
    "SADAQAH-ELIGIBLE": 5,
}

# Program expense ratio → Directness points (higher ratio = more direct)
PROGRAM_RATIO_THRESHOLDS = [
    (0.90, 15),  # ≥90% → maximum directness
    (0.80, 12),  # 80-89%
    (0.70, 9),  # 70-79%
    (0.60, 6),  # 60-69%
    (0.0, 3),  # <60%
]

# Cause area → beneficiary proximity points
# Higher for causes where funds directly reach individuals
BENEFICIARY_PROXIMITY = {
    "HUMANITARIAN": 10,
    "EXTREME_POVERTY": 10,
    "FOOD_HUNGER": 10,
    "DOMESTIC_POVERTY": 8,
    "GLOBAL_HEALTH": 7,
    "EDUCATION_GLOBAL": 5,
    "ORPHAN_CARE": 9,
    "REFUGEE": 9,
    "WATER": 7,
    "RELIGIOUS_CULTURAL": 4,
    "ADVOCACY": 2,
    "RESEARCH": 1,
}

# Muslim charity fit → Community Identity points
MUSLIM_FIT_POINTS = {
    "high": 20,
    "medium": 12,
    "low": 5,
}

# Cause area → Speed of delivery points
# Higher for causes with faster delivery to beneficiaries
CAUSE_SPEED_POINTS = {
    "HUMANITARIAN": 18,
    "FOOD_HUNGER": 17,
    "EXTREME_POVERTY": 15,
    "DOMESTIC_POVERTY": 14,
    "ORPHAN_CARE": 14,
    "REFUGEE": 13,
    "GLOBAL_HEALTH": 12,
    "WATER": 10,
    "EDUCATION_GLOBAL": 10,
    "RELIGIOUS_CULTURAL": 8,
    "ADVOCACY": 4,
    "RESEARCH": 4,
}


# =============================================================================
# Scorer
# =============================================================================


class TraditionalZakatScorer:
    """Deterministic scorer for the Traditional Zakat lens.

    Prioritizes fiqh compliance, direct relief, Islamic identity,
    and speed of impact delivery.
    """

    def evaluate(
        self,
        metrics: CharityMetrics,
        amal_scores: AmalScoresV2,
    ) -> TraditionalZakatScores:
        """Evaluate charity through the Traditional Zakat lens.

        Args:
            metrics: Aggregated charity metrics
            amal_scores: Existing AMAL V2 scores (reuses wallet_tag, zakat info)

        Returns:
            TraditionalZakatScores with all dimension breakdowns
        """
        fiqh = self._evaluate_fiqh_compliance(amal_scores, metrics)
        directness = self._evaluate_directness(metrics)
        identity = self._evaluate_community_identity(metrics)
        speed = self._evaluate_speed_of_delivery(metrics)

        total = min(100, fiqh.score + directness.score + identity.score + speed.score)

        return TraditionalZakatScores(
            zakat_score=total,
            fiqh_compliance=fiqh,
            directness=directness,
            community_identity=identity,
            speed_of_delivery=speed,
        )

    def _evaluate_fiqh_compliance(
        self, amal_scores: AmalScoresV2, metrics: CharityMetrics | None = None
    ) -> FiqhComplianceAssessment:
        """Evaluate fiqh compliance from wallet tag and asnaf clarity."""
        wallet_tag = amal_scores.wallet_tag
        wallet_pts = WALLET_TAG_POINTS.get(wallet_tag, 5)

        # Asnaf clarity: does the charity specify which asnaf category?
        # Prefer explicit asnaf categories from zakat_metadata when available
        asnaf = amal_scores.zakat_bonus.asnaf_category if amal_scores.zakat_bonus else None
        asnaf_categories = metrics.zakat_categories_served if metrics else None

        if asnaf_categories and len(asnaf_categories) > 0:
            # Base 10 for specifying any category, +2 per additional (max 5 bonus)
            additional = max(0, len(asnaf_categories) - 1)
            asnaf_pts = 10 + min(5, additional * 2)
            asnaf = ", ".join(asnaf_categories)
        elif asnaf and asnaf.lower() not in ("none", "n/a", "unknown", ""):
            asnaf_pts = 10
        elif amal_scores.zakat_bonus and amal_scores.zakat_bonus.charity_claims_zakat:
            asnaf_pts = 5  # Claims zakat but no specific asnaf
        else:
            asnaf_pts = 0

        total = min(35, wallet_pts + asnaf_pts)

        rationale_parts = [f"Wallet tag: {wallet_tag} ({wallet_pts}/20)"]
        if asnaf:
            rationale_parts.append(f"Asnaf: {asnaf} ({asnaf_pts}/15)")
        else:
            rationale_parts.append(f"No specific asnaf category ({asnaf_pts}/15)")

        return FiqhComplianceAssessment(
            score=total,
            wallet_tag_points=wallet_pts,
            asnaf_clarity_points=asnaf_pts,
            wallet_tag=wallet_tag,
            asnaf_category=asnaf,
            rationale=". ".join(rationale_parts),
        )

    def _evaluate_directness(self, metrics: CharityMetrics) -> DirectnessAssessment:
        """Evaluate how directly funds reach beneficiaries."""
        # Program expense ratio → directness points
        ratio = metrics.program_expense_ratio
        ratio_pts = 3  # default for unknown
        if ratio is not None:
            for threshold, points in PROGRAM_RATIO_THRESHOLDS:
                if ratio >= threshold:
                    ratio_pts = points
                    break

        # Beneficiary proximity from cause area
        cause = (metrics.detected_cause_area or "").upper()
        proximity_pts = BENEFICIARY_PROXIMITY.get(cause, 5)  # default 5 for unknown causes

        total = min(25, ratio_pts + proximity_pts)

        ratio_str = f"{ratio:.0%}" if ratio else "unknown"
        return DirectnessAssessment(
            score=total,
            program_ratio_points=ratio_pts,
            beneficiary_proximity_points=proximity_pts,
            program_expense_ratio=ratio,
            rationale=f"Program expense ratio {ratio_str} ({ratio_pts}/15). Cause area {cause or 'unknown'} proximity ({proximity_pts}/10).",
        )

    def _evaluate_community_identity(self, metrics: CharityMetrics) -> CommunityIdentityAssessment:
        """Evaluate Islamic identity and Muslim community connection."""
        fit = "low"  # default
        if hasattr(metrics, "is_muslim_focused"):
            fit = "high" if metrics.is_muslim_focused else "low"

        fit_pts = MUSLIM_FIT_POINTS.get(fit, 5)

        # Islamic identity bonus: use rich signals when available, fall back to basic checks
        identity_bonus = 0
        if metrics.islamic_identity_signals:
            # Count distinct signal categories for richer scoring
            signal_count = len(metrics.islamic_identity_signals)
            identity_bonus = min(5, signal_count)
        else:
            # Fallback: basic checks (existing logic)
            if metrics.zakat_claim_detected:
                identity_bonus += 3
            name_lower = (metrics.name or "").lower()
            islamic_terms = {"islamic", "muslim", "masjid", "mosque", "quran", "zakat", "sadaqah"}
            if any(term in name_lower for term in islamic_terms):
                identity_bonus += 2
            identity_bonus = min(5, identity_bonus)

        total = min(25, fit_pts + identity_bonus)

        return CommunityIdentityAssessment(
            score=total,
            muslim_fit_points=fit_pts,
            islamic_identity_bonus=identity_bonus,
            muslim_charity_fit=fit,
            rationale=f"Muslim charity fit: {fit} ({fit_pts}/20). Islamic identity signals: +{identity_bonus}/5.",
        )

    def _evaluate_speed_of_delivery(self, metrics: CharityMetrics) -> SpeedOfDeliveryAssessment:
        """Evaluate speed of impact delivery based on cause area.

        The urgency bonus rewards conflict-zone charities for addressing acute
        need — not for faster logistics (which may actually be slower due to
        blockades, checkpoints, and access restrictions).
        """
        cause = (metrics.detected_cause_area or "").upper()
        speed_pts = CAUSE_SPEED_POINTS.get(cause, 8)  # default 8 for unknown

        # Urgency bonus: conflict zones have acute need even if delivery is slower
        urgency_bonus = 0
        if metrics.conflict_zones and len(metrics.conflict_zones) > 0:
            urgency_bonus = 2

        total = min(20, speed_pts + urgency_bonus)

        return SpeedOfDeliveryAssessment(
            score=total,
            cause_speed_points=speed_pts,
            urgency_bonus=urgency_bonus,
            cause_area=metrics.detected_cause_area,
            rationale=f"Cause area {cause or 'unknown'} speed ({speed_pts}/18). Conflict zone urgency: {'yes' if urgency_bonus else 'no'} (+{urgency_bonus}/2).",
        )

"""Strategic Believer Scorer - 100-Point Scoring Framework.

Evaluates charities through the lens of systemic change, leverage, and future-proofing.
Designed for donors who prioritize long-term structural impact over immediate relief.

Dimensions (100 pts total):
1. Resilience (30 pts): Does this charity break cycles of poverty/dependency?
2. Leverage (25 pts): Does each $1 create >$1 in downstream value?
3. Future-Proofing (25 pts): Does the charity build durable assets and sovereignty?
4. Competence (20 pts): Can the org actually execute? (reuses AMAL Trust + Evidence)

All calculations are deterministic Python functions.
Inputs: CharityMetrics + AmalScoresV2 + StrategicClassification
"""

from pydantic import BaseModel, Field
from src.llm.schemas.baseline import AmalScoresV2
from src.parsers.charity_metrics_aggregator import CharityMetrics
from src.scorers.strategic_classifier import StrategicClassification

# =============================================================================
# Pydantic Assessment Models
# =============================================================================


class ResilienceAssessment(BaseModel):
    """Resilience dimension (30 pts max).

    Does this charity break cycles of poverty, dependency, or marginalization?
    """

    score: int = Field(ge=0, le=30, description="Total resilience score (max 30)")
    loop_breaking_raw: int = Field(ge=0, le=10, description="Raw loop_breaking from classifier (0-10)")
    loop_breaking_points: int = Field(ge=0, le=30, description="loop_breaking × 3.0")
    rationale: str = Field(description="1-2 sentence explanation")


class LeverageAssessment(BaseModel):
    """Leverage dimension (25 pts max).

    Does each $1 create >$1 in downstream value?
    """

    score: int = Field(ge=0, le=25, description="Total leverage score (max 25)")
    multiplier_raw: int = Field(ge=0, le=10, description="Raw multiplier from classifier (0-10)")
    multiplier_points: int = Field(ge=0, le=25, description="multiplier × 2.5")
    rationale: str = Field(description="1-2 sentence explanation")


class FutureProofingAssessment(BaseModel):
    """Future-Proofing dimension (25 pts max).

    Does the charity build durable assets and community self-determination?
    """

    score: int = Field(ge=0, le=25, description="Total future-proofing score (max 25)")
    asset_creation_raw: int = Field(ge=0, le=10, description="Raw asset_creation from classifier (0-10)")
    asset_creation_points: int = Field(ge=0, le=15, description="asset_creation × 1.5")
    sovereignty_raw: int = Field(ge=0, le=10, description="Raw sovereignty from classifier (0-10)")
    sovereignty_points: int = Field(ge=0, le=10, description="sovereignty × 1.0")
    rationale: str = Field(description="1-2 sentence explanation")


class CompetenceAssessment(BaseModel):
    """Competence dimension (20 pts max).

    Can the organization actually execute? Reuses AMAL Trust + Evidence,
    but reweights evidence toward Theory of Change and Outcome Measurement
    rather than the raw Evidence Grade. This avoids rewarding simple output
    tracking (Grade D) in a lens that demands resilience and leverage.

    Breakdown (12 evidence pts):
      - Theory of Change: 0-5 pts (strategic thinkers articulate *how* change happens)
      - Outcome Measurement: 0-4 pts (rigor of tracking, not just grade letter)
      - Evidence Grade: 0-3 pts (tiebreaker, not driver)
    """

    score: int = Field(ge=0, le=20, description="Total competence score (max 20)")
    trust_contribution: int = Field(ge=0, le=8, description="From AMAL trust verification_tier (0-8)")
    toc_contribution: int = Field(ge=0, le=5, description="From AMAL theory of change (0-5)")
    outcome_contribution: int = Field(ge=0, le=4, description="From AMAL outcome measurement (0-4)")
    evidence_grade_contribution: int = Field(ge=0, le=3, description="From AMAL evidence grade (0-3)")
    rationale: str = Field(description="1-2 sentence explanation")


class StrategicBelieverScores(BaseModel):
    """Complete Strategic Believer evaluation (100-point scale)."""

    strategic_score: int = Field(ge=0, le=100, description="Total Strategic Believer score")
    archetype: str = Field(description="Strategic archetype from classifier")
    archetype_label: str = Field(default="", description="Human-readable archetype label")
    archetype_description: str = Field(default="", description="1-2 sentence archetype explanation")

    resilience: ResilienceAssessment = Field(description="Resilience dimension (max 30)")
    leverage: LeverageAssessment = Field(description="Leverage dimension (max 25)")
    future_proofing: FutureProofingAssessment = Field(description="Future-Proofing dimension (max 25)")
    competence: CompetenceAssessment = Field(description="Competence dimension (max 20)")


# =============================================================================
# Archetype metadata — human-readable labels and descriptions
# =============================================================================

ARCHETYPE_METADATA: dict[str, dict[str, str]] = {
    "SOVEREIGNTY": {
        "label": "Institution Builder",
        "description": "Creates things communities own and run themselves — like local schools, clinics, or cooperatives — so they don't need outside help forever.",
    },
    "RESILIENCE": {
        "label": "Cycle Breaker",
        "description": "Works to fix the reasons people stay poor, not just the symptoms. For example, providing job training instead of only food aid, so families can support themselves long-term.",
    },
    "LEVERAGE": {
        "label": "Force Multiplier",
        "description": "Makes every dollar go further. For example, training local teachers who then train others, or unlocking matching funds — so your donation creates a ripple effect.",
    },
    "ASSET_CREATION": {
        "label": "Asset Creator",
        "description": "Builds things that last — schools, wells, housing, training programs — that keep helping people long after the initial donation is spent.",
    },
    "DIRECT_SERVICE": {
        "label": "Direct Responder",
        "description": "Provides immediate help to people in need, like food, shelter, or medical care. Essential work, though this lens focuses more on long-term solutions.",
    },
    "UNKNOWN": {
        "label": "Unclassified",
        "description": "We don't have enough information yet to classify this charity's strategic approach.",
    },
}


# =============================================================================
# Human-readable dimension interpretation helpers
# =============================================================================


def _resilience_interpretation(raw: int, archetype_rationale: str) -> str:
    """Convert raw loop_breaking score to human-readable rationale."""
    if raw >= 8:
        return f"Tackles the deep reasons people stay in poverty — not just the symptoms — creating changes that last across generations. {archetype_rationale}"
    if raw >= 6:
        return f"Works to fix the underlying problems that keep people poor or excluded, with programs designed to help people become self-sufficient. {archetype_rationale}"
    if raw >= 4:
        return f"Has some programs that address deeper problems, though much of its work still depends on ongoing donations to keep running. {archetype_rationale}"
    if raw >= 2:
        return f"Mostly helps with immediate needs rather than fixing the deeper problems behind them. {archetype_rationale}"
    return f"Focused on providing immediate help, without programs specifically designed to address long-term causes. {archetype_rationale}"


def _leverage_interpretation(raw: int) -> str:
    """Convert raw multiplier score to human-readable rationale."""
    if raw >= 8:
        return "Your dollar goes much further here — for example, by training people who go on to train others, or by unlocking matching funds that double or triple the original gift."
    if raw >= 6:
        return "Each dollar does more than face value — the charity uses approaches like training local leaders or partnering with other organizations to stretch donations further."
    if raw >= 4:
        return "Some ability to stretch donations through partnerships or smart program design, but impact is mostly proportional to the amount given."
    if raw >= 2:
        return "Most of your donation goes directly to providing services — effective, but each dollar mostly funds one unit of help."
    return "Each dollar funds a specific service or item. There is little built-in way for donations to create additional impact beyond the direct service."


def _future_proofing_interpretation(asset_raw: int, sov_raw: int) -> str:
    """Convert raw asset_creation and sovereignty scores to human-readable rationale."""
    asset_level = "strong" if asset_raw >= 7 else "moderate" if asset_raw >= 4 else "limited"
    sov_level = "strong" if sov_raw >= 7 else "moderate" if sov_raw >= 4 else "limited"

    if asset_level == "strong" and sov_level == "strong":
        return "Builds lasting things — like schools, wells, or local organizations — that communities own and run themselves, so the impact continues even without future donations."
    if asset_level == "strong":
        return "Creates things that last — buildings, equipment, training programs, or savings funds — though the community could have a bigger role in running them."
    if sov_level == "strong":
        return "Helps communities take charge and run programs on their own, even though it may not build much physical infrastructure."
    if asset_level == "moderate" or sov_level == "moderate":
        return "Some investment in things that last or in helping communities become independent, though the work still depends a lot on continued donations."
    return "Most of the impact stops when funding stops — there is little investment in lasting infrastructure or helping communities become self-sufficient."


def _competence_interpretation(trust_tier: str, toc_status: str, outcome_level: str) -> str:
    """Convert AMAL trust/evidence sub-components into a competence rationale.

    Emphasizes theory of change and outcome measurement quality rather than
    the raw evidence grade, matching the Strategic Believer philosophy.
    """
    trust_desc = {
        "HIGH": "independently verified finances and openly shares how it operates",
        "MODERATE": "reasonable openness about its operations with some outside review",
        "BASIC": "limited outside review of how it operates",
        "NONE": "very little public information about its accountability",
    }.get(trust_tier, "unknown accountability status")

    toc_desc = {
        "PUBLISHED": "a published theory of change explaining how its work creates lasting impact",
        "DOCUMENTED": "a documented strategic plan linking programs to outcomes",
        "IMPLICIT": "an implicit logic connecting programs to results, though not formally documented",
        "NONE": "no documented theory of how its programs create systemic change",
    }.get(toc_status, "unknown strategic planning")

    outcome_desc = {
        "COMPREHENSIVE": "rigorous outcome tracking over multiple years",
        "STRONG": "solid outcome measurement with documented methods",
        "MODERATE": "some outcome tracking in place",
        "BASIC": "tracks outputs but not deeper outcomes",
        "WEAK": "limited tracking of whether programs actually work",
    }.get(outcome_level, "unknown outcome tracking")

    return f"This charity has {trust_desc}, {toc_desc}, and {outcome_desc}."


# =============================================================================
# Trust verification tier → Competence points mapping
# =============================================================================

TRUST_TIER_TO_COMPETENCE = {
    "HIGH": 8,
    "MODERATE": 6,
    "BASIC": 3,
    "NONE": 0,
}

# Theory of Change → Competence points (0-5)
# Strategic thinkers articulate *how* change happens — this is the primary
# evidence signal for competence in a lens about systemic change.
TOC_TO_COMPETENCE = {
    "PUBLISHED": 5,
    "DOCUMENTED": 4,
    "IMPLICIT": 2,
    "NONE": 0,
}

# Outcome Measurement → Competence points (0-4)
# Rewards rigor of tracking systems, not just the evidence letter grade.
OUTCOME_TO_COMPETENCE = {
    "COMPREHENSIVE": 4,
    "STRONG": 3,
    "MODERATE": 2,
    "BASIC": 1,
    "WEAK": 0,
}

# Evidence Grade → Competence points (0-3)
# Kept as a tiebreaker — differentiates between orgs with similar ToC/Outcome,
# but no longer dominates. A Grade D (output tracking) gets only 1 pt here.
EVIDENCE_GRADE_TO_COMPETENCE = {
    "A": 3,
    "B": 3,
    "C": 2,
    "D": 1,
    "E": 0,
    "F": 0,
    "G": 0,
    "H": 0,
}


# =============================================================================
# Scorer
# =============================================================================


class StrategicBelieverScorer:
    """Deterministic scorer for the Strategic Believer lens.

    Takes LLM-classified strategic scores and AMAL assessments,
    applies fixed multipliers to produce a 100-point score.
    """

    def evaluate(
        self,
        metrics: CharityMetrics,  # noqa: ARG002 - kept for consistent scorer API
        amal_scores: AmalScoresV2,
        classification: StrategicClassification | None,
    ) -> StrategicBelieverScores:
        """Evaluate charity through the Strategic Believer lens.

        Args:
            metrics: Aggregated charity metrics
            amal_scores: Existing AMAL V2 scores (for Competence reuse)
            classification: Strategic classification from LLM (may be None)

        Returns:
            StrategicBelieverScores with all dimension breakdowns
        """
        # If no classification, score conservatively
        if classification is None:
            return self._score_without_classification(amal_scores)

        # Archetype metadata
        meta = ARCHETYPE_METADATA.get(classification.archetype, ARCHETYPE_METADATA["UNKNOWN"])

        # 1. Resilience (30 pts) = loop_breaking × 3.0
        loop_raw = max(0, min(10, classification.loop_breaking or 0))
        loop_pts = min(30, round(loop_raw * 3.0))
        resilience = ResilienceAssessment(
            score=loop_pts,
            loop_breaking_raw=loop_raw,
            loop_breaking_points=loop_pts,
            rationale=_resilience_interpretation(loop_raw, classification.archetype_rationale),
        )

        # 2. Leverage (25 pts) = multiplier × 2.5
        mult_raw = max(0, min(10, classification.multiplier or 0))
        mult_pts = min(25, round(mult_raw * 2.5))
        leverage = LeverageAssessment(
            score=mult_pts,
            multiplier_raw=mult_raw,
            multiplier_points=mult_pts,
            rationale=_leverage_interpretation(mult_raw),
        )

        # 3. Future-Proofing (25 pts) = asset_creation × 1.5 + sovereignty × 1.0
        asset_raw = max(0, min(10, classification.asset_creation or 0))
        asset_pts = min(15, round(asset_raw * 1.5))
        sov_raw = max(0, min(10, classification.sovereignty or 0))
        sov_pts = min(10, sov_raw)
        fp_total = min(25, asset_pts + sov_pts)
        future_proofing = FutureProofingAssessment(
            score=fp_total,
            asset_creation_raw=asset_raw,
            asset_creation_points=asset_pts,
            sovereignty_raw=sov_raw,
            sovereignty_points=sov_pts,
            rationale=_future_proofing_interpretation(asset_raw, sov_raw),
        )

        # 4. Competence (20 pts) = Trust tier (0-8) + Evidence grade (0-12)
        competence = self._evaluate_competence(amal_scores)

        # Total
        total = min(100, resilience.score + leverage.score + future_proofing.score + competence.score)

        return StrategicBelieverScores(
            strategic_score=total,
            archetype=classification.archetype,
            archetype_label=meta["label"],
            archetype_description=meta["description"],
            resilience=resilience,
            leverage=leverage,
            future_proofing=future_proofing,
            competence=competence,
        )

    def _evaluate_competence(self, amal_scores: AmalScoresV2) -> CompetenceAssessment:
        """Evaluate competence by reusing AMAL Trust + Evidence sub-components.

        Reweights evidence toward Theory of Change (5 pts) and Outcome
        Measurement (4 pts) instead of the raw Evidence Grade (3 pts).
        This prevents a relief charity with perfect output tracking from
        getting full competence credit in a lens about systemic change.
        """
        # Trust tier (0-8) — unchanged
        trust_tier = amal_scores.trust.verification_tier
        trust_pts = TRUST_TIER_TO_COMPETENCE.get(trust_tier, 0)

        # Theory of Change (0-5) — primary evidence signal for strategic competence
        toc_status = amal_scores.evidence.theory_of_change or "NONE"
        toc_pts = TOC_TO_COMPETENCE.get(toc_status, 0)

        # Outcome Measurement (0-4) — rewards rigor, not just the letter grade
        outcome_level = amal_scores.evidence.outcome_measurement or "WEAK"
        outcome_pts = OUTCOME_TO_COMPETENCE.get(outcome_level, 0)

        # Evidence Grade (0-3) — tiebreaker only
        evidence_grade = amal_scores.evidence.evidence_grade.value if amal_scores.evidence.evidence_grade else "H"
        grade_pts = EVIDENCE_GRADE_TO_COMPETENCE.get(evidence_grade, 0)

        total = min(20, trust_pts + toc_pts + outcome_pts + grade_pts)

        return CompetenceAssessment(
            score=total,
            trust_contribution=trust_pts,
            toc_contribution=toc_pts,
            outcome_contribution=outcome_pts,
            evidence_grade_contribution=grade_pts,
            rationale=_competence_interpretation(trust_tier, toc_status, outcome_level),
        )

    def _score_without_classification(self, amal_scores: AmalScoresV2) -> StrategicBelieverScores:
        """Fallback scoring when no strategic classification is available."""
        competence = self._evaluate_competence(amal_scores)

        meta = ARCHETYPE_METADATA["UNKNOWN"]
        return StrategicBelieverScores(
            strategic_score=competence.score,
            archetype="UNKNOWN",
            archetype_label=meta["label"],
            archetype_description=meta["description"],
            resilience=ResilienceAssessment(
                score=0,
                loop_breaking_raw=0,
                loop_breaking_points=0,
                rationale="No strategic classification available.",
            ),
            leverage=LeverageAssessment(
                score=0,
                multiplier_raw=0,
                multiplier_points=0,
                rationale="No strategic classification available.",
            ),
            future_proofing=FutureProofingAssessment(
                score=0,
                asset_creation_raw=0,
                asset_creation_points=0,
                sovereignty_raw=0,
                sovereignty_points=0,
                rationale="No strategic classification available.",
            ),
            competence=competence,
        )

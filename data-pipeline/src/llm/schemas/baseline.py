"""Pydantic schema for Baseline Narrative.

Baseline narratives are concise (~150-200 words) summaries generated for all
charities. They provide essential information for quick donor decisions:
- Headline and summary
- At-a-glance facts (founded, revenue, employees, reach)
- Programs and beneficiaries served
- 2-3 key strengths with evidence citations
- 1-2 improvement areas
- Impact metrics with AMAL score rationale
- Zakat guidance and confidence score
- Website and donation URLs

GMG Score (100-Point Framework) — 2 Dimensions + Risk + Data Confidence:

- Impact (50 pts): CPB(20) + Directness(7) + Financial Health(7) + Program Ratio(6) + Evidence & Outcomes(5) + TOC(3) + Governance(2)
- Alignment (50 pts): Muslim Donor Fit(19) + Cause Urgency(13) + Underserved Space(7) + Track Record(6) + Funding Gap(5)
- Risk (-10 max): Case Against risk deductions
- Data Confidence (0.0-1.0): Verification + Transparency + Data Quality (outside score)

IMPORTANT: Zakat eligibility determines wallet tag ONLY, not score.

Max score: 100 points

Expected scores:
- GiveWell Top Charity: 85-100
- Strong poverty relief: 70-85
- Average nonprofit: 50-65
- Well-run Islamic school/mosque: 40-60

Legacy structures are preserved below for migration purposes.
"""

from typing import Optional

from pydantic import BaseModel, Field

from .common import (
    AtAGlance,
    CaseAgainst,
    Confidence,
    CostEffectivenessBenchmark,
    EvidenceGrade,
    EvidenceQualityGrade,
    ImprovementArea,
    ScoreComponent,
    Strength,
    ThirdPartyVerification,
    ZakatGuidance,
)


# Sub-score models
class SubScore(BaseModel):
    """A sub-component score with rationale and evidence."""

    score: int = Field(description="Score for this sub-component")
    rationale: str = Field(description="1-3 sentence explanation of WHY this score was assigned")
    evidence: list[str] = Field(
        default_factory=list,
        description="Short evidence references (e.g., 'Form 990 2023', 'Candid profile')",
    )


class DimensionConfidence(BaseModel):
    """Per-dimension confidence assessment."""

    score: int = Field(ge=0, le=100, description="Confidence score 0-100 for this dimension")
    rationale: str = Field(description="Brief explanation of data quality for this dimension")


# =============================================================================
# NEW 5-Assessment Structure (GWWC + Longview Anchored)
# =============================================================================


class TrustAssessment(BaseModel):
    """Trust Assessment (25 points max).

    Question: Can we believe what they claim?

    Components:
    - verification_tier (10 pts): HIGH (any 2 of CN>=90/Candid Gold+/BBB) = 10, MODERATE = 6, BASIC = 3, NONE = 0
    - data_quality (8 pts): HIGH (4+ sources) = 8, MODERATE (2-3) = 5, LOW (1) = 2, CONFLICTING = 0
    - transparency (7 pts): PLATINUM = 7, GOLD = 5, SILVER = 4, BRONZE = 2, NONE = 0

    B1 Corroboration: When website claims match third-party data, adds to corroboration_notes.
    B4 Transparency: Website disclosure richness can boost transparency tier (see TrustScorer).
    """

    score: int = Field(ge=0, le=25, description="Total Trust score (max 25)")
    verification_tier: str = Field(
        description="Third-party verification tier: HIGH (any 2 of CN>=90/Candid Gold+/BBB), MODERATE (any 1), BASIC, NONE"
    )
    verification_tier_points: int = Field(ge=0, le=10, description="Points for verification tier (0-10)")
    data_quality: str = Field(
        description="Data source quality: HIGH (4+ sources), MODERATE (2-3), LOW (1), CONFLICTING"
    )
    data_quality_points: int = Field(ge=0, le=8, description="Points for data quality (0-8)")
    transparency: str = Field(
        description="Transparency level based on Candid seal: PLATINUM, GOLD, SILVER, BRONZE, NONE"
    )
    transparency_points: int = Field(ge=0, le=7, description="Points for transparency (0-7)")
    rationale: str = Field(description="1-2 sentence explanation of trust assessment")
    confidence_notes: list[str] = Field(default_factory=list, description="What we're uncertain about")
    corroboration_notes: list[str] = Field(
        default_factory=list, description="B1: Where website claims are corroborated by third-party data"
    )
    improvement_suggestions: list[str] = Field(
        default_factory=list, description="Actionable steps to strengthen Trust score (shown when score < 20)"
    )


class EvidenceAssessment(BaseModel):
    """Evidence Assessment (25 points max).

    Question: Does the program actually work?

    Components:
    - evidence_grade (10 pts): Methodology-agnostic, rigor and verification matter
      - A = 10 (third-party evaluation with published methodology)
      - B = 8 (3+ years outcome tracking with documented methodology)
      - C = 6 (1-2 years outcome data OR external evaluation)
      - D = 4 (tracks outputs but not outcomes)
      - F = 2 (no outcome data)
    - outcome_measurement (10 pts): COMPREHENSIVE = 10, STRONG = 8, MODERATE = 6, BASIC = 4, WEAK = 2
    - theory_of_change (5 pts): Published = 5, Documented = 4, Implicit = 2, None = 0
    """

    score: int = Field(ge=0, le=25, description="Total Evidence score (max 25)")
    evidence_grade: EvidenceGrade = Field(description="Evidence quality grade (A-F based on Candid metrics)")
    evidence_grade_points: int = Field(ge=0, le=10, description="Points for evidence grade (0-10)")
    evidence_grade_rationale: str = Field(description="Why this evidence grade was assigned")
    outcome_measurement: str = Field(
        description="Outcome measurement level: COMPREHENSIVE, STRONG, MODERATE, BASIC, WEAK"
    )
    outcome_measurement_points: int = Field(ge=0, le=10, description="Points for outcome measurement (0-10)")
    theory_of_change: str = Field(description="Theory of change status: PUBLISHED, DOCUMENTED, IMPLICIT, NONE")
    theory_of_change_points: int = Field(ge=0, le=5, description="Points for theory of change (0-5)")
    rationale: str = Field(description="1-2 sentence summary of evidence assessment")
    third_party_evaluated: bool = Field(default=False, description="Whether claims are verified by external evaluators")
    rct_available: bool = Field(default=False, description="Whether RCT evidence exists for this intervention type")
    improvement_suggestions: list[str] = Field(
        default_factory=list, description="Actionable steps to strengthen Evidence score (shown when score < 15)"
    )
    capacity_limited_evidence: bool = Field(
        default=False,
        description="True if low evidence score likely reflects limited M&E infrastructure rather than weak programs",
    )


class EffectivenessAssessment(BaseModel):
    """Effectiveness Assessment (25 points max).

    Question: How much good per dollar?

    Components:
    - cost_efficiency (10 pts): Exceptional=10, Above-avg=8, Avg=6, Below-avg=4, Poor=2, Unknown=0
    - scale_efficiency (10 pts): Same gradient (revenue-adjusted beneficiary reach)
    - room_for_funding (5 pts): High=5, Medium=3, Low=1, Unknown=0
    """

    score: int = Field(ge=0, le=25, description="Total Effectiveness score (max 25)")
    cost_efficiency: str = Field(
        description="Cost efficiency vs cause-area benchmark: EXCEPTIONAL, ABOVE_AVERAGE, AVERAGE, BELOW_AVERAGE, POOR, UNKNOWN"
    )
    cost_efficiency_points: int = Field(
        ge=0, le=10, description="Points for program efficiency floor check (0-5, le=10 for back-compat)"
    )
    cost_per_beneficiary: Optional[float] = Field(default=None, description="Calculated cost per beneficiary in USD")
    cause_benchmark: Optional[str] = Field(default=None, description="Cause-area benchmark used for comparison")
    scale_efficiency: str = Field(
        description="Revenue-adjusted scale efficiency: EXCEPTIONAL, ABOVE_AVERAGE, AVERAGE, BELOW_AVERAGE, POOR, UNKNOWN"
    )
    scale_efficiency_points: int = Field(
        ge=0, le=15, description="Points for cost-effectiveness (0-15, promoted from 10)"
    )
    room_for_funding: str = Field(
        description="Room for more funding: HIGH (10x more), MEDIUM (2-5x), LOW (near ceiling), UNKNOWN"
    )
    room_for_funding_points: int = Field(ge=0, le=5, description="Points for room for funding (0-5)")
    rationale: str = Field(description="1-2 sentence summary of effectiveness assessment")
    cash_comparison: Optional[str] = Field(
        default=None,
        description="Comparison to GiveDirectly benchmark: 10X_PLUS, 3_10X, 1_3X, BELOW_CASH, UNKNOWN",
    )
    improvement_suggestions: list[str] = Field(
        default_factory=list, description="Actionable steps to strengthen Effectiveness score (shown when score < 15)"
    )


class FitAssessment(BaseModel):
    """Fit Assessment (25 points max).

    Question: Is this right for donor goals?

    Components:
    - counterfactual (10 pts): HIGH (Muslim + zakat) = 10, MEDIUM (Muslim OR niche) = 6, LOW = 2
    - cause_fit (15 pts): importance (0-9) + neglectedness (0-6)
      - Importance based on detected_cause_area:
        - GLOBAL_HEALTH/HUMANITARIAN/EXTREME_POVERTY = 9
        - EDUCATION_GLOBAL = 7, DOMESTIC_POVERTY = 5, ADVOCACY = 4
        - RELIGIOUS_CULTURAL = 2, UNKNOWN = 3
      - Neglectedness: MUSLIM_FOCUSED = 6, NICHE = 4, MAINSTREAM = 2
    """

    score: int = Field(ge=0, le=25, description="Total Fit score (max 25)")
    counterfactual: str = Field(
        description="Counterfactual/replaceability: HIGH (Muslim + zakat), MEDIUM (Muslim OR niche), LOW (many alternatives)"
    )
    counterfactual_points: int = Field(
        ge=0, le=19, description="Points for counterfactual (0-19, rescaled from legacy 0-10)"
    )
    counterfactual_rationale: str = Field(description="Why this counterfactual assessment was assigned")
    cause_importance: str = Field(description="Cause importance level: HIGH, MEDIUM, LOW")
    cause_importance_points: int = Field(
        ge=0, le=13, description="Points for cause importance (0-13, rescaled from legacy 0-9)"
    )
    cause_neglectedness: str = Field(description="Cause neglectedness: MUSLIM_FOCUSED (6), NICHE (4), MAINSTREAM (2)")
    cause_neglectedness_points: int = Field(ge=0, le=6, description="Points for cause neglectedness (0-6)")
    rationale: str = Field(description="1-2 sentence summary of fit assessment")
    improvement_suggestions: list[str] = Field(
        default_factory=list, description="Actionable steps to strengthen Fit score (shown when score < 15)"
    )


class ZakatBonusAssessment(BaseModel):
    """Zakat Eligibility Assessment (Wallet Tag Only - NOT in score).

    IMPORTANT: Zakat eligibility determines wallet tag assignment ONLY.
    It does NOT contribute to the 100-point score.

    bonus_points is always 0 in V2 100-point scoring.
    """

    bonus_points: int = Field(ge=0, le=0, description="Always 0 - zakat is wallet tag only, not in score")
    charity_claims_zakat: bool = Field(description="Does charity explicitly claim zakat eligibility on website?")
    claim_evidence: Optional[str] = Field(default=None, description="Quote or location of zakat claim on website")
    asnaf_category: Optional[str] = Field(default=None, description="Asnaf category cited by charity")
    notes: Optional[str] = Field(default=None, description="Any caveats about the zakat claim")


# =============================================================================
# 3-Dimension Assessment Structure (GMG Score)
# =============================================================================


class CredibilityAssessment(BaseModel):
    """Credibility Assessment (33 points max).

    Merges former Trust + Evidence dimensions. Answers: Can we believe
    what they claim, and is there real evidence behind it?

    Components:
    - Verification Tier (10 pts): CN/Candid/BBB multi-signal
    - Transparency (7 pts): Candid seal + non-Candid signals
    - Data Quality (3 pts): # of corroborating sources
    - Theory of Change (5 pts): STRONG(5)/CLEAR(4)/DEVELOPING(2)/BASIC(1)/ABSENT(0)
    - Evidence & Outcomes (5 pts): VERIFIED(5)/TRACKED(4)/MEASURED(3)/REPORTED(1)/UNVERIFIED(0)
    - Governance (3 pts): Board size and oversight
    """

    score: int = Field(ge=0, le=33, description="Total Credibility score (max 33)")
    components: list[ScoreComponent] = Field(default_factory=list, description="Itemized score breakdown")
    rationale: str = Field(default="", description="1-2 sentence summary")

    # Carry-forward fields for narrative generation
    verification_tier: str = Field(default="NONE", description="HIGH/MODERATE/BASIC/NONE")
    theory_of_change_level: str = Field(default="ABSENT", description="STRONG/CLEAR/DEVELOPING/BASIC/ABSENT")
    evidence_quality_level: str = Field(
        default="UNVERIFIED", description="VERIFIED/TRACKED/MEASURED/REPORTED/UNVERIFIED"
    )
    confidence_notes: list[str] = Field(default_factory=list, description="Data gaps")
    corroboration_notes: list[str] = Field(default_factory=list, description="Corroborated claims")
    capacity_limited_evidence: bool = Field(
        default=False, description="Low evidence reflects M&E capacity, not program weakness"
    )


class DataConfidence(BaseModel):
    """Data Confidence signal (0.0-1.0, outside the 100-point score).

    Derived from credibility data-availability components:
    - Verification Tier (weight 0.50): HIGH=1.0, MODERATE=0.7, BASIC=0.4, NONE=0.0
    - Transparency (weight 0.35): PLATINUM=1.0, GOLD=0.86, SILVER=0.57, BRONZE=0.29, NONE=0.0
    - Data Quality (weight 0.15): HIGH=1.0, MODERATE=0.67, LOW=0.33, CONFLICTING=0.0

    Badge levels: HIGH (≥0.7), MEDIUM (0.4-0.7), LOW (<0.4)
    """

    overall: float = Field(ge=0.0, le=1.0, description="Weighted confidence score (0.0-1.0)")
    badge: str = Field(description="Display badge: HIGH, MEDIUM, LOW")

    # Component breakdown
    verification_tier: str = Field(default="NONE", description="HIGH/MODERATE/BASIC/NONE")
    verification_value: float = Field(default=0.0, ge=0.0, le=1.0, description="Verification confidence value")
    transparency_label: str = Field(default="NONE", description="PLATINUM/GOLD/SILVER/BRONZE/NONE")
    transparency_value: float = Field(default=0.0, ge=0.0, le=1.0, description="Transparency confidence value")
    data_quality_label: str = Field(default="LOW", description="HIGH/MODERATE/LOW/CONFLICTING")
    data_quality_value: float = Field(default=0.0, ge=0.0, le=1.0, description="Data quality confidence value")


class ImpactAssessment(BaseModel):
    """Impact Assessment (50 points max).

    Answers: How much good per dollar, and can they prove it?

    Components are re-weighted per archetype (v5.0.0):
    - Cost Per Beneficiary: Cause-adjusted benchmarks with smooth interpolation
    - Directness: How directly funds reach people
    - Financial Health: Reserves sweet spot (smooth interpolation)
    - Program Ratio: Smooth interpolation over ratio
    - Evidence & Outcomes: Absorbed from Credibility
    - Theory of Change: Absorbed from Credibility
    - Governance: Absorbed from Credibility

    All archetypes sum to 50.
    """

    score: int = Field(ge=0, le=50, description="Total Impact score (max 50)")
    components: list[ScoreComponent] = Field(default_factory=list, description="Itemized score breakdown")
    rationale: str = Field(default="", description="1-2 sentence summary")

    # Carry-forward fields
    cost_per_beneficiary: Optional[float] = Field(default=None, description="Calculated $/beneficiary")
    directness_level: str = Field(default="UNKNOWN", description="Direct service → Indirect scale")
    impact_design_categories: list[str] = Field(
        default_factory=list,
        description="Which keyword categories matched: resilience, leverage, durability, sovereignty",
    )
    rubric_archetype: str = Field(
        default="DIRECT_SERVICE",
        description="Archetype used for Impact weight profile (e.g. SYSTEMIC_CHANGE, EDUCATION)",
    )


class AlignmentAssessment(BaseModel):
    """Alignment Assessment (50 points max).

    Answers: Is this the right charity for me as a Muslim donor?

    Components:
    - Muslim Donor Fit (19 pts): Layered additive (zakat clarity + asnaf + Muslim-focused + populations + identity)
    - Cause Urgency (13 pts): Cause map from global health(13) → religious(4)
    - Underserved Space (7 pts): Niche cause + underserved populations
    - Track Record (6 pts): Smooth interpolation over years since founding
    - Funding Gap (5 pts): Compressed revenue tiers
    """

    score: int = Field(ge=0, le=50, description="Total Alignment score (max 50)")
    components: list[ScoreComponent] = Field(default_factory=list, description="Itemized score breakdown")
    rationale: str = Field(default="", description="1-2 sentence summary")

    # Carry-forward fields
    muslim_donor_fit_level: str = Field(default="LOW", description="HIGH/MEDIUM/LOW")
    cause_urgency_label: str = Field(default="UNKNOWN", description="Cause area label")


class AmalScoresV2(BaseModel):
    """GMG Score — 2-Dimension Framework (100-Point Scale).

    Impact (50) + Alignment (50) + Risk (-10 max).
    Data Confidence (0.0-1.0) reported separately, outside the score.

    IMPORTANT: Zakat eligibility determines wallet tag ONLY, not score.

    Max score: 100 points
    Min score: 0 (with up to -10 risk deductions capped at 0)

    Expected score ranges:
    - GiveWell Top Charity: 85-100
    - Strong poverty relief: 70-85
    - Average nonprofit: 50-65
    - Well-run Islamic school: 45-60
    - Typical mosque: 35-50
    """

    amal_score: int = Field(ge=0, le=100, description="Total GMG score (max 100)")

    # The 2 scored dimensions
    impact: ImpactAssessment = Field(description="Impact dimension (max 50 pts)")
    alignment: AlignmentAssessment = Field(description="Alignment dimension (max 50 pts)")

    # Internal credibility (feeds DataConfidence, not in score)
    credibility: CredibilityAssessment = Field(description="Internal credibility (feeds DataConfidence, not in score)")

    # Data Confidence (outside score)
    data_confidence: DataConfidence = Field(description="Data confidence signal (0.0-1.0, outside score)")

    # Wallet tag info (not in score)
    zakat_bonus: ZakatBonusAssessment = Field(description="Zakat eligibility (wallet tag only, NOT in score)")

    # Risk Assessment (Longview "Case Against")
    case_against: CaseAgainst = Field(description="Longview-style risk disclosure with deductions (up to -10)")
    risk_deduction: int = Field(ge=-10, le=0, description="Total risk deduction (0 to -10)")

    # Wallet routing
    wallet_tag: str = Field(
        description="Wallet routing tag: ZAKAT-ELIGIBLE or SADAQAH-ELIGIBLE (binary classification based on charity's self-assertion)"
    )

    # Plain-English summary (deterministic template, not LLM-generated)
    score_summary: str = Field(
        default="",
        description="One-sentence plain-English explanation of the score",
    )

    # Legacy compatibility — old 5-assessment fields (populated from new dimensions)
    trust: Optional[TrustAssessment] = Field(default=None, description="Legacy: mapped from credibility")
    evidence: Optional[EvidenceAssessment] = Field(default=None, description="Legacy: mapped from credibility")
    effectiveness: Optional[EffectivenessAssessment] = Field(default=None, description="Legacy: mapped from impact")
    fit: Optional[FitAssessment] = Field(default=None, description="Legacy: mapped from alignment")

    def calculate_score(self) -> int:
        """Calculate total GMG score from 2 dimensions + risk."""
        base_score = self.impact.score + self.alignment.score + self.risk_deduction
        return max(0, min(100, base_score))


# =============================================================================
# LEGACY: Old Tier-based Structure (to be deprecated)
# =============================================================================


# Ummah Gap sub-scores (total: 0-20)
class UmmahGapSubScores(BaseModel):
    """Sub-component scores for Ummah Gap dimension.

    Total: 0-20 points = Replaceability (0-8) + Ummah Relevance (0-6) + Funding Gap (0-6)
    """

    replaceability: SubScore = Field(
        description="0-8: If this org disappeared tomorrow, how hard to replace what they do?"
    )
    ummah_relevance: SubScore = Field(
        description="0-6: Does this disproportionately affect Muslims (even if not exclusively serving them)?"
    )
    funding_gap: SubScore = Field(description="0-6: Is this underfunded by Muslim donors relative to need?")


# Operational Capability sub-scores (total: 0-25)
class OperationalCapabilitySubScores(BaseModel):
    """Sub-component scores for Operational Capability dimension.

    Total: 0-25 points = Governance (0-8) + Program Efficiency (0-8) + Deployment (0-6) + Track Record (0-3)
    """

    governance: SubScore = Field(
        description="0-8: CN accountability score, board independence, audits, policies (reduced weight)"
    )
    program_efficiency: SubScore = Field(
        description="0-8: Program expense ratio (85%+=8, 80-84%=6, 75-79%=4, 65-74%=2, <65%=0)"
    )
    deployment_capacity: SubScore = Field(
        description="0-6: Can absorb additional funds? ($25M+ multi-country=6, $5-25M national=4, $1-5M regional=2, <$1M local=0)"
    )
    track_record: SubScore = Field(description="0-3: Consistent delivery over time (10+ years=3, 5-10=2, 2-5=1, <2=0)")


# Mission Delivery sub-scores (total: 0-25)
class MissionDeliverySubScores(BaseModel):
    """Sub-component scores for Mission Delivery dimension.

    Total: 0-25 points = Delivery Evidence (0-12) + Cost-Effectiveness (0-8) + Learning (0-5)

    Key point: The right metric depends on the mission. "Meals served" IS the outcome
    if feeding people is the goal. We're not requiring downstream impact measurement -
    just evidence they're doing what they say.

    Evidence-Based Giving additions:
    - evidence_quality: A-F grade based on research methodology (RCT > observational > self-reported)
    - third_party_verification: Whether claims are verified by external evaluators
    - cost_benchmark: Comparison to cause-area cost-effectiveness benchmarks
    """

    delivery_evidence: SubScore = Field(
        description="0-12: Are they actually delivering on their stated mission? (meals for food banks, surgeries for medical orgs, graduates for schools)"
    )
    cost_effectiveness: SubScore = Field(
        description="0-8: Cost per unit of delivery vs benchmarks (top quartile=8, below median=6, average=4, poor=2, no data=0)"
    )
    learning_adaptation: SubScore = Field(
        description="0-5: Do they improve based on data? (systematic=5, informal=3, static=1)"
    )

    # Evidence-Based Giving additions
    evidence_quality: Optional[EvidenceQualityGrade] = Field(
        default=None,
        description="Evidence quality grade (A-F) based on research methodology. Modifies delivery_evidence score.",
    )
    third_party_verification: Optional[ThirdPartyVerification] = Field(
        default=None,
        description="Third-party verification status. Tier 1 (J-PAL, GiveWell) adds +1 to delivery_evidence.",
    )
    cost_benchmark: Optional[CostEffectivenessBenchmark] = Field(
        default=None,
        description="Cost-effectiveness comparison to cause-area benchmarks (GiveWell, J-PAL standards).",
    )


class Program(BaseModel):
    """A program run by the charity."""

    name: str = Field(description="Program name")
    description: str = Field(description="Brief description of what the program does")


class Beneficiaries(BaseModel):
    """Information about who the charity serves."""

    populations_served: list[str] = Field(
        description="Types of populations served (e.g., 'refugees', 'orphans', 'low-income families')"
    )
    annual_beneficiaries: Optional[int] = Field(
        default=None, description="Estimated number of beneficiaries served annually"
    )
    geographic_focus: Optional[str] = Field(
        default=None, description="Primary geographic areas served (e.g., 'Syria, Yemen, Gaza')"
    )


class ImpactMetrics(BaseModel):
    """Measurable impact data for the charity."""

    key_metrics: list[str] = Field(
        description="2-3 key impact metrics with numbers (e.g., '500,000 meals distributed', '10,000 students educated')"
    )
    outcome_highlights: Optional[str] = Field(
        default=None, description="Notable outcomes or achievements with evidence"
    )


class Links(BaseModel):
    """External links for the charity."""

    website_url: Optional[str] = Field(default=None, description="Official website URL")
    donation_url: Optional[str] = Field(default=None, description="Direct donation page URL")


class AmalDimensionScore(BaseModel):
    """Score and rationale for a single AMAL dimension.

    Used for systemic_leverage (no sub-scores).
    """

    score: int = Field(ge=0, le=30, description="Score for this dimension")
    confidence: DimensionConfidence = Field(description="Data quality assessment for this dimension")
    narrative: str = Field(description="1-3 sentence explanation of the score")
    evidence: list[str] = Field(
        default_factory=list,
        description="Short evidence references (e.g., 'Form 990 2023', 'CN Profile')",
    )


class UmmahGapScore(BaseModel):
    """Ummah Gap dimension score with sub-components.

    Total: 0-20 points = Replaceability (0-8) + Ummah Relevance (0-6) + Funding Gap (0-6)
    """

    score: int = Field(ge=0, le=20, description="Total Ummah Gap score (sum of sub-scores)")
    confidence: DimensionConfidence = Field(description="Data quality assessment for this dimension")
    narrative: str = Field(description="1-3 sentence summary of Ummah Gap assessment")
    sub_scores: UmmahGapSubScores = Field(description="Breakdown by sub-component")


class OperationalCapabilityScore(BaseModel):
    """Operational Capability dimension score with sub-components.

    Total: 0-25 points = Governance (0-8) + Program Efficiency (0-8) + Deployment (0-6) + Track Record (0-3)
    """

    score: int = Field(ge=0, le=25, description="Total Operational Capability score (sum of sub-scores)")
    confidence: DimensionConfidence = Field(description="Data quality assessment for this dimension")
    narrative: str = Field(description="1-3 sentence summary of Operational Capability assessment")
    sub_scores: OperationalCapabilitySubScores = Field(description="Breakdown by sub-component")


class MissionDeliveryScore(BaseModel):
    """Mission Delivery dimension score with sub-components.

    Total: 0-25 points = Delivery Evidence (0-12) + Cost-Effectiveness (0-8) + Learning (0-5)
    """

    score: int = Field(ge=0, le=25, description="Total Mission Delivery score (sum of sub-scores)")
    confidence: DimensionConfidence = Field(description="Data quality assessment for this dimension")
    narrative: str = Field(description="1-3 sentence summary of Mission Delivery assessment")
    sub_scores: MissionDeliverySubScores = Field(description="Breakdown by sub-component")


class Tier1StrategicFit(BaseModel):
    """Tier 1 Strategic Fit scores (50 points max).

    Assesses whether the charity addresses root causes and fills gaps
    in the Muslim philanthropic ecosystem.
    """

    subtotal: int = Field(ge=0, le=50, description="Sum of systemic_leverage + ummah_gap (max 50)")
    systemic_leverage: AmalDimensionScore = Field(
        description="0-30 points: Is this a root-cause cure or temporary band-aid?"
    )
    ummah_gap: UmmahGapScore = Field(
        description="0-20 points: Is this an orphaned cause or crowded trade? Includes sub-scores."
    )


class Tier2Execution(BaseModel):
    """Tier 2 Execution Effectiveness scores (50 points max).

    Assesses whether the charity is actually delivering on its mission
    and has the operational capability to do so effectively.
    """

    subtotal: int = Field(ge=0, le=50, description="Sum of operational_capability + mission_delivery (max 50)")
    operational_capability: OperationalCapabilityScore = Field(
        description="0-25 points: Can they execute well? Governance (reduced weight) + efficiency + deployment capacity."
    )
    mission_delivery: MissionDeliveryScore = Field(
        description="0-25 points: Are they actually delivering? Delivery evidence is primary signal."
    )


class ZakatClaimInfo(BaseModel):
    """Charity's self-assertion of zakat eligibility."""

    charity_claims_zakat: bool = Field(
        description="Does the charity explicitly claim zakat eligibility on their website?"
    )
    claim_evidence: Optional[str] = Field(
        default=None,
        description="Direct quote or description of where claim appears on website",
    )
    asnaf_category: Optional[str] = Field(
        default=None,
        description="Which asnaf category does the charity cite (fuqara, masakin, fi_sabilillah, etc.)",
    )
    notes: Optional[str] = Field(default=None, description="Any caveats or clarifications about the claim")


class AmalScores(BaseModel):
    """AMAL Impact Matrix evaluation scores.

    Total score is 100 points: Tier 1 (50) + Tier 2 (50).
    This structure matches the website's AmalEvaluation type.
    """

    amal_score: int = Field(ge=0, le=100, description="Total AMAL score (tier_1 + tier_2)")
    tier_1_strategic_fit: Tier1StrategicFit = Field(description="Strategic fit assessment (50 points max)")
    tier_2_execution: Tier2Execution = Field(description="Execution capability assessment (50 points max)")
    wallet_tag: str = Field(description="Wallet routing tag: ZAKAT-ELIGIBLE or SADAQAH-ELIGIBLE (binary)")
    zakat_eligible: bool = Field(
        description="True ONLY if charity explicitly claims zakat eligibility on their website"
    )
    zakat_claim: Optional[ZakatClaimInfo] = Field(
        default=None,
        description="Details of charity's zakat claim from their website",
    )


class BaselineNarrative(BaseModel):
    """Complete baseline narrative schema.

    This is the structured output format for LLM generation.
    All fields are required except those marked Optional in nested models.

    Constraints:
    - headline: max 200 characters
    - summary: 150-200 words (~750-1000 characters)
    - strengths: exactly 2-3 items, each with evidence
    - programs: 1-3 key programs
    - impact_metrics: 2-3 measurable metrics

    Note: amal_scores includes detailed rationale for each dimension.
    """

    headline: str = Field(max_length=200, description="Compelling 1-line headline about the charity")
    at_a_glance: AtAGlance = Field(description="Quick facts section")
    summary: str = Field(max_length=1500, description="150-200 word overview of the charity")
    programs: list[Program] = Field(min_length=1, max_length=3, description="1-3 key programs the charity runs")
    beneficiaries: Beneficiaries = Field(description="Who the charity serves")
    strengths: list[Strength] = Field(min_length=2, max_length=3, description="2-3 key strengths with evidence")
    improvement_areas: list[ImprovementArea] = Field(
        min_length=1, max_length=2, description="1-2 areas for improvement (constructive, data-backed)"
    )
    impact_metrics: ImpactMetrics = Field(description="Measurable impact data")
    zakat_guidance: ZakatGuidance = Field(description="Zakat eligibility guidance with donor advisory")
    amal_scores: AmalScores = Field(description="AMAL evaluation scores with rationale for each dimension")
    links: Links = Field(description="Website and donation URLs")
    confidence: Confidence = Field(description="Data confidence assessment")

    @classmethod
    def get_field_count(cls) -> int:
        """Return the total number of countable fields for density calculation.

        Baseline fields (67 total):
        - headline: 1
        - at_a_glance: 8 (includes signature_achievement)
        - summary: 1
        - programs: 2 (name + description, union across all programs)
        - beneficiaries: 3 (populations_served, annual_beneficiaries, geographic_focus)
        - strengths: 2 (point + evidence, union across all strengths)
        - improvement_areas: 2 (area + context, union across all areas)
        - impact_metrics: 2 (key_metrics, outcome_highlights)
        - zakat_guidance: 5 (eligibility, categories_served, rationale, scholarly_considerations, donor_advisory)
        - amal_scores: 21 (amal_score(1) + tier_1(1 + 2×4) + tier_2(1 + 2×4) + wallet_tag + zakat_eligible)
        - links: 2
        - confidence: 3
        - evidence_quality: 4 (grade, methodology_type, sources, rationale)
        - third_party_verification: 5 (verified, sources, verification_type, last_verified_year, tier)
        - cost_benchmark: 7 (cause_area, cost_per_beneficiary, benchmark_name, benchmark_range, comparison, ratio, data_source)
        """
        return 67


# =============================================================================
# V2 Narrative Structure (GWWC + Longview Anchored)
# =============================================================================


class BaselineNarrativeV2(BaseModel):
    """Complete baseline narrative schema V2 — GMG 2-Dimension Framework.

    Key changes from V1:
    - Uses 2-dimension structure (Impact 50, Alignment 50)
    - Data Confidence (0.0-1.0) reported separately, outside the score
    - Includes "Case Against" risk disclosure per Longview
    - Zakat eligibility is wallet tag only, NOT in score
    - Max score: 100 points

    All fields are required except those marked Optional in nested models.

    Constraints:
    - headline: max 200 characters
    - summary: 150-200 words (~750-1000 characters)
    - strengths: exactly 2-3 items, each with evidence
    - programs: 1-3 key programs
    - impact_metrics: 2-3 measurable metrics
    """

    headline: str = Field(max_length=200, description="Compelling 1-line headline about the charity")
    at_a_glance: AtAGlance = Field(description="Quick facts section")
    summary: str = Field(max_length=1500, description="150-200 word overview of the charity")
    programs: list[Program] = Field(min_length=1, max_length=3, description="1-3 key programs the charity runs")
    beneficiaries: Beneficiaries = Field(description="Who the charity serves")
    strengths: list[Strength] = Field(min_length=2, max_length=3, description="2-3 key strengths with evidence")
    improvement_areas: list[ImprovementArea] = Field(
        min_length=1, max_length=2, description="1-2 areas for improvement (constructive, data-backed)"
    )
    impact_metrics: ImpactMetrics = Field(description="Measurable impact data")
    zakat_guidance: ZakatGuidance = Field(description="Zakat eligibility guidance with donor advisory")

    # V2: New 5-assessment structure
    amal_scores: AmalScoresV2 = Field(description="AMAL evaluation scores V2 with 5 assessments")

    links: Links = Field(description="Website and donation URLs")
    confidence: Confidence = Field(description="Data confidence assessment")

    @classmethod
    def get_field_count(cls) -> int:
        """Return the total number of countable fields for density calculation.

        V2 Baseline fields (estimated 75 total):
        - headline: 1
        - at_a_glance: 8
        - summary: 1
        - programs: 2
        - beneficiaries: 3
        - strengths: 2
        - improvement_areas: 2
        - impact_metrics: 2
        - zakat_guidance: 5
        - amal_scores_v2: ~30 (5 assessments × ~6 fields each)
        - links: 2
        - confidence: 3
        """
        return 75

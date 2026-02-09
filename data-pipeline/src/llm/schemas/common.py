"""Shared Pydantic schema classes for Baseline and Rich Narratives.

This module contains unified schema classes used by both baseline.py and rich.py.
Optional fields with defaults allow the same classes to work for both simpler
baseline narratives and more detailed rich narratives.

Redesign anchored on GWWC + Longview evidence-based giving principles.
See data-pipeline/docs/EVALUATION_REDESIGN.md for full specification.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# =============================================================================
# Evidence Grade Enum (GWWC Hierarchy)
# =============================================================================


class EvidenceGrade(str, Enum):
    """Evidence quality classification using GWWC/GiveWell research hierarchy.

    Points allocation (out of 15):
    - A: 15 points (RCT-validated, gold standard)
    - B: 12 points (third-party evaluated)
    - C: 10 points (outcomes with methodology)
    - D: 8 points (outcomes reported)
    - E: 6 points (outputs tracked over time)
    - F: 4 points (outputs only)
    - G: 2 points (claims only)
    - H: 0 points (no evidence)
    """

    A = "A"  # RCT-validated intervention (GiveWell Top Charity level)
    B = "B"  # Third-party evaluated (J-PAL, IDinsight, external audit)
    C = "C"  # Outcomes with methodology documented
    D = "D"  # Outcomes reported without methodology
    E = "E"  # Outputs tracked with trends over time
    F = "F"  # Basic outputs only ("served 10,000")
    G = "G"  # Claims only (testimonials, anecdotes)
    H = "H"  # No evidence available

    @property
    def points(self) -> int:
        """Return point value for this grade (out of 15)."""
        return {
            "A": 15,
            "B": 12,
            "C": 10,
            "D": 8,
            "E": 6,
            "F": 4,
            "G": 2,
            "H": 0,
        }[self.value]

    @property
    def description(self) -> str:
        """Human-readable description of this grade."""
        return {
            "A": "RCT-validated intervention",
            "B": "Third-party evaluated",
            "C": "Outcomes with methodology",
            "D": "Outcomes reported",
            "E": "Outputs tracked over time",
            "F": "Basic outputs only",
            "G": "Claims only",
            "H": "No evidence",
        }[self.value]


# =============================================================================
# Risk Assessment (Longview "Case Against")
# =============================================================================


class RiskCategory(str, Enum):
    """Categories of risk for the Case Against assessment."""

    FINANCIAL = "financial"  # Revenue decline, concentration, reserves
    OPERATIONAL = "operational"  # Leadership, geography, program dependency
    IMPACT = "impact"  # Evidence gaps, unproven intervention
    EXTERNAL = "external"  # Regulatory, political, controversy


class RiskSeverity(str, Enum):
    """Severity level for identified risks.

    Point deductions:
    - HIGH: -5 each (max -10 total)
    - MEDIUM: -2 each (max -6 total)
    - LOW: -1 each (max -3 total)
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def deduction(self) -> int:
        """Return point deduction for this severity."""
        return {"high": 5, "medium": 2, "low": 1}[self.value]


class RiskFactor(BaseModel):
    """A single identified risk factor.

    Part of Longview's "Case Against" requirement - explicit documentation
    of the strongest objections to funding this charity.
    """

    category: RiskCategory = Field(description="Risk category: financial, operational, impact, or external")
    description: str = Field(description="Clear description of the risk (e.g., 'Revenue declined 15% YoY')")
    severity: RiskSeverity = Field(description="Risk severity: high, medium, or low")
    mitigation: Optional[str] = Field(
        default=None,
        description="What the charity is doing to address this risk (if known)",
    )
    data_source: Optional[str] = Field(
        default=None,
        description="Source of data supporting this risk (e.g., 'Form 990 2023')",
    )


class CaseAgainst(BaseModel):
    """Longview-style 'Case Against' risk disclosure.

    Required for both Baseline (1-2 key risks) and Rich (full analysis) narratives.
    Documents the strongest objections to funding this charity.
    """

    risks: list[RiskFactor] = Field(
        default_factory=list,
        description="List of identified risk factors",
    )
    overall_risk_level: str = Field(description="Overall risk level: LOW, MODERATE, ELEVATED, or HIGH")
    risk_summary: str = Field(description="1-2 sentence summary of key risks for donors")
    total_deduction: Optional[int] = Field(
        default=None,
        description="Total point deduction from risks (max -10)",
    )


# =============================================================================
# Original Models (Evidence, Strength, etc.)
# =============================================================================


class Evidence(BaseModel):
    """Evidence citation for a claim.

    Every claim in the narrative must be backed by evidence from
    actual data sources with specific field references.
    """

    claim: str = Field(description="The claim being made")
    source: str = Field(description="Data source (e.g., 'Form 990', 'Website', 'GuideStar')")
    source_year: int = Field(description="Year of the source data")
    field: str = Field(description="Specific field from the source (e.g., 'total_revenue')")
    value: str = Field(description="The actual value from the source")
    confidence: Optional[str] = Field(
        default=None, description="Confidence level: HIGH, MEDIUM, or LOW (rich narratives only)"
    )


class Strength(BaseModel):
    """A key strength of the charity with supporting evidence."""

    point: str = Field(description="Brief description of the strength")
    evidence: Evidence = Field(description="Evidence supporting this strength")


class AtAGlance(BaseModel):
    """Quick facts about the charity.

    These fields populate the at-a-glance section visible in search results
    and the top of charity profiles.
    """

    founded_year: Optional[int] = Field(default=None, description="Year the organization was founded")
    annual_revenue: Optional[str] = Field(
        default=None, description="Annual revenue as formatted string (e.g., '$12.5M')"
    )
    revenue_year: Optional[int] = Field(default=None, description="Fiscal year for the revenue figure")
    employees: Optional[int] = Field(default=None, description="Number of employees")
    geographic_reach: Optional[str] = Field(
        default=None, description="Geographic scope (e.g., 'Global - 40+ countries')"
    )
    key_stat: Optional[str] = Field(
        default=None, description="One impactful statistic (e.g., '500,000 meals served annually')"
    )
    signature_achievement: Optional[str] = Field(
        default=None, description="Notable accomplishment or milestone (rich narratives only)"
    )
    last_updated: str = Field(description="ISO date when this data was last verified (e.g., '2024-12')")


class ImprovementArea(BaseModel):
    """An area where the charity could improve.

    Framed constructively to help donors understand gaps without being
    overly critical. Focus on transparency, efficiency, or impact opportunities.
    """

    area: str = Field(description="Brief description of the improvement opportunity")
    context: str = Field(
        description="Why this matters or what data suggests this (e.g., 'Program expense ratio of 65% is below sector average')"
    )
    constructive_note: Optional[str] = Field(
        default=None, description="Additional constructive framing (rich narratives only)"
    )


class Confidence(BaseModel):
    """Confidence score for the narrative.

    Indicates how complete and reliable the data is for this charity.
    """

    score: int = Field(ge=0, le=100, description="Confidence score 0-100")
    level: str = Field(description="Human-readable level: HIGH (80-100), MEDIUM (50-79), LOW (0-49)")
    data_gaps: list[str] = Field(default_factory=list, description="List of missing or outdated data fields")
    data_freshness: Optional[str] = Field(
        default=None, description="Assessment of how recent the data is (rich narratives only)"
    )
    sources_used: Optional[list[str]] = Field(
        default=None, description="List of data sources used in this narrative (rich narratives only)"
    )
    notes: Optional[str] = Field(
        default=None, description="Additional notes on data quality or limitations (rich narratives only)"
    )


class ZakatClaim(BaseModel):
    """Charity's self-assertion of zakat eligibility.

    Based on what the charity explicitly claims on their website.
    We report the claim, not make the determination ourselves.
    """

    charity_claims_zakat: bool = Field(
        description="Does the charity explicitly claim zakat eligibility on their website?"
    )
    claim_evidence: Optional[str] = Field(
        default=None,
        description="Direct quote or description of where claim appears (e.g., 'Donate page states: 100% Zakat Policy')",
    )
    asnaf_category: Optional[str] = Field(
        default=None,
        description="Which asnaf category does the charity cite (fuqara, masakin, fi_sabilillah, etc.)",
    )
    notes: Optional[str] = Field(default=None, description="Any caveats or clarifications about the claim")


class ZakatGuidance(BaseModel):
    """Zakat eligibility guidance.

    Based on charity's self-assertion, not our judgment.
    """

    eligibility: str = Field(
        description="Classification: ZAKAT-ELIGIBLE or SADAQAH-ELIGIBLE (binary based on self-assertion)"
    )
    categories_served: list[str] = Field(
        default_factory=list,
        description="Asnaf categories the charity claims to serve (if any)",
    )
    rationale: str = Field(description="Explanation based on charity's own claims")
    scholarly_considerations: Optional[str] = Field(
        default=None, description="Notes on scholarly differences or areas of ijtihad"
    )
    donor_advisory: Optional[str] = Field(default=None, description="Practical advice for the donor regarding zakat")


# Evidence-Based Giving Models
# These support the A-F evidence grading, third-party verification, and cost benchmarking


class EvidenceQualityGrade(BaseModel):
    """Evidence quality classification using research hierarchy.

    Based on GiveWell's evidence standards:
    - A: RCT/meta-analysis (gold standard)
    - B: Quasi-experimental (diff-in-diff, regression discontinuity)
    - C: Observational with controls (cohort, case-control)
    - D: Pre/post only (no control group)
    - E: Self-reported (internal monitoring only)
    - F: Anecdotal (testimonials only)

    Score modifiers: A=+2, B=+1, C=0, D=-1, E=-2, F=-3
    """

    grade: str = Field(description="Evidence quality grade: A, B, C, D, E, or F")
    methodology_type: Optional[str] = Field(
        default=None,
        description="Specific methodology: RCT, difference-in-difference, cohort study, pre-post, etc.",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Sources where evidence methodology was found (e.g., 'Annual Report 2023', 'J-PAL evaluation')",
    )
    rationale: str = Field(description="1-2 sentences explaining WHY this grade was assigned")


class ThirdPartyVerification(BaseModel):
    """Third-party verification status for impact claims.

    Distinguishes between verified and self-reported outcomes.
    Verification by tier 1 sources (J-PAL, GiveWell, IDinsight) provides
    highest confidence in impact claims.
    """

    verified: bool = Field(description="True if impact claims are verified by independent third party")
    sources: list[str] = Field(
        default_factory=list,
        description="Verification sources (e.g., 'J-PAL', 'GiveWell', 'IDinsight', 'External audit')",
    )
    verification_type: Optional[str] = Field(
        default=None,
        description="Type: independent_evaluation, external_audit, peer_review, media_investigation",
    )
    last_verified_year: Optional[int] = Field(default=None, description="Year of most recent third-party verification")
    tier: Optional[str] = Field(
        default=None,
        description="Verification tier: tier_1_gold, tier_2_strong, tier_3_moderate",
    )


class CostEffectivenessBenchmark(BaseModel):
    """Cost-effectiveness comparison to cause-area benchmarks.

    Compares charity's cost-per-beneficiary to sector standards
    from GiveWell, J-PAL, and industry benchmarks.
    """

    cause_area: str = Field(
        description="Cause area for benchmarking: HUMANITARIAN, MEDICAL_HEALTH, EDUCATION_K12, etc."
    )
    cost_per_beneficiary: Optional[float] = Field(
        default=None, description="Charity's calculated cost per beneficiary in USD"
    )
    benchmark_name: str = Field(
        description="Name of benchmark used (e.g., 'cost_per_life_saved', 'cost_per_student_year')"
    )
    benchmark_range: Optional[list[float]] = Field(
        default=None,
        description="Benchmark range [low, high] for 'good' performance",
    )
    comparison: str = Field(
        description="Result: above_benchmark (better), at_benchmark, below_benchmark (worse), insufficient_data"
    )
    ratio: Optional[float] = Field(
        default=None,
        description="Charity cost / benchmark midpoint (lower is better for most metrics)",
    )
    data_source: Optional[str] = Field(
        default=None, description="Source for cost data: Form 990, annual report, website"
    )


# =============================================================================
# 3-Dimension Scoring Framework Models
# =============================================================================


class EvidenceQuality(str, Enum):
    """Evidence quality level for outcome tracking.

    Used in Credibility dimension to assess how rigorously
    a charity tracks and verifies its outcomes.

    Points (out of 5):
    - VERIFIED (5): Third-party verified outcomes with published methodology
    - TRACKED (4): 3+ years outcome tracking with documented methodology
    - MEASURED (3): 1-2 years outcome data or external evaluation
    - REPORTED (1): Tracks outputs but not outcomes
    - UNVERIFIED (0): No outcome data or external review
    """

    VERIFIED = "VERIFIED"
    TRACKED = "TRACKED"
    MEASURED = "MEASURED"
    REPORTED = "REPORTED"
    UNVERIFIED = "UNVERIFIED"

    @property
    def points(self) -> int:
        """Return point value for this quality level (out of 5)."""
        return {
            "VERIFIED": 5,
            "TRACKED": 4,
            "MEASURED": 3,
            "REPORTED": 1,
            "UNVERIFIED": 0,
        }[self.value]

    @property
    def description(self) -> str:
        """Human-readable description."""
        return {
            "VERIFIED": "Third-party verified outcomes",
            "TRACKED": "Multi-year outcome tracking with methodology",
            "MEASURED": "Outcome data collected",
            "REPORTED": "Outputs tracked, not outcomes",
            "UNVERIFIED": "No outcome data",
        }[self.value]


class ComponentStatus(str, Enum):
    """Status of a score component's data availability."""

    FULL = "full"  # All data available, scored at full fidelity
    PARTIAL = "partial"  # Some data missing, scored with caveats
    MISSING = "missing"  # No data available, scored at minimum


class ScoreComponent(BaseModel):
    """Atomic scoring unit — one sub-score within a dimension.

    Every component in every dimension produces one of these.
    Frontend renders as a progress bar row with evidence + improvement tips.
    """

    name: str = Field(description="Component name (e.g., 'Verification Tier', 'Cost Per Beneficiary')")
    scored: int = Field(description="Points earned for this component")
    possible: int = Field(description="Maximum possible points for this component")
    evidence: str = Field(description="1-2 sentence evidence string explaining the score")
    status: ComponentStatus = Field(description="Data availability: full, partial, or missing")
    improvement_suggestion: Optional[str] = Field(
        default=None,
        description="Actionable improvement tip (shown when points are recoverable)",
    )
    improvement_value: int = Field(
        default=0,
        description="Points recoverable if improvement suggestion is followed",
    )

    @property
    def pct(self) -> float:
        """Percentage of possible points earned."""
        return (self.scored / self.possible * 100) if self.possible > 0 else 0.0


class DimensionScore(BaseModel):
    """Score for one of the 3 main dimensions (Credibility, Impact, Alignment).

    Aggregates ScoreComponents and provides the dimension total.
    """

    dimension: str = Field(description="Dimension name: credibility, impact, or alignment")
    score: int = Field(description="Total points earned in this dimension")
    max_score: int = Field(description="Maximum possible points (33, 33, or 34)")
    components: list[ScoreComponent] = Field(
        default_factory=list,
        description="Itemized score breakdown",
    )
    rationale: str = Field(default="", description="1-2 sentence summary of dimension assessment")

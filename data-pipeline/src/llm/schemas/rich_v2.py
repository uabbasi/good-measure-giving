"""RichNarrativeV2 - Rich Narrative with Citation Support.

Rich narratives are 500-800 word evaluations for curated charities that
elaborate on baseline without contradicting scores or facts.

Key features:
- Inline citation markers [1], [2], [3] for all factual claims
- Citation registry mapping markers to sources
- Immutable fields inherited from baseline (not regenerated)
- Consistency validation with baseline narrative

Citation sources come from:
- Form 990 (ProPublica)
- Charity Navigator ratings
- Agent discoveries (rating, evidence, reputation, profile)
- Website content
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .baseline import AmalScores
from .common import AtAGlance, Confidence, ZakatGuidance


class SourceType(str, Enum):
    """Types of citation sources."""

    FORM_990 = "form990"
    RATING = "rating"
    EVALUATION = "evaluation"
    NEWS = "news"
    WEBSITE = "website"
    SEARCH = "search"
    ACADEMIC = "academic"
    GOVERNMENT = "government"


class Citation(BaseModel):
    """A citation supporting a claim in the narrative.

    Each citation maps to an inline marker like [1], [2], etc.
    """

    id: str = Field(description="Marker ID, e.g., '[1]', '[2]'")
    claim: str = Field(description="The specific claim this citation supports")
    source_name: str = Field(description="Human-readable source name, e.g., 'Charity Navigator'")
    source_url: Optional[str] = Field(default=None, description="URL to the source")
    source_type: SourceType = Field(description="Type of source: form990, rating, news, etc.")
    quote: Optional[str] = Field(default=None, description="Exact quote from source if available")
    access_date: str = Field(default_factory=lambda: date.today().isoformat(), description="When source was accessed")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="Confidence in this citation (0-1)")


class CitationStats(BaseModel):
    """Statistics about citations in the narrative."""

    total_count: int = Field(description="Total number of citations")
    by_source_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count of citations by source type",
    )
    high_confidence_count: int = Field(default=0, description="Citations with confidence >= 0.8")
    unique_sources: int = Field(default=0, description="Number of unique source URLs")


class StrengthWithCitation(BaseModel):
    """A strength with citation support."""

    point: str = Field(description="Brief description of the strength")
    detail: str = Field(description="1-2 sentence elaboration with citation markers")
    citation_ids: list[str] = Field(description="List of citation IDs supporting this strength, e.g., ['[1]', '[2]']")


class CaseAgainstWithSources(BaseModel):
    """Risk analysis with source attribution.

    Follows Longview "Case Against" pattern - documents strongest
    objections to funding this charity.
    """

    summary: str = Field(description="1-2 sentence summary of key risks with citation markers")
    risk_factors: list[str] = Field(description="List of specific risks with citations")
    mitigation_notes: Optional[str] = Field(default=None, description="What charity is doing to address risks")
    citation_ids: list[str] = Field(description="Citation IDs supporting risk claims")


class PeerComparison(BaseModel):
    """Comparison with peer organizations."""

    peer_group: str = Field(description="Category of similar organizations")
    differentiator: str = Field(description="What distinguishes this charity from peers")
    similar_orgs: list[str] = Field(default_factory=list, description="Names of comparable organizations")
    citation_ids: list[str] = Field(default_factory=list, description="Citation IDs supporting comparison")


# ============================================================================
# NEW INVESTMENT MEMO SECTIONS (V3)
# ============================================================================


class DonorFitMatrix(BaseModel):
    """Best for donors who care about specific areas.

    Helps donors quickly assess if this charity matches their giving priorities.
    """

    zakat_status: str = Field(description="ZAKAT-ELIGIBLE or SADAQAH-ONLY")
    zakat_asnaf_served: list[str] = Field(
        default_factory=list, description="Which of the 8 asnaf categories this charity serves"
    )
    cause_area: str = Field(description="Primary cause area (HUMANITARIAN, EDUCATION, etc.)")
    geographic_focus: list[str] = Field(description="Countries or regions served")
    giving_style: str = Field(description="Direct service / Capacity building / Advocacy / Research")
    evidence_rigor: str = Field(description="Evidence grade A-H with brief explanation")
    tax_deductible: bool = Field(default=True, description="501(c)(3) tax-deductible status")
    citation_ids: list[str] = Field(default_factory=list)


class ImpactEvidence(BaseModel):
    """Theory of change and evidence quality.

    Educates donors on evidence-based giving while showing this charity's evidence level.
    """

    theory_of_change: str = Field(description="PUBLISHED / DOCUMENTED / IMPLICIT")
    theory_of_change_summary: Optional[str] = Field(
        default=None, description="Brief description of how the charity creates impact"
    )
    evidence_grade: str = Field(description="Grade A-H (GWWC scale)")
    evidence_grade_explanation: str = Field(description="What this grade means")
    rct_available: bool = Field(default=False, description="Whether RCT evidence exists")
    external_evaluations: list[str] = Field(
        default_factory=list, description="List of external evaluators (GiveWell, J-PAL, etc.)"
    )
    outcome_tracking_years: Optional[int] = Field(default=None, description="Years of outcome data tracked")
    why_evidence_matters: str = Field(
        default="Evidence helps ensure donations create real impact, not just good intentions.",
        description="Educational note for donors",
    )
    citation_ids: list[str] = Field(default_factory=list)


class YearlyFinancials(BaseModel):
    """Financial data for a single year."""

    year: int
    revenue: Optional[float] = None
    expenses: Optional[float] = None
    net_assets: Optional[float] = None


class FinancialDeepDive(BaseModel):
    """3-year financial trends and benchmarks.

    Shows financial health trajectory, not just a snapshot.
    """

    annual_revenue: Optional[float] = Field(default=None, description="Most recent annual revenue")
    program_expense_ratio: Optional[float] = Field(default=None, description="% to programs")
    admin_ratio: Optional[float] = Field(default=None, description="% to admin")
    fundraising_ratio: Optional[float] = Field(default=None, description="% to fundraising")
    reserves_months: Optional[float] = Field(default=None, description="Months of operating reserves")

    # Benchmarks
    peer_program_ratio_median: Optional[float] = Field(default=None)
    industry_program_ratio: float = Field(default=0.75)
    peer_count: int = Field(default=0, description="Number of peers in benchmark")

    # 3-year trends
    yearly_financials: list[YearlyFinancials] = Field(default_factory=list)
    revenue_cagr_3yr: Optional[float] = Field(default=None, description="3-year revenue CAGR %")

    # Health signals
    cn_financial_score: Optional[float] = Field(default=None, description="Charity Navigator financial score")

    citation_ids: list[str] = Field(default_factory=list)


class LongTermOutlook(BaseModel):
    """Room for funding and organizational trajectory.

    Helps donors think about sustained giving, not just one-time donations.
    """

    room_for_funding: str = Field(description="HIGH / MEDIUM / LOW / UNKNOWN")
    room_for_funding_explanation: str = Field(description="Why this charity can/cannot absorb more funding")

    founded_year: Optional[int] = Field(default=None)
    years_operating: Optional[int] = Field(default=None)
    maturity_stage: str = Field(description="Startup / Growth / Established / Institution")

    revenue_growth_3yr: Optional[float] = Field(default=None, description="3-year revenue CAGR %")

    strategic_priorities: list[str] = Field(
        default_factory=list, description="Key strategic goals from website/annual report"
    )

    citation_ids: list[str] = Field(default_factory=list)


class OrganizationalCapacity(BaseModel):
    """Team, governance, and operational capacity.

    Shows whether the charity can actually execute on its mission.
    """

    employees_count: Optional[int] = Field(default=None)
    volunteers_count: Optional[int] = Field(default=None)
    ceo_name: Optional[str] = Field(default=None)
    ceo_compensation: Optional[float] = Field(default=None)
    ceo_compensation_pct_revenue: Optional[float] = Field(default=None)

    board_size: Optional[int] = Field(default=None)
    independent_board_pct: Optional[float] = Field(default=None)
    has_conflict_policy: bool = Field(default=False)
    has_financial_audit: bool = Field(default=False)

    geographic_reach: Optional[str] = Field(default=None, description="X countries, Y programs")
    programs_count: Optional[int] = Field(default=None)

    # Operational efficiency signals
    payroll_to_revenue_pct: Optional[float] = Field(default=None)
    staff_per_million_revenue: Optional[float] = Field(default=None)

    citation_ids: list[str] = Field(default_factory=list)


class SimilarOrgEntry(BaseModel):
    """A similar organization for comparison."""

    name: str
    differentiator: str = Field(description="What makes them different (e.g., 'Larger scale')")


class DataConfidence(BaseModel):
    """Data quality and freshness assessment.

    Transparent about what we know and don't know.
    """

    form_990_tax_year: Optional[int] = Field(default=None)
    ratings_last_updated: Optional[str] = Field(default=None)
    website_last_crawled: Optional[str] = Field(default=None)

    known_gaps: list[str] = Field(default_factory=list, description="Missing data that would improve assessment")

    total_citations: int = Field(default=0)
    unique_sources: int = Field(default=0)
    confidence_score: int = Field(ge=0, le=100, default=50, description="0-100 based on data completeness")


class DimensionExplanation(BaseModel):
    """A single dimension explanation with citation support and improvement path."""

    explanation: str = Field(description="Plain English explanation with inline <cite> citation markers")
    improvement: str = Field(
        default="", description="What this charity can do to improve this dimension (1-2 sentences with citations)"
    )
    citation_ids: list[str] = Field(default_factory=list, description="Citation IDs used, e.g., ['[1]', '[2]']")


class DimensionExplanations(BaseModel):
    """Per-dimension explanations for the 3-dimension GMG Score."""

    credibility: DimensionExplanation = Field(
        description="Why donors can trust this charity (governance, transparency, accountability)"
    )
    impact: DimensionExplanation = Field(description="How efficiently and effectively this charity delivers programs")
    alignment: DimensionExplanation = Field(description="How well this charity fits Muslim donor priorities")


class AreaForImprovement(BaseModel):
    """An improvement area with citation support - matches baseline field name."""

    area: str = Field(description="Brief description of the improvement area")
    context: str = Field(description="1-2 sentence elaboration with citation markers")
    citation_ids: list[str] = Field(default_factory=list, description="Citation IDs supporting this")


class IdealDonorProfile(BaseModel):
    """Who should donate to this charity.

    Describes the DONOR PERSONA, not the charity's work.
    This answers "What kind of donor would be most aligned with this charity?"
    rather than "What does this charity do?"

    Examples of GOOD best_for_summary:
    - "Best for donors who prioritize rigorous evidence of impact and want to save the most lives per dollar"
    - "Best for donors who value Islamic institutional development and long-term community infrastructure"
    - "Best for donors who care about Palestinian humanitarian needs and want zakat-eligible direct aid"

    Examples of BAD best_for_summary (describes charity, not donor):
    - "Best for international humanitarian relief" (describes work, not donor)
    - "Best for education in South Asia" (describes programs, not donor persona)
    """

    best_for_summary: str = Field(description="1-2 sentence summary starting with 'Best for donors who...'")

    donor_motivations: list[str] = Field(
        description="What motivates donors who choose this charity (3-5 items). "
        "e.g., 'Want direct impact on poverty', 'Value evidence-based giving'"
    )

    giving_considerations: list[str] = Field(
        description="Key factors for donors to consider (2-4 items). "
        "e.g., 'Large organization with institutional stability', 'Programs in politically unstable regions'"
    )

    not_ideal_for: Optional[str] = Field(
        default=None,
        description="Honest note about who might prefer alternatives. e.g., 'Donors seeking hyperlocal US-only impact'",
    )

    citation_ids: list[str] = Field(default_factory=list)


class RichNarrativeV2(BaseModel):
    """Complete rich narrative with citation support.

    This schema extends baseline narratives with:
    - 500-800 word summary with inline citation markers
    - Detailed strength analysis with sources
    - Per-dimension score reasoning with citations
    - Case Against risk analysis
    - Complete citation registry

    Immutable fields (inherited from baseline, not regenerated):
    - headline
    - at_a_glance
    - amal_scores
    - zakat_guidance

    These are injected from the baseline evaluation after generation
    to ensure consistency.
    """

    # Immutable from baseline (injected post-generation)
    headline: str = Field(max_length=250, description="Headline from baseline (immutable)")
    at_a_glance: AtAGlance = Field(description="Quick facts from baseline (immutable)")
    amal_scores: AmalScores = Field(description="AMAL scores from baseline (immutable)")
    zakat_guidance: ZakatGuidance = Field(description="Zakat guidance from baseline (immutable)")

    # Enhanced narrative with citations (LLM generates these)
    summary: str = Field(
        min_length=400,
        max_length=1500,
        description="500-800 word narrative summary with inline [1], [2] citation markers",
    )

    strengths: list[StrengthWithCitation] = Field(
        min_length=3,
        description="At least 3 strengths with citation support",
    )
    strengths_deep_dive: list[str] = Field(
        default_factory=list,
        description="1-2 paragraphs of detailed strength analysis with citations",
    )

    # Aligned with baseline field names (rich adds citations)
    areas_for_improvement: list[AreaForImprovement] = Field(
        default_factory=list,
        description="Areas for improvement with context and citations (matches baseline field name)",
    )

    amal_score_rationale: str = Field(
        description="1-2 sentences explaining the overall score with inline [n] citation markers",
    )

    dimension_explanations: DimensionExplanations = Field(
        description="Per-dimension explanations matching baseline, with citations",
    )

    case_against: CaseAgainstWithSources = Field(
        description="Longview-style risk analysis with sources",
    )

    peer_comparison: Optional[PeerComparison] = Field(
        default=None,
        description="Comparison with similar organizations (optional)",
    )

    # NEW V3 Investment Memo Sections
    donor_fit_matrix: Optional[DonorFitMatrix] = Field(
        default=None,
        description="Charity characteristics (cause area, geographic focus, evidence rigor)",
    )
    ideal_donor_profile: Optional[IdealDonorProfile] = Field(
        default=None,
        description="Donor-centric 'Best For' - describes who should donate, not what charity does",
    )
    impact_evidence: Optional[ImpactEvidence] = Field(
        default=None,
        description="Theory of change and evidence quality",
    )
    financial_deep_dive: Optional[FinancialDeepDive] = Field(
        default=None,
        description="3-year financial trends and benchmarks",
    )
    long_term_outlook: Optional[LongTermOutlook] = Field(
        default=None,
        description="Room for funding and trajectory",
    )
    organizational_capacity: Optional[OrganizationalCapacity] = Field(
        default=None,
        description="Team, governance, and capacity",
    )
    similar_organizations: list[SimilarOrgEntry] = Field(
        default_factory=list,
        description="Similar orgs with differentiators",
    )
    data_confidence: Optional[DataConfidence] = Field(
        default=None,
        description="Data quality and freshness assessment",
    )

    # Citation registry
    all_citations: list[Citation] = Field(
        min_length=10,
        description="All citations referenced in narrative (target 10-20)",
    )
    citation_stats: CitationStats = Field(
        description="Summary statistics about citations",
    )

    # Metadata
    confidence: Confidence = Field(description="Data confidence assessment")
    generated_at: str = Field(
        default_factory=lambda: date.today().isoformat(),
        description="When this narrative was generated",
    )

    @classmethod
    def get_minimum_citations(cls) -> int:
        """Return minimum required citations."""
        return 10

    @classmethod
    def get_target_citations(cls) -> int:
        """Return target number of citations."""
        return 15

    def validate_citation_markers(self) -> list[str]:
        """Validate that all citation markers in text exist in registry.

        Returns list of validation errors (empty if valid).
        """
        errors = []
        citation_ids = {c.id for c in self.all_citations}

        # Check summary
        import re

        markers_in_summary = set(re.findall(r"\[\d+\]", self.summary))
        for marker in markers_in_summary:
            if marker not in citation_ids:
                errors.append(f"Summary references {marker} but not in citation registry")

        # Check strengths
        for s in self.strengths:
            for cid in s.citation_ids:
                if cid not in citation_ids:
                    errors.append(f"Strength references {cid} but not in citation registry")

        return errors


# Convenience type alias
RichNarrative = RichNarrativeV2

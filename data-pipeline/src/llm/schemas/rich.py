"""Pydantic schema for Rich Narrative.

Rich narratives are comprehensive (~500-800 words) evaluations generated for
curated charities (50-70 organizations). They provide in-depth analysis:
- Full narrative sections (mission, operations, differentiation)
- Detailed strengths with confidence-scored evidence
- Improvement areas and risk factors
- Donor decision support with giving scenarios
- Comprehensive zakat guidance with scholarly considerations
- Comparative context with peer organizations
"""

from typing import Optional

from pydantic import BaseModel, Field

from .baseline import AmalScores
from .common import AtAGlance, Confidence, Strength, ZakatGuidance


class NarrativeSections(BaseModel):
    """Main narrative content sections.

    These form the body of the rich narrative, providing detailed
    analysis in three key areas.
    """

    mission_and_impact: str = Field(description="2-3 paragraphs on mission, programs, and measurable impact")
    operational_excellence: str = Field(description="1-2 paragraphs on governance, financial health, efficiency")
    what_sets_them_apart: str = Field(description="1-2 paragraphs on unique approach or competitive advantage")


class ImprovementArea(BaseModel):
    """An area where the charity could improve.

    Presented constructively to help donors understand limitations
    without being overly critical.
    """

    point: str = Field(description="The area needing improvement")
    constructive_note: str = Field(description="Constructive framing of the issue")


class RiskFactor(BaseModel):
    """A risk factor and how the charity mitigates it."""

    risk: str = Field(description="Description of the risk")
    mitigation: str = Field(description="How the charity addresses this risk")


class GivingScenarios(BaseModel):
    """Example giving scenarios grounded in real cost data.

    Helps donors understand the tangible impact of different
    donation amounts based on actual program costs.
    """

    currency_code: str = Field(default="USD", description="Currency for amounts")
    cost_per_beneficiary: Optional[str] = Field(
        default=None, description="Calculated from program_expenses / annual_beneficiaries with source citation"
    )
    small_gift: str = Field(
        description="Impact of $25-50 gift, grounded in cost_per_beneficiary or specific program costs"
    )
    medium_gift: str = Field(description="Impact of $100-500 gift, grounded in real costs")
    large_gift: str = Field(description="Impact of $1000+ gift, grounded in real costs")
    data_source: Optional[str] = Field(
        default=None, description="Where cost data came from (e.g., 'Form 990 2023', 'Annual Report 2024')"
    )
    is_estimate: bool = Field(
        default=True, description="True if extrapolated from limited data, false if directly from source"
    )


class DonorDecisionSupport(BaseModel):
    """Information to help donors decide if this charity is right for them."""

    ideal_for: str = Field(
        description="Types of donors or causes this charity is ideal for, based on programs and mission"
    )
    less_ideal_for: str = Field(description="Situations where other charities might be better fits")
    giving_scenarios: GivingScenarios = Field(
        description="Example impact at different giving levels, grounded in real costs"
    )
    questions_to_ask: list[str] = Field(
        description="Evidence-based giving questions aligned with AMAL scores or improvement areas"
    )


class ComparativeContext(BaseModel):
    """How this charity compares to peers."""

    peer_group: str = Field(description="Category of similar organizations")
    differentiator: str = Field(description="What distinguishes this charity from peers")
    similar_orgs_to_consider: list[str] = Field(description="Names of similar organizations donors might also consider")


class RichNarrative(BaseModel):
    """Complete rich narrative schema.

    This is the structured output format for LLM generation of
    comprehensive charity evaluations.

    Constraints:
    - headline: max 250 characters
    - strengths: minimum 3 items with evidence
    - All narrative sections required
    """

    headline: str = Field(max_length=250, description="Compelling headline about the charity")
    at_a_glance: AtAGlance = Field(description="Quick facts section")
    narrative_sections: NarrativeSections = Field(description="Main narrative content")
    strengths: list[Strength] = Field(min_length=3, description="At least 3 key strengths with evidence")
    improvement_areas: list[ImprovementArea] = Field(
        default_factory=list, description="Areas where the charity could improve"
    )
    risk_factors: list[RiskFactor] = Field(default_factory=list, description="Risk factors and mitigations")
    transparency_gaps: list[str] = Field(default_factory=list, description="Areas where transparency is lacking")
    donor_decision_support: DonorDecisionSupport = Field(description="Information to help donors decide")
    zakat_guidance: ZakatGuidance = Field(description="Comprehensive zakat eligibility guidance")
    amal_scores: AmalScores = Field(description="Amal evaluation scores across key dimensions")
    comparative_context: ComparativeContext = Field(description="Comparison with peer organizations")
    confidence: Confidence = Field(description="Data confidence assessment")

    @classmethod
    def get_field_count(cls) -> int:
        """Return the total number of countable fields for density calculation.

        Rich narrative fields (~58 total):
        - headline: 1
        - at_a_glance: 8 (includes signature_achievement)
        - narrative_sections: 3
        - strengths: 3 (counting min required)
        - improvement_areas: counted dynamically
        - risk_factors: counted dynamically
        - transparency_gaps: 1 (list exists)
        - donor_decision_support: 7 (ideal_for, less_ideal_for, 3 scenarios, questions)
        - zakat_guidance: 5
        - amal_scores: 7 (overall, impact, financial, transparency, governance, zakat_eligible, rationale)
        - comparative_context: 3
        - confidence: 6
        - evidence_quality: 4 (grade, methodology_type, sources, rationale)
        - third_party_verification: 5 (verified, sources, verification_type, last_verified_year, tier)
        - cost_benchmark: 7 (cause_area, cost_per_beneficiary, benchmark_name, benchmark_range, comparison, ratio, data_source)
        """
        return 58

"""
Pydantic schemas for LLM extraction responses.

These schemas validate LLM outputs for different page types using instructor library.
Each schema corresponds to a prompt in config/page_prompts.yaml.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class HomepageResponse(BaseModel):
    """LLM response schema for homepage extraction."""

    mission: Optional[str] = Field(None, max_length=2000, description="The charity's mission statement")
    vision: Optional[str] = Field(None, max_length=2000, description="Vision statement if present")
    target_populations: Optional[list[str]] = Field(
        default_factory=list, max_length=10, description="High-level beneficiary populations"
    )
    geographic_coverage: Optional[list[str]] = Field(
        default_factory=list, max_length=50, description="Geographic regions served"
    )
    founded_year: Optional[int] = Field(None, ge=1800, le=2100, description="Year the charity was founded")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mission": "To provide clean water and sanitation to communities in need across Africa",
                "vision": "A world where everyone has access to safe drinking water",
                "target_populations": ["Rural communities", "Children", "Women"],
                "geographic_coverage": ["Kenya", "Uganda", "Tanzania"],
                "founded_year": 2005,
            }
        }
    )


class AboutResponse(BaseModel):
    """LLM response schema for about/mission page extraction."""

    mission: Optional[str] = Field(None, max_length=2000, description="The charity's mission statement")
    vision: Optional[str] = Field(None, max_length=2000, description="Vision statement")
    theory_of_change: Optional[str] = Field(
        None,
        max_length=3000,
        description="How the organization believes their work creates lasting impact (logic model, intervention theory)",
    )
    values: Optional[list[str]] = Field(default_factory=list, max_length=10, description="Core values")
    target_populations: Optional[list[str]] = Field(
        default_factory=list, max_length=10, description="Populations served"
    )
    geographic_coverage: Optional[list[str]] = Field(
        default_factory=list, max_length=50, description="Geographic coverage"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mission": "To provide clean water and sanitation to communities in need",
                "vision": "A world where everyone has access to safe drinking water",
                "theory_of_change": "By providing clean water access, we reduce waterborne diseases, enabling children to attend school and adults to work, breaking the cycle of poverty.",
                "values": ["Transparency", "Sustainability", "Community empowerment"],
                "target_populations": ["Rural communities", "Children"],
                "geographic_coverage": ["Kenya", "Uganda"],
            }
        }
    )


class ProgramsResponse(BaseModel):
    """LLM response schema for programs page extraction."""

    programs: Optional[list[str]] = Field(
        default_factory=list,
        min_length=1,
        max_length=20,
        description="List of program descriptions (20-500 chars each)",
    )
    target_populations: Optional[list[str]] = Field(
        default_factory=list, max_length=10, description="Populations served by programs"
    )
    geographic_coverage: Optional[list[str]] = Field(
        default_factory=list, max_length=50, description="Geographic coverage of programs"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "programs": [
                    "Clean Water Wells: Drilling and maintaining water wells in rural villages",
                    "Sanitation Education: Teaching hygiene and sanitation practices in schools",
                ],
                "target_populations": ["Rural communities", "School children"],
                "geographic_coverage": ["Kenya", "Uganda"],
            }
        }
    )


class OutcomeSummary(BaseModel):
    """Structured outcomes data."""

    total_beneficiaries: Optional[int] = Field(None, description="Total number of beneficiaries served")
    key_outcomes: Optional[list[str]] = Field(
        default_factory=list, max_length=20, description="Key measurable outcomes achieved"
    )
    cost_per_beneficiary: Optional[float] = Field(None, description="Cost per beneficiary if available")
    methodology: Optional[str] = Field(None, max_length=1000, description="How outcomes are measured")


class ImpactResponse(BaseModel):
    """LLM response schema for impact/results page extraction."""

    impact_metrics: Optional[dict[str, str | int | float | list[str] | dict]] = Field(
        default_factory=dict, description="Key impact metrics and statistics (flexible structure, allows nested dicts)"
    )
    outcomes_summary: Optional[OutcomeSummary] = Field(
        None, description="Structured outcomes data with beneficiary counts and key results"
    )
    theory_of_change: Optional[str] = Field(
        None, max_length=3000, description="How the organization believes their work creates lasting impact"
    )
    beneficiaries: Optional[str] = Field(None, max_length=1000, description="Description of beneficiaries served")
    geographic_coverage: Optional[list[str]] = Field(
        default_factory=list, max_length=50, description="Geographic reach of impact"
    )
    additional_info: Optional[str] = Field(None, max_length=2000, description="Additional impact information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "impact_metrics": {
                    "people_served": 50000,
                    "wells_built": 125,
                    "communities_reached": 45,
                    "lives_saved": 1200,
                },
                "outcomes_summary": {
                    "total_beneficiaries": 50000,
                    "key_outcomes": [
                        "80% reduction in waterborne diseases",
                        "45% increase in school attendance",
                        "30% improvement in household income",
                    ],
                    "cost_per_beneficiary": 25.50,
                    "methodology": "Annual household surveys and health clinic data",
                },
                "theory_of_change": "By providing clean water, we reduce disease burden, enabling education and economic participation.",
                "beneficiaries": "Over 50,000 people in rural communities now have access to clean water",
                "geographic_coverage": ["Kenya", "Uganda", "Tanzania"],
                "additional_info": "Our programs have reduced waterborne diseases by 80% in target communities",
            }
        }
    )


class DonateResponse(BaseModel):
    """LLM response schema for donation page extraction."""

    tax_deductible: Optional[bool] = Field(None, description="Whether donations are tax-deductible")
    donation_methods: Optional[list[str]] = Field(
        default_factory=list, max_length=10, description="Accepted donation methods"
    )
    donate_url: Optional[HttpUrl] = Field(None, description="Primary donation URL")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tax_deductible": True,
                "donation_methods": ["credit_card", "paypal", "bank_transfer", "check"],
                "donate_url": "https://charity.org/donate",
            }
        }
    )


class LeadershipMember(BaseModel):
    """Schema for a single leadership team member."""

    name: str = Field(..., min_length=2, max_length=100, description="Person's name")
    title: str = Field(..., min_length=2, max_length=100, description="Job title or position")
    role: Optional[str] = Field(None, max_length=500, description="Description of their role")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Jane Smith",
                "title": "Executive Director",
                "role": "Oversees all program operations and strategic planning",
            }
        }
    )


class ContactResponse(BaseModel):
    """LLM response schema for contact/team/leadership page extraction."""

    leadership: list[LeadershipMember] = Field(
        default_factory=list, max_length=50, description="Leadership team members"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leadership": [
                    {"name": "Jane Smith", "title": "Executive Director", "role": "Oversees all program operations"},
                    {"name": "John Doe", "title": "Director of Programs", "role": "Manages all field programs"},
                ]
            }
        }
    )


class ZakatResponse(BaseModel):
    """LLM response schema for zakat eligibility page extraction."""

    zakat_eligible_programs: Optional[list[str]] = Field(
        default_factory=list,
        max_length=20,
        description="Programs the charity claims are zakat-eligible",
    )
    asnaf_served: Optional[list[str]] = Field(
        default_factory=list,
        max_length=8,
        description="Which of the 8 zakat recipient categories (asnaf) are served",
    )
    scholarly_endorsements: Optional[list[str]] = Field(
        default_factory=list,
        max_length=10,
        description="Scholars, institutions, or Islamic bodies endorsing zakat eligibility",
    )
    zakat_distribution_details: Optional[str] = Field(
        None,
        max_length=2000,
        description="How the charity handles, tracks, or distributes zakat funds",
    )
    zakat_policy_url: Optional[str] = Field(
        None,
        max_length=500,
        description="Direct URL to the charity's zakat policy or eligibility page",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zakat_eligible_programs": [
                    "Emergency Food Assistance",
                    "Refugee Resettlement Support",
                    "Orphan Sponsorship Program",
                ],
                "asnaf_served": ["Fuqara (the poor)", "Masakin (the needy)", "Gharimin (those in debt)"],
                "scholarly_endorsements": [
                    "AMJA (Assembly of Muslim Jurists of America)",
                    "Dr. Yasir Qadhi",
                ],
                "zakat_distribution_details": "100% of zakat donations go directly to eligible recipients. We maintain separate accounting for zakat funds and provide donors with detailed reports.",
                "zakat_policy_url": "https://charity.org/zakat-policy",
            }
        }
    )


class PolicyInfluenceMetrics(BaseModel):
    """Schema for policy influence data (for RESEARCH_POLICY track organizations).

    Used to validate and store policy influence data extracted from charity websites.
    This data is used in the RESEARCH_POLICY evidence scoring rubric.
    """

    publications: list[str] | None = Field(
        default=None,
        description="Publications - reports, white papers, research papers, policy briefs",
    )
    publications_count: int | None = Field(
        default=None,
        ge=0,
        description="Total count of publications",
    )
    peer_reviewed_count: int | None = Field(
        default=None,
        ge=0,
        description="Count of peer-reviewed academic publications",
    )
    media_mentions: list[str] | None = Field(
        default=None,
        description="Significant media coverage - outlet names and topics",
    )
    policy_wins: list[str] | None = Field(
        default=None,
        description="Policy changes, legislation passed, or regulations influenced by the organization",
    )
    government_citations: list[str] | None = Field(
        default=None,
        description="Government/institutional citations - testimony, agency briefs, court amicus briefs",
    )
    testimony_count: int | None = Field(
        default=None,
        ge=0,
        description="Count of congressional or legislative testimony appearances",
    )
    academic_citations: int | None = Field(
        default=None,
        ge=0,
        description="Count of academic citations if mentioned on site",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "publications": [
                    "Report: The State of Muslim Civil Rights 2024",
                    "Policy Brief: Recommendations for Countering Islamophobia",
                ],
                "publications_count": 15,
                "peer_reviewed_count": 3,
                "media_mentions": [
                    "NYT op-ed on civil rights",
                    "NPR interview on religious discrimination",
                ],
                "policy_wins": [
                    "Contributed to passage of SB-234 protecting religious expression",
                    "Helped draft DOJ guidance on religious discrimination",
                ],
                "government_citations": [
                    "Testified before Senate Judiciary Committee on hate crimes",
                    "Cited in EEOC annual report on workplace discrimination",
                ],
                "testimony_count": 5,
                "academic_citations": 42,
            }
        }
    )


# Map page types to their corresponding response schemas
PAGE_TYPE_SCHEMAS = {
    "homepage": HomepageResponse,
    "about": AboutResponse,
    "programs": ProgramsResponse,
    "impact": ImpactResponse,
    "donate": DonateResponse,
    "contact": ContactResponse,
    "zakat": ZakatResponse,
}

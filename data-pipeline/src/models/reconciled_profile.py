"""
Pydantic models for reconciled charity profiles.

These models define the structure of reconciled data consolidated from multiple
sources into a single authoritative charity profile.
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConflictType(str, Enum):
    """Types of data conflicts between sources."""

    NUMERIC_MISMATCH = "numeric_mismatch"  # Numbers differ significantly
    TEXT_DIFFERENCE = "text_difference"  # Text content differs
    MISSING_IN_SOME = "missing_in_some"  # Some sources have data, others don't
    CATEGORICAL_MISMATCH = "categorical_mismatch"  # Different categories/types


class SourceAttribution(BaseModel):
    """Tracks which source provided a specific field value."""

    source_name: str = Field(..., description="Data source name (e.g., 'ProPublica', 'Charity Navigator')")
    field_name: str = Field(..., description="Name of the field this attribution applies to")
    value: Any = Field(..., description="The actual value from this source")
    timestamp: datetime = Field(..., description="When this data was collected from the source")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_name": "ProPublica",
                "field_name": "total_revenue",
                "value": 1500000.0,
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }
    )


class ConflictRecord(BaseModel):
    """Records a data conflict between sources for audit purposes."""

    field_name: str = Field(..., description="Field that has conflicting values")
    source_values: dict[str, Any] = Field(..., description="Map of source_name -> conflicting_value")
    selected_source: str = Field(..., description="Which source was ultimately chosen")
    selected_value: Any = Field(None, description="The value that was selected")
    selection_reason: str = Field(..., description="Why this source was selected over others")
    conflict_type: ConflictType = Field(
        default=ConflictType.TEXT_DIFFERENCE, description="Type of conflict"
    )
    flagged_for_review: bool = Field(default=False, description="Whether this needs manual review")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When conflict was detected")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field_name": "mission",
                "source_values": {
                    "charity_website": "Providing clean water to rural communities",
                    "candid": "Clean water access",
                },
                "selected_source": "charity_website",
                "selected_value": "Providing clean water to rural communities",
                "selection_reason": "Website source more complete (50 chars vs 18 chars)",
                "conflict_type": "text_difference",
                "flagged_for_review": False,
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }
    )


class ReconciledCharityProfile(BaseModel):
    """
    Authoritative consolidated charity profile from all sources.

    This model represents the final reconciled data that will be stored in the
    charities table and exported to the frontend.
    """

    # Core identification
    ein: str = Field(..., description="IRS Employer Identification Number (primary key)")
    name: str = Field(..., description="Official charity name")

    # Mission and programs
    mission: Optional[str] = Field(None, description="Mission statement")
    category: Optional[str] = Field(None, description="Charity category/cause area")
    programs: Optional[List[str]] = Field(None, description="List of program descriptions")
    populations_served: Optional[List[str]] = Field(None, description="Beneficiary populations")
    geographic_coverage: Optional[List[str]] = Field(None, description="Geographic areas served")

    # Contact information
    website: Optional[str] = Field(None, description="Primary website URL")

    # Financial metrics (from IRS 990)
    total_revenue: Optional[float] = Field(None, description="Total annual revenue")
    program_expenses: Optional[float] = Field(None, description="Program service expenses")
    admin_expenses: Optional[float] = Field(None, description="Administrative expenses")
    fundraising_expenses: Optional[float] = Field(None, description="Fundraising expenses")
    program_expense_ratio: Optional[float] = Field(None, description="Program expense ratio (0-1)")
    fiscal_year_end: Optional[str] = Field(None, description="Fiscal year end date")

    # Ratings and scores
    overall_score: Optional[float] = Field(None, description="Charity Navigator overall score (0-100)")
    financial_score: Optional[float] = Field(None, description="Charity Navigator financial score (0-100)")
    accountability_score: Optional[float] = Field(None, description="Charity Navigator accountability score (0-100)")
    transparency_score: Optional[float] = Field(None, description="Transparency score (0-100)")
    rating_timestamp: Optional[datetime] = Field(None, description="When ratings were last updated")

    # Effectiveness (from evaluations)
    effectiveness_score: Optional[float] = Field(None, description="Custom effectiveness score")
    cost_effectiveness_ratio: Optional[float] = Field(None, description="Cost-effectiveness metric")

    # Zakaat classification
    is_muslim_charity: Optional[bool] = Field(None, description="Whether charity has Muslim focus")
    zakaat_eligible: Optional[bool] = Field(None, description="Eligible for Zakaat donations")
    zakaat_criteria_met: Optional[List[str]] = Field(None, description="Which Zakaat criteria are met")

    # Governance (from multiple sources)
    board_size: Optional[int] = Field(None, description="Number of board members")
    independent_board_members: Optional[int] = Field(None, description="Number of independent board members")

    # Reconciliation metadata
    source_attribution: dict[str, SourceAttribution] = Field(
        default_factory=dict, description="Map of field_name -> source attribution"
    )
    reconciliation_conflicts: List[ConflictRecord] = Field(
        default_factory=list, description="List of conflicts detected during reconciliation"
    )
    last_reconciliation: Optional[datetime] = Field(None, description="When reconciliation last ran")

    # General metadata
    data_source: Optional[str] = Field("reconciled", description="Data source identifier")
    last_updated: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ein": "12-3456789",
                "name": "Example Charity Foundation",
                "mission": "Providing clean water to communities in need",
                "total_revenue": 1500000.0,
                "program_expense_ratio": 0.85,
                "overall_score": 95.0,
                "source_attribution": {
                    "total_revenue": {
                        "source_name": "ProPublica",
                        "field_name": "total_revenue",
                        "value": 1500000.0,
                        "timestamp": "2024-01-15T10:30:00Z",
                    }
                },
            }
        }
    )


# ============================================================================
# CHARITY DATA BUNDLE - Aggregated data from all sources
# ============================================================================


class RatingEntry(BaseModel):
    """A single rating from a rating source."""

    source_name: str = Field(..., description="Rating source (e.g., 'Charity Navigator')")
    source_url: Optional[str] = Field(None, description="URL to the rating")
    rating_value: Optional[str] = Field(None, description="Rating value")
    rating_max: Optional[str] = Field(None, description="Maximum possible rating")
    rating_type: Optional[str] = Field(None, description="Type: stars, percentage, letter_grade, seal")
    confidence: float = Field(default=0.8, description="Confidence in this rating")


class EvidenceEntry(BaseModel):
    """A piece of evidence about charity effectiveness."""

    source_name: str = Field(..., description="Source of evidence")
    source_url: Optional[str] = Field(None, description="URL to the evidence")
    evidence_type: str = Field(
        default="anecdotal",
        description="Type: rct, quasi_experimental, observational, third_party_eval, self_reported, anecdotal",
    )
    summary: Optional[str] = Field(None, description="Summary of findings")
    evaluator: Optional[str] = Field(None, description="Organization that conducted evaluation")
    year: Optional[int] = Field(None, description="Year of study")
    confidence: float = Field(default=0.6, description="Confidence in this evidence")


class ReputationEntry(BaseModel):
    """A reputation data point (news, award, controversy)."""

    source_name: str = Field(..., description="Source of information")
    source_url: Optional[str] = Field(None, description="URL to the source")
    headline: Optional[str] = Field(None, description="Headline or title")
    summary: Optional[str] = Field(None, description="Summary of the item")
    sentiment: str = Field(default="neutral", description="Sentiment: positive, negative, neutral")
    date: Optional[str] = Field(None, description="Date of the item")
    resolved: Optional[bool] = Field(None, description="If negative, was it resolved?")
    confidence: float = Field(default=0.7, description="Confidence in this data")


class ProfileEntry(BaseModel):
    """Profile information from a source."""

    source_name: str = Field(..., description="Source of profile data")
    source_url: Optional[str] = Field(None, description="URL to the source")
    mission_statement: Optional[str] = Field(None, description="Mission statement")
    programs: List[str] = Field(default_factory=list, description="Programs/services")
    geographic_scope: Optional[str] = Field(None, description="Geographic areas served")
    year_founded: Optional[int] = Field(None, description="Year founded")
    leadership: List[str] = Field(default_factory=list, description="Leadership/executives")


class FinancialsBundle(BaseModel):
    """Financial data bundle."""

    total_revenue: Optional[float] = Field(None, description="Total annual revenue")
    total_expenses: Optional[float] = Field(None, description="Total annual expenses")
    total_assets: Optional[float] = Field(None, description="Total assets")
    total_liabilities: Optional[float] = Field(None, description="Total liabilities")
    net_assets: Optional[float] = Field(None, description="Net assets")
    program_expenses: Optional[float] = Field(None, description="Program expenses")
    admin_expenses: Optional[float] = Field(None, description="Administrative expenses")
    fundraising_expenses: Optional[float] = Field(None, description="Fundraising expenses")
    program_expense_ratio: Optional[float] = Field(None, description="Program expense ratio (0-1)")
    fiscal_year: Optional[int] = Field(None, description="Fiscal year")
    source: str = Field(default="unknown", description="Primary source of financial data")


class LegalStatus(BaseModel):
    """Legal/IRS status information."""

    ein: str = Field(..., description="EIN")
    name: str = Field(..., description="Legal name")
    ntee_code: Optional[str] = Field(None, description="NTEE classification code")
    subsection_code: Optional[str] = Field(None, description="IRS subsection (e.g., 501c3)")
    ruling_date: Optional[str] = Field(None, description="IRS ruling date")
    deductibility_status: Optional[str] = Field(None, description="Tax deductibility status")
    foundation_type: Optional[str] = Field(None, description="Foundation classification")


class CharityDataBundle(BaseModel):
    """
    Aggregated charity data from all discovery sources.

    This is the output of the reconciliation engine, combining data from:
    - Form 990 (via ProPublica)
    - Charity Navigator, BBB, GuideStar ratings
    - Agent discoveries (profile, evidence, reputation)
    - Website scraping
    """

    # Identification
    charity_ein: str = Field(..., description="EIN (primary key)")
    charity_name: str = Field(..., description="Charity name")

    # Core data bundles
    financials: Optional[FinancialsBundle] = Field(None, description="Financial data")
    legal_status: Optional[LegalStatus] = Field(None, description="Legal/IRS status")

    # Discovered data (lists from agents)
    ratings: List[RatingEntry] = Field(default_factory=list, description="All ratings discovered")
    profiles: List[ProfileEntry] = Field(default_factory=list, description="Profile data from sources")
    evidence: List[EvidenceEntry] = Field(default_factory=list, description="Evidence of effectiveness")
    reputation: List[ReputationEntry] = Field(default_factory=list, description="News/awards/controversies")

    # Primary/canonical values (selected from sources)
    primary_mission: Optional[str] = Field(None, description="Selected mission statement")
    primary_programs: List[str] = Field(default_factory=list, description="Selected programs list")
    primary_rating: Optional[RatingEntry] = Field(None, description="Primary rating (highest confidence)")

    # Discovery metadata
    sources_discovered: List[str] = Field(default_factory=list, description="All sources that provided data")
    conflicts: List[ConflictRecord] = Field(default_factory=list, description="Conflicts detected")
    coverage_score: float = Field(default=0.0, description="Proportion of fields populated (0-1)")

    # Timestamps
    reconciled_at: datetime = Field(default_factory=datetime.utcnow, description="When reconciliation ran")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "charity_ein": "95-4453134",
                "charity_name": "Islamic Relief USA",
                "financials": {"total_revenue": 133000000, "program_expense_ratio": 0.85},
                "ratings": [
                    {"source_name": "Charity Navigator", "rating_value": "4", "rating_type": "stars"}
                ],
                "coverage_score": 0.75,
            }
        }
    )

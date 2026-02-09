"""
Pydantic validator for Candid profile data.

Validates data extracted from Candid profiles against the schema.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.validators.base_validator import normalize_ein


class CandidProfile(BaseModel):
    """
    Candid charity profile data.

    This model validates data extracted from FREE Candid profiles using BeautifulSoup.
    Note: Many fields require Candid Pro subscription and are not available on free profiles.
    """

    model_config = ConfigDict(extra="forbid")

    # Required fields (per spec: use 'name' not 'organization_name')
    name: str = Field(..., min_length=1)
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")

    # Core information
    tagline: Optional[str] = None  # From H4 tagline or meta description
    aka_names: List[str] = Field(default_factory=list)  # Also known as names
    mission: Optional[str] = None
    vision: Optional[str] = None  # Often not available
    strategic_goals: Optional[str] = None  # Often not available

    # Programs and impact
    programs: List[str] = Field(default_factory=list)
    program_details: List[Dict[str, Any]] = Field(default_factory=list)  # Program name, description, populations served
    outcomes: List[str] = Field(default_factory=list)
    populations_served: List[str] = Field(default_factory=list)
    geographic_coverage: List[str] = Field(default_factory=list)  # Per spec: was 'areas_served'
    goals_strategy_text: Optional[str] = None

    # Results and metrics (from "Our results" section)
    metrics: List[Dict[str, Any]] = Field(default_factory=list)  # Metric name, years, values, type, direction

    # Charting impact / Goals & Strategy (detailed)
    charting_impact_goal: Optional[str] = None  # What org aims to accomplish
    charting_impact_strategies: Optional[str] = None  # Key strategies
    charting_impact_capabilities: Optional[str] = None  # Organization capabilities
    charting_impact_progress: Optional[str] = None  # What accomplished and what's next

    # Leadership (limited on free profiles)
    ceo_name: Optional[str] = None  # Sometimes available
    board_members: List[Dict[str, str]] = Field(default_factory=list)  # Name, title/role, affiliation
    board_size: Optional[int] = None  # Total number of board members

    # Contact information (limited on free profiles)
    address: Optional[str] = None
    payment_address: Optional[str] = None  # Separate payment/PO Box address
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None  # May require Pro subscription
    email: Optional[str] = None  # May require Pro subscription

    # Social media (per spec: consolidated into single object)
    social_media: Dict[str, str] = Field(
        default_factory=dict,
        description="Social media links: {facebook, twitter, linkedin, youtube, instagram}"
    )

    # Organization details (per spec: use 'irs_ruling_year' not 'ruling_year')
    irs_ruling_year: Optional[int] = Field(None, ge=1800, le=2100)  # IRS tax-exempt ruling year
    formerly_known_as: List[str] = Field(default_factory=list)  # Previous organization names
    ntee_code: Optional[str] = None
    ntee_description: Optional[str] = None  # Human-readable NTEE description
    irs_filing_requirement: Optional[str] = (
        None  # e.g., "This organization is required to file an IRS Form 990 or 990-EZ."
    )
    candid_seal: Optional[str] = None  # Candid transparency seal: platinum, gold, silver, bronze
    candid_url: Optional[str] = None  # Direct URL to app.candid.org profile (user-facing)

    # Feedback practices ("How We Listen" section - Platinum profiles)
    feedback_practices: List[str] = Field(default_factory=list)  # What feedback practices org uses
    feedback_usage: Optional[str] = None  # How org uses feedback from people served
    feedback_collection: Optional[str] = None  # How org routinely collects feedback

    # Evaluation documents
    evaluation_documents: List[Dict[str, str]] = Field(default_factory=list)  # Links to evaluation reports

    # Additional metadata
    logo_url: Optional[str] = None  # Organization logo URL
    has_photos: Optional[bool] = None  # Whether organization has uploaded photos
    has_videos: Optional[bool] = None  # Whether organization has uploaded videos

    # Derived evidence fields (computed during HTML parsing, per spec)
    metrics_count: Optional[int] = Field(None, ge=0, description="Count of outcome metrics reported")
    max_years_tracked: Optional[int] = Field(None, ge=0, description="Max year span in any single metric")
    has_charting_impact: Optional[bool] = Field(None, description="Whether Charting Impact section is present")

    @field_validator("ein")
    @classmethod
    def validate_ein_format(cls, v: str) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        return normalize_ein(v)

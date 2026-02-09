"""
Pydantic validator for CauseIQ profile data.

Validates data extracted from CauseIQ nonprofit profiles against the schema.
CauseIQ provides detailed program descriptions, grantmaking data, and financial metrics.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.validators.base_validator import normalize_ein


class CauseIQProfile(BaseModel):
    """
    CauseIQ nonprofit profile data.

    This model validates data extracted from CauseIQ profiles using BeautifulSoup.
    CauseIQ provides uniquely detailed program narratives with beneficiary counts,
    grantmaking data (grants made and received), and financial information.
    """

    model_config = ConfigDict(extra="forbid")

    # Required fields
    organization_name: str = Field(..., min_length=1)
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")

    # Core information
    mission: Optional[str] = None
    description: Optional[str] = None
    tagline: Optional[str] = None

    # Programs and impact (HIGH VALUE - most detailed source)
    programs: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # name, description, beneficiaries, locations, outcomes
    program_areas: List[str] = Field(default_factory=list)  # Simple list of program area names
    populations_served: List[str] = Field(default_factory=list)
    geographic_coverage: List[str] = Field(default_factory=list)  # Countries, states, regions served
    total_beneficiaries: Optional[int] = Field(None, ge=0)  # Aggregate beneficiary count if available

    # Grantmaking data (UNIQUE TO CAUSEIQ)
    grants_made: List[Dict[str, Any]] = Field(default_factory=list)  # grantee_name, amount, year, description, location
    grants_received: List[Dict[str, Any]] = Field(default_factory=list)  # grantor_name, amount, year, description
    total_grants_made: Optional[float] = Field(None, ge=0)  # Total $ of grants made
    total_grants_received: Optional[float] = Field(None, ge=0)  # Total $ of grants received

    # Financial information (derived from IRS 990)
    total_revenue: Optional[float] = Field(None, ge=0)
    total_expenses: Optional[float] = Field(None, ge=0)
    total_assets: Optional[float] = Field(None, ge=0)
    total_liabilities: Optional[float] = Field(None, ge=0)
    net_assets: Optional[float] = None  # Can be negative
    program_expense_ratio: Optional[float] = Field(None, ge=0, le=1)  # Program expenses / total expenses

    # Multi-year financial trends (if available)
    revenue_trend: List[Dict[str, Any]] = Field(default_factory=list)  # year, amount
    expense_trend: List[Dict[str, Any]] = Field(default_factory=list)  # year, amount

    # Organization details
    year_founded: Optional[int] = Field(None, ge=1800, le=2100)
    ntee_code: Optional[str] = None
    ntee_description: Optional[str] = None
    irs_subsection: Optional[str] = None  # 501(c)(3), etc.
    number_of_employees: Optional[int] = Field(None, ge=0)

    # Leadership and governance
    board_members: List[Dict[str, Any]] = Field(default_factory=list)  # name, title, compensation
    board_size: Optional[int] = Field(None, ge=0)
    key_personnel: List[Dict[str, Any]] = Field(default_factory=list)  # name, title, compensation

    # Contact information
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None

    # Metadata
    causeiq_url: Optional[str] = None  # URL of CauseIQ profile
    slug: Optional[str] = None  # CauseIQ URL slug for this organization

    @field_validator("ein")
    @classmethod
    def validate_ein_format(cls, v: str) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        return normalize_ein(v)

    @field_validator("program_expense_ratio")
    @classmethod
    def validate_expense_ratio(cls, v: Optional[float]) -> Optional[float]:
        """Ensure expense ratio is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Program expense ratio must be between 0 and 1")
        return v

    @property
    def has_program_data(self) -> bool:
        """Check if organization has detailed program information."""
        return len(self.programs) > 0 or len(self.program_areas) > 0

    @property
    def has_grantmaking_data(self) -> bool:
        """Check if organization has grantmaking information."""
        return len(self.grants_made) > 0 or len(self.grants_received) > 0

    @property
    def has_financial_data(self) -> bool:
        """Check if organization has financial information."""
        return self.total_revenue is not None or self.total_expenses is not None or self.total_assets is not None

"""
Pydantic validator for Charity Navigator data.

Validates data from Charity Navigator web scraping (comprehensive extraction).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.validators.base_validator import normalize_ein


class CharityNavigatorProfile(BaseModel):
    """
    Charity Navigator profile data from web scraping.

    Extracts ALL available data including 4 beacon scores, detailed accountability
    metrics, financial data, governance information, and IRS data.
    """

    model_config = ConfigDict(extra="forbid")

    # Required fields
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")
    name: str = Field(..., min_length=1)

    # Basic information
    mission: Optional[str] = None
    website_url: Optional[str] = None
    irs_subsection: Optional[str] = None
    irs_ruling_year: Optional[int] = Field(None, ge=1800, le=2100)

    # Address and contact
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None

    # Rating status
    cn_is_rated: Optional[bool] = None  # True if charity has full beacon rating (not just award)
    cn_has_encompass_award: Optional[bool] = None  # True if only has culture_score (Encompass Award)
    cn_beacon_count: Optional[int] = Field(None, ge=0, le=4)  # Number of beacon scores available
    star_rating: Optional[float] = Field(None, ge=0, le=4)  # 0-4 star rating

    # Overall and legacy scores (0-100)
    overall_score: Optional[float] = Field(None, ge=0, le=100)
    financial_score: Optional[float] = Field(None, ge=0, le=100)  # Legacy
    accountability_score: Optional[float] = Field(None, ge=0, le=100)  # Legacy or new beacon

    # New 4 Beacon Scores (0-100)
    impact_score: Optional[float] = Field(None, ge=0, le=100)
    culture_score: Optional[float] = Field(None, ge=0, le=100)
    leadership_score: Optional[float] = Field(None, ge=0, le=100)

    # Beacons/badges
    beacons: List[str] = Field(default_factory=list)

    # Financial ratios (0-1)
    program_expense_ratio: Optional[float] = Field(None, ge=0, le=1)
    admin_expense_ratio: Optional[float] = Field(None, ge=0, le=1)
    fundraising_expense_ratio: Optional[float] = Field(None, ge=0, le=1)
    fundraising_efficiency: Optional[float] = Field(None, ge=0)  # Cost to raise $1 (e.g., 0.15 = $0.15)
    working_capital_ratio: Optional[float] = Field(None, ge=0)

    # Financial amounts
    program_expenses: Optional[float] = Field(None, ge=0)
    admin_expenses: Optional[float] = Field(None, ge=0)
    administrative_expenses: Optional[float] = Field(None, ge=0)  # Alias from LLM extraction
    fundraising_expenses: Optional[float] = Field(None, ge=0)
    total_revenue: Optional[float] = Field(None, ge=0)
    total_expenses: Optional[float] = Field(None, ge=0)

    # Balance sheet
    total_assets: Optional[float] = Field(None, ge=0)
    total_liabilities: Optional[float] = Field(None, ge=0)
    net_assets: Optional[float] = Field(None)

    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100)
    has_financial_audit: Optional[bool] = None

    # Governance and leadership
    ceo_name: Optional[str] = None
    ceo_compensation: Optional[float] = Field(None, ge=0)
    board_size: Optional[int] = Field(None, ge=0)
    independent_board_percentage: Optional[int] = Field(None, ge=0, le=100)

    # Detailed accountability metrics (dict of metric_name -> {earned, total, percentage})
    accountability_metrics: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("ein")
    @classmethod
    def validate_ein_format(cls, v: str) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        return normalize_ein(v)

    @field_validator("independent_board_percentage", mode="before")
    @classmethod
    def cap_board_percentage(cls, v: Optional[int]) -> Optional[int]:
        """Cap independent_board_percentage at 100 (bad source data sometimes exceeds 100)."""
        if v is not None and v > 100:
            return 100
        return v

    @field_validator("program_expense_ratio", "admin_expense_ratio", "fundraising_expense_ratio")
    @classmethod
    def validate_expense_ratios(cls, v: Optional[float]) -> Optional[float]:
        """Ensure expense ratios sum to approximately 1.0 (with some tolerance for rounding)."""
        # Individual validation - just ensure in range
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Expense ratio must be between 0 and 1")
        return v

    @property
    def total_expense_ratio_check(self) -> bool:
        """
        Check if expense ratios sum to approximately 1.0.

        Returns True if ratios are consistent, False otherwise.
        """
        ratios = [
            self.program_expense_ratio,
            self.admin_expense_ratio,
            self.fundraising_expense_ratio,
        ]

        # If all ratios are present, they should sum to ~1.0
        if all(r is not None for r in ratios):
            total = sum(ratios)
            return 0.95 <= total <= 1.05  # Allow 5% tolerance for rounding

        return True  # Can't validate if ratios are missing

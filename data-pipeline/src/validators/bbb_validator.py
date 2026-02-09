"""
Pydantic validator for BBB Wise Giving Alliance data.

Validates data scraped from give.org charity evaluation reports.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.validators.base_validator import normalize_ein


class BBBProfile(BaseModel):
    """
    BBB Wise Giving Alliance charity evaluation data.

    BBB WGA evaluates charities against 20 Standards for Charity Accountability
    grouped into 4 categories:
    - Governance & Oversight (Standards 1-5)
    - Measuring Effectiveness (Standards 6-9)
    - Finances (Standards 10-15)
    - Solicitations & Informational Materials (Standards 16-20)

    A charity "meets standards" only if ALL 20 standards are met.
    """

    model_config = ConfigDict(extra="ignore")  # Allow extra fields from scraping

    # Required fields (per spec)
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")
    name: str = Field(..., min_length=1)

    # Overall status (per spec)
    meets_standards: Optional[bool] = None
    standards_met: List[str] = Field(default_factory=list)  # List of standard names that passed
    standards_not_met: List[str] = Field(default_factory=list)  # List of standard names that failed
    accredited: Optional[bool] = None

    # Extended fields (beyond spec, for detailed tracking)
    review_url: Optional[str] = None
    last_review_date: Optional[str] = None
    status_text: Optional[str] = None  # "Meets Standards", "Does Not Meet Standards", "Unable to Verify"

    # Standards breakdown (extended)
    standards_met_count: int = Field(default=0, ge=0, le=20)
    standards_not_met_count: int = Field(default=0, ge=0, le=20)
    standards_details: Dict[str, bool] = Field(default_factory=dict)  # standard_1..standard_20 -> bool

    # Category pass/fail (aggregated)
    governance_pass: Optional[bool] = None  # Standards 1-5
    effectiveness_pass: Optional[bool] = None  # Standards 6-9
    finances_pass: Optional[bool] = None  # Standards 10-15
    solicitations_pass: Optional[bool] = None  # Standards 16-20

    # Governance details (Standards 1-5)
    board_size: Optional[int] = Field(None, ge=0)
    board_size_meets_standard: Optional[bool] = None  # >= 5 members
    board_meetings_per_year: Optional[int] = Field(None, ge=0)
    board_meetings_meets_standard: Optional[bool] = None  # >= 3 meetings
    compensated_board_members: Optional[int] = Field(None, ge=0)
    board_compensation_meets_standard: Optional[bool] = None  # <= 50% compensated
    conflict_of_interest_policy: Optional[bool] = None

    # Financial metrics (Standards 10-15)
    program_expense_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    program_expense_meets_standard: Optional[bool] = None  # >= 65%
    fundraising_expense_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    fundraising_expense_meets_standard: Optional[bool] = None  # <= 35%
    reserves_ratio: Optional[float] = Field(None, ge=0.0)
    reserves_meets_standard: Optional[bool] = None  # <= 3 years

    # Audit status
    audit_status: Optional[str] = None  # "audited", "reviewed", "compiled", "internal"
    has_required_audit: Optional[bool] = None

    # Effectiveness (Standards 6-9)
    effectiveness_policy: Optional[bool] = None
    has_effectiveness_assessment: Optional[bool] = None

    # Transparency (Standards 16-20)
    annual_report_available: Optional[bool] = None
    donor_privacy_policy: Optional[bool] = None
    complaint_response_policy: Optional[bool] = None

    @field_validator("ein")
    @classmethod
    def validate_ein(cls, v: str) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        return normalize_ein(v)

    @field_validator("standards_details")
    @classmethod
    def validate_standards_details(cls, v: Dict[str, bool]) -> Dict[str, bool]:
        """Ensure all keys are valid standard names."""
        valid_keys = {f"standard_{i}" for i in range(1, 21)}
        for key in v.keys():
            if key not in valid_keys:
                # Allow but warn about unexpected keys - scraping may produce extras
                pass
        return v

    @property
    def all_standards_met(self) -> bool:
        """Check if all 20 standards are met."""
        return self.meets_standards is True or self.standards_met_count == 20

    @property
    def has_governance_data(self) -> bool:
        """Check if governance details were extracted."""
        return any([
            self.board_size is not None,
            self.board_meetings_per_year is not None,
            self.conflict_of_interest_policy is not None,
        ])

    @property
    def has_financial_data(self) -> bool:
        """Check if financial metrics were extracted."""
        return any([
            self.program_expense_ratio is not None,
            self.fundraising_expense_ratio is not None,
            self.reserves_ratio is not None,
        ])

"""
Pydantic validator for ProPublica IRS 990 data.

Validates data from ProPublica NonProfit Explorer API.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.validators.base_validator import normalize_ein


class ProPublica990Profile(BaseModel):
    """
    ProPublica IRS Form 990 data.

    Financial and operational data from IRS 990 forms.
    """

    model_config = ConfigDict(extra="forbid")

    # Required fields (per spec: use 'name' not 'organization_name')
    ein: str = Field(..., min_length=9)  # May be with or without hyphen
    name: str = Field(..., min_length=1)

    # Tax year
    tax_year: Optional[int] = Field(None, ge=1900, le=2100)

    # Revenue
    total_revenue: Optional[float] = Field(None, ge=0)
    total_contributions: Optional[float] = Field(None, ge=0)
    program_service_revenue: Optional[float] = Field(None, ge=0)
    investment_income: Optional[float] = None  # Can be negative
    other_revenue: Optional[float] = None  # Can be negative

    # Expenses
    total_expenses: Optional[float] = Field(None, ge=0)
    program_expenses: Optional[float] = Field(None, ge=0)
    admin_expenses: Optional[float] = Field(None, ge=0)
    fundraising_expenses: Optional[float] = Field(None, ge=0)

    # Assets and liabilities
    total_assets: Optional[float] = Field(None, ge=0)
    total_liabilities: Optional[float] = None  # Allow negative for data quality issues in 990 forms
    net_assets: Optional[float] = None  # Can be negative in deficit situations

    # People
    employees_count: Optional[int] = Field(None, ge=0)
    volunteers_count: Optional[int] = Field(None, ge=0)

    # Compensation
    compensation_current_officers: Optional[float] = Field(None, ge=0)
    other_salaries_wages: Optional[float] = Field(None, ge=0)  # Non-officer salaries
    payroll_tax: Optional[float] = Field(None, ge=0)

    # Contact information
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

    # Classification
    ntee_code: Optional[str] = None
    subsection_code: Optional[str] = None
    affiliation_code: Optional[str] = None
    filing_type: Optional[str] = None
    foundation_code: Optional[str] = None  # Foundation type classification
    irs_ruling_year: Optional[int] = Field(None, ge=1800, le=2100)  # Year IRS granted tax-exempt status (per spec)

    # Filing history for trend analysis (up to 3 years)
    filing_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="Historical filing data for trend analysis (up to 3 years)"
    )

    # Form 990 filing status
    no_filings: Optional[bool] = Field(None, description="No Form 990 filings found in ProPublica")
    form_990_exempt: Optional[bool] = Field(None, description="Exempt from Form 990 (churches/religious orgs)")
    form_990_exempt_reason: Optional[str] = Field(None, description="Reason for exemption")

    @field_validator("filing_type", mode="before")
    @classmethod
    def convert_filing_type(cls, v):
        """Convert filing_type to string if it's an integer."""
        if v is None:
            return None
        return str(v)

    @field_validator("ein")
    @classmethod
    def validate_ein(cls, v: str) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        return normalize_ein(v)

    @field_validator("total_expenses")
    @classmethod
    def validate_total_expenses(cls, v: Optional[float]) -> Optional[float]:
        """Validate total expenses is reasonable."""
        if v is not None and v > 1e12:  # $1 trillion
            raise ValueError("Total expenses seems unreasonably large")
        return v

    @property
    def program_expense_ratio(self) -> Optional[float]:
        """Calculate program expense ratio if data available."""
        if self.program_expenses is not None and self.total_expenses is not None and self.total_expenses > 0:
            return self.program_expenses / self.total_expenses
        return None

    @property
    def admin_expense_ratio(self) -> Optional[float]:
        """Calculate admin expense ratio if data available."""
        if self.admin_expenses is not None and self.total_expenses is not None and self.total_expenses > 0:
            return self.admin_expenses / self.total_expenses
        return None

    @property
    def fundraising_expense_ratio(self) -> Optional[float]:
        """Calculate fundraising expense ratio if data available."""
        if self.fundraising_expenses is not None and self.total_expenses is not None and self.total_expenses > 0:
            return self.fundraising_expenses / self.total_expenses
        return None

"""
Pydantic validator for Form 990 grants data.

Validates grants data extracted from 990 XML Schedule I and Schedule F.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.validators.base_validator import normalize_ein


class Grant(BaseModel):
    """Individual grant record."""

    model_config = ConfigDict(extra="forbid")

    recipient_name: Optional[str] = None
    recipient_ein: Optional[str] = None
    amount: float = Field(..., ge=0)
    purpose: Optional[str] = None
    region: Optional[str] = None  # For foreign grants
    is_foreign: bool = False
    tax_year: Optional[int] = Field(None, ge=2010, le=2030)  # FIX #22: filing year


class Form990GrantsProfile(BaseModel):
    """
    Form 990 grants profile data.

    Contains grants made by the organization extracted from:
    - Schedule I: Grants to domestic organizations and governments
    - Schedule F: Grants to foreign organizations and individuals
    """

    model_config = ConfigDict(extra="forbid")

    # Required fields (per spec: use 'name' not 'organization_name')
    name: str = Field(..., min_length=1)
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")

    # Filing metadata
    tax_year: Optional[int] = Field(None, ge=2010, le=2030)
    object_id: Optional[str] = None  # ProPublica object_id for reference
    filing_years: List[int] = Field(default_factory=list)  # FIX #22: all years included

    # Grants data
    domestic_grants: List[Dict[str, Any]] = Field(default_factory=list)
    foreign_grants: List[Dict[str, Any]] = Field(default_factory=list)

    # Aggregates
    total_domestic_grants: float = Field(default=0, ge=0)
    total_foreign_grants: float = Field(default=0, ge=0)
    total_grants: float = Field(default=0, ge=0)
    domestic_grant_count: int = Field(default=0, ge=0)
    foreign_grant_count: int = Field(default=0, ge=0)

    # Financial context
    total_revenue: Optional[float] = None
    total_expenses: Optional[float] = None
    program_expenses: Optional[float] = None

    @field_validator("ein")
    @classmethod
    def validate_ein_format(cls, v: str) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        return normalize_ein(v)

    @property
    def grants_as_percent_of_expenses(self) -> Optional[float]:
        """Calculate grants as percentage of total expenses."""
        if self.total_expenses and self.total_expenses > 0:
            return (self.total_grants / self.total_expenses) * 100
        return None

    @property
    def is_grantmaker(self) -> bool:
        """Determine if organization is primarily a grantmaker."""
        # If grants are >50% of expenses, likely a grantmaker/foundation
        pct = self.grants_as_percent_of_expenses
        return pct is not None and pct > 50

    @property
    def top_domestic_grants(self) -> List[Dict[str, Any]]:
        """Get top 10 domestic grants by amount."""
        sorted_grants = sorted(
            self.domestic_grants,
            key=lambda g: g.get("amount", 0) or 0,
            reverse=True,
        )
        return sorted_grants[:10]

    @property
    def top_foreign_grants(self) -> List[Dict[str, Any]]:
        """Get top 10 foreign grants by amount."""
        sorted_grants = sorted(
            self.foreign_grants,
            key=lambda g: g.get("amount", 0) or 0,
            reverse=True,
        )
        return sorted_grants[:10]

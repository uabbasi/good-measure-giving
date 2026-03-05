"""Data models for the adversarial reconciliation phase.

Contradiction signals are first-class outputs that flow into scoring and export.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SignalSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SignalCategory(str, Enum):
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    GOVERNANCE = "governance"
    IMPACT = "impact"


class ContradictionSignal(BaseModel):
    """A single contradiction or red-flag detected by a deterministic check."""

    check_name: str = Field(description="Registry key, e.g. 'gik_inflated_ratio'")
    severity: SignalSeverity
    category: SignalCategory
    headline: str = Field(description="One-line donor-facing summary")
    detail: str = Field(description="Explanation with numbers")
    data_points: dict[str, Any] = Field(default_factory=dict, description="Evidence values")


class ReconciliationResult(BaseModel):
    """Output of the full reconciliation pass for one charity."""

    signals: list[ContradictionSignal] = Field(default_factory=list)
    completeness_gaps: list[str] = Field(
        default_factory=list, description="Fields that were null and could not be re-derived"
    )
    patched_fields: list[str] = Field(
        default_factory=list, description="Fields successfully re-derived from source data"
    )

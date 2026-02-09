"""Evaluation Dataset model for versioned test sets."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EvaluationDataset(BaseModel):
    """
    Versioned test dataset used for model evaluation.
    """

    name: str = Field(..., description="Dataset name (e.g., 'pilot-charities')")
    version: Optional[str] = Field(None, description="Semantic version (e.g., 'v1.2.3')")
    record_count: int = Field(..., description="Number of records in this version")
    created_at: datetime = Field(..., description="Dataset creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")
    metadata: dict = Field(default_factory=dict, description="Custom metadata (source, tags)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "pilot-charities",
                "version": "v3.7.0",
                "record_count": 17,
                "created_at": "2025-12-20T00:00:00Z",
                "updated_at": "2025-12-20T12:00:00Z",
                "metadata": {"source": "pilot_charities.txt", "description": "Standard 17-charity pilot set"},
            }
        }

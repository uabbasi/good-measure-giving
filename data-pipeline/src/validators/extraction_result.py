"""
Extraction result model with provenance tracking.

This module provides transparent tracking of where each field was extracted from.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """Single extracted field with provenance."""

    field_name: str  # e.g., "mission", "ein", "donate_url"
    field_value: Any  # Actual extracted value
    extraction_source: Literal[
        "json-ld",
        "opengraph",
        "microdata",
        "regex-ein",
        "regex-contact",
        "regex-social",
        "regex-donate",
        "llm-homepage",
        "llm-about",
        "llm-programs",
        "llm-impact",
        "llm-donate",
        "llm-contact",
    ]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    extraction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_schema_extra = {
            "example": {
                "field_name": "ein",
                "field_value": "95-4453134",
                "extraction_source": "json-ld",
                "confidence_score": 1.0,
                "extraction_timestamp": "2025-11-22T13:45:00Z",
            }
        }

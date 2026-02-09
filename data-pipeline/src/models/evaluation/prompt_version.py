"""PromptVersion model for semantic versioning of evaluation prompts."""

import hashlib
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PromptVersion(BaseModel):
    """
    Semantic versioning for charity evaluation prompts.

    Prompts are versioned to track changes over time and enable A/B testing.
    """

    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version (e.g., '3.5.0')")
    prompt_text: str = Field(..., min_length=100, description="Full prompt text")
    prompt_hash: str = Field(..., description="SHA256 hash for deduplication")
    model: str = Field(..., description="LLM model (e.g., 'gemini-3.0-pro')")
    created_at: datetime = Field(..., description="Version creation timestamp (UTC)")
    created_by: str = Field(..., description="Author (e.g., 'pipeline')")
    changelog: Optional[str] = Field(None, description="What changed in this version")
    metadata: dict = Field(default_factory=dict, description="Custom metadata")

    @field_validator("prompt_hash")
    @classmethod
    def validate_prompt_hash(cls, v: str, info) -> str:
        """Ensure prompt_hash matches SHA256 of prompt_text."""
        prompt_text = info.data.get("prompt_text", "")
        expected_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        if v != expected_hash:
            raise ValueError(f"prompt_hash mismatch: expected {expected_hash}, got {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "version": "3.5.0",
                "prompt_text": "You are evaluating a charity for zakat eligibility...",
                "prompt_hash": "a1b2c3d4e5f6...",
                "model": "gemini-3.0-pro",
                "created_at": "2025-12-06T12:00:00Z",
                "created_by": "pipeline",
                "changelog": "Added section on program efficiency scoring",
            }
        }

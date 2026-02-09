"""Experiment model for tracking local LLM evaluation runs."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExperimentStatus(str, Enum):
    """Experiment execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Experiment(BaseModel):
    """
    Local experiment tracking charity evaluations.

    Each experiment tests a specific prompt version against a set of charities.
    """

    experiment_id: str = Field(..., description="Unique experiment ID (UUID)")
    project_name: str = Field(..., description="Project category name")
    experiment_name: str = Field(..., description="Human-readable name (e.g., 'prompt-v3.7.0')")
    llm_model: str = Field(..., description="LLM model used (e.g., 'gemini-3-flash-preview')")
    prompt_version: str = Field(..., description="Prompt version tested (e.g., '3.7.0')")
    dataset_name: str = Field(..., description="Dataset name (e.g., 'pilot-charities')")
    status: ExperimentStatus = Field(ExperimentStatus.PENDING, description="Execution status")
    sample_size: int = Field(..., description="Number of charities evaluated")
    started_at: Optional[datetime] = Field(None, description="Experiment start timestamp (UTC)")
    completed_at: Optional[datetime] = Field(None, description="Experiment completion timestamp (UTC)")
    total_cost_usd: float = Field(0.0, description="Estimated total API cost")
    metadata: dict = Field(default_factory=dict, description="Custom metadata (git commit, parallel workers)")

    class Config:
        json_schema_extra = {
            "example": {
                "experiment_id": "abc123-def456",
                "project_name": "zakaat-charity-evaluations",
                "experiment_name": "prompt-v3.7.0",
                "llm_model": "gemini-3-flash-preview",
                "prompt_version": "3.7.0",
                "dataset_name": "pilot-charities",
                "status": "completed",
                "sample_size": 17,
                "started_at": "2025-12-20T12:00:00Z",
                "completed_at": "2025-12-20T12:25:00Z",
                "total_cost_usd": 0.45,
                "metadata": {"git_commit": "0462608", "workers": 5},
            }
        }

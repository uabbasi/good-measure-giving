"""ExperimentComparison model for statistical comparison between local experiments."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ScorerDiff(BaseModel):
    """Score difference for a single scorer."""

    scorer_name: str
    experiment_a_score: float
    experiment_b_score: float
    absolute_diff: float  # B - A
    percent_diff: float  # ((B - A) / A) * 100
    statistically_significant: bool  # T-test p < 0.05


class ExperimentComparison(BaseModel):
    """
    Statistical comparison between two local experiments.

    Used for prompt A/B testing and model comparison.
    """

    experiment_a_id: str = Field(..., description="First experiment (baseline)")
    experiment_b_id: str = Field(..., description="Second experiment (new)")
    experiment_a_name: str
    experiment_b_name: str
    scorer_diffs: List[ScorerDiff] = Field(..., description="Score differences per scorer")
    winner: Optional[str] = Field(None, description="'A', 'B', or 'tie'")
    recommendation: str = Field(..., description="Human-readable recommendation")

    class Config:
        json_schema_extra = {
            "example": {
                "experiment_a_id": "gemini-3-flash",
                "experiment_b_id": "gemini-3-pro",
                "experiment_a_name": "Gemini 3 Flash",
                "experiment_b_name": "Gemini 3 Pro",
                "scorer_diffs": [
                    {
                        "scorer_name": "Input Handling",
                        "experiment_a_score": 0.68,
                        "experiment_b_score": 0.69,
                        "absolute_diff": 0.01,
                        "percent_diff": 1.47,
                        "statistically_significant": False,
                    }
                ],
                "winner": "B",
                "recommendation": "Gemini 3 Pro shows slight improvement over Flash. Both are viable.",
            }
        }

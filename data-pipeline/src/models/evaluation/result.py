"""ExperimentResult model for aggregated experiment scores."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ScorerResult(BaseModel):
    """Individual scorer results."""

    scorer_name: str = Field(..., description="Scorer name (e.g., 'Factuality', 'ClosedQA')")
    mean_score: float = Field(..., ge=0.0, le=1.0, description="Mean score across all evaluations")
    median_score: float = Field(..., ge=0.0, le=1.0, description="Median score")
    std_dev: float = Field(..., ge=0.0, description="Standard deviation")
    min_score: float = Field(..., ge=0.0, le=1.0, description="Minimum score")
    max_score: float = Field(..., ge=0.0, le=1.0, description="Maximum score")
    num_evaluations: int = Field(..., description="Number of evaluations scored")


class ExperimentResult(BaseModel):
    """
    Aggregated results from a Braintrust experiment.

    Computed by Braintrust after experiment completion.
    """

    experiment_id: str = Field(..., description="Parent experiment ID")
    scorers: List[ScorerResult] = Field(..., description="Results per scorer")
    total_evaluations: int = Field(..., description="Total charity evaluations logged")
    scored_evaluations: int = Field(..., description="Number of evaluations scored (with sampling)")
    avg_latency_seconds: float = Field(..., description="Average evaluation latency")
    total_cost_usd: float = Field(..., description="Total LLM API cost (evaluations + scoring)")
    regression_detected: bool = Field(False, description="True if scores dropped >5% from baseline")
    baseline_experiment_id: Optional[str] = Field(None, description="Baseline experiment for comparison")

    class Config:
        json_schema_extra = {
            "example": {
                "experiment_id": "abc123-def456",
                "scorers": [
                    {
                        "scorer_name": "Factuality",
                        "mean_score": 0.85,
                        "median_score": 0.87,
                        "std_dev": 0.12,
                        "min_score": 0.45,
                        "max_score": 0.98,
                        "num_evaluations": 15,
                    }
                ],
                "total_evaluations": 150,
                "scored_evaluations": 15,
                "avg_latency_seconds": 3.2,
                "total_cost_usd": 12.50,
                "regression_detected": False,
                "baseline_experiment_id": "xyz789",
            }
        }

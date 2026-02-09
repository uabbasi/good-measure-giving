"""LLM-as-Judge schema for narrative quality evaluation.

Defines the JudgeResult schema used by NarrativeJudge to evaluate
generated narratives before routing to human review or auto-approval.
"""

from typing import Literal

from pydantic import BaseModel, Field


class JudgeResult(BaseModel):
    """LLM judge evaluation of a generated narrative.

    The judge evaluates narratives across 5 dimensions, each scored 0-100.
    A composite score determines the routing decision:
    - >= 85: Auto-approve (no human review needed)
    - 60-84: Human review required
    - < 60: Auto-reject

    Attributes:
        factual_accuracy: Do narrative claims match the source data?
        completeness: Are all required fields populated meaningfully?
        coherence: Is the narrative internally consistent and well-structured?
        tone_style: Does it match the expected donor-facing voice?
        zakat_validity: Is the zakat classification defensible?
        composite_score: Weighted average of dimension scores
        issues_found: Specific problems identified during evaluation
        recommendation: The routing decision based on composite score
    """

    factual_accuracy: int = Field(
        ge=0,
        le=100,
        description="Do claims in the narrative match the source data? Check financial figures, dates, and factual statements.",
    )
    completeness: int = Field(
        ge=0,
        le=100,
        description="Are all required fields populated with meaningful content? Check for missing or placeholder text.",
    )
    coherence: int = Field(
        ge=0,
        le=100,
        description="Is the narrative internally consistent and well-structured? Check for contradictions or logical gaps.",
    )
    tone_style: int = Field(
        ge=0,
        le=100,
        description="Does the narrative match donor-facing expectations? Check for appropriate formality and clarity.",
    )
    zakat_validity: int = Field(
        ge=0,
        le=100,
        description="Is the zakat classification defensible? Check if rationale aligns with Islamic principles.",
    )
    composite_score: int = Field(
        ge=0,
        le=100,
        description="Weighted average of all dimension scores. Determines routing decision.",
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="Specific problems identified during evaluation. Be precise and actionable.",
    )
    recommendation: Literal["auto_approve", "human_review", "auto_reject"] = Field(
        description="Routing decision: auto_approve (score >= 85), human_review (60-84), auto_reject (< 60)",
    )


# Dimension weights for composite score calculation
DIMENSION_WEIGHTS = {
    "factual_accuracy": 0.30,  # Most critical - must match source data
    "completeness": 0.20,
    "coherence": 0.20,
    "tone_style": 0.15,
    "zakat_validity": 0.15,
}

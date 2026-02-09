"""
Pydantic models for validating charity data schemas.

These models ensure data quality and consistency across all pipeline stages.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Enums for Tier Classifications
# ============================================================================


class TierLevel(str, Enum):
    """Overall tier classifications."""

    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ScoreColor(str, Enum):
    """Dimension score colors."""

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    UNKNOWN = "UNKNOWN"


class ZakatClassification(str, Enum):
    """Zakat eligibility classifications."""

    LIKELY_ELIGIBLE = "likely_eligible"
    PARTIALLY_ELIGIBLE = "partially_eligible"
    UNCLEAR = "unclear"
    SADAQAH_ONLY = "sadaqah_only"
    INSUFFICIENT_DATA = "insufficient_data"


class RecommendationLevel(str, Enum):
    """Overall recommendation levels for donors."""

    HIGHLY_RECOMMENDED = "HIGHLY_RECOMMENDED"
    RECOMMENDED = "RECOMMENDED"
    ACCEPTABLE = "ACCEPTABLE"
    PROCEED_WITH_CAUTION = "PROCEED_WITH_CAUTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DataSource(str, Enum):
    """Data source identifiers."""

    CHARITY_NAVIGATOR = "charity_navigator"
    PROPUBLICA = "propublica"
    CANDID = "candid"
    WEBSITE = "website"


# ============================================================================
# Dimension Score Models
# ============================================================================


class DimensionScore(BaseModel):
    """Individual dimension score with rationale."""

    model_config = ConfigDict(extra="forbid")

    dimension_name: str = Field(..., description="Name of the dimension")
    score_color: ScoreColor = Field(..., description="GREEN/YELLOW/RED classification")
    score_value: Optional[float] = Field(None, ge=0, le=100, description="Optional numeric score")
    weight: float = Field(..., ge=0, le=1, description="Weight in tier calculation")
    rationale: Optional[str] = Field(None, description="Brief explanation of score")
    cited_metrics: List[str] = Field(default_factory=list, description="Metrics used in scoring")
    data_available: bool = Field(True, description="Whether data was available for scoring")


class ImpactDimensions(BaseModel):
    """All five Impact dimension scores."""

    model_config = ConfigDict(extra="forbid")

    problem_importance: DimensionScore
    intervention_strength: DimensionScore
    scale_of_reach: DimensionScore
    cost_effectiveness: DimensionScore
    long_term_benefit: DimensionScore


class ConfidenceDimensions(BaseModel):
    """All five Confidence dimension scores."""

    model_config = ConfigDict(extra="forbid")

    transparency: DimensionScore
    accountability_governance: DimensionScore
    use_of_funds: DimensionScore
    third_party_verification: DimensionScore
    reporting_quality: DimensionScore


# ============================================================================
# Evaluation Models
# ============================================================================


class Evaluation(BaseModel):
    """Complete evaluation result for a charity."""

    model_config = ConfigDict(extra="forbid")

    charity_id: int = Field(..., description="Database ID of charity")
    ein: str = Field(..., description="EIN for reference")
    methodology_version: str = Field(..., description="Version of methodology used")

    # Tier classifications
    impact_tier: TierLevel
    confidence_tier: TierLevel
    zakat_classification: ZakatClassification
    overall_recommendation: RecommendationLevel

    # Dimension scores
    impact_dimensions: ImpactDimensions
    confidence_dimensions: ConfidenceDimensions

    # Metadata
    data_completeness_pct: float = Field(..., ge=0, le=100)
    evaluation_date: datetime = Field(default_factory=datetime.now)
    sources_used: List[DataSource] = Field(default_factory=list)


# ============================================================================
# LLM Narrative Models
# ============================================================================


class DimensionRating(BaseModel):
    """Individual dimension rating with rationale (for LLM output)."""

    model_config = ConfigDict(extra="forbid")

    rating: ScoreColor = Field(..., description="GREEN/YELLOW/RED/UNKNOWN classification")
    rationale: str = Field(..., min_length=10, max_length=500, description="Explanation with evidence")


class ImpactNarrative(BaseModel):
    """LLM-generated Impact narrative with dimension ratings and overall assessment."""

    model_config = ConfigDict(extra="forbid")

    overall_rating: ScoreColor = Field(..., description="Overall GREEN/YELLOW/RED/UNKNOWN rating")
    dimension_ratings: Dict[str, DimensionRating] = Field(
        ...,
        description="Ratings for all 5 dimensions: problem_importance_tractability, evidence_of_effectiveness, "
        "scale_of_reach, cost_effectiveness, sustainability_depth",
    )
    good_measure_impact_rating: str = Field(
        ..., pattern="^(HIGH|MODERATE|LOW|INSUFFICIENT_DATA)$", description="Good Measure tier classification"
    )
    summary: str = Field(..., min_length=50, max_length=500, description="Brief summary of impact assessment")
    areas_for_improvement: List[str] = Field(
        default_factory=list, description="Specific areas where the charity could improve"
    )
    cited_sources: List[str] = Field(default_factory=list, description="Only sources actually used")
    key_strengths: List[str] = Field(default_factory=list)
    growth_opportunities: List[str] = Field(default_factory=list)
    confidence_level: str = Field(
        ..., pattern="^(high|medium|low)$", description="high=≤1 UNKNOWN, medium=2 UNKNOWN, low=≥3 UNKNOWN"
    )

    @field_validator("dimension_ratings")
    @classmethod
    def validate_all_dimensions_present(cls, v: Dict[str, DimensionRating]) -> Dict[str, DimensionRating]:
        """Ensure all 5 Impact dimensions are rated."""
        required_dimensions = {
            "problem_importance_tractability",
            "evidence_of_effectiveness",
            "scale_of_reach",
            "cost_effectiveness",
            "sustainability_depth",
        }

        missing = required_dimensions - set(v.keys())
        if missing:
            raise ValueError(f"Missing required dimensions: {missing}")

        return v


class ConfidenceNarrative(BaseModel):
    """LLM-generated Confidence narrative."""

    model_config = ConfigDict(extra="forbid")

    tier: TierLevel
    narrative: str = Field(..., min_length=150, max_length=2000)
    cited_sources: List[str] = Field(..., min_length=1)
    key_strengths: List[str] = Field(default_factory=list)
    growth_opportunities: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    confidence_level: str = Field(..., pattern="^(high|medium|low)$")


class ZakatNarrative(BaseModel):
    """LLM-generated Zakat alignment assessment."""

    model_config = ConfigDict(extra="forbid")

    zakat_classification: ZakatClassification
    primary_matching_categories: List[str] = Field(default_factory=list)
    explanation: str = Field(..., min_length=50, max_length=1000)
    caveats: List[str] = Field(default_factory=list)
    scholar_consultation_recommended: bool
    specific_guidance: str
    program_level_breakdown: Dict[str, List[str]] = Field(default_factory=dict)
    confidence: str = Field(..., pattern="^(high|medium|low)$")


class RecommendationNarrative(BaseModel):
    """LLM-generated donor recommendations."""

    model_config = ConfigDict(extra="forbid")

    recommendation_tier: RecommendationLevel
    summary: str = Field(..., min_length=20, max_length=500)
    giving_guidance: str = Field(..., min_length=50, max_length=1000)
    due_diligence: str
    alternatives_note: Optional[str] = None
    suitable_for_zakat: str = Field(..., pattern="^(yes|consult_scholar|no|insufficient_data)$")
    suitable_for_sadaqah: str = Field(..., pattern="^(yes|yes_with_caution|insufficient_data)$")


class UnifiedNarrativeResponse(BaseModel):
    """Unified response containing all 3 narrative types from a single LLM call."""

    model_config = ConfigDict(extra="forbid")

    impact_narrative: ImpactNarrative
    confidence_narrative: ConfidenceNarrative
    zakat_narrative: ZakatNarrative


# ============================================================================
# Data Validation Models (for pipeline inputs/outputs)
# ============================================================================


class ScrapedData(BaseModel):
    """Validated scraped data record."""

    model_config = ConfigDict(extra="forbid")

    charity_id: int
    source: DataSource
    raw_html: Optional[str] = None
    parsed_json: Dict[str, Any] = Field(..., description="Source-specific structured data")
    scrape_timestamp: datetime = Field(default_factory=datetime.now)
    data_freshness_days: Optional[int] = None
    scrape_success: bool = True
    error_message: Optional[str] = None

    @field_validator("parsed_json")
    @classmethod
    def validate_parsed_json_structure(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        """Ensure parsed_json follows the documented pattern."""
        if not v:
            raise ValueError("parsed_json cannot be empty")

        # Check that it has the expected top-level key based on source
        # This will be validated more strictly by source-specific validators
        return v


class LLMCostTracking(BaseModel):
    """Track LLM API costs and token usage."""

    model_config = ConfigDict(extra="forbid")

    model: str
    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    estimated_cost_usd: float = Field(..., ge=0)
    generation_timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Pipeline Metadata Models
# ============================================================================


class PipelineRun(BaseModel):
    """Metadata for a complete pipeline run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    charities_processed: int = 0
    charities_succeeded: int = 0
    charities_failed: int = 0
    total_llm_cost_usd: float = 0.0
    methodology_version: str = "1.0"


class SourceFailure(BaseModel):
    """Record of a data source failure."""

    model_config = ConfigDict(extra="forbid")

    charity_id: int
    ein: str
    source: DataSource
    error_message: str
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Helper Functions
# ============================================================================


def validate_tier_consistency(impact_tier: TierLevel, confidence_tier: TierLevel) -> bool:
    """
    Validate that Impact and Confidence tiers are independent.

    This is a sanity check - there should be no forced correlation between the two.
    Both can be HIGH, both can be LOW, or any combination.
    """
    # No validation rules - they are intentionally independent
    # This function exists for future consistency checks if needed
    return True


def calculate_data_completeness(dimensions: List[DimensionScore]) -> float:
    """
    Calculate data completeness percentage based on available dimensions.

    Args:
        dimensions: List of dimension scores

    Returns:
        Percentage of dimensions with data available (0-100)
    """
    if not dimensions:
        return 0.0

    available = sum(1 for d in dimensions if d.data_available)
    return (available / len(dimensions)) * 100


def meets_minimum_data_threshold(completeness_pct: float, threshold: float = 50.0) -> bool:
    """
    Check if data completeness meets minimum threshold for evaluation.

    Args:
        completeness_pct: Percentage of data available
        threshold: Minimum required percentage (default 50%)

    Returns:
        True if threshold is met
    """
    return completeness_pct >= threshold

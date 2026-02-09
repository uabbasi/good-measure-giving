"""Pydantic schemas for narrative generation.

This module contains:
- BaselineNarrative: Concise narrative for all charities (~150-200 words)
- RichNarrative: Comprehensive narrative for curated charities (~500-800 words)
- JudgeResult: LLM-as-judge evaluation for quality gating
- Enums: NarrativeKind, WorkflowState, RejectionReason, etc.
"""

from .baseline import (
    AmalDimensionScore,
    AmalScores,
    AmalScoresV2,
    BaselineNarrative,
    BaselineNarrativeV2,
    Beneficiaries,
    DimensionConfidence,
    EffectivenessAssessment,
    EvidenceAssessment,
    FitAssessment,
    ImpactMetrics,
    Links,
    MissionDeliveryScore,
    MissionDeliverySubScores,
    OperationalCapabilityScore,
    OperationalCapabilitySubScores,
    Program,
    SubScore,
    Tier1StrategicFit,
    Tier2Execution,
    TrustAssessment,
    UmmahGapScore,
    UmmahGapSubScores,
    ZakatBonusAssessment,
    ZakatClaimInfo,
)
from .common import (
    AtAGlance,
    CaseAgainst,
    Confidence,
    Evidence,
    EvidenceGrade,
    ImprovementArea,
    RiskCategory,
    RiskSeverity,
    Strength,
    ZakatClaim,
    ZakatGuidance,
)
from .enums import (
    SCORE_AUTO_APPROVE,
    SCORE_AUTO_REJECT,
    NarrativeKind,
    RejectionReason,
    WorkflowState,
    is_exportable_state,
    needs_review,
    should_auto_reject,
)
from .judge import DIMENSION_WEIGHTS, JudgeResult
from .rich import (
    ComparativeContext,
    DonorDecisionSupport,
    GivingScenarios,
    NarrativeSections,
    RichNarrative,
    RiskFactor,
)

__all__ = [
    # Enums and helpers
    "NarrativeKind",
    "WorkflowState",
    "RejectionReason",
    "is_exportable_state",
    "needs_review",
    "should_auto_reject",
    "SCORE_AUTO_APPROVE",
    "SCORE_AUTO_REJECT",
    # Judge schema
    "JudgeResult",
    "DIMENSION_WEIGHTS",
    # Common schema (shared by baseline and rich)
    "Evidence",
    "Strength",
    "AtAGlance",
    "ImprovementArea",
    "Confidence",
    "ZakatClaim",
    "ZakatGuidance",
    # V2 common schema
    "EvidenceGrade",
    "RiskCategory",
    "RiskSeverity",
    "CaseAgainst",
    # Baseline schema (V1)
    "ZakatClaimInfo",
    "BaselineNarrative",
    "Program",
    "Beneficiaries",
    "ImpactMetrics",
    "Links",
    "AmalScores",
    "AmalDimensionScore",
    "Tier1StrategicFit",
    "Tier2Execution",
    # Sub-score schemas
    "SubScore",
    "DimensionConfidence",
    "UmmahGapScore",
    "UmmahGapSubScores",
    "OperationalCapabilityScore",
    "OperationalCapabilitySubScores",
    "MissionDeliveryScore",
    "MissionDeliverySubScores",
    # Baseline schema (V2 - GWWC + Longview anchored)
    "BaselineNarrativeV2",
    "AmalScoresV2",
    "TrustAssessment",
    "EvidenceAssessment",
    "EffectivenessAssessment",
    "FitAssessment",
    "ZakatBonusAssessment",
    # Rich schema
    "RichNarrative",
    "NarrativeSections",
    "RiskFactor",
    "GivingScenarios",
    "DonorDecisionSupport",
    "ComparativeContext",
]

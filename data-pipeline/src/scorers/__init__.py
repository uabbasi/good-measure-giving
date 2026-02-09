"""Deterministic scoring modules for AMAL evaluation."""

from src.scorers.benchmark_comparison import (
    BenchmarkComparison,
    compare_to_benchmark,
    get_benchmark_context_for_prompt,
    get_benchmark_for_cause_area,
    get_givewell_charity,
    is_benchmark_charity,
)
from src.scorers.deterministic_t2 import (
    DeterministicT2Scores,
    calculate_deployment_capacity_score,
    calculate_deterministic_t2_scores,
    calculate_governance_score,
    calculate_program_efficiency_score,
    calculate_track_record_score,
)
from src.scorers.evidence_quality_scorer import (
    CostBenchmarkResult,
    EvidenceBasedGivingScores,
    EvidenceQualityResult,
    ThirdPartyVerificationResult,
    apply_evidence_modifiers,
    calculate_cost_benchmark,
    calculate_evidence_based_scores,
    calculate_evidence_grade,
    calculate_verification_status,
)

# V2 Scorers (GWWC + Longview anchored)
from src.scorers.v2_scorers import (
    AmalScorerV2,
    EffectivenessScorer,
    EvidenceScorer,
    FitScorer,
    RiskScorer,
    TrustScorer,
    ZakatScorer,
)

__all__ = [
    # Deterministic T2 scoring
    "DeterministicT2Scores",
    "calculate_deterministic_t2_scores",
    "calculate_deployment_capacity_score",
    "calculate_governance_score",
    "calculate_program_efficiency_score",
    "calculate_track_record_score",
    # Evidence-based giving scoring
    "EvidenceBasedGivingScores",
    "EvidenceQualityResult",
    "ThirdPartyVerificationResult",
    "CostBenchmarkResult",
    "calculate_evidence_grade",
    "calculate_verification_status",
    "calculate_cost_benchmark",
    "apply_evidence_modifiers",
    "calculate_evidence_based_scores",
    # Benchmark comparison
    "BenchmarkComparison",
    "compare_to_benchmark",
    "get_benchmark_for_cause_area",
    "get_givewell_charity",
    "is_benchmark_charity",
    "get_benchmark_context_for_prompt",
    # V2 Scorers (GWWC + Longview anchored)
    "AmalScorerV2",
    "TrustScorer",
    "EvidenceScorer",
    "EffectivenessScorer",
    "FitScorer",
    "ZakatScorer",
    "RiskScorer",
]

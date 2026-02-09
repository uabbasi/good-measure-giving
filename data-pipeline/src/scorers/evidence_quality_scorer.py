"""
Evidence Quality Scorer - calculates evidence quality grade and verification status.

Based on GiveWell's evidence hierarchy and evidence-based giving standards:
- A: RCT/meta-analysis (gold standard)
- B: Quasi-experimental (diff-in-diff, regression discontinuity)
- C: Observational with controls (cohort, case-control)
- D: Pre/post only (no control group)
- E: Self-reported (internal monitoring only)
- F: Anecdotal (testimonials only)

Score modifiers for delivery_evidence:
- A: +2 points
- B: +1 point
- C: 0 (baseline)
- D: -1 point
- E: -2 points
- F: -3 points

Third-party verification boost: +1 point for tier_1 sources
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class EvidenceQualityResult:
    """Result of evidence quality assessment."""

    grade: str  # A, B, C, D, E, F
    methodology_type: Optional[str]  # RCT, cohort study, etc.
    sources: list[str]  # Where evidence was found
    rationale: str  # Explanation
    score_modifier: int  # -3 to +2


@dataclass
class ThirdPartyVerificationResult:
    """Result of third-party verification assessment."""

    verified: bool
    sources: list[str]
    verification_type: Optional[str]
    tier: Optional[str]  # tier_1_gold, tier_2_strong, tier_3_moderate
    score_boost: float  # 0, 0.5, or 1.0


@dataclass
class CostBenchmarkResult:
    """Result of cost-effectiveness benchmark comparison."""

    cause_area: str
    cost_per_beneficiary: Optional[float]
    benchmark_name: str
    benchmark_range: Optional[list[float]]
    comparison: str  # above_benchmark, at_benchmark, below_benchmark, insufficient_data
    ratio: Optional[float]
    data_source: Optional[str]


# Evidence methodology keyword patterns
EVIDENCE_PATTERNS = {
    "A": {
        "keywords": [
            r"\brct\b",
            r"randomized controlled trial",
            r"randomised controlled trial",
            r"meta-analysis",
            r"meta analysis",
            r"systematic review",
            r"published in.*journal",
            r"peer-reviewed",
            r"peer reviewed",
        ],
        "methodology_type": "RCT/meta-analysis",
        "score_modifier": 2,
    },
    "B": {
        "keywords": [
            r"difference-in-difference",
            r"diff-in-diff",
            r"regression discontinuity",
            r"matched comparison",
            r"propensity score",
            r"quasi-experimental",
            r"quasi experimental",
            r"natural experiment",
            r"instrumental variable",
        ],
        "methodology_type": "Quasi-experimental",
        "score_modifier": 1,
    },
    "C": {
        "keywords": [
            r"longitudinal study",
            r"cohort study",
            r"case-control",
            r"case control",
            r"statistical controls",
            r"controlled for",
            r"regression analysis",
            r"multivariate analysis",
        ],
        "methodology_type": "Observational with controls",
        "score_modifier": 0,
    },
    "D": {
        "keywords": [
            r"pre-post",
            r"pre post",
            r"before and after",
            r"before-after",
            r"year-over-year",
            r"compared to baseline",
            r"compared to last year",
        ],
        "methodology_type": "Pre/post comparison",
        "score_modifier": -1,
    },
    "E": {
        "keywords": [
            r"internal monitoring",
            r"self-reported",
            r"we surveyed",
            r"beneficiary survey",
            r"we tracked",
            r"our data shows",
            r"we measured",
        ],
        "methodology_type": "Self-reported outcomes",
        "score_modifier": -2,
    },
    "F": {
        "keywords": [
            r"testimonial",
            r"success story",
            r"success stories",
            r"lives changed",
            r"impact story",
            r"impact stories",
            r"client story",
        ],
        "methodology_type": "Anecdotal only",
        "score_modifier": -3,
    },
}

# Third-party verification source patterns
VERIFICATION_PATTERNS = {
    "tier_1_gold": {
        "sources": [
            r"\bj-pal\b",
            r"jameel poverty action lab",
            r"\bgivewell\b",
            r"give well",
            r"\bidinsight\b",
            r"\bipa\b",
            r"innovations for poverty action",
            r"\b3ie\b",
            r"international initiative for impact evaluation",
        ],
        "boost": 1.0,
    },
    "tier_2_strong": {
        "sources": [
            r"external evaluation",
            r"external evaluator",
            r"independent audit",
            r"program audit",
            r"academic research",
            r"university partner",
            r"research partner",
            r"government evaluation",
        ],
        "boost": 0.5,
    },
    "tier_3_moderate": {
        "sources": [
            r"charity navigator.*site visit",
            r"bbb wise giving",
            r"give\.org",
            r"accredited",
            r"certified",
        ],
        "boost": 0.0,
    },
}


def load_benchmarks() -> dict:
    """Load cost-effectiveness benchmarks from config."""
    config_path = Path(__file__).parent.parent.parent / "config" / "cost_benchmarks.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def calculate_evidence_grade(
    text_content: str,
    pdf_content: Optional[str] = None,
    website_content: Optional[str] = None,
) -> EvidenceQualityResult:
    """
    Calculate evidence quality grade from available text content.

    Searches for methodology keywords in:
    - Annual report text
    - Website pages (especially impact/results pages)
    - PDF documents

    Returns:
        EvidenceQualityResult with grade A-F and score modifier
    """
    # Combine all text content
    all_text = text_content.lower()
    if pdf_content:
        all_text += " " + pdf_content.lower()
    if website_content:
        all_text += " " + website_content.lower()

    sources = []
    if text_content:
        sources.append("parsed data")
    if pdf_content:
        sources.append("PDF documents")
    if website_content:
        sources.append("website")

    # Search for evidence patterns in priority order (A first)
    for grade in ["A", "B", "C", "D", "E", "F"]:
        pattern_info = EVIDENCE_PATTERNS[grade]
        for keyword in pattern_info["keywords"]:
            if re.search(keyword, all_text, re.IGNORECASE):
                return EvidenceQualityResult(
                    grade=grade,
                    methodology_type=pattern_info["methodology_type"],
                    sources=sources,
                    rationale=f"Found '{keyword}' indicating {pattern_info['methodology_type']} methodology",
                    score_modifier=pattern_info["score_modifier"],
                )

    # Default to E (self-reported) if no methodology keywords found
    return EvidenceQualityResult(
        grade="E",
        methodology_type="Self-reported outcomes",
        sources=sources,
        rationale="No explicit methodology mentioned; defaulting to self-reported outcomes",
        score_modifier=-2,
    )


def calculate_verification_status(
    text_content: str,
    pdf_content: Optional[str] = None,
    website_content: Optional[str] = None,
    givewell_top_charity: bool = False,
) -> ThirdPartyVerificationResult:
    """
    Check for third-party verification mentions.

    Tier 1 (gold): J-PAL, GiveWell, IDinsight, IPA, 3ie
    Tier 2 (strong): External evaluation, academic research, government
    Tier 3 (moderate): Accreditation, industry certification

    Returns:
        ThirdPartyVerificationResult with verification status
    """
    # Special case: GiveWell top charity
    if givewell_top_charity:
        return ThirdPartyVerificationResult(
            verified=True,
            sources=["GiveWell"],
            verification_type="independent_evaluation",
            tier="tier_1_gold",
            score_boost=1.0,
        )

    # Combine all text content
    all_text = text_content.lower()
    if pdf_content:
        all_text += " " + pdf_content.lower()
    if website_content:
        all_text += " " + website_content.lower()

    # Search for verification patterns in priority order
    for tier in ["tier_1_gold", "tier_2_strong", "tier_3_moderate"]:
        pattern_info = VERIFICATION_PATTERNS[tier]
        found_sources = []

        for pattern in pattern_info["sources"]:
            if re.search(pattern, all_text, re.IGNORECASE):
                # Extract the matched source name
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    found_sources.append(match.group(0).strip())

        if found_sources:
            return ThirdPartyVerificationResult(
                verified=tier in ["tier_1_gold", "tier_2_strong"],
                sources=found_sources,
                verification_type="independent_evaluation" if tier != "tier_3_moderate" else "accreditation",
                tier=tier,
                score_boost=pattern_info["boost"],
            )

    # No verification found
    return ThirdPartyVerificationResult(
        verified=False,
        sources=[],
        verification_type=None,
        tier=None,
        score_boost=0.0,
    )


def calculate_cost_benchmark(
    cause_area: str,
    program_expenses: Optional[float] = None,
    beneficiaries: Optional[int] = None,
    cost_per_beneficiary: Optional[float] = None,
    data_source: Optional[str] = None,
) -> CostBenchmarkResult:
    """
    Compare charity's cost-per-beneficiary to cause-area benchmarks.

    Args:
        cause_area: Cause area for benchmarking (HUMANITARIAN, MEDICAL_HEALTH, etc.)
        program_expenses: Total program expenses
        beneficiaries: Number of beneficiaries served
        cost_per_beneficiary: Pre-calculated cost (if available)
        data_source: Source of cost data

    Returns:
        CostBenchmarkResult with comparison to benchmarks
    """
    # Calculate cost per beneficiary if not provided
    if cost_per_beneficiary is None:
        if program_expenses and beneficiaries and beneficiaries > 0:
            cost_per_beneficiary = program_expenses / beneficiaries
        else:
            return CostBenchmarkResult(
                cause_area=cause_area,
                cost_per_beneficiary=None,
                benchmark_name="cost_per_beneficiary",
                benchmark_range=None,
                comparison="insufficient_data",
                ratio=None,
                data_source=data_source,
            )

    # Load benchmarks
    benchmarks = load_benchmarks()
    area_benchmarks = benchmarks.get("benchmarks", {}).get(cause_area, {})

    if not area_benchmarks:
        # No benchmark for this cause area
        return CostBenchmarkResult(
            cause_area=cause_area,
            cost_per_beneficiary=cost_per_beneficiary,
            benchmark_name="cost_per_beneficiary",
            benchmark_range=None,
            comparison="insufficient_data",
            ratio=None,
            data_source=data_source,
        )

    # Get the first available benchmark metric
    metrics = area_benchmarks.get("metrics", {})
    benchmark_name = "cost_per_beneficiary"
    benchmark_range = None

    for metric_name, metric_data in metrics.items():
        if "good" in metric_data:
            benchmark_name = metric_name
            benchmark_range = metric_data["good"]
            break

    if not benchmark_range:
        return CostBenchmarkResult(
            cause_area=cause_area,
            cost_per_beneficiary=cost_per_beneficiary,
            benchmark_name=benchmark_name,
            benchmark_range=None,
            comparison="insufficient_data",
            ratio=None,
            data_source=data_source,
        )

    # Compare to benchmark
    low, high = benchmark_range[0], benchmark_range[1]
    midpoint = (low + high) / 2 if high else low

    if cost_per_beneficiary <= low:
        comparison = "better_than_benchmark"  # Lower cost = more efficient
    elif cost_per_beneficiary <= high if high else cost_per_beneficiary <= low * 1.5:
        comparison = "at_benchmark"
    else:
        comparison = "worse_than_benchmark"  # Higher cost = less efficient

    ratio = cost_per_beneficiary / midpoint if midpoint > 0 else None

    return CostBenchmarkResult(
        cause_area=cause_area,
        cost_per_beneficiary=cost_per_beneficiary,
        benchmark_name=benchmark_name,
        benchmark_range=benchmark_range,
        comparison=comparison,
        ratio=ratio,
        data_source=data_source,
    )


def apply_evidence_modifiers(
    base_delivery_score: int,
    evidence_grade: str,
    third_party_verified: bool,
    verification_tier: Optional[str] = None,
) -> int:
    """
    Apply evidence quality modifiers to delivery_evidence score.

    Modifiers:
    - Grade A: +2 points (capped at max 12)
    - Grade B: +1 point
    - Grade C: 0 (baseline)
    - Grade D: -1 point
    - Grade E: -2 points
    - Grade F: -3 points
    - Third-party tier_1 verification: +1 point

    Args:
        base_delivery_score: Base delivery_evidence score (0-12)
        evidence_grade: Evidence quality grade (A-F)
        third_party_verified: Whether verified by third party
        verification_tier: Verification tier (for tier_1 boost)

    Returns:
        Adjusted score clamped to 0-12
    """
    grade_modifiers = {
        "A": 2,
        "B": 1,
        "C": 0,
        "D": -1,
        "E": -2,
        "F": -3,
    }

    modifier = grade_modifiers.get(evidence_grade, 0)

    # Tier 1 verification boost
    if third_party_verified and verification_tier == "tier_1_gold":
        modifier += 1

    adjusted = base_delivery_score + modifier
    return max(0, min(12, adjusted))


@dataclass
class EvidenceBasedGivingScores:
    """Combined evidence-based giving assessment."""

    evidence_quality: EvidenceQualityResult
    verification: ThirdPartyVerificationResult
    cost_benchmark: CostBenchmarkResult
    adjusted_delivery_score: Optional[int]

    def to_prompt_section(self) -> str:
        """Format as a section to inject into the LLM prompt."""
        lines = [
            "## EVIDENCE-BASED GIVING ASSESSMENT",
            "",
            "### Evidence Quality Grade",
            f"**Grade: {self.evidence_quality.grade}** ({self.evidence_quality.methodology_type})",
            f"Rationale: {self.evidence_quality.rationale}",
            f"Score modifier: {self.evidence_quality.score_modifier:+d} to delivery_evidence",
            "",
            "### Third-Party Verification",
            f"**Verified: {'Yes' if self.verification.verified else 'No'}**",
        ]

        if self.verification.verified:
            lines.extend([
                f"Sources: {', '.join(self.verification.sources)}",
                f"Tier: {self.verification.tier}",
            ])

        lines.extend([
            "",
            "### Cost-Effectiveness Benchmark",
            f"**Cause Area: {self.cost_benchmark.cause_area}**",
        ])

        if self.cost_benchmark.cost_per_beneficiary:
            lines.append(f"Cost per beneficiary: ${self.cost_benchmark.cost_per_beneficiary:.2f}")
            lines.append(f"Comparison: {self.cost_benchmark.comparison}")
            if self.cost_benchmark.ratio:
                lines.append(f"Ratio to benchmark: {self.cost_benchmark.ratio:.2f}x")
        else:
            lines.append("Cost data: insufficient")

        lines.append("")

        return "\n".join(lines)


def calculate_evidence_based_scores(
    text_content: str,
    cause_area: str,
    program_expenses: Optional[float] = None,
    beneficiaries: Optional[int] = None,
    cost_per_beneficiary: Optional[float] = None,
    pdf_content: Optional[str] = None,
    website_content: Optional[str] = None,
    givewell_top_charity: bool = False,
    base_delivery_score: int = 6,
) -> EvidenceBasedGivingScores:
    """
    Calculate all evidence-based giving scores.

    Args:
        text_content: Main text content to analyze
        cause_area: Cause area for benchmarking
        program_expenses: Total program expenses
        beneficiaries: Number of beneficiaries served
        cost_per_beneficiary: Pre-calculated cost (if available)
        pdf_content: Optional PDF text content
        website_content: Optional website text content
        givewell_top_charity: Whether this is a GiveWell top charity
        base_delivery_score: Base delivery_evidence score before modifiers

    Returns:
        EvidenceBasedGivingScores with all assessments
    """
    evidence = calculate_evidence_grade(text_content, pdf_content, website_content)
    verification = calculate_verification_status(
        text_content, pdf_content, website_content, givewell_top_charity
    )
    benchmark = calculate_cost_benchmark(
        cause_area, program_expenses, beneficiaries, cost_per_beneficiary
    )

    adjusted = apply_evidence_modifiers(
        base_delivery_score,
        evidence.grade,
        verification.verified,
        verification.tier,
    )

    return EvidenceBasedGivingScores(
        evidence_quality=evidence,
        verification=verification,
        cost_benchmark=benchmark,
        adjusted_delivery_score=adjusted,
    )

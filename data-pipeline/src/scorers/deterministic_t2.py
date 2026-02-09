"""
Deterministic Tier 2 scoring - calculates sub-scores from database data.

The LLM should NEVER do math or score things that can be calculated deterministically.
This module pre-calculates scores from hard data, which are then passed to the LLM
as immutable facts.

Deterministic sub-scores:
- governance (0-8): from CN accountability score
- program_efficiency (0-8): from program expense ratio
- deployment_capacity (0-6): from total revenue
- track_record (0-3): from founding year (if available)

LLM-judged sub-scores (NOT calculated here):
- delivery_evidence (0-12): qualitative assessment of mission delivery
- cost_effectiveness (0-8): only if no data; otherwise could be calculated
- learning_adaptation (0-5): qualitative assessment of iteration/improvement
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DeterministicT2Scores:
    """Pre-calculated Tier 2 sub-scores from database data."""

    # Operational Capability sub-scores
    governance: int  # 0-8
    governance_rationale: str
    program_efficiency: int  # 0-8
    program_efficiency_rationale: str
    deployment_capacity: int  # 0-6
    deployment_capacity_rationale: str
    track_record: Optional[int]  # 0-3, None if no founding year
    track_record_rationale: Optional[str]

    # Totals
    operational_capability_deterministic: int  # Sum of above (max 25 if track_record known)

    def to_prompt_section(self) -> str:
        """Format as a section to inject into the LLM prompt."""
        lines = [
            "## PRE-CALCULATED SCORES (DO NOT CHANGE)",
            "",
            "The following Tier 2 sub-scores have been calculated from verified data.",
            "You MUST use these exact scores. Do NOT recalculate or adjust them.",
            "Your job is to write rationales that explain these scores, not to change them.",
            "",
            "### Operational Capability (deterministic sub-scores)",
            "",
            f"**governance: {self.governance}/8**",
            f"  Data: {self.governance_rationale}",
            "",
            f"**program_efficiency: {self.program_efficiency}/8**",
            f"  Data: {self.program_efficiency_rationale}",
            "",
            f"**deployment_capacity: {self.deployment_capacity}/6**",
            f"  Data: {self.deployment_capacity_rationale}",
            "",
        ]

        if self.track_record is not None:
            lines.extend([
                f"**track_record: {self.track_record}/3**",
                f"  Data: {self.track_record_rationale}",
                "",
            ])
        else:
            lines.extend([
                "**track_record: [LLM TO ASSESS]**",
                "  No founding year data available. Assess from other sources (0-3 points).",
                "",
            ])

        lines.extend([
            "### Mission Delivery (LLM to assess)",
            "",
            "You must assess these qualitative sub-scores based on available evidence:",
            "- delivery_evidence (0-12): Is there measurable evidence of mission delivery?",
            "- cost_effectiveness (0-8): Is the cost per outcome competitive?",
            "- learning_adaptation (0-5): Do they iterate based on data?",
            "",
        ])

        return "\n".join(lines)


def calculate_governance_score(accountability_score: Optional[float]) -> tuple[int, str]:
    """
    Calculate governance sub-score from CN accountability score.

    Rubric:
    - 95+ = 8 points (EXCELLENT)
    - 85-94 = 6 points (STRONG)
    - 70-84 = 4 points (ADEQUATE)
    - 50-69 = 2 points (WEAK)
    - <50 or None = 0 points (POOR/NO DATA)
    """
    if accountability_score is None:
        return 0, "No CN accountability score available"

    if accountability_score >= 95:
        return 8, f"CN accountability score {accountability_score:.0f}/100 (95+ = excellent)"
    elif accountability_score >= 85:
        return 6, f"CN accountability score {accountability_score:.0f}/100 (85-94 = strong)"
    elif accountability_score >= 70:
        return 4, f"CN accountability score {accountability_score:.0f}/100 (70-84 = adequate)"
    elif accountability_score >= 50:
        return 2, f"CN accountability score {accountability_score:.0f}/100 (50-69 = weak)"
    else:
        return 0, f"CN accountability score {accountability_score:.0f}/100 (<50 = poor)"


def calculate_program_efficiency_score(program_expense_ratio: Optional[float]) -> tuple[int, str]:
    """
    Calculate program efficiency sub-score from program expense ratio.

    Rubric:
    - 85%+ = 8 points (EXCELLENT)
    - 80-84% = 6 points (STRONG)
    - 75-79% = 4 points (ADEQUATE)
    - 65-74% = 2 points (BELOW AVG)
    - <65% or None = 0 points (POOR/NO DATA)
    """
    if program_expense_ratio is None:
        return 0, "No program expense ratio available"

    # Convert to percentage if it's a decimal
    pct = program_expense_ratio * 100 if program_expense_ratio <= 1 else program_expense_ratio

    if pct >= 85:
        return 8, f"Program expense ratio {pct:.1f}% (85%+ = excellent)"
    elif pct >= 80:
        return 6, f"Program expense ratio {pct:.1f}% (80-84% = strong)"
    elif pct >= 75:
        return 4, f"Program expense ratio {pct:.1f}% (75-79% = adequate)"
    elif pct >= 65:
        return 2, f"Program expense ratio {pct:.1f}% (65-74% = below average)"
    else:
        return 0, f"Program expense ratio {pct:.1f}% (<65% = poor)"


def calculate_deployment_capacity_score(total_revenue: Optional[float]) -> tuple[int, str]:
    """
    Calculate deployment capacity sub-score from total revenue.

    Rubric:
    - $25M+ = 6 points (HIGH capacity)
    - $5-25M = 4 points (MEDIUM capacity)
    - $1-5M = 2 points (LOW capacity)
    - <$1M or None = 0 points (MINIMAL capacity)
    """
    if total_revenue is None:
        return 0, "No revenue data available"

    if total_revenue >= 25_000_000:
        return 6, f"Revenue ${total_revenue/1_000_000:.1f}M ($25M+ = high capacity)"
    elif total_revenue >= 5_000_000:
        return 4, f"Revenue ${total_revenue/1_000_000:.1f}M ($5-25M = medium capacity)"
    elif total_revenue >= 1_000_000:
        return 2, f"Revenue ${total_revenue/1_000_000:.1f}M ($1-5M = low capacity)"
    else:
        return 0, f"Revenue ${total_revenue/1_000:.0f}K (<$1M = minimal capacity)"


def calculate_track_record_score(founding_year: Optional[int], current_year: int = 2024) -> tuple[Optional[int], Optional[str]]:
    """
    Calculate track record sub-score from founding year.

    Rubric:
    - 10+ years = 3 points (PROVEN)
    - 5-10 years = 2 points (ESTABLISHED)
    - 2-5 years = 1 point (EMERGING)
    - <2 years = 0 points (NEW)
    - None = None (let LLM assess)
    """
    if founding_year is None:
        return None, None

    years = current_year - founding_year

    if years >= 10:
        return 3, f"Founded {founding_year}, operating {years} years (10+ = proven)"
    elif years >= 5:
        return 2, f"Founded {founding_year}, operating {years} years (5-10 = established)"
    elif years >= 2:
        return 1, f"Founded {founding_year}, operating {years} years (2-5 = emerging)"
    else:
        return 0, f"Founded {founding_year}, operating {years} years (<2 = new)"


def calculate_deterministic_t2_scores(
    accountability_score: Optional[float],
    program_expense_ratio: Optional[float],
    total_revenue: Optional[float],
    founding_year: Optional[int] = None,
) -> DeterministicT2Scores:
    """
    Calculate all deterministic Tier 2 sub-scores from database data.

    Args:
        accountability_score: CN accountability score (0-100)
        program_expense_ratio: Program expense ratio (0-1 or 0-100)
        total_revenue: Total annual revenue in dollars
        founding_year: Year organization was founded (optional)

    Returns:
        DeterministicT2Scores with all calculated values
    """
    gov_score, gov_rationale = calculate_governance_score(accountability_score)
    prog_score, prog_rationale = calculate_program_efficiency_score(program_expense_ratio)
    deploy_score, deploy_rationale = calculate_deployment_capacity_score(total_revenue)
    track_score, track_rationale = calculate_track_record_score(founding_year)

    # Calculate deterministic total
    deterministic_total = gov_score + prog_score + deploy_score
    if track_score is not None:
        deterministic_total += track_score

    return DeterministicT2Scores(
        governance=gov_score,
        governance_rationale=gov_rationale,
        program_efficiency=prog_score,
        program_efficiency_rationale=prog_rationale,
        deployment_capacity=deploy_score,
        deployment_capacity_rationale=deploy_rationale,
        track_record=track_score,
        track_record_rationale=track_rationale,
        operational_capability_deterministic=deterministic_total,
    )

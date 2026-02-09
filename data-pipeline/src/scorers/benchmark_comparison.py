"""
Benchmark Comparison - compares charities against GiveWell gold standard benchmarks.

Uses cohort analysis to compare Muslim charities to GiveWell top charities
in similar cause areas (health, cash/zakat, nutrition, humanitarian).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class BenchmarkComparison:
    """Result of comparing a charity to its benchmark cohort."""

    cohort_name: str  # health_medical, cash_zakat, nutrition_food, humanitarian
    benchmark_charity: str  # e.g., "Against Malaria Foundation"
    benchmark_ein: str
    benchmark_metric: str  # e.g., "cost_per_life_saved"
    benchmark_value: float
    charity_value: Optional[float]
    ratio: Optional[float]  # charity_value / benchmark_value
    comparison: str  # better, comparable, worse, insufficient_data
    context: str  # Human-readable explanation


def load_benchmark_config() -> dict:
    """Load benchmark configuration from YAML."""
    config_path = Path(__file__).parent.parent.parent / "config" / "cost_benchmarks.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def get_benchmark_for_cause_area(cause_area: str) -> Optional[dict]:
    """
    Get the benchmark charity for a given cause area.

    Args:
        cause_area: MEDICAL_HEALTH, BASIC_NEEDS, HUMANITARIAN, etc.

    Returns:
        Benchmark cohort data or None
    """
    config = load_benchmark_config()
    cohorts = config.get("benchmark_cohorts", {})

    # Map cause areas to cohort names
    cause_to_cohort = {
        "MEDICAL_HEALTH": "health_medical",
        "BASIC_NEEDS": "cash_zakat",  # Cash/zakat is closest
        "HUMANITARIAN": "humanitarian",
        "EDUCATION_K12": None,  # No GiveWell benchmark
        "EDUCATION_HIGHER": None,
        "ISLAMIC_EDUCATION": None,
        "ORPHAN_SUPPORT": None,
        "CIVIL_RIGHTS_LEGAL": None,
        "ECONOMIC_DEVELOPMENT": None,
    }

    # Also check nutrition for food-related
    cohort_name = cause_to_cohort.get(cause_area)
    if cohort_name and cohort_name in cohorts:
        return cohorts[cohort_name]

    return None


def get_givewell_charity(ein: str) -> Optional[dict]:
    """
    Check if a charity is a GiveWell top charity.

    Args:
        ein: EIN to check

    Returns:
        GiveWell charity data or None
    """
    config = load_benchmark_config()
    charities = config.get("givewell_top_charities", [])

    ein_normalized = ein.replace("-", "")
    for charity in charities:
        charity_ein = charity.get("ein", "").replace("-", "")
        if charity_ein == ein_normalized:
            return charity

    return None


def is_benchmark_charity(ein: str) -> bool:
    """Check if a charity is a designated benchmark."""
    charity = get_givewell_charity(ein)
    return charity.get("is_benchmark", False) if charity else False


def compare_to_benchmark(
    ein: str,
    cause_area: str,
    cost_per_beneficiary: Optional[float] = None,
    program_expense_ratio: Optional[float] = None,
) -> Optional[BenchmarkComparison]:
    """
    Compare a charity's metrics to its benchmark cohort.

    Args:
        ein: Charity EIN
        cause_area: Cause area for finding comparable benchmark
        cost_per_beneficiary: Charity's cost per beneficiary
        program_expense_ratio: Charity's program expense ratio

    Returns:
        BenchmarkComparison with analysis, or None if no benchmark
    """
    # Check if this charity IS a benchmark
    if is_benchmark_charity(ein):
        gw = get_givewell_charity(ein)
        return BenchmarkComparison(
            cohort_name="benchmark",
            benchmark_charity=gw["name"],
            benchmark_ein=ein,
            benchmark_metric="self",
            benchmark_value=0,
            charity_value=None,
            ratio=None,
            comparison="is_benchmark",
            context=f"This is a GiveWell top charity used as a benchmark ({gw.get('cash_multiplier', 'N/A')}x as effective as cash transfers).",
        )

    # Get benchmark for this cause area
    cohort = get_benchmark_for_cause_area(cause_area)
    if not cohort:
        return None

    benchmark = cohort.get("benchmark_charity", {})
    benchmark_name = benchmark.get("name", "Unknown")
    benchmark_ein = benchmark.get("ein", "")

    # Determine which metric to compare
    if cost_per_beneficiary and benchmark.get("cost_per_life_saved"):
        benchmark_value = benchmark.get("cost_per_life_saved")
        ratio = cost_per_beneficiary / benchmark_value if benchmark_value else None

        if ratio is None:
            comparison = "insufficient_data"
            context = "Insufficient data for comparison."
        elif ratio <= 0.5:
            comparison = "better"
            context = f"Significantly more efficient than {benchmark_name} ({ratio:.1f}x the cost-effectiveness)."
        elif ratio <= 1.5:
            comparison = "comparable"
            context = f"Comparable efficiency to {benchmark_name} (within 50% of benchmark)."
        elif ratio <= 3.0:
            comparison = "worse"
            context = f"Less efficient than {benchmark_name} ({ratio:.1f}x higher cost per outcome)."
        else:
            comparison = "worse"
            context = f"Significantly less efficient than {benchmark_name} ({ratio:.1f}x higher cost). May indicate different intervention type or scope."

        return BenchmarkComparison(
            cohort_name=_get_cohort_name(cause_area),
            benchmark_charity=benchmark_name,
            benchmark_ein=benchmark_ein,
            benchmark_metric="cost_per_beneficiary",
            benchmark_value=benchmark_value,
            charity_value=cost_per_beneficiary,
            ratio=ratio,
            comparison=comparison,
            context=context,
        )

    # Compare program expense ratio for cash/zakat cohort
    if program_expense_ratio and cause_area == "BASIC_NEEDS":
        benchmark_efficiency = benchmark.get("transfer_efficiency", 0.90)

        if program_expense_ratio >= benchmark_efficiency:
            comparison = "better"
            context = f"Transfer efficiency ({program_expense_ratio:.0%}) meets or exceeds GiveDirectly benchmark ({benchmark_efficiency:.0%})."
        elif program_expense_ratio >= 0.75:
            comparison = "comparable"
            context = f"Good transfer efficiency ({program_expense_ratio:.0%}), within range of benchmark ({benchmark_efficiency:.0%})."
        else:
            comparison = "worse"
            context = f"Lower transfer efficiency ({program_expense_ratio:.0%}) than GiveDirectly benchmark ({benchmark_efficiency:.0%})."

        return BenchmarkComparison(
            cohort_name="cash_zakat",
            benchmark_charity="GiveDirectly",
            benchmark_ein="27-1661997",
            benchmark_metric="transfer_efficiency",
            benchmark_value=benchmark_efficiency,
            charity_value=program_expense_ratio,
            ratio=program_expense_ratio / benchmark_efficiency if benchmark_efficiency else None,
            comparison=comparison,
            context=context,
        )

    return None


def _get_cohort_name(cause_area: str) -> str:
    """Map cause area to cohort name."""
    mapping = {
        "MEDICAL_HEALTH": "health_medical",
        "BASIC_NEEDS": "cash_zakat",
        "HUMANITARIAN": "humanitarian",
    }
    return mapping.get(cause_area, "general")


def get_benchmark_context_for_prompt(
    ein: str,
    cause_area: str,
    cost_per_beneficiary: Optional[float] = None,
    program_expense_ratio: Optional[float] = None,
) -> str:
    """
    Generate benchmark context section for LLM prompt.

    Returns a formatted string to inject into the narrative prompt.
    """
    comparison = compare_to_benchmark(
        ein, cause_area, cost_per_beneficiary, program_expense_ratio
    )

    if not comparison:
        return ""

    lines = [
        "## BENCHMARK COMPARISON",
        "",
        f"**Cohort:** {comparison.cohort_name}",
        f"**Benchmark Charity:** {comparison.benchmark_charity}",
    ]

    if comparison.comparison == "is_benchmark":
        lines.append("**Status:** This IS a GiveWell benchmark charity")
        lines.append(f"**Context:** {comparison.context}")
    else:
        lines.append(f"**Benchmark {comparison.benchmark_metric}:** {comparison.benchmark_value}")
        if comparison.charity_value:
            lines.append(f"**This Charity:** {comparison.charity_value}")
        if comparison.ratio:
            lines.append(f"**Ratio:** {comparison.ratio:.2f}x")
        lines.append(f"**Comparison:** {comparison.comparison}")
        lines.append(f"**Context:** {comparison.context}")

    lines.append("")

    return "\n".join(lines)

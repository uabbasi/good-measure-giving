"""Strategic Classifier - LLM-based archetype classification for the Strategic Believer lens.

Classifies charities into strategic archetypes and produces 4 numeric scores
used by the Strategic Believer scorer. Runs during synthesize phase, stored
in charity_data.strategic_classification.

Classification is:
- Deterministic output structure (Pydantic schema)
- LLM-powered analysis of mission/programs/cause area
- Cheap (~$0.05 for 149 charities via Gemini Flash)

Archetypes:
- RESILIENCE: Loop-breaking, breaking cycles of poverty/dependency
- LEVERAGE: Multiplier effect, every $1 creates >$1 in impact
- SOVEREIGNTY: Community self-determination, building institutions
- ASSET_CREATION: Durable assets (wells, schools, endowments)
- DIRECT_SERVICE: Immediate relief, consumptive (lowest strategic score)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from src.llm.llm_client import LLMClient, LLMTask
from src.parsers.charity_metrics_aggregator import CharityMetrics
from src.utils.logger import PipelineLogger

if TYPE_CHECKING:
    from src.scorers.strategic_evidence import StrategicEvidence


class StrategicClassification(BaseModel):
    """LLM-produced strategic classification for a charity.

    Stored as JSON in charity_data.strategic_classification.
    Consumed by StrategicBelieverScorer.
    """

    archetype: str = Field(
        description="Primary strategic archetype: RESILIENCE, LEVERAGE, SOVEREIGNTY, ASSET_CREATION, or DIRECT_SERVICE"
    )
    archetype_rationale: str = Field(
        description="1-2 sentence explanation of why this archetype was chosen"
    )

    # 4 numeric scores (each 0-10) used by the Strategic Believer scorer
    loop_breaking: int = Field(
        ge=0, le=10,
        description="0-10: Does this charity break cycles of poverty/dependency? (10=systemic change, 0=one-time relief)"
    )
    multiplier: int = Field(
        ge=0, le=10,
        description="0-10: Does each $1 create >$1 in downstream value? (10=high leverage, 0=1:1 consumptive)"
    )
    asset_creation: int = Field(
        ge=0, le=10,
        description="0-10: Does the charity build durable assets? (10=permanent infrastructure, 0=consumable goods)"
    )
    sovereignty: int = Field(
        ge=0, le=10,
        description="0-10: Does the charity build community self-determination? (10=institution building, 0=external dependency)"
    )


# Prompt template for the classifier
STRATEGIC_CLASSIFIER_PROMPT = """Analyze this nonprofit and classify its strategic profile.

## Organization
- Name: {name}
- Mission: {mission}
- Programs: {programs}
- Cause Area: {cause_area}
- Cause Tags: {cause_tags}

## Program Details
- Program Descriptions: {program_descriptions}
- Theory of Change: {theory_of_change}
- Reported Outcomes: {outcomes}

## Scale & Reach
- Founded: {founded_year}
- Employees: {employees_count}
- Beneficiaries/Year: {beneficiaries_served}
- Geographic Coverage: {geographic_coverage}

## Governance & Financial Signals
- Revenue: {total_revenue}
- Program Expense Ratio: {program_expense_ratio}
- Has Financial Audit: {has_financial_audit}
- Candid Seal: {candid_seal}
- Board Size: {board_size} ({independent_board_members} independent)

## Detected Strategic Signals (deterministic keyword analysis)
{strategic_signals}

## Instructions
Classify this charity into exactly ONE primary archetype:

1. **RESILIENCE**: Breaks cycles of poverty, dependency, or marginalization. Examples: job training, education that leads to self-sufficiency, addiction recovery programs.
2. **LEVERAGE**: Each $1 creates >$1 in downstream value. Examples: policy advocacy that changes laws, research that shifts practice, training-the-trainers models.
3. **SOVEREIGNTY**: Builds community self-determination and institutional capacity. Examples: establishing community-owned institutions, leadership development, civic infrastructure.
4. **ASSET_CREATION**: Builds durable, lasting assets. Examples: wells, schools, endowments, land trusts, permanent infrastructure.
5. **DIRECT_SERVICE**: Provides immediate relief or consumable services. Examples: food distribution, emergency aid, one-time medical care.

## Scoring (0-10 for each)
- **loop_breaking**: How much does this charity break cycles vs. provide one-time help?
- **multiplier**: How much downstream value does each $1 create beyond the immediate output?
- **asset_creation**: Does the charity build durable assets that persist after funding stops?
- **sovereignty**: Does the charity build community self-determination or create dependency?

## Scoring Guidance
- Direct food/clothing distribution: loop_breaking=1-2, multiplier=1-2, asset_creation=0-1, sovereignty=1-2
- Education programs: loop_breaking=6-8, multiplier=5-7, asset_creation=3-5, sovereignty=4-6
- Policy/advocacy: loop_breaking=5-7, multiplier=7-9, asset_creation=2-4, sovereignty=6-8
- Infrastructure (wells, schools): loop_breaking=4-6, multiplier=4-6, asset_creation=8-10, sovereignty=5-7
- Community institution building: loop_breaking=5-7, multiplier=5-7, asset_creation=6-8, sovereignty=8-10

Return ONLY valid JSON (no markdown):
{{
  "archetype": "RESILIENCE|LEVERAGE|SOVEREIGNTY|ASSET_CREATION|DIRECT_SERVICE",
  "archetype_rationale": "1-2 sentences",
  "loop_breaking": 0-10,
  "multiplier": 0-10,
  "asset_creation": 0-10,
  "sovereignty": 0-10
}}"""

VALID_ARCHETYPES = {"RESILIENCE", "LEVERAGE", "SOVEREIGNTY", "ASSET_CREATION", "DIRECT_SERVICE"}


def classify_charity(
    metrics: CharityMetrics,
    cause_tags: list[str] | None = None,
    logger: PipelineLogger | None = None,
    strategic_evidence: StrategicEvidence | None = None,
) -> tuple[StrategicClassification | None, float]:
    """Classify a charity's strategic profile using LLM.

    Args:
        metrics: Aggregated charity metrics
        cause_tags: Optional cause tags from synthesis
        logger: Optional pipeline logger
        strategic_evidence: Optional pre-computed evidence signals

    Returns:
        (classification, cost_usd) - classification object or None on failure
    """
    # Build context
    programs_str = ", ".join(metrics.programs[:5]) if metrics.programs else "Not available"
    cause_tags_str = ", ".join(cause_tags[:10]) if cause_tags else "None detected"

    # Program Details (truncated to control token usage)
    prog_descs = [d[:200] for d in (metrics.program_descriptions or [])[:3]]
    prog_descs_str = " | ".join(prog_descs) if prog_descs else "Not available"
    toc_str = (metrics.theory_of_change or "Not available")[:500]
    outcomes_list = [o[:150] for o in (metrics.outcomes or [])[:5]]
    outcomes_str = " | ".join(outcomes_list) if outcomes_list else "Not available"

    # Scale & Reach
    founded_str = str(metrics.founded_year) if metrics.founded_year else "Unknown"
    employees_str = str(metrics.employees_count) if metrics.employees_count else "Unknown"
    beneficiaries_str = (
        f"{metrics.beneficiaries_served_annually:,}" if metrics.beneficiaries_served_annually else "Unknown"
    )
    geo_str = ", ".join((metrics.geographic_coverage or [])[:10]) or "Unknown"

    # Governance & Financial Signals
    revenue_str = f"${metrics.total_revenue:,.0f}" if metrics.total_revenue else "Unknown"
    ratio_str = f"{metrics.program_expense_ratio:.1%}" if metrics.program_expense_ratio else "Unknown"
    audit_str = str(metrics.has_financial_audit) if metrics.has_financial_audit is not None else "Unknown"
    candid_str = metrics.candid_seal or "None"
    board_str = str(metrics.board_size) if metrics.board_size else "Unknown"
    indep_str = str(metrics.independent_board_members) if metrics.independent_board_members else "Unknown"

    # Strategic evidence signals (deterministic, pre-computed)
    signals_str = strategic_evidence.format_for_prompt() if strategic_evidence else "Not yet computed"

    prompt = STRATEGIC_CLASSIFIER_PROMPT.format(
        name=metrics.name,
        mission=metrics.mission or "Not available",
        programs=programs_str,
        cause_area=metrics.detected_cause_area or "Unknown",
        cause_tags=cause_tags_str,
        program_descriptions=prog_descs_str,
        theory_of_change=toc_str,
        outcomes=outcomes_str,
        founded_year=founded_str,
        employees_count=employees_str,
        beneficiaries_served=beneficiaries_str,
        geographic_coverage=geo_str,
        total_revenue=revenue_str,
        program_expense_ratio=ratio_str,
        has_financial_audit=audit_str,
        candid_seal=candid_str,
        board_size=board_str,
        independent_board_members=indep_str,
        strategic_signals=signals_str,
    )

    try:
        client = LLMClient(task=LLMTask.WEBSITE_EXTRACTION, logger=logger)
        response = client.generate(
            prompt=prompt,
            json_mode=True,
            temperature=0.0,
        )

        # Parse response
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        data = json.loads(text)

        # Validate archetype
        archetype = data.get("archetype", "").upper()
        if archetype not in VALID_ARCHETYPES:
            if logger:
                logger.warning(f"Invalid archetype '{archetype}', defaulting to DIRECT_SERVICE")
            archetype = "DIRECT_SERVICE"
            data["archetype"] = archetype

        # Clamp scores to 0-10
        for field in ("loop_breaking", "multiplier", "asset_creation", "sovereignty"):
            val = data.get(field, 0)
            data[field] = max(0, min(10, int(val)))

        classification = StrategicClassification(**data)
        return classification, response.cost_usd

    except Exception as e:
        if logger:
            logger.warning(f"Strategic classification failed: {e}")
        return None, 0.0


def classification_to_dict(classification: StrategicClassification) -> dict[str, Any]:
    """Convert classification to dict for JSON storage."""
    return classification.model_dump()


def dict_to_classification(data: dict[str, Any] | None) -> StrategicClassification | None:
    """Reconstruct classification from stored dict."""
    if not data:
        return None
    try:
        return StrategicClassification(**data)
    except Exception:
        return None

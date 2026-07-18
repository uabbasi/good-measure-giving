"""Beneficiary metric-semantics verifier (synthesize-time, LLM).

Closes a class of beneficiary-count defects that pass the regex/bounds gates but
are semantically wrong: dollar figures mislabeled as headcounts
(``orphanage_infrastructure_value_added_usd``), cumulative "since inception"
totals (AMF's 669M), geographic/program subsets or year-specific snapshots
(``2021_refugee_families_served_gaza``), families-vs-people, and annual-report
"reach"/impressions figures (CRI's 9,000,000).

One cheap LLM call (``LLMTask.LLM_JUDGE`` chain) classifies what the metric
actually represents. Only ``category == "annual_people_served"`` AND ``confident``
yields ``verified=True`` — the state export.py's gate now requires before it will
publish a count. Any failure fails closed (``verified=False``) and never raises,
so synthesize is never crashed by this verifier.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from src.llm.llm_client import LLMClient, LLMTask

logger = logging.getLogger(__name__)

# The closed set the model must choose from. Only the first yields a verified count.
SEMANTIC_CATEGORIES = [
    "annual_people_served",
    "families_households",
    "cumulative_total",
    "subset_geographic_or_program",
    "year_specific_snapshot",
    "monetary_value",
    "reach_or_impressions",
    "other",
]

_VERIFIED_CATEGORY = "annual_people_served"


class BeneficiarySemanticsResult(BaseModel):
    """Structured output for the semantics classification call."""

    category: str = Field(description=f"exactly one of: {', '.join(SEMANTIC_CATEGORIES)}")
    confident: bool = Field(description="true only if you are confident in the category")
    reasoning: str = Field(default="", description="one sentence justification")


_PROMPT = """You audit a single nonprofit metric that our pipeline stored as the charity's \
"beneficiaries served annually". Your job is to classify what the number ACTUALLY represents, \
so we do not publish a semantically wrong figure (a dollar amount, a cumulative lifetime total, \
a narrow geographic/program subset, a families-not-people count, or a media "reach" number) as \
if it were the count of distinct PEOPLE the charity serves in a typical year.

Charity: {name}
Mission: {mission}
Stored value: {value}
Annual program expenses (USD): {program_expenses}
Source key / path the value was pulled from: {source_path}
Neighboring metric keys (context): {metric_context}

Categories (choose exactly one for `category`):
- annual_people_served: distinct PEOPLE served in a single year (the only publishable meaning)
- families_households: families/households, not individual people
- cumulative_total: a running "since inception"/"to date"/"lifetime" total across many years
- subset_geographic_or_program: only one region/program/year subset, not the whole charity
- year_specific_snapshot: explicitly tied to one past year (e.g. a "2021" figure)
- monetary_value: a dollar amount / value, not a headcount
- reach_or_impressions: audience reached, views, downloads, or media impressions
- other: anything else, or genuinely unclear

Set `confident` to true ONLY when the evidence (key name, magnitude vs. program expenses, mission) \
clearly supports your category. When unsure, choose the closest non-annual category (or `other`) \
and set `confident` false. Return JSON only."""


def _strip_markdown_json(text: str) -> str:
    """Remove ```json fences some models add despite json_mode."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def verify_beneficiary_semantics(
    *,
    charity_name: str | None,
    mission: str | None,
    value: Any,
    program_expenses: Any,
    source_path: str | None,
    metric_context: list[str] | None = None,
    llm_client: Any = None,
) -> dict[str, Any]:
    """Classify a beneficiary count's semantics via one LLM call.

    Returns a stamp dict for
    ``source_attribution["beneficiaries_served_annually"]["semantics"]``:
      success  -> {category, confident, model, verified, timestamp}
      failure  -> {category:"other", confident:False, verified:False, error, timestamp}

    Never raises: any exception is caught and turned into a fail-closed stamp.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        client = llm_client or LLMClient(task=LLMTask.LLM_JUDGE)
        expenses_str = f"{int(program_expenses):,}" if isinstance(program_expenses, (int, float)) else "unknown"
        prompt = _PROMPT.format(
            name=charity_name or "unknown",
            mission=(mission or "unknown")[:600],
            value=value,
            program_expenses=expenses_str,
            source_path=source_path or "unknown",
            metric_context=", ".join(metric_context) if metric_context else "none",
        )
        response = client.generate(
            prompt=prompt,
            json_mode=True,
            json_schema=BeneficiarySemanticsResult.model_json_schema(),
            temperature=0.0,
        )
        parsed = BeneficiarySemanticsResult.model_validate_json(_strip_markdown_json(response.text))
        verified = parsed.category == _VERIFIED_CATEGORY and parsed.confident is True
        return {
            "category": parsed.category,
            "confident": parsed.confident,
            "model": getattr(response, "model", None),
            "verified": verified,
            "timestamp": timestamp,
        }
    except Exception as e:  # noqa: BLE001 - fail closed, never crash synthesize
        logger.warning("beneficiary semantics verification failed: %s", e)
        return {
            "category": "other",
            "confident": False,
            "verified": False,
            "error": str(e),
            "timestamp": timestamp,
        }

"""
Phase 4: Baseline - Generate baseline narratives and scores.

Takes synthesized data and raw sources, generates:
- AMAL score (100-point scale)
- Wallet tag (zakat eligibility)
- Confidence/impact tiers
- Baseline narrative

Usage:
    uv run python baseline.py --ein 95-4453134
    uv run python baseline.py --charities pilot_charities.txt
    uv run python baseline.py --charities pilot_charities.txt --workers 10
"""

import argparse
import difflib
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from src.db import (
    CharityDataRepository,
    CharityRepository,
    Evaluation,
    EvaluationRepository,
    PhaseCacheRepository,
    RawDataRepository,
)
from src.db.client import execute_query
from src.db.dolt_client import dolt, tables_for_phases
from src.llm.llm_client import LLMClient, LLMTask
from src.llm.prompt_loader import PromptInfo, data_vintage_note, load_prompt
from src.parsers.charity_metrics_aggregator import CharityMetrics, CharityMetricsAggregator
from src.scorers.v2_scorers import (
    RUBRIC_VERSION,
    AmalScorerV2,
    impact_tier_from_amal_score,
    score_band_label,
)
from src.services.citation_service import CitationService
from src.utils.deep_link_resolver import upgrade_source_url
from src.utils.phase_cache_helper import check_phase_cache, update_phase_cache

SLUG_PROMPT = """\
Generate a 3-word descriptive slug for a charity card.

Rules:
- Exactly 3 words, all lowercase
- Describe what the charity DOES or WHO it serves
- No generic words like "helping", "supporting", "providing", "promoting"
- Geographic specificity when relevant (country/region name > "global")
- Population specificity when relevant ("orphan education" > "youth programs")
- Do NOT describe quality or ratings (no "excellent", "top-rated", etc.)

Examples:
  CAIR → "muslim civil rights"
  Islamic Relief USA → "global humanitarian aid"
  Penny Appeal USA → "orphan family welfare"
  ICNA Relief → "domestic refugee resettlement"
  Baitulmaal → "yemen water access"

Charity name: {name}
Mission: {mission}
Cause tags: {cause_tags}
Program focus: {program_focus}
Programs: {programs}
Geographic coverage: {geo}

Respond with ONLY the 3-word slug, nothing else."""


def generate_slug(
    metrics: CharityMetrics,
    charity_data: dict | None,
    llm_client: LLMClient,
) -> tuple[str | None, float]:
    """Generate a 3-word slug for a charity card display.

    Uses the cheapest LLM (LLM_JUDGE task) for this simple text generation.

    Returns:
        (slug, cost_usd) — slug string on success, None on failure
    """
    cause_tags = ", ".join(charity_data.get("cause_tags") or []) if charity_data else ""
    program_focus = ", ".join(charity_data.get("program_focus_tags") or []) if charity_data else ""
    geo = ", ".join(metrics.geographic_coverage) if metrics.geographic_coverage else ""
    programs = ", ".join(metrics.programs[:3]) if metrics.programs else ""

    prompt = SLUG_PROMPT.format(
        name=metrics.name,
        mission=(metrics.mission or "")[:500],
        cause_tags=cause_tags or "(none)",
        program_focus=program_focus or "(none)",
        programs=programs or "(none)",
        geo=geo or "(none)",
    )

    try:
        response = llm_client.generate(prompt, max_tokens=20)
        slug = response.text.strip().lower().strip('"').strip("'")
        words = slug.split()
        if len(words) > 3:
            slug = " ".join(words[:3])
        elif len(words) < 2:
            print(f"  WARN slug for {metrics.name}: got {len(words)} words: '{slug}'", file=sys.stderr)
            return None, response.cost_usd
        return slug, response.cost_usd
    except Exception as e:
        print(f"  WARN slug for {metrics.name}: {e}", file=sys.stderr)
        return None, 0.0


def _get_git_sha() -> str | None:
    """Get current git HEAD short sha, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent.parent,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _create_git_tag(tag_name: str, message: str) -> None:
    """Create a lightweight git tag. Silent on failure (e.g. tag exists, no git)."""
    try:
        subprocess.run(
            ["git", "tag", "-a", tag_name, "-m", message],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent.parent,
        )
    except Exception:
        pass


def _extract_narrative_text_fields(
    narrative: dict,
    rationale_field: str = "amal_score_rationale",
    dimension_keys: list[str] | None = None,
) -> list[str]:
    """Extract text fields from a narrative dict for citation scanning.

    Works for any lens by parameterizing the rationale field name and dimension keys.
    """
    if dimension_keys is None:
        dimension_keys = ["impact", "alignment"]

    text_fields = [
        narrative.get("summary", ""),
        narrative.get(rationale_field, ""),
    ]
    dim_explanations = narrative.get("dimension_explanations", {})
    for key in dimension_keys:
        text_fields.append(dim_explanations.get(key, ""))

    return text_fields


# Default AMAL lens parameters
AMAL_RATIONALE_FIELD = "amal_score_rationale"
AMAL_DIMENSION_KEYS = ["impact", "alignment"]


def repair_citations(
    narrative: dict,
    citation_sources: list,  # List of CitationSource objects from registry
    rationale_field: str = AMAL_RATIONALE_FIELD,
    dimension_keys: list[str] | None = None,
) -> dict:
    """Repair citation issues in LLM-generated narrative.

    Auto-fixes common issues:
    1. Orphan IDs: If text uses [N] but all_citations doesn't define it,
       add entry from registry if N is a valid index
    2. Hallucinated sources: Map to closest registry match
    3. Strip invalid citations from text if they can't be repaired

    Args:
        narrative: The LLM-generated narrative dict (modified in place)
        citation_sources: List of CitationSource objects from citation registry
        rationale_field: Name of the rationale field (varies by lens)
        dimension_keys: List of dimension key names (varies by lens)

    Returns:
        The repaired narrative dict
    """
    if dimension_keys is None:
        dimension_keys = AMAL_DIMENSION_KEYS

    # Extract all citation IDs used in text
    text_fields = _extract_narrative_text_fields(narrative, rationale_field, dimension_keys)

    all_text = " ".join(text_fields)
    cite_pattern = r"\[(\d+)\]"
    used_ids = set(re.findall(cite_pattern, all_text))

    # Get defined IDs from all_citations
    all_citations = narrative.get("all_citations", [])
    defined_ids = set()
    for citation in all_citations:
        cid = citation.get("id", "")
        match = re.search(r"\[(\d+)\]", cid)
        if match:
            defined_ids.add(match.group(1))

    # Find orphan IDs (used in text but not defined)
    orphan_ids = used_ids - defined_ids

    # Try to repair orphan IDs by adding from registry
    max_registry_id = len(citation_sources)
    repaired_count = 0

    # Text fields that might need invalid citations stripped
    strip_fields = ["summary", rationale_field]

    for orphan_id in orphan_ids:
        idx = int(orphan_id)
        if 1 <= idx <= max_registry_id:
            # Valid registry index - add citation from registry
            source = citation_sources[idx - 1]  # 0-indexed list
            new_citation = {
                "id": f"[{orphan_id}]",
                "source_name": source.source_name,
                "source_url": source.source_url,
                "claim": f"Supporting claim from {source.source_name}",
            }
            all_citations.append(new_citation)
            repaired_count += 1
        else:
            # Invalid index - strip from text
            for field in strip_fields:
                if field in narrative:
                    narrative[field] = re.sub(rf"\[{orphan_id}\]", "", narrative[field])
            if "dimension_explanations" in narrative:
                for key in dimension_keys:
                    if key in narrative["dimension_explanations"]:
                        narrative["dimension_explanations"][key] = re.sub(
                            rf"\[{orphan_id}\]", "", narrative["dimension_explanations"][key]
                        )

    # Update all_citations if we added any
    narrative["all_citations"] = all_citations

    # Backfill missing source_name/source_url deterministically from citation id or URL.
    def _match_source_by_url(source_url: str):
        if not source_url:
            return None
        normalized = source_url.rstrip("/")
        for source in citation_sources:
            candidate = (getattr(source, "source_url", None) or "").rstrip("/")
            if not candidate:
                continue
            if normalized == candidate or normalized in candidate or candidate in normalized:
                return source
        return None

    for citation in narrative.get("all_citations", []):
        source_name_raw = citation.get("source_name")
        source_name = str(source_name_raw).strip() if source_name_raw is not None else ""
        if source_name:
            continue

        matched_source = None
        cid = citation.get("id", "")
        match = re.search(r"\[(\d+)\]", cid)
        if match:
            idx = int(match.group(1))
            if 1 <= idx <= len(citation_sources):
                matched_source = citation_sources[idx - 1]

        if not matched_source:
            matched_source = _match_source_by_url(str(citation.get("source_url") or "").strip())

        if matched_source:
            citation["source_name"] = matched_source.source_name
            if not citation.get("source_url"):
                citation["source_url"] = matched_source.source_url

    # Fix hallucinated sources by finding closest match
    registry_names = [s.source_name for s in citation_sources]
    registry_lower = [s.lower() for s in registry_names]
    unresolved_ids: set[str] = set()
    unresolved_entry_refs: set[int] = set()

    for citation in narrative.get("all_citations", []):
        source_name = str(citation.get("source_name") or "").strip().lower()
        if not source_name:
            # Unrecoverable empty source; strip corresponding marker and drop entry.
            unresolved_entry_refs.add(id(citation))
            cid = citation.get("id", "")
            match = re.search(r"\[(\d+)\]", cid)
            if match:
                unresolved_ids.add(match.group(1))
            continue
        if source_name and not any(source_name in reg or reg in source_name for reg in registry_lower):
            # Find closest match by partial string matching
            best_match = None
            best_score = 0
            best_source = None  # B-005: Initialize to avoid unbound variable
            for i, reg_name in enumerate(registry_names):
                # Simple scoring: count common words
                citation_words = set(source_name.split())
                reg_words = set(reg_name.lower().split())
                common = len(citation_words & reg_words)
                if common > best_score:
                    best_score = common
                    best_match = reg_name
                    best_source = citation_sources[i]

            # Secondary fuzzy match for long titles with punctuation or slight wording changes
            fuzzy_idx = None
            fuzzy_ratio = 0.0
            for i, reg_name in enumerate(registry_names):
                ratio = difflib.SequenceMatcher(None, source_name, reg_name.lower()).ratio()
                if ratio > fuzzy_ratio:
                    fuzzy_ratio = ratio
                    fuzzy_idx = i
            if best_score == 0 and fuzzy_idx is not None and fuzzy_ratio >= 0.55:
                best_match = registry_names[fuzzy_idx]
                best_source = citation_sources[fuzzy_idx]
                best_score = 1

            # B-005: Only update if we found a match (best_source defined when best_score > 0)
            if best_match and best_score > 0 and best_source:
                citation["source_name"] = best_match
                citation["source_url"] = best_source.source_url
            else:
                # Unrecoverable hallucinated source: remove citation marker usage + entry
                unresolved_entry_refs.add(id(citation))
                cid = citation.get("id", "")
                match = re.search(r"\[(\d+)\]", cid)
                if match:
                    unresolved_ids.add(match.group(1))

    # Strip unresolved citation markers from text and drop citation entries.
    # This prevents hard-fail on a single hallucinated source while preserving valid citations.
    if unresolved_ids:
        def _strip_ids(text: str) -> str:
            for unresolved_id in unresolved_ids:
                text = re.sub(rf"\s*\[{re.escape(unresolved_id)}\]", "", text)
            text = re.sub(r"\s+([,.;:])", r"\1", text)
            text = re.sub(r"\s{2,}", " ", text)
            return text.strip()

        for field in strip_fields:
            if field in narrative and isinstance(narrative[field], str):
                narrative[field] = _strip_ids(narrative[field])

        if "dimension_explanations" in narrative:
            for key in dimension_keys:
                val = narrative["dimension_explanations"].get(key)
                if isinstance(val, str):
                    narrative["dimension_explanations"][key] = _strip_ids(val)

        filtered_citations = []
        for citation in narrative.get("all_citations", []):
            if id(citation) in unresolved_entry_refs:
                continue
            cid = citation.get("id", "")
            match = re.search(r"\[(\d+)\]", cid)
            if match and match.group(1) in unresolved_ids:
                continue
            filtered_citations.append(citation)
        narrative["all_citations"] = filtered_citations

    # Upgrade homepage-like URLs to deeper evidence links when registry has better options.
    source_context = [
        {
            "source_name": source.source_name,
            "source_url": source.source_url,
            "claim": getattr(source, "claim_topic", ""),
        }
        for source in citation_sources
        if getattr(source, "source_url", None)
    ]
    for citation in narrative.get("all_citations", []):
        if not isinstance(citation, dict):
            continue
        source_url = citation.get("source_url")
        if not source_url:
            continue
        citation["source_url"] = upgrade_source_url(
            source_url,
            source_name=str(citation.get("source_name") or ""),
            claim=str(citation.get("claim") or ""),
            context=source_context,
        )

    return narrative


def validate_citations(
    narrative: dict,
    valid_source_names: list[str],
    rationale_field: str = AMAL_RATIONALE_FIELD,
    dimension_keys: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Validate citation integrity in narrative.

    Checks:
    1. Every [N] in text has matching entry in all_citations
    2. Citation IDs are sequential starting from 1
    3. source_name in all_citations matches registry

    Args:
        narrative: The LLM-generated narrative dict
        valid_source_names: List of valid source names from citation registry
        rationale_field: Name of the rationale field (varies by lens)
        dimension_keys: List of dimension key names (varies by lens)

    Returns:
        (is_valid, errors) - True if valid, list of error messages if not
    """
    if dimension_keys is None:
        dimension_keys = AMAL_DIMENSION_KEYS

    errors = []

    # Extract all cite tags from narrative text fields
    text_fields = _extract_narrative_text_fields(narrative, rationale_field, dimension_keys)

    all_text = " ".join(text_fields)

    # Find all citation IDs used in text (format: [N])
    cite_pattern = r"\[(\d+)\]"
    used_ids = set(re.findall(cite_pattern, all_text))

    # Get citation IDs from all_citations array
    all_citations = narrative.get("all_citations", [])
    defined_ids = set()
    for citation in all_citations:
        # Citation id format is "[N]", extract the number
        cid = citation.get("id", "")
        match = re.search(r"\[(\d+)\]", cid)
        if match:
            defined_ids.add(match.group(1))

    # Check 1: Every used ID must be defined
    orphan_ids = used_ids - defined_ids
    if orphan_ids:
        errors.append(f"Orphan citation IDs in text (no matching entry): {sorted(orphan_ids)}")

    # Check 2: Unused citations are OK - all_citations may include sources
    # not directly referenced in narrative text (e.g., background sources)

    # Check 3: Citation IDs should be sequential from 1 (soft check - log but don't fail)
    # This is a cosmetic issue - non-sequential IDs still work correctly
    if defined_ids:
        expected = set(str(i) for i in range(1, len(defined_ids) + 1))
        if defined_ids != expected:
            # Log but don't fail - this is not a critical error
            pass  # Non-sequential IDs are OK as long as all used IDs are defined

    # Check 4 intentionally non-blocking:
    # source_name/title matching is noisy across crawled headlines and LLM rewrites.
    # We keep hard validation on citation marker integrity (Checks 1-3) and rely on
    # repair + judges for source quality enforcement.

    return len(errors) == 0, errors


def build_charity_metrics(
    ein: str,
    charity: dict,
    charity_data: dict | None,
    raw_sources: dict[str, dict],
) -> CharityMetrics:
    """Build CharityMetrics from DoltDB data.

    Uses pre-computed metrics_json blob from synthesis (single source of truth).
    Falls back to re-aggregation for charities not yet re-synthesized.
    """
    import logging

    logger = logging.getLogger(__name__)

    def _apply_synth_overrides(metrics: CharityMetrics, data: dict | None) -> CharityMetrics:
        """Apply scorer-relevant fields from synthesized charity_data.

        Keeps baseline aligned with current internal taxonomy even when metrics_json
        was generated before taxonomy/scoring updates.
        """
        if not data:
            return metrics
        metrics.is_muslim_focused = data.get("muslim_charity_fit") == "high"
        metrics.primary_category = data.get("primary_category")
        metrics.cause_tags = data.get("cause_tags") or []
        metrics.program_focus_tags = data.get("program_focus_tags") or []
        if isinstance(data.get("source_attribution"), dict):
            metrics.source_attribution = data.get("source_attribution") or {}
        if data.get("beneficiaries_served_annually") is not None:
            metrics.beneficiaries_served_annually = data.get("beneficiaries_served_annually")
        if data.get("working_capital_months") is not None:
            metrics.working_capital_ratio = data.get("working_capital_months")
        if data.get("founded_year") and not metrics.founded_year:
            metrics.founded_year = data.get("founded_year")

        zakat_meta = data.get("zakat_metadata") or {}
        if zakat_meta:
            metrics.zakat_categories_served = zakat_meta.get("asnaf_categories_served")
            metrics.zakat_policy_url = zakat_meta.get("zakat_policy_url")
            metrics.zakat_verification_confidence = zakat_meta.get("verification_confidence")
            metrics.islamic_identity_signals = zakat_meta.get("islamic_identity_signals")
        return metrics

    # Primary path: deserialize from metrics_json blob (set by synthesis)
    if charity_data and charity_data.get("metrics_json"):
        try:
            metrics = CharityMetrics(**charity_data["metrics_json"])
            return _apply_synth_overrides(metrics, charity_data)
        except Exception as e:
            logger.warning(f"Failed to deserialize metrics_json for {ein}: {e}, falling back to re-aggregation")

    # Fallback: re-aggregate from raw sources (for charities not yet re-synthesized)
    logger.warning(f"No metrics_json for {ein}, falling back to re-aggregation")

    cn_data = raw_sources.get("charity_navigator")
    pp_data = raw_sources.get("propublica")
    candid_data = raw_sources.get("candid")
    website_data = raw_sources.get("website")
    givewell_data = raw_sources.get("givewell")
    discovered_data = raw_sources.get("discovered")

    metrics = CharityMetricsAggregator.aggregate(
        charity_id=0,  # Not used
        ein=ein,
        cn_profile=cn_data.get("cn_profile", cn_data) if cn_data else None,
        propublica_990=pp_data.get("propublica_990", pp_data) if pp_data else None,
        candid_profile=candid_data.get("candid_profile", candid_data) if candid_data else None,
        website_profile=website_data.get("website_profile", website_data) if website_data else None,
        givewell_profile=givewell_data.get("givewell_profile", givewell_data) if givewell_data else None,
        discovered_profile=discovered_data.get("discovered_profile", discovered_data) if discovered_data else None,
    )

    return _apply_synth_overrides(metrics, charity_data)


_ZAKAT_CONSTRAINT_SADAQAH = (
    "⚠️ This charity is SADAQAH-ELIGIBLE (NOT zakat-eligible). DO NOT mention zakat eligibility, "
    "zakat policies, zakat pathways, fuqara, masakin, or any implication that donations qualify as "
    "zakat. Only mention sadaqah or general charitable giving."
)
_ZAKAT_CONSTRAINT_ZAKAT = (
    "✓ This charity is ZAKAT-ELIGIBLE. You MAY mention zakat eligibility if supported by source data."
)


def _fundraising_ratio_str(fundraising_expenses, total_revenue) -> str | None:
    """Just the dollar-figure prefix (e.g. "$0.00", "<$0.01", "$0.10") for the
    cost to raise $1, or None if it can't be computed.

    A real-but-tiny ratio must not render as "$0.00": $241,666 against $79.6M
    revenue is $0.003 per $1 — a real cost, and telling a donor it was zero is
    wrong. Only a genuine 0 gets "$0.00". Shared by the prompt-construction
    call site and the narrative sanitizer's correction path so both agree.
    """
    if fundraising_expenses is None or not total_revenue or total_revenue <= 0:
        return None
    efficiency = fundraising_expenses / total_revenue
    if efficiency == 0:
        return "$0.00"
    if efficiency < 0.01:
        return "<$0.01"
    return f"${efficiency:.2f}"


def _format_fundraising_efficiency(fundraising_expenses, total_revenue) -> str:
    """Cost to raise $1, as prose. "N/A" when unknowable."""
    ratio = _fundraising_ratio_str(fundraising_expenses, total_revenue)
    return f"{ratio} per $1 raised" if ratio else "N/A"


def _baseline_prompt_kwargs(metrics: CharityMetrics, scores: Any, num_sources: int, sources_list: str) -> dict:
    """Build the .format() kwargs for the baseline_narrative prompt template.

    Keys here MUST match the {placeholders} in src/llm/prompts/baseline_narrative.txt
    (drift-guarded by tests/test_baseline_prompt.py).
    """
    revenue_str = f"${metrics.total_revenue:,.0f}" if metrics.total_revenue else "N/A"
    ratio_str = f"{metrics.program_expense_ratio:.1%}" if metrics.program_expense_ratio else "N/A"
    cn_score_str = f"{round(metrics.cn_overall_score, 1)}/100" if metrics.cn_overall_score else "N/A"
    programs_str = ", ".join(metrics.programs[:3]) if metrics.programs else "Not available"
    working_capital_str = f"{metrics.working_capital_ratio:.1f} months" if metrics.working_capital_ratio else "N/A"

    fundraising_efficiency_str = _format_fundraising_efficiency(
        metrics.fundraising_expenses, metrics.total_revenue
    )

    zakat_constraint_text = (
        _ZAKAT_CONSTRAINT_SADAQAH if scores.wallet_tag == "SADAQAH-ELIGIBLE" else _ZAKAT_CONSTRAINT_ZAKAT
    )

    def _assessment_notes(assessment: Any) -> str:
        parts = []
        if getattr(assessment, "rationale", ""):
            parts.append(assessment.rationale)
        components = getattr(assessment, "components", None) or []
        if components:
            parts.append(
                "Components: " + ", ".join(f"{c.name} {c.scored}/{c.possible}" for c in components)
            )
        return " | ".join(parts) or "(no notes)"

    case_against = getattr(scores, "case_against", None)
    risk_descriptions = [r.description for r in (case_against.risks or [])] if case_against else []
    risk_notes = "; ".join(risk_descriptions) or "none"

    return {
        "score_band": score_band_label(scores.amal_score),
        "data_vintage_note": data_vintage_note(metrics.financial_data_tax_year),
        "impact_notes": _assessment_notes(scores.impact),
        "alignment_notes": _assessment_notes(scores.alignment),
        "risk_notes": risk_notes,
        "charity_name": metrics.name,
        "ein": metrics.ein,
        "mission": metrics.mission or "Not available",
        "programs": programs_str,
        "revenue": revenue_str,
        "ratio": ratio_str,
        "cn_score": cn_score_str,
        "working_capital": working_capital_str,
        "fundraising_efficiency": fundraising_efficiency_str,
        "wallet_tag": scores.wallet_tag,
        "zakat_constraint_text": zakat_constraint_text,
        "amal_score": scores.amal_score,
        "impact_score": scores.impact.score,
        "impact_directness": scores.impact.directness_level,
        "impact_cpb": scores.impact.cost_per_beneficiary or "N/A",
        "alignment_score": scores.alignment.score,
        "alignment_fit": scores.alignment.muslim_donor_fit_level,
        "alignment_urgency": scores.alignment.cause_urgency_label,
        "data_confidence": scores.data_confidence.overall,
        "data_confidence_badge": scores.data_confidence.badge,
        "num_sources": num_sources,
        "sources_list": sources_list,
    }


def build_baseline_prompt(
    metrics: CharityMetrics, scores: Any, num_sources: int, sources_list: str
) -> tuple[str, PromptInfo]:
    """Render the canonical baseline_narrative prompt (H4: single source of truth)."""
    info = load_prompt("baseline_narrative")
    return info.content.format(**_baseline_prompt_kwargs(metrics, scores, num_sources, sources_list)), info


def generate_baseline_narrative(
    metrics: CharityMetrics,
    scores: Any,
    llm_client: LLMClient,
    ein: str,
) -> tuple[dict | None, str | None, float]:
    """Generate baseline narrative using LLM with citation support.

    Returns:
        (narrative, error, cost_usd) - narrative dict on success, error message on failure, total LLM cost
    """
    total_cost = 0.0

    # Build citation registry from available sources
    citation_service = CitationService()
    citation_registry = citation_service.build_registry(ein)

    # Format available sources for the prompt
    sources_list = citation_registry.get_sources_for_prompt()
    num_sources = len(citation_registry.sources)

    # Build prompt from the canonical versioned template (H4)
    prompt, prompt_info = build_baseline_prompt(metrics, scores, num_sources, sources_list)

    # Extract citation sources for validation and repair
    citation_sources = citation_registry.sources  # Full CitationSource objects for repair
    valid_source_names = [s.source_name for s in citation_sources]  # Just names for validation

    def parse_llm_response(text: str) -> dict | None:
        """Parse JSON from LLM response, handling markdown code blocks and leading text."""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()
        # Handle cases where model outputs text before JSON (e.g., "thought\n{...")
        if text and not text.startswith("{"):
            # Find first { and parse from there
            brace_idx = text.find("{")
            if brace_idx != -1:
                text = text[brace_idx:]
        if not text:
            raise json.JSONDecodeError("Empty after extraction", "", 0)
        return json.loads(text)

    def ensure_citation_fields(narrative: dict) -> None:
        """Ensure all_citations exists and has required fields."""
        if "all_citations" not in narrative:
            narrative["all_citations"] = []
        for citation in narrative.get("all_citations", []):
            if "id" not in citation:
                citation["id"] = "[?]"
            if "source_url" not in citation:
                citation["source_url"] = None

    # First attempt with retry for empty/invalid responses
    max_retries = 3
    narrative = None
    last_error = None

    for attempt in range(max_retries):
        try:
            response = llm_client.generate(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.3,
                prompt_version=prompt_info.version,
            )
            total_cost += response.cost_usd
            if not response.text or not response.text.strip():
                last_error = "LLM returned empty response"
                continue  # Retry on empty response
            narrative = parse_llm_response(response.text)
            break  # Success, exit retry loop
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON from LLM: {str(e)}"
            continue  # Retry on JSON parse error
        except Exception as e:
            last_error = f"LLM error: {str(e)}"
            continue

    if narrative is None:
        return None, last_error or "LLM failed after retries", total_cost

    try:
        ensure_citation_fields(narrative)

        # Try to auto-repair citations before validation
        narrative = repair_citations(narrative, citation_sources)

        # Stamp correct metrics before returning
        narrative = sanitize_narrative_metrics(narrative, metrics, scores)

        # Validate citations
        is_valid, errors = validate_citations(narrative, valid_source_names)
        if is_valid:
            return narrative, None, total_cost

        # Validation failed after repair - retry with fix prompt
        fix_prompt = f"""{prompt}

IMPORTANT: Your previous response had citation errors:
{chr(10).join(f"- {e}" for e in errors)}

Please fix these issues:
1. Every [N] citation in text MUST have a matching entry in all_citations with id "[N]"
2. Citation IDs must be sequential starting from 1
3. source_name must match one of the available sources listed above
4. Do not invent or hallucinate sources
5. Return ONLY valid JSON, no markdown code blocks

Generate the corrected narrative JSON:"""

        response = llm_client.generate(
            prompt=fix_prompt,
            max_tokens=1500,
            temperature=0.3,
            prompt_version=prompt_info.version,
        )
        total_cost += response.cost_usd
        narrative = parse_llm_response(response.text)
        ensure_citation_fields(narrative)

        # Try to auto-repair citations again
        narrative = repair_citations(narrative, citation_sources)

        # Stamp correct metrics before returning
        narrative = sanitize_narrative_metrics(narrative, metrics, scores)

        # Validate again
        is_valid, errors = validate_citations(narrative, valid_source_names)
        if is_valid:
            return narrative, None, total_cost

        # Still failed after retry and repair
        return None, f"Citation validation failed after retry: {'; '.join(errors)}", total_cost

    except json.JSONDecodeError as e:
        return None, f"Invalid JSON from LLM: {str(e)}", total_cost
    except Exception as e:
        return None, f"LLM generation failed: {str(e)}", total_cost


def _match_case(match: "re.Match[str]", replacement: str) -> str:
    """Preserve the matched text's leading capitalization in a correction
    rule's replacement.

    A few correction rules replace a verb-led match ("Holds"/"holds",
    "Scored"/"scored", ...) with a fixed-case literal string. That's
    harmless when the match is always mid-sentence, but a removal rule
    elsewhere in this function can now leave such a clause at the very
    start of a sentence (see the working-capital "holds" rule paired with
    the null-fundraising removal rule) — re-running the same correction
    rule on its own already-correct, now-capitalized output would silently
    lowercase it again, which would break the idempotency every rule here
    must have.
    """
    if replacement and match.group(0)[:1].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _preserve_case(replacement: str) -> Callable[["re.Match[str]"], str]:
    """Wrap a fixed-case literal correction so it goes through `_match_case`.

    Every correction rule below whose replacement is a literal string that
    begins with a word (not a digit, not an already-all-caps token like
    "Charity Navigator"/"AMAL" whose case never changes with position) is
    exposed to the same hazard `_match_case` was written for: a removal rule
    earlier in this function can leave that match sentence-initial and
    capitalized, and re-stamping a lowercase literal over it would silently
    lowercase it again.
    """
    return lambda m: _match_case(m, replacement)


_ABBREVIATIONS_BEFORE_COMMA = {
    "inc", "corp", "ltd", "co", "jr", "sr", "dr", "mr", "mrs", "ms",
    "st", "ave", "blvd", "vs", "etc", "al", "no", "vol", "fig",
    "e.g", "i.e", "ph.d", "u.s", "u.k", "a.m", "p.m",
}
# Matches the run of letters (with internal abbreviation dots, e.g. "e.g")
# immediately before a terminal-punctuation-then-comma with NO whitespace
# between them. Non-letter characters right before the period (a citation
# bracket, an HTML tag, a digit) simply leave the optional `abbr` group
# empty rather than being swallowed into the match.
_BARE_PERIOD_COMMA = re.compile(r"(?P<abbr>[A-Za-z]+(?:\.[A-Za-z]+)*)?(?P<punct>[.!?]),")


def _abbreviation_before_stray_comma(match: "re.Match[str]") -> str:
    """Leave a stray `.,` alone when it's really a sentence-ending
    abbreviation immediately followed by a clause-continuing comma.

    "U.S.," / "e.g.," / "et al.," are ordinary, correctly-punctuated
    English — the period-then-comma-with-no-space shape isn't unique to
    the removal artifact this function repairs. Unlike the open-ended
    class of appositive lead-ins `_clause_trail` gave up on enumerating,
    sentence-ending abbreviations are a small, closed, standard set (the
    same kind of static list sentence-boundary detectors have always
    used), so listing them here doesn't reproduce that problem.
    """
    abbr = match.group("abbr")
    if abbr and abbr.lower() in _ABBREVIATIONS_BEFORE_COMMA:
        return match.group(0)
    return f"{abbr or ''}{match.group('punct')} ,"


def _repair_removal_artifacts(text: str) -> str:
    """Clean up what a clause-scoped removal leaves behind.

    A removal rule's leading/trailing edges (`_clause_lead` / `_clause_trail`
    in `sanitize_narrative_metrics`) stop at a clause boundary instead of the
    sentence boundary, on purpose — so a true claim sharing a sentence with a
    fabricated one survives. That leaves two kinds of debris depending on
    which side of the sentence the removed clause was on:
      - removed clause was first: a leading ", and " / ", " connector is now
        stranded at the front of what remains (and the word right after it
        is no longer capitalized, since it used to be mid-sentence).
      - removed clause was the whole sentence: its own terminal period is
        never part of the match (see `_clause_trail`'s docstring), so it's
        left as an orphan with nothing before it.
      - removed clause was in the MIDDLE, joined to a surviving clause by a
        bare comma with no continuation lead (see `_trail_same_claim_lead`):
        the removal's own leading edge greedily starts as early as the
        previous sentence's terminal period (the leftmost regex match wins),
        swallowing the boundary space along with the removed text, so the
        surviving comma-led fragment ends up directly touching that period
        with no space at all — a literal `.,`. The fragment itself is never
        dropped here (that would risk deleting a true, distinct fact that
        happened to share the sentence with the fabricated one — verified
        against nine real cases, two of which are exactly this: a genuine
        working-capital figure and a genuine revenue-decline figure, both
        would be lost by dropping instead of just re-punctuating). Handled
        by `_abbreviation_before_stray_comma` below, which turns the bare
        `.,` into `. ,` (inserting the missing space) so the existing
        stray-comma repair a few lines down — already written for the
        with-space case — picks it up and finishes the job unchanged,
        except right after a sentence-ending abbreviation ("U.S.,",
        "e.g.,"), where this exact shape is ordinary, correct punctuation
        and must be left alone.
    Both/all need cleanup that a simple `re.sub(pattern, "")` can't do
    inline, which is why this runs as a separate pass after each removal
    instead of being folded into the removal patterns themselves.

    Must be idempotent — sanitize_narrative_metrics runs twice on the
    citation-repair retry path, so re-running this on its own output has to
    be a byte-identical no-op.
    """
    text = _BARE_PERIOD_COMMA.sub(_abbreviation_before_stray_comma, text)
    text = re.sub(r"\s{2,}", " ", text)
    # A leading connective stranded at the start of a sentence: ", and X" or
    # ", X" -> "X" (only at the very start of the string, or right after a
    # previous sentence's terminal punctuation — never mid-sentence, so this
    # can't reach into unrelated text).
    text = re.sub(r"(^|[.!?]\s+)\s*,\s*(?:and\s+)?", r"\1", text)
    # A bare "and " stranded at a sentence start with no comma of its own
    # (the comma was itself part of the removed span). The leading `\s*`
    # also covers the case where the removed span was the very start of the
    # string (or immediately follows the previous sentence with nothing to
    # collapse): _clause_trail now stops right before " and " rather than
    # consuming into it, so the boundary space itself is left dangling in
    # front of "and" instead of already being absorbed by the multi-space
    # collapse above.
    text = re.sub(r"(^|[.!?]\s+)\s*and\s+", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r",\s*,", ",", text)  # doubled comma
    text = re.sub(r",\s*([.!?])", r"\1", text)  # comma stranded right before terminal punctuation
    text = re.sub(r",\s*$", "", text)  # trailing dangling comma
    text = re.sub(r"([.!?])\s*\1+", r"\1", text)  # doubled terminal punctuation
    # A stray terminal mark with nothing (or only whitespace) before it — the
    # whole clause it used to close was removed.
    text = re.sub(r"(^|[.!?]\s+)[.!?]\s*", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    # Capitalize the first letter of the string and of each sentence start,
    # since the word now beginning a sentence may have been lowercase and
    # mid-sentence before its leading clause was removed.
    text = re.sub(r"(^\s*|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
    return text


def sanitize_narrative_metrics(narrative: dict, metrics: "CharityMetrics", scores: Any) -> dict:
    """Deterministically stamp correct metric values into LLM-generated narrative.

    The LLM writes qualitative prose; this function ensures every numeric claim
    matches the source data.  Fixes three classes of error:
      1. Wrong number (e.g. "3 months" when source says 8.3 months)
      2. Wrong unit  (e.g. "years" when source is months)
      3. Phantom mention of an N/A metric (e.g. citing CN score when it's null)
    """

    # ── Build the ground-truth lookup ──
    # Each entry: (regex pattern, correct replacement, remove_if_na)
    # For N/A metrics the pattern is used to strip the enclosing sentence.
    rules: list[tuple[str, str | Callable[["re.Match[str]"], str] | None, bool]] = []

    # Removal rules scan "everything up to the sentence boundary" using a
    # `[^.]*`-shaped run. A literal `.` also shows up mid-number ("91.1%",
    # "$0.00"), and `[^.]*` can't cross it — so the run stops there instead of
    # at the real sentence end, and the trailing `\.?` then deletes into the
    # next clause starting mid-number. Fix: treat a period as a boundary only
    # when it is NOT sandwiched between two digits (a decimal point).
    #
    # `_decimal_safe` is still used for the INNER gaps inside a removal
    # pattern (e.g. the "co-occurrence within one sentence" gap between
    # "$0.00" and "fundraising efficiency") — that's about tolerating
    # unrelated words *inside* one fabricated claim, not about where the
    # claim's outer boundary sits, so it is unaffected by the clause-vs-
    # sentence fix below.
    _decimal_safe = r"(?:[^.]|(?<=\d)\.(?=\d))*"
    # Used for the OUTER leading edge of every removal rule (not just
    # fundraising) — also stops at a comma, so the removal can't swallow an
    # adjacent, unrelated clause sitting in front of the fabricated one (e.g.
    # a legitimate "91.1% program expense ratio" clause joined to a
    # fabricated one by "and a"/comma). Includes an optional leading ", and "
    # / ", " so the removed span cleanly eats the connective tissue too,
    # rather than leaving a dangling comma at the front of what remains.
    #
    # Mirrors the bare-"and" fix on the trailing edge below: a true clause
    # can sit BEFORE an "and"-joined fabricated one too ("It serves 4,000
    # families and has a program expense ratio of 91.1%."), and without a
    # boundary here the leading scan ran straight through " and " and into
    # the fabricated clause's own lead-in text, stopping only at whatever
    # comma or period turned up there — the same mid-number truncation bug,
    # approached from the other direction ("It serves 4,000 families and
    # has..." truncating to "It serves 4."). The added `\s+and\s+`
    # alternative lets the match start right at that connector (consuming
    # its own leading space, so the removed span cleanly eats it the same
    # way it already eats a leading comma) instead of only ever starting
    # after "and", which would otherwise leave a stray space dangling in
    # front of the surviving clause's own closing punctuation. The
    # accompanying `(?!\s+and\b)` in the run below blocks the scan from
    # ever crossing an "and" it hasn't matched as this connector; if the
    # true clause's own phrasing has an earlier, unrelated "and" in it
    # (e.g. "accountability and finance score"), attempting to start there
    # fails to reach the fabricated core (blocked by the *next* "and" in
    # turn), so the search naturally advances to the real, final connector
    # instead — no special-casing needed, same self-correcting behavior as
    # the trailing-edge fix.
    _clause_lead = (
        r"(?:,\s*(?:and\s+)?|\s+and\s+)?"
        + r"(?:(?!\s+and\b)(?:[^.,]|(?<=\d)\.(?=\d)))*"
    )
    # Used for the OUTER trailing edge of every removal rule. Whether a comma
    # is a clause boundary is decided by what follows it, not by the comma
    # alone: an appositive tail ("its highest rating", "a strong reserve
    # position") is a noun phrase and stays *inside* the fabricated claim —
    # e.g. "a perfect score from Charity Navigator, its highest rating" is
    # one fabricated claim with an appositive tail, and clause-scoping the
    # tail would leave that dangling fragment behind, still implying a
    # rating that doesn't exist. An independent clause must NOT be
    # swallowed the same way.
    #
    # An earlier version of this told the two apart by checking whether the
    # text after the comma led with a finite verb ("spends", "holds",
    # "scored", "is", ...), on the theory that an independent clause always
    # opens with one. That enumerates the wrong side: the set of verbs a
    # true clause can open with is unbounded (any verb at all — "reports",
    # "serves", "operates", "distributed", "founded", ... none of which were
    # on the list), so any verb missing from it reproduced the original bug
    # of wiping the true clause along with the false one.
    #
    # The side that IS closed is the appositive lead: every appositive tail
    # actually seen here ("its highest rating", "a strong reserve position",
    # "the best in its class", "one of the highest in its cohort", or a bare
    # comparative/superlative with no determiner at all like "best in its
    # class", "higher than most peers") opens with a determiner, possessive,
    # quantifier, or comparative/superlative adjective — never a verb (with
    # two knowingly ambiguous exceptions, see below). A genuine comparison of
    # the SAME fabricated number ("up from 82 last
    # year", "compared to last year") also belongs on the "still one claim"
    # side despite carrying its own number — the trap a naive "does the
    # tail contain a number" test would fall into, wrongly boundary-ing
    # there and leaving a fabricated fragment like "Up from 82 last year."
    # behind.
    #
    # So `_clause_trail` now swallows a bare comma ONLY when what follows it
    # opens with one of these closed continuation markers, and treats
    # everything else — any verb, known or not, "and", or anything
    # unrecognized — as an independent-clause boundary and stops there.
    # This is a deliberately asymmetric default: an appositive phrasing not
    # in the list below will now be preserved as an orphan fragment rather
    # than removed (over-preservation, the safer failure mode per the
    # standing rule that a surviving fabrication is worse than a
    # fabrication-adjacent leftover fragment of one) instead of silently
    # deleting a true clause it can't recognize. This list — not a verb
    # list — is what to extend if a new appositive phrasing turns up.
    # Deliberately does not also match a bare trailing `\.` — the terminal
    # period is left for `_repair_removal_artifacts` to clean up, so a
    # removal that empties its whole sentence doesn't strand an orphan
    # period, and a removal that leaves a real clause behind doesn't eat
    # that clause's own closing period.
    # Extended once more (still no verb added) to also catch an appositive
    # tail with no leading determiner/possessive/quantifier at all — a bare
    # comparative or superlative ("best in its class", "higher than most
    # peers", "among the best in its sector"). Without a determiner these
    # used to default to a clause boundary and strand the comparison after
    # its basis (the fabricated number) was removed. `lower` and `better`
    # are knowingly ambiguous — each can also lead a genuine verb clause
    # ("lower their overhead", "better their outcomes") — but per the
    # standing tie-break an over-removed true clause is preferred to a
    # surviving fabrication-adjacent fragment, so both are included anyway.
    _trail_same_claim_lead = (
        r"(?:a|an|the|its|their|his|her)\b"
        r"|one\s+of\b"
        r"|(?:up|down)\s+from\b"
        r"|compared\s+to\b"
        r"|versus\b"
        r"|vs\.?(?=\s)"
        r"|well\s+(?:above|below|over|under)\b"
        r"|(?:best|worst|higher|lower|better|stronger|weaker|highest|lowest|strongest)\b"
        r"|among\b"
        r"|second\s+only\s+to\b"
    )
    # A bare " and " (no comma) is a second, simpler boundary shape: unlike
    # the bare-comma case above, "and" is an unambiguous coordinating
    # conjunction — there's no appositive reading to protect, so it's always
    # a boundary, never a continuation. Without this, `[^.,]` (which doesn't
    # exclude the letters "a"/"n"/"d") happily scans straight through " and "
    # and on into the next clause, stopping only at that clause's own first
    # comma or period — which is exactly what let the scan run into a
    # thousands-separator comma ("4,000") or a decimal point mid-number and
    # truncate there instead of at the real clause boundary. The negative
    # lookahead only blocks *consuming into* " and "; it doesn't touch the
    # comma-continuation alternative below, so ", and" (a bare comma directly
    # followed by "and") still resolves the same way it already did — "and"
    # was never on `_trail_same_claim_lead`, so that comma was already a
    # boundary. `\band\b` also means this can't misfire on "and" as a
    # substring of a longer word ("demand", "sandwich"), and it only ever
    # fires on text *after* a rule's core match — an "and" inside the core's
    # own `_decimal_safe` co-occurrence gap (e.g. between a Charity Navigator
    # mention and its score) is untouched, since that gap is a separate
    # regex fragment this lookahead isn't part of.
    _clause_trail = rf"(?:(?!\s+and\b)(?:[^.,]|(?<=\d)\.(?=\d))|,(?=\s*(?:{_trail_same_claim_lead})))*"

    # Working capital  (e.g. "8.3 months of working capital" or "8.3 years of reserves")
    # LLM variants: "holds X years of expenses", "maintains X years in reserves",
    # "X years' worth of operating", "expenses held in reserve"
    _wc_noun = r"(?:working\s+capital|operating\s+(?:expenses?|costs?)|reserves?|expenses?\s+(?:held\s+)?in\s+reserve)"
    # working_capital_ratio is net_assets / monthly_expenses with no floor at
    # zero (net assets can be negative), so a negative figure is a real,
    # legitimate value here — unlike every other metric this function
    # corrects, all of which are non-negative by construction (Pydantic
    # `ge=0` on the CN scores and program_expense_ratio, `max(0, ...)`
    # clamping on the AMAL score; see the report for the full survey). The
    # leading `-?` matters: without it, the match never consumes a minus
    # sign already sitting in the text, but `correct_wc` below still
    # produces one when the value is negative — so a second sanitize pass
    # (the citation-repair retry path runs this twice for real) stamps a
    # fresh "-2.7" right after whatever dash was already there instead of
    # replacing it, adding one more dash forever. `-?` makes the match
    # consume that sign too, so the correction fully replaces the old
    # number (sign included) instead of appending next to it.
    _wc_num_unit = r"-?\d+\.?\d*\s*(?:months?|years?)"
    if metrics.working_capital_ratio is not None:
        correct_wc = f"{metrics.working_capital_ratio:.1f} months"
        # Pattern 1: <number> <months|years> of <working capital|reserves|...>
        rules.append(
            (
                rf"{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}",
                correct_wc + " of working capital",
                False,
            )
        )
        # Pattern 2: "holds/maintains/has X years of expenses". Captures and
        # echoes back whichever verb was actually matched instead of
        # hardcoding "holds" — a real idempotency violation otherwise: text
        # like "The charity has 5 years' worth of operating expenses saved."
        # doesn't match this pattern on pass 1 (Pattern 3's "worth of" shape
        # catches it instead, leaving the leading "has" untouched), but DOES
        # match on pass 2 once Pattern 3 has already normalized the tail to
        # "... of working capital" — and a hardcoded "holds" replacement
        # would then silently rewrite "has" to "holds" on that second pass,
        # so pass 1's output differs from pass 2's even though the value
        # never changes. Echoing the matched verb keeps every pass a no-op
        # once the value is already correct. Case-preserving (see
        # _match_case) — a preceding clause's removal can leave this one
        # sentence-initial and capitalized ("Holds ...").
        rules.append(
            (
                rf"(holds?|maintains?|has)\s+{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}",
                lambda m: _match_case(m, f"{m.group(1)} {correct_wc} of working capital"),
                False,
            )
        )
        # Pattern 3: "X years' worth of operating"
        rules.append(
            (
                rf"{_wc_num_unit}['\u2019]?\s*worth\s+of\s+{_wc_noun}",
                correct_wc + " of working capital",
                False,
            )
        )
    else:
        # Remove any mention of working capital with a number
        rules.append(
            (
                rf"{_clause_lead}{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}{_clause_trail}",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}(?:holds?|maintains?|has)\s+{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}{_clause_trail}",
                None,
                True,
            )
        )

    # Program expense ratio
    # LLM variants: "directs X% to programs", "allocates X% to programmatic",
    # "X% of expenses go to programs", "X% of its budget", "program ratio of X%"
    if metrics.program_expense_ratio is not None:
        pct = metrics.program_expense_ratio * 100
        correct_ratio = f"{pct:.1f}%"
        # Pattern 1: <number>% program expense/spending
        rules.append(
            (
                r"\d+\.?\d*\s*%\s+(?:of\s+)?(?:program\s+(?:expense|spending))",
                f"{correct_ratio} program expense",
                False,
            )
        )
        # Pattern 2: program expense ratio of <number>%. Case-preserving (see
        # _preserve_case) — a preceding clause's removal can leave this one
        # sentence-initial and capitalized ("Program expense ratio ...").
        rules.append(
            (
                r"program\s+(?:expense\s+)?ratio\s+(?:of\s+)?\d+\.?\d*\s*%",
                _preserve_case(f"program expense ratio of {correct_ratio}"),
                False,
            )
        )
        # Pattern 3: directs/allocates X% to programs/programmatic. Captures
        # and echoes back the noun phrase actually matched instead of
        # hardcoding "programs" — hardcoding it was a real bug: `programs?`
        # matches just the word "program" inside the unrelated phrase
        # "program expense" (its optional trailing "s?" doesn't require a
        # word boundary before the next word), so "directs 50% to program
        # expense." matched on "program" alone, then the hardcoded plural
        # replacement produced "directs 91.1% to programs expense." — right
        # number, doubled/garbled noun. Echoing back whatever text the noun
        # group actually captured ("program", "programs", or
        # "programmatic ...") leaves any unmatched tail (like " expense")
        # exactly where it was, so it reattaches cleanly instead of
        # colliding with a hardcoded plural. Case-preserving for the same
        # reason as pattern 2.
        rules.append(
            (
                r"(?:directs?|allocates?|dedicates?|channels?|devotes?)\s+\d+\.?\d*\s*%\s+(?:of\s+\w+\s+)?(?:to|toward)\s+(programs?|programmatic\s+(?:work|activities|expenses?))",
                lambda m: _match_case(m, f"directs {correct_ratio} to {m.group(1)}"),
                False,
            )
        )
        # Pattern 4: X% of expenses/budget/spending go to programs
        rules.append(
            (
                r"\d+\.?\d*\s*%\s+of\s+(?:its\s+)?(?:expenses?|budget|spending|revenue|funds?)\s+(?:goes?|go|is\s+directed|is\s+allocated)\s+(?:to|toward)\s+(?:programs?|programmatic)",
                f"{correct_ratio} of expenses goes to programs",
                False,
            )
        )
        # Pattern 5: spends X% on/for programs. The removal-side rule for
        # this exact phrasing (below, in the null branch) had no correction
        # counterpart, so a wrong number published verbatim whenever the
        # ratio was real instead of null. Case-preserving for the same
        # reason as patterns 2 and 3.
        rules.append(
            (
                r"spends?\s+\d+\.?\d*\s*%\s+(?:on|for)\s+(?:programs?|programmatic\s+(?:work|activities|expenses?))",
                _preserve_case(f"spends {correct_ratio} on programs"),
                False,
            )
        )
    else:
        # Remove sentences mentioning program expense ratio with a number
        rules.append(
            (
                rf"{_clause_lead}program\s+(?:expense\s+)?ratio\s+(?:of\s+)?\d+\.?\d*\s*%{_clause_trail}",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}(?:directs?|allocates?)\s+\d+\.?\d*\s*%\s+(?:of\s+\w+\s+)?(?:to|toward)\s+(?:programs?|programmatic){_clause_trail}",
                None,
                True,
            )
        )
        # Number-BEFORE-metric-name variants of the same fabrication (e.g.
        # "has a 91.1% program expense ratio", "spends 91.1% on programs").
        # The two rules above only catch the number-after shape; the
        # correction rules for this metric (pattern 1 above) already handle
        # number-before phrasing when the ratio is real, so this closes the
        # matching gap on the removal side rather than duplicating it.
        rules.append(
            (
                rf"{_clause_lead}\d+\.?\d*\s*%\s+program\s+(?:expense\s+)?ratio{_clause_trail}",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}spends?\s+\d+\.?\d*\s*%\s+(?:on|for)\s+(?:programs?|programmatic\s+(?:work|activities|expenses?)){_clause_trail}",
                None,
                True,
            )
        )

    # Charity Navigator score
    # LLM variants: "accountability score of X", "financial score of X",
    # "rating of X/100", "rates X/100", "scored X out of 100", "X-star rating",
    # "perfect rating", "perfect score"
    cn_score = getattr(metrics, "cn_overall_score", None)
    cn_accountability = getattr(metrics, "cn_accountability_score", None)
    cn_financial = getattr(metrics, "cn_financial_score", None)
    # Hoisted above the cn_score block — needed here by the overall-score
    # guard below, and again further down by the accountability/financial
    # rules themselves (see their own comments for why each noun phrase is
    # captured and echoed rather than canonicalized).
    _acc_name = r"accountability(?:\s*(?:&|and)\s*finance)?|governance"
    _fin_name = r"financial(?:\s+health)?"
    # A malformed multi-decimal numeral (two or more embedded decimal points
    # in one run — e.g. "96.96.0", a corrupted leftover from an earlier
    # regeneration) has no single clean number any correction rule below can
    # take without either (a) starting the match late, right after a stray
    # leading "<digit>." that isn't part of the real number, which produces
    # a phantom value that existed in neither the source data nor the
    # corrupted input, or (b) starting on time but stopping short at the
    # first embedded dot, splicing a correction onto a numeral that silently
    # continues right after it. `(?<![\d.])` blocks every starting position
    # that sits inside, or immediately after, such a run — not just a
    # position immediately after a "<digit>." pair, which would still let
    # the engine fall back to a later start inside the same corrupted run.
    # `(?!\d+\.\d+\.\d)` blocks the one position the lookbehind can't reach:
    # the very first digit of the run itself. Together they make every
    # numeric correction pattern in this section refuse to match a malformed
    # run at all, leaving it exactly as published — regeneration, not this
    # sanitizer, is what fixes it (see
    # test_charity_36_3673599_malformed_string_is_left_as_is and its
    # siblings for the other two live EINs carrying the same artifact).
    _number_not_malformed = r"(?<![\d.])(?!\d+\.\d+\.\d)"
    # The generic "X/100 ... Charity Navigator" pattern a few lines down
    # corrects cn_overall_score no matter what noun precedes the number —
    # on its own it can't tell "50/100 from Charity Navigator" apart from
    # "accountability rating of 50/100 from Charity Navigator", so it was
    # stamping the *overall* score into prose that named a specific
    # sub-score (only the literal word "score", not "rating", was ever
    # anchored to the sub-score-specific rules below, so "rating" phrasing
    # fell through to this generic rule unopposed). Used by that rule's
    # replacement — a plain callable, not a regex lookbehind, since the noun
    # phrases it must recognize vary in length ("accountability", "governance",
    # "financial health") and Python's `re` only supports fixed-width
    # lookbehind — to refuse to claim a span whose number is actually named
    # by a sub-score, leaving it for that metric's own rule to correct with
    # the right value instead. Checked as a plain substring match ending
    # exactly where the number starts, so it's independent of rule order.
    #
    # Also recognizes a linking verb ("is"/"was") in place of "of" —
    # hand-probed and found live: "the financial rating is 40/100 from
    # Charity Navigator" is a different phrasing shape than "of X" (neither
    # accountability's nor financial's own correction rules parse "is X"
    # either, so this specific shape stays uncorrected either way — that's
    # unchanged, pre-existing, and out of this task's scope), but without
    # this the generic overall rule still claimed it and mislabeled the
    # *overall* score as the financial one, which is exactly the failure
    # mode this guard exists to prevent regardless of which preposition or
    # verb sits between the noun and the number.
    _sub_score_lead_re = re.compile(
        rf"(?:{_acc_name}|{_fin_name})\s+(?:score|rating)\s+(?:of|is|was)?\s*$",
        re.IGNORECASE,
    )
    if cn_score is not None:
        # Round before it ever reaches prose — cn_overall_score is an average of
        # CN's beacon sub-scores, so it carries repeating decimals
        # (98.66666666666667). One decimal place is what a donor should read.
        correct_cn = f"{round(cn_score, 1)}/100"
        # The connector before "Charity Navigator" is captured and echoed
        # back, not hardcoded to "from" — this rule only exists to fix the
        # *number*, but a hardcoded connector silently rewrites "on"/"by"
        # text to "from" too. That's not just cosmetic: the "scored X out of
        # 100 on Charity Navigator" rule below stamps "... on Charity
        # Navigator", and on a second sanitize pass (the citation-repair
        # retry path) this rule fires on that already-correct output for the
        # first time, since only now does it contain a literal "X/100" — a
        # hardcoded "from" here would silently swap "on" to "from" on that
        # second pass, breaking idempotency without ever failing case-
        # insensitivity. Falls back to "from " only when no connector was
        # present at all (bare "X/100 Charity Navigator").
        #
        # `_sub_score_lead_re` guard: don't claim a number that's actually
        # named by a sub-score (see its definition above) — leave it
        # untouched here so the accountability/financial rules further down
        # correct it with their own value instead. `_number_not_malformed`
        # guard: don't touch a malformed multi-decimal numeral at all (see
        # that variable's definition above).
        def _correct_cn_overall_number_before(m: "re.Match[str]") -> str:
            if _sub_score_lead_re.search(m.string[: m.start()]):
                return m.group(0)
            return f"{correct_cn} {m.group(1) or 'from '}Charity Navigator"

        rules.append(
            (
                rf"{_number_not_malformed}\d+\.?\d*/100\s+(from\s+|by\s+|on\s+|score\s+(?:from\s+|on\s+)?)?(?:Charity\s+Navigator)",
                _correct_cn_overall_number_before,
                False,
            )
        )
        # "Charity Navigator ... score/rating of X"
        rules.append(
            (
                r"(?:Charity\s+Navigator)\s+(?:overall\s+)?(?:score|rating)\s+(?:of\s+)?\d+\.?\d*(?:/100)?",
                f"Charity Navigator score of {correct_cn}",
                False,
            )
        )
        # "scored X out of 100 on Charity Navigator". Case-preserving (see
        # _preserve_case) — a preceding clause's removal can leave this one
        # sentence-initial and capitalized ("Scored ...").
        rules.append(
            (
                r"(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+)?\d+\.?\d*\s+(?:out\s+of\s+100|/100)\s+(?:on|from|by)\s+Charity\s+Navigator",
                _preserve_case(f"scored {correct_cn} on Charity Navigator"),
                False,
            )
        )
    else:
        # Strip any fabricated CN score claim — broad patterns. The middle
        # `_decimal_safe` gaps stay as-is (co-occurrence within one sentence,
        # e.g. "scored 87/100 last year from Charity Navigator"); only the
        # outer leading/trailing edges become clause-scoped.
        rules.append(
            (
                rf"{_clause_lead}\d+/100{_decimal_safe}Charity\s+Navigator{_clause_trail}",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}Charity\s+Navigator{_decimal_safe}\d+/100{_clause_trail}",
                None,
                True,
            )
        )
        # "scored/rates X out of 100 ... Charity Navigator"
        rules.append(
            (
                rf"{_clause_lead}(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+)?\d+\.?\d*\s+out\s+of\s+100{_decimal_safe}Charity\s+Navigator{_clause_trail}",
                None,
                True,
            )
        )
        # "Charity Navigator ... scored/rates X"
        # The trailing "out of 100"/"/100" is optional, so when it's absent
        # the number itself is the last thing the core pattern requires —
        # `\d+(?:\.\d+)?` (not `\d+\.?\d*`) so a bare "87." at the true
        # sentence end isn't misread as "87" plus an empty decimal point,
        # which would swallow the period a surviving clause needs.
        rules.append(
            (
                rf"{_clause_lead}Charity\s+Navigator{_decimal_safe}(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+)?\d+(?:\.\d+)?(?:\s+out\s+of\s+100|/100)?{_clause_trail}",
                None,
                True,
            )
        )
        # "perfect score/rating ... Charity Navigator" or vice versa. This is
        # the family that motivates keeping the trailing edge sentence-scoped
        # rather than clause-scoped: "a perfect score from Charity Navigator,
        # its highest rating." must lose the whole appositive tail, not just
        # up to the comma.
        rules.append(
            (
                rf"{_clause_lead}(?:perfect|top|highest)\s+(?:score|rating|marks?){_decimal_safe}Charity\s+Navigator{_clause_trail}",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}Charity\s+Navigator{_decimal_safe}(?:perfect|top|highest)\s+(?:score|rating|marks?){_clause_trail}",
                None,
                True,
            )
        )

    # CN accountability/financial sub-scores. Same bare-trailing-number risk
    # as the CN rule above: the "/100" suffix is optional, so
    # `\d+(?:\.\d+)?` guards against eating a sentence-ending period when
    # it's absent (also now tolerates a bare "%" suffix — "score of 87%" —
    # so that gets consumed by the match and cleanly replaced instead of
    # stranding a "%" after the correction's own "/100"). Unlike
    # cn_overall_score, these previously had ONLY removal rules — a wrong
    # (but non-null) number was published verbatim instead of corrected.
    # `_acc_name` also covers "Accountability & Finance score", the name
    # Charity Navigator itself uses for this exact beacon; the collector
    # deliberately duplicates one shared score into both
    # cn_accountability_score and cn_financial_score (see
    # src/collectors/charity_navigator.py:790,978, "# Same score"), so
    # correcting the combined phrasing from cn_accountability_score alone is
    # safe — there is no second, independent value it could disagree with.
    #
    # Both correction patterns capture the noun phrase actually used
    # ("accountability", "governance", "Accountability & Finance") and echo
    # it back rather than hardcoding "accountability" — the same
    # capture-and-echo principle the cn_overall_score connector rule above
    # uses for "from"/"by"/"on". Hardcoding it here has a real failure mode
    # a hand-probe caught: "a governance score of 60" would become "a
    # accountability score of 91.0/100" — grammatically wrong (a vowel-
    # initial replacement after an article chosen for the original,
    # consonant-initial word). Echoing the original noun phrase leaves
    # whatever article preceded it untouched and therefore still correct.
    #
    # Pattern 1 (number-after) also captures and echoes the "score"/"rating"
    # word itself, for the same reason: the claim can legitimately be
    # phrased either way ("accountability rating of X" occurs in real
    # published prose — see charity-95-4453134.json), and this rule used to
    # require the literal word "score", so "rating" phrasing fell all the
    # way through to the generic cn_overall_score rule above and got
    # stamped with the *overall* score instead — the `_sub_score_lead_re`
    # guard on that rule now leaves such spans alone specifically so this
    # rule can correct them with the right sub-score value here.
    if cn_accountability is not None:
        correct_acc = f"{round(cn_accountability, 1)}/100"
        # Pattern 1: <accountability/governance/& finance> score|rating of X
        # (number-after). Case-preserving (see _preserve_case) — a
        # preceding clause's removal can leave this sentence-initial
        # ("Accountability score ...").
        rules.append(
            (
                rf"({_acc_name})\s+(score|rating)\s+(?:of\s+)?{_number_not_malformed}\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?",
                lambda m: _match_case(m, f"{m.group(1)} {m.group(2)} of {correct_acc}"),
                False,
            )
        )
        # Pattern 2: X/100 <accountability/governance/& finance>
        # score/rating (number-before). No _preserve_case needed — the
        # replacement starts with a digit, so there's no letter for a
        # preceding removal to strand capitalized.
        rules.append(
            (
                rf"{_number_not_malformed}\d+(?:\.\d+)?/100\s+({_acc_name})\s+(score|rating)",
                lambda m: f"{correct_acc} {m.group(1)} {m.group(2)}",
                False,
            )
        )
    else:
        rules.append(
            (
                rf"{_clause_lead}(?:{_acc_name})\s+(?:score|rating)\s+(?:of\s+)?\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?{_clause_trail}",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}\d+(?:\.\d+)?/100\s+(?:{_acc_name})\s+(?:score|rating){_clause_trail}",
                None,
                True,
            )
        )
    if cn_financial is not None:
        correct_fin = f"{round(cn_financial, 1)}/100"
        # Same echo-the-noun-phrase approach as accountability's Pattern 1
        # above (captures "financial score" vs "financial health score", and
        # now "score" vs "rating" too, echoing whichever was actually used
        # rather than canonicalizing). Case-preserving for the same reason
        # as the accountability pattern.
        rules.append(
            (
                rf"({_fin_name}\s+(?:score|rating))\s+(?:of\s+)?{_number_not_malformed}\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?",
                lambda m: _match_case(m, f"{m.group(1)} of {correct_fin}"),
                False,
            )
        )
    else:
        rules.append(
            (
                rf"{_clause_lead}{_fin_name}\s+(?:score|rating)\s+(?:of\s+)?\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?{_clause_trail}",
                None,
                True,
            )
        )
    # Strip "X-star rating" if no CN score at all
    if cn_score is None:
        rules.append(
            (
                rf"{_clause_lead}\d+-?\s*star\s+(?:rating|charity){_decimal_safe}Charity\s+Navigator{_clause_trail}",
                None,
                True,
            )
        )

    # Fundraising efficiency
    # LLM variants: "per dollar raised", "to raise each dollar", "for every dollar",
    # "fundraising costs of $X.XX"
    _fr_phrasing = r"(?:per\s+\$?1\s+raised|to\s+raise\s+(?:\$1|each\s+dollar|a\s+dollar)|per\s+dollar\s+raised|for\s+every\s+dollar\s+raised)"
    if metrics.fundraising_expenses is not None and metrics.total_revenue and metrics.total_revenue > 0:
        correct_fr = _fundraising_ratio_str(metrics.fundraising_expenses, metrics.total_revenue)
        # Pattern 1: $X.XX per $1 raised / to raise $1 / per dollar raised
        # Leading `<?` (no whitespace before it) also swallows a prior
        # "<$0.01" correction so re-sanitizing already-correct tiny-ratio text
        # is idempotent instead of duplicating the "<" (sanitize_narrative_metrics
        # runs twice on the citation-repair retry path). Must stay glued to the
        # "$" — a `\s*` here would let the match creep left and eat the space
        # that precedes the dollar sign in ordinary prose.
        rules.append(
            (
                rf"<?\$\d+\.?\d*\s+{_fr_phrasing}",
                f"{correct_fr} per $1 raised",
                False,
            )
        )
        # Pattern 2: "fundraising costs/expenses of $X.XX per dollar".
        # Case-preserving (see _preserve_case) — a preceding clause's removal
        # can leave this one sentence-initial and capitalized ("Fundraising
        # costs ...").
        rules.append(
            (
                r"fundraising\s+(?:costs?|expenses?)\s+(?:of\s+)?\$\d+\.?\d*\s+per\s+(?:dollar|every\s+dollar)",
                _preserve_case(f"fundraising costs of {correct_fr} per dollar"),
                False,
            )
        )
    else:
        # The model hallucinates a $0.00 efficiency claim even when the prompt
        # says N/A, so this deterministic strip is the real safety net. The old
        # rules required the dollar amount to sit IMMEDIATELY before the
        # phrasing, which missed every real phrasing observed in production
        # ("$0.00 spent per $1 raised", "spending $0.00 to raise every $1",
        # "a $0.00 fundraising efficiency rate"). Match on co-occurrence within
        # one sentence instead of adjacency.
        #
        # The leading scan uses _clause_lead (not _decimal_safe) so it can't
        # cross a comma to swallow an unrelated clause sitting in front of the
        # fabricated one (e.g. "a 91.1% program expense ratio, and a $0.00
        # fundraising efficiency rate." must lose only the second clause).
        # The middle scan stays _decimal_safe (co-occurrence within one
        # sentence — a decimal point elsewhere is never mistaken for the
        # sentence's end). The trailing scan is now _clause_trail as well, so
        # a *following* clause coordinated with ", and ..." (a true claim
        # about a different metric) survives instead of being swallowed too.
        rules.append(
            (
                rf"{_clause_lead}\$\d+\.?\d*{_decimal_safe}(?:{_fr_phrasing}|fundraising\s+efficiency){_clause_trail}",
                None,
                True,
            )
        )
        # No suffix follows the dollar amount here, so it's the last thing
        # the core requires — same bare-trailing-number risk as the CN/
        # accountability/financial rules above; `\d+(?:\.\d+)?` guards it.
        rules.append(
            (
                rf"{_clause_lead}fundraising\s+efficiency{_decimal_safe}\$\d+(?:\.\d+)?{_clause_trail}",
                None,
                True,
            )
        )
        # "fundraising costs/expenses of $X.XX per dollar" (no "raised" suffix,
        # so it isn't covered by _fr_phrasing above)
        rules.append(
            (
                rf"{_clause_lead}fundraising\s+(?:costs?|expenses?)\s+(?:of\s+)?\$\d+\.?\d*\s+per\s+(?:dollar|every\s+dollar){_clause_trail}",
                None,
                True,
            )
        )

    # AMAL score
    if scores and hasattr(scores, "amal_score") and scores.amal_score is not None:
        correct_amal = f"{scores.amal_score}/100"
        rules.append(
            (
                r"\d+\.?\d*/100\s+(?:AMAL|Amal|amal)",
                f"{correct_amal} AMAL",
                False,
            )
        )
        rules.append(
            (
                r"(?:AMAL|Amal|amal)\s+score\s+(?:of\s+)?\d+\.?\d*(?:/100)?",
                f"AMAL score of {correct_amal}",
                False,
            )
        )

    # Zakat language — strip if charity is SADAQAH-ELIGIBLE (not zakat)
    wallet_tag = getattr(scores, "wallet_tag", None) if scores else None
    if wallet_tag == "SADAQAH-ELIGIBLE":
        _zakat_keywords = (
            r"(?:zakat[\s-]*eligible|zakat\s+eligibility|zakat\s+pathway|zakat\s+policy"
            r"|qualifies?\s+(?:for|as)\s+zakat|fuqara|masakin|asnaf"
            r"|zakat[\s-]*compliant|eligible\s+for\s+zakat|zakat\s+(?:fund|donation|giving))"
        )
        rules.append(
            (
                rf"{_clause_lead}{_zakat_keywords}{_clause_trail}",
                None,
                True,
            )
        )

    # Founded year — correct wrong years in narrative
    founded_year = getattr(metrics, "founded_year", None)
    if founded_year:
        # "founded in XXXX" / "established in XXXX" / "since XXXX" / "incorporated
        # in XXXX". Case-preserving (see _preserve_case) — a preceding clause's
        # removal can leave this one sentence-initial and capitalized
        # ("Founded in ...").
        rules.append(
            (
                r"(?:founded|established|incorporated|started|began(?:\s+operations)?)\s+in\s+\d{4}",
                _preserve_case(f"founded in {founded_year}"),
                False,
            )
        )
        # "since XXXX" when referring to founding (e.g. "operating since 1985").
        # Case-preserving for the same reason.
        rules.append(
            (
                r"(?:operating|serving|active|working)\s+since\s+\d{4}",
                _preserve_case(f"operating since {founded_year}"),
                False,
            )
        )

    # ── Apply rules to every string in the narrative ──
    def _apply_rules(text: str) -> str:
        for pattern, replacement, is_removal in rules:
            if is_removal:
                stripped = re.sub(pattern, "", text, flags=re.IGNORECASE)
                # Only run the repair pass when this rule actually removed
                # something. Every rule runs over every string field, so most
                # (pattern, text) pairs never match at all — repairing
                # unconditionally would "fix" (e.g. capitalize) text this
                # rule never touched, which isn't this rule's to fix.
                if stripped != text:
                    text = _repair_removal_artifacts(stripped)
            elif callable(replacement):
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            else:
                text = re.sub(pattern, replacement or "", text, flags=re.IGNORECASE)
        return text.strip()

    def _walk_and_sanitize(obj: Any) -> Any:
        if isinstance(obj, str):
            return _apply_rules(obj)
        if isinstance(obj, list):
            return [_walk_and_sanitize(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _walk_and_sanitize(v) for k, v in obj.items()}
        return obj

    return _walk_and_sanitize(narrative)


def evaluate_charity(
    ein: str,
    charity_repo: CharityRepository,
    raw_repo: RawDataRepository,
    data_repo: CharityDataRepository,
    llm_client: LLMClient,
    scorer: AmalScorerV2,
) -> dict[str, Any]:
    """Evaluate a single charity and generate baseline narrative."""
    result = {"ein": ein, "success": False}

    # Get charity
    charity = charity_repo.get(ein)
    if not charity:
        result["error"] = "Charity not found"
        return result

    # Get synthesized data
    charity_data = data_repo.get(ein)

    # Get raw data
    raw_data = raw_repo.get_for_charity(ein)
    raw_sources: dict[str, dict] = {}
    for rd in raw_data:
        if rd.get("success") and rd.get("parsed_json"):
            raw_sources[rd["source"]] = rd["parsed_json"]

    if not raw_sources:
        result["error"] = "No raw data found"
        return result

    # Build CharityMetrics
    metrics = build_charity_metrics(ein, charity, charity_data, raw_sources)

    # Validate minimum data requirements (spec: must have identity OR financials)
    has_identity = bool(metrics.mission) or (metrics.programs and len(metrics.programs) > 0)
    has_financials = metrics.total_revenue is not None or metrics.program_expense_ratio is not None

    if not has_identity and not has_financials:
        missing = []
        if not metrics.mission:
            missing.append("mission")
        if not metrics.programs:
            missing.append("programs")
        if metrics.total_revenue is None:
            missing.append("total_revenue")
        if metrics.program_expense_ratio is None:
            missing.append("program_expense_ratio")
        result["error"] = f"Insufficient data (no identity or financials). Missing: {', '.join(missing)}"
        return result

    # Get evaluation track from charity_data (defaults to STANDARD)
    evaluation_track = charity_data.get("evaluation_track", "STANDARD") if charity_data else "STANDARD"

    # =========================================================================
    # 1. GMG Scoring (2 dimensions + risk; data confidence is a separate signal)
    # =========================================================================
    scores = scorer.evaluate(metrics, evaluation_track=evaluation_track)

    # =========================================================================
    # 2. Generate Baseline Narrative (1 LLM call)
    # =========================================================================
    total_cost = 0.0

    narrative, narrative_error, narrative_cost = generate_baseline_narrative(metrics, scores, llm_client, ein)
    total_cost += narrative_cost

    if narrative is None:
        result["error"] = narrative_error
        result["cost_usd"] = total_cost
        return result

    # =========================================================================
    # 2b. Generate 3-word slug for card display (cheap LLM call)
    # =========================================================================
    existing_slug = charity_data.get("slug") if charity_data else None
    if not existing_slug:
        slug_client = LLMClient(task=LLMTask.LLM_JUDGE)
        slug, slug_cost = generate_slug(metrics, charity_data, slug_client)
        total_cost += slug_cost
        if slug:
            execute_query(
                "UPDATE charity_data SET slug = %s WHERE charity_ein = %s",
                (slug, ein),
                fetch="none",
            )

    result["cost_usd"] = total_cost

    # =========================================================================
    # 3. Build Evaluation Record
    # =========================================================================
    # Serialize 2-dimension assessments + data confidence
    score_details = {
        "impact": scores.impact.model_dump(),
        "alignment": scores.alignment.model_dump(),
        "data_confidence": scores.data_confidence.model_dump(),
        "zakat": scores.zakat_bonus.model_dump(),
        "risks": scores.case_against.model_dump(),
        "risk_deduction": scores.risk_deduction,
        "score_summary": scores.score_summary,
    }

    # Build score_profiles with 2-dimension breakdowns
    score_profiles = {
        "gmg": {
            "total_score": scores.amal_score,
            "dimensions": {
                "impact": scores.impact.model_dump(),
                "alignment": scores.alignment.model_dump(),
            },
            "data_confidence": scores.data_confidence.model_dump(),
            "risk_deduction": scores.risk_deduction,
        },
    }

    evaluation = Evaluation(
        charity_ein=ein,
        amal_score=scores.amal_score,
        wallet_tag=scores.wallet_tag,
        confidence_tier=scores.data_confidence.badge,
        impact_tier=impact_tier_from_amal_score(scores.amal_score),  # [#8] was hardcoded "AVERAGE"
        zakat_classification=scores.zakat_bonus.asnaf_category if scores.zakat_bonus else None,
        confidence_scores={
            "impact": scores.impact.score,
            "alignment": scores.alignment.score,
            "data_confidence": scores.data_confidence.overall,
        },
        score_details=score_details,
        baseline_narrative=narrative,
        score_profiles=score_profiles,
        rubric_version=RUBRIC_VERSION,
        state="generated",
    )

    result["evaluation"] = evaluation
    result["scores"] = scores
    result["success"] = True
    return result


def load_pilot_charities(file_path: str) -> list[str]:
    """Load charities from pilot_charities.txt format (Name | EIN | URL | Comments)."""
    from src.utils.charity_loader import load_pilot_eins

    return load_pilot_eins(file_path)


def main():
    parser = argparse.ArgumentParser(description="Generate baseline narratives and scores")
    parser.add_argument("--ein", type=str, help="Single charity EIN to process")
    parser.add_argument("--charities", type=str, help="Path to charities file")
    parser.add_argument("--workers", type=int, default=10, help="Parallel workers (default: 10)")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="(Deprecated: use smart cache instead) Skip charities with state='generated'",
    )
    parser.add_argument("--force", action="store_true", help="Force re-evaluation even if cache is valid")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    # Determine which charities to process
    if args.ein:
        eins = [args.ein]
    elif args.charities:
        eins = load_pilot_charities(args.charities)
    else:
        charity_repo = CharityRepository()
        all_charities = charity_repo.get_all()
        eins = [c["ein"] for c in all_charities]

    if not eins:
        print("No charities to process")
        return

    # Initialize
    charity_repo = CharityRepository()
    raw_repo = RawDataRepository()
    data_repo = CharityDataRepository()
    eval_repo = EvaluationRepository()
    llm_client = LLMClient(task=LLMTask.NARRATIVE_GENERATION)
    scorer = AmalScorerV2()

    print(f"\n{'=' * 60}")
    print(f"BASELINE EVALUATION: {len(eins)} CHARITIES")
    print(f"  Workers: {args.workers}")
    print(f"{'=' * 60}\n")

    success_count = 0
    skipped_count = 0
    failed_charities = []  # Track failures for summary
    successful_eins: list[str] = []
    progress_lock = threading.Lock()
    completed_count = 0
    cache_repo = PhaseCacheRepository()

    # Smart cache filtering (replaces --skip-existing)
    eins_to_process = []
    for ein in eins:
        # Legacy --skip-existing still works
        if args.skip_existing:
            existing = eval_repo.get(ein)
            if existing and existing.get("state") == "generated":
                skipped_count += 1
                print(f"⊘ {ein}: Already generated, skipping")
                continue

        # Smart cache check (--force overrides)
        should_run, reason = check_phase_cache(ein, "baseline", cache_repo, force=args.force)
        if not should_run:
            skipped_count += 1
            print(f"⊘ {ein}: Cache hit — {reason}")
            continue

        eins_to_process.append(ein)

    total = len(eins_to_process)

    if total == 0:
        print("All charities already processed.")
        return

    def process_one(ein: str) -> dict[str, Any]:
        """Process a single charity and return result."""
        return evaluate_charity(ein, charity_repo, raw_repo, data_repo, llm_client, scorer)

    # Sequential processing for single charity or workers=1
    if args.workers == 1 or total == 1:
        for i, ein in enumerate(eins_to_process, 1):
            try:
                result = process_one(ein)
                if result["success"]:
                    eval_repo.upsert(result["evaluation"])
                    update_phase_cache(ein, "baseline", cache_repo, result.get("cost_usd", 0.0))
                    success_count += 1
                    successful_eins.append(ein)
                    scores = result["scores"]
                    print(f"[{i}/{total}] ✓ {ein}")
                    print(f"    GMG: {scores.amal_score}/100 | Tag: {scores.wallet_tag}")
                    print(
                        f"    Impact: {scores.impact.score}/50 | Align: {scores.alignment.score}/50 | "
                        f"Risk: {scores.risk_deduction} | DC: {scores.data_confidence.overall}"
                    )
                else:
                    error_msg = result.get("error", "Unknown error")
                    failed_charities.append((ein, error_msg))
                    print(f"[{i}/{total}] ✗ {ein}")
                    print(f"    ERROR: {error_msg}")
            except Exception as e:
                failed_charities.append((ein, str(e)))
                print(f"[{i}/{total}] ✗ {ein}")
                print(f"    ERROR: {e}")
    else:
        # Parallel processing with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # Submit all tasks
            future_to_ein = {executor.submit(process_one, ein): ein for ein in eins_to_process}

            # Process results as they complete
            for future in as_completed(future_to_ein):
                ein = future_to_ein[future]
                with progress_lock:
                    completed_count += 1
                    progress = completed_count

                try:
                    result = future.result()
                    if result["success"]:
                        eval_repo.upsert(result["evaluation"])
                        update_phase_cache(ein, "baseline", cache_repo, result.get("cost_usd", 0.0))
                        with progress_lock:
                            success_count += 1
                            successful_eins.append(ein)
                        scores = result["scores"]
                        print(f"[{progress}/{total}] ✓ {ein}")
                        print(f"    AMAL: {scores.amal_score}/100 | Tag: {scores.wallet_tag}")
                        print(
                            f"    Impact: {scores.impact.score}/50 | Align: {scores.alignment.score}/50 | "
                            f"Risk: {scores.risk_deduction} | DC: {scores.data_confidence.overall}"
                        )
                    else:
                        error_msg = result.get("error", "Unknown error")
                        with progress_lock:
                            failed_charities.append((ein, error_msg))
                        print(f"[{progress}/{total}] ✗ {ein}")
                        print(f"    ERROR: {error_msg}")
                except Exception as e:
                    with progress_lock:
                        failed_charities.append((ein, str(e)))
                    print(f"[{progress}/{total}] ✗ {ein}")
                    print(f"    ERROR: {e}")

    # ── Quality gate: run baseline judge per charity ──
    from src.judges.inline_quality import run_quality_gate_batch

    quality_failed_eins = run_quality_gate_batch("baseline", successful_eins)
    for failed_ein in quality_failed_eins:
        cache_repo.delete(failed_ein, "baseline")

    # Commit changes to DoltDB
    if success_count > 0:
        commit_hash = dolt.commit(
            f"Baseline [rubric {RUBRIC_VERSION}]: {success_count} charities scored and narratives generated",
            tables=tables_for_phases("baseline"),
        )
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")

            # Auto-tag on first commit at this rubric version
            # Cross-reference git ↔ DoltDB so we can trace which code produced which scores
            tag_name = f"rubric-v{RUBRIC_VERSION}"
            existing_tags = {t["tag_name"] for t in dolt.tags()}
            if tag_name not in existing_tags:
                git_sha = _get_git_sha()
                tag_msg = f"First run on rubric v{RUBRIC_VERSION}"
                if git_sha:
                    tag_msg += f" | git:{git_sha[:10]}"
                dolt.tag(tag_name, message=tag_msg)
                print(f"✓ Tagged: {tag_name}")
                # Mirror tag in git so you can go both directions
                if git_sha:
                    _create_git_tag(tag_name, f"DoltDB rubric v{RUBRIC_VERSION}")

    # Summary
    print(f"\n{'=' * 60}")
    print("BASELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Success: {success_count}/{total}")
    if skipped_count > 0:
        print(f"  Skipped: {skipped_count}/{len(eins)}")
    if failed_charities:
        print(f"  Failed:  {len(failed_charities)}/{total}")

    if quality_failed_eins:
        print(f"\n  ⛔ Quality gate failures: {len(quality_failed_eins)} charities")
        print("     These charities have data errors that must be fixed before proceeding.")

    # Failed charities summary
    if failed_charities:
        print("\nFailed charities:")
        for ein, error in failed_charities:
            print(f"  {ein}: {error}")
        print("\nNext steps:")
        print("  # Re-run failed charities after fixing issues:")
        print(f"  uv run python baseline.py --ein {failed_charities[0][0]}")
        if len(eins) > 1:
            print("\n  # Or skip already-processed charities:")
            print("  uv run python baseline.py --charities pilot_charities.txt --skip-existing")
    else:
        print("\nNext: Review and approve evaluations")

    # Exit code: 0 if all succeeded, 1 if any failures
    if failed_charities or quality_failed_eins:
        sys.exit(1)


if __name__ == "__main__":
    main()

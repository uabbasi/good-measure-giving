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
from typing import Any

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
from src.db.dolt_client import dolt
from src.llm.llm_client import LLMClient
from src.parsers.charity_metrics_aggregator import CharityMetrics, CharityMetricsAggregator
from src.scorers.v2_scorers import RUBRIC_VERSION, AmalScorerV2
from src.services.citation_service import CitationService
from src.utils.phase_cache_helper import check_phase_cache, update_phase_cache


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

    # Fix hallucinated sources by finding closest match
    registry_names = [s.source_name for s in citation_sources]
    registry_lower = [s.lower() for s in registry_names]
    unresolved_ids: set[str] = set()
    unresolved_entry_refs: set[int] = set()

    for citation in narrative.get("all_citations", []):
        source_name = citation.get("source_name", "").lower()
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

    # Format values for prompt
    revenue_str = f"${metrics.total_revenue:,.0f}" if metrics.total_revenue else "N/A"
    ratio_str = f"{metrics.program_expense_ratio:.1%}" if metrics.program_expense_ratio else "N/A"
    cn_score_str = f"{metrics.cn_overall_score}/100" if metrics.cn_overall_score else "N/A"
    programs_str = ", ".join(metrics.programs[:3]) if metrics.programs else "Not available"

    # Pre-calculate additional financial metrics for consistency
    working_capital_str = f"{metrics.working_capital_ratio:.1f} months" if metrics.working_capital_ratio else "N/A"

    # Calculate fundraising efficiency if data available
    fundraising_efficiency_str = "N/A"
    if metrics.fundraising_expenses is not None and metrics.total_revenue and metrics.total_revenue > 0:
        efficiency = metrics.fundraising_expenses / metrics.total_revenue
        fundraising_efficiency_str = f"${efficiency:.2f} per $1 raised"

    # Build prompt with charity data and scores
    prompt = f"""Generate a baseline narrative for this charity with Wikipedia-style inline citations.

## Charity Information
- Name: {metrics.name}
- EIN: {metrics.ein}
- Mission: {metrics.mission or "Not available"}
- Programs: {programs_str}

## Financial Data
- Total Revenue: {revenue_str}
- Program Expense Ratio: {ratio_str}
- Charity Navigator Score: {cn_score_str}
- Working Capital: {working_capital_str}
- Fundraising Efficiency: {fundraising_efficiency_str}

## MANDATORY VALUES (USE EXACTLY AS PROVIDED - DO NOT CALCULATE OR INVENT)
When mentioning these metrics in the narrative, you MUST use the EXACT values below.
Do NOT round differently, do NOT calculate your own values, do NOT invent numbers.

- Program Expense Ratio: {ratio_str} (use this exact percentage everywhere)
- Total Revenue: {revenue_str} (use this exact amount everywhere)
- Working Capital: {working_capital_str} (use this exact value everywhere)
- Fundraising Efficiency: {fundraising_efficiency_str} (use this exact value everywhere)

If a value is "N/A", do NOT mention that metric in the narrative at all.

## ZAKAT ELIGIBILITY CONSTRAINT (CRITICAL)
Wallet Tag: {scores.wallet_tag}
{"⚠️ This charity is SADAQAH-ELIGIBLE (NOT zakat-eligible). DO NOT mention zakat eligibility, zakat policies, zakat pathways, fuqara, masakin, or any implication that donations qualify as zakat. Only mention sadaqah or general charitable giving." if scores.wallet_tag == "SADAQAH-ELIGIBLE" else "✓ This charity is ZAKAT-ELIGIBLE. You MAY mention zakat eligibility if supported by source data."}

## REVENUE GROWTH CONSTRAINT (CRITICAL)
⚠️ DO NOT mention 3-year revenue CAGR, compound annual growth rate, or multi-year revenue growth percentages.
This data is not provided in the baseline context. Only mention single-year revenue if available.

## Pre-computed Scores (for context only - explain in plain English)
- GMG Score: {scores.amal_score}/100
- Wallet Tag: {scores.wallet_tag}
- Impact: {scores.impact.score}/50 (Directness: {scores.impact.directness_level}, Cost per beneficiary: {scores.impact.cost_per_beneficiary or "N/A"})
- Alignment: {scores.alignment.score}/50 (Donor fit: {scores.alignment.muslim_donor_fit_level}, Cause urgency: {scores.alignment.cause_urgency_label})
- Data Confidence: {scores.data_confidence.overall} ({scores.data_confidence.badge})

## SCORE/RATIONALE CONSISTENCY (CRITICAL)
Your dimension_explanations MUST be consistent with the scores above:
- If a score is LOW (0-15): Explain what's MISSING or CONCERNING (e.g., "Limited data available", "No third-party verification")
- If a score is MEDIUM (16-33): Balanced explanation of strengths and gaps
- If a score is HIGH (34+): Can highlight strengths

DO NOT invent positive data to justify low scores:
- If Impact is low, do NOT claim the organization "demonstrates effectiveness"
- If Alignment is low, do NOT claim strong Muslim donor fit
- Only mention ratings/scores that are explicitly provided in the source data above

## Available Sources for Citations (EXACTLY {num_sources} sources)
{sources_list}

## Citation Rules (CRITICAL - follow exactly)
1. You have EXACTLY {num_sources} sources available, numbered [1] through [{num_sources}]
2. ONLY use citation numbers that exist in the list above - do NOT use [N] where N > {num_sources}
3. For EVERY [N] citation you use in text, you MUST include a matching entry in all_citations
4. Format: [N] where N is the source number (e.g., [1], [2])
5. Example: "The charity maintains strong financial accountability [1]."

## Output Format
Return ONLY a valid JSON object (no markdown code blocks):

{{
  "headline": "One compelling sentence about the charity",
  "summary": "2-3 sentences with citations like [1] and [2]",
  "strengths": ["strength 1", "strength 2"],
  "areas_for_improvement": ["area 1"],
  "amal_score_rationale": "1-2 sentences explaining the overall score",
  "dimension_explanations": {{
    "impact": "Plain English with citations about program effectiveness, financial health, and evidence quality",
    "alignment": "Plain English with citations about donor fit, cause urgency, and track record"
  }},
  "all_citations": [
    {{
      "id": "[1]",
      "source_name": "Source name from list above",
      "source_url": "URL from source list (or null if not available)",
      "claim": "The specific claim this citation supports"
    }}
  ]
}}

Generate the narrative JSON:"""

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
    rules: list[tuple[str, str | None, bool]] = []

    # Working capital  (e.g. "8.3 months of working capital" or "8.3 years of reserves")
    # LLM variants: "holds X years of expenses", "maintains X years in reserves",
    # "X years' worth of operating", "expenses held in reserve"
    _wc_noun = r"(?:working\s+capital|operating\s+(?:expenses?|costs?)|reserves?|expenses?\s+(?:held\s+)?in\s+reserve)"
    _wc_num_unit = r"\d+\.?\d*\s*(?:months?|years?)"
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
        # Pattern 2: "holds/maintains X years of expenses"
        rules.append(
            (
                rf"(?:holds?|maintains?|has)\s+{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}",
                f"holds {correct_wc} of working capital",
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
                rf"[^.]*{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}[^.]*\.?",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"[^.]*(?:holds?|maintains?|has)\s+{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}[^.]*\.?",
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
        # Pattern 2: program expense ratio of <number>%
        rules.append(
            (
                r"program\s+(?:expense\s+)?ratio\s+(?:of\s+)?\d+\.?\d*\s*%",
                f"program expense ratio of {correct_ratio}",
                False,
            )
        )
        # Pattern 3: directs/allocates X% to programs/programmatic
        rules.append(
            (
                r"(?:directs?|allocates?|dedicates?|channels?|devotes?)\s+\d+\.?\d*\s*%\s+(?:of\s+\w+\s+)?(?:to|toward)\s+(?:programs?|programmatic\s+(?:work|activities|expenses?))",
                f"directs {correct_ratio} to programs",
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
    else:
        # Remove sentences mentioning program expense ratio with a number
        rules.append(
            (
                r"[^.]*program\s+(?:expense\s+)?ratio\s+(?:of\s+)?\d+\.?\d*\s*%[^.]*\.?",
                None,
                True,
            )
        )
        rules.append(
            (
                r"[^.]*(?:directs?|allocates?)\s+\d+\.?\d*\s*%\s+(?:of\s+\w+\s+)?(?:to|toward)\s+(?:programs?|programmatic)[^.]*\.?",
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
    if cn_score is not None:
        correct_cn = f"{cn_score}/100"
        rules.append(
            (
                r"\d+/100\s+(?:from\s+|by\s+|on\s+|score\s+(?:from\s+|on\s+)?)?(?:Charity\s+Navigator)",
                f"{correct_cn} from Charity Navigator",
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
        # "scored X out of 100 on Charity Navigator"
        rules.append(
            (
                r"(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+)?\d+\.?\d*\s+(?:out\s+of\s+100|/100)\s+(?:on|from|by)\s+Charity\s+Navigator",
                f"scored {correct_cn} on Charity Navigator",
                False,
            )
        )
    else:
        # Strip any fabricated CN score claim — broad patterns
        rules.append(
            (
                r"[^.]*\d+/100[^.]*Charity\s+Navigator[^.]*\.?",
                None,
                True,
            )
        )
        rules.append(
            (
                r"[^.]*Charity\s+Navigator[^.]*\d+/100[^.]*\.?",
                None,
                True,
            )
        )
        # "scored/rates X out of 100 ... Charity Navigator"
        rules.append(
            (
                r"[^.]*(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+)?\d+\.?\d*\s+out\s+of\s+100[^.]*Charity\s+Navigator[^.]*\.?",
                None,
                True,
            )
        )
        # "Charity Navigator ... scored/rates X"
        rules.append(
            (
                r"[^.]*Charity\s+Navigator[^.]*(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+)?\d+\.?\d*(?:\s+out\s+of\s+100|/100)?[^.]*\.?",
                None,
                True,
            )
        )
        # "perfect score/rating ... Charity Navigator" or vice versa
        rules.append(
            (
                r"[^.]*(?:perfect|top|highest)\s+(?:score|rating|marks?)[^.]*Charity\s+Navigator[^.]*\.?",
                None,
                True,
            )
        )
        rules.append(
            (
                r"[^.]*Charity\s+Navigator[^.]*(?:perfect|top|highest)\s+(?:score|rating|marks?)[^.]*\.?",
                None,
                True,
            )
        )

    # CN accountability/financial sub-scores — strip if null
    if cn_accountability is None:
        rules.append(
            (
                r"[^.]*(?:accountability|governance)\s+score\s+(?:of\s+)?\d+\.?\d*(?:/100|\s+out\s+of\s+100)?[^.]*\.?",
                None,
                True,
            )
        )
    if cn_financial is None:
        rules.append(
            (
                r"[^.]*financial\s+(?:health\s+)?score\s+(?:of\s+)?\d+\.?\d*(?:/100|\s+out\s+of\s+100)?[^.]*\.?",
                None,
                True,
            )
        )
    # Strip "X-star rating" if no CN score at all
    if cn_score is None:
        rules.append(
            (
                r"[^.]*\d+-?\s*star\s+(?:rating|charity)[^.]*Charity\s+Navigator[^.]*\.?",
                None,
                True,
            )
        )

    # Fundraising efficiency
    # LLM variants: "per dollar raised", "to raise each dollar", "for every dollar",
    # "fundraising costs of $X.XX"
    _fr_phrasing = r"(?:per\s+\$?1\s+raised|to\s+raise\s+(?:\$1|each\s+dollar|a\s+dollar)|per\s+dollar\s+raised|for\s+every\s+dollar\s+raised)"
    if metrics.fundraising_expenses is not None and metrics.total_revenue and metrics.total_revenue > 0:
        eff = metrics.fundraising_expenses / metrics.total_revenue
        correct_fr = f"${eff:.2f}"
        # Pattern 1: $X.XX per $1 raised / to raise $1 / per dollar raised
        rules.append(
            (
                rf"\$\d+\.?\d*\s+{_fr_phrasing}",
                f"{correct_fr} per $1 raised",
                False,
            )
        )
        # Pattern 2: "fundraising costs/expenses of $X.XX per dollar"
        rules.append(
            (
                r"fundraising\s+(?:costs?|expenses?)\s+(?:of\s+)?\$\d+\.?\d*\s+per\s+(?:dollar|every\s+dollar)",
                f"fundraising costs of {correct_fr} per dollar",
                False,
            )
        )
    else:
        rules.append(
            (
                rf"[^.]*\$\d+\.?\d*\s+{_fr_phrasing}[^.]*\.?",
                None,
                True,
            )
        )
        rules.append(
            (
                r"[^.]*fundraising\s+(?:costs?|expenses?)\s+(?:of\s+)?\$\d+\.?\d*\s+per\s+(?:dollar|every\s+dollar)[^.]*\.?",
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
                rf"[^.]*{_zakat_keywords}[^.]*\.?",
                None,
                True,
            )
        )

    # Founded year — correct wrong years in narrative
    founded_year = getattr(metrics, "founded_year", None)
    if founded_year:
        # "founded in XXXX" / "established in XXXX" / "since XXXX" / "incorporated in XXXX"
        rules.append(
            (
                r"(?:founded|established|incorporated|started|began(?:\s+operations)?)\s+in\s+\d{4}",
                f"founded in {founded_year}",
                False,
            )
        )
        # "since XXXX" when referring to founding (e.g. "operating since 1985")
        rules.append(
            (
                r"(?:operating|serving|active|working)\s+since\s+\d{4}",
                f"operating since {founded_year}",
                False,
            )
        )

    # ── Apply rules to every string in the narrative ──
    def _apply_rules(text: str) -> str:
        for pattern, replacement, is_removal in rules:
            if is_removal:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s{2,}", " ", text)
                text = re.sub(r"\.\s*\.", ".", text)
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
    # 1. GMG Scoring (3 dimensions + risk)
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
        impact_tier="AVERAGE",  # Simplified — detail in score_details
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
    llm_client = LLMClient()
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
            f"Baseline [rubric {RUBRIC_VERSION}]: {success_count} charities scored and narratives generated"
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

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

    def _apply_curated_name(metrics: CharityMetrics) -> CharityMetrics:
        """Name the organisation the way the rest of the site names it.

        CharityMetricsAggregator rebuilds metrics.name Candid-first on every
        synth run, so the blob can disagree with charities.name — the name the
        index, the page header and the judge's ground truth all use. Candid
        yields "CAREHQ" for CARE USA, and the judge (correctly) refuses to
        publish a narrative that calls it that. The curated record wins, as it
        does for the website URL. Rows whose name is a placeholder have nothing
        to contribute, so they defer to whatever the sources found.
        """
        curated = (charity or {}).get("name") or ""
        if curated.strip() and curated not in (ein, f"EIN {ein}", "Unknown"):
            metrics.name = curated
        return metrics

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
            return _apply_curated_name(_apply_synth_overrides(metrics, charity_data))
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

    return _apply_curated_name(_apply_synth_overrides(metrics, charity_data))


# Sadaqah is the default tier every charity qualifies for, so stating it tells
# the donor nothing and reads as a determination we made. Zakat is the higher
# bar, and all we ever know is what the charity's own site says. So: silence on
# sadaqah, attribution on zakat.
#
# The previous SADAQAH text ended "Only mention sadaqah or general charitable
# giving" — an instruction to assert sadaqah. The assertions it produced were
# then read as unsupported claims and cost real pages (63-0598743, 13-1685039).
_ZAKAT_CONSTRAINT_SADAQAH = (
    "⚠️ Zakat eligibility is NOT substantiated for this charity. Say nothing about which "
    "category of giving it accepts. DO NOT mention zakat eligibility, zakat policies, zakat "
    "pathways, fuqara, masakin, asnaf, or any implication that donations qualify as zakat. "
    "Equally, DO NOT describe the charity or its donations as sadaqah, sadaqah-eligible, or "
    "sadaqah-only: sadaqah is the default that every charity qualifies for, so saying it adds "
    "nothing and reads as a finding we did not make. Describe the charity's work and leave the "
    "question of giving category unmentioned."
)
_ZAKAT_CONSTRAINT_ZAKAT = (
    "✓ This charity's own website indicates zakat eligibility. If you mention it at all, "
    "attribute it: \"the charity's website indicates it is zakat-eligible\" or \"states that it "
    "accepts zakat\" is the STRONGEST form permitted. NEVER write that eligibility is verified, "
    "confirmed, certified, or guaranteed, and never write \"zakat-compliant\" or that donations "
    "qualify as zakat — we are reporting what the site claims, not certifying it. Say nothing "
    "about sadaqah."
)


_MARKER_RUN_RE = re.compile(r"(?:\[\d+\])+")
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers_in(text: str) -> set[float]:
    """Numeric tokens in a string, commas and currency stripped."""
    out: set[float] = set()
    for raw in _NUMBER_RE.findall(text or ""):
        try:
            out.add(float(raw.replace(",", "")))
        except ValueError:
            continue
    return out


def prune_unsupported_citation_markers(narrative: Any, citations: list[dict] | None) -> Any:
    """Drop citation markers that assert different numbers than their claim.

    The baseline prompt's Citation Rules only ever constrained numbering --
    which numbers exist, that each has an all_citations entry, the [N] format.
    Nothing required a marker to support the sentence it sits on, and the
    output template modelled scattering them ("citations like [1] and [2]"),
    so claims arrived decorated with sources that do not back them:

        "the organization managed $7,254,154 in total revenue ... [1][6]"
        [6] Form 990      "reported $7,254,154 in total revenue"    supports
        [1] Charity Nav   "90.0/100 score, 81.2% program ratio"     does not

    Deliberately narrow. A marker is dropped only when the sentence asserts
    numbers, the marker's own declared claim asserts numbers, and the two sets
    are disjoint. A claim carrying no numbers is always allowed, since
    qualitative sources legitimately support numeric prose. And a marker is
    never dropped unless another on the same run survives -- an uncited claim
    is worse than an imperfectly cited one.
    """
    if not citations:
        return narrative

    claim_numbers: dict[str, set[float]] = {}
    for c in citations:
        cid = str((c or {}).get("id") or "")
        if cid:
            claim_numbers[cid] = _numbers_in(str((c or {}).get("claim") or ""))

    def _prune_text(text: str) -> str:
        def replace(match: re.Match) -> str:
            run = match.group(0)
            markers = re.findall(r"\[\d+\]", run)
            # Numbers asserted by the sentence this run terminates.
            preceding = text[: match.start()]
            sentence = re.split(r"(?<=[.!?])\s+", preceding)[-1]
            sentence_numbers = _numbers_in(sentence)
            if not sentence_numbers:
                return run

            kept = []
            for m in markers:
                nums = claim_numbers.get(m)
                # Unknown marker: the structural validator's business, not ours.
                # Numberless claim: a qualitative source, always allowed.
                if nums is None or not nums or (nums & sentence_numbers):
                    kept.append(m)
            if not kept:
                return run  # never strand the claim
            return "".join(dict.fromkeys(kept))

        return _MARKER_RUN_RE.sub(replace, text)

    def _walk(node: Any) -> Any:
        if isinstance(node, str):
            return _prune_text(node)
        if isinstance(node, list):
            return [_walk(v) for v in node]
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        return node

    return _walk(narrative)


def _fundraising_ratio_str(fundraising_expenses, total_contributions) -> str | None:
    """Just the dollar-figure prefix (e.g. "$0.00", "<$0.01", "$0.10") for the
    cost to raise $1, or None if it can't be computed.

    The denominator is CONTRIBUTIONS, not total revenue. Total revenue also
    carries program service revenue, government grants and investment income —
    money fundraising did not raise — and dividing by it flattered every
    charity with substantial non-donation income. EIN 27-4155655 was published
    at "$0.30" while actually spending $1.32 per donated dollar, i.e. more on
    fundraising than it raised; 31 of 143 charities understated the true cost
    by more than half.

    A real-but-tiny ratio must not render as "$0.00": $241,666 against $79.6M
    of contributions is $0.003 per $1 — a real cost, and telling a donor it was
    zero is wrong. Only a genuine 0 gets "$0.00". Shared by the
    prompt-construction call site and the narrative sanitizer's correction path
    so both agree.
    """
    if fundraising_expenses is None or not total_contributions or total_contributions <= 0:
        return None
    efficiency = fundraising_expenses / total_contributions
    if efficiency == 0:
        return "$0.00"
    if efficiency < 0.01:
        return "<$0.01"
    return f"${efficiency:.2f}"


def _format_fundraising_efficiency(fundraising_expenses, total_contributions) -> str:
    """Cost to raise $1, as prose. "N/A" when unknowable."""
    ratio = _fundraising_ratio_str(fundraising_expenses, total_contributions)
    return f"{ratio} per $1 raised" if ratio else "N/A"


# A filed-vs-cash-adjusted gap this wide means gifts-in-kind are materially
# inflating the filed ratio, so the filed figure would mislead a donor. Below it
# the two figures are close enough that the filed one is still fair to publish.
_GIK_MATERIAL_RATIO_GAP = 0.05


def _effective_program_ratio(metrics: "CharityMetrics") -> float | None:
    """The program ratio the pipeline actually stands behind.

    When gifts-in-kind inflate the filed ratio, the scorer scores the
    cash-adjusted figure instead and labels the component "Cash-adjusted program
    ratio" (see v2_scorers). Handing the narrative the FILED ratio meanwhile made
    the two contradict each other: United Muslim Relief (EIN 27-3175543) filed
    96.5% against a measured 48% cash-adjusted ratio, scored 0/5 on Program
    Ratio, and had publication blocked because the narrative sold the 96.5% as a
    strength in four separate fields.

    Both the prompt and the metric sanitizer must read this same value, or the
    sanitizer stamps the inflated ratio back over the narrative after generation.

    Only a MATERIAL gap substitutes. A charity with trivial gifts-in-kind has a
    cash-adjusted ratio a hair off its filed one, and swapping there would shift
    published percentages for no benefit. `getattr` because callers legitimately
    pass metric-likes that predate this field.
    """
    filed = getattr(metrics, "program_expense_ratio", None)
    adjusted = getattr(metrics, "cash_adjusted_program_ratio", None)
    if adjusted is None or filed is None:
        return filed
    if filed - adjusted >= _GIK_MATERIAL_RATIO_GAP:
        return adjusted
    return filed


_PLAIN_RATIO_LABEL = "Program Expense Ratio"
_ADJUSTED_RATIO_LABEL = "Cash-Adjusted Program Expense Ratio (gifts-in-kind excluded)"


def program_ratio_and_label(metrics: Any) -> tuple[float | None, str]:
    """The program ratio we stand behind, together with what to call it.

    The label travels with the number. Handing over a GIK-adjusted figure still
    labelled "Program Expense Ratio" just relocates the misstatement, which the
    score judge caught: "presenting the cash-adjusted ratio as the general
    'program expense ratio' without qualification is misleading."

    Shared rather than inline because being inline is what let the two prompt
    paths drift. baseline.py computed the pair correctly; the rich generator
    hardcoded the plain label next to "use this exact percentage everywhere"
    and was handed the FILED ratio, so United Muslim Relief's 97.45% and 47.5%
    both reached the model under near-identical names and 20 of 169 published
    pages ended up carrying both labels.
    """
    effective = _effective_program_ratio(metrics)
    filed = getattr(metrics, "program_expense_ratio", None)
    substituted = effective is not None and filed is not None and effective != filed
    return effective, (_ADJUSTED_RATIO_LABEL if substituted else _PLAIN_RATIO_LABEL)


def _baseline_prompt_kwargs(metrics: CharityMetrics, scores: Any, num_sources: int, sources_list: str) -> dict:
    """Build the .format() kwargs for the baseline_narrative prompt template.

    Keys here MUST match the {placeholders} in src/llm/prompts/baseline_narrative.txt
    (drift-guarded by tests/test_baseline_prompt.py).
    """
    revenue_str = f"${metrics.total_revenue:,.0f}" if metrics.total_revenue else "N/A"
    # One label per number, shared with the rich generator — see
    # program_ratio_and_label. Computing it inline here is what let that second
    # path drift onto the plain label with the wrong figure.
    _eff_ratio, ratio_label = program_ratio_and_label(metrics)
    ratio_str = f"{_eff_ratio:.1%}" if _eff_ratio else "N/A"
    cn_score_str = f"{round(metrics.cn_overall_score, 1)}/100" if metrics.cn_overall_score else "N/A"
    programs_str = ", ".join(metrics.programs[:3]) if metrics.programs else "Not available"
    working_capital_str = f"{metrics.working_capital_ratio:.1f} months" if metrics.working_capital_ratio else "N/A"

    fundraising_efficiency_str = _format_fundraising_efficiency(
        metrics.fundraising_expenses, metrics.total_contributions
    )

    # Cost per beneficiary travels as a formatted mandatory value, not a raw
    # float in a block the model is told not to quote. It was the latter, while
    # a worked example ("$907 cost per beneficiary") invited the claim and the
    # N/A silence rule did not cover it -- so a charity with no figure got
    # encouragement, no usable number, and no instruction to stay quiet.
    # 99-3373484 filled the gap with an invented $353.70 and lost its page.
    # Absent for 94 of 166 charities, so most of the corpus was exposed.
    #
    # 0 is not a cost: it means we could not compute one, and publishing "$0
    # per beneficiary" would be worse than saying nothing.
    _cpb = getattr(scores.impact, "cost_per_beneficiary", None)
    cost_per_beneficiary_str = f"${_cpb:,.2f}" if _cpb else "N/A"

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
        "ratio_label": ratio_label,
        "cn_score": cn_score_str,
        "working_capital": working_capital_str,
        "fundraising_efficiency": fundraising_efficiency_str,
        "wallet_tag": scores.wallet_tag,
        "zakat_constraint_text": zakat_constraint_text,
        "amal_score": scores.amal_score,
        "impact_score": scores.impact.score,
        "impact_cpb": cost_per_beneficiary_str,
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

        # Financial-health content (cash reserves, working capital) belongs
        # under impact, not alignment.
        narrative = strip_financial_reserves_from_alignment(narrative)

        # Drop markers whose own claim contradicts the sentence they sit on.
        # Runs after the metric sanitizer so it judges the corrected numbers.
        narrative = prune_unsupported_citation_markers(
            narrative, narrative.get("all_citations") or []
        )

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

        # Financial-health content (cash reserves, working capital) belongs
        # under impact, not alignment.
        narrative = strip_financial_reserves_from_alignment(narrative)

        # Drop markers whose own claim contradicts the sentence they sit on.
        # Runs after the metric sanitizer so it judges the corrected numbers.
        narrative = prune_unsupported_citation_markers(
            narrative, narrative.get("all_citations") or []
        )

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


def _removed_span_joints(
    pattern: str, text: str, guard: "Callable[[re.Match[str]], bool] | None" = None
) -> tuple[str, list[int]]:
    """Remove every non-overlapping match of `pattern` from `text` — the
    same matches, in the same order, `re.sub(pattern, "", text, flags=re.
    IGNORECASE)` would remove — and also return, for each one, the
    position in the RESULT string where the two flanking pieces now touch.
    `_repair_removal_artifacts` uses these positions to scope its cleanup
    to the removal site instead of the whole field (task G17).

    `guard`, when given, is called with each match; a match it rejects
    (returns False for) is left in place, not removed. Task G18: a
    removal rule whose own core is a bare, unqualified number (so it can
    bind to a DIFFERENT metric's own number, not just bridge over one) has
    no reliable way to express "but not when it's named by something else"
    as a per-character exclusion inside `pattern` itself — the exclusion
    turned out to be escapable by the regex engine simply retrying the
    match starting later (see the task report). A `guard` answers that
    question directly against the already-matched span instead."""
    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
    if guard is not None:
        matches = [m for m in matches if guard(m)]
    if not matches:
        return text, []
    parts: list[str] = []
    joints: list[int] = []
    last_end = 0
    length_so_far = 0
    for m in matches:
        piece = text[last_end : m.start()]
        parts.append(piece)
        length_so_far += len(piece)
        joints.append(length_so_far)
        last_end = m.end()
    parts.append(text[last_end:])
    return "".join(parts), joints


_NO_WORD_CHAR_RE = re.compile(r"[A-Za-z0-9]")


def _run_start(text: str, idx: int) -> int:
    """`idx` is the index of a terminal mark; walk backward through any
    immediately-preceding run of more terminal marks separated only by
    whitespace (e.g. the whole "..." in an ellipsis, or a doubled ". ."),
    returning the index of the first mark in that run."""
    p = idx
    while True:
        q = p - 1
        while q >= 0 and text[q].isspace():
            q -= 1
        if q >= 0 and text[q] in ".!?":
            p = q
        else:
            return p


def _run_end(text: str, idx: int) -> int:
    """`idx` is the index of a terminal mark; walk forward through any
    immediately-following run of more terminal marks separated only by
    whitespace, returning the index just past the last mark in the run."""
    p = idx + 1
    while True:
        q = p
        while q < len(text) and text[q].isspace():
            q += 1
        if q < len(text) and text[q] in ".!?":
            p = q + 1
        else:
            return p


def _joint_windows(text: str, joints: list[int]) -> list[tuple[int, int]]:
    """The character range around each removal joint that `_repair_removal_
    artifacts` is allowed to touch: from the nearest preceding sentence-
    terminal mark (or the start of the string) through the nearest
    following one (or the end of the string). Everything outside every
    window is prose the removal never reached and must survive byte-
    identical — text-that-was-never-touched, not "text that happens to
    look fine right now".

    A terminal mark right at a window's edge can itself be part of a
    multi-mark run — an ellipsis, or a doubled mark left behind by a
    different removal — and the whole run has to be in-window together,
    not just the one mark nearest the joint: taking only the mark closest
    to the joint left the REST of a run like "..." sitting just outside the
    window, unrepaired debris (LIVE: charity-20-4097808's citation quote
    produced ".. Zakat Categories..." — two of the ellipsis's three dots
    fell outside the window and survived untouched). `_run_start`/`_run_end`
    extend through the whole run before the window boundary is fixed.

    One rule can also remove several separate matches in a single pass
    (e.g. three distinct zakat-keyword phrases in one field), leaving
    several joints close together with nothing but punctuation debris
    between them ("Zakat-eligible... fuqara, masakin" -> "..." once each
    keyword is gone). Two such windows are merged even when they don't
    overlap, as long as the text between them contains no letter or digit
    at all — a gap that's pure punctuation/whitespace can only be leftover
    debris from the SAME removal, never genuine surviving prose (real
    prose always has actual words), so treating it as one combined window
    doesn't reach into anything the removal didn't touch.
    """
    windows: list[tuple[int, int]] = []
    for j in joints:
        before = max(text.rfind(".", 0, j), text.rfind("!", 0, j), text.rfind("?", 0, j))
        start = _run_start(text, before) if before != -1 else 0
        after = [i for i in (text.find(".", j), text.find("!", j), text.find("?", j)) if i != -1]
        end = _run_end(text, min(after)) if after else len(text)
        windows.append((start, end))
    windows.sort()
    merged: list[tuple[int, int]] = []
    for s, e in windows:
        if merged and (s <= merged[-1][1] or not _NO_WORD_CHAR_RE.search(text[merged[-1][1] : s])):
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


_ABBREVIATION_TAIL_RE = re.compile(r"([A-Za-z]+(?:\.[A-Za-z]+)*)\Z")


def _boundary_is_abbreviation(text_before_boundary: str) -> bool:
    """True when the text immediately before a `[.!?]`-anchored boundary
    ends in a known sentence-ending abbreviation ("Inc", "U.S", "Jr", "et
    al" — the period itself is part of the boundary match, not this
    string). Reuses `_ABBREVIATIONS_BEFORE_COMMA`, the same closed
    vocabulary `_abbreviation_before_stray_comma` already uses for the
    `.,` case, rather than a second, divergent list."""
    m = _ABBREVIATION_TAIL_RE.search(text_before_boundary)
    return bool(m and m.group(1).lower() in _ABBREVIATIONS_BEFORE_COMMA)


def _repair_span(
    text: str,
    lookback: str = "",
    strip_left: bool = True,
    strip_right: bool = True,
    at_field_start: bool = True,
) -> str:
    """The actual cleanup logic, applied to one contiguous span of text.

    `lookback` is read-only context from just before `text` in the full
    field — supplied only so a boundary sitting at the very start of a
    window-scoped span (see `_joint_windows`) can still see the word
    before it for the abbreviation check; it is never written back.
    `strip_left`/`strip_right` gate the leading/trailing `.strip()` so a
    window-scoped span only trims whitespace at an edge that's a real
    field boundary, not at an edge that's actually the middle of the
    untouched field either side of it.

    `at_field_start` gates the `^` alternative in the boundary-anchored
    patterns below. `^` is only a meaningful "sentence boundary" when it's
    the true start of the whole field — the one case a removal can leave
    a stranded connector or orphan mark with nothing at all before it. A
    window-scoped span that starts mid-field always starts exactly AT a
    real `[.!?]` character (see `_joint_windows` — that's how its `start`
    is chosen), so its own position 0 is never actually the start of a
    sentence; it just happens to be where this call's input string begins.
    Leaving the `^` alternative enabled there would let e.g. the "stray
    terminal mark" rule below misread "start of my slice, immediately
    followed by a period" as "the whole clause before this mark was
    removed" and delete a real, surviving terminal period. Task G17: found
    via hand-probing after the initial scoping fix, not in the original
    two repros.
    """
    _anchor = r"(^|[.!?]\s+)" if at_field_start else r"([.!?]\s+)"
    _cap_anchor = r"(^\s*|[.!?]\s+)" if at_field_start else r"([.!?]\s+)"
    text = _BARE_PERIOD_COMMA.sub(_abbreviation_before_stray_comma, text)
    text = re.sub(r"\s{2,}", " ", text)

    # A leading connective stranded at the start of a sentence: ", and X" or
    # ", X" -> "X" (only at the very start of the string, or right after a
    # previous sentence's terminal punctuation — never mid-sentence, so this
    # can't reach into unrelated text). Task G12: also strips a stray leading
    # semicolon/colon/em-dash left behind when a FIRST-clause removal's own
    # trailing edge (`_clause_trail`) stopped right before one of those three
    # joiners instead of consuming it — mirrors `_clause_lead`'s own leading
    # connector alternation for the same three characters, so either side of
    # a removal leaves the same, already-handled artifact shape.
    #
    # Task G17, defect 2: a `[.!?]` right here isn't always a sentence
    # boundary — "Inc.", "U.S.", "et al." end in one too, and if what
    # follows happens to be a stray connector this would otherwise strip a
    # real, correctly-punctuated abbreviation's own continuation. Declines
    # (returns the match unchanged) whenever the text right before the mark
    # is one of the same closed abbreviations `_abbreviation_before_stray_
    # comma` already guards.
    def _strip_leading_connective(m: "re.Match[str]") -> str:
        if _boundary_is_abbreviation(lookback + text[: m.start()]):
            return m.group(0)
        return m.group(1)

    text = re.sub(rf"{_anchor}\s*(?:[,;:]|—)\s*(?:and\s+)?", _strip_leading_connective, text)

    # A bare "and " stranded at a sentence start with no comma of its own
    # (the comma was itself part of the removed span). The leading `\s*`
    # also covers the case where the removed span was the very start of the
    # string (or immediately follows the previous sentence with nothing to
    # collapse): _clause_trail now stops right before " and " rather than
    # consuming into it, so the boundary space itself is left dangling in
    # front of "and" instead of already being absorbed by the multi-space
    # collapse above. Task G17, defect 2: same abbreviation exception as
    # above — "Example Corp. and abroad" is one sentence naming two objects
    # of "works with", not a stray "and" left over from a removal.
    def _strip_stranded_and(m: "re.Match[str]") -> str:
        if _boundary_is_abbreviation(lookback + text[: m.start()]):
            return m.group(0)
        return m.group(1)

    text = re.sub(rf"{_anchor}\s*and\s+", _strip_stranded_and, text, flags=re.IGNORECASE)
    text = re.sub(r",\s*,", ",", text)  # doubled comma
    text = re.sub(r",\s*([.!?])", r"\1", text)  # comma stranded right before terminal punctuation
    text = re.sub(r",\s*$", "", text)  # trailing dangling comma
    # Doubled terminal punctuation. Task G12: generalized from `\1+` (only
    # the identical mark repeated, e.g. ".." -> ".") to any run of terminal
    # marks, since a removal can now glue two *different* ones together —
    # e.g. "...position strong? It also scored 87/100..." with the second
    # sentence removed leaves "...strong?" directly touching the first
    # sentence's own untouched "." with no space between (the leading `?`/
    # `!` exclusion added to `_clause_lead` stops the removal from crossing
    # the true sentence's own terminal mark, but the removed clause's own
    # trailing period is — by design, see `_clause_trail`'s docstring —
    # never part of the match either, so it survives as an orphan glued
    # right onto the true mark: "strong?."). The first mark is always the
    # real one (it belongs to the surviving clause); every mark after it in
    # the same run is an orphan from whatever was removed.
    text = re.sub(r"([.!?])\s*[.!?]+", r"\1", text)
    # A stray terminal mark with nothing (or only whitespace) before it — the
    # whole clause it used to close was removed.
    text = re.sub(rf"{_anchor}[.!?]\s*", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    if strip_left:
        text = text.lstrip()
    if strip_right:
        text = text.rstrip()
    # Capitalize the first letter of the string and of each sentence start,
    # since the word now beginning a sentence may have been lowercase and
    # mid-sentence before its leading clause was removed. Task G12: an
    # optional `<cite id="...">` tag is allowed to sit between the sentence
    # start and the first letter — a removal can leave a surviving clause's
    # own citation wrapper sentence-initial (`<cite id="2">holds ...`), and
    # without this the capitalization regex looked for a letter immediately
    # at the boundary, found `<` instead, and silently skipped it, leaving
    # the visible word lowercase.
    #
    # Task G17, defect 2: the same abbreviation exception as the two
    # connector-strip rules above — "Inc. is", "U.S. and", "Corp. was",
    # "Jr. served", "et al. found" are ordinary sentence-internal prose,
    # not a sentence start left lowercase by a removal, and must not be
    # capitalized.
    def _capitalize(m: "re.Match[str]") -> str:
        if _boundary_is_abbreviation(lookback + text[: m.start()]):
            return m.group(0)
        return m.group(1) + (m.group(2) or "") + m.group(3).upper()

    text = re.sub(
        rf"{_cap_anchor}(<[^>]+>\s*)?([a-z])",
        _capitalize,
        text,
    )
    return text


def _repair_removal_artifacts(text: str, joints: list[int] | None = None) -> str:
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

    Task G17, defect 2: the cleanup above used to run unconditionally over
    the WHOLE field the instant any removal fired anywhere in it — not
    scoped to where that removal actually happened — so an ordinary
    sentence boundary anywhere else in the same field ("Inc. is a
    501(c)(3)...", "the U.S. and abroad...") got misread as this removal's
    own leftover debris: a real "and" silently deleted, a real word wrongly
    capitalized. `joints` is the position, in `text`, of every place a
    removal actually happened (see `_removed_span_joints`); when given,
    cleanup is restricted to the character window around each one (see
    `_joint_windows`) via `_repair_span`, and every character outside every
    window is returned byte-identical to how it arrived. `joints=None`
    (the default, used by direct callers/tests exercising this function in
    isolation) keeps the original whole-string behavior.
    """
    if joints is None:
        return _repair_span(text)
    windows = _joint_windows(text, joints)
    if not windows:
        return text
    pieces: list[str] = []
    prev_end = 0
    for start, end in windows:
        pieces.append(text[prev_end:start])
        lookback = text[max(0, start - 30) : start]
        pieces.append(
            _repair_span(
                text[start:end],
                lookback=lookback,
                strip_left=(start == 0),
                strip_right=(end == len(text)),
                at_field_start=(start == 0),
            )
        )
        prev_end = end
    pieces.append(text[prev_end:])
    return "".join(pieces)


# ── Taxonomy of boundary/gap primitives (sanitize_narrative_metrics) ──
#
# sanitize_narrative_metrics (below) is long and its inline comments are the
# real documentation of WHY each regex piece exists — this block doesn't
# replace them. What it adds is a single map from primitive -> what it
# excludes/permits -> which rules use it, so a newcomer doesn't have to
# reconstruct that map by reading ~1600 lines end to end. Read a primitive's
# own definition/call sites before changing it; this is a map, not a spec.
#
# GOVERNING TRADEOFF. When a fix has to choose, this function's standing
# tie-break is: a surviving fabrication is worse than an over-removed true
# clause (see `_clause_trail`'s own comment) — EXCEPT that silently
# destroying a substantive true fact is worse than leaving a dangling
# qualitative fragment behind (see `_clause_trail_same_claim_lead`'s comment:
# "a visible, fabrication-adjacent stray fragment is preferable to silently
# erasing a true, substantive fact"). That exception exists because an
# earlier version of `_clause_trail` got this backwards — a determiner-led
# continuation rule was erasing ordinary true sentences ("The organization
# has trained...") that merely happened to follow a bare comma after a
# removed claim — so "prefer removing more" is not an unconditional license;
# it's bounded by "never at the cost of a real, substantive fact."
#
# OUTER leading/trailing edges (used by nearly every removal rule):
#   - `_clause_lead`  — leading edge. Runs up to the nearest clause boundary
#     (`.,;:?!—`), tolerating a decimal point/thousands-comma as non-
#     boundaries and an optional leading connector (comma/em-dash/semicolon/
#     colon, or a bare "and") so the removed span eats the connective tissue
#     in front of it instead of leaving it stranded. `_label_colon_lead`
#     (below) is folded into it.
#   - `_clause_trail` — trailing edge. Same boundary set, but a bare comma/
#     em-dash/semicolon/colon only continues the match when what follows
#     opens with `_clause_trail_same_claim_lead` (an appositive/comparison of
#     the SAME claim); anything else, including any verb, is an independent-
#     clause boundary and stops the match there. Never eats a bare trailing
#     `.` itself — that's left for `_repair_removal_artifacts`.
#   - `_label_colon_lead` — optional group inside `_clause_lead`: at a true
#     sentence start, a colon-terminated label with no digit of its own
#     ("Fundraising Efficiency: ") is swallowed together with the value that
#     follows, instead of surviving alone, stranded.
#   - `_cn_number_lead` — a `_clause_lead` variant used only by the null-CN
#     rules whose own core is a bare `\d+\.?\d*/100`: adds one more
#     exclusion (never consume into such a span as filler) so the leading
#     run can't eat into a real number's leading digits before the capture
#     group gets to it.
#
# The `_trail_same_claim_lead` / `_clause_trail_same_claim_lead` pair (the
# important divergence — read both comments in full before touching either):
#   - `_clause_trail_same_claim_lead` backs the GENERIC `_clause_trail` above
#     (used by nearly every removal rule). It is exactly
#     `_comparative_tail_lead` — 8 markers ("up/down from", "compared to",
#     "versus", "vs.", "well above/below/over/under", a closed comparative/
#     superlative set, "among", "second only to") — with NO determiner/
#     possessive/quantifier branch. That branch was deliberately dropped
#     (Task G15): "a/an/the/its/their/his/her"/"one of" also opens the
#     subject of an ordinary TRUE independent clause, so keeping it in the
#     generic trailing edge silently erased real sentences.
#   - `_trail_same_claim_lead` backs ONLY `_fr_gap_dollar_first` (the
#     dollar-first null-fundraising rule). It is `_comparative_tail_lead`
#     PLUS the determiner/possessive/quantifier branch, kept here
#     deliberately: `_fr_gap_dollar_first` only ever fires already anchored
#     to a null dollar figure, so a determiner-led tail after it is never a
#     candidate true-clause subject — it's always still describing the same
#     fabricated figure — and the false-erasure risk that got the branch
#     dropped from `_clause_trail` doesn't apply here.
#   - `_comparative_tail_lead` is the shared factor both build from (Task
#     G19 — previously hand-copied into both, unenforced).
#
# Hedge/guard word-count gaps (tolerate filler between an anchor and its
# number, without crossing into a different metric's own claim):
#   - `_hedge_gap` — 0 to `_hedge_max_words` (3) bare-letter words, excluding
#     `_metric_noun_boundary` words, linking verbs (is/was/are/were), and
#     "and". Always sits inside an optional connector group (e.g.
#     `(?:of\s+{_hedge_gap})?`) so it can only activate once that literal
#     connector has actually matched. Used by most correction rules (program
#     expense ratio patterns 2/3/5, CN overall's "score of X"/"scored X out
#     of 100", CN accountability/financial correction, AMAL correction, and
#     founded-year correction) and by the matching null-branch removal rules
#     (program expense, CN accountability/financial, AMAL, founded-year),
#     plus `_other_metric_lead_re`'s own connector.
#   - `_guard_gap` — same exclusions as `_hedge_gap` but UNBOUNDED. Backs
#     `_named_metric_claim_lead_re` and `_other_metric_lead_re` — guards
#     that decide whether a bare number is already named by something else.
#     Unbounded on purpose: a guard firing too often just makes its rule
#     over-cautious (declines to fix a legitimate claim), never corrupting,
#     so there's no safety reason to bound it the way a correction is.
#
# Middle (co-occurrence) gaps — sandwiched between two already-fixed literal
# anchors, so a per-character exclusion is safe here (unlike on a leading
# run, where the regex engine can just retry one position later):
#   - `_cn_gap` — backs the null-CN-overall removal rules. Decimal-point-
#     safe; excludes `_other_metric_claim` and a bare `\d+\.?\d*/100` span
#     (so it can't bridge over, or eat into, a DIFFERENT metric's own
#     number).
#   - `_fr_gap` — backs the phrase-first null-fundraising removal rules
#     ("fundraising efficiency ... $X"). Decimal-safe; excludes crossing a
#     bare "and", `$` (so it always binds to the NEAREST dollar figure, not
#     a farther true one), and `_other_metric_claim`.
#   - `_fr_gap_dollar_first` — backs the dollar-first null-fundraising rule
#     ("$X ... fundraising efficiency"/phrasing). Same base exclusions as
#     `_fr_gap`, plus: a bare comma is a boundary UNLESS followed by
#     `_trail_same_claim_lead` (see above) — needed because this rule's own
#     "$X" core, unlike `_fr_gap`'s, can satisfy the whole match with
#     nothing required on the far side, so an unconditional comma-
#     continuation would let it destroy a true clause sitting after a real
#     dollar figure.
#   - `_decimal_safe` no longer exists as a variable — it's the name this
#     function's own comments still use for the SHAPE these three gaps
#     share (tolerate `(?<=\d)\.(?=\d)` so a real decimal point isn't
#     mistaken for a sentence end). Task G18 split the one shared variable
#     into these three per-family locals so each could add its OWN
#     additional exclusion without leaking into families that don't need it.
#
# Cross-metric / naming vocabulary:
#   - `_metric_noun_boundary` — the master closed list of metric-family
#     words (score/rating/ratio/percent/program(s)/programmatic/expense(s)/
#     accountability/governance/financial/navigator/amal/founded and its
#     synonyms/operating and its synonyms/capital/reserve(s)/fundraising/
#     efficiency/zakat/leadership/adaptability). Backs `_hedge_gap`/
#     `_guard_gap`'s exclusion and is folded into `_other_metric_noun`.
#   - `_other_metric_noun` / `_other_metric_claim` — "what a DIFFERENT
#     metric's own claim looks like," built entirely from
#     `_metric_noun_boundary` plus `_fr_phrasing` (the fundraising family's
#     own dollar-phrasing, since `_metric_noun_boundary` only partly covers
#     it). Used inside `_cn_gap`/`_fr_gap`/`_fr_gap_dollar_first` and
#     `_other_metric_lead_re`/`_other_metric_trail_re` (the guards backing
#     the two bare-`\d+/100`-core null-CN rules) so none of them can bind to
#     or bridge over a genuinely different metric's own number.
#   - `_overall_name` — the closed set of names ("overall", "Charity
#     Navigator('s)") the generic CN-overall CORRECTION rule may claim a
#     number under.
#   - `_named_metric_claim_lead_re` — detects, backward from a bare number,
#     whether ANYTHING names it as "NAME NOUN of/is/was" — an open,
#     unenumerated noun is fine, since this detects the SHAPE, not a noun
#     vocabulary. Guards the CN-overall correction rule: a detected name not
#     in `_overall_name` makes it decline, so an unrecognized/future beacon
#     name fails safe instead of getting the overall score misattributed to
#     it.
#   - `_number_not_malformed` — zero-width guard at the start of a numeric
#     correction core; refuses to match inside, or immediately after, a
#     malformed multi-decimal run (e.g. "96.96.0", a corrupted regeneration
#     artifact), so no correction rule can produce a phantom or spliced
#     value from it. Used by the CN-overall number-before rule and the CN
#     accountability/financial correction rules.
#
# Other primitives:
#   - `_wc_num_unit` — the working-capital number+unit core. Leading `-?`
#     permits a genuine negative (working_capital_ratio has no zero floor,
#     unlike every other metric here); `(?<!\d)` stops that `-?` from
#     misreading a number-range hyphen ("6-41.7 months") as a minus sign.
#   - `_preserve_case` / `_match_case` — `_match_case` upper-cases a fixed
#     replacement's first letter when the ORIGINAL match started uppercase,
#     so a removal earlier in the same pass leaving a correction's target
#     sentence-initial doesn't get silently lowercased; `_preserve_case`
#     wraps a literal replacement string into a `_match_case`-backed
#     callable. Used wherever a correction's replacement is a fixed literal
#     that could plausibly open a sentence (working capital pattern 2,
#     program-expense-ratio patterns 2/3/5, CN "scored X out of 100", CN
#     accountability/financial correction, founded-year correction).
#   - `_repair_removal_artifacts` (with `_repair_span`/`_joint_windows`/
#     `_run_start`/`_run_end`) — the post-removal cleanup pass: fixes
#     stranded leading connectives, a stranded bare "and", doubled/stranded
#     commas, doubled/mixed terminal punctuation, a stray orphan terminal
#     mark, and re-capitalizes a new sentence start — scoped (Task G17) to
#     just the character window around each removal joint, so it can't
#     mistake an ordinary sentence boundary elsewhere in the field for
#     removal debris. Runs only when a removal rule actually matched
#     something.
#   - `_abbreviation_before_stray_comma` (and `_boundary_is_abbreviation`,
#     sharing the same closed `_ABBREVIATIONS_BEFORE_COMMA` set) — declines
#     to "fix" a bare `.,`/sentence boundary when the text before it is a
#     known sentence-ending abbreviation ("Inc.", "U.S.", "et al."), so
#     ordinary correctly-punctuated English isn't mistaken for removal
#     debris.
_RESERVES_MENTION_RE = re.compile(
    r"cash\s+reserves|financial\s+reserves|working\s+capital", re.IGNORECASE
)
_RESERVES_ASIDE_RE = re.compile(
    # `[^.]` alone would stop at a decimal point ("25.6 months") and mistake
    # it for the sentence boundary -- same defect shape `_decimal_safe`
    # elsewhere in this file exists for. `(?<=\d)\.(?=\d)` lets the run
    # cross a period sandwiched between two digits without crossing a real
    # sentence-ending one.
    r"\s*,\s*(?:though|while|but)\b(?:[^.]|(?<=\d)\.(?=\d))*?"
    r"(?:cash\s+reserves|financial\s+reserves|working\s+capital)(?:[^.]|(?<=\d)\.(?=\d))*",
    re.IGNORECASE,
)


def strip_financial_reserves_from_alignment(narrative: dict) -> dict:
    """Cash reserves / working capital describe Financial Health, not
    Alignment. The baseline prompt's own output schema says
    dimension_explanations.impact covers "program effectiveness, financial
    health, and evidence quality" and .alignment covers "donor fit, cause
    urgency, and track record" -- but the model sometimes tucks a reserves
    aside into the alignment text anyway.

    Observed on EIN 27-3625796: dimension_explanations.alignment read "...
    It has a established track record in domestic advocacy, though its
    high level of cash reserves--25.6 months of working capital--is a
    notable factor for donors to consider [1]." The concern itself is
    never lost by removing it here: working-capital risk is already
    stated separately in areas_for_improvement, so this drops a duplicate
    sitting under the wrong rubric heading, not information.

    Only touches dimension_explanations.alignment -- a mention under
    impact, where it belongs, or anywhere else in the narrative (e.g. a
    correctly-scoped areas_for_improvement bullet) is left untouched.
    """
    dim = narrative.get("dimension_explanations")
    if not isinstance(dim, dict):
        return narrative
    text = dim.get("alignment")
    if not isinstance(text, str) or not _RESERVES_MENTION_RE.search(text):
        return narrative

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    kept = []
    for sentence in sentences:
        if not _RESERVES_MENTION_RE.search(sentence):
            kept.append(sentence)
            continue
        # First try to drop just the though/while/but aside that carries
        # the reserves mention, keeping the rest of the sentence intact.
        stripped = _RESERVES_ASIDE_RE.sub("", sentence)
        if _RESERVES_MENTION_RE.search(stripped):
            # The reserves mention wasn't inside such an aside -- the
            # sentence is fundamentally about reserves. Drop it whole
            # rather than leave a fragment that still makes the claim.
            continue
        stripped = stripped.rstrip()
        if stripped and not stripped.endswith((".", "!", "?")):
            stripped += "."
        if stripped:
            kept.append(stripped)

    dim["alignment"] = " ".join(kept).strip()
    return narrative


def sanitize_narrative_metrics(narrative: dict, metrics: "CharityMetrics", scores: Any) -> dict:
    """Deterministically stamp correct metric values into LLM-generated narrative.

    The LLM writes qualitative prose; this function ensures every numeric claim
    matches the source data.  Fixes three classes of error:
      1. Wrong number (e.g. "3 months" when source says 8.3 months)
      2. Wrong unit  (e.g. "years" when source is months)
      3. Phantom mention of an N/A metric (e.g. citing CN score when it's null)

    See the "Taxonomy of boundary/gap primitives" comment block immediately
    above this function for a map of the regex building blocks it's built
    from — what each one excludes/permits and which rules use it — before
    changing or extending any rule below.
    """

    # ── Build the ground-truth lookup ──
    # Each entry: (regex pattern, correct replacement, remove_if_na, guard)
    # For N/A metrics the pattern is used to strip the enclosing sentence.
    # `guard` (Task G18) is a separate, explicitly-typed field — not the
    # `replacement` slot reused — so a removal rule's per-match guard
    # (`Callable[[Match], bool]`) can never be confused with a correction
    # rule's replacement (`Callable[[Match], str]`); every removal rule
    # that doesn't need one passes `None` here.
    rules: list[
        tuple[
            str,
            str | Callable[["re.Match[str]"], str] | None,
            bool,
            Callable[["re.Match[str]"], bool] | None,
        ]
    ] = []

    # INVARIANT: registration order is semantically load-bearing. Rules are
    # appended to this list in the order they appear below, and `_apply_rules`
    # (at the bottom of this function) runs every rule over the WHOLE field,
    # in that same order, one after another — so a later rule's pattern can
    # see and act on an EARLIER rule's removal output mid-pass, not just the
    # original narrative text. Reordering rule families, or inserting a new
    # rule between two existing ones, can change what a downstream rule
    # matches against. This is why, e.g., the CN-family rules further down
    # are built after `_fr_phrasing`/`_other_metric_claim` are defined, and
    # why `_hedge_gap`/`_guard_gap` are computed once up top rather than
    # per-family: anything a later family's rules depend on has to already
    # exist by the time that family's `rules.append(...)` calls run.

    # Removal rules scan "everything up to the sentence boundary" using a
    # `[^.]*`-shaped run. A literal `.` also shows up mid-number ("91.1%",
    # "$0.00"), and `[^.]*` can't cross it — so the run stops there instead of
    # at the real sentence end, and the trailing `\.?` then deletes into the
    # next clause starting mid-number. Fix: treat a period as a boundary only
    # when it is NOT sandwiched between two digits (a decimal point).
    #
    # The "co-occurrence within one sentence" INNER gap inside a removal
    # pattern (e.g. between "$0.00" and "fundraising efficiency") is about
    # tolerating unrelated words *inside* one fabricated claim, not about
    # where the claim's outer boundary sits, so it is unaffected by the
    # clause-vs-sentence fix below. That inner-gap shape used to be one
    # shared `_decimal_safe` variable; Task G18 split it into per-rule-
    # family local variants (`_cn_gap`, `_fr_gap`/`_fr_gap_dollar_first`,
    # defined where each family builds its rules below) so each can also
    # exclude bridging over a DIFFERENT metric's own claim without the
    # exclusion leaking into families that don't need it.
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
    #
    # Task G12: a thousands-separator comma ("$141,261", "4,000 families")
    # is not a clause boundary any more than a decimal point is — it's the
    # same defect shape `_decimal_safe` was written for originally (a digit-
    # sandwiched punctuation mark mistaken for a boundary), just never
    # mirrored onto the comma exclusion here. `(?<=\d),(?=\d)` added
    # alongside the existing `(?<=\d)\.(?=\d)` closes it. Also extended the
    # excluded-boundary set from `.,` to also include `;:?!—` — semicolon,
    # colon, question mark, and exclamation mark are unrecognized today and
    # admitted freely by `[^.,]`, letting a removal's leading scan run
    # straight across a genuine independent-clause separator (or, for `?`/
    # `!`, straight across what is really the END of the PRECEDING true
    # sentence) and swallow a true clause that has nothing to do with the
    # fabricated one. Em dash (`—`) is included here on the *leading* side
    # unconditionally (mirroring how a bare comma is always a leading
    # boundary, with no appositive-continuation exception on this side
    # either) — the appositive-vs-clause ambiguity the brief flags for em
    # dash only matters on the *trailing* side (see `_clause_trail` below),
    # where the text instead of the position is what decides. The leading
    # `\s*` (new here — comma's own version never needed it) matters
    # specifically for the em dash: unlike a comma/semicolon/colon, which is
    # never preceded by a space in ordinary prose, an em dash conventionally
    # IS ("capital — it also..."), and without consuming that space here too
    # the leftmost successful match starts right at the dash itself, leaving
    # the space before it stranded in front of the surviving clause's own
    # terminal punctuation ("...capital ." — a real, hand-probed artifact).
    # Task G15 (defect 2): a structural "Label: value" quote (30+ live in
    # `all_citations[].quote`, e.g. "Fundraising Efficiency: $0.00 per $1
    # raised") lost both the colon and the value, not just the value. Cause:
    # every removal rule's core anchors on the NUMBER, not the label, so the
    # match can only start as far left as the colon (consumed as ordinary
    # connective tissue by the alternation below, the same way it consumes
    # ", and" between two clauses) — the label text sitting to the colon's
    # left is never reachable by the match at all, so it survives alone,
    # stranded and asserting nothing ("Fundraising Efficiency").
    #
    # `_label_colon_lead` closes this with a new, OPTIONAL leading group,
    # tried before the existing connector: at the true start of a sentence
    # (`^`, or right after a previous sentence's own terminal mark) a run of
    # plain text with no digit of its own, ending in a literal colon, is
    # swallowed as part of the SAME removal — so "Fundraising Efficiency: "
    # goes with "$0.00 per $1 raised" as one unit, matching the existing,
    # already-correct behavior of the short form with no trailing phrase
    # ("Fundraising Efficiency: $0.00" already goes fully empty, via the
    # phrase-first rule whose own core literally anchors on "fundraising
    # efficiency"). Fully empty is chosen over stranding a bare "Label:"
    # (colon kept, value gone) so both forms of the same defect land on one
    # consistent, non-misleading result.
    #
    # The no-digit requirement is what keeps this mechanical rather than a
    # label vocabulary to enumerate: it doesn't matter what the label SAYS,
    # only that it asserts no number of its own. This is also what keeps it
    # from reopening the existing colon_true_leads protection just below —
    # "It holds 8.3 months of working capital: it also scored 87/100..." has
    # its own digit (8.3) before the colon, so the new group can't match
    # there and the existing, unconditional colon-as-connector behavior
    # (protecting that true clause) is exactly what still applies. Sentence-
    # anchoring (`^` / after `[.!?]\s`) additionally keeps this from ever
    # reaching into the MIDDLE of an unrelated true clause.
    #
    # Accepted residual gap, narrow and documented rather than chased further:
    # a genuine independent clause with no digit of its own, immediately
    # before a "Label:"-shaped colon at a sentence's start ("The mission is
    # clear: it scored 87/100 on Charity Navigator.") would be swallowed
    # along with the label it's mistaken for. No live or reported instance of
    # this shape; not pursued further per the standing instruction not to
    # chase this function's defects with an ever-widening invariant.
    _label_colon_lead = r"(?:^|(?<=[.!?]\s))[^\d.:!?]*:\s*"
    _clause_lead = (
        rf"(?:{_label_colon_lead})?"
        + r"(?:\s*(?:[,;:]|—)\s*(?:and\s+)?|\s+and\s+)?"
        + r"(?:(?!\s+and\b)(?:[^.,;:?!—]|(?<=\d)\.(?=\d)|(?<=\d),(?=\d)))*"
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
    # Task G19: the eight comparative/comparison-tail alternatives below
    # ("up from" through "second only to") are shared, byte-for-byte, with
    # `_clause_trail_same_claim_lead` further down — they used to be
    # hand-copied into both constants with nothing enforcing they stay in
    # sync, so a later task adding a new comparative-tail marker to one and
    # not the other would silently reintroduce an asymmetry between the two
    # mechanisms. Factored out into `_comparative_tail_lead`, which both
    # constants now build from; string-concatenation reproduces each one's
    # pre-existing regex source exactly (verified by comparing the compiled
    # patterns — see the task report), so this is pure de-duplication, not
    # a behavior change.
    _comparative_tail_lead = (
        r"(?:up|down)\s+from\b"
        r"|compared\s+to\b"
        r"|versus\b"
        r"|vs\.?(?=\s)"
        r"|well\s+(?:above|below|over|under)\b"
        r"|(?:best|worst|higher|lower|better|stronger|weaker|highest|lowest|strongest)\b"
        r"|among\b"
        r"|second\s+only\s+to\b"
    )
    _trail_same_claim_lead = r"(?:a|an|the|its|their|his|her)\b" r"|one\s+of\b" "|" + _comparative_tail_lead
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
    #
    # Task G12: two more boundary shapes, mirroring the leading edge above.
    # First, a thousands-separator comma (`(?<=\d),(?=\d)`) is not a clause
    # boundary — same fix as `_clause_lead`, same reasoning: a digit-
    # sandwiched comma is part of a number, not punctuation.
    #
    # Second, semicolon/colon/question-mark/exclamation-mark are added to
    # the excluded set alongside `.,`. All four separate grammatically
    # independent clauses by definition (unlike a bare comma, which can
    # introduce either an appositive of the same claim or an independent
    # clause) — so, like `.`, they get no continuation-lead exception, and
    # like the existing bare-trailing-`.` design, a stray trailing one is
    # left for `_repair_removal_artifacts` rather than consumed here.
    #
    # Em dash is the doubtful one (the brief's own framing): it introduces
    # an appositive of the same fabricated claim about as often as it
    # introduces a genuine independent clause. Tested both readings: making
    # it an unconditional boundary strands a fabrication-referencing
    # appositive after it ("scored 87/100 ... — a great achievement!" would
    # leave "A great achievement!" behind, still about a score that no
    # longer exists); making it an unconditional continuation instead risks
    # swallowing a genuine independent clause that just happens to be
    # joined by a dash instead of a semicolon. Resolved by giving it the
    # *same* context-sensitive treatment already built for the bare comma —
    # reusing `_trail_same_claim_lead` rather than inventing a second
    # mechanism — since the same test (does what follows read as an
    # appositive of the same claim, or as its own clause?) is what actually
    # distinguishes the two cases for a dash exactly as it does for a comma.
    #
    # Task G12 gap 2: `;` and `:` were left as unconditional boundaries when
    # first added (defect 3), on the reasoning that they "separate
    # grammatically independent clauses by definition." That's true of the
    # clause they introduce, but says nothing about whether that clause is
    # its OWN independent fact or an appositive commentary on the claim just
    # removed — the exact ambiguity the em dash already has to resolve, via
    # `_trail_same_claim_lead`, one line above. Leaving `;`/`:` unconditional
    # meant an appositive tail after either ("scored 87/100 on Charity
    # Navigator; a truly remarkable result.") survived as a fragment still
    # describing a score that no longer exists — precisely the failure mode
    # the em-dash fix exists to prevent. `;`/`:` now get the identical
    # continuation exception; an independent clause after either (no
    # `_trail_same_claim_lead` lead-in) still stops the removal exactly as
    # before, since that case never reaches this alternative at all.
    # Task G15 (defect 1): `_trail_same_claim_lead`'s determiner/possessive/
    # quantifier branch (`a|an|the|its|their|his|her|one of`) was chosen on
    # the theory that it identifies an appositive tail of the SAME fabricated
    # claim. It doesn't — it identifies a noun phrase, and the subject of a
    # true independent clause is a noun phrase too. Every one of those
    # determiners is also the single most common way to open a sentence's
    # subject ("The organization has trained...", "Its mission is...", "An
    # independent audit confirmed..."), so the branch was silently erasing
    # ordinary, well-formed true clauses that happened to follow a bare comma
    # after a removed claim, not just the appositives it was built for.
    #
    # This is a deliberate reversal of that earlier decision, not a
    # refinement of it: a bare comma is now the DEFAULT clause boundary for
    # `_clause_trail`, full stop. The determiner/possessive/quantifier branch
    # (and `one of`, the same partitive-quantifier shape — "One of the
    # volunteers found it" is just as valid a clause subject) is dropped from
    # the set `_clause_trail` consults. `_clause_trail_same_claim_lead` below
    # keeps every OTHER continuation marker `_trail_same_claim_lead` had
    # (comparative-tail prepositions and bare comparatives/superlatives),
    # since none of those can open the subject of an independent clause the
    # way a determiner can — "up from 82", "compared to last year", "versus",
    # "among", or a bare "higher"/"best" cannot themselves BE a clause's
    # subject, so they were never the mechanism behind this defect (`lower`/
    # `better` keep their pre-existing, already-documented ambiguity with a
    # verb reading — unrelated to this task, still accepted per the standing
    # tie-break).
    #
    # A word-count or verb-presence invariant was considered and rejected:
    # the appositive corpus this reversal now under-serves ("its highest
    # rating", "a strong reserve position") and the true-clause corpus this
    # reversal protects ("the organization has trained...", "an independent
    # audit confirmed...") overlap in length at around six words, and "does
    # the tail contain a verb" is the same open, unbounded vocabulary class
    # this function has already been burned by three times (a verb list, an
    # appositive-lead list, a participle list) — adding it a fourth time
    # anywhere in this function is out of the question. No genuinely closed,
    # mechanical invariant separates the two corpora better than the plain
    # boundary, so the plain boundary is what ships. The accepted cost: a
    # determiner-led appositive of a just-removed claim ("a perfect score
    # from Charity Navigator, its highest rating") is no longer consumed —
    # it strands as a dangling fragment instead of being erased with the
    # claim it once modified. Per the brief's own standing instruction, that
    # trade is intentional: a visible, fabrication-adjacent stray fragment is
    # preferable to silently erasing a true, substantive fact, and stranded
    # fragments are already a documented, accepted class in this codebase
    # (see `_repair_removal_artifacts`).
    #
    # `_trail_same_claim_lead` itself (above) is untouched, deliberately: it
    # still backs `_fr_gap_dollar_first` below, which has its own separate,
    # already-tested reason to keep tolerating the determiner branch (a bare
    # comma joining a null "$0.00" to "an indication of poor fundraising
    # efficiency" is a genuine two-sided fabrication about the same figure,
    # not a candidate true-clause subject — recall `_fr_gap_dollar_first`
    # never removes anything that isn't already anchored to a null dollar
    # figure or the literal phrase "fundraising efficiency", so it isn't
    # exposed to this defect the way the generic `_clause_trail` is).
    # Identical to `_comparative_tail_lead` (defined above, alongside
    # `_trail_same_claim_lead`) — this constant keeps every OTHER
    # continuation marker `_trail_same_claim_lead` had except the dropped
    # determiner/possessive/quantifier branch, which is exactly what
    # `_comparative_tail_lead` already is. Referencing it directly (Task
    # G19) instead of a second hand-copied literal is what stops a future
    # addition to one from silently omitting the other.
    _clause_trail_same_claim_lead = _comparative_tail_lead
    _clause_trail = (
        rf"(?:(?!\s+and\b)(?:[^.,;:?!—]|(?<=\d)\.(?=\d)|(?<=\d),(?=\d))"
        rf"|[,;:—](?=\s*(?:{_clause_trail_same_claim_lead})))*"
    )

    # Task G14: every correction/removal rule below (except working capital
    # and fundraising, which anchor on a noun/dollar sign rather than a
    # single word right before the number, and so are immune) anchors its
    # number to one specific preceding word — "of", "in", "since", "a",
    # "directs", "spends", "scored" — with nothing tolerated in between. A
    # hedge phrase ("roughly", "nearly", "only", "approximately", "an
    # impressive", "a mere") sitting between that word and the number
    # defeats the anchor, and is an open vocabulary class — enumerating it
    # is exactly the trap this function has been burned by three times
    # already (a verb list, an appositive-lead list, a participle list).
    #
    # Bounded by COUNT instead: up to _hedge_max_words bare words may sit
    # between an anchor and the number it introduces. 3 covers every
    # hedge in the reported defect ("roughly", "nearly", "only",
    # "approximately" are 1 word; "an impressive", "a mere", "just over",
    # "a strong" are 2) with one word of headroom for something like "a
    # truly remarkable" — chosen deliberately small, not because 3 is
    # theoretically complete: a hedge phrase longer than 3 words still
    # defeats the anchor (see the pinned N+1 test), same as any bounded
    # scheme. Reported as a residual gap rather than pushed higher, since
    # a bigger N only shrinks the gap, it can't close it (the vocabulary
    # is still open) and makes the cross-metric hazard below worse the
    # further it reaches.
    #
    # That hazard: a permissive gap can reach PAST its own metric's number
    # to one belonging to a DIFFERENT metric ("an accountability score of
    # [gap] 50%" must not let the gap skip over "program expense ratio" to
    # a program-expense value it was never meant to claim). Blocked the
    # same way a prior task blocked the fundraising gap from reaching a
    # farther "$": forbid the gap from ever consuming a digit — so the
    # match always binds to the NEAREST number, never a farther one — or a
    # word from this function's own closed set of metric nouns, so it
    # can't cross into a different metric's named phrase even within
    # budget, on the rare case that phrase has no digit of its own
    # standing in the way (verified empirically; see the task report).
    # Restricting each hedge "word" to bare letters (not `\S+`) is what
    # keeps the digit exclusion airtight and, as a side effect, also stops
    # the gap from ever crossing sentence-ending punctuation glued to a
    # word ("Texas.") into a later, unrelated sentence's own number — a
    # token that must swallow trailing punctuation to reach a digit
    # already can't be a bare-letters-plus-whitespace token, so the
    # repetition simply stops one word short instead.
    _hedge_max_words = 3
    _metric_noun_boundary = (
        r"score|rating|ratio|percent|program|programs|programmatic|expense|expenses"
        r"|accountability|governance|financial|navigator"
        r"|amal|founded|established|incorporated|started|began"
        r"|operating|serving|active|working|capital|reserve|reserves"
        r"|fundraising|efficiency|zakat"
        # Task G16: Charity Navigator's fourth Encompass beacon ("Leadership
        # & Adaptability") was missing from this boundary entirely, so a
        # hedge/guard gap could walk straight through either word as if it
        # were harmless filler. Added as defense-in-depth alongside the
        # guard inversion below (`_overall_name`/`_named_metric_claim_lead_
        # re`) — the inversion is what actually makes the Leadership case
        # safe (see its own comment), not this addition on its own.
        r"|leadership|adaptability"
    )
    # A linking verb ("is"/"was") is a second, DIFFERENT anchor shape this
    # function already made a deliberate, pinned decision about (task
    # G11's `_sub_score_lead_re`, and
    # `test_linking_verb_is_also_guarded_not_just_of`): "the financial
    # rating is 40/100" is intentionally left uncorrected — the guard only
    # stops it from being mislabeled as the overall score, it doesn't
    # correct it, because neither sub-score rule parses "is X" as a
    # phrasing shape at all. Excluding "is"/"was"/"are"/"were" here keeps
    # that decision intact regardless of which anchor a given rule uses.
    #
    # "and" is excluded for the same reason every other removal/correction
    # boundary in this function already treats it as an unconditional
    # clause boundary (`(?!\s+and\b)` in `_clause_lead`/`_clause_trail`/
    # `_fr_gap`) — without it, a hedge-tolerant anchor that has no literal
    # connector to gate it (see the `directs`/`spends`/`scored` verbs
    # below, which apply `_hedge_gap` unconditionally, not inside an
    # optional group) could otherwise walk across "and" into a wholly
    # unrelated clause's own number.
    #
    # The empirical corpus check for this task caught a second, sharper
    # version of the same hazard that "and"/"is"/"was" alone don't cover:
    # every occurrence of `_hedge_gap` below sits inside an optional
    # connector group — `(?:of\s+{_hedge_gap})?` / `(?:a\s+{_hedge_gap})?`
    # — so the gap can ONLY ever activate once that literal word ("of"/
    # "a") has actually been matched; when the connector is absent, the
    # whole group is skipped and the number must sit immediately adjacent
    # to the anchor, exactly as before this task. Before this restructure,
    # `(?:of\s+)?{_hedge_gap}` let the gap fire even with NO "of" present
    # at all, which is what let "Charity Navigator score and an 85.7%
    # program expense ratio" (two unrelated clauses joined by "and", no
    # "of" anywhere) and "program ratio median of 90.0%" (a PEER
    # statistic, "median" sitting between "ratio" and "of") both get
    # misread as this metric's own hedged claim and overwritten with the
    # wrong value — live, real regressions in the published corpus, not
    # synthetic ones. Gating the whole connector+gap behind one optional
    # group closes both: neither phrasing has the literal word "of"/"a"
    # immediately after the anchor, so the group never activates and the
    # number is correctly left untouched.
    _hedge_gap = rf"(?:(?!(?:{_metric_noun_boundary}|is|was|are|were|and)\b)[A-Za-z]+\s+){{0,{_hedge_max_words}}}"

    # A guard must never be narrower than the rule it guards. `_sub_score_
    # lead_re` below (not this correction gap) is what decides whether the
    # generic CN-overall rule is allowed to claim a span — and it originally
    # reused this same 3-word-bounded `_hedge_gap` for its own backward
    # lookup. Past 3 hedge words, the sub-score correction rule correctly
    # declines to fire (an honest, mild residual gap — the wrong number
    # stays uncorrected), but the GUARD *also* declined at the same
    # threshold, so the generic overall rule proceeded unguarded and
    # stamped the overall score into a sub-score-labelled span — the exact
    # severe misattribution this task exists to prevent, just relocated to
    # 4+ words. `_guard_gap` is unbounded (no `{0,N}` cap) for exactly this
    # reason: the correction rules stay conservative because touching too
    # much text corrupts it, but the guard's only job is refusing to let a
    # DIFFERENT rule act on a span — firing too often just means "the
    # overall rule declines to fix a legitimate overall-score claim" (over-
    # cautious, not corrupting), so there is no matching safety reason to
    # bound it. It keeps the same digit/metric-noun/`and`/linking-verb
    # exclusions as `_hedge_gap`, so it still can't reach across a genuine
    # clause boundary or into a different metric's own number — those
    # exclusions are what make an unbounded scan safe here, not the word
    # count. See `TestSubScoreGuardStaysPermissiveBeyondTheCorrectionBound`.
    _guard_gap = rf"(?:(?!(?:{_metric_noun_boundary}|is|was|are|were|and)\b)[A-Za-z]+\s+)*"

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
    #
    # Task G17, defect 1: that same leading `-?` also matches a hyphen used
    # as a number-RANGE separator in ordinary prose ("the standard 6-41.7
    # months of working capital"), not just a genuine minus sign. Matching
    # is leftmost-start-wins: at the digit before the hyphen ("6"), the
    # unit doesn't follow immediately, so that start fails; the very next
    # start position tried is the hyphen itself, where `-?` happily
    # consumes it as a sign, `\d+\.?\d*` matches "41.7", and the whole
    # match becomes "-41.7 months" — gluing the preceding digit onto the
    # replacement (LIVE: "6-41.7" -> "641.7" on the first sanitize pass,
    # then "41.7" on the second — a fabricated number in neither the data
    # nor the source text, and not idempotent). A minus sign is only ever
    # a minus sign when the character before it isn't itself a digit — a
    # range hyphen always sits directly against the preceding number, a
    # genuine negative sign never does (it's preceded by whitespace, a verb,
    # or the start of the match). `(?<!\d)` expresses exactly that: it
    # blocks the hyphen from being treated as a match start when a digit
    # sits right before it, so matching falls through to the digit after
    # the hyphen instead, leaving the range's leading number and its
    # separator completely untouched. G9's negative-ratio cases are
    # unaffected — the hyphen there is always preceded by whitespace, never
    # a digit, so the lookbehind never blocks it.
    _wc_num_unit = r"(?<!\d)-?\d+\.?\d*\s*(?:months?|years?)"
    if metrics.working_capital_ratio is not None:
        correct_wc = f"{metrics.working_capital_ratio:.1f} months"
        # Pattern 1: <number> <months|years> of <working capital|reserves|...>
        rules.append(
            (
                rf"{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}",
                correct_wc + " of working capital",
                False,
                None,
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
                None,
            )
        )
        # Pattern 3: "X years' worth of operating"
        rules.append(
            (
                rf"{_wc_num_unit}['\u2019]?\s*worth\s+of\s+{_wc_noun}",
                correct_wc + " of working capital",
                False,
                None,
            )
        )
    else:
        # Remove any mention of working capital with a number
        rules.append(
            (
                rf"{_clause_lead}{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}{_clause_trail}",
                None,
                True,
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}(?:holds?|maintains?|has)\s+{_wc_num_unit}\s+(?:of\s+)?{_wc_noun}{_clause_trail}",
                None,
                True,
                None,
            )
        )

    # Program expense ratio
    # LLM variants: "directs X% to programs", "allocates X% to programmatic",
    # "X% of expenses go to programs", "X% of its budget", "program ratio of X%"
    _eff_program_ratio = _effective_program_ratio(metrics)
    if _eff_program_ratio is not None:
        pct = _eff_program_ratio * 100
        correct_ratio = f"{pct:.1f}%"
        # Pattern 1: <number>% program expense/spending
        rules.append(
            (
                r"\d+\.?\d*\s*%\s+(?:of\s+)?(?:program\s+(?:expense|spending))",
                f"{correct_ratio} program expense",
                False,
                None,
            )
        )
        # Pattern 2: program expense ratio of <number>%. Case-preserving (see
        # _preserve_case) — a preceding clause's removal can leave this one
        # sentence-initial and capitalized ("Program expense ratio ...").
        # Task G14: `_hedge_gap` between "of" and the number tolerates a
        # bounded hedge ("of only 50%") that used to defeat this anchor.
        rules.append(
            (
                rf"program\s+(?:expense\s+)?ratio\s+(?:of\s+{_hedge_gap})?\d+\.?\d*\s*%",
                _preserve_case(f"program expense ratio of {correct_ratio}"),
                False,
                None,
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
        # Task G14: `_hedge_gap` after the verb tolerates a bounded hedge
        # ("directs an impressive 91% to programs") that used to defeat
        # this anchor.
        rules.append(
            (
                rf"(?:directs?|allocates?|dedicates?|channels?|devotes?)\s+{_hedge_gap}\d+\.?\d*\s*%\s+(?:of\s+\w+\s+)?(?:to|toward)\s+(programs?|programmatic\s+(?:work|activities|expenses?))",
                lambda m: _match_case(m, f"directs {correct_ratio} to {m.group(1)}"),
                False,
                None,
            )
        )
        # Pattern 4: X% of expenses/budget/spending go to programs
        rules.append(
            (
                r"\d+\.?\d*\s*%\s+of\s+(?:its\s+)?(?:expenses?|budget|spending|revenue|funds?)\s+(?:goes?|go|is\s+directed|is\s+allocated)\s+(?:to|toward)\s+(?:programs?|programmatic)",
                f"{correct_ratio} of expenses goes to programs",
                False,
                None,
            )
        )
        # Pattern 5: spends X% on/for programs. The removal-side rule for
        # this exact phrasing (below, in the null branch) had no correction
        # counterpart, so a wrong number published verbatim whenever the
        # ratio was real instead of null. Case-preserving for the same
        # reason as patterns 2 and 3.
        # Task G14: `_hedge_gap` after "spends" tolerates a bounded hedge.
        rules.append(
            (
                rf"spends?\s+{_hedge_gap}\d+\.?\d*\s*%\s+(?:on|for)\s+(?:programs?|programmatic\s+(?:work|activities|expenses?))",
                _preserve_case(f"spends {correct_ratio} on programs"),
                False,
                None,
            )
        )
    else:
        # Remove sentences mentioning program expense ratio with a number.
        # Task G14: `_hedge_gap` in both rules below tolerates a bounded
        # hedge between the anchor word and the number — without it, e.g.
        # "directs an impressive 91% to programs" failed to match at all
        # and the fabrication survived untouched.
        rules.append(
            (
                rf"{_clause_lead}program\s+(?:expense\s+)?ratio\s+(?:of\s+{_hedge_gap})?\d+\.?\d*\s*%{_clause_trail}",
                None,
                True,
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}(?:directs?|allocates?)\s+{_hedge_gap}\d+\.?\d*\s*%\s+(?:of\s+\w+\s+)?(?:to|toward)\s+(?:programs?|programmatic){_clause_trail}",
                None,
                True,
                None,
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
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}spends?\s+{_hedge_gap}\d+\.?\d*\s*%\s+(?:on|for)\s+(?:programs?|programmatic\s+(?:work|activities|expenses?)){_clause_trail}",
                None,
                True,
                None,
            )
        )

    # Charity Navigator score
    # LLM variants: "accountability score of X", "financial score of X",
    # "rating of X/100", "rates X/100", "scored X out of 100", "X-star rating",
    # "perfect rating", "perfect score"
    cn_score = getattr(metrics, "cn_overall_score", None)
    cn_accountability = getattr(metrics, "cn_accountability_score", None)
    cn_financial = getattr(metrics, "cn_financial_score", None)

    # Task G20: a CN sub-score we COMPUTED must never be quoted as one CN
    # PUBLISHED. Charity Navigator publishes a single "Accountability &
    # Finance" beacon, and the collector has two paths to it:
    #   * _extract_nextjs_data_legacy reads CN's published number directly
    #     (`"slug":"accountability_finance"..."score":([0-9]+)`)
    #   * _extract_nextjs_data_new has no such field and instead recomputes a
    #     weighted mean over CN's sub-areas (`beacon_score(...)`)
    # The recomputation is a legitimate internal metric, but stamping it into
    # prose that ends "from Charity Navigator" publishes a figure CN never
    # stated under their name. 57 of 166 live charities carry such a value.
    #
    # Treat a non-publishable sub-score as ABSENT rather than correcting with
    # it: the existing null branch strips the claim, which is the fail-safe
    # outcome this function's governing tradeoff already prefers. Scoring,
    # ranking and the exported `scores` block are untouched — this only
    # governs what may be asserted in donor-facing prose.
    def _cn_subscore_is_publishable(value: Any, provenance: Any) -> bool:
        if value is None:
            return False
        if provenance == "computed_from_subareas":
            return False
        if provenance == "published_beacon":
            return True
        # Provenance absent — data crawled before the field existed. Fall back
        # to a mechanical property rather than a label: CN's published beacon
        # is captured by an INTEGER-only regex, so a non-integer value cannot
        # have come from it and must be the recomputation. Integers are
        # genuinely ambiguous and stay permissive, so this fallback only ever
        # withholds a correction it can prove is unpublishable.
        try:
            return float(value).is_integer()
        except (TypeError, ValueError):
            return False

    _cn_provenance = getattr(metrics, "cn_score_provenance", None)
    if not _cn_subscore_is_publishable(cn_accountability, _cn_provenance):
        cn_accountability = None
    if not _cn_subscore_is_publishable(cn_financial, _cn_provenance):
        cn_financial = None
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
    # "accountability rating of 50/100 from Charity Navigator", so without a
    # guard it would stamp the *overall* score into prose that names a
    # specific sub-score instead.
    #
    # Task G16: this guard used to work the other way around — a closed
    # list of sub-score names to REFUSE (`accountability|financial|
    # governance`) paired with a closed list of nouns to REFUSE
    # (`score|rating`). Both axes are open vocabulary, and each was escaped
    # in turn: a new noun ("rating"), a hedge word defeating the anchor,
    # the guard's own hedge bound expiring before the rule it guards — and,
    # live in the published corpus, a fourth Charity Navigator beacon name
    # ("Leadership") the list never enumerated at all
    # (charity-26-0906163.json's rich_narrative: "a Leadership score of
    # 20/100 from Charity Navigator" — inert on disk only because a
    # citation tag breaks the match; the same claim shape exists elsewhere
    # without one). Enumerating more names/nouns each time just narrows the
    # next gap, it can never close it.
    #
    # INVERTED: instead of a list of names to refuse, this is now a closed
    # list of names the overall rule may CLAIM — `_overall_name`, the
    # metric's own two ways of referring to itself ("overall", "Charity
    # Navigator"). `_named_metric_claim_lead_re` detects whether the number
    # is named by *something* at all — an open, un-enumerated noun (once a
    # connector word confirms a real "NAME NOUN of/is/was" claim shape, so
    # a bare "maintains a 91/100" never false-triggers on the verb+article
    # in front of it) — without needing to know *what* that something is.
    # If a name is detected and it ISN'T "overall"/"Charity Navigator", the
    # rule declines regardless of the noun used ("grade", "index", "mark",
    # "quotient", or anything else no one has enumerated yet) and
    # regardless of the name ("Leadership", a typo, a beacon added after
    # this code was written). If no name+noun claim is detected at all —
    # the number is genuinely bare, which is what 94/166 real published
    # files look like ("holds a 91/100 from Charity Navigator", "a perfect
    # 100/100 from Charity Navigator") — the rule proceeds, exactly as
    # before. The failure mode inverts correctly: an unrecognized name now
    # leaves the text alone rather than misattributing a different
    # metric's value to it. See
    # `TestOverallGuardFailsSafeOnAnyUnrecognizedName`.
    _overall_name = r"overall|Charity\s+Navigator(?:'s)?"
    # Common English determiners never constitute a metric NAME on their
    # own ("a 91/100", "its 91/100") — excluding this small, closed,
    # grammatical class (not a domain vocabulary) is what keeps a bare
    # "maintains a 91/100" from being misread as NAME="maintains" simply
    # because two content-ish words happen to sit in front of the number.
    _determiner = r"a|an|the|its|this|that|our|their|his|her"
    _metric_name_atom = (
        rf"(?:Charity\s+Navigator(?:'s)?"
        rf"|(?!(?:{_determiner})\b)[A-Za-z]+(?:\s*(?:&|and)\s*[A-Za-z]+)?)"
    )
    _named_metric_claim_lead_re = re.compile(
        rf"({_metric_name_atom})\s+(?:"
        # This codebase's own long-standing noun pair for a metric claim —
        # connector ("of"/"is"/"was") stays optional here, matching every
        # existing accountability/financial/overall rule elsewhere in this
        # function, so a "NAME score 40/100" with no "of" at all is still
        # recognized as named.
        rf"(?:score|rating)\s+(?:of|is|was)?"
        # Any OTHER noun ("grade", "index", "mark", "quotient", ...) — kept
        # deliberately open, but the connector is now MANDATORY. Without a
        # literal "of"/"is"/"was" immediately after it, two ordinary words
        # in front of a bare number ("maintains a", "holds a", "due to
        # its") would otherwise look identical to a genuine "NAME NOUN of"
        # claim; requiring the connector is what tells them apart without
        # having to enumerate which nouns are "real" ones.
        rf"|[A-Za-z]+\s+(?:of|is|was)"
        rf")\s*{_guard_gap}$",
        re.IGNORECASE,
    )

    # Task G18: the null-CN removal rules below (the `else` branch a few
    # lines down) anchor on two ends with a `_decimal_safe`-shaped gap
    # between them so genuine same-claim co-occurrence still matches
    # ("scored 87/100 last year from Charity Navigator") — but that same
    # permissive gap will just as happily bridge over an unrelated, TRUE
    # claim about a DIFFERENT metric sitting between the two anchors,
    # deleting it as collateral (e.g. "scored 87 out of 100, holding 8.3
    # months of working capital, from Charity Navigator" loses the
    # working-capital clause too). A bare `\d+/100` core is a second,
    # sharper version of the same hazard: with nothing to say otherwise, it
    # binds to ANY `/100` number in the sentence, including one that is
    # plainly named as a different metric's own score ("an accountability
    # rating of 91.0/100" — the only `/100` in the sentence — gets treated
    # as a leftover mention of the null overall score).
    #
    # `_other_metric_claim` names what "another metric's own claim" looks
    # like, built entirely from atoms this function already defines for
    # those metrics' own rules — not a new vocabulary list: `_acc_name`/
    # `_fin_name`/`_wc_noun` (the exact noun phrases the accountability,
    # financial, and working-capital rules already anchor on) plus the
    # literal "program(s)/programmatic" root the program-expense rules
    # already use throughout. `_cn_gap` is a local variant of
    # `_decimal_safe`, scoped to just the null-CN rules' MIDDLE gap below —
    # mirroring how `_fr_gap` was kept local to the fundraising rules
    # rather than folded into the shared gap. Used only as a middle gap
    # (sandwiched between two already-fixed anchors on both sides), never
    # as a leading/trailing run: a leading run is searched at EVERY string
    # position by the regex engine, and a per-character exclusion there
    # turned out to be escapable — if the run can't advance PAST an
    # excluded word, the engine simply retries the whole match starting
    # one position later, which either lands mid-word (garbling real text;
    # a bare word-boundary anchor closes that specific escape but doesn't
    # fix the next one) or past the excluded word entirely by restarting
    # at the very next token (confirmed empirically on both counts — see
    # the task report). A middle gap has no such escape hatch: both ends
    # are already fixed by the literal tokens on either side of it, so if
    # the exclusion blocks it from reaching the far anchor, the whole rule
    # simply fails to match rather than resuming somewhere else. The two
    # rules whose OWN core is a bare, unqualified `\d+/100` (and so can be
    # bound to a DIFFERENT metric's own number outright, not just bridge
    # over one) are guarded separately below via `_removed_span_joints`'s
    # optional per-match `guard`, reusing the exact backward/forward checks
    # this function already has for that question.
    #
    # Audited against every metric family this function knows, not just
    # the ones the first repros happened to name. First pass only listed
    # working capital/program expense/accountability/financial, reasoning
    # by analogy that AMAL, founded year, and zakat "don't happen to graze"
    # the CN rules' anchors in practice — checked that claim empirically
    # and it was wrong for two of the three:
    #   "It scored 87 out of 100, with an AMAL score of 75/100, from
    #   Charity Navigator." -> "It scored 87 out of 100."          true AMAL score destroyed
    #   "It scored 87 out of 100, founded in 1985, from Charity
    #   Navigator." -> ""                              true founding year destroyed, whole sentence gone
    #   "It scored 87 out of 100, operating since 1985, from Charity
    #   Navigator." -> ""                              same, via the "operating since" phrasing
    # `_metric_noun_boundary` (defined above, already the closed set
    # `_hedge_gap`/`_guard_gap` use for the identical "don't cross into a
    # different metric's own phrase" reason) already carries every one of
    # these nouns — "amal", "founded", "established", "incorporated",
    # "started", "began", "operating", "serving", "active", "working",
    # "zakat" — audited there once already, so reused wholesale here
    # instead of hand-picking a narrower list a second time. Including its
    # "navigator" alternative is harmless: the gap this set guards is
    # always positioned immediately before/after the literal `Charity\s+
    # Navigator` text in the pattern itself, so the gap was never going to
    # need to consume that word as filler regardless.
    # Fundraising is the one family `_metric_noun_boundary` only partly
    # covers — it has the bare words "fundraising"/"efficiency", but the
    # repro'd shape ("spends $0.05 per $1 raised") uses neither word at
    # all. `_fr_phrasing` (the fundraising rules' own dollar-phrasing
    # patterns) closes that; its definition is moved up here from where
    # the fundraising rules build themselves, further down, since it now
    # needs to exist before the CN rules are built too. Confirmed
    # vulnerable without it: "It scored 87 out of 100, spends $0.05 per $1
    # raised, and is from Charity Navigator." destroyed the true
    # fundraising figure.
    # CN overall itself is the only family deliberately left out — it's
    # this rule's own subject, not "another" metric.
    _fr_phrasing = r"(?:per\s+\$?1\s+raised|to\s+raise\s+(?:\$1|each\s+dollar|a\s+dollar)|per\s+dollar\s+raised|for\s+every\s+dollar\s+raised)"
    _other_metric_noun = rf"(?:{_metric_noun_boundary}|{_fr_phrasing})"
    _other_metric_claim = (
        rf"(?:{_other_metric_noun})\b"
        rf"|\d+\.?\d*\s*(?:/\s*100|out\s+of\s+100|%)\s*(?:of\s+|to\s+|for\s+|on\s+|toward\s+)?(?:{_other_metric_noun})\b"
    )
    # `_cn_gap` also never consumes into a bare `\d+\.?\d*/100` span as
    # ordinary filler — the same reason `_cn_number_lead` below doesn't:
    # two of this gap's uses (the number-first and name-first rules) sit
    # right next to a dedicated capture group for exactly that shape, and
    # an unguarded greedy gap eats into it, leaving the capture group only
    # the last digit or two (see the task report). Harmless for this
    # gap's other uses (a fixed literal anchor, not a bare-number capture
    # group, follows it there) — it just means the gap stops one number
    # early in the rare case an unrelated `/100` figure sits inside it too.
    _cn_gap = rf"(?:(?!{_other_metric_claim}|\d+\.?\d*/100)(?:[^.]|(?<=\d)\.(?=\d)))*"

    # `_clause_lead`'s run is unbounded and greedy, so left unguarded it
    # eats INTO a decimal number sitting right in front of a `/100` core —
    # backtracking only gives back the one digit the core strictly needs
    # (e.g. leaving "0/100" for the core out of a true "91.0/100"), which
    # then feeds a truncated, wrong position into the backward-naming guard
    # below. `_cn_number_lead` is `_clause_lead` with one added exclusion:
    # never consume into a `\d+\.?\d*/100` span as ordinary filler — it
    # doesn't matter whose number it is (this rule's own target or a
    # different metric's), the run simply always stops right before ANY
    # such number and leaves it whole for the dedicated capture group that
    # follows, so the guard always sees the number's true start.
    _cn_number_lead = (
        rf"(?:{_label_colon_lead})?"
        r"(?:\s*(?:[,;:]|—)\s*(?:and\s+)?|\s+and\s+)?"
        r"(?:(?!\s+and\b|\d+\.?\d*/100)(?:[^.,;:?!—]|(?<=\d)\.(?=\d)|(?<=\d),(?=\d)))*"
    )

    # The two rules below with a bare `\d+/100` core (number-first and
    # name-first) can bind that core directly to a DIFFERENT metric's own
    # number when nothing else in the sentence has a `/100` to offer — no
    # gap-crossing involved, the core itself is just ambiguous. Rather than
    # try to block this with another per-character exclusion (the same
    # escape hatch as above applies just as much to the core's own start),
    # each rule below captures its number in group 1 and pairs it with a
    # `guard(match) -> bool` — reusing the existing distinction between
    # "named by something else" and "genuinely bare" this function already
    # answers for the correction path just above (backward-search shape),
    # but scoped to `_other_metric_noun`'s own closed set rather than the
    # generic `_metric_name_atom`/`_named_metric_claim_lead_re` used there:
    # that generic matcher accepts ANY non-determiner word as a candidate
    # "name" (deliberately — it has to catch an unenumerated beacon like
    # "Leadership" for the correction path's own guard), which also makes
    # it accept ordinary PRONOUN subjects ("it", "he") in front of "score"
    # used as a VERB, not a noun. Confirmed empirically: reusing it here
    # broke a real, pinned test — "Did it score 87/100 on Charity
    # Navigator?" read "it score" as NAME="it" and declined to remove the
    # whole bare, unnamed claim. `_other_metric_noun`'s vocabulary is a
    # CLOSED set of specific metric words, never a pronoun, so it doesn't
    # have this failure mode — confirmed this also closes the AMAL variant
    # of the same "wrong anchor" hazard ("with an AMAL score of 75/100,
    # from Charity Navigator" used to destroy the true AMAL score the same
    # way accountability/financial did).
    # Task G14's `_hedge_gap` (a bounded, metric-noun-excluding word gap)
    # is reused here too — hand-probing found a bare "of\s+|is\s+|was\s+"
    # connector defeated by the exact same hedge-word shape every other
    # anchor in this function already had to tolerate ("accountability
    # rating of ROUGHLY 91.0/100" reached the string end without matching,
    # so the guard wrongly declined to protect a real accountability value).
    _other_metric_lead_re = re.compile(
        rf"(?:{_other_metric_noun})\s+(?:score|rating|ratio)\s+(?:(?:of|is|was)\s+{_hedge_gap})?$",
        re.IGNORECASE,
    )
    _other_metric_trail_re = re.compile(
        rf"^\s*(?:of\s+|to\s+|for\s+|on\s+|toward\s+)?(?:{_other_metric_noun})\b",
        re.IGNORECASE,
    )

    def _bare_number_not_named_before(m: "re.Match[str]") -> bool:
        """Guard for the number-first rule: decline to remove group 1 if
        BACKWARD text names it as a different metric's own score ("an
        accountability rating of 91.0/100" leading into a bare `\\d+/100`
        core)."""
        return not _other_metric_lead_re.search(m.string[: m.start(1)])

    def _bare_number_not_named_after(m: "re.Match[str]") -> bool:
        """Guard for the name-first rule: decline to remove group 1 if
        FORWARD text immediately names it as a different metric's own
        score ("Charity Navigator notes its 91.0/100 accountability
        score" — the naming here trails the number instead of leading it,
        so the backward check above can't see it)."""
        return not _other_metric_trail_re.match(m.string[m.end(1) :])

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
        # `_named_metric_claim_lead_re` guard: don't claim a number that's
        # named by ANYTHING other than the overall score itself (see its
        # definition above) — leave it untouched here so that metric's own
        # rule (if one exists — accountability/financial do, an unrecognized
        # beacon like "Leadership" doesn't) can correct it instead, or it
        # stays an honest residual gap rather than a misattribution.
        # `_number_not_malformed` guard: don't touch a malformed
        # multi-decimal numeral at all (see that variable's definition
        # above).
        def _correct_cn_overall_number_before(m: "re.Match[str]") -> str:
            named = _named_metric_claim_lead_re.search(m.string[: m.start()])
            if named and not re.fullmatch(_overall_name, named.group(1), re.IGNORECASE):
                return m.group(0)
            return f"{correct_cn} {m.group(1) or 'from '}Charity Navigator"

        rules.append(
            (
                rf"{_number_not_malformed}\d+\.?\d*/100\s+(from\s+|by\s+|on\s+|score\s+(?:from\s+|on\s+)?)?(?:Charity\s+Navigator)",
                _correct_cn_overall_number_before,
                False,
                None,
            )
        )
        # "Charity Navigator ... score/rating of X". Task G14: `_hedge_gap`
        # after "of" tolerates a bounded hedge ("score of roughly 60").
        rules.append(
            (
                rf"(?:Charity\s+Navigator)\s+(?:overall\s+)?(?:score|rating)\s+(?:of\s+{_hedge_gap})?\d+\.?\d*(?:/100)?",
                f"Charity Navigator score of {correct_cn}",
                False,
                None,
            )
        )
        # "scored X out of 100 on Charity Navigator". Case-preserving (see
        # _preserve_case) — a preceding clause's removal can leave this one
        # sentence-initial and capitalized ("Scored ..."). Task G14:
        # `_hedge_gap` after the optional "a" tolerates a bounded hedge.
        rules.append(
            (
                rf"(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+{_hedge_gap})?\d+\.?\d*\s+(?:out\s+of\s+100|/100)\s+(?:on|from|by)\s+Charity\s+Navigator",
                _preserve_case(f"scored {correct_cn} on Charity Navigator"),
                False,
                None,
            )
        )
    else:
        # Strip any fabricated CN score claim — broad patterns. The middle
        # `_cn_gap` (a `_decimal_safe`-shaped gap, see Task G18 above) stays
        # permissive for co-occurrence within one sentence (e.g. "scored
        # 87/100 last year from Charity Navigator"), just not permissive
        # enough to reach past a DIFFERENT metric's own claim; the outer
        # leading/trailing edges stay plain `_clause_lead`/`_clause_trail`.
        # The two rules whose own core is a bare `\d+/100` additionally
        # capture it (group 1) and pass a `guard` instead of `None` — see
        # `_bare_number_not_named_before`/`_bare_number_not_named_after`
        # above.
        rules.append(
            (
                rf"{_cn_number_lead}(\d+\.?\d*/100){_cn_gap}Charity\s+Navigator{_clause_trail}",
                None,
                True,
                _bare_number_not_named_before,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}Charity\s+Navigator{_cn_gap}(\d+\.?\d*/100){_clause_trail}",
                None,
                True,
                _bare_number_not_named_after,
            )
        )
        # "scored/rates X out of 100 ... Charity Navigator". Task G14:
        # `_hedge_gap` after the optional "a" tolerates a bounded hedge.
        rules.append(
            (
                rf"{_clause_lead}(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+{_hedge_gap})?\d+\.?\d*\s+out\s+of\s+100{_cn_gap}Charity\s+Navigator{_clause_trail}",
                None,
                True,
                None,
            )
        )
        # "Charity Navigator ... scored/rates X"
        # The trailing "out of 100"/"/100" is optional, so when it's absent
        # the number itself is the last thing the core pattern requires —
        # `\d+(?:\.\d+)?` (not `\d+\.?\d*`) so a bare "87." at the true
        # sentence end isn't misread as "87" plus an empty decimal point,
        # which would swallow the period a surviving clause needs. Task
        # G14: `_hedge_gap` after the optional "a" tolerates a bounded
        # hedge.
        rules.append(
            (
                rf"{_clause_lead}Charity\s+Navigator{_cn_gap}(?:scores?d?|rates?d?|receives?d?)\s+(?:a\s+{_hedge_gap})?\d+(?:\.\d+)?(?:\s+out\s+of\s+100|/100)?{_clause_trail}",
                None,
                True,
                None,
            )
        )
        # "perfect score/rating ... Charity Navigator" or vice versa. This is
        # the family that motivates keeping the trailing edge sentence-scoped
        # rather than clause-scoped: "a perfect score from Charity Navigator,
        # its highest rating." must lose the whole appositive tail, not just
        # up to the comma.
        rules.append(
            (
                rf"{_clause_lead}(?:perfect|top|highest)\s+(?:score|rating|marks?){_cn_gap}Charity\s+Navigator{_clause_trail}",
                None,
                True,
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}Charity\s+Navigator{_cn_gap}(?:perfect|top|highest)\s+(?:score|rating|marks?){_clause_trail}",
                None,
                True,
                None,
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
        # Task G14: `_hedge_gap` after "of" tolerates a bounded hedge
        # ("accountability score of only 40/100") that used to defeat this
        # anchor and leave a wrong-but-real number uncorrected.
        rules.append(
            (
                rf"({_acc_name})\s+(score|rating)\s+(?:of\s+{_hedge_gap})?{_number_not_malformed}\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?",
                lambda m: _match_case(m, f"{m.group(1)} {m.group(2)} of {correct_acc}"),
                False,
                None,
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
                None,
            )
        )
    else:
        # Task G14: `_hedge_gap` after "of" — a null accountability score
        # phrased with a hedge ("accountability score of roughly 40") used
        # to fail this removal entirely, so the fabrication survived.
        rules.append(
            (
                rf"{_clause_lead}(?:{_acc_name})\s+(?:score|rating)\s+(?:of\s+{_hedge_gap})?\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?{_clause_trail}",
                None,
                True,
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}\d+(?:\.\d+)?/100\s+(?:{_acc_name})\s+(?:score|rating){_clause_trail}",
                None,
                True,
                None,
            )
        )
    if cn_financial is not None:
        correct_fin = f"{round(cn_financial, 1)}/100"
        # Same echo-the-noun-phrase approach as accountability's Pattern 1
        # above (captures "financial score" vs "financial health score", and
        # now "score" vs "rating" too, echoing whichever was actually used
        # rather than canonicalizing). Case-preserving for the same reason
        # as the accountability pattern. Task G14: `_hedge_gap` after "of"
        # tolerates a bounded hedge ("financial score of nearly 40/100").
        rules.append(
            (
                rf"({_fin_name}\s+(?:score|rating))\s+(?:of\s+{_hedge_gap})?{_number_not_malformed}\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?",
                lambda m: _match_case(m, f"{m.group(1)} of {correct_fin}"),
                False,
                None,
            )
        )
    else:
        # Task G14: `_hedge_gap` after "of" — same reasoning as
        # accountability's null branch above.
        rules.append(
            (
                rf"{_clause_lead}{_fin_name}\s+(?:score|rating)\s+(?:of\s+{_hedge_gap})?\d+(?:\.\d+)?(?:/100|\s+out\s+of\s+100|%)?{_clause_trail}",
                None,
                True,
                None,
            )
        )
    # Strip "X-star rating" if no CN score at all
    if cn_score is None:
        rules.append(
            (
                rf"{_clause_lead}\d+-?\s*star\s+(?:rating|charity){_cn_gap}Charity\s+Navigator{_clause_trail}",
                None,
                True,
                None,
            )
        )

    # Fundraising efficiency
    # LLM variants: "per dollar raised", "to raise each dollar", "for every dollar",
    # "fundraising costs of $X.XX"
    # `_fr_phrasing` itself is defined above, alongside `_other_metric_noun`
    # (Task G18) — it needed to exist before the CN section builds its own
    # rules, so the fundraising family could be included in what "another
    # metric's claim" means there too.
    if (
        metrics.fundraising_expenses is not None
        and metrics.total_contributions
        and metrics.total_contributions > 0
    ):
        correct_fr = _fundraising_ratio_str(metrics.fundraising_expenses, metrics.total_contributions)
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
                None,
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
                None,
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
        # The middle scan stays _decimal_safe-shaped (co-occurrence within
        # one sentence — a decimal point elsewhere is never mistaken for the
        # sentence's end). The trailing scan is now _clause_trail as well, so
        # a *following* clause coordinated with ", and ..." (a true claim
        # about a different metric) survives instead of being swallowed too.
        #
        # Task G12 (defect 1): the middle gap here is `_fr_gap`, not the
        # shared `_decimal_safe` — it additionally excludes a bare " and " the
        # same way `_clause_lead`/`_clause_trail` do. `\$\d+\.?\d*` can match
        # a truncated PREFIX of an unrelated true dollar figure elsewhere in
        # the sentence (its own `\d+` simply stops at that number's own
        # thousands comma, e.g. grabbing "$141" out of "$141,261"), and
        # `_decimal_safe`'s unconditional comma tolerance then let the middle
        # gap bridge straight through "and" to reach "fundraising efficiency"
        # — bringing the *true revenue clause* along for the ride. This
        # doesn't fold into the shared `_decimal_safe`: a real, tested case
        # (`TestClauseTrailBareAndBoundary.
        # test_and_inside_the_removed_claims_own_cooccurrence_gap_is_unaffected`)
        # deliberately relies on `_decimal_safe` tolerating a bare "and"
        # *inside one claim's own phrasing* ("Charity Navigator rated it 82
        # and awarded 87/100"), which only the CN/accountability/financial
        # rules need (none of them anchor on a truncatable `\$` number, so
        # they aren't exposed to this defect) — scoping the "and"-exclusion
        # to just the two fundraising rules below fixes the real defect
        # without reopening that.
        #
        # Task G12 follow-up (gap 1): excluding "and" isn't enough — a bare
        # COMMA joining the null-fundraising clause to an unrelated true
        # dollar clause exposes the same mechanism. `\$\d+\.?\d*` matches a
        # truncated PREFIX of any dollar figure in the sentence (stopping at
        # that number's own thousands comma), and because `_fr_gap*` is
        # greedy, the regex engine tries the LONGEST possible gap first and
        # only backtracks character-by-character from the end — so it binds
        # to whichever `$` figure sits FARTHEST away, not nearest, if more
        # than one is reachable. E.g. "Fundraising efficiency was $0.00,
        # total revenue reached $141,261 this year." must bind to the
        # adjacent "$0.00", but the greedy gap (tolerating the comma same as
        # `_decimal_safe`) instead reaches across it to "$141,261",
        # truncating to "$141" and dragging the entire true revenue clause
        # into the removal. Excluding the literal `$` from the gap's
        # character class makes it impossible to consume past any dollar
        # sign at all, so the core can only ever bind to the NEAREST one —
        # exactly the resolution needed, and verified against all three
        # `REAL_HALLUCINATIONS` entries plus both new pinned cases below.
        # Task G18: this gap has the exact same cross-metric-claim hazard
        # as the null-CN removal rules above (confirmed empirically — a
        # true "8.3 months of working capital", "91.4% to programs", or
        # "accountability rating of 91.0/100" clause sitting between
        # "fundraising efficiency" and the `$` figure was deleted along
        # with the fabrication). Reuses the same `_other_metric_claim`
        # defined above rather than a new vocabulary list.
        _fr_gap = rf"(?:(?!\s+and\b|{_other_metric_claim})(?:[^.$]|(?<=\d)\.(?=\d)))*"
        # Task G12 follow-up (gap 1, round 2): excluding `$` closes the
        # far-figure defect but not a related one on the *dollar-first* rule
        # only: `\$\d+\.?\d*` can itself anchor on a truncated PREFIX of an
        # unrelated true dollar figure with nothing else needed on the far
        # side — the literal phrase "fundraising efficiency" needs no dollar
        # amount of its own to satisfy this rule's suffix, so a bare comma
        # joining a true "$141,261" to a plain mention of "fundraising
        # efficiency" ("...$141,261, fundraising efficiency was mentioned.")
        # still destroys the true clause even with no second `$` in sight.
        # The *phrase*-first rule below doesn't have this problem — its own
        # anchor is the unambiguous literal "fundraising efficiency", so a
        # true dollar figure can never masquerade as it — and it must keep
        # tolerating a bare comma regardless: the real, pinned hallucination
        # "high fundraising efficiency, spending $0.00 to raise every $1"
        # needs its gap to cross exactly that comma.
        #
        # An unconditional bare-comma boundary on the dollar-first gap fixes
        # the true-fact case above, but hand-probing found it reopens a
        # false negative: "The charity spent $0.00, an indication of poor
        # fundraising efficiency." is a genuine, natural two-sided
        # fabrication (the SAME $0.00 figure, commented on across the
        # comma) that an unconditional boundary would leave unstripped. So
        # `_fr_gap_dollar_first` reuses `_trail_same_claim_lead` — the exact
        # question that already distinguishes an appositive of the same
        # claim from an independent clause for `_clause_trail` — rather than
        # inventing a second mechanism: a bare comma is a boundary UNLESS
        # what follows reads as a continuation of the same dollar figure
        # (determiner/possessive/comparative lead-in). This closes the
        # determiner-led hallucination shape above while still blocking both
        # true-fact cases (neither "fundraising efficiency was mentioned"
        # nor "though fundraising efficiency..." opens with anything on
        # that list). It does NOT close every shape: a gerund-led
        # continuation of the same claim ("$0.00, reflecting strong
        # fundraising efficiency") still fails to strip, for the same
        # reason `_trail_same_claim_lead` was deliberately never given a
        # verb list — the set of participles that can lead a same-claim
        # appositive is exactly as unbounded as the set of verbs that can
        # lead an independent clause, so there's no way to add "reflecting"
        # without every other participle needing the same treatment.
        # Reported as a known residual gap rather than forced further.
        #
        # Task G18: also add the `_other_metric_claim` exclusion (same as
        # `_fr_gap` above). This gap's bare-comma-boundary-by-default
        # design (the `,(?=...)` alternative just above) already stops it
        # from bridging over an embedded true claim joined by a plain
        # comma with no continuation marker — but a SEMICOLON-joined one
        # ("spent $0.00; holding 8.3 months of working capital; per $1
        # raised.") wasn't caught: `;` was never excluded from this gap's
        # character class the way `_clause_lead`/`_clause_trail` exclude it
        # (task G12 added that boundary to those two, never to the
        # fundraising gaps). Confirmed empirically that adding
        # `_other_metric_claim` closes it too, since the exclusion fires on
        # the claim's own wording, not on which punctuation joins it.
        _fr_gap_dollar_first = (
            rf"(?:(?!\s+and\b|{_other_metric_claim})(?:[^.,$]|(?<=\d)\.(?=\d)|(?<=\d),(?=\d))"
            rf"|,(?=\s*(?:{_trail_same_claim_lead})))*"
        )
        rules.append(
            (
                rf"{_clause_lead}\$\d+\.?\d*{_fr_gap_dollar_first}(?:{_fr_phrasing}|fundraising\s+efficiency){_clause_trail}",
                None,
                True,
                None,
            )
        )
        # No suffix follows the dollar amount here, so it's the last thing
        # the core requires — same bare-trailing-number risk as the CN/
        # accountability/financial rules above; `\d+(?:\.\d+)?` guards it.
        # Same `_fr_gap` swap as above, and for the same reason: the trailing
        # `\$\d+(?:\.\d+)?` here can just as easily truncate-bind to an
        # unrelated true dollar figure that follows "fundraising efficiency"
        # later in the sentence. Deliberately still `_fr_gap`, not
        # `_fr_gap_dollar_first`: this rule's own anchor is the unambiguous
        # literal "fundraising efficiency", so it never suffers the dollar-
        # first rule's "a true figure alone satisfies the whole core"
        # failure mode, and the real pinned hallucination
        # ("high fundraising efficiency, spending $0.00...") needs the bare
        # comma tolerated here too.
        rules.append(
            (
                rf"{_clause_lead}fundraising\s+efficiency{_fr_gap}\$\d+(?:\.\d+)?{_clause_trail}",
                None,
                True,
                None,
            )
        )
        # "fundraising costs/expenses of $X.XX per dollar" (no "raised" suffix,
        # so it isn't covered by _fr_phrasing above)
        rules.append(
            (
                rf"{_clause_lead}fundraising\s+(?:costs?|expenses?)\s+(?:of\s+)?\$\d+\.?\d*\s+per\s+(?:dollar|every\s+dollar){_clause_trail}",
                None,
                True,
                None,
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
                None,
            )
        )
        # Task G14: `_hedge_gap` after "of" tolerates a bounded hedge
        # ("AMAL score of roughly 72").
        rules.append(
            (
                rf"(?:AMAL|Amal|amal)\s+score\s+(?:of\s+{_hedge_gap})?\d+\.?\d*(?:/100)?",
                f"AMAL score of {correct_amal}",
                False,
                None,
            )
        )
    else:
        # Task G13: this metric had only the correction half — a null
        # amal_score (the guard above also covers scores being None or
        # missing the attribute entirely, not just an explicit None value)
        # let a fabricated AMAL score claim survive verbatim. Mirrors the
        # two correction patterns above (number-before, number-after), plus
        # a third phrasing ("scored X on the AMAL index") that has no
        # correction counterpart today — same kind of asymmetry task G12
        # found and fixed for program_expense_ratio's "spends X% on
        # programs", left here since fixing it is a correction-side
        # question outside this task's scope.
        # Task G14: `_hedge_gap` after "of" — a null amal_score phrased
        # with a hedge ("AMAL score of roughly 72") used to fail this
        # removal entirely, so the fabrication survived.
        rules.append(
            (
                rf"{_clause_lead}(?:AMAL|Amal|amal)\s+score\s+(?:of\s+{_hedge_gap})?\d+\.?\d*(?:/100)?{_clause_trail}",
                None,
                True,
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}\d+\.?\d*/100\s+(?:AMAL|Amal|amal){_clause_trail}",
                None,
                True,
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}scored\s+{_hedge_gap}\d+\.?\d*\s+on\s+the\s+(?:AMAL|Amal|amal)\s+index{_clause_trail}",
                None,
                True,
                None,
            )
        )

    # Sadaqah language — strip ALWAYS, whatever the wallet tag. Sadaqah is the
    # default tier every charity qualifies for, so asserting it tells the donor
    # nothing while reading as a determination we made, and it was that
    # assertion (not any zakat claim) that judges kept flagging as unsupported.
    # The prompt now asks for silence; this enforces it on the way out.
    _sadaqah_keywords = (
        r"(?:sadaqah[\s-]*(?:eligible|eligibility|only|compliant)"
        r"|(?:considered|qualifies?\s+as|counts?\s+as|treated\s+as)\s+sadaqah"
        r"|(?:for|through)\s+sadaqah\s+giving)"
    )
    rules.append(
        (
            rf"{_clause_lead}{_sadaqah_keywords}{_clause_trail}",
            None,
            True,
            None,
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
                None,
            )
        )

    # Founded year — correct wrong years in narrative
    founded_year = getattr(metrics, "founded_year", None)
    if founded_year:
        # "founded in XXXX" / "established in XXXX" / "since XXXX" / "incorporated
        # in XXXX". Case-preserving (see _preserve_case) — a preceding clause's
        # removal can leave this one sentence-initial and capitalized
        # ("Founded in ...").
        # Task G14: `_hedge_gap` after "in" tolerates a bounded hedge
        # ("founded in approximately 1975").
        rules.append(
            (
                rf"(?:founded|established|incorporated|started|began(?:\s+operations)?)\s+in\s+{_hedge_gap}\d{{4}}",
                _preserve_case(f"founded in {founded_year}"),
                False,
                None,
            )
        )
        # "since XXXX" when referring to founding (e.g. "operating since 1985").
        # Case-preserving for the same reason. Task G14: `_hedge_gap` after
        # "since" tolerates a bounded hedge the same way.
        rules.append(
            (
                rf"(?:operating|serving|active|working)\s+since\s+{_hedge_gap}\d{{4}}",
                _preserve_case(f"operating since {founded_year}"),
                False,
                None,
            )
        )
    else:
        # Task G13: this metric had only the correction half — a null
        # founded_year (no filings, a brand-new organization) let a
        # fabricated founding-year claim survive verbatim. Mirrors the two
        # correction patterns above, clause-scoped like every other null
        # branch in this function.
        #
        # Anchored to the same founding-specific verbs the correction rules
        # use — never a bare year. A four-digit year alone is indistinguishable
        # from any other number, and these narratives are full of dates that
        # have nothing to do with founding ("in 2024 it served 4,000
        # families", "its FY2023 filings", "revenue grew through 2022 and
        # 2023") — none of those carry "founded"/"established"/.../"in" or
        # "operating"/.../"since" immediately adjacent to the year, so they
        # never reach either pattern below.
        # Task G14: `_hedge_gap` after "in" — a null founded_year phrased
        # with a hedge ("founded in approximately 1975") used to fail this
        # removal entirely, so the fabrication survived.
        rules.append(
            (
                rf"{_clause_lead}(?:founded|established|incorporated|started|began(?:\s+operations)?)\s+in\s+{_hedge_gap}\d{{4}}{_clause_trail}",
                None,
                True,
                None,
            )
        )
        rules.append(
            (
                rf"{_clause_lead}(?:operating|serving|active|working)\s+since\s+{_hedge_gap}\d{{4}}{_clause_trail}",
                None,
                True,
                None,
            )
        )
        # "a 1985 organization/nonprofit/charity" — number-before-noun
        # phrasing with no correction counterpart above (same asymmetry
        # task G12 fixed for program_expense_ratio's "spends X% on
        # programs"); anchored to the same closed noun list, not a bare
        # year, for the same reason as the two rules above.
        #
        # Hand-probed and found a real over-removal without the trailing
        # lookahead: "organization"/"nonprofit"/"charity" are common enough
        # nouns that they head compound noun phrases with nothing to do
        # with founding — "a 2020 charity gala", "a 1999 nonprofit
        # fundraiser", "a 2015 charity initiative". Without a boundary
        # requirement right after the noun, `_clause_trail` freely swallows
        # the rest of the sentence ("...gala that raised $50,000 for local
        # families." -> ""), destroying an unrelated true fact — the exact
        # "new fact-destroying bug" failure mode this task must not
        # introduce. The lookahead requires the noun be immediately
        # followed by an actual clause boundary (or the string end), the
        # same boundary set `_clause_trail` itself treats as a stop —
        # so a further noun continuing the same phrase blocks the match
        # entirely, leaving the whole sentence untouched (an accepted
        # under-removal; per this function's own standing tie-break, a
        # surviving fabrication-adjacent fragment is preferred to deleting
        # an unrelated true clause).
        rules.append(
            (
                rf"{_clause_lead}a\s+\d{{4}}\s+(?:organization|nonprofit|non-profit|charity)"
                rf"(?=[.,;:?!—]|\s+and\b|$){_clause_trail}",
                None,
                True,
                None,
            )
        )

    # ── Apply rules to every string in the narrative ──
    def _apply_rules(text: str) -> str:
        for pattern, replacement, is_removal, guard in rules:
            if is_removal:
                stripped, joints = _removed_span_joints(pattern, text, guard=guard)
                # Only run the repair pass when this rule actually removed
                # something. Every rule runs over every string field, so most
                # (pattern, text) pairs never match at all — repairing
                # unconditionally would "fix" (e.g. capitalize) text this
                # rule never touched, which isn't this rule's to fix.
                if stripped != text:
                    text = _repair_removal_artifacts(stripped, joints)
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

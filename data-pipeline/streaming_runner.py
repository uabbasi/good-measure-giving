#!/usr/bin/env python3
"""
Streaming Pipeline Runner - Process charities end-to-end through all phases.

Queue-based architecture: Each worker processes a charity completely through
all 4 phases (crawl → extract → synthesize → baseline) before taking the next.

Benefits over batch-per-phase:
- Charities complete fully, not stuck mid-pipeline
- Memory efficient (no large intermediate state)
- Progress visible per-charity

Usage:
    uv run python streaming_runner.py --charities pilot_charities.txt --workers 20
    uv run python streaming_runner.py --ein 95-4453134  # Single charity
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.collectors.bbb_collector import BBBCollector
from src.collectors.candid_beautifulsoup import CandidCollector
from src.collectors.charity_navigator import CharityNavigatorCollector
from src.collectors.form990_grants import Form990GrantsCollector
from src.collectors.orchestrator import DataCollectionOrchestrator
from src.collectors.propublica import ProPublicaCollector
from src.collectors.web_collector import WebsiteCollector
from src.db import (
    CharityDataRepository,
    CharityRepository,
    EvaluationRepository,
    PhaseCacheRepository,
    RawDataRepository,
)
from src.db.dolt_client import dolt
from src.llm.llm_client import LLMClient
from src.scorers.v2_scorers import AmalScorerV2
from src.utils.charity_loader import load_charities_from_file, normalize_website_url
from src.utils.ein_utils import validate_and_format
from src.utils.logger import PipelineLogger
from src.utils.phase_cache_helper import (
    check_phase_cache,
    get_phase_fingerprint,
    update_phase_cache,
)
from src.utils.phase_fingerprint import get_ttl_days

# Discovery services - use Gemini's search grounding feature
DISCOVERY_ENABLED = True
# Import from root export.py (not src/export.py)
import importlib.util

from baseline import evaluate_charity
from extract import extract_row
from judge_phase import judge_charity
from rich_phase import generate_rich_for_pipeline

# Quality judges for inline validation after each phase
from src.judges.baseline_quality_judge import BaselineQualityJudge
from src.judges.crawl_quality_judge import CrawlQualityJudge
from src.judges.discover_quality_judge import DiscoverQualityJudge
from src.judges.export_quality_judge import ExportQualityJudge
from src.judges.extract_quality_judge import ExtractQualityJudge
from src.judges.rich_quality_judge import RichQualityJudge
from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import Severity
from src.judges.synthesize_quality_judge import SynthesizeQualityJudge
from src.schemas.discovery import (
    SECTION_AWARDS,
    SECTION_EVALUATIONS,
    SECTION_OUTCOMES,
    SECTION_THEORY_OF_CHANGE,
    SECTION_ZAKAT,
)
from src.services.awards_discovery_service import AwardsDiscoveryService
from src.services.evidence_discovery_service import EvidenceDiscoveryService
from src.services.outcome_discovery_service import OutcomeDiscoveryService
from src.services.toc_discovery_service import TheoryOfChangeDiscoveryService
from src.services.zakat_verification_service import ZakatVerificationService

# Import phase functions
from synthesize import synthesize_charity

_export_spec = importlib.util.spec_from_file_location("root_export", Path(__file__).parent / "export.py")
_export_module = importlib.util.module_from_spec(_export_spec)
_export_spec.loader.exec_module(_export_module)
export_charity = _export_module.export_charity
WEBSITE_DATA_DIR = _export_module.WEBSITE_DATA_DIR
load_pilot_charities = _export_module.load_pilot_charities
build_charity_summary = _export_module.build_charity_summary
load_ui_signals_config = _export_module._load_ui_signals_config
compute_ui_signals_config_hash = _export_module._compute_config_hash

# Thread-safe printing and progress tracking
print_lock = Lock()
progress_lock = Lock()
progress = {"completed": 0, "failed": 0, "total": 0}

# Map source names to collector classes
COLLECTORS = {
    "propublica": ProPublicaCollector,
    "charity_navigator": CharityNavigatorCollector,
    "candid": CandidCollector,
    "form990_grants": Form990GrantsCollector,
    "bbb": BBBCollector,
    "website": WebsiteCollector,
}

# Shared judge config for inline validation (lightweight, no LLM)
_inline_judge_config = JudgeConfig(sample_rate=1.0)

# Map phase names to their quality judge classes
PHASE_QUALITY_JUDGES = {
    "crawl": CrawlQualityJudge,
    "extract": ExtractQualityJudge,
    "discover": DiscoverQualityJudge,
    "synthesize": SynthesizeQualityJudge,
    "baseline": BaselineQualityJudge,
    "rich": RichQualityJudge,
    "export": ExportQualityJudge,
}


def run_inline_quality_check(
    phase: str,
    ein: str,
    output: dict,
    context: dict,
) -> tuple[bool, list[dict]]:
    """Run inline quality validation for a phase.

    Runs the deterministic quality judge for the given phase immediately
    after the phase completes. ERROR-severity issues cause pipeline failure.

    Args:
        phase: Phase name (crawl, extract, discover, synthesize, baseline, export)
        ein: Charity EIN
        output: The phase output data to validate
        context: Source data context for validation

    Returns:
        (passed, issues) - passed is False if any ERROR-severity issues found
    """
    judge_class = PHASE_QUALITY_JUDGES.get(phase)
    if not judge_class:
        return True, []  # No judge for this phase

    try:
        judge = judge_class(_inline_judge_config)
        verdict = judge.validate(output, context)

        # Serialize issues for result tracking
        issues = []
        for issue in verdict.issues:
            issues.append(
                {
                    "judge": verdict.judge_name,
                    "severity": issue.severity.value,
                    "field": issue.field,
                    "message": issue.message,
                }
            )

        # Check for ERROR severity - these are hard failures
        has_errors = any(i.severity == Severity.ERROR for i in verdict.issues)

        return not has_errors, issues

    except Exception as e:
        # Judge execution failures are hard failures for strict data guarantees.
        return False, [
            {
                "judge": f"{phase}_quality",
                "severity": "error",
                "field": "judge_execution",
                "message": f"Quality judge failed: {str(e)[:100]}",
            }
        ]


def lookup_charity_by_ein(ein: str) -> dict | None:
    """Look up a charity from the database by EIN.

    Returns dict with name, ein, website or None if not found.
    """
    from src.db.dolt_client import execute_query

    result = execute_query("SELECT name, ein, website FROM charities WHERE ein = %s", (ein,))
    if result:
        row = result[0]
        return {
            "name": row["name"],
            "ein": row["ein"],
            "website": row.get("website"),
        }
    return None


def sync_websites_to_db(charities: list[dict], logger: PipelineLogger) -> int:
    """Sync websites from charities list to the charities table.

    This ensures that websites defined in pilot_charities.txt are available
    in the database for discovery phase lookups.

    Returns:
        Number of charities updated
    """
    from src.db.dolt_client import execute_query

    updated = 0
    for charity in charities:
        website = normalize_website_url(charity.get("website"))
        ein = charity.get("ein")
        if website and ein:
            result = execute_query(
                """
                UPDATE charities
                SET website = %s
                WHERE ein = %s
                  AND (
                    website IS NULL
                    OR website = ''
                    OR (website NOT LIKE 'http://%%' AND website NOT LIKE 'https://%%')
                  )
                """,
                (website, ein),
            )
            if result is not None:
                updated += 1

    if updated > 0:
        logger.info(f"Synced {updated} websites from charities file to database")

    return updated


def clean_charity_data(ein: str, logger: PipelineLogger) -> dict:
    """Delete all pipeline data for a charity (for fresh reprocessing).

    Deletes from: raw_scraped_data, charity_data, evaluations, citations
    Does NOT delete from: charities (keeps basic info)

    Returns:
        Dict with counts of deleted rows per table
    """
    from src.db.dolt_client import execute_query

    tables = [
        ("raw_scraped_data", "charity_ein"),
        ("charity_data", "charity_ein"),
        ("evaluations", "charity_ein"),
        ("citations", "charity_ein"),
        ("phase_cache", "charity_ein"),
    ]

    deleted = {}
    for table, ein_col in tables:
        try:
            # Get count first
            result = execute_query(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE {ein_col} = %s",
                (ein,),
                fetch="one",
            )
            count = result["cnt"] if result else 0

            if count > 0:
                execute_query(
                    f"DELETE FROM {table} WHERE {ein_col} = %s",
                    (ein,),
                    fetch="none",
                )
                deleted[table] = count
                logger.info(f"Deleted {count} rows from {table} for {ein}")
        except Exception as e:
            logger.warning(f"Could not clean {table} for {ein}: {e}")

    return deleted


# ========== SMART CACHING HELPERS ==========


def should_run_phase(
    ein: str,
    phase: str,
    cache_repo: PhaseCacheRepository,
    force_all: bool = False,
    force_phases: list[str] | None = None,
    upstream_ran: set[str] | None = None,
) -> tuple[bool, str]:
    """Determine if a phase should run or can be skipped.

    Uses shared check_phase_cache for fingerprint+TTL checks, plus
    streaming-runner-specific logic for force flags and in-memory cascade.

    Args:
        ein: Charity EIN
        phase: Phase name
        cache_repo: Phase cache repository
        force_all: If True, always run
        force_phases: List of phases to force rerun
        upstream_ran: Set of upstream phases that ran (triggers cascade)

    Returns:
        Tuple of (should_run, reason)
    """
    # Force flags take precedence
    if force_all:
        return True, "Force all"
    if force_phases and phase in force_phases:
        return True, f"Force phase: {phase}"

    # Cascade invalidation: if any upstream phase ran in this session, we must run too
    if upstream_ran:
        from src.utils.phase_fingerprint import PHASE_DEPENDENCIES

        for dep in PHASE_DEPENDENCIES.get(phase, []):
            if dep in upstream_ran:
                return True, f"Upstream {dep} ran"

    # Delegate fingerprint + TTL check to shared helper
    return check_phase_cache(ein, phase, cache_repo)


def print_cache_status(
    charities: list[dict],
    cache_repo: PhaseCacheRepository,
    force_phases: list[str] | None = None,
) -> None:
    """Print cache status for charities and exit.

    Shows what would run without running, including cascade invalidation
    (upstream phase running forces downstream phases to run too).
    """
    from src.utils.phase_fingerprint import PHASE_DEPENDENCIES

    phases = ["crawl", "extract", "discover", "synthesize", "baseline", "rich", "judge"]

    for charity in charities:
        ein = charity["ein"]
        name = charity["name"]
        print(f"\nCache status for {ein} ({name[:40]}):")

        would_run: set[str] = set()

        for phase in phases:
            current_fp = get_phase_fingerprint(phase)
            ttl_days = get_ttl_days(phase)
            is_valid, reason = cache_repo.is_valid(ein, phase, current_fp, ttl_days)

            cache_entry = cache_repo.get(ein, phase)

            # Check cascade: if any upstream phase would run, this one must too
            cascade_dep = None
            for dep in PHASE_DEPENDENCIES.get(phase, []):
                if dep in would_run:
                    cascade_dep = dep
                    break

            if force_phases and phase in force_phases:
                status = "FORCE"
                detail = "User requested"
                would_run.add(phase)
            elif cascade_dep:
                status = "RUN"
                detail = f"Upstream {cascade_dep} ran"
                would_run.add(phase)
            elif is_valid:
                status = "SKIP"
                if cache_entry:
                    ran_at = cache_entry.get("ran_at")
                    if ran_at:
                        age_days = (datetime.now() - ran_at).days
                        if ttl_days == float("inf"):
                            detail = "code unchanged"
                        else:
                            detail = f"code unchanged, {age_days}d old < {int(ttl_days)}d TTL"
                    else:
                        detail = "code unchanged"
                else:
                    detail = "code unchanged"
            else:
                status = "RUN"
                detail = reason
                would_run.add(phase)

            print(f"  {phase:12} {status:5}  ({detail})")

    print()


def extract_raw_data(ein: str, collectors: dict, logger: PipelineLogger, force: bool = False) -> tuple[int, int]:
    """Phase 2: Parse raw_html into parsed_json for all sources.

    Delegates per-row parsing to extract.extract_row() to keep logic in one place.

    Args:
        ein: The EIN to extract
        collectors: Dict of source -> collector instances
        logger: Pipeline logger
        force: If True, re-parse all rows (not just unparsed). Use when extract
               code has changed and we need to re-run extraction.

    Returns:
        (success_count, fail_count)
    """
    repo = RawDataRepository()
    if force:
        rows = repo.get_all(eins=[ein])
    else:
        rows = repo.get_unparsed(eins=[ein])

    success = 0
    failed = 0

    for row in rows:
        ok, error = extract_row(row, collectors, logger, repo)
        if ok:
            success += 1
        elif error and "Website uses combined mode" not in error:
            failed += 1

    return success, failed


def run_discovery_phase(
    ein: str,
    name: str,
    website: str,
    raw_repo: RawDataRepository,
    logger: PipelineLogger,
) -> dict:
    """Run all discovery services in parallel and store results.

    Discovery uses Google search grounding to find:
    - Zakat eligibility verification
    - Third-party evaluations (GiveWell, J-PAL, etc.)
    - Outcome/impact metrics
    - Theory of change
    - Awards and recognition

    Returns:
        dict with success, cost_usd, and discovered data
    """
    import concurrent.futures
    from datetime import datetime

    result = {
        "success": False,
        "cost_usd": 0.0,
        "queries_run": 0,
        "queries_succeeded": 0,
        "skipped": False,
    }

    if not DISCOVERY_ENABLED:
        result["skipped"] = True
        result["skip_reason"] = "Discovery disabled"
        return result

    # If input website is missing, fall back to the crawled website_profile URL.
    if not website:
        website_row = raw_repo.get_by_source(ein, "website")
        parsed = website_row.get("parsed_json") if website_row else None
        if isinstance(parsed, dict):
            website_profile = parsed.get("website_profile", parsed)
            candidate = website_profile.get("url") if isinstance(website_profile, dict) else None
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                website = candidate

    if not website:
        logger.warning(f"No website for {ein}, skipping discovery")
        result["skipped"] = True
        result["skip_reason"] = "No website"
        return result

    # Initialize services
    zakat_svc = ZakatVerificationService()
    evidence_svc = EvidenceDiscoveryService()
    outcome_svc = OutcomeDiscoveryService()
    toc_svc = TheoryOfChangeDiscoveryService()
    awards_svc = AwardsDiscoveryService()

    discovered_profile = {
        "ein": ein,
        "charity_name": name,
        "website_url": website,
        # D-006: Use UTC for consistent timestamps across timezones
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        SECTION_ZAKAT: None,
        SECTION_EVALUATIONS: None,
        SECTION_OUTCOMES: None,
        SECTION_THEORY_OF_CHANGE: None,
        SECTION_AWARDS: None,
    }

    total_cost = 0.0
    queries_succeeded = 0
    # FIX #7: Differentiate required vs optional discovery services.
    # Required services failing → hard fail. Optional → warn and continue.
    required_sections = {SECTION_ZAKAT, SECTION_EVALUATIONS, SECTION_THEORY_OF_CHANGE}
    required_errors = []
    optional_errors = []

    # Run discovery services in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(zakat_svc.verify, name, website): SECTION_ZAKAT,
            executor.submit(evidence_svc.discover, name, website): SECTION_EVALUATIONS,
            executor.submit(outcome_svc.discover, name, website): SECTION_OUTCOMES,
            executor.submit(toc_svc.discover, name, website): SECTION_THEORY_OF_CHANGE,
            executor.submit(awards_svc.discover, name, website): SECTION_AWARDS,
        }

        for future in concurrent.futures.as_completed(futures):
            service_name = futures[future]
            is_required = service_name in required_sections
            try:
                svc_result = future.result()
                if svc_result:
                    # Check for JSON parsing errors (hard failures)
                    error = getattr(svc_result, "error", None)
                    if error:
                        error_msg = f"{service_name}: {error}"
                        if is_required:
                            required_errors.append(error_msg)
                            logger.error(f"Discovery {service_name} (required) JSON parse failed for {ein}: {error}")
                        else:
                            optional_errors.append(error_msg)
                            logger.warning(f"Discovery {service_name} (optional) JSON parse failed for {ein}: {error}")
                    else:
                        discovered_profile[service_name] = svc_result.to_dict()
                        queries_succeeded += 1
                    total_cost += getattr(svc_result, "cost_usd", 0.0)
            except Exception as e:
                error_msg = f"{service_name}: {e}"
                if is_required:
                    required_errors.append(error_msg)
                    logger.error(f"Discovery {service_name} (required) failed for {ein}: {e}")
                else:
                    optional_errors.append(error_msg)
                    logger.warning(f"Discovery {service_name} (optional) failed for {ein}: {e}")

    # Hard fail only on required service errors
    if required_errors:
        result["success"] = False
        result["error"] = f"Required discovery failures: {'; '.join(required_errors)}"
        result["cost_usd"] = total_cost
        result["queries_run"] = 5
        result["queries_succeeded"] = queries_succeeded
        return result

    # Log optional failures but continue
    if optional_errors:
        logger.warning(f"Optional discovery failures for {ein} (continuing): {'; '.join(optional_errors)}")

    # Store in raw_scraped_data with source="discovered"
    if queries_succeeded > 0:
        raw_repo.upsert(
            charity_ein=ein,
            source="discovered",
            parsed_json={"discovered_profile": discovered_profile},
            success=True,
        )
        result["success"] = True
    else:
        # Valid run, but no discoveries to persist. Do not cache this phase.
        result["success"] = True
        result["skipped"] = True
        result["skip_reason"] = "No discoveries found"

    result["cost_usd"] = total_cost
    result["queries_run"] = 5
    result["queries_succeeded"] = queries_succeeded

    return result


def process_charity_full(
    charity: dict,
    index: int,
    total: int,
    orchestrator: DataCollectionOrchestrator,
    collectors: dict,
    charity_repo: CharityRepository,
    raw_repo: RawDataRepository,
    data_repo: CharityDataRepository,
    eval_repo: EvaluationRepository,
    cache_repo: PhaseCacheRepository,
    llm_client: LLMClient,
    scorer: AmalScorerV2,
    logger: PipelineLogger,
    verbose: bool = False,
    skip_export: bool = False,
    judge_threshold: int = 80,
    output_dir: Path | None = None,
    ui_signals_config: dict | None = None,
    config_hash: str = "",
    pilot_flags: dict | None = None,
    force_all: bool = False,
    force_phases: list[str] | None = None,
) -> dict:
    """Process a single charity through all 7 phases end-to-end.

    Phases:
    1. Crawl: Fetch raw data from all sources
    2. Extract: Parse raw_html into parsed_json
    3. Synthesize: Compute derived fields
    4. Baseline: Generate AMAL score and baseline narrative
    5. Rich: Generate rich investment memo narrative
    6. Judge: Validate evaluation quality
    7. Export: Export to website JSON (if judge_score >= threshold)

    Note: Discover phase runs in parallel with Extract (both are Phase 2).
    """
    ein = charity["ein"]
    name = charity["name"]
    website = charity["website"]

    result = {
        "ein": ein,
        "name": name,
        "phases": {},
        "costs": {
            "crawl": 0.0,
            "extract": 0.0,
            "discover": 0.0,
            "synthesize": 0.0,
            "baseline": 0.0,
            "rich": 0.0,
            "judge": 0.0,
        },
        "total_cost": 0.0,
        "success": False,
        "cache_skips": [],  # Phases skipped due to smart cache
    }

    # Track which phases actually ran (for cascade invalidation)
    phases_ran: set[str] = set()

    try:
        # ========== PHASE 1: CRAWL ==========
        run_crawl, crawl_reason = should_run_phase(ein, "crawl", cache_repo, force_all, force_phases, phases_ran)

        if not run_crawl:
            # Cache hit - skip crawl
            result["phases"]["crawl"] = {
                "success": True,
                "skipped": True,
                "reason": crawl_reason,
                "cost": 0.0,
            }
            result["cache_skips"].append("crawl")
        else:
            phase_start = time.time()
            success, report = orchestrator.fetch_charity_data(ein=ein, website_url=website, charity_name=name)

            if not success:
                result["phases"]["crawl"] = {"success": False, "error": "Fetch failed"}
                with print_lock:
                    print(f"[{index}/{total}] ✗ {name[:40]} - Crawl failed")
                return result

            sources_ok = len(report.get("sources_succeeded", []))
            # Extract LLM cost from website collector (nested in raw_data.website.crawl_stats.llm_cost)
            website_data = report.get("raw_data", {}).get("website", {})
            crawl_stats = website_data.get("crawl_stats", {})
            crawl_cost = crawl_stats.get("llm_cost", 0.0) or 0.0
            crawl_timing = crawl_stats.get("timing", {})
            result["costs"]["crawl"] = crawl_cost
            result["phases"]["crawl"] = {
                "success": True,
                "sources": sources_ok,
                "time": round(time.time() - phase_start, 1),
                "cost": crawl_cost,
                "timing": crawl_timing,
            }
            phases_ran.add("crawl")
            # Update cache
            update_phase_cache(ein, "crawl", cache_repo, crawl_cost)

            # Inline quality check for crawl
            raw_data_for_check = raw_repo.get_for_charity(ein)
            source_data = {rd["source"]: (rd.get("parsed_json") or {}) for rd in raw_data_for_check if rd.get("success")}
            crawl_passed, crawl_issues = run_inline_quality_check(
                "crawl", ein, {"ein": ein}, {"source_data": source_data}
            )
            if crawl_issues:
                result["phases"]["crawl"]["quality_issues"] = crawl_issues
            if not crawl_passed:
                result["phases"]["crawl"]["success"] = False
                result["phases"]["crawl"]["error"] = "Quality check failed"
                cache_repo.delete(ein, "crawl")
                with print_lock:
                    print(f"[{index}/{total}] ✗ {name[:40]} - Crawl quality check failed")
                return result

        # ========== PHASE 2a: EXTRACT ==========
        run_extract, extract_reason = should_run_phase(ein, "extract", cache_repo, force_all, force_phases, phases_ran)

        if not run_extract:
            result["phases"]["extract"] = {
                "success": True,
                "skipped": True,
                "reason": extract_reason,
                "cost": 0.0,
            }
            result["cache_skips"].append("extract")
        else:
            phase_start = time.time()
            # Pass force=True to re-parse all rows (code changed or explicit --force-phase)
            extract_ok, extract_fail = extract_raw_data(ein, collectors, logger, force=True)
            if extract_fail > 0:
                result["phases"]["extract"] = {
                    "success": False,
                    "parsed": extract_ok,
                    "failed": extract_fail,
                    "time": round(time.time() - phase_start, 1),
                    "cost": 0.0,
                    "error": f"Extract failed for {extract_fail} source rows",
                }
                with print_lock:
                    print(f"[{index}/{total}] ✗ {name[:40]} - Extract failed ({extract_fail} rows)")
                return result
            result["phases"]["extract"] = {
                "success": True,
                "parsed": extract_ok,
                "failed": extract_fail,
                "time": round(time.time() - phase_start, 1),
                "cost": 0.0,
            }
            phases_ran.add("extract")
            update_phase_cache(ein, "extract", cache_repo, 0.0)

            # Inline quality check for extract
            raw_data_for_check = raw_repo.get_for_charity(ein)
            extract_output = {"ein": ein, "parsed_sources": {}}
            for rd in raw_data_for_check:
                if rd.get("parsed_json"):
                    extract_output["parsed_sources"][rd["source"]] = rd["parsed_json"]
            extract_passed, extract_issues = run_inline_quality_check(
                "extract", ein, extract_output, {"source_data": extract_output["parsed_sources"]}
            )
            if extract_issues:
                result["phases"]["extract"]["quality_issues"] = extract_issues
            if not extract_passed:
                result["phases"]["extract"]["success"] = False
                result["phases"]["extract"]["error"] = "Quality check failed"
                cache_repo.delete(ein, "extract")
                with print_lock:
                    print(f"[{index}/{total}] ✗ {name[:40]} - Extract quality check failed")
                return result

        # ========== PHASE 2b: DISCOVER ==========
        run_discover, discover_reason = should_run_phase(
            ein, "discover", cache_repo, force_all, force_phases, phases_ran
        )

        if not run_discover:
            result["phases"]["discover"] = {
                "success": True,
                "skipped": True,
                "reason": discover_reason,
                "cost": 0.0,
            }
            result["cache_skips"].append("discover")
        else:
            phase_start = time.time()
            discover_result = run_discovery_phase(ein, name, website, raw_repo, logger)
            discover_cost = discover_result.get("cost_usd", 0.0)
            result["costs"]["discover"] = discover_cost
            if discover_result.get("skipped"):
                skip_cost = discover_cost if discover_result.get("queries_run", 0) > 0 else 0.0
                result["phases"]["discover"] = {
                    "success": True,
                    "skipped": True,
                    "reason": discover_result.get("skip_reason", "Unknown"),
                    "time": round(time.time() - phase_start, 1),
                    "cost": skip_cost,
                }
                # No-op discovery outcomes (e.g., no discoveries/no website) must not be cached.
                cache_repo.delete(ein, "discover")
            else:
                # Check for discovery errors (JSON parse failures are hard errors)
                discover_error = discover_result.get("error")
                if discover_error:
                    result["phases"]["discover"] = {
                        "success": False,
                        "error": discover_error,
                        "queries_run": discover_result.get("queries_run", 0),
                        "queries_succeeded": discover_result.get("queries_succeeded", 0),
                        "time": round(time.time() - phase_start, 1),
                        "cost": discover_cost,
                    }
                    with print_lock:
                        print(f"[{index}/{total}] ✗ {name[:40]} - Discover failed: JSON parse error")
                    return result

                if not discover_result.get("success"):
                    result["phases"]["discover"] = {
                        "success": False,
                        "error": "Discovery did not produce a successful result",
                        "queries_run": discover_result.get("queries_run", 0),
                        "queries_succeeded": discover_result.get("queries_succeeded", 0),
                        "time": round(time.time() - phase_start, 1),
                        "cost": discover_cost,
                    }
                    with print_lock:
                        print(f"[{index}/{total}] ✗ {name[:40]} - Discover failed")
                    return result

                result["phases"]["discover"] = {
                    "success": True,
                    "queries_run": discover_result.get("queries_run", 0),
                    "queries_succeeded": discover_result.get("queries_succeeded", 0),
                    "time": round(time.time() - phase_start, 1),
                    "cost": discover_cost,
                }
                phases_ran.add("discover")
                update_phase_cache(ein, "discover", cache_repo, discover_cost)

                # Inline quality check for discover
                charity_data = data_repo.get(ein) or {}
                # Build source_data from raw_repo for discovered profile
                discover_raw = raw_repo.get_for_charity(ein)
                discover_source_data = {
                    rd["source"]: rd.get("parsed_json", {})
                    for rd in discover_raw
                    if rd.get("success") and rd.get("parsed_json")
                }
                discover_passed, discover_issues = run_inline_quality_check(
                    "discover", ein, {"ein": ein, "charity_data": charity_data}, {"source_data": discover_source_data}
                )
                if discover_issues:
                    result["phases"]["discover"]["quality_issues"] = discover_issues
                if not discover_passed:
                    result["phases"]["discover"]["success"] = False
                    result["phases"]["discover"]["error"] = "Quality check failed"
                    cache_repo.delete(ein, "discover")
                    with print_lock:
                        print(f"[{index}/{total}] ✗ {name[:40]} - Discover quality check failed")
                    return result

        # ========== PHASE 3: SYNTHESIZE ==========
        run_synth, synth_reason = should_run_phase(ein, "synthesize", cache_repo, force_all, force_phases, phases_ran)

        if not run_synth:
            result["phases"]["synthesize"] = {
                "success": True,
                "skipped": True,
                "reason": synth_reason,
                "cost": 0.0,
            }
            result["cache_skips"].append("synthesize")
        else:
            phase_start = time.time()
            synth_result = synthesize_charity(ein, raw_repo, charity_repo)
            synth_cost = synth_result.get("cost_usd", 0.0)
            result["costs"]["synthesize"] = synth_cost

            if not synth_result.get("success"):
                result["phases"]["synthesize"] = {
                    "success": False,
                    "error": synth_result.get("error", "Unknown"),
                    "cost": synth_cost,
                }
                result["success"] = False
                with print_lock:
                    print(f"[{index}/{total}] ✗ {name[:40]} - Synthesize failed")
                return result
            else:
                # Save synthesized data to database
                data_repo.upsert(synth_result["synthesized"])
                result["phases"]["synthesize"] = {
                    "success": True,
                    "time": round(time.time() - phase_start, 1),
                    "cost": synth_cost,
                }
                phases_ran.add("synthesize")
                update_phase_cache(ein, "synthesize", cache_repo, synth_cost)

                # Inline quality check for synthesize
                synth_data = data_repo.get(ein) or {}
                raw_data_for_check = raw_repo.get_for_charity(ein)
                source_data = {
                    rd["source"]: (rd.get("parsed_json") or {}) for rd in raw_data_for_check if rd.get("success")
                }
                synth_passed, synth_issues = run_inline_quality_check(
                    "synthesize", ein, {"ein": ein, "charity_data": synth_data}, {"source_data": source_data}
                )
                if synth_issues:
                    result["phases"]["synthesize"]["quality_issues"] = synth_issues
                if not synth_passed:
                    result["phases"]["synthesize"]["success"] = False
                    result["phases"]["synthesize"]["error"] = "Quality check failed"
                    cache_repo.delete(ein, "synthesize")
                    with print_lock:
                        print(f"[{index}/{total}] ✗ {name[:40]} - Synthesize quality check failed")
                    return result

        # ========== PHASE 4: BASELINE ==========
        run_baseline, baseline_reason = should_run_phase(
            ein, "baseline", cache_repo, force_all, force_phases, phases_ran
        )

        if not run_baseline:
            # Cache hit - get existing evaluation for result
            existing_eval = eval_repo.get(ein)
            amal_score = existing_eval.get("amal_score") if existing_eval else None
            result["phases"]["baseline"] = {
                "success": True,
                "skipped": True,
                "reason": baseline_reason,
                "amal_score": amal_score,
                "cost": 0.0,
            }
            result["cache_skips"].append("baseline")
            result["success"] = True
            result["amal_score"] = amal_score
        else:
            phase_start = time.time()
            eval_result = evaluate_charity(ein, charity_repo, raw_repo, data_repo, llm_client, scorer)
            baseline_cost = eval_result.get("cost_usd", 0.0)
            result["costs"]["baseline"] = baseline_cost

            if eval_result.get("success"):
                scores = eval_result.get("scores")
                amal_score = scores.amal_score if scores else None
                strategic_scores = eval_result.get("strategic_scores")
                zakat_scores = eval_result.get("zakat_scores")
                # Save evaluation to database
                eval_repo.upsert(eval_result["evaluation"])
                result["phases"]["baseline"] = {
                    "success": True,
                    "amal_score": amal_score,
                    "strategic_score": strategic_scores.strategic_score if strategic_scores else None,
                    "zakat_score": zakat_scores.zakat_score if zakat_scores else None,
                    "time": round(time.time() - phase_start, 1),
                    "cost": baseline_cost,
                }
                result["success"] = True
                result["amal_score"] = amal_score
                result["strategic_score"] = strategic_scores.strategic_score if strategic_scores else None
                result["zakat_score"] = zakat_scores.zakat_score if zakat_scores else None
                phases_ran.add("baseline")
                update_phase_cache(ein, "baseline", cache_repo, baseline_cost)

                # Inline quality check for baseline
                evaluation = eval_repo.get(ein) or {}
                charity_data = data_repo.get(ein) or {}
                baseline_passed, baseline_issues = run_inline_quality_check(
                    "baseline", ein, {"ein": ein, "evaluation": evaluation}, {"charity_data": charity_data}
                )
                if baseline_issues:
                    result["phases"]["baseline"]["quality_issues"] = baseline_issues
                if not baseline_passed:
                    result["phases"]["baseline"]["success"] = False
                    result["phases"]["baseline"]["error"] = "Quality check failed"
                    result["success"] = False
                    cache_repo.delete(ein, "baseline")
                    with print_lock:
                        print(f"[{index}/{total}] ✗ {name[:40]} - Baseline quality check failed")
                    return result
            else:
                result["phases"]["baseline"] = {
                    "success": False,
                    "error": eval_result.get("error", "Unknown"),
                    "cost": baseline_cost,
                }

        # ========== PHASE 5: RICH NARRATIVE ==========
        run_rich, rich_reason = should_run_phase(ein, "rich", cache_repo, force_all, force_phases, phases_ran)

        if not run_rich:
            result["phases"]["rich"] = {
                "success": True,
                "skipped": True,
                "reason": rich_reason,
                "cost": 0.0,
            }
            result["cache_skips"].append("rich")
        elif result.get("success"):
            # Only generate rich if baseline succeeded
            phase_start = time.time()
            rich_force = force_all or ("rich" in (force_phases or []))
            rich_result = generate_rich_for_pipeline(ein, eval_repo, force=rich_force)
            rich_cost = rich_result.get("cost_usd", 0.0)
            result["costs"]["rich"] = rich_cost

            if rich_result.get("success"):
                if rich_result.get("skipped"):
                    result["phases"]["rich"] = {
                        "success": True,
                        "skipped": True,
                        "reason": rich_result.get("reason", "Already has rich narrative"),
                        "cost": 0.0,
                    }
                else:
                    result["phases"]["rich"] = {
                        "success": True,
                        "citations_count": rich_result.get("citations_count", 0),
                        "time": round(time.time() - phase_start, 1),
                        "cost": rich_cost,
                    }
                    phases_ran.add("rich")
                    update_phase_cache(ein, "rich", cache_repo, rich_cost)
            else:
                result["phases"]["rich"] = {
                    "success": False,
                    "error": rich_result.get("error", "Unknown"),
                    "cost": rich_cost,
                }
                result["success"] = False
                cache_repo.delete(ein, "rich")
                with print_lock:
                    print(f"[{index}/{total}] ✗ {name[:40]} - Rich failed: {rich_result.get('error', 'Unknown')[:50]}")
                return result

            # Inline quality check for rich (runs after success or skip-with-existing)
            if result["phases"].get("rich", {}).get("success") and not result["phases"]["rich"].get("skipped"):
                rich_eval = eval_repo.get(ein) or {}
                rich_passed, rich_issues = run_inline_quality_check(
                    "rich", ein, {"ein": ein, "evaluation": rich_eval}, {}
                )
                if rich_issues:
                    result["phases"]["rich"]["quality_issues"] = rich_issues
                if not rich_passed:
                    result["phases"]["rich"]["success"] = False
                    result["phases"]["rich"]["error"] = "Quality check failed"
                    cache_repo.delete(ein, "rich")
                    with print_lock:
                        print(f"[{index}/{total}] ✗ {name[:40]} - Rich quality check failed")
                    return result

        # ========== PHASE 6: JUDGE ==========
        run_judge, judge_reason = should_run_phase(ein, "judge", cache_repo, force_all, force_phases, phases_ran)

        if not run_judge:
            existing_eval = eval_repo.get(ein)
            result["phases"]["judge"] = {
                "success": True,
                "skipped": True,
                "reason": judge_reason,
                "judge_score": existing_eval.get("judge_score") if existing_eval else None,
                "cost": 0.0,
            }
            result["cache_skips"].append("judge")
        elif result.get("success"):
            # Only judge if baseline succeeded
            phase_start = time.time()
            # J-001: Removed unused llm_client parameter
            judge_result = judge_charity(ein, eval_repo, data_repo, raw_repo, charity_repo)
            judge_cost = judge_result.get("cost_usd", 0.0)
            result["costs"]["judge"] = judge_cost

            if judge_result.get("success"):
                # Store judge results in database
                eval_repo.update_judge_result(ein, judge_result["judge_score"], judge_result.get("issues", []))
                result["phases"]["judge"] = {
                    "success": True,
                    "judge_score": judge_result["judge_score"],
                    "issues_count": len(judge_result.get("issues", [])),
                    "time": round(time.time() - phase_start, 1),
                    "cost": judge_cost,
                }
                result["judge_score"] = judge_result["judge_score"]
                phases_ran.add("judge")
                update_phase_cache(ein, "judge", cache_repo, judge_cost)
            else:
                result["phases"]["judge"] = {
                    "success": False,
                    "error": judge_result.get("error", "Unknown"),
                    "cost": judge_cost,
                }
                result["success"] = False
                with print_lock:
                    print(
                        f"[{index}/{total}] ✗ {name[:40]} - Judge failed: {judge_result.get('error', 'Unknown')[:50]}"
                    )
                return result

        # ========== PHASE 7: EXPORT ==========
        # Export to website JSON if judge score passes threshold
        if skip_export:
            result["phases"]["export"] = {
                "success": True,
                "skipped": True,
                "reason": "Export disabled (--skip-export)",
            }
        elif not result.get("success"):
            result["phases"]["export"] = {
                "success": False,
                "skipped": True,
                "reason": "Baseline failed - nothing to export",
            }
        else:
            # Get judge score (from result or re-fetch from DB)
            judge_score = result.get("judge_score")
            if judge_score is None:
                existing_eval = eval_repo.get(ein)
                judge_score = existing_eval.get("judge_score") if existing_eval else None

            if judge_threshold > 0 and (judge_score is None or judge_score < judge_threshold):
                result["phases"]["export"] = {
                    "success": True,
                    "skipped": True,
                    "reason": f"Judge score {judge_score} < threshold {judge_threshold}",
                }
            else:
                # Export the charity
                phase_start = time.time()
                export_dir = output_dir or WEBSITE_DATA_DIR
                flags = pilot_flags.get(ein) if pilot_flags else None
                export_result = export_charity(
                    ein,
                    charity_repo,
                    raw_repo,
                    data_repo,
                    eval_repo,
                    export_dir,
                    ui_signals_config=ui_signals_config or {},
                    config_hash=config_hash,
                    hide_from_curated=flags.hide_from_curated if flags else False,
                    pilot_name=flags.name if flags else None,
                )
                if export_result.get("success"):
                    result["phases"]["export"] = {
                        "success": True,
                        "tier": export_result.get("tier"),
                        "time": round(time.time() - phase_start, 1),
                    }
                    result["exported"] = True

                    # Inline quality check for export
                    export_summary = export_result.get("summary", {})
                    export_passed, export_issues = run_inline_quality_check("export", ein, export_summary, {})
                    if export_issues:
                        result["phases"]["export"]["quality_issues"] = export_issues
                    if not export_passed:
                        result["phases"]["export"]["success"] = False
                        result["phases"]["export"]["error"] = "Quality check failed"
                        result["success"] = False
                        result["error"] = "Export quality check failed"
                        result["exported"] = False
                        with print_lock:
                            print(f"[{index}/{total}] ✗ {name[:40]} - Export quality check failed")
                else:
                    result["phases"]["export"] = {
                        "success": False,
                        "error": export_result.get("error", "Unknown"),
                    }
                    result["success"] = False

        # Calculate total cost
        result["total_cost"] = sum(result["costs"].values())

        # Persist cost to database
        if result["total_cost"] > 0:
            eval_repo.update_llm_cost(ein, result["total_cost"])

        # Print progress
        with progress_lock:
            if result["success"]:
                progress["completed"] += 1
            else:
                progress["failed"] += 1

        amal = result.get("amal_score", "N/A")
        strat = result.get("strategic_score")
        zkt = result.get("zakat_score")
        lens_str = f" S:{strat} Z:{zkt}" if strat is not None else ""
        score_str = f"A:{amal}{lens_str}" if result["success"] else "FAILED"
        cost_str = f"${result['total_cost']:.4f}"
        # Show cache skips if any
        cache_skips = result.get("cache_skips", [])
        cache_str = f" [cache:{','.join(cache_skips)}]" if cache_skips else ""
        with print_lock:
            status = "✓" if result["success"] else "✗"
            print(f"[{index}/{total}] {status} {name[:40]} - {score_str} ({cost_str}){cache_str}")

        return result

    except Exception as e:
        logger.error(f"Pipeline failed for {ein}", exception=e)
        with print_lock:
            print(f"[{index}/{total}] ✗ {name[:40]} - Error: {str(e)[:50]}")
        result["error"] = str(e)
        with progress_lock:
            progress["failed"] += 1
        return result


def main():
    parser = argparse.ArgumentParser(description="Streaming pipeline - process charities end-to-end")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--charities", type=str, help="Path to charity list file")
    group.add_argument("--ein", type=str, help="Single charity EIN")
    parser.add_argument("--workers", type=int, default=20, help="Number of parallel workers (default: 20)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--clean", action="store_true", help="Delete existing data before processing (fresh start)")
    parser.add_argument("--model", type=str, help="Override LLM model (e.g., gpt-5.2, claude-sonnet-4-5)")
    parser.add_argument("--tag", type=str, metavar="NAME", help="Custom tag name (default: auto-generated timestamp)")
    parser.add_argument("--no-tag", action="store_true", help="Skip tagging this run")
    parser.add_argument(
        "--judge-threshold", type=int, default=80, help="Min judge score to export (default: 80, 0=export all)"
    )
    parser.add_argument("--skip-export", action="store_true", help="Skip export phase")
    # Smart caching options (ON by default)
    parser.add_argument("--force-all", action="store_true", help="Ignore cache, rerun all phases")
    parser.add_argument(
        "--force-phase",
        type=str,
        action="append",
        help="Force specific phase(s) to rerun (e.g., --force-phase baseline)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without running")
    parser.add_argument("--cache-status", action="store_true", help="Show cache status for charity(ies) and exit")
    parser.add_argument(
        "--checkpoint",
        type=int,
        default=0,
        metavar="N",
        help="Commit to DoltDB every N completed charities (default: 0 = only at end)",
    )

    args = parser.parse_args()

    # Check environment
    required_vars = ["GOOGLE_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Initialize logger
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = PipelineLogger("streaming", log_level=log_level, phase="FullPipeline")

    # Load charities
    if args.ein:
        is_valid, normalized_ein, error = validate_and_format(args.ein)
        if not is_valid:
            print(f"Error: Invalid EIN '{args.ein}': {error}")
            sys.exit(1)
        # Look up charity from database to get name and website
        charity_info = lookup_charity_by_ein(normalized_ein)
        if charity_info:
            charities = [charity_info]
        else:
            # Fallback: charity not in DB yet, will be fetched during crawl
            charities = [{"name": args.ein, "ein": normalized_ein, "website": None}]

        # If website is missing from DB, check pilot_charities.txt
        if not charities[0].get("website"):
            pilot_file = Path(__file__).parent / "pilot_charities.txt"
            if pilot_file.exists():
                from src.utils.charity_loader import load_charity_entries

                for entry in load_charity_entries(str(pilot_file)):
                    if entry.ein == normalized_ein and entry.website:
                        charities[0]["website"] = entry.website
                        logger.info(f"Found website for {normalized_ein} in pilot_charities.txt: {entry.website}")
                        break
    else:
        charities = load_charities_from_file(args.charities, logger)

    if not charities:
        print("No charities to process.")
        sys.exit(0)

    # Normalize website URLs before any phase uses them.
    for charity in charities:
        charity["website"] = normalize_website_url(charity.get("website"))

    # Sync websites from charities file to database
    # This ensures discovery phase can find websites even when using --ein
    sync_websites_to_db(charities, logger)

    # Clean existing data if requested
    if args.clean:
        print(f"\n🧹 Cleaning existing data for {len(charities)} charities...")
        for charity in charities:
            deleted = clean_charity_data(charity["ein"], logger)
            if deleted:
                tables_str = ", ".join(f"{t}:{n}" for t, n in deleted.items())
                print(f"  Cleaned {charity['ein']}: {tables_str}")
        print()

    # Initialize shared resources
    orchestrator = DataCollectionOrchestrator(
        logger=logger,
        max_pdf_downloads=5,
    )

    collectors = {}
    for source, cls in COLLECTORS.items():
        if source == "website":
            collectors[source] = cls(logger=logger, use_llm=False)
        else:
            collectors[source] = cls(logger=logger)

    charity_repo = CharityRepository()
    raw_repo = RawDataRepository()
    data_repo = CharityDataRepository()
    eval_repo = EvaluationRepository()
    cache_repo = PhaseCacheRepository()
    llm_client = LLMClient(model=args.model, logger=logger)
    scorer = AmalScorerV2()

    # Handle --cache-status: show cache status and exit
    if args.cache_status:
        print_cache_status(charities, cache_repo, args.force_phase)
        sys.exit(0)

    # Handle --dry-run: show what would run and exit
    if args.dry_run:
        print("\n🔍 DRY RUN - Showing what would run without running:\n")
        print_cache_status(charities, cache_repo, args.force_phase)
        sys.exit(0)

    # Set progress total
    progress["total"] = len(charities)

    ui_signals_config = load_ui_signals_config()
    config_hash = compute_ui_signals_config_hash(ui_signals_config)

    # Load pilot flags for export phase
    pilot_flags = {}
    default_pilot_file = Path(__file__).parent / "pilot_charities.txt"
    if default_pilot_file.exists():
        pilot_flags.update(load_pilot_charities(str(default_pilot_file)))
    if args.charities and Path(args.charities).exists():
        # Overlay explicit run file on top of defaults.
        pilot_flags.update(load_pilot_charities(args.charities))

    print("=" * 80)
    print(f"STREAMING PIPELINE: {len(charities)} charities × 7 phases")
    print(f"  Workers: {args.workers}")
    print(f"  Model: {llm_client.model_name}")
    print("  Mode: End-to-end (each charity completes fully)")
    # Smart caching info
    if args.force_all:
        cache_info = "OFF (--force-all)"
    elif args.force_phase:
        cache_info = f"ON (forcing: {', '.join(args.force_phase)})"
    else:
        cache_info = "ON (code fingerprint + TTL)"
    print(f"  Caching: {cache_info}")
    checkpoint_info = f"every {args.checkpoint} charities" if args.checkpoint > 0 else "at end only"
    print(f"  Checkpoints: {checkpoint_info}")
    export_info = "(disabled)" if args.skip_export else f"(threshold: {args.judge_threshold})"
    print(f"  Phases: Crawl → Extract → Discover → Synthesize → Baseline → Rich → Judge → Export {export_info}")
    print(f"  UI config: v{ui_signals_config.get('config_version', 'unknown')} ({config_hash[:20]}...)")
    print("=" * 80)

    start_time = time.time()
    results = []
    checkpoint_count = 0  # Number of checkpoint commits made
    since_last_checkpoint = 0  # Charities completed since last checkpoint

    # Process using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for i, charity in enumerate(charities, 1):
            future = executor.submit(
                process_charity_full,
                charity,
                i,
                len(charities),
                orchestrator,
                collectors,
                charity_repo,
                raw_repo,
                data_repo,
                eval_repo,
                cache_repo,
                llm_client,
                scorer,
                logger,
                args.verbose,
                args.skip_export,
                args.judge_threshold,
                WEBSITE_DATA_DIR,
                ui_signals_config,
                config_hash,
                pilot_flags,
                args.force_all,
                args.force_phase,
            )
            futures[future] = charity

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                charity = futures[future]
                logger.error(f"Worker exception for {charity['ein']}", exception=e)
                results.append(
                    {
                        "ein": charity["ein"],
                        "name": charity["name"],
                        "success": False,
                        "error": str(e),
                    }
                )

            # Checkpoint commit: snapshot progress every N charities
            since_last_checkpoint += 1
            if args.checkpoint > 0 and since_last_checkpoint >= args.checkpoint:
                completed = sum(1 for r in results if r.get("success"))
                failed = len(results) - completed
                commit_hash = dolt.commit(
                    f"Checkpoint {checkpoint_count + 1}: "
                    f"{completed} ok, {failed} failed, "
                    f"{len(charities) - len(results)} remaining"
                )
                if commit_hash:
                    checkpoint_count += 1
                    since_last_checkpoint = 0
                    with print_lock:
                        print(
                            f"  ⊟ Checkpoint {checkpoint_count} committed "
                            f"({len(results)}/{len(charities)} processed) [{commit_hash[:8]}]"
                        )

    # Cleanup
    orchestrator.close()

    elapsed = time.time() - start_time

    # Calculate cost totals
    total_cost = sum(r.get("total_cost", 0) for r in results)
    phase_costs = {
        "crawl": sum(r.get("costs", {}).get("crawl", 0) for r in results),
        "extract": sum(r.get("costs", {}).get("extract", 0) for r in results),
        "discover": sum(r.get("costs", {}).get("discover", 0) for r in results),
        "synthesize": sum(r.get("costs", {}).get("synthesize", 0) for r in results),
        "baseline": sum(r.get("costs", {}).get("baseline", 0) for r in results),
        "rich": sum(r.get("costs", {}).get("rich", 0) for r in results),
        "judge": sum(r.get("costs", {}).get("judge", 0) for r in results),
    }
    avg_cost = total_cost / len(results) if results else 0

    # Final commit to DoltDB (captures anything since last checkpoint)
    success_count = sum(1 for r in results if r.get("success"))
    if success_count > 0:
        checkpoint_note = f" ({checkpoint_count} checkpoints)" if checkpoint_count > 0 else ""
        commit_hash = dolt.commit(
            f"Streaming run: {success_count}/{len(results)} charities. "
            f"Cost: ${total_cost:.2f} (${avg_cost:.4f}/charity){checkpoint_note}"
        )
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")
        elif checkpoint_count > 0:
            print(f"\n✓ All changes captured in {checkpoint_count} checkpoint(s)")

        # Tag the run unless --no-tag specified
        # Use the final commit hash, or the latest HEAD if all changes were in checkpoints
        tag_ref = commit_hash or "HEAD"
        if not args.no_tag:
            # Generate tag name
            if args.tag:
                tag_name = args.tag
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
                tag_name = f"run-{timestamp}"

            # Build tag message with run metadata
            source = os.path.basename(args.charities) if args.charities else f"ein:{args.ein}"
            scores = [r.get("amal_score") for r in results if r.get("amal_score")]
            avg_score = sum(scores) / len(scores) if scores else 0

            tag_message = (
                f"Pipeline run: {success_count}/{len(results)} charities from {source}\n"
                f"Cost: ${total_cost:.2f} (${avg_cost:.4f}/charity) | Avg score: {avg_score:.1f}"
            )

            dolt.tag(tag_name, message=tag_message, ref=tag_ref)
            print(f"✓ Tagged: {tag_name}")

    comprehensive_export_count = 0
    comprehensive_export_eligible = 0
    comprehensive_export_failed = 0
    comprehensive_export_hard_failed = False

    # Rebuild exports from all currently exportable charities.
    # This keeps dataset additive/non-regressive across partial reruns.
    if not args.skip_export:
        all_charities = charity_repo.get_all()
        exportable_eins: list[str] = []
        for charity in all_charities:
            ein = charity.get("ein")
            if not ein:
                continue
            evaluation = eval_repo.get(ein)
            if not evaluation:
                continue
            judge_score = evaluation.get("judge_score")
            if args.judge_threshold > 0 and (judge_score is None or judge_score < args.judge_threshold):
                continue
            exportable_eins.append(ein)

        summaries = []
        rebuild_failures: list[tuple[str, str]] = []
        for ein in sorted(set(exportable_eins)):
            flags = pilot_flags.get(ein)
            export_result = export_charity(
                ein,
                charity_repo,
                raw_repo,
                data_repo,
                eval_repo,
                WEBSITE_DATA_DIR,
                ui_signals_config=ui_signals_config,
                config_hash=config_hash,
                hide_from_curated=flags.hide_from_curated if flags else False,
                pilot_name=flags.name if flags else None,
            )
            if not export_result.get("success"):
                rebuild_failures.append((ein, export_result.get("error", "Unknown export error")))
                continue

            export_summary = export_result.get("summary", {})
            export_passed, _ = run_inline_quality_check("export", ein, export_summary, {})
            if not export_passed:
                rebuild_failures.append((ein, "Export quality check failed"))
                continue

            summaries.append(export_summary)
        comprehensive_export_count = len(summaries)
        comprehensive_export_eligible = len(set(exportable_eins))
        comprehensive_export_failed = len(rebuild_failures)
        if rebuild_failures:
            comprehensive_export_hard_failed = True
            print(
                f"⛔ Comprehensive export failed: {len(rebuild_failures)} of {len(set(exportable_eins))} "
                "eligible charities could not be exported"
            )
            for failed_ein, err in rebuild_failures[:10]:
                print(f"    {failed_ein}: {err}")
            if len(rebuild_failures) > 10:
                print(f"    ... and {len(rebuild_failures) - 10} more")

        # Always refresh charities.json so successfully exported charities don't drift
        # from per-charity files when a subset of EINs fails rebuild.
        existing_by_ein: dict[str, dict] = {}
        charities_file = WEBSITE_DATA_DIR / "charities.json"
        if charities_file.exists():
            try:
                with open(charities_file) as f:
                    existing_payload = json.load(f)
                existing_charities = (
                    existing_payload.get("charities", [])
                    if isinstance(existing_payload, dict)
                    else existing_payload
                )
                if isinstance(existing_charities, list):
                    existing_by_ein = {
                        row.get("ein"): row
                        for row in existing_charities
                        if isinstance(row, dict) and row.get("ein")
                    }
            except Exception as e:
                print(f"⚠ Could not read existing charities.json for merge: {e}")

        for summary in summaries:
            ein = summary.get("ein")
            if ein:
                existing_by_ein[ein] = summary

        merged_summaries = [
            existing_by_ein[ein]
            for ein in sorted(set(exportable_eins))
            if ein in existing_by_ein
        ]

        log_entries = dolt.log(1)
        source_commit = log_entries[0].hash if log_entries else None
        with open(charities_file, "w") as f:
            json.dump(
                {"source_commit": source_commit, "charities": merged_summaries},
                f,
                indent=2,
                default=str,
            )
        print(
            f"✓ Updated charities.json: {len(merged_summaries)} charities "
            f"(eligible={len(set(exportable_eins))}, rebuilt={len(summaries)}, failed={len(rebuild_failures)})"
        )

        # Sync data/ → public/data/ for Vite dev server
        convert_script = Path(__file__).parent.parent / "website" / "scripts" / "convertData.ts"
        if convert_script.exists():
            try:
                result = subprocess.run(
                    ["npx", "tsx", str(convert_script)],
                    cwd=convert_script.parent.parent,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    print("✓ Synced data/ → public/data/")
                else:
                    print(f"⚠ convertData.ts failed: {result.stderr[-200:]}")
            except Exception as e:
                print(f"⚠ convertData.ts skipped: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Total charities: {len(results)}")
    print(f"  ✓ Completed: {success_count}")
    print(f"  ✗ Failed: {len(results) - success_count}")
    print(f"Time: {elapsed:.1f}s ({elapsed / len(results):.1f}s per charity)")

    # Score distribution
    scores = [r.get("amal_score") for r in results if r.get("amal_score")]
    if scores:
        print("\nScore distribution:")
        print(f"  Min: {min(scores):.0f}")
        print(f"  Max: {max(scores):.0f}")
        print(f"  Avg: {sum(scores) / len(scores):.0f}")

    # Export summary
    if not args.skip_export:
        exported_count = sum(1 for r in results if r.get("exported"))
        skipped_judge = sum(
            1 for r in results if r.get("phases", {}).get("export", {}).get("reason", "").startswith("Judge score")
        )
        print("\nExport summary:")
        print(f"  Exported in this run: {exported_count}")
        print(
            f"  Comprehensive index size: {comprehensive_export_count} "
            f"(eligible={comprehensive_export_eligible}, failed={comprehensive_export_failed})"
        )
        print(f"  Skipped (judge < {args.judge_threshold}): {skipped_judge}")

    # Cost summary
    print("\n" + "=" * 80)
    print("COST SUMMARY")
    print("=" * 80)
    print("Phase Breakdown:")
    for phase, cost in phase_costs.items():
        pct = (cost / total_cost * 100) if total_cost > 0 else 0
        print(f"  {phase.capitalize():12} ${cost:>8.4f}  ({pct:>5.1f}%)")
    print("  " + "─" * 30)
    print(f"  {'Total':12} ${total_cost:>8.4f}")
    print(f"\nPer-Charity Average: ${avg_cost:.4f}")
    if success_count > 0:
        print(f"Estimated 150 charities: ${avg_cost * 150:.2f}")

    if comprehensive_export_hard_failed:
        print("\n⛔ Exiting with error: comprehensive export rebuild was incomplete")
    sys.exit(0 if success_count == len(results) and not comprehensive_export_hard_failed else 1)


if __name__ == "__main__":
    main()

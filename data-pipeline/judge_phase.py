"""
Phase 5: Judge - Validate evaluations using LLM and deterministic judges.

Takes evaluation data and validates it for:
- Citation accuracy (do URLs exist and support claims?)
- Factual consistency (do claims match source data?)
- Score rationale (does narrative support the score?)
- Zakat classification (is the classification correct?)
- Data quality across all pipeline phases (crawl, extract, discover, synthesize, baseline, export)

Usage:
    # From streaming_runner.py - called after baseline phase
    result = judge_charity(ein, eval_repo, data_repo, raw_repo)
"""

import sys
from pathlib import Path
from typing import Any

# J-004: Consistent sys.path handling with other phases
sys.path.insert(0, str(Path(__file__).parent))

from src.db import (
    CharityDataRepository,
    CharityRepository,
    EvaluationRepository,
    PhaseCacheRepository,
    RawDataRepository,
)
from src.judges.orchestrator import JudgeOrchestrator
from src.judges.schemas.config import JudgeConfig
from src.utils.ein_utils import normalize_ein
from src.utils.phase_cache_helper import check_phase_cache, update_phase_cache

# J-003: Constants for judge_score calculation
# Higher score = fewer issues = better quality
ERROR_PENALTY = 20  # Points deducted per error
WARNING_PENALTY = 5  # Points deducted per warning
MAX_JUDGE_SCORE = 100


def judge_charity(
    ein: str,
    eval_repo: EvaluationRepository,
    data_repo: CharityDataRepository,
    raw_repo: RawDataRepository,
    charity_repo: CharityRepository | None = None,
) -> dict[str, Any]:
    """Run all judges on a charity's evaluation.

    Validates the evaluation for quality issues using both LLM-based judges
    (citation, factual, score, zakat) and deterministic phase quality judges
    (crawl, extract, discover, synthesize, baseline, export).

    Args:
        ein: Charity EIN
        eval_repo: Evaluation repository
        data_repo: Charity data repository
        raw_repo: Raw data repository
        charity_repo: Optional charity repository for basic info

    Returns:
        {
            "success": bool,
            "judge_score": int (0-100, higher = fewer issues),
            "issues": list[dict] (serialized validation issues),
            "cost_usd": float,
            "error": str (if failed)
        }
    """
    result: dict[str, Any] = {"success": False, "cost_usd": 0.0}

    # J-005: Normalize EIN for consistency
    normalized_ein = normalize_ein(ein)
    if not normalized_ein:
        result["error"] = f"Invalid EIN format: {ein}"
        return result
    ein = normalized_ein

    # Get evaluation
    evaluation = eval_repo.get(ein)
    if not evaluation:
        result["error"] = "No evaluation found"
        return result

    # Get charity data for context
    charity_data = data_repo.get(ein)

    # Get charity from charities table (has city, state, mission)
    charity = charity_repo.get(ein) if charity_repo else None

    # Get raw sources for context
    raw_sources = {}
    raw_data = raw_repo.get_for_charity(ein)
    for rd in raw_data:
        if rd.get("success") and rd.get("parsed_json"):
            raw_sources[rd["source"]] = rd["parsed_json"]

    # Determine tier from evaluation (matches export.py logic)
    def _determine_tier(eval_data: dict | None) -> str:
        if not eval_data:
            return "hidden"
        if eval_data.get("rich_narrative"):
            return "rich"
        if eval_data.get("baseline_narrative"):
            return "baseline"
        return "hidden"

    tier = _determine_tier(evaluation)

    # Build charity dict in format expected by judges
    charity_dict = {
        "ein": ein,
        "name": charity.get("name") if charity else ein,  # Name is in charities table
        "tier": tier,  # Required by ExportQualityJudge
        "evaluation": {
            "amal_score": evaluation.get("amal_score"),
            "wallet_tag": evaluation.get("wallet_tag"),
            "confidence_tier": evaluation.get("confidence_tier"),
            "impact_tier": evaluation.get("impact_tier"),
            "zakat_classification": evaluation.get("zakat_classification"),
            "baseline_narrative": evaluation.get("baseline_narrative"),
            "score_details": evaluation.get("score_details"),
        },
        "data": charity_data or {},
    }

    # Build context with raw sources
    context = {
        "raw_sources": raw_sources,
        "source_data": raw_sources,  # Alias for crawl_quality_judge
        "charity_data": charity_data,
        "charity": charity,  # From charities table - has city, state, mission
    }

    # J-002: Configure all judges explicitly (sample_rate=1.0 for single charity)
    # LLM-based judges validate semantic quality
    # Deterministic judges validate data integrity across pipeline phases
    config = JudgeConfig(
        sample_rate=1.0,  # Validate this specific charity
        # LLM-based semantic validation judges
        enable_citation_judge=True,
        enable_factual_judge=True,
        enable_score_judge=True,
        enable_zakat_judge=True,
        enable_data_completeness_judge=True,
        enable_basic_info_judge=True,
        enable_recognition_judge=True,
        # Deterministic phase quality judges
        enable_crawl_quality_judge=True,
        enable_extract_quality_judge=True,
        enable_discover_quality_judge=True,
        enable_synthesize_quality_judge=True,
        enable_baseline_quality_judge=True,
        enable_export_quality_judge=True,
    )

    try:
        with JudgeOrchestrator(config) as orchestrator:
            validation_result = orchestrator.validate_single(charity_dict, context)

        # J-003: Calculate judge_score using deduplicated issue counts
        # Issues sharing the same issue_key are counted only once (highest severity wins)
        deduped_errors, deduped_warnings = validation_result.deduplicated_issues
        error_count = len(deduped_errors)
        warning_count = len(deduped_warnings)
        penalty = error_count * ERROR_PENALTY + warning_count * WARNING_PENALTY
        judge_score = max(0, MAX_JUDGE_SCORE - penalty)

        # Serialize issues for storage
        issues = []
        for verdict in validation_result.verdicts:
            for issue in verdict.issues:
                issues.append(
                    {
                        "judge": verdict.judge_name,
                        "severity": issue.severity.value,
                        "field": issue.field,
                        "message": issue.message,
                    }
                )

        result["success"] = True
        result["judge_score"] = judge_score
        result["issues"] = issues
        result["passed"] = validation_result.passed
        result["error_count"] = error_count
        result["warning_count"] = warning_count
        result["cost_usd"] = validation_result.total_cost_usd

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    import argparse

    from src.db.dolt_client import dolt
    from src.utils.charity_loader import load_pilot_eins

    parser = argparse.ArgumentParser(description="Run all judges on a charity")
    ein_group = parser.add_mutually_exclusive_group(required=True)
    ein_group.add_argument("--ein", help="Single charity EIN to judge")
    ein_group.add_argument("--charities", help="Path to charities file")
    parser.add_argument("--force", action="store_true", help="Force re-judge even if cache is valid")
    args = parser.parse_args()

    # Initialize repos
    eval_repo = EvaluationRepository()
    data_repo = CharityDataRepository()
    raw_repo = RawDataRepository()
    charity_repo = CharityRepository()
    cache_repo = PhaseCacheRepository()

    # Determine EINs to process
    if args.ein:
        eins = [args.ein]
    else:
        eins = load_pilot_eins(args.charities)

    success_count = 0
    skipped_count = 0
    total_cost = 0.0

    for i, ein in enumerate(eins, 1):
        # Smart cache check
        should_run, reason = check_phase_cache(ein, "judge", cache_repo, force=args.force)
        if not should_run:
            skipped_count += 1
            print(f"[{i}/{len(eins)}] ⊘ {ein}: Cache hit — {reason}")
            continue

        print(f"[{i}/{len(eins)}] Judging charity {ein}...")
        result = judge_charity(ein, eval_repo, data_repo, raw_repo, charity_repo)

        if result["success"]:
            update_phase_cache(ein, "judge", cache_repo, result.get("cost_usd", 0.0))
            success_count += 1
            total_cost += result.get("cost_usd", 0.0)
            print(f"  Judge Score: {result['judge_score']}/100")
            print(f"  Passed: {result['passed']}")
            print(f"  Errors: {result['error_count']}")
            print(f"  Warnings: {result['warning_count']}")
            print(f"  Cost: ${result['cost_usd']:.4f}")
            if result["issues"]:
                print("\n  Issues:")
                for issue in result["issues"]:
                    print(f"    [{issue['severity']}] {issue['judge']}: {issue['message']}")
        else:
            print(f"  Failed: {result.get('error')}")

    # Commit to DoltDB
    if success_count > 0:
        commit_hash = dolt.commit(f"Judge: {success_count} charities validated")
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")

    # Summary
    print(f"\nSuccess: {success_count}/{len(eins)}")
    if skipped_count:
        print(f"Cached: {skipped_count}/{len(eins)}")
    if total_cost > 0:
        print(f"Total cost: ${total_cost:.4f}")

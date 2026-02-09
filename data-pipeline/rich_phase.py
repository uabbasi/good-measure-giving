"""
Phase 5: Rich Narrative - Generate detailed investment memo narratives.

Takes baseline evaluation and generates rich narrative with:
- Investment memo sections (benchmarks, trends, governance)
- Citation-backed claims
- External evaluations verification
- Metric validation

Usage:
    # From streaming_runner.py - called after baseline phase
    result = generate_rich_for_pipeline(ein, eval_repo)
"""

import sys
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.db import EvaluationRepository, PhaseCacheRepository
from src.judges.base_judge import JudgeConfig
from src.judges.rich_quality_judge import RichQualityJudge
from src.judges.schemas.verdict import Severity
from src.services.rich_narrative_generator import RichNarrativeGenerator
from src.utils.phase_cache_helper import check_phase_cache, update_phase_cache


def generate_rich_for_pipeline(
    ein: str,
    eval_repo: EvaluationRepository,
    force: bool = False,
) -> dict[str, Any]:
    """Generate rich narrative for streaming pipeline.

    Wraps RichNarrativeGenerator to return cost tracking info.

    Args:
        ein: Charity EIN
        eval_repo: Evaluation repository (for re-entrancy check)
        force: If True, regenerate even if rich narrative exists

    Returns:
        {
            "success": bool,
            "cost_usd": float,
            "citations_count": int,
            "error": str (if failed)
        }
    """
    result: dict[str, Any] = {"success": False, "cost_usd": 0.0}

    # Re-entrancy check
    if not force:
        existing = eval_repo.get(ein)
        if existing and existing.get("rich_narrative"):
            result["success"] = True
            result["skipped"] = True
            result["reason"] = "Already has rich narrative"
            return result

    try:
        generator = RichNarrativeGenerator()

        rich_narrative = generator.generate(ein, force=force)

        # Always capture cost (even on failure - LLM calls cost money)
        result["cost_usd"] = generator.last_generation_cost

        if rich_narrative:
            # Get citation count
            citations = rich_narrative.get("all_citations", [])
            result["citations_count"] = len(citations)
            result["success"] = True
        else:
            result["error"] = "Generation returned None (no baseline or failed)"

    except Exception as e:
        result["error"] = str(e)

    return result


def run_rich_quality_check(ein: str, eval_repo: EvaluationRepository) -> tuple[bool, list[dict]]:
    """Run deterministic rich quality validation for one EIN."""
    try:
        judge = RichQualityJudge(JudgeConfig(sample_rate=1.0))
        evaluation = eval_repo.get(ein) or {}
        verdict = judge.validate({"ein": ein, "evaluation": evaluation}, {})
        issues = [
            {
                "judge": verdict.judge_name,
                "severity": issue.severity.value,
                "field": issue.field,
                "message": issue.message,
            }
            for issue in verdict.issues
        ]
        has_errors = any(issue.severity == Severity.ERROR for issue in verdict.issues)
        return not has_errors, issues
    except Exception as e:
        return True, [
            {
                "judge": "rich_quality",
                "severity": "warning",
                "field": "judge_execution",
                "message": f"Quality judge failed: {str(e)[:100]}",
            }
        ]


if __name__ == "__main__":
    import argparse

    from src.db.dolt_client import dolt
    from src.utils.charity_loader import load_pilot_eins

    parser = argparse.ArgumentParser(description="Generate rich narrative for a charity")
    ein_group = parser.add_mutually_exclusive_group(required=True)
    ein_group.add_argument("--ein", help="Single charity EIN")
    ein_group.add_argument("--charities", help="Path to charities file")
    parser.add_argument("--force", action="store_true", help="Force regeneration (overrides cache)")
    args = parser.parse_args()

    eval_repo = EvaluationRepository()
    cache_repo = PhaseCacheRepository()

    # Determine EINs to process
    if args.ein:
        eins = [args.ein]
    else:
        eins = load_pilot_eins(args.charities)

    success_count = 0
    skipped_count = 0
    total_cost = 0.0
    failed_charities: list[tuple[str, str]] = []

    for i, ein in enumerate(eins, 1):
        # Smart cache check
        should_run, reason = check_phase_cache(ein, "rich", cache_repo, force=args.force)
        if not should_run:
            skipped_count += 1
            print(f"[{i}/{len(eins)}] ⊘ {ein}: Cache hit — {reason}")
            continue

        print(f"[{i}/{len(eins)}] Generating rich narrative for {ein}...")
        result = generate_rich_for_pipeline(ein, eval_repo, force=args.force)

        if result["success"]:
            if result.get("skipped"):
                skipped_count += 1
                print(f"  Skipped: {result.get('reason')}")
            else:
                passed, issues = run_rich_quality_check(ein, eval_repo)
                if not passed:
                    failed_charities.append((ein, "Quality check failed"))
                    print("  Failed: Quality check failed")
                    for issue in issues:
                        if issue.get("severity") == "error":
                            print(f"    {issue['field']}: {issue['message'][:120]}")
                    continue

                update_phase_cache(ein, "rich", cache_repo, result.get("cost_usd", 0.0))
                success_count += 1
                total_cost += result.get("cost_usd", 0.0)
                print(f"  Citations: {result.get('citations_count', 0)}")
                print(f"  Cost: ${result['cost_usd']:.4f}")
        else:
            error = result.get("error", "Unknown")
            failed_charities.append((ein, error))
            print(f"  Failed: {error}")

    # Commit to DoltDB
    if success_count > 0:
        commit_hash = dolt.commit(f"Rich: {success_count} charities enriched")
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")

    # Summary
    print(f"\nSuccess: {success_count}/{len(eins)}")
    if skipped_count:
        print(f"Cached: {skipped_count}/{len(eins)}")
    if failed_charities:
        print(f"Failed: {len(failed_charities)}/{len(eins)}")
        for ein, error in failed_charities:
            print(f"  {ein}: {error}")
    if total_cost > 0:
        print(f"Total cost: ${total_cost:.4f}")

    if failed_charities:
        sys.exit(1)

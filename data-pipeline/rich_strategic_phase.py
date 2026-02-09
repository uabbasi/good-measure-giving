"""
Phase 5b: Rich Strategic Narrative - Deep strategic analysis with grounded evidence.

Generates citation-backed strategic narratives that go beyond baseline with:
- Strategic deep dive (loop-breaking, multiplier, asset, sovereignty evidence)
- Operational capacity analysis (maturity, sustainability, track record)
- Peer comparison context
- 15-20 grounded citations

Requires baseline strategic narrative to exist first.

Usage:
    uv run python rich_strategic_phase.py --ein 95-4453134
    uv run python rich_strategic_phase.py --charities pilot_charities.txt --workers 5
"""

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.db import EvaluationRepository
from src.db.dolt_client import dolt
from src.services.rich_strategic_narrative_generator import RichStrategicNarrativeGenerator


def generate_rich_strategic_for_pipeline(
    ein: str,
    eval_repo: EvaluationRepository,
    force: bool = False,
) -> dict[str, Any]:
    """Generate rich strategic narrative for a single charity.

    Args:
        ein: Charity EIN
        eval_repo: Evaluation repository
        force: If True, regenerate even if exists

    Returns:
        {success, cost_usd, citations_count, error}
    """
    result: dict[str, Any] = {"success": False, "cost_usd": 0.0}

    # Re-entrancy check
    if not force:
        existing = eval_repo.get(ein)
        if existing and existing.get("rich_strategic_narrative"):
            result["success"] = True
            result["skipped"] = True
            result["reason"] = "Already has rich strategic narrative"
            return result

    try:
        generator = RichStrategicNarrativeGenerator()
        rich_narrative = generator.generate(ein, force=force)
        result["cost_usd"] = generator.last_generation_cost

        if rich_narrative:
            citations = rich_narrative.get("all_citations", [])
            result["citations_count"] = len(citations)
            result["success"] = True
        else:
            result["error"] = "Generation returned None"

    except Exception as e:
        result["error"] = str(e)

    return result


def load_pilot_charities(filepath: str) -> list[str]:
    """Load EINs from pilot_charities.txt."""
    from src.utils.charity_loader import load_pilot_eins

    return load_pilot_eins(filepath)


def main():
    parser = argparse.ArgumentParser(description="Generate rich strategic narratives")
    parser.add_argument("--ein", type=str, help="Single charity EIN")
    parser.add_argument("--charities", type=str, help="Path to charities file")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers (default: 5)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if exists")
    args = parser.parse_args()

    # Determine EINs
    if args.ein:
        eins = [args.ein]
    elif args.charities:
        eins = load_pilot_charities(args.charities)
    else:
        eval_repo = EvaluationRepository()
        # Process all charities that have baseline strategic narratives
        all_evals = eval_repo.get_by_state("generated")
        eins = [
            e["charity_ein"]
            for e in all_evals
            if e.get("strategic_narrative") and (args.force or not e.get("rich_strategic_narrative"))
        ]

    if not eins:
        print("No charities to process")
        return

    eval_repo = EvaluationRepository()
    total = len(eins)
    print(f"\n{'=' * 60}")
    print(f"RICH STRATEGIC NARRATIVE: {total} CHARITIES")
    print(f"  Workers: {args.workers}")
    print(f"  Force: {args.force}")
    print(f"{'=' * 60}\n")

    success_count = 0
    skipped_count = 0
    failed = []
    total_cost = 0.0
    progress_lock = threading.Lock()
    completed = 0

    def process_one(ein: str) -> tuple[str, dict]:
        result = generate_rich_strategic_for_pipeline(ein, eval_repo, force=args.force)
        return ein, result

    if args.workers == 1 or total == 1:
        for ein in eins:
            ein, result = process_one(ein)
            completed += 1
            total_cost += result.get("cost_usd", 0)
            if result.get("skipped"):
                skipped_count += 1
                print(f"  [{completed}/{total}] {ein}: SKIPPED")
            elif result["success"]:
                success_count += 1
                citations = result.get("citations_count", 0)
                cost = result.get("cost_usd", 0)
                print(f"  [{completed}/{total}] {ein}: OK ({citations} citations, ${cost:.4f})")
            else:
                failed.append((ein, result.get("error", "Unknown")))
                print(f"  [{completed}/{total}] {ein}: FAILED - {result.get('error')}")
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(process_one, ein): ein for ein in eins}
            for future in as_completed(futures):
                ein, result = future.result()
                with progress_lock:
                    completed += 1
                    total_cost += result.get("cost_usd", 0)
                    if result.get("skipped"):
                        skipped_count += 1
                        print(f"  [{completed}/{total}] {ein}: SKIPPED")
                    elif result["success"]:
                        success_count += 1
                        citations = result.get("citations_count", 0)
                        cost = result.get("cost_usd", 0)
                        print(f"  [{completed}/{total}] {ein}: OK ({citations} citations, ${cost:.4f})")
                    else:
                        failed.append((ein, result.get("error", "Unknown")))
                        print(f"  [{completed}/{total}] {ein}: FAILED - {result.get('error')}")

    # Commit to DoltDB
    if success_count > 0:
        commit_hash = dolt.commit(
            f"Rich strategic: {success_count} charities, ${total_cost:.4f} LLM cost"
        )
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {success_count} success, {skipped_count} skipped, {len(failed)} failed")
    print(f"Total LLM cost: ${total_cost:.4f}")
    if failed:
        print("\nFailed charities:")
        for ein, error in failed:
            print(f"  {ein}: {error}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()

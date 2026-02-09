"""
Benchmark CLI - Command-line interface for running benchmarks.

Usage:
    # Run full benchmark suite (all models × benchmark charities)
    uv run python -m src.benchmarks suite

    # Run with specific model on benchmark charities
    uv run python -m src.benchmarks run --model gemini-3-flash-preview

    # Run with specific model on custom charities
    uv run python -m src.benchmarks run --model gemini-3-flash-preview --charities pilot_charities.txt

    # Estimate cost of full benchmark
    uv run python -m src.benchmarks cost

    # List available runs
    uv run python -m src.benchmarks list

    # Show run summary
    uv run python -m src.benchmarks show 2026-01-24_gemini-3-flash-preview_baseline-v2.0.0

    # Compare two runs
    uv run python -m src.benchmarks compare run1 run2
"""

import argparse
import json
import sys
from pathlib import Path

from .config import (
    BENCHMARK_CHARITIES,
    BENCHMARK_EINS,
    BENCHMARK_MODELS,
    MODEL_INFO,
    estimate_full_benchmark_cost,
)
from .runner import BenchmarkRunner, RunConfig, load_pilot_charities
from .storage import BenchmarkStorage


def cmd_run(args: argparse.Namespace) -> int:
    """Run a benchmark evaluation."""
    # Load charities
    if args.ein:
        eins = [args.ein]
    elif args.charities:
        charities_path = Path(args.charities)
        if not charities_path.exists():
            print(f"Error: File not found: {args.charities}")
            return 1
        eins = load_pilot_charities(charities_path)
    else:
        # Default to benchmark charities (not full pilot list)
        print(f"Using benchmark charities ({len(BENCHMARK_EINS)} charities)")
        eins = BENCHMARK_EINS

    if not eins:
        print("Error: No charities to evaluate")
        return 1

    # Create config
    config = RunConfig(
        model=args.model,
        prompt_name=args.prompt or "baseline_narrative",
        prompt_version=args.prompt_version,
        max_charities=args.max,
        notes=args.notes or "",
    )

    # Run benchmark
    runner = BenchmarkRunner()
    run = runner.run(eins, config)

    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    summary = run.to_summary()
    print(json.dumps(summary, indent=2))

    return 0


def cmd_suite(args: argparse.Namespace) -> int:
    """Run full benchmark suite (all models × benchmark charities)."""
    models = args.models.split(",") if args.models else BENCHMARK_MODELS

    print("=" * 60)
    print("BENCHMARK SUITE")
    print("=" * 60)
    print(f"Charities: {len(BENCHMARK_EINS)}")
    print(f"Models: {len(models)}")
    print()

    # Show charities
    print("Benchmark charities:")
    for name, ein in BENCHMARK_CHARITIES:
        print(f"  - {name} ({ein})")
    print()

    # Show models
    print("Models to evaluate:")
    for model in models:
        info = MODEL_INFO.get(model, {})
        tier = info.get("tier", "unknown")
        print(f"  - {model} ({tier})")
    print()

    # Estimate cost
    cost_estimate = estimate_full_benchmark_cost()
    print(f"Estimated total cost: ${cost_estimate['total']:.4f}")
    print()

    if not args.yes:
        response = input("Proceed? [y/N] ")
        if response.lower() != "y":
            print("Aborted.")
            return 1

    # Run each model
    runner = BenchmarkRunner()
    results = []

    for i, model in enumerate(models):
        print()
        print(f"[{i + 1}/{len(models)}] Running {model}...")
        print("-" * 40)

        config = RunConfig(
            model=model,
            notes=f"Suite run: {len(models)} models × {len(BENCHMARK_EINS)} charities",
        )

        try:
            run = runner.run(BENCHMARK_EINS, config)
            results.append((model, run))
        except Exception as e:
            print(f"Error running {model}: {e}")
            results.append((model, None))

    # Summary
    print()
    print("=" * 80)
    print("SUITE COMPLETE")
    print("=" * 80)
    print()
    print(f"{'Model':<28} {'Success':<10} {'Cost':<10} {'Quality':<10} {'Charity Score':<12}")
    print("-" * 80)

    for model, run in results:
        if run:
            success = f"{run.charities_succeeded}/{run.charities_count}"
            cost = f"${run.total_cost_usd:.4f}"
            # LLM quality score
            summary = run.to_summary()
            quality = summary.get("llm_quality", {}).get("avg_overall", 0)
            quality_str = f"{quality:.1f}"
            # Charity scores (deterministic, should be same across models)
            scores = [e.amal_score for e in run.evaluations if e.amal_score]
            avg_score = f"{sum(scores) / len(scores):.1f}" if scores else "N/A"
        else:
            success = "FAILED"
            cost = "-"
            quality_str = "-"
            avg_score = "-"
        print(f"{model:<28} {success:<10} {cost:<10} {quality_str:<10} {avg_score:<12}")

    return 0


def cmd_cost(args: argparse.Namespace) -> int:
    """Estimate cost of running the full benchmark suite."""
    cost = estimate_full_benchmark_cost()

    print("Benchmark Cost Estimate")
    print("=" * 40)
    print(f"Charities: {cost['charities']}")
    print(f"Models: {cost['models']}")
    print()
    print("Per-model costs:")
    for model, model_cost in cost["per_model"].items():
        info = MODEL_INFO.get(model, {})
        tier = info.get("tier", "?")
        print(f"  {model:<30} ${model_cost:.4f} ({tier})")
    print()
    print(f"Total estimated cost: ${cost['total']:.4f}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List available benchmark runs."""
    storage = BenchmarkStorage()
    runs = storage.list_runs()

    if not runs:
        print("No benchmark runs found.")
        return 0

    print(f"Found {len(runs)} benchmark runs:\n")
    for run_id in runs:
        run = storage.load(run_id)
        if run:
            success_rate = f"{run.success_rate:.0f}%" if run.charities_count > 0 else "N/A"
            print(f"  {run_id}")
            print(f"    Model: {run.model}")
            print(f"    Charities: {run.charities_succeeded}/{run.charities_count} ({success_rate})")
            print(f"    Cost: ${run.total_cost_usd:.4f}")
            print()

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show details of a specific run."""
    storage = BenchmarkStorage()
    run = storage.load(args.run_id)

    if not run:
        print(f"Error: Run not found: {args.run_id}")
        return 1

    summary = run.to_summary()
    print(json.dumps(summary, indent=2))

    if args.verbose:
        print("\n" + "-" * 40)
        print("EVALUATIONS:")
        for eval in run.evaluations:
            status = "✓" if eval.amal_score is not None else "✗"
            score = eval.amal_score or "N/A"
            print(f"  {status} {eval.ein}: {eval.name[:40]:<40} Score: {score}")
            if eval.error:
                print(f"      Error: {eval.error}")

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two benchmark runs."""
    storage = BenchmarkStorage()

    run1 = storage.load(args.run1)
    run2 = storage.load(args.run2)

    if not run1:
        print(f"Error: Run not found: {args.run1}")
        return 1
    if not run2:
        print(f"Error: Run not found: {args.run2}")
        return 1

    print("=" * 70)
    print("BENCHMARK COMPARISON")
    print("=" * 70)
    print()

    # Header comparison
    print(f"{'Metric':<25} {'Run 1':<20} {'Run 2':<20} {'Delta':<10}")
    print("-" * 70)

    # Model/prompt info
    print(f"{'Run ID':<25} {run1.run_id[:18]:<20} {run2.run_id[:18]:<20}")
    print(f"{'Model':<25} {run1.model:<20} {run2.model:<20}")
    print(f"{'Prompt':<25} {run1.prompt_name:<20} {run2.prompt_name:<20}")
    print(f"{'Prompt Version':<25} {run1.prompt_version:<20} {run2.prompt_version:<20}")
    print()

    # Success metrics
    s1 = f"{run1.charities_succeeded}/{run1.charities_count}"
    s2 = f"{run2.charities_succeeded}/{run2.charities_count}"
    delta_success = run2.success_rate - run1.success_rate
    print(f"{'Succeeded':<25} {s1:<20} {s2:<20} {delta_success:+.1f}%")

    # Cost comparison
    c1 = f"${run1.total_cost_usd:.4f}"
    c2 = f"${run2.total_cost_usd:.4f}"
    if run1.total_cost_usd > 0:
        delta_cost = (run2.total_cost_usd - run1.total_cost_usd) / run1.total_cost_usd * 100
        delta_cost_str = f"{delta_cost:+.1f}%"
    else:
        delta_cost_str = "N/A"
    print(f"{'Total Cost':<25} {c1:<20} {c2:<20} {delta_cost_str}")

    # Per-charity cost
    pc1 = f"${run1.avg_cost_per_charity:.4f}"
    pc2 = f"${run2.avg_cost_per_charity:.4f}"
    print(f"{'Avg Cost/Charity':<25} {pc1:<20} {pc2:<20}")

    # Latency
    l1 = f"{run1.avg_latency_per_charity:.1f}s"
    l2 = f"{run2.avg_latency_per_charity:.1f}s"
    print(f"{'Avg Latency/Charity':<25} {l1:<20} {l2:<20}")

    print()

    # LLM Quality metrics comparison
    summary1 = run1.to_summary()
    summary2 = run2.to_summary()
    q1 = summary1.get("llm_quality", {})
    q2 = summary2.get("llm_quality", {})

    if q1 and q2:
        print("LLM QUALITY METRICS")
        print("-" * 70)
        for metric in ["avg_structural", "avg_citation", "avg_specificity", "avg_completeness", "avg_overall"]:
            v1 = q1.get(metric, 0)
            v2 = q2.get(metric, 0)
            delta = v2 - v1
            label = metric.replace("avg_", "").title()
            print(f"{label:<25} {v1:<20.1f} {v2:<20.1f} {delta:+.1f}")
        print()

    # Score comparison (for charities in both runs)
    eins1 = {e.ein: e for e in run1.evaluations if e.amal_score is not None}
    eins2 = {e.ein: e for e in run2.evaluations if e.amal_score is not None}
    common_eins = set(eins1.keys()) & set(eins2.keys())

    if common_eins:
        print(f"Score comparison for {len(common_eins)} common charities:")
        print("-" * 70)

        score_diffs = []
        for ein in sorted(common_eins):
            e1 = eins1[ein]
            e2 = eins2[ein]
            diff = (e2.amal_score or 0) - (e1.amal_score or 0)
            score_diffs.append(diff)

            if abs(diff) >= 5 or args.verbose:  # Show significant changes or all if verbose
                print(f"  {ein}: {e1.amal_score} -> {e2.amal_score} ({diff:+d})")

        # Summary stats
        if score_diffs:
            avg_diff = sum(score_diffs) / len(score_diffs)
            max_diff = max(score_diffs)
            min_diff = min(score_diffs)
            print()
            print(f"Score delta: avg={avg_diff:+.1f}, min={min_diff:+d}, max={max_diff:+d}")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Benchmark CLI for model/prompt comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # suite command (run all models)
    suite_parser = subparsers.add_parser("suite", help="Run full benchmark suite (all models)")
    suite_parser.add_argument("--models", help="Comma-separated models (default: all benchmark models)")
    suite_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # run command (single model)
    run_parser = subparsers.add_parser("run", help="Run a benchmark evaluation")
    run_parser.add_argument("--model", required=True, help="Model to use (e.g., gemini-3-flash-preview)")
    run_parser.add_argument("--prompt", help="Prompt name (default: baseline_narrative)")
    run_parser.add_argument("--prompt-version", help="Specific prompt version (default: current)")
    run_parser.add_argument("--charities", help="Path to charities file (default: benchmark set)")
    run_parser.add_argument("--ein", help="Single EIN to evaluate")
    run_parser.add_argument("--max", type=int, help="Maximum charities to evaluate")
    run_parser.add_argument("--notes", help="Notes for this run")

    # cost command
    subparsers.add_parser("cost", help="Estimate cost of full benchmark suite")

    # list command
    subparsers.add_parser("list", help="List available benchmark runs")

    # show command
    show_parser = subparsers.add_parser("show", help="Show details of a run")
    show_parser.add_argument("run_id", help="Run ID to show")
    show_parser.add_argument("-v", "--verbose", action="store_true", help="Show all evaluations")

    # compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two runs")
    compare_parser.add_argument("run1", help="First run ID")
    compare_parser.add_argument("run2", help="Second run ID")
    compare_parser.add_argument("-v", "--verbose", action="store_true", help="Show all score changes")

    args = parser.parse_args()

    if args.command == "suite":
        return cmd_suite(args)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "cost":
        return cmd_cost(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "show":
        return cmd_show(args)
    elif args.command == "compare":
        return cmd_compare(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

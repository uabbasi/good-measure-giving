#!/usr/bin/env python3
"""Quick summary of all benchmark results."""

import json
from pathlib import Path


def main():
    results_dir = Path(__file__).parent / "results"

    # Load all summaries
    runs = []
    for run_dir in sorted(results_dir.iterdir()):
        if run_dir.is_dir():
            summary_file = run_dir / "summary.json"
            if summary_file.exists():
                with open(summary_file) as f:
                    runs.append(json.load(f))

    if not runs:
        print("No benchmark results found.")
        return

    # Sort by quality score descending
    runs.sort(key=lambda r: r.get("llm_quality", {}).get("avg_overall", 0), reverse=True)

    print("=" * 80)
    print("LLM BENCHMARK SUMMARY")
    print("=" * 80)
    print()

    # Header
    print(f"{'Model':<28} {'Success':>8} {'Quality':>8} {'Cost':>10} {'Latency':>10}")
    print("-" * 80)

    for run in runs:
        model = run["model"]
        charities = run["charities"]
        success_rate = f"{charities['succeeded']}/{charities['total']}"
        success_pct = charities['succeeded'] / charities['total'] * 100

        quality = run.get("llm_quality", {}).get("avg_overall", 0)
        cost = run["cost"]["avg_per_charity_usd"]
        latency = run["latency"]["avg_per_charity_seconds"]

        print(f"{model:<28} {success_rate:>5} ({success_pct:>2.0f}%) {quality:>7.1f} ${cost:>8.4f} {latency:>8.1f}s")

    print()
    print("=" * 80)
    print("QUALITY BREAKDOWN")
    print("=" * 80)
    print()

    print(f"{'Model':<28} {'Struct':>8} {'Citation':>8} {'Specific':>8} {'Complete':>8} {'Overall':>8}")
    print("-" * 80)

    for run in runs:
        model = run["model"]
        q = run.get("llm_quality", {})
        if not q:
            continue
        print(f"{model:<28} {q.get('avg_structural', 0):>8.1f} {q.get('avg_citation', 0):>8.1f} {q.get('avg_specificity', 0):>8.1f} {q.get('avg_completeness', 0):>8.1f} {q.get('avg_overall', 0):>8.1f}")

    print()
    print("=" * 80)
    print("COST PROJECTION (155 charities)")
    print("=" * 80)
    print()

    for run in runs:
        model = run["model"]
        cost_per = run["cost"]["avg_per_charity_usd"]
        total_cost = cost_per * 155
        print(f"{model:<28} ${total_cost:>6.2f}")

    print()


if __name__ == "__main__":
    main()

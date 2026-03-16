#!/usr/bin/env python3
"""
Autoprompt — Autonomous prompt optimization via eval-driven iteration.

Applies the autoresearch pattern: modify prompt → generate narratives → measure
metrics → keep/revert. Tests each candidate prompt on multiple models simultaneously
and only keeps changes that improve across ALL target models.

Usage:
    # Universal: optimize across 3 models
    uv run python autoprompt.py \
        --models gemini-3-pro-preview,claude-sonnet-4-5,gpt-5.2 \
        --iterations 20 --budget 10.00

    # Quick dev test: single model, 3 charities
    uv run python autoprompt.py \
        --model gemini-3-pro-preview --eval-set mini --iterations 2 --dry-run

    # Different optimizer LLM
    uv run python autoprompt.py \
        --models gemini-3-pro-preview,claude-sonnet-4-5 \
        --optimizer-model claude-opus-4-5
"""

import argparse
import csv
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from src.autoprompt.evaluator import AutopromptEvaluator, PairwiseEvaluator
from src.autoprompt.optimizer import IterationFeedback, PromptOptimizer
from src.benchmarks.config import BENCHMARK_CHARITIES
from src.llm.prompt_loader import load_prompt

logger = logging.getLogger("autoprompt")

# Mini eval set: 3 diverse charities for fast dev iteration
MINI_EINS = [
    "95-4453134",  # Islamic Relief USA (large, well-documented)
    "47-1313957",  # Khalil Center (small, sparse data)
    "20-3069841",  # Against Malaria Foundation (non-Muslim, GiveWell)
]

RESULTS_DIR = Path(__file__).parent / "src" / "autoprompt" / "results"


def prompt_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode()).hexdigest()[:12]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Autonomous prompt optimization via eval-driven iteration"
    )
    parser.add_argument(
        "--target-prompt",
        default="rich_narrative_v2",
        help="Which prompt to optimize (default: rich_narrative_v2)",
    )
    parser.add_argument(
        "--model",
        help="Single target model (shortcut for --models with 1 model)",
    )
    parser.add_argument(
        "--models",
        help="Comma-separated target models for universal optimization",
    )
    parser.add_argument(
        "--optimizer-model",
        default="claude-sonnet-4-5",
        help="LLM for meta-prompting (default: claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--pairwise-model",
        default="claude-sonnet-4-5",
        help="LLM for pairwise judging (default: claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Max iterations (default: 20)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=10.00,
        help="Max USD spend (default: 10.00)",
    )
    parser.add_argument(
        "--eval-set",
        choices=["benchmark", "mini"],
        default="benchmark",
        help="Eval charity set: benchmark (20) or mini (3 for dev)",
    )
    parser.add_argument(
        "--pairwise-interval",
        type=int,
        default=5,
        help="Run pairwise every N iterations (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run 1 iteration and stop",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Resolve models
    if args.model and args.models:
        parser.error("Use --model OR --models, not both")
    if args.model:
        args.target_models = [args.model]
    elif args.models:
        args.target_models = [m.strip() for m in args.models.split(",")]
    else:
        parser.error("Must specify --model or --models")

    if args.dry_run:
        args.iterations = 1

    return args


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy loggers
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)


class AutopromptRunner:
    """Main optimization loop."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.total_cost = 0.0

        # Eval set
        if args.eval_set == "mini":
            self.eval_eins = MINI_EINS
        else:
            self.eval_eins = [ein for _, ein in BENCHMARK_CHARITIES]

        # Components
        self.evaluator = AutopromptEvaluator(self.eval_eins)
        self.optimizer = PromptOptimizer(
            optimizer_model=args.optimizer_model,
            target_prompt_name=args.target_prompt,
        )
        self.pairwise = PairwiseEvaluator(
            judge_model=args.pairwise_model,
            eval_eins=self.eval_eins[:5],
        )

        # Results storage
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = RESULTS_DIR / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.iterations_log: list[dict] = []

    def run(self):
        """Execute the optimization loop."""
        logger.info("=" * 60)
        logger.info(f"Autoprompt run: {self.run_id}")
        logger.info(f"Target prompt: {self.args.target_prompt}")
        logger.info(f"Target models: {self.args.target_models}")
        logger.info(f"Eval charities: {len(self.eval_eins)}")
        logger.info(f"Max iterations: {self.args.iterations}")
        logger.info(f"Budget: ${self.args.budget:.2f}")
        logger.info("=" * 60)

        # Load current prompt
        prompt_info = load_prompt(self.args.target_prompt)
        current_prompt = prompt_info.content
        best_prompt = current_prompt

        # Run baseline
        logger.info("\n--- Baseline evaluation ---")
        baseline_results = self.evaluator.evaluate(
            current_prompt, self.args.target_models
        )
        baseline_cost = sum(r.total_cost_usd for r in baseline_results.values())
        self.total_cost += baseline_cost

        baseline_scores = {
            model: result.avg_scores for model, result in baseline_results.items()
        }
        current_scores = dict(baseline_scores)

        # Log baseline
        self._log_iteration(
            iteration=0,
            prompt_content=current_prompt,
            model_results=baseline_results,
            kept=True,
            changelog="baseline",
        )

        logger.info("\nBaseline scores:")
        for model, scores in baseline_scores.items():
            logger.info(f"  {model}: overall={scores.get('overall_score', 0):.1f}")

        # Track baseline narratives for pairwise
        baseline_narratives = self._extract_narratives(baseline_results)
        best_confirmed_prompt = current_prompt
        best_confirmed_scores = dict(baseline_scores)

        # Optimization loop
        for iteration in range(1, self.args.iterations + 1):
            logger.info(f"\n--- Iteration {iteration}/{self.args.iterations} ---")

            # Budget check
            if self.total_cost >= self.args.budget:
                logger.info(f"Budget exhausted: ${self.total_cost:.2f} >= ${self.args.budget:.2f}")
                break

            # Propose modification
            logger.info("Proposing prompt modification...")
            candidate_prompt = self.optimizer.propose(
                best_prompt, baseline_scores, current_scores, iteration
            )

            if candidate_prompt == best_prompt:
                logger.info("Optimizer returned unchanged prompt, skipping")
                continue

            # Evaluate candidate on all models
            logger.info("Evaluating candidate...")
            candidate_results = self.evaluator.evaluate(
                candidate_prompt, self.args.target_models
            )
            iter_cost = sum(r.total_cost_usd for r in candidate_results.values())
            self.total_cost += iter_cost

            candidate_scores = {
                model: result.avg_scores for model, result in candidate_results.items()
            }

            # Universal keep rule: no model regresses, mean improves
            deltas = {}
            for model in self.args.target_models:
                base = current_scores.get(model, {}).get("overall_score", 0)
                cand = candidate_scores.get(model, {}).get("overall_score", 0)
                deltas[model] = cand - base

            min_delta = min(deltas.values()) if deltas else 0
            mean_delta = sum(deltas.values()) / len(deltas) if deltas else 0

            kept = min_delta >= -0.5 and mean_delta > 0

            if kept:
                logger.info(f"  KEEP: min_delta={min_delta:.1f}, mean_delta={mean_delta:.1f}")
                for model, delta in deltas.items():
                    logger.info(f"    {model}: {'↑' if delta > 0 else '↓'}{abs(delta):.1f}")
                best_prompt = candidate_prompt
                current_scores = candidate_scores
            else:
                logger.info(f"  REVERT: min_delta={min_delta:.1f}, mean_delta={mean_delta:.1f}")
                for model, delta in deltas.items():
                    logger.info(f"    {model}: {'↑' if delta > 0 else '↓'}{abs(delta):.1f}")

            # Record feedback for optimizer
            changelog = f"min_delta={min_delta:.1f}, mean_delta={mean_delta:.1f}"
            feedback = IterationFeedback(
                iteration=iteration,
                kept=kept,
                changelog=changelog,
                model_scores=candidate_scores,
                model_deltas={m: {"overall": d} for m, d in deltas.items()},
            )

            # Pairwise comparison — compare current best against original baseline
            pairwise_win_rate = None
            if iteration % self.args.pairwise_interval == 0:
                logger.info("Running pairwise comparison on current best prompt...")
                # Re-generate with the current best prompt (not the just-reverted candidate)
                best_results = self.evaluator.evaluate(
                    best_prompt, self.args.target_models
                )
                best_cost = sum(r.total_cost_usd for r in best_results.values())
                self.total_cost += best_cost
                best_narratives = self._extract_narratives(best_results)
                win_rates, judge_reasons = self.pairwise.compare(
                    baseline_narratives, best_narratives
                )
                pairwise_win_rate = (
                    sum(win_rates.values()) / len(win_rates) if win_rates else 0.5
                )
                feedback.pairwise_win_rate = pairwise_win_rate
                feedback.pairwise_reasons = judge_reasons

                if pairwise_win_rate > 0.5:
                    logger.info(f"  Pairwise CONFIRMED: win_rate={pairwise_win_rate:.2f}")
                    best_confirmed_prompt = best_prompt
                    best_confirmed_scores = dict(current_scores)
                else:
                    logger.info(
                        f"  Pairwise ROLLBACK: win_rate={pairwise_win_rate:.2f}, "
                        f"reverting to last confirmed prompt"
                    )
                    best_prompt = best_confirmed_prompt
                    current_scores = dict(best_confirmed_scores)

            self.optimizer.record_iteration(feedback)
            self._log_iteration(
                iteration=iteration,
                prompt_content=candidate_prompt,
                model_results=candidate_results,
                kept=kept,
                changelog=changelog,
                pairwise_win_rate=pairwise_win_rate,
            )

            logger.info(f"  Cost this iteration: ${iter_cost:.4f}, total: ${self.total_cost:.4f}")

        # Save final results
        self._save_results(best_prompt, baseline_scores, current_scores)
        logger.info("\n" + "=" * 60)
        logger.info(f"Autoprompt complete: {self.run_id}")
        logger.info(f"Total cost: ${self.total_cost:.4f}")
        logger.info(f"Results: {self.run_dir}")
        logger.info("=" * 60)

    def _extract_narratives(
        self, results: dict
    ) -> dict[str, dict[str, dict]]:
        """Extract {model: {ein: narrative}} from results."""
        narratives: dict[str, dict[str, dict]] = {}
        for model, result in results.items():
            narratives[model] = {}
            for cn in result.charities:
                if cn.narrative is not None:
                    narratives[model][cn.ein] = cn.narrative
        return narratives

    def _log_iteration(
        self,
        iteration: int,
        prompt_content: str,
        model_results: dict,
        kept: bool,
        changelog: str,
        pairwise_win_rate: float | None = None,
    ):
        """Log iteration to in-memory list and TSV."""
        phash = prompt_hash(prompt_content)

        # Aggregate across models
        all_overalls = []
        readability_grades = []
        ai_phrases = []
        for result in model_results.values():
            scores = result.avg_scores
            all_overalls.append(scores.get("overall_score", 0))
            # Get readability/ai details from individual charities
            for cn in result.charities:
                if cn.quality and cn.quality.readability_details:
                    readability_grades.append(cn.quality.readability_details.get("grade_level", 0))
                if cn.quality and cn.quality.human_voice_details:
                    ai_phrases.append(cn.quality.human_voice_details.get("ai_phrases_found", 0))

        entry = {
            "iteration": iteration,
            "prompt_hash": phash,
            "mean_overall": sum(all_overalls) / len(all_overalls) if all_overalls else 0,
            "min_overall": min(all_overalls) if all_overalls else 0,
            "readability_grade": (
                sum(readability_grades) / len(readability_grades) if readability_grades else 0
            ),
            "ai_phrases": sum(ai_phrases) / len(ai_phrases) if ai_phrases else 0,
            "pairwise": pairwise_win_rate,
            "kept": kept,
            "cost": sum(r.total_cost_usd for r in model_results.values()),
            "changelog": changelog,
            "models": {
                model: result.avg_scores for model, result in model_results.items()
            },
        }
        self.iterations_log.append(entry)

        # Append to TSV
        tsv_path = self.run_dir / "iterations.tsv"
        write_header = not tsv_path.exists()
        with open(tsv_path, "a", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            if write_header:
                writer.writerow([
                    "iter", "prompt_hash", "mean_overall", "min_overall",
                    "readability_grade", "ai_phrases", "pairwise", "kept",
                    "cost", "changelog",
                ])
            writer.writerow([
                iteration,
                phash,
                f"{entry['mean_overall']:.1f}",
                f"{entry['min_overall']:.1f}",
                f"{entry['readability_grade']:.1f}",
                f"{entry['ai_phrases']:.1f}",
                f"{pairwise_win_rate:.2f}" if pairwise_win_rate is not None else "-",
                "true" if kept else "false",
                f"{entry['cost']:.4f}",
                changelog,
            ])

    def _save_results(
        self,
        best_prompt: str,
        baseline_scores: dict,
        final_scores: dict,
    ):
        """Save final results to JSON files."""
        # Metadata
        metadata = {
            "run_id": self.run_id,
            "target_prompt": self.args.target_prompt,
            "target_models": self.args.target_models,
            "optimizer_model": self.args.optimizer_model,
            "eval_set": self.args.eval_set,
            "eval_charities": len(self.eval_eins),
            "iterations": len(self.iterations_log) - 1,  # exclude baseline
            "total_cost_usd": round(self.total_cost, 4),
            "budget": self.args.budget,
        }
        self._write_json(self.run_dir / "metadata.json", metadata)

        # Iterations detail
        self._write_json(self.run_dir / "iterations.json", self.iterations_log)

        # Summary
        summary = {
            "baseline_scores": baseline_scores,
            "final_scores": final_scores,
            "improvement": {
                model: {
                    metric: round(
                        final_scores.get(model, {}).get(metric, 0)
                        - baseline_scores.get(model, {}).get(metric, 0),
                        1,
                    )
                    for metric in baseline_scores.get(model, {})
                }
                for model in self.args.target_models
            },
            "total_cost_usd": round(self.total_cost, 4),
        }
        self._write_json(self.run_dir / "summary.json", summary)

        # Save best prompt
        (self.run_dir / "best_prompt.txt").write_text(best_prompt)

        logger.info(f"\nSummary:")
        for model in self.args.target_models:
            base = baseline_scores.get(model, {}).get("overall_score", 0)
            final = final_scores.get(model, {}).get("overall_score", 0)
            logger.info(f"  {model}: {base:.1f} → {final:.1f} ({final - base:+.1f})")

    def _write_json(self, path: Path, data) -> None:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False, default=str)
            f.write("\n")


def main():
    args = parse_args()
    setup_logging(args.verbose)
    runner = AutopromptRunner(args)
    runner.run()


if __name__ == "__main__":
    main()

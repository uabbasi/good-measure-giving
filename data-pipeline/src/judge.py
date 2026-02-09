#!/usr/bin/env python3
"""LLM Judge - Post-export validation of charity evaluations.

Validates the actual exported JSON that users see on the website.

Runs LLM-based validation to catch:
- Citation issues (broken links, unsupported claims)
- Factual errors (narrative claims that don't match source data)
- Score mismatches (rationale that doesn't explain the score)
- Zakat classification issues (asnaf category doesn't match programs)

Uses spot-check sampling to balance thoroughness with cost.

Usage:
    uv run judge                                  # Validate 10% from website/data/charities
    uv run judge --sample-rate 0.5                # Validate 50%
    uv run judge --output /tmp/report.json        # Save report
    uv run judge --ein 36-4476244                 # Validate single charity
    uv run judge --json-dir path/to/charities     # Custom JSON directory
"""

import argparse
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.db import CharityDataRepository, CharityRepository, RawDataRepository
from src.judges import JudgeConfig, JudgeOrchestrator

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

# Default path to exported charity JSON files
DEFAULT_JSON_DIR = Path(__file__).parent.parent.parent / "website" / "data" / "charities"


def load_charities_from_json(json_dir: Path, ein_filter: Optional[str] = None) -> list[dict]:
    """Load charity data from exported JSON files.

    Args:
        json_dir: Directory containing charity-{ein}.json files
        ein_filter: Optional EIN to filter to a single charity

    Returns:
        List of charity dicts normalized for judge consumption
    """
    charities = []

    if not json_dir.exists():
        logger.error(f"JSON directory not found: {json_dir}")
        return []

    # Find all charity JSON files
    pattern = f"charity-{ein_filter}.json" if ein_filter else "charity-*.json"
    files = list(json_dir.glob(pattern))

    if not files:
        logger.warning(f"No charity files found in {json_dir}")
        return []

    for file_path in files:
        try:
            data = json.loads(file_path.read_text())
            charity = normalize_charity_json(data)
            if charity:
                charities.append(charity)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")

    return charities


def _extract_strategic_data(data: dict) -> dict:
    """Extract strategic evaluation data for judge consumption.

    Returns dict keys to merge into the normalized charity structure:
    - strategic_narrative: narrative dict from strategicEvaluation
    - strategic_evaluation: scores, archetype, dimensions
    - strategic_citations: normalized citations from strategic narrative
    """
    strat_eval = data.get("strategicEvaluation") or {}
    if not strat_eval:
        return {}

    strat_narrative = strat_eval.get("narrative") or {}

    # Normalize strategic citations (same format as AMAL citations)
    strat_citations = []
    for cit in strat_narrative.get("all_citations", []):
        strat_citations.append(
            {
                "index": cit.get("id", "").strip("[]"),
                "url": cit.get("source_url", ""),
                "claim": cit.get("claim", ""),
                "source_name": cit.get("source_name", ""),
                "quote": cit.get("quote"),
            }
        )

    # Build strategic evaluation summary
    dimensions = strat_eval.get("dimensions", {})
    strat_evaluation = {
        "total_score": strat_eval.get("total_score"),
        "archetype": strat_eval.get("archetype"),
        "archetype_label": strat_eval.get("archetype_label"),
        "dimensions": {k: v.get("score") if isinstance(v, dict) else v for k, v in dimensions.items()},
    }

    return {
        "strategic_narrative": {
            "summary": strat_narrative.get("summary", ""),
            "headline": strat_narrative.get("headline", ""),
            "strengths": strat_narrative.get("strengths", []),
            "areas_for_improvement": strat_narrative.get("areas_for_improvement", []),
            "dimension_explanations": strat_narrative.get("dimension_explanations", {}),
            "score_interpretation": strat_narrative.get("score_interpretation", ""),
            "score_rationale": strat_narrative.get("score_rationale", ""),
            "ideal_donor_profile": strat_narrative.get("ideal_donor_profile", ""),
            "case_against": strat_narrative.get("case_against", ""),
            "all_citations": strat_narrative.get("all_citations", []),
        },
        "strategic_evaluation": strat_evaluation,
        "strategic_citations": strat_citations,
    }


def normalize_charity_json(data: dict) -> Optional[dict]:
    """Normalize website JSON structure for judge consumption.

    Transforms camelCase website format to the structure judges expect.
    """
    ein = data.get("ein")
    if not ein:
        return None

    # Handle both website format (amalEvaluation) and export format (evaluation)
    amal_eval = data.get("amalEvaluation") or data.get("evaluation") or {}

    # Get narrative and citations - prefer rich if available, fall back to baseline
    # Handle both nested format (amalEvaluation.rich_narrative) and flat format (narrative)
    rich_narrative = amal_eval.get("rich_narrative", {})
    baseline_narrative = amal_eval.get("baseline_narrative") or data.get("narrative") or {}

    # Use rich narrative if available, otherwise baseline
    narrative = rich_narrative if rich_narrative else baseline_narrative

    # Get citations from narrative
    citations = narrative.get("all_citations", [])

    # Normalize citation format
    normalized_citations = []
    for cit in citations:
        normalized_citations.append(
            {
                "index": cit.get("id", "").strip("[]"),
                "url": cit.get("source_url", ""),
                "claim": cit.get("claim", ""),
                "source_name": cit.get("source_name", ""),
                "quote": cit.get("quote"),  # Rich narratives have quotes
            }
        )

    # Extract zakat evaluation data
    zakat_eval = data.get("zakatEvaluation") or {}
    zakat_narrative = zakat_eval.get("narrative") or {}

    # Extract strategic data (returns strategic_narrative, strategic_evaluation, strategic_citations)
    strategic_data = _extract_strategic_data(data)
    strategic_narr = strategic_data.get("strategic_narrative")

    # Build normalized structure
    return {
        "ein": ein,
        "name": data.get("name", ""),
        "tier": data.get("tier", "baseline"),
        "evaluation": {
            "amal_score": amal_eval.get("amal_score"),
            "wallet_tag": amal_eval.get("wallet_tag"),
            "confidence_tier": amal_eval.get("confidence_tier") or data.get("confidenceTier"),
            "impact_tier": amal_eval.get("impact_tier") or data.get("impactTier"),
            "zakat_classification": {
                "asnaf_category": amal_eval.get("zakat_classification") or data.get("zakatClassification"),
            },
            "pillar_scores": amal_eval.get("confidence_scores", {}),
            "score_details": amal_eval.get("score_details", {}),
            # Narratives for narrative_quality + cross_lens judges
            "baseline_narrative": baseline_narrative if baseline_narrative else None,
            "strategic_narrative": strategic_narr if strategic_narr else None,
            "zakat_narrative": zakat_narrative if zakat_narrative else None,
            "rich_strategic_narrative": amal_eval.get("rich_strategic_narrative"),
            # Scores for cross_lens judge score-tone checks
            "strategic_score": (data.get("strategicEvaluation") or {}).get("total_score"),
            "zakat_score": zakat_eval.get("total_score"),
        },
        "financials": data.get("financials", {}),
        "narrative": {
            "summary": narrative.get("summary", ""),
            "headline": narrative.get("headline", ""),
            "strengths": narrative.get("strengths", []),
            "areas_for_improvement": narrative.get("areas_for_improvement", []),
            "dimension_explanations": narrative.get("dimension_explanations", {}),
            "amal_score_rationale": narrative.get("amal_score_rationale", ""),
        },
        "citations": normalized_citations,
        # Include source attribution for factual verification
        "source_attribution": data.get("sourceAttribution", {}),
        # Strategic evaluation data (for multi-variant judge execution)
        **strategic_data,
        # Raw data for context
        "_raw": data,
    }


def get_context_from_charity(charity: dict) -> dict:
    """Extract context from the normalized charity data.

    The context provides ground truth for judges to verify against.
    """
    raw = charity.get("_raw", {})

    context = {
        "ein": charity["ein"],
        "metrics": {
            "amal_score": charity["evaluation"].get("amal_score"),
            "wallet_tag": charity["evaluation"].get("wallet_tag"),
            "pillar_scores": charity["evaluation"].get("pillar_scores", {}),
            **charity.get("financials", {}),
        },
        "source_attribution": charity.get("source_attribution", {}),
        "programs": raw.get("programs", []),
        "cause_tags": raw.get("causeTags", []),
    }

    # Add strategic evaluation context if present
    strat_eval = charity.get("strategic_evaluation", {})
    if strat_eval and strat_eval.get("total_score") is not None:
        context["metrics"]["strategic_score"] = strat_eval["total_score"]
        context["metrics"]["archetype"] = strat_eval.get("archetype")
        context["metrics"]["archetype_label"] = strat_eval.get("archetype_label")
        context["metrics"]["strategic_dimensions"] = strat_eval.get("dimensions", {})

    # Add zakat evaluation context if present
    zakat_eval = raw.get("zakatEvaluation") or {}
    if zakat_eval and zakat_eval.get("total_score") is not None:
        context["metrics"]["zakat_score"] = zakat_eval["total_score"]
        context["metrics"]["zakat_metadata"] = zakat_eval.get("metadata", {})

    return context


def validate_charities(
    charities: list[dict],
    config: JudgeConfig,
    diff_mode: bool = False,
    since_commit: str = "HEAD~1",
    persist_verdicts: bool = False,
    charity_repo: CharityRepository | None = None,
    data_repo: CharityDataRepository | None = None,
    raw_repo: RawDataRepository | None = None,
) -> dict:
    """Run validation on charities.

    Args:
        charities: List of normalized charity data
        config: Judge configuration
        diff_mode: Enable diff-based validation
        since_commit: Commit to compare against for diff mode
        persist_verdicts: Save verdicts to database for regression tracking
        charity_repo: Repository for charities table (mission, city, state, address)
        data_repo: Repository for charity_data table (founded_year, etc.)
        raw_repo: Repository for raw_scraped_data (source data for crawl/extract judges)

    Returns:
        Validation report as dict
    """
    # Create context provider from charity data itself
    charity_map = {c["ein"]: c for c in charities}

    def get_context(ein: str) -> dict:
        normalized = charity_map.get(ein, {})
        context = get_context_from_charity(normalized)

        # Add charity table data (mission, city, state, address) for BasicInfoJudge
        if charity_repo:
            charity_record = charity_repo.get(ein)
            if charity_record:
                context["charity"] = charity_record

        # Add charity_data table data (founded_year, etc.) for BasicInfoJudge
        if data_repo:
            charity_data = data_repo.get(ein)
            if charity_data:
                context["charity_data"] = charity_data

        # Add source_data from raw_scraped_data for CrawlQualityJudge/ExtractQualityJudge
        if raw_repo:
            raw_data = raw_repo.get_for_charity(ein)
            source_data = {rd["source"]: rd["parsed_json"] for rd in raw_data if rd.get("parsed_json")}
            context["source_data"] = source_data
            context["raw_sources"] = source_data  # Alias used by RecognitionDataJudge

        return context

    # Run validation
    with JudgeOrchestrator(
        config,
        diff_mode=diff_mode,
        since_commit=since_commit,
        persist_verdicts=persist_verdicts,
    ) as orchestrator:
        result = orchestrator.validate_batch(charities, context_provider=get_context)

    return result.to_dict()


def display_results(report: dict, verbose: bool = False) -> None:
    """Display validation results in a nice format."""
    console.print()

    # Summary panel
    summary = (
        f"Charities validated: {report['charities_sampled']} of {report['charities_total']}\n"
        f"Passed: {report['charities_passed']}\n"
        f"Flagged: {report['charities_flagged']}\n"
        f"Errors: {report['total_errors']}\n"
        f"Warnings: {report['total_warnings']}\n"
        f"Cost: ${report['total_cost_usd']:.4f}"
    )
    console.print(Panel(summary, title="Validation Summary", border_style="blue"))

    # Results table
    if report["results"]:
        table = Table(title="Charity Results")
        table.add_column("EIN", style="cyan")
        table.add_column("Name")
        table.add_column("Status", justify="center")
        table.add_column("Errors", justify="right")
        table.add_column("Warnings", justify="right")

        for result in report["results"]:
            status = "[green]PASS[/green]" if result["passed"] else "[red]FLAGGED[/red]"
            name = result.get("name", "")
            table.add_row(
                result["ein"],
                name[:30] + "..." if len(name) > 30 else name,
                status,
                str(result["error_count"]),
                str(result["warning_count"]),
            )

        console.print(table)

    # Show issues if verbose
    if verbose:
        for result in report["results"]:
            if result["error_count"] > 0 or result["warning_count"] > 0:
                console.print()
                console.print(f"[bold]{result['ein']} - {result['name']}[/bold]")

                for verdict in result["verdicts"]:
                    if verdict["issues"]:
                        console.print(f"  [{verdict['judge_name']}]")
                        for issue in verdict["issues"]:
                            severity_color = "red" if issue["severity"] == "error" else "yellow"
                            console.print(
                                f"    [{severity_color}]{issue['severity'].upper()}[/{severity_color}] "
                                f"{issue['field']}: {issue['message']}"
                            )


def collect_stale_sources(report: dict) -> list[dict]:
    """Scan judge results for citation errors indicating stale crawled data.

    Looks for content-mismatch errors (where the URL was reachable but the
    content doesn't support the claim) — these indicate the underlying source
    data has changed and needs re-crawling.

    HTTP errors (403, 404) are excluded since those are typically transient
    bot-blocking, not stale data.

    Returns:
        List of dicts with 'ein', 'source', and 'reason' keys.
    """
    stale: list[dict] = []
    seen = set()

    for charity in report.get("results", []):
        ein = charity.get("ein", "")
        if not ein:
            continue

        for verdict in charity.get("verdicts", []):
            if "citation" not in verdict.get("judge_name", ""):
                continue

            for issue in verdict.get("issues", []):
                # Only content-mismatch errors (not HTTP failures)
                if issue.get("severity") != "error":
                    continue

                message = issue.get("message", "")
                # Skip HTTP-level errors — those are transient
                if "URL unreachable" in message:
                    continue

                # This is a content-mismatch error: the URL was fetched
                # but the content doesn't match the claim. The source data
                # has likely changed since we last crawled.
                key = (ein, "website")
                if key not in seen:
                    seen.add(key)
                    stale.append(
                        {
                            "ein": ein,
                            "source": "website",
                            "reason": f"citation content mismatch: {message[:200]}",
                        }
                    )

    return stale


def invalidate_stale_sources(stale_sources: list[dict]) -> int:
    """Invalidate crawl cache for sources with stale data.

    Args:
        stale_sources: Output from collect_stale_sources()

    Returns:
        Number of sources invalidated
    """
    raw_repo = RawDataRepository()
    count = 0
    for entry in stale_sources:
        if raw_repo.invalidate(entry["ein"], entry["source"], entry["reason"]):  # type: ignore[attr-defined]
            count += 1
            logger.info("Invalidated %s/%s: %s", entry["ein"], entry["source"], entry["reason"])
    return count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run LLM judge validation on exported charity JSON files")
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=DEFAULT_JSON_DIR,
        help=f"Directory containing charity-*.json files (default: {DEFAULT_JSON_DIR})",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=0.1,
        help="Fraction of charities to validate (0.0-1.0, default: 0.1)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save report to JSON file",
    )
    parser.add_argument(
        "--ein",
        type=str,
        help="Validate a single charity by EIN",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed issue information",
    )
    parser.add_argument(
        "--no-citation",
        action="store_true",
        help="Disable citation validation",
    )
    parser.add_argument(
        "--no-factual",
        action="store_true",
        help="Disable factual claim validation",
    )
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="Disable score rationale validation",
    )
    parser.add_argument(
        "--no-zakat",
        action="store_true",
        help="Disable zakat classification validation",
    )
    parser.add_argument(
        "--diff",
        type=str,
        nargs="?",
        const="HEAD~1",
        default="HEAD~1",
        help="Run diff-based validation against a previous commit (default: HEAD~1). "
        "Validates only charities that changed and checks for unexplained score changes.",
    )
    parser.add_argument(
        "--no-diff",
        action="store_true",
        help="Disable diff mode and use random sampling instead.",
    )
    parser.add_argument(
        "--no-persist-verdicts",
        action="store_true",
        help="Disable persisting judge verdicts to database (enabled by default).",
    )
    parser.add_argument(
        "--no-show-regressions",
        action="store_true",
        help="Hide regression detection (shown by default).",
    )
    parser.add_argument(
        "--auto-invalidate",
        action="store_true",
        help="Invalidate crawl cache for sources with stale citation data. "
        "Forces re-crawl on next pipeline run for charities with content-mismatch errors.",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    console.print("[bold]LLM Judge Validation[/bold]")
    console.print()

    # Load charities from JSON
    console.print(f"Loading charities from: {args.json_dir}")
    charities = load_charities_from_json(args.json_dir, ein_filter=args.ein)

    if not charities:
        console.print("[yellow]No charities to validate[/yellow]")
        return

    # Set 100% sample rate for single charity
    if args.ein:
        args.sample_rate = 1.0

    console.print(f"Found {len(charities)} charities")

    # Variables for diff mode integration
    diff_mode_enabled = args.diff and not args.no_diff and not args.ein

    # Handle diff mode (default unless --no-diff or --ein specified)
    if diff_mode_enabled:
        from src.judges.diff_validator import DiffValidator, get_charities_to_validate

        console.print(f"\n[bold]Diff Mode[/bold]: Validating changes since {args.diff}")

        # Run diff validation first
        diff_validator = DiffValidator(since_commit=args.diff, include_score_history=True)
        diff_report = diff_validator.validate()

        console.print(f"Changes detected: {diff_report.charities_changed} charities")
        console.print(f"  Added: {diff_report.charities_added}")
        console.print(f"  Modified: {diff_report.charities_modified}")
        console.print(f"  Removed: {diff_report.charities_removed}")

        if diff_report.unexplained_score_changes:
            console.print(
                f"\n[yellow]⚠ Unexplained score changes: {len(diff_report.unexplained_score_changes)}[/yellow]"
            )
            for change in diff_report.unexplained_score_changes[:5]:
                severity_color = "red" if change.severity and change.severity.value == "error" else "yellow"
                trend_info = f" [{change.score_trend}]" if change.score_trend else ""
                console.print(
                    f"  [{severity_color}]{change.ein}[/{severity_color}]: "
                    f"{change.old_score} → {change.new_score} (Δ{change.score_delta}){trend_info}"
                )

        # Filter charities to only those that changed
        changed_eins = get_charities_to_validate(since_commit=args.diff)
        if changed_eins:
            charities = [c for c in charities if c["ein"] in changed_eins]
            console.print(f"\nFiltered to {len(charities)} changed charities for LLM validation")
            args.sample_rate = 1.0  # Validate all changed charities
        else:
            console.print("\n[green]No charities changed - skipping LLM validation[/green]")
            return

        console.print()

    # Show regressions (default behavior unless --no-show-regressions)
    if not args.no_show_regressions:
        from src.db.client import execute_query
        from src.db.repository import JudgeVerdictRepository

        console.print("\n[bold]Checking for Regressions[/bold]")

        # Get current commit hash
        row = execute_query("SELECT commit_hash FROM dolt_log LIMIT 1", fetch="one")
        if row and isinstance(row, dict):
            current_commit = row.get("commit_hash")
            if current_commit:
                verdict_repo = JudgeVerdictRepository()
                regressions = verdict_repo.get_regressions(since_commit=args.diff, to_commit=current_commit)

                if regressions:
                    console.print(f"[red]Found {len(regressions)} regressions:[/red]")
                    for reg in regressions[:10]:
                        console.print(f"  {reg['charity_ein']} - {reg['judge_name']}: was passing, now failing")
                else:
                    console.print("[green]No regressions found[/green]")
            else:
                console.print("[yellow]Could not determine current commit[/yellow]")
        else:
            console.print("[yellow]Could not determine current commit[/yellow]")

        console.print()

    # Build configuration
    config = JudgeConfig(
        sample_rate=args.sample_rate,
        enable_citation_judge=not args.no_citation,
        enable_factual_judge=not args.no_factual,
        enable_score_judge=not args.no_score,
        enable_zakat_judge=not args.no_zakat,
    )

    enabled = config.get_enabled_judges()
    console.print(f"Enabled judges: {', '.join(enabled)}")
    console.print(f"Sample rate: {config.sample_rate * 100:.0f}%")
    console.print()

    # Run validation
    console.print("Running validation...")
    persist_verdicts = not args.no_persist_verdicts
    if not persist_verdicts:
        console.print("[dim]Verdict persistence disabled[/dim]")

    # Initialize repositories for judge context
    charity_repo = CharityRepository()
    data_repo = CharityDataRepository()
    raw_repo = RawDataRepository()

    report = validate_charities(
        charities,
        config,
        diff_mode=diff_mode_enabled,
        since_commit=args.diff,
        persist_verdicts=persist_verdicts,
        charity_repo=charity_repo,
        data_repo=data_repo,
        raw_repo=raw_repo,
    )

    # Display results
    display_results(report, verbose=args.verbose)

    # Auto-invalidate stale crawl sources
    if args.auto_invalidate:
        stale = collect_stale_sources(report)
        if stale:
            console.print(f"\n[bold]Auto-Invalidation[/bold]: Found {len(stale)} stale source(s)")
            for entry in stale:
                console.print(f"  {entry['ein']}/{entry['source']}: {entry['reason'][:80]}")
            invalidated = invalidate_stale_sources(stale)
            console.print(f"[green]Invalidated {invalidated} source(s) — will re-crawl on next pipeline run[/green]")
        else:
            console.print("\n[dim]No stale sources detected for invalidation[/dim]")

    # Save report if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))
        )
        console.print(f"\nReport saved to: {args.output}")

    # Exit with error if any charities were flagged
    if report["charities_flagged"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

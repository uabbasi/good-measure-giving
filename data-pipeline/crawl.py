#!/usr/bin/env python3
"""
V2 Pipeline Phase 1: Crawl - FETCH raw data from all sources (no parsing).

Fetches raw HTML/JSON/XML from 6 sources and stores in raw_scraped_data.raw_html:
- ProPublica 990 filings (JSON)
- Charity Navigator (HTML)
- Candid/GuideStar (HTML)
- Form 990 Grants - Schedule I/F via ProPublica XML (XML)
- Charity Website - multi-page crawl + LLM extraction (combined*)
- BBB Wise Giving Alliance (HTML)

*Website is combined fetch+parse due to expensive LLM extraction.

Parsing happens in extract.py (Phase 2).

Pipeline:
  crawl.py (fetch) → extract.py (parse) → synthesize.py → baseline.py → export.py

Usage:
    uv run python crawl.py --charities pilot_charities.txt --workers 6
    uv run python crawl.py --ein 95-4453134  # Single charity
"""

import argparse
import os
import sys
from pathlib import Path
from threading import Lock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.collectors.orchestrator import DataCollectionOrchestrator, classify_failure
from src.constants import SOURCE_TTL_DAYS
from src.db import PhaseCacheRepository
from src.db.dolt_client import dolt, tables_for_phases
from src.db.repository import CharityRepository, RawDataRepository
from src.utils.charity_loader import load_charities_from_file
from src.utils.ein_utils import validate_and_format
from src.utils.freshness import source_freshness_state
from src.utils.logger import PipelineLogger
from src.utils.phase_cache_helper import check_phase_cache, update_phase_cache
from src.utils.worker_pool import WorkerPool

# Thread-safe printing
print_lock = Lock()


def select_stale_website_eins(
    charity_repo: CharityRepository, raw_repo: RawDataRepository, older_than_days: int | None = None
) -> list[dict]:
    """
    Select charities whose 'website' raw_scraped_data row is missing,
    failed (success=0), or older than the TTL — via source_freshness_state,
    so CLI selection and in-run freshness decisions agree.

    Args:
        charity_repo: CharityRepository (injected for testability)
        raw_repo: RawDataRepository (injected for testability)
        older_than_days: TTL override in days (default: SOURCE_TTL_DAYS["website"])

    Returns:
        List of dicts: [{"name", "ein", "website"}, ...] for stale/missing/failed EINs
    """
    ttl_days = older_than_days if older_than_days is not None else SOURCE_TTL_DAYS["website"]
    stale = []

    for charity in charity_repo.get_all():
        ein = charity["ein"]
        row = raw_repo.get_by_source(ein, "website")
        state = source_freshness_state(row, ttl_days)
        if state in {"missing", "failed", "stale"}:
            stale.append({"name": charity.get("name"), "ein": ein, "website": charity.get("website")})

    return stale


def crawl_freshness_summary(raw_repo: RawDataRepository, eins: list[str]) -> dict[str, dict]:
    """
    Per-source freshness counts across a set of EINs, for the run-end report.

    For each of the 6 sources, counts how many of the given EINs have raw
    data in each freshness state. The "website" entry additionally carries
    "website_action": the EINs a follow-up --refresh-stale run would pick
    back up (state in {missing, failed, stale}), each as a dict
    {"ein", "state", "reason"} where "reason" is the classify_failure()
    terminal marker for a "failed" row (None if the failure was transient,
    e.g. rate-limited) and None for "missing"/"stale" (those did not fail
    with an error).

    Args:
        raw_repo: RawDataRepository (injected for testability)
        eins: EINs to summarize (typically the charities processed this run)

    Returns:
        {source: {"fresh": N, "stale": N, "failed": N, "missing": N, ...}, ...}
        for each of propublica, charity_navigator, candid, form990_grants,
        website, bbb.
    """
    summary = {}
    for source, ttl_days in SOURCE_TTL_DAYS.items():
        counts = {"fresh": 0, "stale": 0, "failed": 0, "missing": 0}
        website_action = []
        for ein in eins:
            row = raw_repo.get_by_source(ein, source)
            state = source_freshness_state(row, ttl_days)
            counts[state] += 1
            if source == "website" and state in {"missing", "failed", "stale"}:
                reason = None
                if state == "failed" and row is not None:
                    reason = classify_failure(row.get("error_message") or row.get("last_failure_reason"))
                website_action.append({"ein": ein, "state": state, "reason": reason})
        if source == "website":
            counts["website_action"] = website_action
        summary[source] = counts

    return summary


def fetch_charity_data(charity, index, total, orchestrator, logger, verbose=False, force_sources=None):
    """
    Fetch raw data for a single charity (worker function for parallel execution).

    This is FETCH ONLY - no parsing. Parsing happens in extract.py.

    Args:
        charity: Dict with name, ein, website
        index: Current position in processing
        total: Total number of charities
        orchestrator: DataCollectionOrchestrator instance
        logger: PipelineLogger instance
        verbose: Show detailed output
        force_sources: Optional set of source names to force-bypass the
            freshness/failure gates for (e.g. {"website"} for --refresh-stale)

    Returns:
        dict: Result with status, charity info, and fetch report
    """
    charity_name = charity["name"]
    charity_ein = charity["ein"]
    charity_website = charity["website"]

    if verbose:
        with print_lock:
            print(f"\n[{index}/{total}] Fetching data: {charity_name}")
            print(f"  EIN: {charity_ein}")
            print(f"  Website: {charity_website}")
            print("-" * 80)

    try:
        # Fetch raw data from all sources (no parsing)
        success, report = orchestrator.fetch_charity_data(
            ein=charity_ein, website_url=charity_website, charity_name=charity_name, force_sources=force_sources
        )

        # FIX #24: Validate crawl output against phase contract
        from src.schemas.phase_contracts import validate_crawl_output

        contract = validate_crawl_output(report)
        if contract.warnings and verbose:
            with print_lock:
                for w in contract.warnings:
                    print(f"  [contract] {w}")

        if success:
            sources_succeeded = report.get("sources_succeeded", [])
            sources_failed = report.get("sources_failed", {})

            if verbose:
                with print_lock:
                    print(f"\n[P1 Fetch] [{index}/{total}] ✓ {charity_name}")
                    print(f"  Sources fetched: {len(sources_succeeded)}/6")
                    if sources_failed:
                        failed_names = list(sources_failed.keys())
                        print(f"  Sources failed: {', '.join(failed_names)}")
            else:
                with print_lock:
                    print(f"[P1 Fetch] [{index}/{total}] ✓ {charity_name[:40]} ({len(sources_succeeded)}/6)")

            return {
                "charity": charity_name,
                "ein": charity_ein,
                "status": "success",
                "sources_succeeded": len(sources_succeeded),
                "sources_failed": len(sources_failed),
            }
        else:
            with print_lock:
                if verbose:
                    print(f"\n[{index}/{total}] ✗ {charity_name}")
                    print("  Fetch failed (ProPublica required)")
                else:
                    print(f"[{index}/{total}] ✗ {charity_name[:40]}")

            return {"charity": charity_name, "ein": charity_ein, "status": "failed", "error": "Fetch failed"}

    except Exception as e:
        logger.error(f"Error fetching data for {charity_name}", exception=e)
        with print_lock:
            if verbose:
                print(f"\n[{index}/{total}] ✗ {charity_name}")
                print(f"  Error: {str(e)}")
            else:
                print(f"[{index}/{total}] ✗ {charity_name[:40]}")

        return {"charity": charity_name, "ein": charity_ein, "status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Collect charity data from multiple sources (stored in DoltDB)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--charities", type=str, help="Path to charity list file (format: EIN # Name or Name | EIN | Website)"
    )
    group.add_argument("--ein", type=str, help="Single charity EIN to collect (format: XX-XXXXXXX)")
    group.add_argument(
        "--refresh-stale",
        action="store_true",
        help="Re-crawl only the website source for EINs whose website raw data is missing, "
        "failed, or stale (see --older-than)",
    )
    parser.add_argument(
        "--older-than",
        type=int,
        default=None,
        help="Staleness TTL in days for --refresh-stale (default: SOURCE_TTL_DAYS['website'] = 30)",
    )
    parser.add_argument("--workers", type=int, default=6, help="Number of parallel workers (default: 6)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output (default: concise progress only)")
    parser.add_argument(
        "--pdf-downloads", type=int, default=10, help="Maximum PDFs to download per charity website (default: 10)"
    )
    parser.add_argument(
        "--skip",
        type=str,
        action="append",
        default=[],
        help="Skip specific data sources (can be used multiple times). Options: propublica, charity_navigator, candid, form990_grants, website, bbb",
    )
    parser.add_argument(
        "--sources",
        type=str,
        action="append",
        default=[],
        help="Explicitly re-enable a frozen source for this run (currently frozen: bbb)",
    )
    parser.add_argument(
        "--phase", type=str, default="P1:Collect", help="Pipeline phase identifier for logging (default: P1:Collect)"
    )
    parser.add_argument("--force", action="store_true", help="Force re-crawl even if cache is valid")

    args = parser.parse_args()

    # Handle single EIN mode
    if args.ein:
        is_valid, normalized_ein, error = validate_and_format(args.ein)
        if not is_valid:
            print(f"Error: Invalid EIN '{args.ein}': {error}")
            sys.exit(1)
        charities = [{"name": f"EIN {normalized_ein}", "ein": normalized_ein, "website": None}]
    elif args.refresh_stale:
        # Charity list is selected from the DB after the repos are available (see below).
        pass
    else:
        # Validate charity file exists
        if not Path(args.charities).exists():
            print(f"Error: Charity file not found: {args.charities}")
            sys.exit(1)

    # Initialize logger with appropriate log level and phase
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = PipelineLogger("data_collection", log_level=log_level, phase=args.phase)

    # Note: DoltDB connection configured via DOLT_HOST, DOLT_PORT, DOLT_USER, DOLT_DATABASE
    # Defaults work for local development (127.0.0.1:3306, root, zakaat)

    # Verify required API keys
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("GOOGLE_API_KEY must be set in environment")
        print("Error: Missing Google API key for website extraction. Set GOOGLE_API_KEY in .env")
        sys.exit(1)

    # Initialize data collection orchestrator (connects to DoltDB)
    orchestrator = DataCollectionOrchestrator(
        logger=logger,
        max_pdf_downloads=args.pdf_downloads,
        skip_sources=args.skip or [],
        include_sources=args.sources or [],
    )

    # Load charities: from the DB (--refresh-stale) or from file (default mode)
    if args.refresh_stale:
        charities = select_stale_website_eins(
            CharityRepository(), RawDataRepository(), older_than_days=args.older_than
        )
        if not charities:
            print("✓ No stale/missing/failed website rows found. Nothing to refresh.")
            sys.exit(0)
        print(f"ℹ --refresh-stale selected {len(charities)} charities with stale/missing/failed website data")
    elif not args.ein:
        try:
            charities = load_charities_from_file(args.charities, logger=logger)
        except ValueError as e:
            # Malformed EIN - fail fast per spec
            logger.error(f"Invalid input file: {e}")
            print(f"Error: {e}")
            print("Fix the charity list file and retry. Malformed EINs must be corrected.")
            sys.exit(1)
        if not charities:
            print(f"Error: No valid charities found in {args.charities}")
            sys.exit(1)

    # Build sources list (6 sources per spec)
    all_sources = ["ProPublica", "Charity Navigator", "Candid", "Form 990 Grants", "Website", "BBB"]
    source_map = {
        "propublica": "ProPublica",
        "charity_navigator": "Charity Navigator",
        "candid": "Candid",
        "form990_grants": "Form 990 Grants",
        "website": "Website",
        "bbb": "BBB",
    }
    if args.skip:
        skipped_display = [source_map.get(s, s) for s in args.skip]
        active_sources = [s for s in all_sources if s not in skipped_display]
        sources_str = ", ".join(active_sources)
        skipped_str = f" (skipping: {', '.join(skipped_display)})"
    else:
        sources_str = ", ".join(all_sources)
        skipped_str = ""

    print("=" * 80)
    print(f"DATA COLLECTION: {len(charities)} CHARITIES")
    print(f"  Sources: {sources_str}{skipped_str}")
    print(f"  Parallel workers: {args.workers}")
    print(f"  Database: DoltDB ({os.getenv('DOLT_HOST', '127.0.0.1')}:{os.getenv('DOLT_PORT', '3306')})")
    print("=" * 80)

    # Smart caching: skip charities with valid cache.
    # Disable cache reads/writes when --skip is used so partial-source runs
    # cannot create cache entries that mask full-source requirements later.
    # --refresh-stale also disables the gate: it force-bypasses freshness at the
    # source level, so the charity-level phase cache must not re-skip the very
    # EINs it selected as stale.
    cache_enabled = len(args.skip or []) == 0 and not args.refresh_stale
    cache_repo = PhaseCacheRepository()
    cache_skipped = []

    charities_to_process = []
    if cache_enabled:
        for charity in charities:
            should_run, reason = check_phase_cache(charity["ein"], "crawl", cache_repo, force=args.force)
            if not should_run:
                cache_skipped.append((charity["ein"], reason))
                print(f"⊘ {charity['name'][:40]} ({charity['ein']}): Cache hit — {reason}")
            else:
                charities_to_process.append(charity)
    else:
        charities_to_process = list(charities)
        if args.refresh_stale:
            print("ℹ Cache disabled for this run (--refresh-stale in use)")
        else:
            print("ℹ Cache disabled for this run (--skip in use)")

    if cache_skipped:
        print(f"\nSkipped {len(cache_skipped)} charities (cache valid), processing {len(charities_to_process)}\n")

    if not charities_to_process:
        print("All charities cached. Use --force to re-crawl.")
        sys.exit(0)

    # Process charities in parallel using WorkerPool
    worker_pool = WorkerPool(max_workers=args.workers, logger=logger)

    # Create worker function with fixed parameters
    force_sources = {"website"} if args.refresh_stale else None

    def process_charity(item):
        """Worker function for parallel processing."""
        charity, index = item
        return fetch_charity_data(
            charity,
            index,
            len(charities_to_process),
            orchestrator,
            logger,
            verbose=args.verbose,
            force_sources=force_sources,
        )

    # Prepare items with indices
    charity_items = [(charity, i) for i, charity in enumerate(charities_to_process, 1)]

    # Process in parallel
    parallel_results = worker_pool.map(process_charity, charity_items, desc="Fetching charity data")

    # Convert WorkerPool results to expected format and update cache
    results = []
    for success, (charity, index), result_or_error in parallel_results:
        if success:
            results.append(result_or_error)
            # Update cache on successful crawl
            if cache_enabled and result_or_error.get("status") == "success":
                update_phase_cache(result_or_error["ein"], "crawl", cache_repo)
        else:
            # Exception occurred - create error result
            results.append(
                {"charity": charity["name"], "ein": charity["ein"], "status": "error", "error": str(result_or_error)}
            )

    # Get worker pool statistics before shutdown
    pool_stats = worker_pool.get_stats()

    # Shutdown worker pool
    worker_pool.shutdown()

    # Shutdown orchestrator
    orchestrator.close()

    # Print summary
    print("\n" + "=" * 80)
    print("FETCH SUMMARY (Phase 1)")
    print("=" * 80)

    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    error_count = sum(1 for r in results if r["status"] == "error")

    total_sources = sum(r.get("sources_succeeded", 0) for r in results if r["status"] == "success")
    avg_sources = total_sources / success_count if success_count > 0 else 0

    print(f"\nTotal charities: {len(results) + len(cache_skipped)}")
    if cache_skipped:
        print(f"  ⊘ Cached: {len(cache_skipped)}")
    if len(results) > 0:
        print(f"  ✓ Success: {success_count} ({success_count / len(results) * 100:.1f}%)")
    else:
        print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Failed: {failed_count}")
    print(f"  ✗ Error: {error_count}")

    if success_count > 0:
        print("\nData Sources Fetched:")
        print(f"  Average sources per charity: {avg_sources:.1f}/6")
        print(f"  Total raw data fetched: {total_sources} source files")

    # Print worker pool statistics
    print("\nParallel Processing:")
    print(f"  Workers: {pool_stats['max_workers']}")
    print(f"  Tasks completed: {pool_stats['total_completed']}/{pool_stats['total_submitted']}")
    if pool_stats["total_completed"] > 0:
        print(
            f"  Success rate: {pool_stats['total_successful']}/{pool_stats['total_completed']} ({pool_stats['total_successful'] / pool_stats['total_completed'] * 100:.1f}%)"
        )

    # H5: blocked-sites report
    blocked = orchestrator.get_blocked_sites()
    if blocked:
        print(f"\nBlocked sites (CAPTCHA/anti-bot): {len(blocked)}")
        for b in blocked:
            print(f"  ✗ {b['ein']}: {b['url']} — {b['reason']}")

    # Per-source freshness report — surfaces staleness that a run summary
    # otherwise hides (e.g. the 149 stale websites that went unnoticed).
    freshness = crawl_freshness_summary(RawDataRepository(), [c["ein"] for c in charities_to_process])
    print("\nSource Freshness:")
    for source in SOURCE_TTL_DAYS:
        counts = freshness[source]
        display = source_map.get(source, source)
        print(f"  {display}: {counts['fresh']} fresh / {counts['stale']} stale / {counts['failed']} failed / {counts['missing']} missing")

    website_action = freshness["website"]["website_action"]
    if website_action:
        print(f"\nWebsite EINs needing refresh (missing/failed/stale): {len(website_action)}")
        for entry in website_action:
            reason = entry["reason"] or ""
            print(f"  {entry['ein']}  [{entry['state']}]  {reason}")

    if orchestrator.frozen_sources:
        frozen_str = ", ".join(sorted(orchestrator.frozen_sources))
        print(f"\nNote: frozen sources skipped this run: {frozen_str} "
              f"(existing rows kept; pass --sources {frozen_str} to re-enable)")

    # Commit changes to DoltDB
    if success_count > 0:
        commit_hash = dolt.commit(
            f"Crawl: {success_count} charities fetched, {total_sources} sources",
            tables=tables_for_phases("crawl"),
        )
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")

    print("\n✓ Fetch complete (raw content stored, parsing pending)")
    print("  Results saved to: DoltDB raw_scraped_data table")
    print("\nNext steps:")
    print("  1. Run extract phase: python extract.py")
    print("  2. Run synthesize phase: python synthesize.py")
    print("  3. Run baseline scorer: python baseline.py")

    # Hard-fail semantics: any failed/error EIN should fail the batch.
    if success_count == 0:
        logger.error("Data collection failed: no charities processed successfully")
        sys.exit(1)

    if failed_count > 0 or error_count > 0:
        logger.error(
            f"Data collection incomplete: {failed_count + error_count} charities failed ({failed_count} failed, {error_count} errored)"
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

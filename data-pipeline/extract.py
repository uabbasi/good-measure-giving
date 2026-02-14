#!/usr/bin/env python3
"""
V2 Pipeline Phase 2: Extract - Parse raw_html into validated parsed_json.

Reads raw_html from raw_scraped_data (populated by crawl.py) and calls
collector.parse() to produce validated parsed_json (Pydantic schemas).

This is MANDATORY after crawl.py - crawl only fetches, extract parses.

Pipeline:
  crawl.py (fetch) → extract.py (parse) → synthesize.py → baseline.py → export.py

Usage:
    uv run python extract.py                           # Parse all unparsed rows
    uv run python extract.py --ein 95-4453134         # Single charity
    uv run python extract.py --charities charities.txt # From file
    uv run python extract.py --source candid          # Single source
    uv run python extract.py --force                  # Re-parse even if parsed_json exists
    uv run python extract.py --workers 5              # Parallel processing
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.collectors.bbb_collector import BBBCollector
from src.collectors.candid_beautifulsoup import CandidCollector
from src.collectors.charity_navigator import CharityNavigatorCollector
from src.collectors.form990_grants import Form990GrantsCollector
from src.collectors.propublica import ProPublicaCollector
from src.collectors.web_collector import WebsiteCollector
from src.db import PhaseCacheRepository
from src.db.dolt_client import dolt
from src.db.repository import RawDataRepository
from src.utils.ein_utils import validate_and_format
from src.utils.logger import PipelineLogger
from src.utils.phase_cache_helper import check_phase_cache, update_phase_cache

# Thread-safe printing
print_lock = Lock()

# Map source names to collector classes
COLLECTORS = {
    "propublica": ProPublicaCollector,
    "charity_navigator": CharityNavigatorCollector,
    "candid": CandidCollector,
    "form990_grants": Form990GrantsCollector,
    "bbb": BBBCollector,
    "website": WebsiteCollector,
}

# Required environment variables (none for extract - LLM used in crawl, not here)
REQUIRED_ENV_VARS: list[str] = []


def check_environment() -> list[str]:
    """Check for required environment variables.

    Returns:
        List of missing variable names (empty if all present).
    """
    return [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]


def load_eins_from_file(filepath: str) -> list[str]:
    """Load EINs from a charity list file.

    Supports pipe-delimited format: Name | EIN | URL | Comments
    Also supports simple one-EIN-per-line format.

    Args:
        filepath: Path to charity list file (comments start with #).

    Returns:
        List of validated EINs.
    """
    eins = []
    seen = set()
    path = Path(filepath)
    if not path.exists():
        print(f"Error: Charity file not found: {filepath}")
        sys.exit(1)

    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse pipe-delimited format: Name | EIN | URL | ...
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                ein = parts[1]  # EIN is second field
            else:
                ein = line  # Fallback to whole line

            # Skip N/A entries
            if not ein or ein == "N/A" or ein.startswith("N/A"):
                continue

            is_valid, normalized_ein, error = validate_and_format(ein)
            if is_valid:
                if normalized_ein not in seen:
                    eins.append(normalized_ein)
                    seen.add(normalized_ein)
            else:
                print(f"Warning: Line {line_num}: Skipping invalid EIN '{ein}': {error}")

    return eins


def extract_row(
    row: dict, collectors: dict, logger: PipelineLogger, repo: RawDataRepository
) -> tuple[bool, str | None]:
    """
    Parse a single raw_scraped_data row into validated schema.

    Args:
        row: Database row with charity_ein, source, raw_content
        collectors: Dict of instantiated collectors by source name
        logger: Logger instance
        repo: Shared RawDataRepository instance (E-001: avoid creating per-row)

    Returns:
        Tuple of (success, error_message)
    """
    from src.validators.bounds_validator import validate_dict_bounds

    ein = row["charity_ein"]
    source = row["source"]
    raw_content = row.get("raw_content")

    # Website uses combined fetch+parse (LLM extraction during crawl)
    # Skip re-parsing - it already has parsed_json from crawl.py
    if source == "website":
        return False, "Website uses combined mode (already parsed in crawl)"

    if not raw_content:
        return False, "No raw_content"

    collector = collectors.get(source)
    if not collector:
        return False, f"Unknown source: {source}"

    try:
        # Call the collector's parse method
        result = collector.parse(raw_content, ein)

        if result.success:
            # E-008: Apply bounds validation to catch implausible values
            validated_data = validate_dict_bounds(result.parsed_data, ein=ein, log_warnings=True)

            # Update the database with validated parsed_json
            repo.upsert(
                charity_ein=ein,
                source=source,
                parsed_json=validated_data,
                success=True,
            )
            return True, None
        else:
            return False, result.error

    except Exception as e:
        logger.error(f"Extract failed for {ein}/{source}", exception=e)
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Extract: Parse raw data into validated schemas")
    ein_group = parser.add_mutually_exclusive_group()
    ein_group.add_argument("--ein", type=str, help="Single charity EIN to extract")
    ein_group.add_argument("--charities", type=str, help="Path to charity list file")
    parser.add_argument(
        "--source",
        type=str,
        choices=list(COLLECTORS.keys()),
        help="Extract only this source type",
    )
    parser.add_argument("--workers", type=int, default=10, help="Parallel workers (default: 10)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--force", action="store_true", help="Re-extract even if parsed_json exists")
    parser.add_argument("--phase", type=str, default="P1.5a:Extract", help="Pipeline phase identifier for logging")

    args = parser.parse_args()

    if args.source == "website":
        print("Website source uses combined fetch+extract in crawl.py; nothing to do in extract.py.")
        sys.exit(0)

    # Check required environment variables
    missing_env = check_environment()
    if missing_env:
        print(f"Error: Missing required environment variables: {', '.join(missing_env)}")
        sys.exit(1)

    # Get EINs to process
    eins = None  # None means all
    if args.ein:
        is_valid, normalized_ein, error = validate_and_format(args.ein)
        if not is_valid:
            print(f"Error: Invalid EIN '{args.ein}': {error}")
            sys.exit(1)
        eins = [normalized_ein]
    elif args.charities:
        eins = load_eins_from_file(args.charities)
        if not eins:
            print(f"Error: No valid EINs found in {args.charities}")
            sys.exit(1)

    # Initialize logger
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = PipelineLogger("extract", log_level=log_level, phase=args.phase)

    # Initialize collectors (skip website - it uses combined fetch+parse in crawl.py)
    collectors = {}
    sources_to_init = [args.source] if args.source else list(COLLECTORS.keys())

    for source in sources_to_init:
        if source == "website":
            # Website uses combined mode in crawl.py, skip initialization
            continue
        collector_class = COLLECTORS[source]
        collectors[source] = collector_class(logger=logger)

    # Get rows to process
    repo = RawDataRepository()
    if args.force:
        # Get all rows (including already parsed)
        rows = repo.get_all(eins=eins)
    else:
        # Get only unparsed rows
        rows = repo.get_unparsed(eins=eins)

    # Filter by source if specified
    if args.source:
        rows = [r for r in rows if r["source"] == args.source]
    else:
        # Website rows are already parsed during crawl (combined mode).
        rows = [r for r in rows if r["source"] != "website"]

    if not rows:
        print("No rows found to extract.")
        if eins:
            print(f"  (filtered by EINs: {len(eins)} charities)")
        if args.source:
            print(f"  (filtered by source: {args.source})")
        if not args.force:
            print("  (use --force to re-extract already parsed rows)")
        sys.exit(0)

    # Smart caching: filter out rows for EINs with valid cache
    cache_repo = PhaseCacheRepository()
    cache_skipped_eins = []

    if not args.force:
        # Group rows by EIN and check cache per-EIN
        eins_in_rows = sorted({r["charity_ein"] for r in rows})
        eins_to_skip = set()
        for ein_check in eins_in_rows:
            should_run, reason = check_phase_cache(ein_check, "extract", cache_repo)
            if not should_run:
                eins_to_skip.add(ein_check)
                cache_skipped_eins.append((ein_check, reason))
                print(f"⊘ {ein_check}: Cache hit — {reason}")

        if eins_to_skip:
            rows = [r for r in rows if r["charity_ein"] not in eins_to_skip]
            print(f"\nSkipped {len(cache_skipped_eins)} charities (cache valid), {len(rows)} rows remaining\n")

        if not rows:
            print("All charities cached. Use --force to re-extract.")
            sys.exit(0)

    print("=" * 80)
    print(f"EXTRACTION: {len(rows)} rows to parse")
    if eins:
        print(f"  EIN filter: {len(eins)} charities")
    if args.source:
        print(f"  Source filter: {args.source}")
    if args.force:
        print("  Mode: Force re-extract")
    print(f"  Workers: {args.workers}")
    print("=" * 80)

    # Process rows with parallel workers
    success_count = 0
    error_count = 0
    errors_by_source = {}
    completed = 0

    def process_row(row):
        """Process a single row and return result."""
        return row, extract_row(row, collectors, logger, repo)

    if args.workers == 1:
        # Sequential processing
        for i, row in enumerate(rows, 1):
            source = row["source"]
            charity_ein = row["charity_ein"]

            success, error = extract_row(row, collectors, logger, repo)

            if success:
                success_count += 1
                if args.verbose:
                    with print_lock:
                        print(f"[{i}/{len(rows)}] ✓ {charity_ein}/{source}")
            else:
                error_count += 1
                errors_by_source.setdefault(source, []).append((charity_ein, error))
                with print_lock:
                    if args.verbose:
                        print(f"[{i}/{len(rows)}] ✗ {charity_ein}/{source}: {error}")
                    else:
                        print(f"[{i}/{len(rows)}] ✗ {charity_ein}/{source}")
    else:
        # Parallel processing
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(process_row, row): row for row in rows}

            for future in as_completed(futures):
                completed += 1
                row, (success, error) = future.result()
                source = row["source"]
                charity_ein = row["charity_ein"]

                if success:
                    success_count += 1
                    if args.verbose:
                        with print_lock:
                            print(f"[{completed}/{len(rows)}] ✓ {charity_ein}/{source}")
                else:
                    error_count += 1
                    errors_by_source.setdefault(source, []).append((charity_ein, error))
                    with print_lock:
                        if args.verbose:
                            print(f"[{completed}/{len(rows)}] ✗ {charity_ein}/{source}: {error}")
                        else:
                            print(f"[{completed}/{len(rows)}] ✗ {charity_ein}/{source}")

    # Update cache for EINs where all rows succeeded
    eins_with_failures = set()
    for source_errors in errors_by_source.values():
        for err_ein, _ in source_errors:
            eins_with_failures.add(err_ein)

    unique_eins = sorted({r["charity_ein"] for r in rows})
    for ein_done in unique_eins:
        if ein_done not in eins_with_failures:
            update_phase_cache(ein_done, "extract", cache_repo)

    # ── Quality gate: run extract judge per charity ──
    from src.judges.inline_quality import run_quality_gate_batch

    quality_failed_eins = run_quality_gate_batch("extract", unique_eins)
    for failed_ein in quality_failed_eins:
        cache_repo.delete(failed_ein, "extract")

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)

    print(f"\nTotal rows: {len(rows)}")
    if cache_skipped_eins:
        print(f"  ⊘ Cached EINs: {len(cache_skipped_eins)}")
    print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Failed: {error_count}")

    if quality_failed_eins:
        print(f"\n  ⛔ Quality gate failures: {len(quality_failed_eins)} charities")
        print("     These charities have data errors that must be fixed before proceeding.")

    if errors_by_source:
        print("\nErrors by source:")
        for source, errs in sorted(errors_by_source.items()):
            print(f"  {source}: {len(errs)} failures")
            if args.verbose:
                for err_ein, err_msg in errs[:3]:  # Show first 3
                    print(f"    - {err_ein}: {err_msg}")
                if len(errs) > 3:
                    print(f"    ... and {len(errs) - 3} more")

    # Commit changes to DoltDB
    if success_count > 0:
        commit_hash = dolt.commit(f"Extract: {success_count} rows parsed from {len(rows)} total")
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")

    print("\n✓ Extraction complete (parsed_json populated)")
    print("\nNext steps:")
    print("  1. Run synthesize phase: python synthesize.py")
    print("  2. Run baseline scorer: python baseline.py")
    print("  3. Recommended for full flow: python streaming_runner.py --charities <file>")

    # Exit with error if quality gate failed or any extraction failed
    if quality_failed_eins:
        print(f"\n⛔ Exiting with error: {len(quality_failed_eins)} charities failed quality gate")
        sys.exit(1)
    if error_count > 0:
        print(f"\n⛔ Exiting with error: {error_count} rows failed extraction")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

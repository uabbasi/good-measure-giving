#!/usr/bin/env python3
"""Generate rich narratives with citation support.

Usage:
    uv run python rich_narrative.py --ein 95-4453134
    uv run python rich_narrative.py --charities pilot_charities.txt
    uv run python rich_narrative.py --ein 95-4453134 --force
    uv run python rich_narrative.py --charities pilot_charities.txt --workers 10
"""

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv()

from src.services.rich_narrative_generator import RichNarrativeGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def load_eins_from_file(file_path: str) -> list[str]:
    """Load EINs from pilot charities file.

    Format: Name | EIN | URL | RICH | Comments
    """
    eins = []
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                ein = parts[1].strip()
                if ein:
                    eins.append(ein)
    return eins


def main():
    parser = argparse.ArgumentParser(
        description="Generate rich narratives with citation support"
    )
    parser.add_argument(
        "--ein",
        help="Single EIN to process",
    )
    parser.add_argument(
        "--charities",
        help="Path to pilot_charities.txt file",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if rich narrative exists",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of charities to process",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers (default: 10)",
    )
    args = parser.parse_args()

    if not args.ein and not args.charities:
        parser.error("Must specify --ein or --charities")

    # Collect EINs to process
    eins = []
    if args.ein:
        eins.append(args.ein)
    if args.charities:
        eins.extend(load_eins_from_file(args.charities))

    if args.limit:
        eins = eins[:args.limit]

    logger.info(f"Processing {len(eins)} charities with {args.workers} workers")

    generator = RichNarrativeGenerator()

    success = 0
    failed = 0
    skipped = 0

    def process_ein(ein: str) -> tuple[str, str, str | None]:
        """Process a single EIN. Returns (ein, status, error_msg)."""
        try:
            result = generator.generate(ein, force=args.force)
            if result:
                citations = result.get("all_citations", [])
                summary_len = len(result.get("summary", "").split())
                return (ein, "success", f"{len(citations)} citations, {summary_len} words")
            else:
                return (ein, "skipped", None)
        except Exception as e:
            return (ein, "failed", str(e))

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_ein, ein): ein for ein in eins}

        for future in as_completed(futures):
            ein = futures[future]
            result = future.result()
            status, msg = result[1], result[2]

            if status == "success":
                logger.info(f"✓ [{success + failed + skipped + 1}/{len(eins)}] {ein}: {msg}")
                success += 1
            elif status == "skipped":
                logger.warning(f"⊘ [{success + failed + skipped + 1}/{len(eins)}] {ein}: skipped (no baseline or exists)")
                skipped += 1
            else:
                logger.error(f"✗ [{success + failed + skipped + 1}/{len(eins)}] {ein}: {msg}")
                failed += 1

    logger.info(f"\n{'='*60}")
    logger.info(f"Summary: {success} success, {skipped} skipped, {failed} failed")
    logger.info(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

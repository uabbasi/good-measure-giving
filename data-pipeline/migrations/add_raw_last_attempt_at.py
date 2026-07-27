#!/usr/bin/env python3
"""Add raw_scraped_data.last_attempt_at (soft-fail re-crawl backoff, blocker 2A).

Nullable TIMESTAMP: the "last crawl attempt" clock, separate from
scraped_at (the "last real data" clock). Existing rows are NULL on
purpose — treated as "no recent attempt" so they get one re-crawl, then
get stamped from then on. scraped_at semantics are untouched by this
migration; the 2-year aged-out drop still keys off scraped_at alone.

Usage: uv run python migrations/add_raw_last_attempt_at.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import execute_query
from src.db.dolt_client import dolt


def column_exists() -> bool:
    row = execute_query(
        """
        SELECT COUNT(*) AS n
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'raw_scraped_data'
          AND column_name = 'last_attempt_at'
        """,
        fetch="one",
    )
    return bool(row and row["n"])


def main() -> int:
    if column_exists():
        print("raw_scraped_data.last_attempt_at already exists; nothing to do")
        return 0
    execute_query(
        "ALTER TABLE raw_scraped_data ADD COLUMN last_attempt_at TIMESTAMP NULL",
        fetch="none",
    )
    dolt.commit(
        "Migration: add raw_scraped_data.last_attempt_at (soft-fail re-crawl backoff)",
        tables=("raw_scraped_data",),
    )
    print("Added raw_scraped_data.last_attempt_at (nullable; all existing rows NULL => one re-crawl, then backed off)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

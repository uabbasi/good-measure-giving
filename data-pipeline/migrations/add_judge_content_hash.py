#!/usr/bin/env python3
"""Add evaluations.judge_content_hash (content-bound judge gate).

Nullable VARCHAR(16): sha256-hex16 of the canonical judge projection
(judge_phase.build_judge_projection) captured at judge time. NULL or
mismatch fails closed at every export gate — existing rows are NULL on
purpose: their judge_score predates the hash and IS stale.

Usage: uv run python migrations/add_judge_content_hash.py
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
          AND table_name = 'evaluations'
          AND column_name = 'judge_content_hash'
        """,
        fetch="one",
    )
    return bool(row and row["n"])


def main() -> int:
    if column_exists():
        print("evaluations.judge_content_hash already exists; nothing to do")
        return 0
    execute_query(
        "ALTER TABLE evaluations ADD COLUMN judge_content_hash VARCHAR(16) NULL",
        fetch="none",
    )
    dolt.commit(
        "Migration: add evaluations.judge_content_hash (content-bound judge gate)",
        tables=("evaluations",),
    )
    print("Added evaluations.judge_content_hash (nullable; all existing rows NULL => fail closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

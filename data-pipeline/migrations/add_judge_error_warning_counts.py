#!/usr/bin/env python3
"""Add evaluations.judge_error_count / judge_warning_count (Option A publication gate).

Two nullable INT columns holding the DEDUPED judge issue counts captured at
judge time (judge_phase, from validation_result.deduplicated_issues — the same
numbers judge_score is computed from). The publication gate ships a charity
only when judge_error_count == 0 (and the content hash is fresh); warnings
never gate publication — they feed reports/editorial-queue.json. NULL fails
closed: existing rows predate the counts and ARE stale.

Idempotent: adds only the columns that are missing, so a partial prior run is
safe to re-run.

Usage: uv run python migrations/add_judge_error_warning_counts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import execute_query
from src.db.dolt_client import dolt

NEW_COLUMNS = ("judge_error_count", "judge_warning_count")


def _existing_columns() -> set[str]:
    rows = (
        execute_query(
            """
            SELECT column_name AS cn
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'evaluations'
              AND column_name IN ('judge_error_count', 'judge_warning_count')
            """,
        )
        or []
    )
    return {row["cn"] for row in rows}


def main() -> int:
    to_add = [col for col in NEW_COLUMNS if col not in _existing_columns()]
    if not to_add:
        print("evaluations.judge_error_count/judge_warning_count already exist; nothing to do")
        return 0
    for col in to_add:
        execute_query(f"ALTER TABLE evaluations ADD COLUMN {col} INT NULL", fetch="none")
    dolt.commit(
        "Migration: add evaluations.judge_error_count/judge_warning_count (Option A gate)",
        tables=("evaluations",),
    )
    print(f"Added evaluations columns: {', '.join(to_add)} (nullable INT; NULL => fail closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regenerate dolt_schema.sql from the live Dolt database.

The schema file is documentation + bootstrap input for import_dolt.py.
It drifts unless regenerated after DDL changes; this makes regeneration a
one-liner and gives humans/CI a --check mode.

Usage:
    uv run python migrations/regenerate_dolt_schema.py           # rewrite file
    uv run python migrations/regenerate_dolt_schema.py --check   # diff vs live
"""

import argparse
import difflib
import os
import sys
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

SCHEMA_PATH = Path(__file__).parent.parent / "dolt_schema.sql"

# Per-table annotation comments injected above the CREATE statement.
# NOTE: keep these free of semicolons (import_dolt splits on ';').
TABLE_ANNOTATIONS = {
    "organization_families": (
        "-- organization_families: created ad-hoc 2026-01..02 — "
        "holds real data, no code writers yet"
    ),
    "export_exclusions": (
        "-- export_exclusions: defined in ExportExclusionRepository.ensure_table "
        "(src/db/repository.py) — created lazily on first write, so it may not "
        "exist in the live DB yet; DDL below is hardcoded from that canonical "
        "source and is superseded by the live SHOW CREATE TABLE once it exists"
    ),
}

# export_exclusions is created lazily (ExportExclusionRepository.ensure_table,
# src/db/repository.py) on the first write, so it may not exist in the live DB
# yet. Hardcode its canonical DDL here so a fresh bootstrap always includes it;
# once the table exists live, generate_schema_sql() prefers the live
# SHOW CREATE TABLE output over this fallback.
FALLBACK_DDL = {
    "export_exclusions": """CREATE TABLE `export_exclusions` (
  `charity_ein` varchar(12) NOT NULL,
  `judge_score` int,
  `reason` text,
  `excluded_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`charity_ein`,`excluded_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin""",
}

HEADER = """\
-- dolt_schema.sql — GENERATED FILE. Do not hand-edit.
-- Regenerate: uv run python migrations/regenerate_dolt_schema.py
-- Verify:     uv run python migrations/regenerate_dolt_schema.py --check
-- Source: live SHOW CREATE statements from the zakaat Dolt database, plus
-- any tables listed in FALLBACK_DDL that don't exist live yet.
"""


def get_connection() -> pymysql.Connection:
    return pymysql.connect(
        host=os.environ.get("DOLT_HOST", "127.0.0.1"),
        port=int(os.environ.get("DOLT_PORT", "3306")),
        user=os.environ.get("DOLT_USER", "root"),
        password=os.environ.get("DOLT_PASSWORD", ""),
        database=os.environ.get("DOLT_DATABASE", "zakaat"),
        autocommit=True,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def generate_schema_sql(conn: pymysql.Connection) -> str:
    cursor = conn.cursor()
    cursor.execute("SHOW FULL TABLES")
    rows = cursor.fetchall()
    name_col = next(k for k in rows[0] if k.startswith("Tables_in_"))
    live_tables = {r[name_col] for r in rows if r["Table_type"] == "BASE TABLE"}
    views = sorted(r[name_col] for r in rows if r["Table_type"] == "VIEW")

    tables = sorted(live_tables | FALLBACK_DDL.keys())

    chunks = [HEADER]
    for table in tables:
        annotation = TABLE_ANNOTATIONS.get(table)
        if annotation:
            chunks.append(annotation)
        if table in live_tables:
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            ddl = cursor.fetchone()["Create Table"]
        else:
            ddl = FALLBACK_DDL[table]
        chunks.append(ddl + ";\n")
    for view in views:
        cursor.execute(f"SHOW CREATE VIEW `{view}`")
        ddl = cursor.fetchone()["Create View"]
        chunks.append(ddl + ";\n")
    cursor.close()
    return "\n".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Diff file vs live; exit 1 on drift")
    args = parser.parse_args()

    conn = get_connection()
    try:
        generated = generate_schema_sql(conn)
    finally:
        conn.close()

    n_tables = generated.count("CREATE TABLE `")
    n_views = generated.count("CREATE VIEW `")

    if args.check:
        current = SCHEMA_PATH.read_text() if SCHEMA_PATH.exists() else ""
        if current == generated:
            print(f"OK: {SCHEMA_PATH.name} matches live database ({n_tables} tables, {n_views} view(s))")
            return 0
        print(f"DRIFT: {SCHEMA_PATH.name} does not match live database:")
        sys.stdout.writelines(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=str(SCHEMA_PATH),
                tofile="live database",
            )
        )
        return 1

    SCHEMA_PATH.write_text(generated)
    print(f"Wrote {SCHEMA_PATH} ({n_tables} tables, {n_views} view(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

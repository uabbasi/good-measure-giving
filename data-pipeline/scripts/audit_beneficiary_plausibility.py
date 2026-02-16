#!/usr/bin/env python3
"""Audit beneficiary metrics for citation coverage and plausibility.

Usage:
  uv run python data-pipeline/scripts/audit_beneficiary_plausibility.py
  uv run python data-pipeline/scripts/audit_beneficiary_plausibility.py --fail-on-severe
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _safe_number(value):
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit beneficiary citation and plausibility in exported website data.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("website/data/charities"),
        help="Directory containing charity-*.json detail exports",
    )
    parser.add_argument(
        "--min-revenue-per-beneficiary",
        type=float,
        default=2.0,
        help="Flag records with revenue/beneficiary below this threshold",
    )
    parser.add_argument(
        "--max-beneficiaries",
        type=int,
        default=100_000_000,
        help="Flag records above this beneficiary count",
    )
    parser.add_argument(
        "--fail-on-severe",
        action="store_true",
        help="Exit with code 1 if severe findings exist",
    )
    args = parser.parse_args()

    files = sorted(args.data_dir.glob("charity-*.json"))
    if not files:
        print(f"No charity files found under {args.data_dir}")
        return 0

    severe_rows: list[str] = []
    missing_source_rows: list[str] = []
    total_with_beneficiaries = 0

    for path in files:
        data = json.loads(path.read_text())
        ein = str(data.get("ein") or "")
        name = str(data.get("name") or ein)
        beneficiaries = _safe_number(data.get("beneficiariesServedAnnually"))
        if beneficiaries <= 0:
            continue
        total_with_beneficiaries += 1

        source_meta = data.get("sourceAttribution", {}).get("beneficiaries_served_annually", {})
        source_url = source_meta.get("source_url") if isinstance(source_meta, dict) else None
        has_source = isinstance(source_url, str) and source_url.startswith(("http://", "https://"))
        if not has_source:
            missing_source_rows.append(f"{ein}\t{name}\tbeneficiaries={int(beneficiaries)}")

        revenue = _safe_number((data.get("financials") or {}).get("totalRevenue"))
        program = _safe_number((data.get("financials") or {}).get("programExpenses"))
        rev_per_ben = revenue / beneficiaries if revenue > 0 else 0.0
        prog_per_ben = program / beneficiaries if program > 0 else 0.0

        severe = (
            beneficiaries > args.max_beneficiaries
            or (revenue > 0 and rev_per_ben < args.min_revenue_per_beneficiary)
            or (program > 0 and prog_per_ben < args.min_revenue_per_beneficiary)
        )
        if severe:
            severe_rows.append(
                f"{ein}\t{name}\tben={int(beneficiaries)}\trev={int(revenue)}\tprog={int(program)}"
                f"\trev_per_ben={rev_per_ben:.4f}\tprog_per_ben={prog_per_ben:.4f}"
            )

    print(f"Analyzed {len(files)} charity files")
    print(f"Charities with beneficiariesServedAnnually > 0: {total_with_beneficiaries}")
    print(f"Missing beneficiary source citation: {len(missing_source_rows)}")
    print(f"Severe plausibility flags: {len(severe_rows)}")

    if missing_source_rows:
        print("\nMissing citation samples:")
        for row in missing_source_rows[:20]:
            print(f"  {row}")

    if severe_rows:
        print("\nSevere plausibility samples:")
        for row in severe_rows[:20]:
            print(f"  {row}")

    if args.fail_on_severe and severe_rows:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

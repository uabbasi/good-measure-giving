"""Detect and optionally restore charity_data fields that regressed to NULL.

Report-only by default; --apply restores the most recent non-null historical
value for each guarded field that is currently NULL. Leans on Dolt history —
no new storage. Same preserve+flag philosophy: a human confirms bug vs drop.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import CharityDataRepository, CharityRepository  # noqa: E402
from src.db.dolt_client import get_dolt  # noqa: E402
from synthesize import REGRESSION_GUARDED_FIELDS  # noqa: E402


def find_regressions(current_row: dict, history_rows: list[dict], fields) -> list[dict]:
    """Pure: for each guarded field currently NULL, find the most recent
    non-null value in history (history_rows newest-first)."""
    out: list[dict] = []
    if not current_row:
        return out
    for field in fields:
        if current_row.get(field) is not None:
            continue
        for hrow in history_rows:
            val = hrow.get(field)
            if val is not None:
                out.append(
                    {
                        "charity_ein": current_row.get("charity_ein"),
                        "field": field,
                        "current_value": None,
                        "last_good_value": val,
                        "last_good_commit": hrow.get("commit_hash") or hrow.get("dolt_commit_hash"),
                    }
                )
                break
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile regressed charity_data fields from Dolt history.")
    parser.add_argument("--ein", help="Limit to one EIN.")
    parser.add_argument("--apply", action="store_true", help="Restore last-good values (default: report only).")
    args = parser.parse_args()

    data_repo = CharityDataRepository()
    charity_repo = CharityRepository()
    dolt = get_dolt()

    eins = [args.ein] if args.ein else [c["ein"] for c in charity_repo.get_all() if c.get("ein")]
    all_flags: list[dict] = []
    for ein in eins:
        try:
            current = data_repo.get(ein)
        except Exception as e:  # best-effort Dolt reads
            print(f"  skip {ein}: failed to load charity_data ({e})")
            continue
        if not current:
            continue
        try:
            history = dolt.history("charity_data", {"charity_ein": ein}, limit=20)
        except Exception as e:  # best-effort Dolt reads
            print(f"  skip {ein}: failed to load history ({e})")
            continue
        flags = find_regressions(current, history, REGRESSION_GUARDED_FIELDS)
        for f in flags:
            all_flags.append(f)
            if args.apply:
                restored_row = dict(current)
                restored_row[f["field"]] = f["last_good_value"]
                data_repo.upsert(restored_row)
                print(f"  restored {ein}.{f['field']} = {f['last_good_value']}")

    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "data-recovery-candidates.json"
    path.write_text(json.dumps(all_flags, indent=2, default=str))
    verb = "restored" if args.apply else "candidates"
    print(f"reconcile: {len(all_flags)} {verb} across {len(eins)} charities → {path}")


if __name__ == "__main__":
    main()

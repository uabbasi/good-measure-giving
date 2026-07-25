"""Detect and optionally restore charity_data fields that regressed to NULL.

Report-only by default; --apply restores the most recent non-null historical
value for each guarded field that is currently NULL. Leans on Dolt history —
no new storage. Same preserve+flag philosophy: a human confirms bug vs drop.
"""
import argparse
import json
import sys
from datetime import date  # noqa: E402
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS  # noqa: E402
from src.db import CharityDataRepository, CharityRepository  # noqa: E402
from src.db.client import execute_query  # noqa: E402
from synthesize import REGRESSION_GUARDED_FIELDS, REPORTS_DIR  # noqa: E402


def find_regressions(current_row: dict, history_rows: list[dict], fields) -> list[dict]:
    """Pure: for each guarded field currently NULL, find the most recent
    plausible non-null value in history (history_rows newest-first).

    Two guards keep this from fabricating data:

    1. If the current metrics_json carries a value for the field — INCLUDING a
       genuine 0 — the column being NULL is not a regression. It is either the
       zero-coercion case or a live disagreement; either way, restoring a
       historical value would write a number nobody observed. ~15 of the 25
       live candidates were total_liabilities on charities whose real, current
       liabilities are 0.
    2. A candidate older than DATA_FULL_CONFIDENCE_MAX_AGE_YEARS is rejected.
       Deep history holds seed placeholders (total_revenue=100000,
       net_assets=10) that predate real collection.

    Every surviving candidate carries its commit date so a human reviewing
    reports/data-recovery-candidates.json can judge it.
    """
    out: list[dict] = []
    if not current_row:
        return out
    metrics_json = current_row.get("metrics_json") or {}
    cutoff = date.today().year - DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
    for field in sorted(fields):
        if current_row.get(field) is not None:
            continue
        if metrics_json.get(field) is not None:
            continue  # guard 1: observed value exists, column NULL is not a loss
        for hrow in history_rows:
            val = hrow.get(field)
            if val is None:
                continue
            commit_date = hrow.get("commit_date")
            if _commit_year(commit_date) is not None and _commit_year(commit_date) < cutoff:
                break  # guard 2: history newest-first, so everything deeper is older still
            out.append(
                {
                    "charity_ein": current_row.get("charity_ein"),
                    "field": field,
                    "current_value": None,
                    "last_good_value": val,
                    "last_good_commit": hrow.get("commit_hash") or hrow.get("dolt_commit_hash"),
                    "last_good_commit_date": str(commit_date) if commit_date else None,
                }
            )
            break
    return out


def _commit_year(commit_date) -> int | None:
    """Year of a dolt_history commit_date (datetime or 'YYYY-MM-DD...' string)."""
    if commit_date is None:
        return None
    if hasattr(commit_date, "year"):
        return commit_date.year
    try:
        return int(str(commit_date)[:4])
    except ValueError:
        return None


_HISTORY_COLUMNS = ["charity_ein", "commit_hash", "commit_date", "metrics_json"] + sorted(REGRESSION_GUARDED_FIELDS)

# dolt_history_charity_data emits a row per commit that touched the TABLE, not
# the row, and the pipeline commits per phase per run — so history is dense with
# unchanged duplicates. A 20-row window covered 2h40m of a 6-month history for
# EIN 31-1267559 (1032 rows) and found 0 of 25 genuine candidates. Bound it high
# enough to reach real history; the age guard in find_regressions is what keeps
# deep placeholder values from being restored.
HISTORY_SCAN_LIMIT = 2000


def load_history(ein: str) -> list[dict]:
    """Load charity_data row history, newest-first (metadata columns +
    commit_hash + commit_date).

    NOTE: deliberately NOT using get_dolt().history() — that shared helper
    orders by `dolt_commit_timestamp`, which is not a real dolt_history_*
    column. The proven column is `commit_date` (see
    src/judges/diff_validator.py:_get_score_history). Direct query here; the
    shared helper is left untouched (unknown other callers).

    NOTE: `SELECT *` on dolt_history_charity_data triggers a server-side panic
    in Dolt (`index out of range` in prolly_fields.go/historyIter) whenever
    the table's schema changed across the queried history — a known Dolt bug
    where `SELECT *` does positional field access that breaks across schema
    versions. Naming columns explicitly avoids the positional path and maps
    them correctly by name (fields missing in older commits come back NULL).
    """
    cols = ", ".join(f"`{c}`" for c in _HISTORY_COLUMNS)
    return execute_query(
        f"SELECT {cols} FROM dolt_history_charity_data WHERE charity_ein = %s "
        "ORDER BY commit_date DESC LIMIT %s",
        (ein, HISTORY_SCAN_LIMIT),
    ) or []


def reconcile(eins, data_repo, history_fn, apply: bool = False) -> tuple[list[dict], int, int]:
    """Core reconciliation loop (injectable for testing).

    history_fn(ein) -> list[dict] newest-first. Returns
    (all_flags, skipped, processed):
      - all_flags: flat list of regression flag dicts across all EINs
      - skipped:   EINs whose current/history load RAISED (systemic-failure signal)
      - processed: EINs successfully queried (current found AND history loaded)

    Under apply=True, restores are accumulated PER EIN: one full-row upsert
    carrying every restored field, issued once after all of that EIN's flags are
    collected. A per-field upsert would clobber earlier restores, since upsert is
    a full-row overwrite and the guarded set is a frozenset (nondeterministic order).
    """
    all_flags: list[dict] = []
    skipped = 0
    processed = 0
    for ein in eins:
        try:
            current = data_repo.get(ein)
        except Exception as e:  # best-effort Dolt reads; feeds systemic-failure guard
            print(f"  skip {ein}: failed to load charity_data ({e})", file=sys.stderr)
            skipped += 1
            continue
        if not current:
            continue
        try:
            history = history_fn(ein)
        except Exception as e:  # best-effort Dolt reads; feeds systemic-failure guard
            print(f"  skip {ein}: failed to load history ({e})", file=sys.stderr)
            skipped += 1
            continue
        processed += 1
        flags = find_regressions(current, history, REGRESSION_GUARDED_FIELDS)
        if not flags:
            continue
        all_flags.extend(flags)
        if apply:
            restored_row = dict(current)
            for f in flags:
                restored_row[f["field"]] = f["last_good_value"]
                print(f"  restored {ein}.{f['field']} = {f['last_good_value']}")
            data_repo.upsert(restored_row)  # ONE upsert per EIN, all fields at once
    return all_flags, skipped, processed


def is_systemic_failure(processed: int, skipped: int) -> bool:
    """True when the run's results cannot be trusted as a clean read.

    Two cases: nothing was successfully queried (processed == 0 — including
    when nothing was even attempted, e.g. a mistyped --ein), or a
    mostly-broken run where more EINs failed than succeeded. Either must exit
    non-zero rather than silently reporting an empty/partial candidate list as
    if it were complete.
    """
    if processed == 0:
        return True
    return skipped > processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile regressed charity_data fields from Dolt history.")
    parser.add_argument("--ein", help="Limit to one EIN.")
    parser.add_argument("--apply", action="store_true", help="Restore last-good values (default: report only).")
    args = parser.parse_args()

    data_repo = CharityDataRepository()
    charity_repo = CharityRepository()

    eins = [args.ein] if args.ein else [c["ein"] for c in charity_repo.get_all() if c.get("ein")]
    all_flags, skipped, processed = reconcile(eins, data_repo, load_history, apply=args.apply)

    # Systemic-failure guard: a total (or near-total) history-query failure must
    # NEVER read as "clean" or "mostly fine." If nothing was successfully
    # queried, OR more EINs failed than succeeded, the run cannot be trusted —
    # say so loudly and exit non-zero WITHOUT overwriting the report with a
    # misleading empty/partial list.
    if is_systemic_failure(processed, skipped):
        if processed == 0 and skipped == 0:
            print(
                f"reconcile: NONE of the {len(eins)} requested charities had a "
                "charity_data row — nothing was reconciled. Check the EIN(s).",
                file=sys.stderr,
            )
        elif processed == 0:
            print(
                f"reconcile: history query FAILED for all {len(eins)} charities — "
                "reconciliation did NOT run (no charity was successfully queried).",
                file=sys.stderr,
            )
        else:
            print(
                f"reconcile: history query FAILED for {skipped} of {len(eins)} charities "
                f"(only {processed} succeeded) — reconciliation did NOT run reliably.",
                file=sys.stderr,
            )
        sys.exit(1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "data-recovery-candidates.json"
    path.write_text(json.dumps(all_flags, indent=2, default=str))

    if skipped:
        print(
            f"reconcile: WARNING — {skipped} of {len(eins)} charities were SKIPPED due to "
            "read/history failures; results below are PARTIAL.",
            file=sys.stderr,
        )

    verb = "restored" if args.apply else "candidates"
    print(f"reconcile: {len(all_flags)} {verb} across {processed} queried charities → {path}")


if __name__ == "__main__":
    main()

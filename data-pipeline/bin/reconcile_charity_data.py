"""Detect and optionally restore charity_data fields that regressed to NULL.

Report-only by default; --apply restores the most recent non-null historical
value for each guarded field that is currently NULL. Leans on Dolt history —
no new storage. Same preserve+flag philosophy: a human confirms bug vs drop.
"""
import argparse
import json
import sys
from datetime import date, datetime  # noqa: E402
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS  # noqa: E402
from src.db import CharityDataRepository, CharityRepository  # noqa: E402
from src.db.client import execute_query  # noqa: E402
from src.utils.financial_coherence import FINANCIAL_FIELDS, restore_breaks_balance_sheet  # noqa: E402
from synthesize import REGRESSION_GUARDED_FIELDS, REPORTS_DIR  # noqa: E402


def find_regressions(current_row: dict, history_rows: list[dict], fields) -> list[dict]:
    """Pure: for each guarded field currently NULL, find the most recent
    plausible non-null value in history (history_rows newest-first).

    Four guards keep this from fabricating data:

    1. If the current metrics_json carries a value for the field — INCLUDING a
       genuine 0 — the column being NULL is not a regression. It is either the
       zero-coercion case or a live disagreement; either way, restoring a
       historical value would write a number nobody observed. ~15 of the 25
       live candidates were total_liabilities on charities whose real, current
       liabilities are 0.
    2. A candidate whose commit_date is older than
       DATA_FULL_CONFIDENCE_MAX_AGE_YEARS, OR whose commit_date is missing or
       unparseable, is rejected. Deep history holds seed placeholders
       (total_revenue=100000, net_assets=10) that predate real collection, and
       for a restoration tool an unknown age must fail closed, not open.
    3. An organization with no Form 990 filings (guard 3a) has no financials
       to restore, and a candidate that would contradict the current row's own
       balance sheet (guard 3b) is rejected. `source_attribution` coverage is
       deliberately NOT required here — it's populated for total_revenue on
       165/165 live rows but 0/136-165 for the other four guarded fields, so
       requiring it would reject nearly every legitimate restore.

    Every surviving candidate carries its commit date and source attribution
    (if any) so a human reviewing reports/data-recovery-candidates.json can
    judge it.
    """
    out: list[dict] = []
    if not current_row:
        return out
    metrics_json = current_row.get("metrics_json") or {}
    cutoff = _history_cutoff()
    for field in sorted(fields):
        if current_row.get(field) is not None:
            continue
        if metrics_json.get(field) is not None:
            continue  # guard 1: observed value exists, column NULL is not a loss
        if current_row.get("no_filings") and field in FINANCIAL_FIELDS:
            continue  # guard 3a: no filings means no financials to restore
        for hrow in history_rows:
            val = hrow.get(field)
            if val is None:
                continue
            commit_date = hrow.get("commit_date")
            parsed_date = _parsed_commit_date(commit_date)
            if parsed_date is None or parsed_date < cutoff:
                break  # guard 2: unknown or too-old age fails closed; history
                # newest-first, so everything deeper is older or equally unknown
            if restore_breaks_balance_sheet(current_row, field, val):
                continue  # guard 3b: this candidate is incoherent; an older one might not be
            trace, null_transitions = _value_trace(history_rows, field)
            out.append(
                {
                    "charity_ein": current_row.get("charity_ein"),
                    "field": field,
                    "current_value": None,
                    "last_good_value": val,
                    "last_good_commit": hrow.get("commit_hash") or hrow.get("dolt_commit_hash"),
                    "last_good_commit_date": str(commit_date) if commit_date else None,
                    "last_good_attribution": (hrow.get("source_attribution") or {}).get(field),
                    "value_trace": trace,
                    "null_transitions": null_transitions,
                }
            )
            break
    return out


def _value_trace(history_rows: list[dict], field: str) -> tuple[list[dict], int]:
    """Distinct (value, commit_date) trace of `field` across history_rows,
    oldest to newest, collapsing consecutive commits with the same value.

    So a human deciding whether a candidate is a real fix or a scrape
    artifact doesn't have to hand-write a dolt_history_charity_data query to
    see it — the whole trace this tool already loaded is right there in the
    report. `null_transitions` counts how many times the value flipped
    into or out of NULL, since a field that oscillates NULL<->value is a
    different (and more suspicious) shape than one that changed once.
    """
    trace: list[dict] = []
    for hrow in reversed(history_rows):  # history_rows is newest-first
        val = hrow.get(field)
        commit_date = hrow.get("commit_date")
        if trace and trace[-1]["value"] == val:
            continue  # collapse a run of unchanged commits
        trace.append({"value": val, "commit_date": str(commit_date) if commit_date else None})
    null_transitions = sum(
        1 for prev, cur in zip(trace, trace[1:]) if (prev["value"] is None) != (cur["value"] is None)
    )
    return trace, null_transitions


def _history_cutoff() -> date:
    """Oldest commit date treated as within the confidence window.

    A real calendar date, not a bare year: `date.today().year - N` gives a
    window that is 2-3 years wide depending on what day of the year this
    runs, not exactly N years. Shared with load_history's SQL bound so the
    same policy isn't expressed in two places.
    """
    today = date.today()
    try:
        return today.replace(year=today.year - DATA_FULL_CONFIDENCE_MAX_AGE_YEARS)
    except ValueError:  # today is Feb 29 and the cutoff year has no Feb 29
        return today.replace(month=2, day=28, year=today.year - DATA_FULL_CONFIDENCE_MAX_AGE_YEARS)


def _parsed_commit_date(commit_date) -> date | None:
    """Real date of a dolt_history commit_date (datetime/date or
    'YYYY-MM-DD...' string). None when missing or unparseable."""
    if commit_date is None:
        return None
    if isinstance(commit_date, datetime):
        return commit_date.date()
    if isinstance(commit_date, date):
        return commit_date
    try:
        return date.fromisoformat(str(commit_date)[:10])
    except ValueError:
        return None


_HISTORY_COLUMNS = ["charity_ein", "commit_hash", "commit_date", "source_attribution"] + sorted(
    REGRESSION_GUARDED_FIELDS
)

# Which of _HISTORY_COLUMNS are JSON-typed and need deserializing after a raw
# query. Named explicitly (rather than inferred) so adding a second JSON
# column to _HISTORY_COLUMNS is a one-line addition here, not a silent gap.
_JSON_HISTORY_COLUMNS = {"source_attribution"}


def _deserialize_json_columns(rows: list[dict]) -> list[dict]:
    """Mutate rows in place: raw SQL (unlike CharityDataRepository.get())
    doesn't deserialize JSON columns, so they come back as strings.

    A dict value (already deserialized, e.g. from a test fixture) and a None
    value both pass through unchanged. A malformed blob degrades that row's
    column to `{}` rather than raising — one unreadable attribution string
    should cost a human "no attribution for this row," not the whole EIN
    getting dropped as skipped by reconcile()'s blanket except.
    """
    for row in rows:
        for col in _JSON_HISTORY_COLUMNS:
            raw = row.get(col)
            if not isinstance(raw, str):
                continue
            try:
                row[col] = json.loads(raw)
            except (ValueError, TypeError):
                row[col] = {}
    return rows


def load_history(ein: str, query_fn=execute_query) -> list[dict]:
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

    Bounded by the same confidence-window cutoff find_regressions' age guard
    uses, rather than a row LIMIT: dolt_history_charity_data emits a row per
    commit that touched the TABLE, not the row, and the pipeline commits per
    phase per run, so history is dense with unchanged duplicates. A fixed
    LIMIT eventually falls short of that growth and fails silently (0
    candidates) — a date bound is self-limiting and never runs out.

    `query_fn` defaults to the real execute_query but is injectable so tests
    can exercise the SQL shape and deserialization without a live Dolt server.
    """
    cols = ", ".join(f"`{c}`" for c in _HISTORY_COLUMNS)
    rows = (
        query_fn(
            f"SELECT {cols} FROM dolt_history_charity_data "
            "WHERE charity_ein = %s AND commit_date >= %s "
            "ORDER BY commit_date DESC",
            (ein, _history_cutoff()),
        )
        or []
    )
    return _deserialize_json_columns(rows)


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
            attribution = dict(restored_row.get("source_attribution") or {})
            for f in flags:
                restored_row[f["field"]] = f["last_good_value"]
                if f.get("last_good_attribution"):
                    attribution[f["field"]] = f["last_good_attribution"]
                print(f"  restored {ein}.{f['field']} = {f['last_good_value']}")
            restored_row["source_attribution"] = attribution
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


def build_report(flags: list[dict], scope, run_at: str, processed: int, skipped: int) -> dict:
    """Wrap candidate rows with run provenance.

    The bare list was indistinguishable from a stale or single-EIN run: a
    fleet run flagging 12 fields could be silently replaced by a later
    `--ein` run's empty list, and the file is gitignored so there was no
    fallback.

    `processed`/`skipped` are recorded here, not just printed to stderr:
    is_systemic_failure only exits non-zero when skipped > processed, so a
    run with (say) 80 skipped and 89 processed still writes a report — and
    without these counts in the file itself, `scope` listing all 169
    requested EINs would look like a complete run to anyone opening the
    gitignored JSON after stderr scrolled away.
    """
    return {"run_at": run_at, "scope": list(scope), "processed": processed, "skipped": skipped, "rows": flags}


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
    report = build_report(
        all_flags, eins, datetime.now().isoformat(timespec="seconds"), processed=processed, skipped=skipped
    )
    path.write_text(json.dumps(report, indent=2, default=str))

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

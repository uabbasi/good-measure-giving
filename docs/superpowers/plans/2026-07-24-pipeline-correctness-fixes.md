# Pipeline Correctness Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every correctness defect found by the four-reviewer audit of branch `worktree-pipeline-review-v53-prep`, so the pipeline's write path, crawl backoff, judge gate, and published narratives are all trustworthy.

**Architecture:** These are surgical bug fixes to an existing working pipeline, not a redesign. Each task is independently testable and independently revertable. Fixes are grouped by subsystem; groups are ordered so that a fix never lands before the fix it depends on. No group restructures a module.

**Tech Stack:** Python 3.13, DoltDB (MySQL-compatible), pytest, TypeScript 5.8 / React 19 / Vite 6, vitest.

## Global Constraints

- Working directory is the worktree `/Users/uabbasi/dev/good-measure-giving/.claude/worktrees/pipeline-review-v53-prep`. Python commands run from `data-pipeline/`; frontend commands from `website/`.
- **NEVER `git push`.** Commit locally only. Pushing deploys the live website.
- Full Python suite must stay green: `cd data-pipeline && uv run pytest -q` → currently **998 passed**. Frontend: `cd website && npx vitest run` → currently **252 passed**.
- `ruff check .` must introduce **zero new findings**. Baseline on this branch is 50 errors, all pre-existing.
- **No data regeneration in this plan.** The user chose "code fixes only, no regen yet." Do NOT run `streaming_runner.py`, `synthesize.py`, `baseline.py`, `rich_phase.py`, or `export.py` against real charities. Do not modify anything under `website/data/`.
- Read-only DoltDB queries are fine for verification. Never run `bin/reconcile_charity_data.py --apply`.
- TDD throughout: write the failing test, watch it fail, implement, watch it pass, commit.
- One commit per task, message prefixed `fix(<area>):`.

## Domain gotcha (applies to every task)

In exports, `overallScore` / `scores.overall` is **Charity Navigator's** rating (fractional, e.g. 99.33). The project's own GMG Score is `amalScore` (index) / `amalEvaluation.amal_score` (detail) = impact + alignment − risk. Never read one where the other is meant.

---

## Group A — Synthesize write path (live data corruption)

These two are visible in `website/data/` right now. Task A1 must land before Group B.

### Task A1: Move the regression guard so restores reach `metrics_json`, the columns, and the size tier

**Why:** `synthesize.py:2050` snapshots `metrics_json` before the guard runs at `:2142`, so the guard restores only the top-level column. Scoring reads `metrics_json`; export reads the column. Live result on EIN `31-1267559`: exported `totalRevenue: 11342603` with `fiscalYear: null`, `metrics_json.total_revenue = None`, `no_filings: true`, and `nonprofit_size_tier: "small_nonprofit"` on $11.3M. EIN `81-3451645` ships `netAssets: 10796` against `totalAssets: 5638`.

**Files:**
- Modify: `data-pipeline/synthesize.py:93-122` (guard signature + null test), `:2029-2050` (new call site), `:2142-2152` (remove old call site)
- Test: `data-pipeline/tests/test_write_safety.py`

**Interfaces:**
- Produces: `apply_regression_guard(synthesized, metrics, prior_row) -> list[dict]` — note the **new second positional parameter**. Group B tasks do not call this function; only `synthesize.py` does.

- [ ] **Step 1: Write the failing test**

Add to `data-pipeline/tests/test_write_safety.py`:

```python
def test_guard_restores_into_metrics_so_metrics_json_agrees_with_column():
    """The guard must restore into `metrics`, not just the synthesized column.

    Regression: EIN 31-1267559 shipped total_revenue=11342603 on the column
    while metrics_json.total_revenue was None, so the scorer saw no revenue
    and the size tier was derived as small_nonprofit on $11.3M.
    """
    from types import SimpleNamespace
    from synthesize import apply_regression_guard

    metrics = SimpleNamespace(total_revenue=None, total_expenses=None,
                              total_assets=None, total_liabilities=None,
                              net_assets=None, source_attribution={})
    synthesized = SimpleNamespace(charity_ein="31-1267559", total_revenue=None,
                                  total_expenses=None, total_assets=None,
                                  total_liabilities=None, net_assets=None,
                                  source_attribution={})
    prior = {"charity_ein": "31-1267559", "total_revenue": 11342603,
             "source_attribution": {"total_revenue": {"source_name": "Charity Navigator"}}}

    flags = apply_regression_guard(synthesized, metrics, prior)

    assert metrics.total_revenue == 11342603, "restore must reach metrics (drives metrics_json + size tier)"
    assert synthesized.total_revenue == 11342603, "restore must also reach the column"
    assert [f["field"] for f in flags] == ["total_revenue"]


def test_guard_does_not_fire_on_a_genuine_zero_in_metrics():
    """A real 0 is a value, not a regression — the guard must leave it alone."""
    from types import SimpleNamespace
    from synthesize import apply_regression_guard

    metrics = SimpleNamespace(total_revenue=None, total_expenses=None,
                              total_assets=None, total_liabilities=0,
                              net_assets=None, source_attribution={})
    synthesized = SimpleNamespace(charity_ein="26-3342933", total_liabilities=None,
                                  total_revenue=None, total_expenses=None,
                                  total_assets=None, net_assets=None,
                                  source_attribution={})
    prior = {"charity_ein": "26-3342933", "total_liabilities": 861467, "source_attribution": {}}

    flags = apply_regression_guard(synthesized, metrics, prior)

    assert metrics.total_liabilities == 0, "a genuine 0 must survive"
    assert flags == [], "0 is not a non-null -> null regression"


def test_guard_report_field_order_is_deterministic():
    """REGRESSION_GUARDED_FIELDS is a frozenset; iterate sorted so the report doesn't churn."""
    from types import SimpleNamespace
    from synthesize import apply_regression_guard

    def run():
        metrics = SimpleNamespace(total_revenue=None, total_expenses=None, total_assets=None,
                                  total_liabilities=None, net_assets=None, source_attribution={})
        synthesized = SimpleNamespace(charity_ein="12-3456789", total_revenue=None,
                                      total_expenses=None, total_assets=None,
                                      total_liabilities=None, net_assets=None,
                                      source_attribution={})
        prior = {"charity_ein": "12-3456789", "total_revenue": 1, "total_expenses": 2,
                 "total_assets": 3, "total_liabilities": 4, "net_assets": 5,
                 "source_attribution": {}}
        return [f["field"] for f in apply_regression_guard(synthesized, metrics, prior)]

    assert run() == sorted(run()), "flag order must be sorted, not frozenset iteration order"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py -k "guard_restores_into_metrics or genuine_zero_in_metrics or field_order_is_deterministic" -v`
Expected: FAIL — `TypeError: apply_regression_guard() takes 2 positional arguments but 3 were given`

- [ ] **Step 3: Change the guard to restore into both objects**

Replace `data-pipeline/synthesize.py:93-122` with:

```python
def apply_regression_guard(synthesized, metrics, prior_row: dict | None) -> list[dict]:
    """Restore guarded scalar fields that recomputed non-null -> null this run.

    Returns a list of flag dicts for the editorial/regressions report. Mutates
    BOTH `metrics` and `synthesized` in place. Restoring into `metrics` is what
    makes the restore real: metrics_json is dumped from it, the top-level
    columns are overwritten from it, and nonprofit_size_tier is derived from
    the result. Restoring only the column left metrics_json disagreeing with
    the exported row (EIN 31-1267559 shipped $11.3M revenue while the scorer
    saw None and tagged it small_nonprofit).

    The null test reads `metrics`, which is authoritative at this point in
    synthesize_charity; `synthesized`'s financial columns are still the early
    pre-aggregator values and have not yet been overwritten.

    metrics_json-nested ratios are intentionally excluded — see the comment
    above REGRESSION_GUARDED_FIELDS.

    Restoring a value without its source_attribution left the field
    "has value but no source attribution" (S-J-002) — real incident: EIN
    31-1267559's total_revenue was restored this way and failed the
    synthesize quality gate. The prior attribution is still accurate
    provenance for the restored value, so it's carried forward alongside it.
    """
    if not prior_row:
        return []
    prior_attribution = prior_row.get("source_attribution") or {}
    flags: list[dict] = []
    # sorted(): REGRESSION_GUARDED_FIELDS is a frozenset, so unsorted iteration
    # made the regressions report diff-noisy between runs.
    for field in sorted(REGRESSION_GUARDED_FIELDS):
        prior_value = prior_row.get(field)
        if prior_value is None or getattr(metrics, field, None) is not None:
            continue
        setattr(metrics, field, prior_value)
        setattr(synthesized, field, prior_value)
        if field in prior_attribution:
            if synthesized.source_attribution is None:
                synthesized.source_attribution = {}
            synthesized.source_attribution[field] = prior_attribution[field]
        flags.append(
            {"charity_ein": synthesized.charity_ein, "field": field, "prior_value": prior_value}
        )
    return flags
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py -k "guard_restores_into_metrics or genuine_zero_in_metrics or field_order_is_deterministic" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Move the call site**

In `data-pipeline/synthesize.py`, DELETE the block currently at `:2142-2152`:

```python
    # Non-destructive write: never let a guarded scalar regress non-null -> null.
    if data_repo is None:
        data_repo = CharityDataRepository()
    prior_row = data_repo.get(ein)
    regression_flags = apply_regression_guard(synthesized, prior_row)
    if regression_flags:
        logging.getLogger(__name__).warning(
            f"{ein}: preserved {len(regression_flags)} regressed field(s): "
            f"{[f['field'] for f in regression_flags]}"
        )
    result["regressions"] = regression_flags
```

and INSERT this immediately after `synthesized.source_attribution = source_attribution` (line 2029), before the `metrics.is_muslim_focused = ...` block:

```python
    # Non-destructive write: never let a guarded scalar regress non-null -> null.
    # MUST run before metrics_json is dumped (below) and before the size tier is
    # derived — restoring after those left metrics_json and the column disagreeing.
    if data_repo is None:
        data_repo = CharityDataRepository()
    prior_row = data_repo.get(ein)
    regression_flags = apply_regression_guard(synthesized, metrics, prior_row)
    if regression_flags:
        logging.getLogger(__name__).warning(
            f"{ein}: preserved {len(regression_flags)} regressed field(s): "
            f"{[f['field'] for f in regression_flags]}"
        )
    result["regressions"] = regression_flags
```

Note: `synthesized.source_attribution` and the local `source_attribution` dict are the same object after line 2029, so the guard's attribution writes still flow into `metrics.source_attribution` via the existing merge at what was line 2047.

- [ ] **Step 6: Run the full suite**

Run: `cd data-pipeline && uv run pytest -q`
Expected: PASS, 998 + 3 = **1001 passed**. If any pre-existing test fails, it is asserting the old call signature — read it and fix the test to match the new behavior, do not revert the fix.

- [ ] **Step 7: Verify no new lint**

Run: `cd data-pipeline/.. && uv run ruff check . 2>&1 | tail -2`
Expected: `Found 50 errors` (unchanged from baseline)

- [ ] **Step 8: Commit**

```bash
git add data-pipeline/synthesize.py data-pipeline/tests/test_write_safety.py
git commit -m "fix(synthesize): restore regressed fields into metrics, not just the column

The guard ran after metrics_json was dumped and after nonprofit_size_tier
was derived, so a restore reached the exported column but never the object
the scorer reads. EIN 31-1267559 shipped \$11.3M revenue with
metrics_json.total_revenue=None, no_filings=true, and small_nonprofit."
```

---

### Task A2: Stop coercing a genuine `0` to NULL on the financial columns

**Why:** `synthesize.py:2054-2061` uses `int(x) if x else None`, so a charity that pays off its debt (`total_liabilities = 0`) writes NULL. 18 EINs currently have `metrics_json.total_liabilities = 0` with the column already NULL. After A1 the guard no longer masks this with a stale value, but the column is still wrong.

**Files:**
- Modify: `data-pipeline/synthesize.py:2054-2061`
- Test: `data-pipeline/tests/test_write_safety.py`

- [ ] **Step 1: Write the failing test**

```python
def test_zero_financials_persist_as_zero_not_null():
    """A real 0 must reach the column. `int(x) if x else None` turned a debt-free
    charity's total_liabilities=0 into NULL on 18 live EINs."""
    from synthesize import _coerce_financial_column

    assert _coerce_financial_column(0) == 0
    assert _coerce_financial_column(0.0) == 0
    assert _coerce_financial_column(None) is None
    assert _coerce_financial_column(1131154) == 1131154
    assert _coerce_financial_column(11342603.0) == 11342603
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::test_zero_financials_persist_as_zero_not_null -v`
Expected: FAIL — `ImportError: cannot import name '_coerce_financial_column'`

- [ ] **Step 3: Add the helper and use it**

Add near `apply_regression_guard` in `data-pipeline/synthesize.py`:

```python
def _coerce_financial_column(value) -> int | None:
    """int() a financial value, preserving a genuine 0.

    `int(x) if x else None` treated 0 as missing, so a debt-free charity wrote
    NULL for total_liabilities and the regression guard then restored last
    period's non-zero value over it.
    """
    return None if value is None else int(value)
```

Replace `data-pipeline/synthesize.py:2054-2061` with:

```python
    synthesized.total_revenue = _coerce_financial_column(metrics.total_revenue)
    synthesized.total_expenses = _coerce_financial_column(metrics.total_expenses)
    synthesized.program_expenses = _coerce_financial_column(metrics.program_expenses)
    synthesized.admin_expenses = _coerce_financial_column(metrics.admin_expenses)
    synthesized.fundraising_expenses = _coerce_financial_column(metrics.fundraising_expenses)
    synthesized.total_assets = _coerce_financial_column(metrics.total_assets)
    synthesized.total_liabilities = _coerce_financial_column(metrics.total_liabilities)
    synthesized.net_assets = _coerce_financial_column(metrics.net_assets)
```

- [ ] **Step 4: Check the size-tier derivation still reads correctly**

`synthesized.nonprofit_size_tier` at `:2082-2087` uses `if synthesized.total_revenue and ...`. With revenue `0` that correctly falls through to `small_nonprofit`, which is right. Leave it. Confirm by reading the block — no change needed.

- [ ] **Step 5: Run the full suite**

Run: `cd data-pipeline && uv run pytest -q`
Expected: PASS, 1002 passed.

- [ ] **Step 6: Commit**

```bash
git add data-pipeline/synthesize.py data-pipeline/tests/test_write_safety.py
git commit -m "fix(synthesize): preserve a genuine 0 on financial columns

int(x) if x else None wrote NULL for a real zero. 18 EINs have
metrics_json.total_liabilities=0 with a NULL column today."
```

---

### Task A3: Never restore a value that contradicts the current row

**Why:** The guard restores ONE field from the prior DB row — a prior fiscal year — while its siblings come from the current run. That produces balance sheets that cannot exist. Verified live on EIN `81-3451645`:

| field | column | metrics_json | attributed |
|---|---|---|---|
| total_assets | 5638 | 5638 | no |
| total_liabilities | None | 0 | no |
| net_assets | **10796** | **None** | no |
| total_revenue | 32150 | 32150 | yes |

`net_assets` is `None` in `metrics_json` and `10796` on the column — i.e. restored — while `total_assets = 5638` is current. Net assets exceeding total assets is impossible with non-negative liabilities, and that row is **published today**. Task A1 widens the blast radius: the mixed-vintage value now reaches `metrics_json`, so the scorer sees it too.

A second, related defect: **7 live charities carry financials while `no_filings = 1`** — `20-8085421`, `23-7065716`, `31-1267559`, `83-0668931`, `88-2454707`, `93-1556038`, `99-3373484`. ProPublica found no Form 990 at all for these, so there are no financials to restore; a restore invents revenue for an organization that never filed. Note `31-1267559` and `88-2454707` are two of the three EINs from the Task A1 finding — this is a real mechanism, not a hypothetical.

**Design:** reject the restore rather than restoring-then-flagging. A missing value renders as absent, which is honest; a mixed-vintage value renders as a specific wrong number, which is not. Every rejection is still recorded in the regressions report so a human sees it.

**Files:**
- Create: `data-pipeline/src/utils/financial_coherence.py`
- Modify: `data-pipeline/synthesize.py` (`apply_regression_guard`)
- Test: `data-pipeline/tests/test_write_safety.py`

**Interfaces (Task B4 consumes these — keep the names and signatures exactly):**
- `FINANCIAL_FIELDS: frozenset[str]`
- `balance_sheet_violations(total_assets, total_liabilities, net_assets) -> list[str]`
- `restore_breaks_balance_sheet(row: dict, field: str, value) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
class TestFinancialCoherence:
    def test_net_assets_above_total_assets_is_a_violation(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(5638, None, 10796)

    def test_a_coherent_balance_sheet_has_no_violations(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(28413661, 1131154, 27282507) == []

    def test_unknown_values_cannot_violate(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(None, None, None) == []
        assert balance_sheet_violations(None, None, 10796) == []

    def test_zero_liabilities_is_evaluated_not_skipped(self):
        """A genuine 0 is a value — Task A2 made sure it survives."""
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(5638, 0, 10796)
        assert balance_sheet_violations(5638, 0, 5638) == []

    def test_identity_allows_small_rounding_slack(self):
        from src.utils.financial_coherence import balance_sheet_violations
        assert balance_sheet_violations(1_000_000, 400_000, 600_001) == []
        assert balance_sheet_violations(1_000_000, 400_000, 900_000)


class TestGuardRejectsIncoherentRestores:
    def _run(self, prior, current_metrics, no_filings=0):
        from types import SimpleNamespace
        from synthesize import apply_regression_guard
        metrics = SimpleNamespace(source_attribution={}, **current_metrics)
        synthesized = SimpleNamespace(charity_ein="81-3451645", source_attribution={},
                                      no_filings=no_filings, **current_metrics)
        flags = apply_regression_guard(synthesized, metrics, prior)
        return metrics, flags

    def test_restore_that_would_exceed_total_assets_is_rejected(self):
        """EIN 81-3451645 publishes net_assets 10796 against total_assets 5638."""
        metrics, flags = self._run(
            prior={"charity_ein": "81-3451645", "net_assets": 10796, "source_attribution": {}},
            current_metrics={"total_assets": 5638, "total_liabilities": None,
                             "net_assets": None, "total_revenue": 32150,
                             "total_expenses": None},
        )
        assert metrics.net_assets is None, "an incoherent restore must be refused"
        assert any(f.get("rejected") for f in flags), "and must still be reported"

    def test_a_coherent_restore_still_happens(self):
        metrics, flags = self._run(
            prior={"charity_ein": "x", "net_assets": 4000, "source_attribution": {}},
            current_metrics={"total_assets": 5638, "total_liabilities": 1000,
                             "net_assets": None, "total_revenue": 32150,
                             "total_expenses": None},
        )
        assert metrics.net_assets == 4000
        assert not any(f.get("rejected") for f in flags)

    def test_no_filings_org_gets_no_financial_restore(self):
        """31-1267559 and 88-2454707 carry financials with no_filings=1 today."""
        metrics, flags = self._run(
            prior={"charity_ein": "31-1267559", "total_revenue": 11342603,
                   "source_attribution": {}},
            current_metrics={"total_assets": None, "total_liabilities": None,
                             "net_assets": None, "total_revenue": None,
                             "total_expenses": None},
            no_filings=1,
        )
        assert metrics.total_revenue is None
        assert any(f.get("rejected") for f in flags)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py -k "FinancialCoherence or GuardRejectsIncoherent" -v`
Expected: FAIL — `ModuleNotFoundError: src.utils.financial_coherence`

- [ ] **Step 3: Create the shared module**

```python
"""Deterministic coherence checks on a charity's financial columns.

Shared by synthesize's regression guard and the recovery tool: both restore a
historical value onto a row whose other fields came from a different run, and
both must refuse a restore that produces a balance sheet which cannot exist.
"""

from typing import Optional

FINANCIAL_FIELDS = frozenset(
    {"total_revenue", "total_expenses", "total_assets", "total_liabilities", "net_assets"}
)

# Sources round and restate; only flag a gap too large to be rounding.
_IDENTITY_TOLERANCE_RATIO = 0.01


def balance_sheet_violations(
    total_assets: Optional[float],
    total_liabilities: Optional[float],
    net_assets: Optional[float],
) -> list[str]:
    """Names of balance-sheet invariants this triple breaks. Empty == coherent.

    Unknown (None) values cannot violate anything — absence is not a
    contradiction. A genuine 0 IS evaluated (Task A2 made zeros survive).
    """
    out: list[str] = []
    if total_assets is not None and net_assets is not None and net_assets > total_assets:
        out.append("net_assets_exceeds_total_assets")
    if total_assets is not None and total_liabilities is not None and total_liabilities > total_assets:
        out.append("total_liabilities_exceeds_total_assets")
    if total_assets is not None and total_liabilities is not None and net_assets is not None:
        expected = total_assets - total_liabilities
        slack = max(abs(total_assets), 1.0) * _IDENTITY_TOLERANCE_RATIO
        if abs(expected - net_assets) > slack:
            out.append("assets_minus_liabilities_not_net_assets")
    return out


def restore_breaks_balance_sheet(row: dict, field: str, value) -> bool:
    """True if writing `value` into `row[field]` would create a violation the
    row does not already have.

    Only NEW violations block a restore — a row that is already incoherent for
    reasons of its own is a separate problem, and refusing to restore would not
    fix it.
    """
    if field not in {"total_assets", "total_liabilities", "net_assets"}:
        return False
    current = {k: row.get(k) for k in ("total_assets", "total_liabilities", "net_assets")}
    before = set(balance_sheet_violations(**current))
    after = set(balance_sheet_violations(**{**current, field: value}))
    return bool(after - before)
```

- [ ] **Step 4: Use it in the guard**

In `synthesize.py`'s `apply_regression_guard`, before restoring a field:

- skip when `getattr(synthesized, "no_filings", None)` is truthy and `field in FINANCIAL_FIELDS`;
- skip when `restore_breaks_balance_sheet(<the current metrics values>, field, prior_value)`.

In both cases append a flag carrying `"rejected": <reason>` instead of restoring, so the regressions report records the refusal. Restored (non-rejected) flags keep their existing shape — add `"rejected": None` to them so every flag has the same keys.

Build the row passed to `restore_breaks_balance_sheet` from `metrics` (the authoritative object at that point), not from `synthesized`.

- [ ] **Step 5: Run the tests and the full suite**

Run: `cd data-pipeline && uv run pytest -q`
Expected: green, and the count rises by the number of new tests. `TestSynthesizeCharityOrdering` must still pass — do not move the guard call.

- [ ] **Step 6: Verify against live data, read-only**

Query `charity_data` for the 7 `no_filings=1` EINs listed above and for `81-3451645`, and confirm your predicate would have refused the restores that produced their current state. This does not repair the published rows — that needs a re-synthesize the user has deferred — but it must demonstrate the fix would have prevented them. Report the real output.

- [ ] **Step 7: Commit**

```bash
git add data-pipeline/src/utils/financial_coherence.py data-pipeline/synthesize.py data-pipeline/tests/test_write_safety.py
git commit -m "fix(synthesize): refuse restores that contradict the current row

The guard restored one field from a prior fiscal year while its siblings
came from the current run, publishing balance sheets that cannot exist --
81-3451645 ships net_assets 10796 against total_assets 5638. It also
restored financials onto orgs ProPublica shows as never having filed
(7 live charities carry financials with no_filings=1). Refuse both, and
report the refusal rather than silently shipping a wrong number."
```

---

## Group B — Recovery tool (`bin/reconcile_charity_data.py`)

**Ordering:** Group A must be committed first. The window widening and the plausibility guard must land in the SAME commit (Task B1) — widening the history window without the guard turns a no-op tool into a corrupting one.

### Task B1: Widen the history search AND add the provenance/plausibility guard

**Why:** `LIMIT 20` covers 2h40m of a six-month history (EIN 31-1267559 has 1032 history rows), so the tool finds **0 of 25** real candidates. But `find_regressions` accepts any non-null as "last good" with no age or provenance check — the deeper candidates include seed placeholders (`total_revenue = 100000`, `net_assets = 10`), and ~15 are `total_liabilities` on exactly the EINs whose current `0` is correct after Task A2.

**Files:**
- Modify: `data-pipeline/bin/reconcile_charity_data.py:19-41` (`find_regressions`), `:44-69` (`load_history`)
- Test: `data-pipeline/tests/test_reconcile.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_find_regressions_skips_field_when_current_metrics_json_has_a_value():
    """After the zero-coercion fix, a NULL column with metrics_json=0 is not a
    regression — it's a correctly-observed zero. Restoring would fabricate debt."""
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "26-3342933", "total_liabilities": None,
               "metrics_json": {"total_liabilities": 0}}
    history = [{"total_liabilities": 861467, "commit_hash": "abc", "commit_date": "2026-03-09"}]

    assert find_regressions(current, history, {"total_liabilities"}) == []


def test_find_regressions_rejects_a_candidate_older_than_the_confidence_window():
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "93-2136609", "total_revenue": None, "metrics_json": {}}
    history = [{"total_revenue": 100000, "commit_hash": "old", "commit_date": "2019-01-25"}]

    assert find_regressions(current, history, {"total_revenue"}) == []


def test_find_regressions_reports_the_candidate_age_for_human_review():
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "12-3456789", "total_revenue": None, "metrics_json": {}}
    history = [{"total_revenue": 5_000_000, "commit_hash": "abc123", "commit_date": "2026-07-01"}]

    flags = find_regressions(current, history, {"total_revenue"})

    assert len(flags) == 1
    assert flags[0]["last_good_value"] == 5_000_000
    assert flags[0]["last_good_commit_date"] == "2026-07-01"


def test_find_regressions_scans_past_the_twentieth_history_row():
    """The real last-good value sat at depth 437-1017 on live data; a 20-row
    window found 0 of 25 genuine candidates."""
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "12-3456789", "total_revenue": None, "metrics_json": {}}
    history = [{"total_revenue": None, "commit_hash": f"h{i}", "commit_date": "2026-07-01"}
               for i in range(30)]
    history[25] = {"total_revenue": 7_000_000, "commit_hash": "deep", "commit_date": "2026-06-01"}

    flags = find_regressions(current, history, {"total_revenue"})

    assert len(flags) == 1 and flags[0]["last_good_commit"] == "deep"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd data-pipeline && uv run pytest tests/test_reconcile.py -k "skips_field_when_current or older_than_the_confidence or reports_the_candidate_age or scans_past_the_twentieth" -v`
Expected: FAIL — the first three fail on assertions; the fourth passes already (`find_regressions` itself has no limit — the limit is in `load_history`). Confirm which fail before implementing.

- [ ] **Step 3: Add the guards to `find_regressions`**

Replace `data-pipeline/bin/reconcile_charity_data.py:19-41` with:

```python
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
```

Add to the imports at the top of the file:

```python
from datetime import date  # noqa: E402
from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS  # noqa: E402
```

- [ ] **Step 4: Widen the history window**

`load_history` must also select `metrics_json` so guard 1 has data, and stop truncating at 20. Replace the `execute_query` call in `data-pipeline/bin/reconcile_charity_data.py:64-69` with:

```python
    cols = ", ".join(f"`{c}`" for c in _HISTORY_COLUMNS)
    return execute_query(
        f"SELECT {cols} FROM dolt_history_charity_data WHERE charity_ein = %s "
        "ORDER BY commit_date DESC LIMIT %s",
        (ein, HISTORY_SCAN_LIMIT),
    ) or []
```

and add above `load_history`:

```python
# dolt_history_charity_data emits a row per commit that touched the TABLE, not
# the row, and the pipeline commits per phase per run — so history is dense with
# unchanged duplicates. A 20-row window covered 2h40m of a 6-month history for
# EIN 31-1267559 (1032 rows) and found 0 of 25 genuine candidates. Bound it high
# enough to reach real history; the age guard in find_regressions is what keeps
# deep placeholder values from being restored.
HISTORY_SCAN_LIMIT = 2000
```

- [ ] **Step 5: Run the tests**

Run: `cd data-pipeline && uv run pytest tests/test_reconcile.py -v`
Expected: PASS (all, including the 4 new ones)

- [ ] **Step 6: Verify against the live DB, read-only**

Run: `cd data-pipeline && uv run python bin/reconcile_charity_data.py`
Expected: exits 0 and reports a candidate count. Read `reports/data-recovery-candidates.json` and confirm every entry has a `last_good_commit_date` within the confidence window and that no entry is a `total_liabilities` restore on an EIN whose `metrics_json.total_liabilities` is 0. **Do NOT run `--apply`.**

- [ ] **Step 7: Run the full suite and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1006 passed
git add data-pipeline/bin/reconcile_charity_data.py data-pipeline/tests/test_reconcile.py
git commit -m "fix(recovery): scan real history depth, reject implausible candidates

LIMIT 20 covered 2h40m of a 6-month history and found 0 of 25 genuine
candidates. Widening it alone would have restored seed placeholders
(total_revenue=100000, net_assets=10) and fabricated liabilities on ~15
charities whose current 0 is correct, so the age + metrics_json guards
land in the same commit."
```

---

### Task B3: Treat "queried nothing" as a systemic failure, and stop clobbering the report

**Why:** `is_systemic_failure(processed=0, skipped=0)` returns `False` because of the `skipped > 0 and` prefix, so `--ein 99-9999999` (a typo) exits 0, prints "0 candidates," and overwrites the previous run's real candidate list with `[]`.

**Files:**
- Modify: `data-pipeline/bin/reconcile_charity_data.py:118-126`, `:129-173` (main)
- Test: `data-pipeline/tests/test_reconcile.py`

- [ ] **Step 1: Write the failing test**

```python
def test_processed_zero_is_systemic_even_with_no_skips():
    """--ein with a typo queried nothing; exiting 0 read as a clean bill of health."""
    from bin.reconcile_charity_data import is_systemic_failure

    assert is_systemic_failure(processed=0, skipped=0) is True
    assert is_systemic_failure(processed=0, skipped=5) is True
    assert is_systemic_failure(processed=1, skipped=5) is True
    assert is_systemic_failure(processed=10, skipped=0) is False
    assert is_systemic_failure(processed=10, skipped=2) is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd data-pipeline && uv run pytest tests/test_reconcile.py::test_processed_zero_is_systemic_even_with_no_skips -v`
Expected: FAIL — `assert False is True` on the first case

- [ ] **Step 3: Fix the predicate**

Replace the body of `is_systemic_failure` (`:118-126`) with:

```python
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
```

- [ ] **Step 4: Update `main`'s message for the no-skip case**

In `main`, the `processed == 0` branch currently says "history query FAILED for all N charities". That is wrong when `skipped == 0`. Change the `if processed == 0:` branch to:

```python
        if processed == 0 and skipped == 0:
            print(
                f"reconcile: NONE of the {len(eins)} requested charities had a "
                "charity_data row — nothing was reconciled. Check the EIN(s).",
                file=sys.stderr,
            )
        elif processed == 0:
```

- [ ] **Step 5: Guard the report write**

The report must not be overwritten by a run that reconciled nothing. The `sys.exit(1)` already happens before `REPORTS_DIR.mkdir(...)`, so this is already correct — confirm by reading `:146-163` and make no change.

- [ ] **Step 6: Verify the real behavior**

Run: `cd data-pipeline && uv run python bin/reconcile_charity_data.py --ein 99-9999999; echo "exit=$?"`
Expected: `exit=1` and the "NONE of the 1 requested charities" message. Confirm `reports/data-recovery-candidates.json` was NOT modified (`git status` / file mtime).

- [ ] **Step 7: Run the full suite and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1007 passed
git add data-pipeline/bin/reconcile_charity_data.py data-pipeline/tests/test_reconcile.py
git commit -m "fix(recovery): a run that queried nothing is a failure, not a clean report"
```

---

### Task B4: Carry `source_attribution` through a restore, and stamp the report

**Why:** `--apply` builds `restored_row = dict(current)`, keeping the *current* attribution, which by construction lacks the restored field — producing exactly the "has value but no source attribution" (S-J-002) state that `apply_regression_guard` works around. Separately, `reports/*.json` is truncated by every run including single-EIN ones, and the file is gitignored so there is no fallback.

**Files:**
- Modify: `data-pipeline/bin/reconcile_charity_data.py` (`_HISTORY_COLUMNS`, `find_regressions`, `reconcile`, `main`), `data-pipeline/synthesize.py:2161-2174` (`write_synthesize_regressions`)
- Test: `data-pipeline/tests/test_reconcile.py`, `data-pipeline/tests/test_write_safety.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_restore_carries_source_attribution_from_the_same_commit():
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "12-3456789", "total_revenue": None, "metrics_json": {},
               "source_attribution": {}}
    history = [{"total_revenue": 5_000_000, "commit_hash": "abc", "commit_date": "2026-07-01",
                "source_attribution": {"total_revenue": {"source_name": "ProPublica"}}}]

    flags = find_regressions(current, history, {"total_revenue"})

    assert flags[0]["last_good_attribution"] == {"source_name": "ProPublica"}


def test_report_is_stamped_with_run_scope_and_time():
    from bin.reconcile_charity_data import build_report

    report = build_report(flags=[{"field": "total_revenue"}], scope=["12-3456789"], run_at="2026-07-24T12:00:00")

    assert report["scope"] == ["12-3456789"]
    assert report["run_at"] == "2026-07-24T12:00:00"
    assert report["rows"] == [{"field": "total_revenue"}]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_reconcile.py -k "carries_source_attribution or stamped_with_run_scope" -v`
Expected: FAIL — `KeyError: 'last_good_attribution'` and `ImportError: cannot import name 'build_report'`

- [ ] **Step 3: Add `source_attribution` to the history columns**

Change `_HISTORY_COLUMNS` (`:44`) to:

```python
_HISTORY_COLUMNS = ["charity_ein", "commit_hash", "commit_date", "metrics_json", "source_attribution"] + sorted(
    REGRESSION_GUARDED_FIELDS
)
```

- [ ] **Step 4: Carry attribution into the flag AND require it (guard 3)**

In `find_regressions`, inside the appended dict, add:

```python
                    "last_good_attribution": (hrow.get("source_attribution") or {}).get(field),
```

Then add **guard 3**, from `src/utils/financial_coherence.py` (created in Task A3 — that task must land first).

**A rejected approach, recorded so nobody re-proposes it.** The obvious third guard is "require a `source_attribution` entry for the field." It is **wrong**. Measured across all 169 live `charity_data` rows:

| field | attributed / non-null |
|---|---|
| total_revenue | **165 / 165** |
| total_expenses | 0 / 165 |
| total_assets | 0 / 161 |
| total_liabilities | 0 / 136 |
| net_assets | 0 / 156 |

Attribution is populated for `total_revenue` and nothing else, so requiring it would reject **every legitimate restore** for four of the five guarded fields. Do not add it.

Use two deterministic checks against the **current** row instead — no new data, both columns already loaded:

```python
        # Guard 3a: an organization with no Form 990 filings has no financials to
        # restore. Measured live: 7 charities carry financials with no_filings=1
        # (20-8085421, 23-7065716, 31-1267559, 83-0668931, 88-2454707, 93-1556038,
        # 99-3373484) — restoring invents revenue for an org that never filed.
        if current_row.get("no_filings") and field in FINANCIAL_FIELDS:
            continue
```

and, per candidate, before appending:

```python
            # Guard 3b: reject a candidate that would contradict the current row's
            # own balance sheet — e.g. net_assets greater than total_assets, which
            # is impossible with non-negative liabilities.
            if restore_breaks_balance_sheet(current_row, field, val):
                continue
```

- [ ] **Step 4b: Add the guard-3 tests**

```python
def test_no_filings_org_gets_no_financial_restore():
    """An org ProPublica shows as never having filed has no financials to restore."""
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "93-2136609", "total_revenue": None,
               "metrics_json": {}, "no_filings": 1}
    history = [{"total_revenue": 100000, "commit_hash": "cn",
                "commit_date": "2026-01-25"}]

    assert find_regressions(current, history, {"total_revenue"}) == []


def test_candidate_exceeding_current_total_assets_is_rejected():
    """net_assets > total_assets is impossible with non-negative liabilities."""
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "81-2566656", "net_assets": None,
               "metrics_json": {}, "no_filings": 0, "total_assets": 23205}
    history = [{"net_assets": 100000, "commit_hash": "cn", "commit_date": "2026-02-08"}]

    assert find_regressions(current, history, {"net_assets"}) == []


def test_a_coherent_in_window_candidate_still_survives():
    """The guards must not reject everything — one real candidate must get through."""
    from bin.reconcile_charity_data import find_regressions

    current = {"charity_ein": "83-1794093", "net_assets": None,
               "metrics_json": {}, "no_filings": 0, "total_assets": 116544}
    history = [{"net_assets": 10222, "commit_hash": "real", "commit_date": "2026-03-07"}]

    flags = find_regressions(current, history, {"net_assets"})
    assert len(flags) == 1 and flags[0]["last_good_value"] == 10222
```

- [ ] **Step 4c: Re-verify against the live DB, read-only**

Run `uv run python bin/reconcile_charity_data.py` (NEVER `--apply`). Expect the candidate count to drop from **5 to 1**, the survivor being `83-1794093 / net_assets` — the one genuinely ambiguous case (the org files, `total_assets = 116544`, and history shows `115000 → 10222` overwritten by `100000`). Report the real output. If the count is not 1, investigate and report rather than tuning the guard to force the number.

- [ ] **Step 4d: Replace the row LIMIT with a date bound**

`HISTORY_SCAN_LIMIT = 2000` has only ~2x headroom (deepest real history is 1034 rows for `20-3069841`, accumulating ~170 rows/month/EIN), so it is exhausted around early 2027 — and it fails **silently**, reverting to "0 candidates," which is the exact bug Task B1 fixed. Replace the row limit with a date predicate using the same cutoff the age guard already computes:

```python
        f"SELECT {cols} FROM dolt_history_charity_data "
        "WHERE charity_ein = %s AND commit_date >= %s "
        "ORDER BY commit_date DESC",
```

This makes the window self-limiting and removes the duplicate expression of the same policy in two places. Delete `HISTORY_SCAN_LIMIT`.

- [ ] **Step 4e: Drop `metrics_json` from `_HISTORY_COLUMNS`**

Guard 1 reads `current_row["metrics_json"]` (from `data_repo.get(ein)`), never a history row's. The column is never read from history — verify with grep — and it materializes ~21MB of JSON per EIN. Remove it from `_HISTORY_COLUMNS`; keep `source_attribution` (Step 3 uses it for the restore's provenance).

- [ ] **Step 5: Apply the attribution in `reconcile`**

In `reconcile`'s `if apply:` block, replace the loop body so attribution rides along:

```python
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
```

- [ ] **Step 6: Add `build_report` and use it in `main`**

```python
def build_report(flags: list[dict], scope, run_at: str) -> dict:
    """Wrap candidate rows with run provenance.

    The bare list was indistinguishable from a stale or single-EIN run: a
    fleet run flagging 12 fields could be silently replaced by a later
    `--ein` run's empty list, and the file is gitignored so there was no
    fallback.
    """
    return {"run_at": run_at, "scope": list(scope), "rows": flags}
```

In `main`, replace the write with:

```python
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "data-recovery-candidates.json"
    report = build_report(all_flags, eins, datetime.now().isoformat(timespec="seconds"))
    path.write_text(json.dumps(report, indent=2, default=str))
```

Add `from datetime import date, datetime  # noqa: E402` to the imports (merging with the `date` import from Task B1).

- [ ] **Step 7: Do the same for the synthesize regressions report**

Replace the body of `write_synthesize_regressions` in `data-pipeline/synthesize.py:2161-2174`:

```python
def write_synthesize_regressions(rows: list[dict], reports_dir: Path = REPORTS_DIR, scope=None) -> Path:
    """Write preserved-regression flags to reports/synthesize-regressions.json.

    Wrapped with run provenance: a bare list let a later single-EIN run
    silently replace a fleet run's 12 flags with an empty one, and the file is
    gitignored so nothing recovered them.

    Each row: {charity_ein, field, prior_value}. Internal-only editorial signal
    — a human confirms bug vs genuine drop. Never gates anything.
    """
    import json
    from datetime import datetime

    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "synthesize-regressions.json"
    payload = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "scope": list(scope) if scope is not None else "fleet",
        "rows": rows,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"  synthesize regressions: {len(rows)} field(s) preserved")
    return path
```

Then find every caller (`synthesize.py:2306`, `streaming_runner.py:1844`) and check whether any reads the file back expecting a bare list. Fix any reader. Run `grep -rn "synthesize-regressions" data-pipeline/` to find them.

- [ ] **Step 8: Run the full suite and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1009 passed
git add data-pipeline/bin/reconcile_charity_data.py data-pipeline/synthesize.py data-pipeline/tests/
git commit -m "fix(recovery): carry attribution through a restore + stamp both reports with run scope"
```

---

## Group C — Crawl politeness and backoff

### Task C1: Make the failure backoff read the attempt clock

**Why:** `orchestrator.py:402-486` computes the 180d terminal TTL, the 30d permanent-failure TTL, and the graduated `RETRY_BACKOFF_HOURS` all from `scraped_at`. The write-safety work deliberately freezes `scraped_at` on preserved-content failures, so for exactly the rows preservation protects the clock never advances — and the terminal TTL now measures time since last *success*, so February-era CAPTCHA blocks read as expired and get re-hammered every run. This branch added `last_attempt_at` for precisely this and nothing reads it here (verified: the only reader is `src/utils/freshness.py:83`).

**Files:**
- Modify: `data-pipeline/src/collectors/orchestrator.py:402-486`
- Test: `data-pipeline/tests/test_crawl_politeness.py`

- [ ] **Step 1: Write the failing test**

```python
class TestFailureBackoffUsesAttemptClock:
    """scraped_at is frozen by the preservation path, so it cannot drive backoff."""

    def _orch(self, row):
        from unittest.mock import MagicMock
        from src.collectors.orchestrator import DataCollectionOrchestrator
        orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
        orch.raw_data_repo = MagicMock()
        orch.raw_data_repo.get_for_charity.return_value = [row]
        orch.logger = None
        return orch

    def test_recent_attempt_is_backed_off_even_when_scraped_at_is_ancient(self):
        from datetime import datetime, timedelta
        row = {
            "source": "website", "success": 0, "retry_count": 1,
            "last_failure_reason": "RATE_LIMITED: HTTP 429",
            "scraped_at": datetime.now() - timedelta(days=45),   # frozen by preservation
            "last_attempt_at": datetime.now() - timedelta(minutes=5),
        }
        skip, reason = self._orch(row)._should_skip_failed_source("12-3456789", "website")
        assert skip is True and "backoff" in reason.lower()

    def test_terminal_block_measures_from_last_attempt_not_last_success(self):
        from datetime import datetime, timedelta
        row = {
            "source": "website", "success": 0, "retry_count": 3,
            "last_failure_reason": "CAPTCHA_BLOCKED: challenge page (HTTP 200)",
            "scraped_at": datetime.now() - timedelta(days=200),  # last SUCCESS, long ago
            "last_attempt_at": datetime.now() - timedelta(days=2),
        }
        skip, reason = self._orch(row)._should_skip_failed_source("12-3456789", "website")
        assert skip is True, "a site captcha-blocked 2 days ago must not be re-hammered"

    def test_null_last_attempt_at_falls_back_to_scraped_at(self):
        """Pre-migration rows have last_attempt_at NULL — one re-crawl, then backed off."""
        from datetime import datetime, timedelta
        row = {
            "source": "website", "success": 0, "retry_count": 1,
            "last_failure_reason": "RATE_LIMITED: HTTP 429",
            "scraped_at": datetime.now() - timedelta(minutes=5),
            "last_attempt_at": None,
        }
        skip, _ = self._orch(row)._should_skip_failed_source("12-3456789", "website")
        assert skip is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py::TestFailureBackoffUsesAttemptClock -v`
Expected: FAIL on the first two (returns `(False, '')`), PASS on the third.

- [ ] **Step 3: Introduce a single clock accessor and use it in all three places**

Read `data-pipeline/src/collectors/orchestrator.py:402-486` in full. It parses `scraped_at` three separate times (terminal TTL, permanent-failure TTL, graduated backoff), each with the same str/datetime branch. Replace all three with one helper added just above `_should_skip_failed_source`:

```python
    @staticmethod
    def _attempt_clock(row: dict):
        """When this source was last ATTEMPTED, as a datetime (or None).

        Prefers last_attempt_at over scraped_at. scraped_at is the DATA clock
        and is deliberately frozen when a failed re-crawl preserves last-good
        content, so using it for backoff meant the retry clock never advanced
        for exactly the rows preservation protects — and made the 180d terminal
        TTL measure time since last SUCCESS, so long-blocked sites read as
        expired and were re-hammered every run. Falls back to scraped_at for
        pre-migration rows where last_attempt_at is NULL.
        """
        raw = row.get("last_attempt_at") or row.get("scraped_at")
        if not raw:
            return None
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        return raw
```

Then in each of the three blocks, replace the local `scraped_at = row.get("scraped_at")` + isinstance parsing with `attempted_dt = self._attempt_clock(row)` and compute the age from it. Keep the existing TTL constants and messages unchanged.

- [ ] **Step 4: Run the tests**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py -v`
Expected: PASS, all — including the pre-existing backoff tests. If a pre-existing test set only `scraped_at` and expected backoff, it still passes via the fallback.

- [ ] **Step 5: Run the full suite and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1012 passed
git add data-pipeline/src/collectors/orchestrator.py data-pipeline/tests/test_crawl_politeness.py
git commit -m "fix(crawl): drive failure backoff off last_attempt_at, not the frozen data clock"
```

---

### Task C2: Make the CAPTCHA/rate-limit latches thread-local

**Why:** `_last_captcha_error` / `_last_rate_limit_error` are plain instance attributes (`web_collector.py:203,207`) while `_playwright_local` immediately below at `:275` is correctly `threading.local()`. `crawl.py` builds ONE `DataCollectionOrchestrator` and hands it to all `--workers` (default 6) threads. So charity B can inherit charity A's CAPTCHA and get a 180-day terminal block it never earned — the exact poisoning this branch set out to remove.

**Files:**
- Modify: `data-pipeline/src/collectors/web_collector.py:203,207` (declaration), `:1417-1420` (`_record_fetch_error`), `:2476-2477` (reset), `:2551,2595,2598,2642` (reads)
- Test: `data-pipeline/tests/test_crawl_politeness.py`

- [ ] **Step 1: Write the failing test**

```python
class TestCaptchaLatchIsThreadLocal:
    def test_one_threads_captcha_does_not_leak_into_another(self):
        """Shared latch let charity B inherit A's CAPTCHA -> 180d terminal block."""
        import threading
        from src.collectors.web_collector import WebsiteCollector

        collector = WebsiteCollector.__new__(WebsiteCollector)
        collector._init_failure_latches()

        seen = {}
        barrier = threading.Barrier(2)

        def worker_a():
            collector._reset_failure_latches()
            collector._record_fetch_error("CAPTCHA_BLOCKED: challenge page (HTTP 200)")
            barrier.wait()
            seen["a"] = collector._captcha_error()

        def worker_b():
            collector._reset_failure_latches()
            barrier.wait()
            seen["b"] = collector._captcha_error()

        ta, tb = threading.Thread(target=worker_a), threading.Thread(target=worker_b)
        ta.start(); tb.start(); ta.join(); tb.join()

        assert seen["a"] == "CAPTCHA_BLOCKED: challenge page (HTTP 200)"
        assert seen["b"] is None, "B must not inherit A's captcha"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py::TestCaptchaLatchIsThreadLocal -v`
Expected: FAIL — `AttributeError: '_init_failure_latches'`

- [ ] **Step 3: Implement thread-local latches**

In `data-pipeline/src/collectors/web_collector.py`, replace the two declarations at `:203` and `:207` with a call to a new initializer, and add these methods next to `_record_fetch_error`:

```python
    def _init_failure_latches(self) -> None:
        """Per-thread CAPTCHA / rate-limit latches.

        crawl.py shares ONE orchestrator (and so one WebsiteCollector) across
        every worker thread — the same sharing that forced the thread-local
        Playwright renderer. As plain instance attributes these latched one
        charity's CAPTCHA onto whichever charity happened to finish next,
        writing an unearned 180-day terminal block.
        """
        self._failure_local = threading.local()

    def _reset_failure_latches(self) -> None:
        self._failure_local.captcha = None
        self._failure_local.rate_limit = None

    def _captcha_error(self) -> Optional[str]:
        return getattr(self._failure_local, "captcha", None)

    def _rate_limit_error(self) -> Optional[str]:
        return getattr(self._failure_local, "rate_limit", None)

    def _record_fetch_error(self, error: Optional[str]) -> None:
        """Latch the first captcha/rate-limit error seen this crawl, per thread."""
        if not error:
            return
        if "CAPTCHA_BLOCKED" in error and self._captcha_error() is None:
            self._failure_local.captcha = error
        if "RATE_LIMITED" in error and self._rate_limit_error() is None:
            self._failure_local.rate_limit = error
```

Call `self._init_failure_latches()` where the old attributes were assigned in `__init__`.

- [ ] **Step 4: Update every read site**

Replace `self._last_captcha_error` with `self._captcha_error()` and `self._last_rate_limit_error` with `self._rate_limit_error()` at `:2551`, `:2595`, `:2598`, `:2642`. Replace the reset pair at `:2476-2477` with `self._reset_failure_latches()`. Confirm none remain: `grep -n "_last_captcha_error\|_last_rate_limit_error" data-pipeline/src/collectors/web_collector.py` must return nothing.

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest tests/test_crawl_politeness.py -v && uv run pytest -q   # expect 1013 passed
git add data-pipeline/src/collectors/web_collector.py data-pipeline/tests/test_crawl_politeness.py
git commit -m "fix(crawl): thread-local captcha/rate-limit latches

One shared collector across 6 worker threads let charity B inherit
charity A's CAPTCHA and take an unearned 180-day terminal block."
```

---

### Task C3: Stop treating a richer re-crawl as a downgrade

**Why:** `orchestrator.py:231-233` marks a crawl a downgrade when the homepage HTML is thin, but `new_raw_content` is the homepage ONLY, fetched separately from the multi-page crawl. A 25-page crawl beating a prior 20 is discarded when the sync homepage fetch 403s — the row reports success, content stays pinned, and it repeats every run on exactly the hard sites this was built for.

**Files:**
- Modify: `data-pipeline/src/collectors/orchestrator.py:231-233`
- Test: `data-pipeline/tests/test_write_safety.py`

- [ ] **Step 1: Write the failing test**

```python
def test_more_pages_with_an_empty_homepage_is_not_a_downgrade():
    """raw_content is the homepage only; it can fail independently of the crawl."""
    from src.collectors.orchestrator import is_content_downgrade

    assert is_content_downgrade(new_raw_content="", new_pages=25, prior_pages=20) is False
    assert is_content_downgrade(new_raw_content="x" * 400, new_pages=25, prior_pages=20) is False


def test_thin_homepage_with_no_page_improvement_is_still_a_downgrade():
    from src.collectors.orchestrator import is_content_downgrade

    assert is_content_downgrade(new_raw_content="", new_pages=18, prior_pages=20) is True


def test_lost_pages_is_a_downgrade_regardless_of_homepage():
    from src.collectors.orchestrator import is_content_downgrade

    assert is_content_downgrade(new_raw_content="x" * 5000, new_pages=3, prior_pages=20) is True
```

Read the real signature of `is_content_downgrade` first and adapt the call shape — the assertions are what matter.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py -k downgrade -v`
Expected: FAIL on the first test (returns True)

- [ ] **Step 3: Fix the predicate**

Replace `:231-233`:

```python
    # raw_content is the HOMEPAGE only, fetched separately from the multi-page
    # crawl — a Cloudflare-fronted site can serve pages fine via curl_cffi while
    # the sync homepage fetch 403s. Thin homepage HTML is only a downgrade
    # signal when the crawl did not otherwise improve; a crawl that found MORE
    # pages than last time is strictly richer no matter what the homepage did.
    thin_raw = not new_raw_content or len(new_raw_content.strip()) < 500
    lost_pages = prior_pages >= 3 and new_pages <= max(1, prior_pages // 3)
    return lost_pages or (thin_raw and new_pages <= prior_pages)
```

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1016 passed
git add data-pipeline/src/collectors/orchestrator.py data-pipeline/tests/test_write_safety.py
git commit -m "fix(crawl): a re-crawl that found more pages is not a downgrade"
```

---

### Task C4: Honor `max_concurrent`, and make the empty-batch retry actually serial

**Why:** `_crawl_urls_async` calls `self._per_domain_semaphores()` with no argument (`web_collector.py:1277`), so the limit is always `PER_DOMAIN_CONCURRENCY` regardless of the `max_concurrent` threaded down from `collect_multi_page`. Consequences: `polite_concurrency` (2 when `crawl_delay >= 1`, else 10) does nothing; the "retry serially (concurrency 1)" at `:2551-2573` is a second *identical parallel* retry that doubles request volume against a host that just returned an empty batch; and the log line at `:1449` is false. The existing tests assert the argument passed to a stub (`calls == [2]`, `calls == [10, 1]`), which stays true while the effect doesn't exist.

**Files:**
- Modify: `data-pipeline/src/collectors/web_collector.py:1277`
- Test: `data-pipeline/tests/test_crawl_politeness.py`

- [ ] **Step 1: Write the failing test — assert the EFFECT, not the argument**

```python
class TestMaxConcurrentIsHonored:
    def test_semaphore_limit_reflects_the_requested_concurrency(self):
        """The existing tests assert the value passed to a stub; this asserts
        the semaphore that actually gates requests."""
        import asyncio
        from src.collectors.web_collector import WebsiteCollector

        get_sem = WebsiteCollector._per_domain_semaphores(1)
        sem = get_sem("https://example.org/a")
        assert sem._value == 1

        get_sem = WebsiteCollector._per_domain_semaphores(2)
        assert get_sem("https://example.org/a")._value == 2

    def test_serial_retry_uses_a_concurrency_of_one(self):
        """The 'serial' retry was a second identical parallel pass, doubling
        load on a host that had just returned an empty batch."""
        import inspect
        from src.collectors import web_collector

        src = inspect.getsource(web_collector.WebsiteCollector._crawl_urls_async)
        assert "_per_domain_semaphores(" in src
        assert "_per_domain_semaphores()" not in src, "must pass the requested limit through"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py::TestMaxConcurrentIsHonored -v`
Expected: FAIL on `test_serial_retry_uses_a_concurrency_of_one`

- [ ] **Step 3: Pass the limit through**

At `data-pipeline/src/collectors/web_collector.py:1277`, replace:

```python
        get_sem = self._per_domain_semaphores()
```

with:

```python
        # Never exceed the per-domain politeness ceiling, but DO honor a caller
        # asking for less — polite_concurrency (2 when the host publishes a
        # Crawl-delay) and the serial empty-batch retry both depend on this.
        get_sem = self._per_domain_semaphores(min(max_concurrent, PER_DOMAIN_CONCURRENCY))
```

Confirm `max_concurrent` is in scope in that method signature; if it is named differently, use the real name.

- [ ] **Step 4: Run the crawl tests**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py -v`
Expected: PASS. The pre-existing `test_crawl_delay_lowers_concurrency` and `test_empty_batch_retries_serially_when_homepage_live` still pass — they assert the argument, which is unchanged.

- [ ] **Step 5: Full suite and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1018 passed
git add data-pipeline/src/collectors/web_collector.py data-pipeline/tests/test_crawl_politeness.py
git commit -m "fix(crawl): honor max_concurrent so polite_concurrency and the serial retry work"
```

---

### Task C5: Never let history bookkeeping change a crawl's outcome

**Why:** `orchestrator.py:1386` calls `record_pages` OUTSIDE the try that wraps the upsert. Any exception there (a URL longer than `crawled_pages.url`'s `VARCHAR(500)`, or a failed lazy `CREATE TABLE`) propagates out of `_store_raw_data`, gets caught by the caller at `:893`, and routes to `_store_failed_crawl` — a successful crawl recorded as a failure. Same shape at `:1401` (where the preserve guard's own `record()` can trigger the very demotion the guard prevents) and `:1426` (a `record()` inside an except handler).

**Files:**
- Modify: `data-pipeline/src/collectors/orchestrator.py:1386,1401,1426`, `data-pipeline/src/db/repository.py` (`record_pages` URL length)
- Test: `data-pipeline/tests/test_crawl_history_repository.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_record_pages_skips_a_url_too_long_for_the_column():
    """crawled_pages.url is VARCHAR(500); a long sitemap query string must not
    raise into the crawl's success path."""
    from unittest.mock import patch
    from src.db.repository import CrawledPageRepository

    repo = CrawledPageRepository()
    CrawledPageRepository._table_ensured = True
    pages = [{"url": "https://x.org/" + "a" * 600, "had_data": True},
             {"url": "https://x.org/ok", "had_data": True}]
    with patch("src.db.repository.execute_query") as mock_exec:
        repo.record_pages("12-3456789", pages)
    _, params = mock_exec.call_args.args
    assert params == ("12-3456789", "https://x.org/ok", True)
```

And in `data-pipeline/tests/test_crawl_politeness.py`:

```python
def test_history_write_failure_does_not_demote_a_successful_crawl():
    """Bookkeeping must never change a crawl's outcome."""
    from unittest.mock import MagicMock, patch
    from src.collectors.orchestrator import DataCollectionOrchestrator

    orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
    orch.logger = None
    orch.raw_data_repo = MagicMock()
    orch.crawled_page_repo = MagicMock()
    orch.crawled_page_repo.record_pages.side_effect = RuntimeError("Data too long for column 'url'")
    orch.crawl_attempt_repo = MagicMock()

    # Should not raise; the upsert must still happen.
    orch._store_raw_data("12-3456789", {"https://x.org/": {"had_data": True}}, "<html/>")
    assert orch.raw_data_repo.upsert.called
```

Read `_store_raw_data`'s real signature and adapt the call; the assertion is what matters.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_history_repository.py tests/test_crawl_politeness.py -k "url_too_long or does_not_demote" -v`
Expected: FAIL

- [ ] **Step 3: Filter over-long URLs in `record_pages`**

In `data-pipeline/src/db/repository.py`, in `record_pages`, change the row comprehension to:

```python
        # crawled_pages.url is VARCHAR(500). A long sitemap/BFS query string
        # would raise into the caller's success path and demote a good crawl.
        rows = [
            (ein, page["url"], bool(page.get("had_data")))
            for page in pages
            if page.get("url") and len(page["url"]) <= 500
        ]
```

- [ ] **Step 4: Wrap all three history writes**

At `orchestrator.py:1386`, `:1401`, and `:1426`, wrap each history call:

```python
        try:
            self.crawled_page_repo.record_pages(ein, pages)
        except Exception as e:  # bookkeeping must never change a crawl's outcome
            if self.logger:
                self.logger.debug(f"crawl history write failed for {ein}: {e}")
```

Apply the same shape to the two `record()` calls. Read each site to get the right receiver and arguments.

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1020 passed
git add data-pipeline/src/collectors/orchestrator.py data-pipeline/src/db/repository.py data-pipeline/tests/
git commit -m "fix(crawl): history bookkeeping can no longer demote a successful crawl"
```

---

### Task C6: Stop false-positiving on Cloudflare Turnstile

**Why:** `web_collector.py:489-503` scans the first 20,000 chars of ANY 200 response for strong bot-challenge markers, and `"verify you are human"` is Turnstile's literal widget label. A charity donate or contact page embedding Turnstile is misread as a challenge page, latches into the CAPTCHA error, and — on a thin sitemap where it was the only page — becomes that charity's 180-day terminal failure reason.

**Files:**
- Modify: `data-pipeline/src/collectors/web_collector.py:489-503`
- Test: `data-pipeline/tests/test_crawl_politeness.py`

- [ ] **Step 1: Write the failing test**

```python
class TestTurnstileIsNotABotChallenge:
    def test_a_donate_page_embedding_turnstile_is_not_a_challenge(self):
        from src.collectors.web_collector import WebsiteCollector

        html = """<html><head><title>Donate — Example Charity</title></head><body>
        <h1>Support our work</h1><p>Your gift funds clean water.</p>
        <form><div class="cf-turnstile" data-sitekey="0x4A"></div>
        <label>Verify you are human</label><button>Give $50</button></form>
        </body></html>"""
        assert WebsiteCollector._is_bot_challenge_html(html) is False

    def test_a_real_challenge_page_is_still_detected(self):
        from src.collectors.web_collector import WebsiteCollector

        html = """<html><head><title>Just a moment...</title></head><body>
        <h1>Verify you are human</h1>
        <p>example.org needs to review the security of your connection.</p>
        <div id="challenge-running"></div></body></html>"""
        assert WebsiteCollector._is_bot_challenge_html(html) is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py::TestTurnstileIsNotABotChallenge -v`
Expected: FAIL on the first test

- [ ] **Step 3: Require co-occurrence for the weak marker**

Read `_is_bot_challenge_html` in full. Move `"verify you are human"` out of the strong-marker list into a weak list that only counts when it co-occurs with a challenge-vendor marker (e.g. `challenge-running`, `cf-chl`, `just a moment`, `_cf_chl_opt`, `ray id`) OR appears in the `<title>`. Keep `sgcaptcha` and `robot challenge screen` as strong markers — they are specific enough. Preserve the existing signature and return type.

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1022 passed
git add data-pipeline/src/collectors/web_collector.py data-pipeline/tests/test_crawl_politeness.py
git commit -m "fix(crawl): Turnstile's widget label is not a bot challenge

'Verify you are human' on a donate page marked the whole crawl
CAPTCHA_BLOCKED and could become a 180-day terminal reason."
```

---

### Task C7: Close every Playwright browser, not just the calling thread's

**Why:** `_cleanup_playwright` (`web_collector.py:296-302`) reads `self._playwright_local`, so it can only close the calling thread's renderer. `crawl.py:492` calls `orchestrator.close()`, which is a no-op (`orchestrator.py:1590-1592`), and `streaming_runner.py:255-260` calls `_cleanup_playwright()` from the main thread where the thread-local is empty. A 6-worker fleet run touching the rescue or SPA path leaks up to 6 chromium browsers plus 6 node driver subprocesses for the process lifetime.

**Files:**
- Modify: `data-pipeline/src/collectors/web_collector.py:270-302`, `data-pipeline/src/collectors/orchestrator.py:1590-1592`
- Test: `data-pipeline/tests/test_spa_rendering.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cleanup_closes_renderers_created_on_other_threads():
    """Cleanup ran on the main thread where the thread-local is empty, leaking
    one chromium + one node driver per worker for the process lifetime."""
    import threading
    from unittest.mock import MagicMock
    from src.collectors.web_collector import WebsiteCollector

    collector = WebsiteCollector.__new__(WebsiteCollector)
    collector._init_playwright_local()

    made = []

    def worker():
        r = MagicMock()
        collector._register_renderer(r)
        made.append(r)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads: t.start()
    for t in threads: t.join()

    collector._cleanup_playwright()   # called from the MAIN thread

    assert len(made) == 3
    for r in made:
        assert r.close.called, "every worker's renderer must be closed"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_spa_rendering.py::test_cleanup_closes_renderers_created_on_other_threads -v`
Expected: FAIL — `AttributeError: '_register_renderer'`

- [ ] **Step 3: Add a lock-guarded registry**

In `data-pipeline/src/collectors/web_collector.py`, add alongside the thread-local setup:

```python
    def _init_playwright_local(self) -> None:
        self._playwright_local = threading.local()
        # Cleanup runs on the main thread, where the thread-local is empty, so a
        # registry is the only way to reach renderers created by worker threads.
        self._renderer_registry: list = []
        self._renderer_registry_lock = threading.Lock()

    def _register_renderer(self, renderer) -> None:
        with self._renderer_registry_lock:
            self._renderer_registry.append(renderer)
```

Call `_register_renderer(renderer)` wherever a renderer is created (the `self._playwright_local.renderer = renderer` site at `:288`). Rewrite `_cleanup_playwright` to drain the registry:

```python
    def _cleanup_playwright(self) -> None:
        """Close every renderer this collector created, on any thread."""
        with self._renderer_registry_lock:
            renderers, self._renderer_registry = self._renderer_registry, []
        for renderer in renderers:
            try:
                renderer.close()
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"playwright cleanup failed: {e}")
        self._playwright_local.renderer = None
```

- [ ] **Step 4: Make `orchestrator.close()` actually close**

Replace the no-op body at `data-pipeline/src/collectors/orchestrator.py:1590-1592`:

```python
    def close(self) -> None:
        """Release collector resources. crawl.py calls this at run end."""
        website = getattr(self, "website", None)
        if website is not None and hasattr(website, "_cleanup_playwright"):
            website._cleanup_playwright()
```

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1023 passed
git add data-pipeline/src/collectors/ data-pipeline/tests/test_spa_rendering.py
git commit -m "fix(crawl): close every worker thread's Playwright browser at run end"
```

---

### Task C8: Route non-website sources through the non-downgrade guard

**Why:** The guard lives inside `_store_raw_data` (`orchestrator.py:1387-1402`), but in `fetch_charity_data` — the ONLY orchestrator entry used by `crawl.py:153` and `streaming_runner.py:928` — only `website` goes through it (`:851`). ProPublica, Charity Navigator, Candid, and `form990_grants` all go through `_store_raw_content_only` (`:779`), which calls `raw_data_repo.upsert(..., parsed_json=None, success=True)` with no downgrade check at all. So `is_content_downgrade`'s `form990_grants` branch is reachable only from `collect_charity_data`, which has **no production callers**. This is Spec B's Vector 2 — a throttled ProPublica grants page returning an empty-but-`success=True` profile overwrites good data, and the grants-derived ratios are (correctly) not in `REGRESSION_GUARDED_FIELDS`, so nothing downstream catches it either. The plan's own self-review claims "Grants required-source constraint honored ✓", which is not true of the path that actually runs.

The same gap makes `crawl_attempts` website-only in practice, despite its docstring claiming "every collection attempt per (charity, source)."

**Files:**
- Modify: `data-pipeline/src/collectors/orchestrator.py:779` (`_store_raw_content_only`)
- Test: `data-pipeline/tests/test_write_safety.py`

- [ ] **Step 1: Write the failing test**

```python
def test_non_website_sources_are_downgrade_guarded_on_the_production_path():
    """Only `website` was guarded; propublica/CN/candid/form990_grants went
    through _store_raw_content_only unguarded (Spec B Vector 2)."""
    from unittest.mock import MagicMock
    from src.collectors.orchestrator import DataCollectionOrchestrator

    orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
    orch.logger = None
    orch.raw_data_repo = MagicMock()
    orch.raw_data_repo.get.return_value = {
        "source": "form990_grants", "success": 1,
        "raw_content": "x" * 50_000, "parsed_json": {"grants": [1, 2, 3]},
    }

    # A thin, empty-but-successful re-fetch must NOT overwrite the good row.
    orch._store_raw_content_only("12-3456789", "form990_grants", "")

    assert orch.raw_data_repo.record_soft_fail.called, "thin re-fetch must soft-fail, not overwrite"
    assert not orch.raw_data_repo.upsert.called


def test_a_genuinely_richer_non_website_fetch_still_writes():
    from unittest.mock import MagicMock
    from src.collectors.orchestrator import DataCollectionOrchestrator

    orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
    orch.logger = None
    orch.raw_data_repo = MagicMock()
    orch.raw_data_repo.get.return_value = {
        "source": "propublica", "success": 1, "raw_content": "x" * 100, "parsed_json": None,
    }

    orch._store_raw_content_only("12-3456789", "propublica", "y" * 50_000)

    assert orch.raw_data_repo.upsert.called
```

Read `_store_raw_content_only`'s real signature at `:779` first and adapt the calls — the assertions are what matter.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py -k "non_website_sources or genuinely_richer" -v`
Expected: FAIL — `upsert` is called unconditionally

- [ ] **Step 3: Apply the same guard**

In `_store_raw_content_only`, load the prior row and reuse the existing `is_content_downgrade` predicate before writing, mirroring what `_store_raw_data` does at `:1387-1402`. On a downgrade, call `record_soft_fail` instead of `upsert` so the content is preserved and the attempt clock still advances. Keep the existing behavior when there is no prior row (first observation always writes).

Do NOT duplicate the guard logic — extract the shared "guard then write or soft-fail" sequence into one private helper and call it from both stores.

- [ ] **Step 4: Record the attempt for non-website sources too**

While here, add the `crawl_attempts` `record()` call to this path (wrapped in try/except per Task C5), so the table matches its docstring instead of being website-only.

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q
git add data-pipeline/src/collectors/orchestrator.py data-pipeline/tests/test_write_safety.py
git commit -m "fix(crawl): guard non-website sources against content downgrade

Spec B Vector 2: only website went through the guard on the production
path, so a throttled ProPublica/grants fetch overwrote good data and
nothing downstream caught it."
```

---

## Group D — Judge gate and narrative generation

### Task D1: Fail the score judge CLOSED when every consensus roll fails

**Why:** `score_judge.py:135-137` logs and sets `metadata["llm_failed"] = True` but adds no issue, so `error_count` is 0, `passed` is True, and the gate opens on a charity whose band/factual consistency was never checked. `factual_judge.py:113-119` on the identical path adds a `Severity.ERROR`; the diff shows score_judge used to as well. `ScoreJudge` is the only judge pinned to `gemini-2.5-flash`, so a model-specific quota exhaustion or a run of unparseable responses hits it alone.

**Files:**
- Modify: `data-pipeline/src/judges/score_judge.py:135-137`
- Test: `data-pipeline/tests/test_judges.py`

- [ ] **Step 1: Write the failing test**

```python
class TestScoreJudgeFailsClosed:
    def test_all_rolls_failing_produces_an_error_not_a_pass(self):
        """A judge that did no work must never report a clean pass."""
        from unittest.mock import patch
        from src.judges.score_judge import ScoreJudge
        from src.judges.base_judge import Severity

        judge = ScoreJudge()
        with patch.object(ScoreJudge, "_verify_rationales_with_llm",
                          side_effect=RuntimeError("gemini 500 internal error")):
            verdict = judge.validate(_minimal_score_judge_output(), _minimal_score_judge_context())

        assert verdict.passed is False
        assert any(i.severity == Severity.ERROR for i in verdict.issues)
        assert verdict.metadata.get("llm_failed") is True
```

Add `_minimal_score_judge_output()` / `_minimal_score_judge_context()` helpers built from the shapes the existing `TestScoreJudgeConsensus` tests already use in this file — reuse them rather than inventing new fixtures.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_judges.py::TestScoreJudgeFailsClosed -v`
Expected: FAIL — `assert True is False` (the judge currently passes)

- [ ] **Step 3: Add the ERROR**

Replace `data-pipeline/src/judges/score_judge.py:135-137`:

```python
        else:
            # Fail CLOSED. A judge that completed no roll verified nothing, and
            # reporting error_count == 0 opened the publication gate on an
            # unchecked narrative. factual_judge.py does the same on this path.
            logger.error("Score judge: all consensus rolls failed")
            metadata["llm_failed"] = True
            self.add_issue(
                issues,
                Severity.ERROR,
                "llm_verification",
                "Score judge could not complete any consensus roll",
            )
```

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1024 passed
git add data-pipeline/src/judges/score_judge.py data-pipeline/tests/test_judges.py
git commit -m "fix(judge): score judge fails closed when every consensus roll fails"
```

---

### Task D2: Re-read the evaluation after a retry, and surface a failed retry

**Why:** `judge_phase.py`'s retry calls `generate_rich_for_pipeline(..., force=True)`. On consistency-validation failure that path calls `clear_rich_narrative(ein)` (NULLing `rich_narrative` and `rich_strategic_narrative`) and returns `success: False`. `judge_charity` then falls through and computes `result["content_hash"]` from the `evaluation` dict read at `:136` — *before* the wipe. The charity ends up with no rich narrative, a persisted hash that can never match, and no log line. It only fires on charities that were otherwise in good shape.

**Files:**
- Modify: `data-pipeline/judge_phase.py:222-239`, `:271`
- Test: `data-pipeline/tests/test_judge_phase.py`

- [ ] **Step 1: Write the failing test**

```python
def test_failed_rich_retry_rereads_evaluation_and_reports(monkeypatch, capsys):
    """A failed retry can NULL the rich narrative; hashing the pre-retry
    evaluation persisted a hash that could never match the stored row."""
    from unittest.mock import MagicMock
    import judge_phase
    from judge_phase import compute_judge_content_hash

    with_rich = {"charity_ein": "12-3456789", "amal_score": 60,
                 "baseline_narrative": {"rationale": "ok"},
                 "rich_narrative": {"body": "long form"}}
    without_rich = {**with_rich, "rich_narrative": None}

    eval_repo = MagicMock()
    eval_repo.get.side_effect = [with_rich, without_rich, without_rich]

    # First pass fails on score only, which is what triggers the retry.
    monkeypatch.setattr(judge_phase, "_run_judges",
                        lambda *a, **k: _fake_verdicts(error_judges={"score"}))
    # The retry regenerates, trips consistency validation, clears the narrative.
    monkeypatch.setattr(judge_phase, "generate_rich_for_pipeline",
                        lambda *a, **k: {"success": False, "cost_usd": 0.0,
                                         "error": "consistency validation failed"})

    result = judge_phase.judge_charity("12-3456789", eval_repo, MagicMock(),
                                       MagicMock(), MagicMock())

    assert result["content_hash"] == compute_judge_content_hash(without_rich), \
        "hash must describe the row as it stands AFTER the retry"
    assert result["rich_retry_failed"]
    assert "retry failed" in capsys.readouterr().out
```

`_run_judges` and `_fake_verdicts` must match the real names and shapes already used by `test_retry_is_bounded_to_one_attempt` in this file — read that test first and reuse its fakes rather than inventing new ones. If `judge_charity` reaches the judges by a different path than a module-level `_run_judges`, patch whatever that test patches.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_judge_phase.py -k failed_rich_retry -v`
Expected: FAIL

- [ ] **Step 3: Re-read and report**

In `judge_phase.py`'s retry block, after the `generate_rich_for_pipeline` call, handle both branches:

```python
        rich_retry = generate_rich_for_pipeline(ein, eval_repo, force=True)
        retry_rich_cost = rich_retry.get("cost_usd", 0.0)
        if rich_retry.get("success") and not rich_retry.get("skipped"):
            update_phase_cache(ein, "rich", PhaseCacheRepository(), retry_rich_cost)
            retried = judge_charity(
                ein, eval_repo, data_repo, raw_repo, charity_repo, _retry_attempted=True
            )
            retried["cost_usd"] = retried.get("cost_usd", 0.0) + retry_rich_cost
            retried["rich_retried"] = True
            return retried
        # The retry FAILED. rich_narrative_generator clears the stored narrative
        # on a consistency-validation failure, so `evaluation` (read before the
        # retry) may no longer describe the row. Re-read before hashing, or we
        # persist a hash that can never match and the charity is excluded
        # forever with nothing logged.
        evaluation = eval_repo.get(ein) or evaluation
        result["rich_retry_failed"] = rich_retry.get("error") or "rich regeneration failed"
        print(f"  ⚠ {ein}: rich narrative retry failed — {result['rich_retry_failed']}")
```

Confirm `evaluation` is the same local the hash at `:271` reads; if the hash reads a different name, rebind that one.

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1025 passed
git add data-pipeline/judge_phase.py data-pipeline/tests/test_judge_phase.py
git commit -m "fix(judge): re-read evaluation after a failed rich retry before hashing"
```

---

### Task D3: Fix the crash on an explicit-NULL `score_details`

**Why:** `rich_narrative_generator.py:826` uses `baseline.get("score_details", {}).get("impact", {})`. The column is nullable (`dolt_schema.sql:148`) and typed `dict | None` (`repository.py:168`), and `.get(k, {})` returns `None` for an explicit SQL NULL — the default only applies to a *missing* key. The existing test covers the missing key, not the null.

**Files:**
- Modify: `data-pipeline/src/services/rich_narrative_generator.py:826`
- Test: `data-pipeline/tests/test_rich_narrative_program_ratio.py`

- [ ] **Step 1: Write the failing test**

```python
def test_no_crash_when_score_details_is_explicitly_null():
    """score_details is a nullable json column; .get(k, {}) returns None for an
    explicit NULL, so the default never applies."""
    from src.services.rich_narrative_generator import RichNarrativeGenerator

    gen = RichNarrativeGenerator.__new__(RichNarrativeGenerator)
    baseline = {"score_details": None, "amal_score": 54}
    # Should not raise.
    gen._format_charity_data({"ein": "12-3456789"}, baseline)
```

Match the real method name and signature — read `:820-835` first.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_rich_narrative_program_ratio.py -k explicitly_null -v`
Expected: FAIL — `AttributeError: 'NoneType' object has no attribute 'get'`

- [ ] **Step 3: Use the `or {}` idiom**

```python
                        for c in (baseline.get("score_details") or {}).get("impact", {}).get("components", [])
```

Then grep the file for other `\.get\([^)]*,\s*\{\}\)` on nullable columns and fix any that can receive an explicit NULL: `grep -n 'get("score_details"\|get("metrics_json"\|get("source_attribution"' data-pipeline/src/services/rich_narrative_generator.py`

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1026 passed
git add data-pipeline/src/services/rich_narrative_generator.py data-pipeline/tests/test_rich_narrative_program_ratio.py
git commit -m "fix(rich): explicit-NULL score_details crashed prompt assembly"
```

---

### Task D4: Feed the narrative to the score judge so the tone contract runs

**Why:** `_quick_tone_checks` reads `output.get("narrative", {})`, but `judge_phase.py:167-176` builds `charity_dict` with keys `ein/name/tier/evaluation/data` — no `narrative` key. So `rationale` is `""`, the function returns `[]` every time, and the deterministic band-tone backstop added in this branch is unreachable. The same `output.get("narrative", {})` in `format_prompt` makes the prompt's `## Narrative Rationale` section render literally as `{}` — plausibly a contributor to the roll-to-roll flip-flopping that motivated k=3 consensus.

**Files:**
- Modify: `data-pipeline/judge_phase.py:167-176`
- Test: `data-pipeline/tests/test_judges.py`

- [ ] **Step 1: Write the failing test**

```python
def test_score_judge_prompt_contains_the_narrative_rationale():
    """The prompt rendered '## Narrative Rationale\\n{}' — the judge was told
    its subject was empty."""
    from src.judges.score_judge import ScoreJudge
    from judge_phase import build_judge_projection

    evaluation = {"amal_score": 42, "baseline_narrative": {"rationale": "This charity performs well."}}
    projection = build_judge_projection(evaluation)
    prompt = ScoreJudge().format_prompt(projection, {})

    assert "This charity performs well." in prompt
    assert "## Narrative Rationale\n{}" not in prompt


def test_quick_tone_checks_flag_praise_language_in_a_below_average_band():
    from src.judges.score_judge import ScoreJudge

    output = {"amal_score": 42, "narrative": {"rationale": "An exceptional, outstanding organization."}}
    issues = ScoreJudge()._quick_tone_checks(output.get("evaluation", output), output.get("narrative"))

    assert issues, "below_average band + praise language must warn"
```

Adapt to the real signatures of `build_judge_projection`, `format_prompt`, and `_quick_tone_checks` — read them first.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_judges.py -k "narrative_rationale or praise_language" -v`
Expected: FAIL

- [ ] **Step 3: Add the narrative to the projection**

In `judge_phase.py`, where `charity_dict` is built (`:167-176`), add:

```python
        # The score judge's tone contract and its prompt both read output["narrative"].
        # Without this the prompt rendered "## Narrative Rationale\n{}" and the
        # deterministic band-tone check returned [] on every charity.
        "narrative": evaluation.get("baseline_narrative") or {},
```

Then ensure `ScoreJudge.validate` passes it to `_quick_tone_checks`.

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1028 passed
git add data-pipeline/judge_phase.py data-pipeline/src/judges/score_judge.py data-pipeline/tests/test_judges.py
git commit -m "fix(judge): feed the narrative to the score judge

The prompt said '## Narrative Rationale {}' and the deterministic
band-tone backstop was dead code on every charity."
```

---

### Task D4b: Measure the blast radius of the newly-activated judges

**Why:** Task D4 added the `narrative` key to the judge input dict. That key is read by four judges, and two of them — `FactualJudge` and `CitationJudge` — have been **complete no-ops for the entire life of this code**, because the key never existed on `main` or anywhere on this branch:

- `factual_judge.py:81-83` — `if not narrative: return create_verdict(passed=True, ...)`, an unconditional early pass.
- `citation_judge.py:101-102` — `citations = narrative.get("all_citations", [])`, so it validated zero citations.

Both are registered in the active gate (`orchestrator.py:229,232`) and both emit `Severity.ERROR`, which blocks publication. This also revises an earlier conclusion: the root-cause investigation into the `$0.00` fundraising hallucination reported that the factual judge classified it as a non-gating warning. It did not — **it never ran**.

The user's decision was: activate them (D4, done), then measure the impact **before** authorizing any fleet run. This task is that measurement. It is **read-only and report-only** — it changes no pipeline behavior.

**Files:**
- Create: `data-pipeline/bin/judge_activation_blast_radius.py`
- Report output: `data-pipeline/reports/judge-activation-blast-radius.json` (gitignored, like the other reports)

- [ ] **Step 1: Establish what can be measured without network or LLM calls**

Read `FactualJudge.validate` and `CitationJudge.validate` and classify each check as:
- **deterministic** — pure logic over stored data, safe to run now
- **LLM-dependent** — needs a model call
- **network-dependent** — needs a live URL fetch (`CitationJudge`'s `url_verifier`)

Record the classification. Only the deterministic checks get measured here; the others get **counted and named** so the report says plainly what it could not evaluate. A blast-radius report that silently omits half the checks is worse than none.

- [ ] **Step 2: Build the read-only harness**

For every charity in `evaluations` that currently has a `baseline_narrative`, construct the same `charity_dict` that `judge_phase.py` now builds (reuse its real construction code — do not reimplement it, or you will measure the wrong thing), and run only the deterministic checks identified in Step 1.

Stub the `url_verifier` so no network call is made. Make no LLM calls. Read-only DoltDB queries only.

- [ ] **Step 3: Report per-charity and in aggregate**

Write `reports/judge-activation-blast-radius.json` with, for each charity: EIN, which judges would now emit ERRORs, the issue category and message for each, and whether that charity currently publishes. Aggregate at the top: how many charities newly fail, broken down by judge and by issue category.

Print a short summary to stdout — the top-line number is "N of 166 charities would newly fail the gate."

- [ ] **Step 4: Sanity-check the result against known data**

Two cross-checks, because a measurement you can't sanity-check is not evidence:
- The 34 charities carrying the hallucinated `$0.00` fundraising claim are known. Does the factual judge flag any of them? If it flags none, say so and explain why — that would mean this class of hallucination still isn't caught, which is important on its own.
- The 35 charities with mangled Charity Navigator scores (`98.98.66666666666667/100`) are known. Does anything flag them?

- [ ] **Step 5: Commit the tool**

```bash
git add data-pipeline/bin/judge_activation_blast_radius.py
git commit -m "feat(judge): read-only blast-radius measurement for the newly-activated judges"
```

Do NOT commit the report (it is gitignored). Report the top-line numbers in your summary.

---

### Task D5: Make B-J-013 a warning until the status-code distribution is known

**Why:** `baseline_quality_judge.py:780-793` makes any non-`01` IRS `exempt_organization_status_code` a publication-blocking ERROR. The field was added in this same branch, so it is `None` on every existing row and the rule is inert today — but the moment a fleet run repopulates it, legitimate BMF codes (e.g. `12` for 4947(a)(2) trusts) hard-block publication, discovered only after export. The distribution across the 166 pilot charities has never been measured.

**Files:**
- Modify: `data-pipeline/src/judges/baseline_quality_judge.py:780-793`
- Test: `data-pipeline/tests/test_baseline_quality_irs_compliance.py`

- [ ] **Step 1: Write the failing test**

```python
def test_unexpected_status_code_warns_rather_than_blocking_publication():
    """Ship as WARNING for one fleet run; promote to ERROR once the real
    distribution across the pilot set is known (BMF code 12 = 4947(a)(2) trust
    is legitimate and would hard-block today)."""
    from src.judges.base_judge import Severity
    issues = _run_b_j_013({"exempt_organization_status_code": "12"})
    assert issues and all(i.severity == Severity.WARNING for i in issues)


def test_status_code_01_is_clean():
    assert _run_b_j_013({"exempt_organization_status_code": "01"}) == []
    assert _run_b_j_013({"exempt_organization_status_code": "1"}) == []


def test_missing_status_code_is_not_flagged():
    assert _run_b_j_013({"exempt_organization_status_code": None}) == []
```

Write `_run_b_j_013` as a small helper that drives the real check — read the judge to find its entry point.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_baseline_quality_irs_compliance.py -k "warns_rather_than_blocking" -v`
Expected: FAIL — severity is ERROR

- [ ] **Step 3: Downgrade to WARNING with a TODO tied to the fleet run**

Change the `Severity.ERROR` in the B-J-013 block to `Severity.WARNING` and add above it:

```python
        # WARNING, not ERROR, until the real distribution is measured. The field
        # landed with this branch, so every existing row is NULL and the rule has
        # never fired against live data. Legitimate BMF codes other than 01 exist
        # (12 = 4947(a)(2) trust). Promote to ERROR for a specific denylist of
        # codes after one fleet run populates the column and the editorial queue
        # shows what actually appears.
```

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1031 passed
git add data-pipeline/src/judges/baseline_quality_judge.py data-pipeline/tests/test_baseline_quality_irs_compliance.py
git commit -m "fix(judge): B-J-013 warns instead of blocking until the code distribution is known"
```

---

### Task D6: Add the new prompt/constant modules to the phase fingerprints

**Why:** `phase_fingerprint.py:77-101` hashes a fixed file list per phase. This branch moved prompt-bearing logic OUT of the listed files: `prompt_loader.py` now holds all of `data_vintage_note` and `DATA_VINTAGE_STALE_YEARS`, and it is in no phase's list. Neither is `constants.py` (`DATA_FULL_CONFIDENCE_MAX_AGE_YEARS`, which drives `_recency_factor`) nor `fiscal_year.py`. The `rich` list omits both `prompt_loader.py` and `v2_scorers.py` even though `rich_narrative_generator.py:718-719` injects `score_band_label()` and `data_vintage_note()` into the rich prompt. Tuning the vintage threshold would be a fleet-wide silent cache hit.

**Files:**
- Modify: `data-pipeline/src/utils/phase_fingerprint.py:77-101`
- Test: `data-pipeline/tests/test_judge_content_hash.py` (or a new `tests/test_phase_fingerprint.py`)

- [ ] **Step 1: Write the failing test**

```python
def test_baseline_fingerprint_covers_prompt_and_constant_modules():
    from src.utils.phase_fingerprint import PHASE_CODE_FILES

    baseline = set(PHASE_CODE_FILES["baseline"])
    assert "src/llm/prompt_loader.py" in baseline
    assert "src/constants.py" in baseline
    assert "src/utils/fiscal_year.py" in baseline


def test_rich_fingerprint_covers_what_the_rich_prompt_injects():
    from src.utils.phase_fingerprint import PHASE_CODE_FILES

    rich = set(PHASE_CODE_FILES["rich"])
    assert "src/llm/prompt_loader.py" in rich, "rich prompt calls data_vintage_note()"
    assert "src/scorers/v2_scorers.py" in rich, "rich prompt calls score_band_label()"


def test_every_listed_fingerprint_file_exists():
    """A typo'd path silently contributes nothing to the hash."""
    from pathlib import Path
    from src.utils.phase_fingerprint import PHASE_CODE_FILES

    root = Path(__file__).parent.parent
    missing = [f for files in PHASE_CODE_FILES.values() for f in files if not (root / f).exists()]
    assert missing == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_phase_fingerprint.py -v`
Expected: FAIL on the first two

- [ ] **Step 3: Extend the lists**

Add `src/llm/prompt_loader.py`, `src/constants.py`, `src/utils/fiscal_year.py` to `baseline`; add `src/llm/prompt_loader.py` and `src/scorers/v2_scorers.py` to `rich`. Match the exact key names and path style already used in the file.

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1034 passed
git add data-pipeline/src/utils/phase_fingerprint.py data-pipeline/tests/test_phase_fingerprint.py
git commit -m "fix(cache): fingerprint the modules that now generate prompt text

prompt_loader.py, constants.py and fiscal_year.py were in no phase's
list, so tuning the vintage threshold would be a fleet-wide silent
cache hit."
```

---

### Task D7: Guard `data_vintage_note` against a non-int fiscal year

**Why:** `prompt_loader.py:243-244` guards with `if not fiscal_year`, but `filing_age_years` returns `None` for any non-`int`. A non-empty non-int (e.g. `"2023"` from a JSON round-trip) passes the guard and hits `None >= 3` → `TypeError`. Unreachable through today's call sites, but the function's own signature is `Optional[int]` and it is now in the phase fingerprint, so it will be edited.

**Files:**
- Modify: `data-pipeline/src/llm/prompt_loader.py:238-250`
- Test: `data-pipeline/tests/test_baseline_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
def test_data_vintage_note_tolerates_a_non_int_fiscal_year():
    from src.llm.prompt_loader import data_vintage_note

    note = data_vintage_note("2023")            # str from a JSON round-trip
    assert isinstance(note, str) and note

    assert isinstance(data_vintage_note(None), str)
    assert isinstance(data_vintage_note(0), str)
    assert isinstance(data_vintage_note(2024, today_year=2026), str)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_baseline_prompt.py -k non_int_fiscal_year -v`
Expected: FAIL — `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`

- [ ] **Step 3: Guard on the computed age**

```python
    age = filing_age_years(fiscal_year, today_year)
    if age is None:
        return (
            "The fiscal year of the financial data is unknown. Do not attribute "
            "financial figures to any specific year, and do not present them as current."
        )
    if age >= DATA_VINTAGE_STALE_YEARS:
```

Keep the existing `if not fiscal_year:` early return, or fold it into this single `age is None` branch if the returned text is identical — prefer one branch.

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1035 passed
git add data-pipeline/src/llm/prompt_loader.py data-pipeline/tests/test_baseline_prompt.py
git commit -m "fix(prompt): data_vintage_note guards on the computed age, not the raw year"
```

---

## Group E — Schema and staging

### Task E1: Regenerate `dolt_schema.sql` and register the crawl-history tables

**Why:** Two independent problems. (1) `last_attempt_at` appears **zero** times in `dolt_schema.sql` but is written unconditionally at `repository.py:313,323,351`, so a DB bootstrapped from that file via `import_dolt.py` fails every `RawDataRepository.upsert` and every `record_soft_fail` with `Unknown column`. `regenerate_dolt_schema.py --check` exits 1. (2) `crawl_attempts` and `crawled_pages` appear in neither `VALID_TABLES` nor `PHASE_TABLES` in `dolt_client.py`, so `commit(tables=...)` never stages them — every crawl run warns "modified but not staged," the rows live only in the working set, and the tree is permanently dirty, defeating the unconditional final commit.

**Files:**
- Modify: `data-pipeline/dolt_schema.sql` (regenerated), `data-pipeline/src/db/dolt_client.py:21-41`
- Test: `data-pipeline/tests/test_final_commit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_crawl_history_tables_are_registered_for_staging():
    """Unregistered tables are never staged, so 'durable' crawl history lived
    only in the working set and left the tree permanently dirty."""
    from src.db.dolt_client import PHASE_TABLES, VALID_TABLES

    assert "crawl_attempts" in VALID_TABLES
    assert "crawled_pages" in VALID_TABLES
    assert "crawl_attempts" in PHASE_TABLES["crawl"]
    assert "crawled_pages" in PHASE_TABLES["crawl"]


def test_schema_file_declares_every_column_the_repositories_write():
    """A column written but not declared breaks a fresh bootstrap."""
    from pathlib import Path

    schema = (Path(__file__).parent.parent / "dolt_schema.sql").read_text()
    assert "last_attempt_at" in schema
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_final_commit.py -k "registered_for_staging or declares_every_column" -v`
Expected: FAIL on both

- [ ] **Step 3: Register the tables**

In `data-pipeline/src/db/dolt_client.py`, add `"crawl_attempts", "crawled_pages"` to `VALID_TABLES`, and change the crawl phase entry to:

```python
    "crawl": ("raw_scraped_data", "charities", "phase_cache", "crawl_attempts", "crawled_pages"),
```

- [ ] **Step 4: Regenerate the schema file**

Run: `cd data-pipeline && uv run python migrations/regenerate_dolt_schema.py`
Then: `uv run python migrations/regenerate_dolt_schema.py --check` → expect exit 0, "in sync".

Review the diff before committing — it should add `last_attempt_at` to `raw_scraped_data` and relocate `crawl_attempts`/`crawled_pages` to their correct alphabetical position. If the diff contains anything else, stop and report it rather than committing.

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1037 passed
git add data-pipeline/dolt_schema.sql data-pipeline/src/db/dolt_client.py data-pipeline/tests/test_final_commit.py
git commit -m "fix(db): register crawl-history tables for staging + regenerate schema

last_attempt_at was written unconditionally but never declared, so a
fresh bootstrap failed every upsert; the two crawl tables were staged
by nothing and left the working tree permanently dirty."
```

---

### Task E2: `ensure_table()` on the crawl-history read paths

**Why:** `CrawlAttemptRepository.get_for_charity`, `CrawledPageRepository.get_for_charity`, and `get_missing_since_last_crawl` don't call `ensure_table()`, so a read before any write in a fresh process raises "table doesn't exist."

**Files:**
- Modify: `data-pipeline/src/db/repository.py:1712-1729`, `:1770-1789`
- Test: `data-pipeline/tests/test_crawl_history_repository.py`

- [ ] **Step 1: Write the failing test**

```python
def test_reads_ensure_the_table_exists_first():
    from unittest.mock import patch
    from src.db.repository import CrawlAttemptRepository, CrawledPageRepository

    for cls, call in [
        (CrawlAttemptRepository, lambda r: r.get_for_charity(EIN)),
        (CrawledPageRepository, lambda r: r.get_for_charity(EIN)),
        (CrawledPageRepository, lambda r: r.get_missing_since_last_crawl(EIN, "2026-07-23 12:00:00")),
    ]:
        cls._table_ensured = False
        with patch("src.db.repository.execute_query", return_value=[]) as mock_exec:
            call(cls())
        sqls = [c.args[0] for c in mock_exec.call_args_list]
        assert any("CREATE TABLE IF NOT EXISTS" in s for s in sqls), f"{cls.__name__} read did not ensure_table"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_history_repository.py -k reads_ensure -v`
Expected: FAIL

- [ ] **Step 3: Add the calls**

Add `self.ensure_table()` as the first statement of all three read methods.

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1038 passed
git add data-pipeline/src/db/repository.py data-pipeline/tests/test_crawl_history_repository.py
git commit -m "fix(db): crawl-history reads ensure their table exists"
```

---

## Group F — Frontend

### Task F1: Type `fiscalYear` where the data actually lives, and use the published age

**Why:** Two problems in one component. (1) `types.ts:1112` added `fiscalYear?: number | null` to `CharityProfile`, which models the **detail** file — but **0 of 166** detail files have a top-level `fiscalYear` (the detail export puts it at `financials.fiscalYear`, already typed at `types.ts:776`). The field `export.py:1568` writes lands on **index** entries, typed by `CharitySummary` in `src/hooks/useCharities.ts:19-77`, which was not updated. So `charity.fiscalYear` type-checks clean and is `undefined` forever, while `summary.fiscalYear` — which does exist in 166/166 — fails to compile. (2) `GmgCharityDetail.tsx:208` computes the age from `new Date().getFullYear()` at both prerender and hydration time, while the backend already publishes `amalEvaluation.score_details.data_confidence.data_age_years` in all 166 detail files. 124 charities are FY2024, so on 2027-01-01 they all cross `age >= 3` at once: a December build serves `FY2024 · IRS 990` and the client re-renders `FY2024 · DATED DATA` — a hydration mismatch across ~124 prerendered pages, with a caution badge appearing sitewide overnight behind no pipeline run.

**Files:**
- Modify: `website/types.ts:1112`, `website/src/hooks/useCharities.ts:19-77` (+ `summaryToProfile`), `website/src/lib/charityAdapter.ts`, `website/src/components/gmg/GmgCharityDetail.tsx:205-215,485-501`
- Test: `website/src/components/gmg/GmgCharityDetail.fiscalYear.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import GmgCharityDetail from './GmgCharityDetail'

const base = {
  ein: '12-3456789', name: 'Test Charity',
  financials: { fiscalYear: 2024, totalRevenue: 1000000 },
  amalEvaluation: { amal_score: 60, score_details: { data_confidence: { data_age_years: 1 } } },
}

const renderDetail = (charity: any) =>
  render(<MemoryRouter><GmgCharityDetail charity={charity} /></MemoryRouter>)

describe('GmgCharityDetail — fiscal year badge', () => {
  it('uses the published data_age_years, not the wall clock', () => {
    renderDetail({ ...base,
      amalEvaluation: { ...base.amalEvaluation, score_details: { data_confidence: { data_age_years: 5 } } } })
    expect(screen.getByText(/DATED DATA/i)).toBeInTheDocument()
  })

  it('shows the source attribution when the data is current', () => {
    renderDetail(base)
    expect(screen.queryByText(/DATED DATA/i)).not.toBeInTheDocument()
    expect(screen.getByText(/IRS 990/i)).toBeInTheDocument()
  })

  it('renders nothing age-related when fiscalYear is null', () => {
    renderDetail({ ...base, financials: { fiscalYear: null },
      amalEvaluation: { ...base.amalEvaluation, score_details: { data_confidence: { data_age_years: null } } } })
    expect(screen.queryByText(/DATED DATA/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/years old/i)).not.toBeInTheDocument()
  })

  it('keeps the badge but adds exempt context for a form-990-exempt org', () => {
    renderDetail({ ...base, form990Exempt: 1,
      financials: { fiscalYear: 2022 },
      amalEvaluation: { ...base.amalEvaluation, score_details: { data_confidence: { data_age_years: 4 } } } })
    expect(screen.getByText(/DATED DATA/i)).toBeInTheDocument()
    expect(screen.getByText(/not required to file/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd website && npx vitest run src/components/gmg/GmgCharityDetail.fiscalYear.test.tsx`
Expected: FAIL

- [ ] **Step 3: Fix the types**

In `website/src/hooks/useCharities.ts`, add to `CharitySummary`:

```ts
  fiscalYear?: number | null
```

and forward it in `summaryToProfile`. In `website/types.ts:1112`, remove `fiscalYear` from `CharityProfile` (the detail file exposes it at `financials.fiscalYear`, already typed at `:776`).

- [ ] **Step 4: Surface the published age through the adapter**

In `website/src/lib/charityAdapter.ts`, expose `dataAgeYears` from `amalEvaluation.score_details.data_confidence.data_age_years` using the existing `numOrNull` helper, alongside the existing `fiscalYear` mapping at `:280`.

- [ ] **Step 5: Use it in the component**

In `GmgCharityDetail.tsx`, replace the `new Date().getFullYear()` computation at `:208-209` with the adapter's `dataAgeYears`, keeping the same `>= 3` threshold and the same null-guard structure (`fyDated` requires a non-null age). Per the user's decision, when `fyDated` is true: **keep the badge, and keep the source attribution rather than replacing it** — render `FY2023 · IRS 990 · DATED DATA`. When `form990Exempt` is truthy (note it is exported as integer `0`/`1` at `export.py:1810` despite being typed `boolean | null`, so use a truthiness check, never `=== true`), append the exempt context, e.g. `· not required to file`.

Also move the explanatory `title=` tooltip text into visible markup or an `aria-label` — `title` never appears on touch devices, so mobile users currently see an unexplained caution chip.

- [ ] **Step 6: Run the tests**

```bash
cd website && npx vitest run   # expect 256 passed
npx tsc --noEmit 2>&1 | grep -E "GmgCharityDetail|types.ts|useCharities|charityAdapter" || echo "no new type errors in touched files"
```

Note: `npx tsc --noEmit` reports 35 pre-existing errors (33 missing vitest globals in test files, 2 in the untouched `GmgBrowse.tsx:164`). Confirm your count is still 35 plus nothing from the files you touched.

- [ ] **Step 7: Commit**

```bash
git add website/types.ts website/src/hooks/useCharities.ts website/src/lib/charityAdapter.ts website/src/components/gmg/
git commit -m "fix(web): type fiscalYear on CharitySummary + badge uses the published age

The type went on CharityProfile where the field does not exist, so it had
zero consumers. The badge recomputed the age from the wall clock, which
would flip 124 prerendered FY2024 pages against a stale SSR on 2027-01-01."
```

---

## Group G — Pre-existing donor-facing defects

These predate the branch. The user explicitly asked for them.

**Note on `cash_adjusted_program_ratio`:** the falsy-`0` bug and the missing upper clamp are the same expression family and land together in G1.

### Task G1: Fix the cash-adjusted program ratio (falsy zero + missing upper clamp)

**Why:** `v2_scorers.py:1524` and `:2428` both use `ratio = metrics.cash_adjusted_program_ratio or metrics.program_expense_ratio`. `charity_metrics_aggregator.py:1741` clamps with `max(0.0, adjusted)`, so a GIK-heavy org whose entire program spend is in-kind lands on exactly `0.0` — falsy, so the `or` discards it and scores the raw filed ratio. Verified: `program_expense_ratio=0.92, cash_adjusted_program_ratio=0.0` scores **6/6** with evidence `"Program expense ratio: 92%"` and no `program_ratio_under_50` deduction — the worst GIK-inflation case scores identically to a genuinely efficient charity. Separately there is no upper clamp (the raw path one screen up at `:1723` uses `min(1.0, …)`), so a ratio of 1.3 produces `"Cash-adjusted program ratio: 130%"`, which commit `3f16fc2` now injects verbatim into the narrative prompt as a mandatory value.

**Files:**
- Modify: `data-pipeline/src/scorers/v2_scorers.py:1524,2428`, `data-pipeline/src/parsers/charity_metrics_aggregator.py:1741`
- Test: `data-pipeline/tests/test_v2_scorers.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_a_fully_in_kind_charity_does_not_score_on_its_filed_ratio():
    """cash_adjusted 0.0 is falsy, so `or` fell back to the 92% filed ratio and
    the worst GIK-inflation case scored 6/6."""
    from src.scorers.v2_scorers import ImpactScorer

    metrics = _metrics(program_expense_ratio=0.92, cash_adjusted_program_ratio=0.0)
    scored, _evidence = _score_program_ratio(ImpactScorer(), metrics)

    assert scored == 0, "a 0% cash-adjusted ratio must score 0, not 6"


def test_risk_deduction_fires_on_a_zero_cash_adjusted_ratio():
    from src.scorers.v2_scorers import RiskScorer

    metrics = _metrics(program_expense_ratio=0.92, cash_adjusted_program_ratio=0.0)
    deduction, factors = _deduction(RiskScorer(), metrics)

    assert any("program_ratio_under_50" in str(f) for f in factors)


def test_a_present_nonzero_cash_adjusted_ratio_still_wins():
    from src.scorers.v2_scorers import ImpactScorer

    metrics = _metrics(program_expense_ratio=0.92, cash_adjusted_program_ratio=0.55)
    scored, evidence = _score_program_ratio(ImpactScorer(), metrics)
    assert "55" in str(evidence)


def test_missing_cash_adjusted_ratio_falls_back_to_the_filed_ratio():
    from src.scorers.v2_scorers import ImpactScorer

    metrics = _metrics(program_expense_ratio=0.92, cash_adjusted_program_ratio=None)
    scored, evidence = _score_program_ratio(ImpactScorer(), metrics)
    assert "92" in str(evidence)


def test_cash_adjusted_ratio_is_clamped_to_one():
    """1.3 rendered as 'Cash-adjusted program ratio: 130%' into the narrative
    prompt as a MANDATORY VALUE."""
    from src.parsers.charity_metrics_aggregator import _compute_cash_adjusted_ratio

    assert _compute_cash_adjusted_ratio(program_expenses=130, total_expenses=100, noncash=0) == 1.0
    assert _compute_cash_adjusted_ratio(program_expenses=0, total_expenses=100, noncash=0) == 0.0
```

Build `_metrics`, `_score_program_ratio`, and `_deduction` helpers from the fixtures already in `test_v2_scorers.py`. If the aggregator's clamp is inline rather than a named function, either extract `_compute_cash_adjusted_ratio` as part of this task (preferred — it makes the clamp testable) or assert the clamp through the aggregator's public entry point.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_v2_scorers.py -k "in_kind or zero_cash_adjusted or clamped_to_one" -v`
Expected: FAIL

- [ ] **Step 3: Fix the falsy `or` at both sites**

At `data-pipeline/src/scorers/v2_scorers.py:1524` and `:2428`:

```python
        # `or` treated a real 0.0 as absent, so a charity whose entire program
        # spend is in-kind scored on its filed ratio instead — the worst
        # GIK-inflation case scored identically to a genuinely efficient one.
        ratio = (
            metrics.cash_adjusted_program_ratio
            if metrics.cash_adjusted_program_ratio is not None
            else metrics.program_expense_ratio
        )
```

- [ ] **Step 4: Clamp the upper bound**

At `data-pipeline/src/parsers/charity_metrics_aggregator.py:1741`:

```python
                        # Clamp both ends, matching the raw ratio path above —
                        # an unclamped 1.3 rendered as "130%" into the narrative
                        # prompt as a mandatory value.
                        metrics_data["cash_adjusted_program_ratio"] = max(0.0, min(1.0, adjusted))
```

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q   # expect 1043 passed
git add data-pipeline/src/scorers/v2_scorers.py data-pipeline/src/parsers/charity_metrics_aggregator.py data-pipeline/tests/test_v2_scorers.py
git commit -m "fix(rubric): cash-adjusted program ratio — real 0.0 counts, and clamp at 1.0

A fully in-kind charity scored 6/6 on its filed 92% ratio because 0.0 is
falsy; an unclamped ratio rendered as '130%' into the narrative prompt."
```

---

### Task G2: Fix the mangled Charity Navigator scores in narrative prose

**Root cause (reproduced):** `baseline.py:914`. The CN correction rule's regex is `r"\d+/100\s+..."` — no decimal allowance, no left anchor — while its replacement value `correct_cn = f"{cn_score}/100"` (`:911`) is the **raw unrounded** float (`cn_overall_score` is an average of CN beacon sub-scores, hence `.66666666666667`, `.5`, `.25`). When the LLM correctly writes the full decimal, the unanchored `\d+` matches only the trailing digit-run before `/100` (`66666666666667`) and `re.sub` replaces that tail with the whole correct value, leaving the `98.` prefix. Net: `98.` + `98.66666666666667/100`.

The AMAL-score rule 140 lines below (`:1054`) already uses the safe `r"\d+\.?\d*/100\s+..."`. The CN rule is the only one combining an unrounded replacement with a decimal-excluding pattern.

Verified reproduction (byte-for-byte match to published `charity-20-3060929.json`), and it is **non-idempotent** — `sanitize_narrative_metrics` is called twice per generation attempt on the retry path, so it compounds:

```
OUT: The charity holds an overall score of 98.98.66666666666667/100 from Charity Navigator.
IDEMPOTENT? False
```

**Blast radius:** 35 EINs. Baseline-only (23): 13-1760110, 13-3377893, 13-3626299, 13-5562162, 13-5660870, 13-6213516, 20-0942434, 20-2714426, 20-3069841, 20-4751162, 26-1140201, 36-3673599, 47-2864379, 47-3342673, 47-5165837, 56-2500794, 75-2352043, 76-0656947, 81-2822877, 81-3072596, 81-3135852, 91-1914868, 95-4453134. Rich-only (11): 04-3810161, 26-3342933, 38-3633581, 46-2431099, 46-3973114, 47-0946122, 47-3564801, 77-0519274, 77-0646756, 83-0919620, 87-2410117. Both (1): 20-3060929. No other numeric claim is affected — every other correction rule rounds its replacement AND allows a decimal in the pattern.

**Files:**
- Modify: `data-pipeline/baseline.py:911-918` (regex + rounding), `:575` (prompt value), `data-pipeline/src/services/rich_narrative_generator.py:1274` (prompt value)
- Test: `data-pipeline/tests/test_baseline_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
class TestCnScoreSanitizationIsIdempotent:
    """baseline.py:914's `\\d+/100` matched only the digits AFTER the decimal
    point, so re.sub re-inserted the full value and left the integer prefix:
    98. + 98.66666666666667/100. Non-idempotent, and sanitize runs twice on
    the retry path."""

    def _sanitize(self, text, cn_score):
        from types import SimpleNamespace
        from baseline import sanitize_narrative_metrics
        metrics = SimpleNamespace(cn_overall_score=cn_score, cn_accountability_score=None,
                                  cn_financial_score=None, fundraising_expenses=1000,
                                  total_revenue=100000, program_expense_ratio=None,
                                  working_capital_ratio=None)
        return sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]

    def test_the_rounded_value_is_left_alone(self):
        """Idempotency: sanitizing already-correct text must be a no-op."""
        text = "The charity holds an overall score of 98.7/100 from Charity Navigator."
        assert self._sanitize(text, 98.66666666666667) == text

    def test_an_unrounded_value_is_replaced_not_doubled(self):
        """The bug: \\d+/100 matched only '66666666666667', leaving the '98.' prefix."""
        import re
        out = self._sanitize(
            "Scored 98.66666666666667/100 from Charity Navigator.", 98.66666666666667)
        assert "98.7/100 from Charity Navigator" in out
        assert not re.search(r"\d+\.\d+\.\d+/100", out)

    def test_sanitizing_twice_is_a_no_op(self):
        text = "Rated 87.5/100 from Charity Navigator."
        once = self._sanitize(text, 87.5)
        assert self._sanitize(once, 87.5) == once

    def test_a_wrong_value_is_replaced_not_concatenated(self):
        out = self._sanitize("Rated 42/100 from Charity Navigator.", 87.5)
        assert "87.5/100 from Charity Navigator" in out
        assert "42" not in out
```

Read `sanitize_narrative_metrics`'s real signature first and adapt the `_sanitize` helper — the assertions are what matter.

**Note:** these tests target the FINAL behavior after both Step 3 and Step 4. Steps 3 and 4 are one logical change — the regex fix alone leaves a 17-digit decimal in donor prose, and the rounding alone still doubles. Make both edits before re-running.

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_baseline_prompt.py::TestCnScoreSanitizationIsIdempotent -v`
Expected: FAIL — `test_an_unrounded_value_is_replaced_not_doubled` produces `98.98.66666666666667/100`

- [ ] **Step 3: Fix the regex**

At `data-pipeline/baseline.py:914`, change the pattern to allow the decimal so the match consumes the whole existing number (mirroring the AMAL rule at `:1054`):

```python
                r"\d+\.?\d*/100\s+(?:from\s+|by\s+|on\s+|score\s+(?:from\s+|on\s+)?)?(?:Charity\s+Navigator)",
```

- [ ] **Step 4: Round the CN score before it reaches prose**

A 17-digit repeating decimal in donor-facing text is wrong independent of this bug. At `data-pipeline/baseline.py:911`:

```python
        # Round before it ever reaches prose — cn_overall_score is an average of
        # CN's beacon sub-scores, so it carries repeating decimals
        # (98.66666666666667). One decimal place is what a donor should read.
        correct_cn = f"{round(cn_score, 1)}/100"
```

Apply the same rounding to the prompt values at `data-pipeline/baseline.py:575` and `data-pipeline/src/services/rich_narrative_generator.py:1274`, so the "use this exact value" instruction hands the model the rounded number in the first place.

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q
git add data-pipeline/baseline.py data-pipeline/src/services/rich_narrative_generator.py data-pipeline/tests/test_baseline_prompt.py
git commit -m "fix(narrative): CN-score sanitizer doubled its own correct output

\\d+/100 matched only the digits after the decimal, so re.sub re-inserted
the full value and left the integer prefix: 98.98.66666666666667/100.
Non-idempotent, and sanitize runs twice on the retry path. 35 published
charities carry the mangled text until regenerated."
```

---

### Task G3: Make the fundraising-efficiency strip actually strip

**Root cause (reproduced):** NOT an arithmetic bug. `baseline.py:579-582` correctly guards the prompt — when `fundraising_expenses is None` the prompt says `Fundraising Efficiency: N/A`, and `baseline_narrative.txt:36` instructs the model not to mention N/A metrics. The model disobeys and hallucinates `$0.00` — including, on `84-5191730`, a **fabricated citation** attributing it to Charity Navigator, a source that never reported the field.

The failure is that the deterministic safety net meant to catch this doesn't match. The strip rules at `baseline.py:1033-1047` require the dollar amount to sit *immediately* before the phrasing (`\$\d+\.?\d*\s+{_fr_phrasing}`), but real output interposes words. All three real published strings miss:

```
re.search(pattern1, "Exceptional fundraising efficiency of $0.00 spent per $1 raised [1].")   -> None
re.search(pattern1, "Operates with high fundraising efficiency, spending $0.00 to raise every $1 in FY2025") -> None
re.search(pattern2, "...and a $0.00 fundraising efficiency rate.")                            -> None
```

**The GMG score is NOT affected** — verified: no Impact or Alignment component reads fundraising data, and the only risk signal (`checks.py:214-248`, `high_fundraising_ratio`) fires at ratio ≥ 0.25 and treats None as absent. This is purely a prose bug.

**Blast radius:** 42 files have `fundraisingExpenses: null`; **34** of them carry the hallucinated claim. The 8 clean ones (model happened to obey): 20-5509305, 22-2086228, 31-1267559, 52-2283398, 81-3451645, 85-3964369, 93-2136609, 99-3032347.

**Files:**
- Modify: `data-pipeline/baseline.py:1033-1047`, `data-pipeline/src/judges/prompts/factual_judge.txt:51-56`
- Test: `data-pipeline/tests/test_baseline_prompt.py`

- [ ] **Step 1: Write the failing test using the REAL published strings as fixtures**

```python
class TestFundraisingClaimIsStrippedWhenDataIsMissing:
    """The model hallucinates $0.00 despite an N/A prompt; the deterministic
    strip is the safety net, and its adjacency requirement made it miss every
    real phrasing. Fixtures below are verbatim from published charities."""

    REAL_HALLUCINATIONS = [
        "Exceptional fundraising efficiency of $0.00 spent per $1 raised [1].",
        "Operates with high fundraising efficiency, spending $0.00 to raise every $1 in FY2025.",
        "The charity has a 91.1% program expense ratio, and a $0.00 fundraising efficiency rate.",
    ]

    def _sanitize_with_null_fundraising(self, text):
        from types import SimpleNamespace
        from baseline import sanitize_narrative_metrics
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        return sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]

    def test_every_real_hallucination_is_stripped(self):
        for text in self.REAL_HALLUCINATIONS:
            out = self._sanitize_with_null_fundraising(text)
            assert "$0.00" not in out, f"not stripped: {text!r}"

    def test_unrelated_sentences_survive(self):
        text = "The charity has a 91.1% program expense ratio. It serves 4,000 families."
        out = self._sanitize_with_null_fundraising(text)
        assert "91.1% program expense ratio" in out
        assert "4,000 families" in out

    def test_strengths_array_entries_are_stripped_too(self):
        from types import SimpleNamespace
        from baseline import sanitize_narrative_metrics
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        out = sanitize_narrative_metrics(
            {"strengths": ["Exceptional fundraising efficiency of $0.00 spent per $1 raised [1]."]},
            metrics, None)
        assert "$0.00" not in str(out["strengths"])
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_baseline_prompt.py::TestFundraisingClaimIsStrippedWhenDataIsMissing -v`
Expected: FAIL on `test_every_real_hallucination_is_stripped` for all three fixtures

- [ ] **Step 3: Replace adjacency with same-sentence co-occurrence**

Replace the two strip rules at `data-pipeline/baseline.py:1033-1047` with one rule that removes any sentence containing a dollar amount AND fundraising-efficiency phrasing, in either order and with arbitrary words between:

```python
    else:
        # The model hallucinates a $0.00 efficiency claim even when the prompt
        # says N/A, so this deterministic strip is the real safety net. The old
        # rules required the dollar amount to sit IMMEDIATELY before the
        # phrasing, which missed every real phrasing observed in production
        # ("$0.00 spent per $1 raised", "spending $0.00 to raise every $1",
        # "a $0.00 fundraising efficiency rate"). Match on co-occurrence within
        # one sentence instead of adjacency.
        rules.append(
            (
                rf"[^.]*\$\d+\.?\d*[^.]*(?:{_fr_phrasing}|fundraising\s+efficiency)[^.]*\.?",
                None,
                True,
            )
        )
        rules.append(
            (
                rf"[^.]*fundraising\s+efficiency[^.]*\$\d+\.?\d*[^.]*\.?",
                None,
                True,
            )
        )
```

Confirm `_fr_phrasing` still covers the observed variants; extend it if the tests show a gap.

- [ ] **Step 4: Close the judge's severity gap**

The factual judge's own rubric (`data-pipeline/src/judges/prompts/factual_judge.txt:51-56`) says *"warning: Claim can't be verified (no corresponding source data)"* — so "narrative cites a number for a null field" was correctly classified as a non-gating warning. That instruction is what let this reach 34 charities. Add an explicit ERROR rule above it:

```
- error: The narrative states a specific numeric value for a field that is
  null or absent in the source data. This is fabrication, not an
  unverifiable claim — a number that no source reported must never appear
  in donor-facing prose, and a citation attributing it to a source that
  did not report it is a compounding error.
```

- [ ] **Step 5: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q
git add data-pipeline/baseline.py data-pipeline/src/judges/prompts/factual_judge.txt data-pipeline/tests/test_baseline_prompt.py
git commit -m "fix(narrative): strip hallucinated fundraising claims on same-sentence match

The model invents '\$0.00 per \$1 raised' when fundraising_expenses is
null (one case fabricated a Charity Navigator citation for it). The
deterministic strip required the dollar amount to be adjacent to the
phrasing and missed every real phrasing. 34 published charities carry
the claim until regenerated. Also promotes 'cites a number for a null
field' from warning to error in the factual judge's rubric."
```

---

### Task G4: Don't render a real-but-tiny fundraising ratio as `$0.00`

**Why:** Separate from G3 and found while measuring its blast radius. 10 charities have real, non-null, non-zero `fundraisingExpenses` whose true ratio rounds to `$0.00` under `:.2f` — e.g. `63-1135091`: $241,666 / $79.6M = $0.003 per $1. The data is correct; the formatting makes a real cost read as zero. Affected: 63-1135091, 86-1226156, 77-0442850, 47-1675693, 77-0412815, 94-3311132, 75-2882187, 56-2500794, 95-1831116, 72-1128279.

**Files:**
- Modify: `data-pipeline/baseline.py:579-582`
- Test: `data-pipeline/tests/test_baseline_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_tiny_but_real_fundraising_ratio_is_not_rendered_as_zero():
    """$241,666 / $79.6M = $0.003 per $1 — real, and not zero."""
    from baseline import _format_fundraising_efficiency

    assert _format_fundraising_efficiency(241666, 79_600_000) == "<$0.01 per $1 raised"
    assert _format_fundraising_efficiency(0, 100_000) == "$0.00 per $1 raised"
    assert _format_fundraising_efficiency(None, 100_000) == "N/A"
    assert _format_fundraising_efficiency(10_000, 100_000) == "$0.10 per $1 raised"
    assert _format_fundraising_efficiency(10_000, 0) == "N/A"
    assert _format_fundraising_efficiency(10_000, None) == "N/A"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd data-pipeline && uv run pytest tests/test_baseline_prompt.py -k tiny_but_real -v`
Expected: FAIL — `ImportError: cannot import name '_format_fundraising_efficiency'`

- [ ] **Step 3: Extract and fix the formatter**

Add to `data-pipeline/baseline.py` and call it from `_baseline_prompt_kwargs` (`:579-582`):

```python
def _format_fundraising_efficiency(fundraising_expenses, total_revenue) -> str:
    """Cost to raise $1, as prose. "N/A" when unknowable.

    A real-but-tiny ratio must not render as "$0.00": $241,666 against $79.6M
    revenue is $0.003 per $1 — a real cost, and telling a donor it was zero is
    wrong. Only a genuine 0 gets "$0.00".
    """
    if fundraising_expenses is None or not total_revenue or total_revenue <= 0:
        return "N/A"
    efficiency = fundraising_expenses / total_revenue
    if efficiency == 0:
        return "$0.00 per $1 raised"
    if efficiency < 0.01:
        return "<$0.01 per $1 raised"
    return f"${efficiency:.2f} per $1 raised"
```

- [ ] **Step 4: Run the tests, full suite, and commit**

```bash
cd data-pipeline && uv run pytest -q
git add data-pipeline/baseline.py data-pipeline/tests/test_baseline_prompt.py
git commit -m "fix(narrative): a real-but-tiny fundraising ratio is not \$0.00

10 charities with real fundraising costs rendered as \$0.00 because
\$0.003 per \$1 rounds to zero at 2dp."
```

---

## Deliberately deferred (recorded so they aren't silently dropped)

These came out of the same review. Each is real but low-value relative to its blast radius, and none is donor-facing. Do NOT fix them in this plan — they are listed so a later pass can pick them up knowingly.

- **`crawl_attempts` PK has second granularity** (`repository.py:1676`) — `PRIMARY KEY (charity_ein, source, attempted_at)` on a plain `TIMESTAMP`. Two attempts for one (ein, source) inside one second collide. Task C5 makes the resulting exception harmless; the collision itself remains. Fix would need a schema change.
- **No backoff for the `failed` website state** (`freshness.py:81-86`) — backoff applies only to `stale`, so every streaming run re-runs the crawl phase for any charity whose website row is `failed` or `missing`, including charities with `website = NULL` that can never converge. Cheap per run, permanent noise. Task C1 removes the harmful half of this (the hammering); what remains is wasted phase-cache churn.
- **`select_stale_website_eins` scans the whole charities table** (`crawl.py:69`) — `--refresh-stale` alone picks up retired/hidden EINs not in `pilot_charities.txt`.
- **Naive DB timestamps treated as local time** (`freshness.py:15-29`, `orchestrator.py:159-179`) — negative ages are reachable; immaterial at 7/30/180-day granularity.
- **Shared `"website"` rate-limiter key** across two very different intervals (2.0s vs 0.2s), and `GlobalRateLimiter.wait` sleeps while holding the lock — roughly 5 min of added wall-clock across a 169-charity fleet run.
- **Retry-path cost accounting** (`judge_phase.py:237`) — drops the first judge run's cost and double-counts `retry_rich_cost` across the `rich` and `judge` phase-cache rows. Reporting only; budget enforcement is correct because `llm_client.py:488` accounts at the source.
- **B-J-014 is structurally inert** (`baseline_quality_judge.py:804`) — compares ProPublica's `irs_ruling_year` against a `founded_year` that falls back to the same value, so the gap is 0 and it never fires. Non-gating warning, so the cost is missed signal.
- **`ScoreComponent.status` disagrees with `scored`** for cash-adjusted-only charities (`v2_scorers.py:1073-1075`).
- **Export-quality pillar-sum window** (`export_quality_judge.py:340-343`) — a `+14` window where an exact `pillar_sum + risk_deduction == amal_score` assertion would catch far more.
- **`judge_model_override` beats an explicit config** (`base_judge.py:108`).
- **QPS tests assert the call, not the ceiling** (`test_crawl_politeness.py:705,734,764,830`) — defensible given the limiter is a real process-wide lock, but nothing verifies composed behavior.

## A note on the test counts in this plan

Each task states an expected total (`998 passed` → `1001` → …). Those are indicative and assume the tasks run in written order with the exact test counts shown. If you add a test or run out of order the totals shift — what matters is that **the suite is green and the number only ever goes up**. Never delete a test to make a count match.

## Final verification

- [ ] **Full Python suite:** `cd data-pipeline && uv run pytest -q` → all green
- [ ] **Frontend suite:** `cd website && npx vitest run` → all green
- [ ] **Lint unchanged:** `uv run ruff check . 2>&1 | tail -2` → still 50 errors, none new
- [ ] **Schema in sync:** `cd data-pipeline && uv run python migrations/regenerate_dolt_schema.py --check` → exit 0
- [ ] **No published data touched:** `git status --short website/data/` → empty
- [ ] **Working tree clean, nothing pushed:** `git status --short` empty; `git log origin/main..HEAD --oneline` shows only local commits

## Known-remaining after this plan

State these plainly when reporting completion — they are not fixed by code alone:

- EINs `31-1267559`, `81-3451645`, `88-2454707` keep their inconsistent published financials until re-synthesized.
- The 18 EINs with a NULL `total_liabilities` column and `metrics_json` `0` keep the NULL until re-synthesized.
- **34 charities** keep the hallucinated `$0.00` fundraising claim, **35** keep the mangled CN score, and **10** keep a real-but-tiny ratio shown as `$0.00`, until narratives are regenerated. The EIN lists are in Tasks G2, G3, and G4 — a targeted re-run needs `baseline.py` for the baseline-narrative cases and `rich_phase.py` for the rich-narrative cases, per the split recorded in G2.
- One charity (`84-5191730`) carries a **fabricated citation** attributing the invented `$0.00` figure to Charity Navigator. The code fix stops new ones; that page keeps it until regenerated.
- Every charity judged before this branch stays excluded from export until re-judged (`JUDGE_PROJECTION_FIELDS` went 12 → 8, changing the content hash) — a bare `export.py` run publishes only what has been re-judged.

# Non-Destructive Synthesize — Write/Recovery Safety Design

**Status:** Approved design (brainstorm 2026-07-19). Spec A of a two-part effort;
Spec B (crawl hardening) is a separate follow-up spec.

**Branch:** `worktree-pipeline-review-v53-prep` (18 commits ahead of `origin/main`).
Builds on the crawl-thread commits `cee8ce5..cc37669`.

**Scope:** Make the synthesize→persist path non-destructive so a transient/degraded
data source or a recompute gap can never overwrite a previously-good value in the
`charity_data` working row. Plus a Dolt-history-based recovery path for rows already
damaged.

**Out of scope (→ Spec B, crawl hardening):** fleet-scale politeness/backoff,
transactional phase writes (no partial-batch), TTL/freshness correctness, and
*permanent* vs transient failure detection. The honest-observation detectors defined
here are deliberately minimal; Spec B deepens them.

---

## Motivation

The pipeline's recent "crawl is corrupting data" thread patched five *causes* of a bad
website crawl (stale cache `da32156`, TLS-fingerprint 404 `dc9de11`, throttle-empty
`cee8ce5`, a prog-ratio recompute gap `77bb563`, judge scoping `cc37669`). An
adversarial 8-vector audit (23 agents, 2026-07-19) established that **the corruption is
not in the crawler — it is one structural defect at the write sink:**

> `CharityDataRepository.upsert` (`src/db/repository.py:575`) is an unconditional
> full-column overwrite (`` `col` = VALUES(`col`) `` for every column,
> `repository.py:597,602`; docstring `:578-581` explicitly declines partial-update
> protection), and `synthesize_charity` (`synthesize.py:1510`) builds a **fresh**
> `CharityData` from only *this run's* sources — it never reads the prior row. So any
> field that recomputes to `None`/empty this pass is written straight over the
> prior-good value.

Two classes of trigger reach this sink:

1. **Soft-fail sources** — a source returns `success=True` while empty/degraded, so no
   gate fires. Confirmed cases: throttle-empty website demoted to "optional"
   (`orchestrator.py:792-795`, marker `:135`) leaving website-derived fields null; a
   ProPublica grants org-page throttle returning an empty-but-successful profile
   (`form990_grants.py:139-142`) nulling the grants ratios.
2. **Recompute gaps** — all sources observed, but a derived computation yields null due
   to a code gap. This is the Al-Furqaan case: `program_expense_ratio` 0.85 → None →
   impact 8/50 (`77bb563`), with every raw source intact.

The *hard*-failure crawl cases (fingerprint-404, CAPTCHA, hard block) are already safe:
the strict-completeness gate (`orchestrator.py:782-802` + `streaming_runner.py:903-907`)
aborts the charity before synthesize, and the C1 raw guard (`repository.py:283-288`)
preserves last-good content. The damage is confined to the two classes above.

### Why not the audit's first suggestion (`COALESCE(VALUES(col), col)`)

A blanket "never overwrite a non-null with a null" rule is wrong for this domain:
charity data is filed **annually**, and a metric legitimately reported one year can be
genuinely dropped the next. `null` is a *valid* value when the source was observed and
the value is truly gone. A blind COALESCE would freeze stale values forever — corruption
in the other direction. The correct invariant is observation-based, defined below.

---

## The invariant (the contract)

**A field changes only on new information about that field's source.** `null` is
disambiguated from a single overloaded value into two distinct meanings —
*known-absent* (source observed, value genuinely gone) versus *unknown* (source not
observed this run) — and only *known-absent* may overwrite.

| This run's observation of the source | Age of last-good | Write |
|---|---|---|
| observed, value present | — | write value |
| observed, value genuinely absent | — | **write null** (valid known-absent) |
| **not** observed (hard-fail *or* soft-fail) | last-good **≤ 2 yr** | **carry forward** last-good (retain original observation timestamp) |
| **not** observed | last-good **> 2 yr** | **drop to null** (aged-out — no longer credibly current) |
| observed, value regressed suspiciously | — | **preserve prior + flag** to editorial queue |

Notes that make the table unambiguous:

- **Staleness is per-source.** Each source carries its own last-observation timestamp,
  reset on every successful re-observation. A broadly-fresh charity with one lagging
  source drops only that source's fields.
- **The 2-year drop is deliberate and does not trip the regression guard.** The
  preserve-prior+flag guard (§3) applies to **observed** sources only. Aged-out drops go
  to null silently; the existing recency/vintage signals already communicate staleness
  to users. The editorial queue stays reserved for genuine anomalies.
- **One staleness constant.** The 2-year ceiling is the same constant that drives the
  rubric's data-confidence recency decay ("full weight through age 2, then decay").
  Define it once; both consumers import it. No competing staleness numbers.
- **Observation clock.** Carry-forward staleness is keyed on *last successful
  observation of the source* (fetch/crawl date), not the data's own fiscal-year vintage.
  It composes with — does not replace — the existing fiscal-year recency decay.

---

## Architecture

Three cooperating pieces, each small and each reusing existing machinery. The persist
layer stays a dumb writer — all decision logic lives at synthesize time, so
`CharityDataRepository.upsert` needs **no** SQL COALESCE and no caller changes.

```
crawl ─▶ raw_data rows (per source: success flag, parsed_json, observed_at)
             │
             ├─ (1) honest observation:  observed = success AND passes substance floor
             │
synthesize ─▶ per source, pick input:
             │     observed        → this-run parsed_json
             │     unobserved ≤2yr  → last-good parsed_json (C1-preserved)  [carry forward]
             │     unobserved >2yr  → omit                                  [aged-out drop]
             │
             ├─ aggregator recomputes over the assembled inputs
             │
             ├─ (3) regression guard: diff new row vs prior (Dolt);
             │        observed-source field non-null→null / large swing
             │        → restore prior value + emit editorial-queue flag
             │
persist ────▶ CharityDataRepository.upsert (unchanged — writes the corrected object)
             │
recovery ───▶ reconciliation script walks Dolt history to find already-damaged
              fields (currently null, prior last-good present) → confirm-or-restore
```

---

## 1. Honest observation

A source counts as **observed** only if `success=True` **and** it clears a substance
floor.

- **Website:** the floor already exists — `_has_content_substance`
  (`orchestrator.py:510`) — but is wired *only* into `_store_raw_content_only`
  (`:570`), the generic-source path. The website store goes through `_store_raw_data`
  (`:753`), which gates on `_is_meaningful_data` (`:1258→1203`) — true for any non-empty
  dict. Wire a richness/substance floor into the website store so a thin 1-2 page crawl
  is recorded `success=False` (kills Vector 5, the degraded-but-non-empty clobber).
- **Form-990 grants:** an empty-but-`success=True` profile
  (`form990_grants.py:488-494,622-631`) must be treated as unobserved (kills Vector 2's
  trigger).

This is the seam Spec B later deepens (richer soft-fail detection, permanent-failure
classification). Here it is intentionally minimal — just enough that "observed" stops
lying for the two confirmed soft-fail sources.

## 2. Bounded last-good carry-forward

The C1 guard (`repository.py:283-288`) *already preserves* the last-good `parsed_json`
when a source write fails — but the audit found that preserved content is thrown away by
the `success` gate at `synthesize.py:1410` (`if rd.get("success") and rd.get("parsed_json")`).

Change synthesize's per-source input selection to:

- **observed** → use this-run `parsed_json`.
- **unobserved, last-good ≤ 2 yr** → use the last-good `parsed_json` (C1-preserved),
  carrying its **original** `observed_at` so vintage/recency stays honest. The aggregator
  then sees a complete source picture; an unobserved source simply looks "unchanged since
  last crawl" — identical to the normal cached case, so no aggregator changes are needed.
- **unobserved, last-good > 2 yr** → omit the source (its derived fields recompute to
  null = aged-out known-absent).

No source→field map is required; the aggregator's existing multi-source logic does the
mapping. Multi-source fields (e.g. corroboration) see a mix of fresh and carried-forward
inputs, which is exactly equivalent to "this source hasn't changed."

## 3. Field-level regression guard

Pieces 1-2 handle the *unobserved-source* class. The *recompute-gap* residue (observed
source, derived value drops for a possibly-buggy reason — the Al-Furqaan class) cannot be
auto-classified as bug-vs-genuine-drop, so:

- After aggregate, diff the candidate row against the prior row (a cheap Dolt read /
  `AS OF`).
- For any field that went **non-null → null** (or swung beyond a per-field threshold)
  **while its source was observed**, restore the prior value and emit a flag to the
  existing `reports/editorial-queue.json` (internal-only, already gitignored). Preserve +
  flag; never silently write the suspicious value.
- Scope: **observed sources only.** Aged-out drops (§2) and legitimate observed-absent
  writes are not regressions and are not touched here.

Threshold policy: exact-match "non-null → null" is unambiguous and ships first. Numeric
"large swing" thresholds are a tunable follow-up within this spec — start conservative
(e.g. relative change beyond a wide band) to avoid false flags.

## 4. Recovery (Dolt-history reconciliation)

A reconciliation script (`bin/` or a `--reconcile` mode) that, per charity, walks Dolt
history (`dolt_history_charity_data`, `AS OF`) to find fields **currently null** (or
regressed) that hold a last-known-good value in history, and **reports them for
confirm-or-restore** — same preserve+flag philosophy: a human confirms a genuine drop
versus a past corruption before restore. This:

- cleans up rows already damaged by the vectors (Al-Furqaan-class), and
- doubles as the offline detector feeding §3.

Restore is guided, not blind, and leans entirely on Dolt's existing version history — no
new storage or schema.

---

## Data flow / persistence

- `synthesize_charity` gains a prior-row read (`data_repo.get(ein)`) — directly fixing
  the audit's root cause ("never reads the prior row"). The prior row feeds both the
  carry-forward input selection (§2) and the regression diff (§3).
- `CharityDataRepository.upsert` is **unchanged**. Because synthesize now hands it a
  corrected object (valid nulls preserved as known-absent, unknowns carried forward,
  regressions restored), the full-column write is correct. Keeping the writer dumb means
  no risk of the COALESCE-vs-valid-null conflict.
- Dolt auto-commit semantics are unchanged; every run remains a versioned snapshot.

## Error handling / edge cases

- **Permanent vs transient failure:** carry-forward serves data up to 2 years even for a
  permanently-dead source. That is the accepted trade (honest timestamp + vintage flags);
  the >2yr ceiling is the backstop. True permanent-failure detection is Spec B.
- **First-ever run (no prior row):** all sources are "observed or nothing"; carry-forward
  and regression guard are no-ops (nothing to preserve). Unchanged behavior.
- **Legitimate clears** (charity genuinely stopped accepting zakat) flow naturally: the
  source is observed, the value is absent → known-absent → null is written. No special
  case needed.
- **Aggregator all-or-nothing** (`synthesize.py:1491-1493`) still catches a hard
  aggregate exception; unchanged.
- **Interaction with the strict-completeness gate:** the existing hard-fail abort
  (`orchestrator.py:782-802` + `streaming_runner.py:903-907`) stays **in place** for
  Spec A. It already protects the prior-good row on a hard failure of a required source
  (the charity never re-synthesizes). Carry-forward here is layered to cover the
  *soft-fail* path the gate misses, not to replace it. Relaxing the gate to
  "proceed-with-carry-forward instead of abort" (so other sources still refresh when one
  hard-fails) is a deliberate Spec B option, explicitly **not** taken here.

## Testing

Property tests as the spine:

- *A run where source X is unobserved never changes any source-X-derived field* (when
  last-good ≤ 2 yr).
- *An observed-absent field writes null* (valid clear is not blocked).
- *A source unobserved for > 2 yr drops its fields to null* (aged-out).
- *A recompute-gap null on an observed source preserves prior + emits a flag.*

Regression fixtures from the three confirmed real vectors: Al-Furqaan prog-ratio,
grants-derived ratios (`noncash_ratio`, `cash_adjusted_program_ratio`,
`domestic_burn_rate`), and `third_party_evaluated`.

Recovery: a fixture with a known history (good → corrupted-null) asserts reconciliation
surfaces exactly that field and restores the last-good value on confirm.

---

## Affected files (anchors for the implementation plan)

| File | Change |
|---|---|
| `src/collectors/orchestrator.py` | wire substance floor into the website store path (`_store_raw_data`, ~`:753`/`:1258`) |
| `src/collectors/form990_grants.py` | treat empty-but-success grants profile as unobserved |
| `synthesize.py` | prior-row read; per-source input selection (observed / carry-forward ≤2yr / aged-out drop); regression diff + flag |
| `src/parsers/charity_metrics_aggregator.py` | no logic change expected (receives assembled inputs); verify carried-forward profiles flow cleanly |
| `src/config` (recency constant) | single shared 2-year staleness constant |
| `reports/editorial-queue.json` writer | regression flags (reuse existing) |
| `bin/reconcile_*` (new) | Dolt-history recovery/reconciliation |
| `src/db/repository.py` | **unchanged** (documented as intentional) |

## Success criteria

- No confirmed audit vector can persist a worse-than-before value: re-running synthesize
  with a simulated soft-fail on website or grants leaves the affected fields at their
  prior values.
- A simulated genuine drop (observed source, value removed) writes null.
- A source aged > 2 yr drops to null.
- Al-Furqaan-class recompute gap preserves prior and appears in the editorial queue.
- Reconciliation restores a known-corrupted fixture row from Dolt history.
- Full pipeline test suite green.

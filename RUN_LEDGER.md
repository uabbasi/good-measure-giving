# 40-Charity End-to-End Pipeline Run — Ledger

**Started:** 2026-07-29 21:55 local (CST-0600)
**Worktree:** `.claude/worktrees/pipeline-40-charity-run` on branch `worktree-pipeline-40-charity-run`
**Base commit:** `e7f88e6` (local main HEAD, 1 ahead of origin/main `2987205`)
**Dolt snapshot before run:** `1gm59qfhe71kqu4qavn68057m8aqcfbc` ("Snapshot: before 40-charity end-to-end run (2026-07-29)")
**Dolt exclusion watermark:** `2026-07-29 20:54:32` (Dolt server tz = PDT/UTC-7; system local is -0600)

Resume protocol if the session dies: read this file top to bottom, then run
`uv run python /private/tmp/.../scratchpad/status.py batchNN.txt` to get live state
before re-running anything. Batch files are committed in `data-pipeline/`.

---

## Environment preflight (done)

- Primary checkout `~/dev/good-measure-giving` clean, on `main`. Other worktree
  (`zakat-motif-theme`) clean. No `streaming_runner`/`export`/`judge` processes running.
  → No concurrent session competing for DoltDB or `website/data`.
- Dolt sql-server running (pid 3398). Only `phase_cache` was dirty pre-run (1 row
  added / 1 deleted); folded into the snapshot commit above.
- `uv sync` done in worktree (separate .venv).

## Key facts established before spending anything

1. **Cache is fully cold.** `--cache-status` shows every phase `RUN` for all 40,
   reason `Code changed (d9e55491→bdec1581)` / `(8265e620→bdec1581)` on `crawl`,
   which cascades to all downstream phases. So batch05 gets **zero** cache benefit
   and pays full price. Corollary: **any pipeline code fix I make re-invalidates the
   cache**, so fixes must be weighed against re-paying for the phases they touch.
2. **`export_exclusions` is append-only** (`ExportExclusionRepository` docstring:
   "Audit trail … one row per gate event", PK `(charity_ein, excluded_at)`). It had
   **29 pre-existing rows**, including 5 of my 40 (see below). It therefore will
   never be literally "empty" for those EINs unless I delete audit rows, which I
   will not do. **Evidence #2 will be reported as: no new exclusion events for any
   of the 40 after the watermark above.** Flagging this as a definitional
   deviation from the literal ask, not a workaround.
3. **File mtime is a useless freshness signal here.** `git worktree add` just
   checked out all 166 `website/data/charities/charity-*.json`, so every mtime reads
   as minutes old. Freshness is instead read from the JSON's embedded
   `lastUpdated` field, plus narrative-text comparison for the spot-checks.
4. Export filename convention is `charity-{EIN}.json` (not `{EIN}.json`).
5. All 40 currently have `judge_error_count = 0` and a non-null `judge_content_hash`,
   but the gate also requires the hash to **match a recomputation over current
   content** — and content is about to change, so these hashes will go stale and
   must be refreshed by a re-judge.

### Pre-existing exclusion rows among the 40 (historical, before this run)

| # | EIN | Name | Pre-existing reason | When |
|---|-----|------|--------------------|------|
| 1 | 20-2714426 | UNRWA | judge errors: 11 | 2026-07-26 22:49 |
| 7 | 27-3175543 | United Muslim Relief | judge errors: 1 | 2026-07-23 15:30 |
| 11 | 88-2980325 | Friends of KDSP | judge errors: 2 | 2026-07-26 22:52 |
| 23 | 20-8540050 | Islamic Scholarship Fund | judge errors: 7 | 2026-07-26 22:47 |
| 34 | 92-3079413 | Humaniti | judge errors: 4 | 2026-07-26 22:44 |

These 5 are the judge-gate risk list. UNRWA (11 errors) is both the worst offender
and a mega org, so it is the single most likely charity to block batch05.

## Batch construction (done, validated)

Built by script (not by hand) from `pilot_charities.txt`, copying each full
pipe-delimited line verbatim in the user's specified order. Validation enforced:
each EIN found **exactly once**, **not** in the `HARD DATA CHARITIES` section,
**not** `HIDE:TRUE`, and the source line's name matches the expected name.
All 40 passed. Loader `load_charity_entries()` parses 5/10/25/40 respectively.

Section spread of the 40: 12 international relief/development, 13 mosques/Islamic
centers, 5 advocacy/civil rights, 5 education/scholarship, 3 health/wellness,
2 active-testing.

---

## Per-batch log

### batch05 — #1-5 (UNRWA, Rahima, Noor Project, Amoud, American Imam Academy)

- **Cost estimate before running:** cache fully cold, so full price. Prior Dolt
  commit recorded a run at `$1.89 / 34 attempted ($0.0555/charity)` but that run had
  21 failures, and failures cost far less than successes — so that number is a floor,
  not a per-success estimate. Estimating ~$0.25-0.35 per normal charity for all 8
  phases including rich narratives, and ~2-3x for UNRWA (mega, $51M filer):
  **~$2.00 expected, ~$2.50 worst case.**
- **Budget set:** `--budget 6.0`. Headroom over the $2.50 worst case because the
  per-charity cost is genuinely unknown on a cold cache, and a budget-truncated run
  wastes the spend already made while looking like a data failure. `--checkpoint 2`.
- **Status:** IN PROGRESS

| # | EIN | Name | Result | Notes |
|---|-----|------|--------|-------|
| 1 | 20-2714426 | UNRWA | pending | |
| 2 | 77-0442850 | Rahima Foundation | pending | |
| 3 | 45-5637293 | The Noor Project | pending | |
| 4 | 75-2882187 | Amoud Foundation | pending | |
| 5 | 82-1150290 | American Imam Academy | pending | |

---

## Cumulative LLM spend

| Batch | Run | Reported cost | Ended because |
|-------|-----|---------------|---------------|
| batch05 | 1 | pending | pending |

## Failures, root causes, fixes, commits

(none yet)

## Pipeline code changes made during this run

(none yet)

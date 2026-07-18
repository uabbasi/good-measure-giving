# Pipeline Orchestration

`streaming_runner.py` is the orchestrator: 8 phases per charity, a thread pool
across charities, per-phase caching, checkpoint commits, run tags, and a
judge-gated export.

## Phase Flow

```
crawl → extract → discover → synthesize → baseline → rich → judge → export
```

Per charity the phases run in order; charities run in parallel
(`--workers`, default 20).

| Phase | Standalone script | Reads | Writes |
|-------|-------------------|-------|--------|
| crawl | `crawl.py` | sources (CN, ProPublica, Candid, CauseIQ, website) | `raw_scraped_data`, `charities` |
| extract | `extract.py` | `raw_scraped_data.raw_content` | `raw_scraped_data.parsed_json` |
| discover | — (streaming only) | web via discovery agents | `raw_scraped_data` (source=`discovered`), `agent_discoveries` |
| synthesize | `synthesize.py` | `raw_scraped_data`, `agent_discoveries` | `charity_data`, `citations` |
| baseline | `baseline.py` | `charity_data` | `evaluations` (scores + baseline narrative) |
| rich | `rich_phase.py`, `rich_strategic_phase.py` | `charity_data`, `evaluations` | `evaluations` (rich narratives), `citations` |
| judge | `judge_phase.py` | `evaluations` | `evaluations.judge_score`, `judge_verdicts` |
| export | `export.py` | `evaluations`, `charity_data`, `citations` | `website/data/*.json`, `export_exclusions` |

## Crawl politeness & frozen sources

- Per-domain fetch concurrency is capped at 2, `robots.txt` is respected, and
  a source that hits a CAPTCHA or comes back not-found gets a 180-day
  terminal backoff before it's retried again.
- BBB is frozen by default (`FROZEN_SOURCES` in `src/collectors/orchestrator.py`,
  H12). Re-enable it per run with `crawl.py --sources bbb`; `streaming_runner.py`
  has no equivalent opt-in flag, so streaming runs never fetch BBB.

## Caching (`phase_cache`)

- Key `(charity_ein, phase)`; value `code_fingerprint` (hash of the phase's
  code), `ran_at`, `cost_usd`.
- A phase is skipped when the fingerprint matches and the TTL has not expired.
- **Not a state machine.** No transitions, no approval workflow. The old
  WorkflowState enum (COLLECTED/DERIVED/RECONCILED/…) no longer exists.
- Controls: `--force-phase X` (repeatable), `--force-all`, `--cache-status`,
  `--clean` (delete existing data first).

## Commits & tags

- Standalone phase scripts commit at end of run with an explicit table list
  (`dolt.commit(msg, tables=tables_for_phases("<phase>"))`).
- `streaming_runner.py`: `--checkpoint N` commits every N completed charities;
  a final commit captures the remainder; the run is tagged `run-<timestamp>`
  (custom name `--tag`, skip with `--no-tag`).
- Export stamps `source_commit` from `HASHOF(active_branch())` only when
  `dolt_status` is clean; a dirty working set stamps NULL with a warning.

## Judge gate & export

- The judge phase persists `judge_score` (internal metric only), the deduped
  `judge_error_count`/`judge_warning_count`, and `judge_content_hash` into
  `evaluations`.
- Export excludes charities with judge errors > 0 or a stale/missing
  `judge_content_hash` (NULL counts fail closed; `--no-judge-gate` is the
  escape hatch). Warnings never gate — they feed
  `data-pipeline/reports/editorial-queue.json`. Exclusions are written to the
  `export_exclusions` table (ein, judge_score, reason, excluded_at).
- Pruning stale exported charities runs ONLY with an explicit `--prune`,
  and never when `--ein` was passed.
- The comprehensive index rebuild is skipped entirely when zero charities
  succeeded in the run.

## Cost controls

- `--budget USD`: pre-call hard stop inside `LLMClient.generate()`
  (`BudgetExceededError`, `src/llm/budget_tracker.py`). `streaming_runner.py`
  defaults `--budget` to $10.0 for the whole run; pass `--budget 0` to run
  uncapped, or a smaller/larger value to override.
- Per-phase cost accumulates in `phase_cache.cost_usd`; the run summary
  prints totals and per-charity averages.

## Error handling (reality, not aspiration)

- Collector failures are isolated per source; a failed crawl records
  `last_failure_reason` on `raw_scraped_data` without clobbering the
  last-good `parsed_json`.
- Phase scripts are print-based today (see the status header in
  `LOGGING_STANDARDS.md`); exit codes reflect failures — `judge_phase.py`
  exits non-zero when judging fails.
- LLM fallback chains are defined per task in `llm_client.py` `TASK_MODELS`.

## Pilot charities

`pilot_charities.txt` is the source of truth (167 charities):

```
# Format: Name | EIN | URL | Comments
Islamic Relief USA | 95-4453134 | https://irusa.org | 100% CN rating, flagship
```

`#` lines are ignored; `HIDE:TRUE` in comments excludes from the curated list.
All scripts take `--charities pilot_charities.txt` or a single `--ein`.

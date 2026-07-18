---
name: data-pipeline
description: Run the charity evaluation pipeline - DoltDB storage, 8-phase streaming runner, repository pattern, judge-gated export. Use when working on collectors, scrapers, pipeline code, database queries, or debugging data flow.
---

# Data Pipeline

8-phase charity evaluation pipeline. All data lives in **DoltDB** (MySQL-compatible,
git-like version control at `~/.amal-metric-data/dolt/zakaat`). Canonical runner:
`data-pipeline/streaming_runner.py`.

**Philosophy**: Capture broadly, filter later. Correctness > cost, but we can have both.

---

## Quick Reference (8 phases)

| # | Phase | Entry Point | What It Does | Writes |
|---|-------|-------------|--------------|--------|
| 1 | Crawl | `crawl.py` | FETCH raw data from sources (no parsing) | `raw_scraped_data`, `charities` |
| 2 | Extract | `extract.py` | PARSE raw_html into validated schemas | `raw_scraped_data.parsed_json` |
| 3 | Discover | `streaming_runner.py` only | Agent discovery: awards, evidence, outcomes, theory-of-change (`src/services/*discovery*`) | `raw_scraped_data` (source=`discovered`), `agent_discoveries` |
| 4 | Synthesize | `synthesize.py` | Aggregate sources + derive fields | `charity_data`, `citations` |
| 5 | Baseline | `baseline.py` | GMG scores (rubric v5.2.0, `src/scorers/v2_scorers.py`) + baseline narratives | `evaluations` |
| 6 | Rich | `rich_phase.py`, `rich_strategic_phase.py` | Rich + strategic narratives | `evaluations`, `citations` |
| 7 | Judge | `judge_phase.py` | LLM judges validate narratives → `judge_score` | `evaluations`, `judge_verdicts` |
| 8 | Export | `export.py` | JSON to `website/data/`, judge-gated | `export_exclusions` + JSON files |

Crawl politeness: per-domain concurrency capped at 2, robots.txt respected, and
a source that hits CAPTCHA or comes back not-found gets a 180-day terminal
backoff before it's retried. BBB is a frozen source by default (H12):
`crawl.py --sources bbb` is the only opt-in; `streaming_runner.py` has no
equivalent flag, so streaming runs never fetch BBB.

---

## Running the Pipeline

```bash
# Canonical: streaming runner (all phases per charity, parallel, cached)
uv run python streaming_runner.py --ein 95-4453134
uv run python streaming_runner.py --charities pilot_charities.txt --workers 10

# Useful flags
#   --force-phase baseline   re-run one phase despite cache (repeatable)
#   --force-all              ignore cache entirely
#   --checkpoint 10          Dolt commit every 10 charities
#   --budget 5.0             hard cap on LLM spend, USD (default: 10.0; 0 = uncapped)
#   --no-judge-gate          escape hatch: export despite judge errors / stale hash
#   --skip-export            stop before export
#   --dry-run / --cache-status

# Standalone phase scripts accept --ein / --charities
uv run python baseline.py --charities pilot_charities.txt --workers 10
```

Test incrementally: 1 → 5 → 10 → all. Always source EINs from `pilot_charities.txt`
(format: `Name | EIN | URL | Comments`, 167 charities).

---

## State: phase_cache is a cache, NOT a state machine

There is no workflow state machine (the old COLLECTED→…→APPROVED enum is gone).
`phase_cache` stores `(charity_ein, phase, code_fingerprint, ran_at, cost_usd)`;
a phase re-runs when its code fingerprint changes or the TTL expires. Control it
with `--force-phase` / `--force-all`, or delete rows via `PhaseCacheRepository`.
Export gating is by `evaluations.judge_score`, not state transitions.

---

## Data Access: repository pattern

All DB access goes through `src/db/repository.py` (pymysql → DoltDB, no ORM):

```python
from src.db.repository import EvaluationRepository

repo = EvaluationRepository()
evaluation = repo.get_by_ein("95-4453134")
```

Repositories: `CharityRepository`, `RawDataRepository`, `CharityDataRepository`,
`EvaluationRepository`, `AgentDiscoveryRepository`, `CitationRepository`,
`JudgeVerdictRepository`, `PhaseCacheRepository`, `ExportExclusionRepository`.

Version control lives in `src/db/dolt_client.py`:

```python
from src.db.dolt_client import dolt, tables_for_phases

dolt.commit("Baseline: 10 charities", tables=tables_for_phases("baseline"))
dolt.log(5)
dolt.diff("HEAD~1", "HEAD", "evaluations")
```

Every phase auto-commits with an explicit table list; streaming runs get a
`run-<timestamp>` Dolt tag.

---

## Export is gated

- `judge_score >= threshold` (default 80) required to export; exclusions are
  recorded in the `export_exclusions` table (`--no-judge-gate` bypasses).
- Pruning previously-exported charities requires an explicit `--prune`;
  it never runs with `--ein`.
- The GMG Score is `amal_score` — NOT `overallScore` (that is Charity
  Navigator's rating; ranking by it has caused real bugs).

---

## Deep Dives

- [orchestration.md](orchestration.md) — phase-by-phase detail, caching, commits/tags
- [extraction.md](extraction.md) — sources, patterns, red flags
- [versioning.md](versioning.md) — hashing, TTLs, skip logic

---

## Anti-Patterns

**Don't:**
- Run all charities first (test 1 → 5 → 10 → all)
- Hardcode EINs (use `pilot_charities.txt`)
- Fabricate missing data (missing stays NULL)
- Trust LLM-extracted hallucination-prone fields (see `src/validators/hallucination_denylist.py`)
- Rank or display "GMG Score" from `overallScore`

**Do:**
- Use the repository pattern for all database access
- Track source for every datum (citations)
- Check `--cache-status` before expensive re-runs
- Commit with explicit phase tables (`tables_for_phases`)

---

## Related Skills

- **llm-prompting**: prompt patterns, schema enforcement
- **form990-expert**: 990 parsing, financial analysis
- **zakat-fiqh**: zakat classification, wallet tags

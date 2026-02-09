---
name: data-pipeline
description: Run the charity evaluation pipeline - extraction, 4-stage V2 workflow, Supabase patterns, versioning. Use when working on collectors, scrapers, pipeline code, database queries, or debugging data flow.
---

# Data Pipeline

4-stage V2 charity evaluation pipeline with 100-point scoring.

**Philosophy**: Capture broadly, filter later. Correctness > cost, but we can have both.

---

## Quick Reference (V2 Pipeline)

| Stage | Entry Point | What It Does |
|-------|-------------|--------------|
| 1. Crawl | `crawl.py` | Collect data from 5 sources |
| 2. Process Data | `process_data.py` | Derive fields + reconcile sources |
| 3. Process Baseline | `process_baseline.py` | Generate baseline narratives + export + verify |
| 4. Process Rich | `process_rich.py` | Generate rich narratives + export + verify |

**Wrapper**: `./run_v2.sh` runs all 4 stages

---

## Decision Tree

**Working on data collection?**
→ See [extraction.md](extraction.md) for sources, patterns, red flags

**Working on pipeline phases or state machine?**
→ See [orchestration.md](orchestration.md) for workflow, CLI, transitions

**Working with database or debugging queries?**
→ See `data-pipeline/src/db/` for Supabase repositories

**Implementing freshness checks or versioning?**
→ See [versioning.md](versioning.md) for hashing, TTLs, skip logic

---

## State Machine

```
NOT_STARTED → COLLECTED → DERIVED → RECONCILED
    → BASELINE_QUEUED → BASELINE_REVIEW
    → RICH_QUEUED → RICH_REVIEW
    → APPROVED (terminal) or REJECTED (terminal)
```

Terminal states require `force=True` to transition.

---

## Key Files

```
data-pipeline/
├── run_v2.sh                    # Wrapper: all 4 stages
├── crawl.py                     # Stage 1: Collect data
├── process_data.py              # Stage 2: Derive + reconcile
├── process_baseline.py          # Stage 3: Baseline narratives
├── process_rich.py              # Stage 4: Rich narratives
├── src/
│   ├── collectors/              # 5 data sources
│   ├── evaluators/              # NarrativeEvaluator, Judge
│   ├── scorers/                 # V2 scoring (100-point scale)
│   ├── quality_judges/          # LLM-as-judge scorers
│   ├── database/                # Schema, WriteQueue, repository
│   └── cli/wizard.py            # Interactive menu (uv run z)
└── pilot_charities.txt          # Source of truth for EINs
```

---

## CLI Commands

```bash
# Full V2 pipeline
./run_v2.sh --charities pilot_charities.txt --workers 10

# Individual stages
uv run python crawl.py --charities pilot_charities.txt --workers 10
uv run python process_data.py --charities pilot_charities.txt
uv run python process_baseline.py --charities pilot_charities.txt --workers 5
uv run python process_rich.py --charities rich_charities.txt --workers 3

# Interactive wizard
uv run z

# Status
zakaat status --ein 95-4453134
```

---

## Critical Patterns

### Supabase Repositories

Data access via repository pattern in `src/db/`:

```python
from src.db import get_client
from src.db.charity_repository import CharityRepository

client = get_client()
repo = CharityRepository(client)
charity = repo.get_by_ein("95-4453134")
```

### Pilot Charities

All operations scope to `pilot_charities.txt`:

```python
from src.cli.wizard import get_pilot_eins
eins = get_pilot_eins()
```

---

## Anti-Patterns

**Don't:**
- Skip phases (must go in order)
- Hardcode EINs (use `pilot_charities.txt`)
- Fabricate missing data

**Do:**
- Use repository pattern for database access
- Track source for every datum
- Check freshness before expensive operations

---

## Related Skills

- **llm-prompting**: Prompt patterns, schema enforcement
- **form990-expert**: 990 parsing, financial analysis
- **zakat-fiqh**: Zakat classification, wallet tags

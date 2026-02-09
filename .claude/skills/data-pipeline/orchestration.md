# Pipeline Orchestration

4-stage V2 pipeline with 100-point scoring.

---

## V2 Pipeline Overview

```
Stage 1: CRAWL           → Raw data from 5 sources
Stage 2: PROCESS DATA    → Derive fields + reconcile sources
Stage 3: PROCESS BASELINE → Generate narratives + export + verify
Stage 4: PROCESS RICH    → Generate rich narratives + export + verify
```

### Entry Points

| Stage | Script | Internal Steps |
|-------|--------|----------------|
| 1 | `crawl.py` | Collect from CN, ProPublica, Candid, CauseIQ, Website |
| 2 | `process_data.py` | derive_data.py → reconcile_data.py |
| 3 | `process_baseline.py` | narrative → export → verify |
| 4 | `process_rich.py` | narrative → export → verify |

**Wrapper**: `./run_v2.sh` runs all stages

---

## State Machine

```python
class WorkflowState(Enum):
    NOT_STARTED = "not_started"
    COLLECTED = "collected"
    DERIVED = "derived"
    RECONCILED = "reconciled"
    BASELINE_QUEUED = "baseline_queued"
    BASELINE_REVIEW = "baseline_review"
    RICH_QUEUED = "rich_queued"
    RICH_REVIEW = "rich_review"
    APPROVED = "approved"      # Terminal
    REJECTED = "rejected"      # Terminal
```

### Valid Transitions

```python
VALID_TRANSITIONS = {
    NOT_STARTED: [COLLECTED],
    COLLECTED: [DERIVED],
    DERIVED: [RECONCILED],
    RECONCILED: [BASELINE_QUEUED],
    BASELINE_QUEUED: [BASELINE_REVIEW, REJECTED],
    BASELINE_REVIEW: [RICH_QUEUED, APPROVED, REJECTED],
    RICH_QUEUED: [RICH_REVIEW, REJECTED],
    RICH_REVIEW: [APPROVED, REJECTED],
    APPROVED: [],   # Terminal - requires force=True
    REJECTED: [],   # Terminal - requires force=True
}
```

---

## Stage Details

### Stage 1: Crawl

**Entry**: `crawl.py`

5 sources run in parallel via `DataCollectionOrchestrator`:
- Failures are isolated (one source failing doesn't crash pipeline)
- 180-day cache TTL
- Output: `raw_scraped_data` table

### Stage 2: Process Data

**Entry**: `process_data.py`

Runs two internal phases:
1. **Derive** - Deterministic computations (no LLM):
   - `is_muslim_charity`: Keyword matching + country detection
   - `transparency_score`: From Candid seal
   - Financial ratios
2. **Reconcile** - Multi-source merging:
   - Deduplication
   - Source prioritization (ProPublica for financials)
   - Outputs canonical fields

**After Stage 2**: All structural data complete.

### Stage 3: Process Baseline

**Entry**: `process_baseline.py`

Three internal steps:
1. **Narrative** - Generate baseline narratives via LLM
2. **Export** - Write charity JSON to website/data/
3. **Verify** - Validate exported data

**Core**: `src/evaluators/narrative_evaluator.py`

### Stage 4: Process Rich

**Entry**: `process_rich.py`

Same structure as Stage 3, but for rich narratives (500-800 words).
Uses `rich_charities.txt` by default.

---

## CLI Commands

### V2 Pipeline

```bash
# Full pipeline
./run_v2.sh --charities pilot_charities.txt --workers 10
./run_v2.sh --skip-rich  # Skip Stage 4

# Individual stages
uv run python crawl.py --charities pilot_charities.txt --workers 10
uv run python process_data.py --charities pilot_charities.txt --workers 10
uv run python process_baseline.py --charities pilot_charities.txt --workers 5
uv run python process_rich.py --charities rich_charities.txt --workers 3

# Stage options
uv run python process_baseline.py --skip-narrative  # Export only
uv run python process_baseline.py --skip-export     # Narrative only
uv run python process_baseline.py --skip-verify     # Skip verification
```

### Interactive Wizard

```bash
uv run z
```

Menu-driven interface showing:
- Real-time phase statistics
- Scoped to `pilot_charities.txt`
- Single-charity lookup

### Status

```bash
zakaat status                    # Pipeline overview
zakaat status --ein 95-4453134   # Single charity
```

---

## Quality Gates

| Check | Threshold | Action on Fail |
|-------|-----------|----------------|
| Information density | < 0.80 | Human review |
| Judge score | < 60 | Auto-reject |
| Judge score | ≥ 85 | Auto-approve |
| Sub-score sum | Mismatch | Retry |
| Schema validation | Invalid | Retry |

---

## Error Handling

### Collector Errors
- Per-source isolation
- Graceful degradation
- Retry with backoff

### Narrative Generation

```python
MAX_GENERATION_RETRIES = 3

for attempt in range(MAX_GENERATION_RETRIES):
    try:
        narrative = generate_narrative(charity)
        if validate(narrative):
            return narrative
    except (JSONDecodeError, ValidationError):
        continue

transition_to_rejected(ein, reason="Generation failed after 3 attempts")
```

---

## Pilot Charities

### Source of Truth: `pilot_charities.txt`

```
# Comment lines start with #
95-4453134  # Islamic Relief USA
36-4398970  # Zakat Foundation
```

### Loading

```python
from src.cli.wizard import get_pilot_eins
eins = get_pilot_eins()  # Returns List[str]
```

All CLI and wizard operations scope to pilot charities by default.

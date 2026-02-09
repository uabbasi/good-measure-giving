# Pipeline Versioning & Freshness

Smart short-circuiting: correctness > cost, but we can have both.

---

## Problem Statement

**Current**: `--force` everywhere to ensure freshness
**Result**: Expensive, slow, unnecessary API calls

**Goal**: Skip unchanged work while guaranteeing correctness

---

## What to Version

| Component | Version ID | Triggers Regen When Changed |
|-----------|------------|----------------------------|
| Prompts | Semantic version + content hash | Yes |
| Schemas | Schema hash | Yes |
| Source data | scrape_timestamp + content hash | Yes |
| LLM model | Model version string | Yes |
| Pipeline code | Git commit hash | Optional |

---

## Version Tracking Schema

```sql
ALTER TABLE charity_pipeline ADD COLUMN IF NOT EXISTS (
    prompt_version VARCHAR,       -- "3.0.0"
    prompt_hash VARCHAR,          -- SHA256 truncated
    model_version VARCHAR,        -- "gemini-2.0-flash"
    schema_version VARCHAR,       -- "baseline_v2"
    source_data_hash VARCHAR,     -- Hash of inputs
    pipeline_commit VARCHAR       -- Git commit
);
```

---

## Freshness Logic by Phase

### Phase 1: Collect (TTL-based)

```python
def should_collect(ein: str, source: str) -> bool:
    last_scrape = get_last_scrape(ein, source)
    if not last_scrape:
        return True

    ttls = {
        "charity_navigator": 30,   # days
        "propublica": 90,          # 990s change annually
        "candid": 60,
        "causeiq": 60,
        "website": 14,             # Websites change often
    }

    age_days = (now() - last_scrape.timestamp).days
    return age_days > ttls[source]
```

### Phases 2-3: Derive/Reconcile (Hash-based)

```python
def should_derive(ein: str) -> bool:
    current_hash = compute_input_hash(
        raw_scraped_data[ein],
        derive_logic_version
    )
    stored_hash = get_stored_hash(ein, "derive")
    return current_hash != stored_hash
```

### Phases 4-7: Narratives (Multi-input hash)

```python
def should_regenerate_narrative(ein: str) -> bool:
    record = get_pipeline_record(ein)

    if not record.baseline_json:
        return True  # No existing narrative

    current_hash = compute_input_hash(
        reconciled_data[ein],
        load_prompt("baseline_narrative").content_hash,
        current_model_version,
        schema_version
    )

    return current_hash != record.source_data_hash
```

---

## Hash Computation

```python
import hashlib
import json

def compute_input_hash(*inputs) -> str:
    hasher = hashlib.sha256()

    for inp in inputs:
        if isinstance(inp, dict):
            serialized = json.dumps(inp, sort_keys=True)
        else:
            serialized = str(inp)
        hasher.update(serialized.encode())

    return hasher.hexdigest()[:16]
```

### Include in Hash
- Source URLs
- Raw data content
- Prompt content
- Model version
- Schema version

### Exclude from Hash
- Timestamps
- Non-deterministic fields
- Debug/logging data

---

## Correctness Guarantees

### Principle: When in Doubt, Regenerate

```python
def should_skip(ein: str, phase: str) -> tuple[bool, str]:
    try:
        is_fresh = check_freshness(ein, phase)
        return is_fresh, "inputs unchanged" if is_fresh else "inputs changed"
    except Exception as e:
        # On error, don't skip - regenerate to be safe
        return False, f"freshness check failed: {e}"
```

### Validate After Skip

```python
if should_skip:
    record = get_record(ein)
    try:
        BaselineNarrative.model_validate_json(record.baseline_json)
        return ProcessResult.SKIPPED
    except ValidationError:
        # Stored data invalid, regenerate
        pass
```

---

## Logging Skip Decisions

```python
def process_charity(ein: str):
    if not should_collect(ein, "website"):
        log.info(f"SKIP collect/website {ein}: fresh (age={age}d, ttl={ttl}d)")
        return ProcessResult.SKIPPED
```

Audit trail in `narrative_state_log`:
```python
{
    "ein": "95-4453134",
    "phase": "narrative",
    "decision": "SKIP",
    "reason": "inputs unchanged",
    "input_hash": "abc123",
    "stored_hash": "abc123"
}
```

---

## CLI Force Flags

```bash
# Normal run - uses freshness logic
zakaat run --charities pilot_charities.txt

# Force specific phase
zakaat run --force-collect
zakaat run --force-narratives
zakaat run --force-all

# Force specific charity
zakaat run --ein 95-4453134 --force
```

---

## Cost Optimization

### 1. TTL-Based Collection
Different sources have different change frequencies - don't re-crawl ProPublica (annual 990s) as often as websites.

### 2. Batch by Staleness
```python
charities_by_staleness = sorted(
    pilot_eins,
    key=lambda ein: get_staleness_score(ein),
    reverse=True
)
```

### 3. Fail Fast
Check freshness before expensive operations:
```python
stale = [ein for ein in eins if not is_fresh(ein)]
log.info(f"Processing {len(stale)}/{len(eins)} stale charities")
```

---

## Migration Path

1. Add hash columns to `charity_pipeline`
2. Backfill hashes for existing records
3. Implement freshness checks (default regenerate if no hash)
4. Add skip logging
5. Monitor skip rate, validate correctness
6. Tune TTLs based on actual change frequency
7. Remove `--force` from regular workflows

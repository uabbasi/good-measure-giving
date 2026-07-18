# Data Pipeline

Charity evaluation pipeline with 2 scored dimensions + data confidence signal. Uses **DoltDB** for version-controlled data storage.

## Pipeline Phases

Canonical runner — all 8 phases per charity, parallel, cached:

```bash
uv run python streaming_runner.py --ein 95-4453134
uv run python streaming_runner.py --charities pilot_charities.txt --workers 10
# --force-phase baseline   selectively re-run a phase (repeatable)
# --checkpoint 10          Dolt commit every 10 charities
# --budget 5.0             hard cap on LLM spend, USD (default: 10.0; 0 = uncapped)
# --no-judge-gate          escape hatch: publish regardless of judge errors / hash freshness
```

Phases: **crawl → extract → discover → synthesize → baseline → rich → judge → export**

Standalone phase scripts (same phases, one at a time; all take `--ein` / `--charities`):

```bash
uv run python crawl.py --ein 95-4453134          # 1 FETCH raw data (no parsing)
uv run python extract.py --ein 95-4453134        # 2 PARSE raw_html into schemas
# 3 discover: streaming_runner only (agent discovery services)
uv run python synthesize.py --ein 95-4453134     # 4 Aggregate + derive fields
uv run python baseline.py --ein 95-4453134       # 5 GMG scores + narratives
uv run python rich_phase.py --ein 95-4453134     # 6 Rich narratives (+ rich_strategic_phase.py)
uv run python judge_phase.py --ein 95-4453134    # 7 LLM-judge validation
uv run python export.py                          # 8 Export to website/data/
```

Export applies the publication gate (Option A): a charity ships only if its
deduped `judge_error_count == 0` **and** `evaluations.judge_content_hash` matches
a recomputation over current content. Stale/missing hashes and missing counts
fail closed until the charity is re-judged; excluded charities are recorded in
the `export_exclusions` table. Warnings **never** gate publication — they feed
`reports/editorial-queue.json` (a ranked editorial work list, internal-only and
gitignored, never under `website/data`). `judge_score` stays computed and
persisted as an internal metric only. `--no-judge-gate` bypasses the gate.
(The `--judge-threshold` flag was removed; the 0=disable semantics went with it.)
In the "3 gates" spirit: deterministic integrity judges + truth/consistency
judges gate publication via errors; the craft judge (`narrative_quality`) never
gates — its warnings only inform the editorial queue. (Splitting these into 3
physical gate modules is deferred to v5.3.0.) Pruning previously-exported
charities never happens implicitly: it requires an explicit `--prune`, and never
runs with `--ein`.

BBB is a frozen source by default (H12): `crawl.py --sources bbb` is the only
opt-in; `streaming_runner.py` has no equivalent flag, so streaming runs never
fetch BBB.

## DoltDB (Version-Controlled Database)

DoltDB is MySQL-compatible with Git-like versioning. Every change is tracked.

### Key Concept: Commits = Snapshots

- **SQL writes happen immediately** (autocommit)
- **Dolt commits create version snapshots** (like `git commit`)
- **Pipeline auto-commits** after each phase

### Starting the Database

```bash
cd ~/.amal-metric-data/dolt/zakaat
dolt sql-server  # Runs on localhost:3306
```

### Viewing History

```bash
cd ~/.amal-metric-data/dolt/zakaat

# Commit history (like git log)
dolt log --oneline

# What changed in last commit
dolt diff HEAD~1 HEAD

# Changes to specific table
dolt diff HEAD~1 HEAD evaluations

# Uncommitted changes (like git status)
dolt status
```

### Creating Manual Snapshots

```bash
# Snapshot current state
dolt add -A
dolt commit -m "Snapshot: before experimental scoring changes"
```

Or in Python:
```python
from src.db.dolt_client import dolt
dolt.commit("Snapshot: before experimental scoring changes")
```

### Branching for Experiments

```bash
# Create and switch to experiment branch
dolt branch experiment-new-scoring
dolt checkout experiment-new-scoring

# Run pipeline with experimental changes...
uv run python baseline.py --charities pilot_charities.txt

# If it works - merge back to main
dolt checkout main
dolt merge experiment-new-scoring

# If it fails - just delete the branch
dolt branch -D experiment-new-scoring
```

### Time Travel Queries

```sql
-- Data as it was 3 commits ago
SELECT * FROM charities AS OF 'HEAD~3' WHERE ein = '12-3456789';

-- Compare scores before/after a run
SELECT 'before' as v, amal_score FROM evaluations AS OF 'HEAD~1' WHERE charity_ein = '12-3456789'
UNION ALL
SELECT 'after', amal_score FROM evaluations WHERE charity_ein = '12-3456789';

-- Full history of a single row
SELECT * FROM dolt_history_evaluations WHERE charity_ein = '12-3456789';
```

### Rollback

```bash
# Undo changes to a specific table (keeps other tables)
dolt checkout HEAD~1 -- evaluations

# Full rollback (nuclear option)
dolt checkout HEAD~1
```

### Python API

```python
from src.db.dolt_client import dolt

# Commit changes
dolt.commit("Description of what changed")

# View history
for c in dolt.log(5):
    print(f"{c.hash[:8]} - {c.message}")

# Check current branch
print(dolt.current_branch())  # 'main'

# Branching
dolt.create_branch("experiment")
dolt.checkout("experiment")
# ... make changes ...
dolt.commit("Experimental changes")
dolt.checkout("main")
dolt.merge("experiment")
```

### What Happens Automatically

| Action | Version Control |
|--------|-----------------|
| Run `crawl.py` | Auto-commits: "Crawl: X charities fetched" |
| Run `synthesize.py` | Auto-commits: "Synthesize: X charities processed" |
| Run `baseline.py` | Auto-commits: "Baseline: X charities scored" |
| Manual data fix | You should commit with descriptive message |

### Environment Variables

```bash
DOLT_HOST=127.0.0.1      # Default
DOLT_PORT=3306           # Default
DOLT_DATABASE=zakaat     # Default
DOLT_USER=root           # Default
DOLT_PASSWORD=           # Default (empty)
```

## Data Access

Repositories in `src/db/`:
- `CharityRepository` - Charity records
- `RawDataRepository` - Raw scraped data from sources
- `CharityDataRepository` - Synthesized charity data
- `EvaluationRepository` - AMAL scores and narratives
- `dolt` - Version control (commit, log, diff, branch, merge)

## Development Workflow

Test incrementally: 1 → 5 → 10 → all. Always use `pilot_charities.txt`.

```bash
# 1. Run on 1 charity
uv run python crawl.py --ein 95-4453134      # Fetch raw data
uv run python extract.py --ein 95-4453134    # Parse into schemas
uv run python synthesize.py --ein 95-4453134 # Aggregate
uv run python baseline.py --ein 95-4453134   # Score + narrative

# 2. Expand to all pilot charities
uv run python crawl.py --charities pilot_charities.txt
uv run python extract.py --charities pilot_charities.txt
uv run python synthesize.py --charities pilot_charities.txt
uv run python baseline.py --charities pilot_charities.txt --workers 10
```

## Testing

```bash
uv run pytest                           # All tests
uv run pytest tests/test_v2_scorers.py  # Scorer tests
ruff check . --fix                      # Lint
```

## Key Files

```
pilot_charities.txt           # Source of truth for EINs (167 charities, organized by category)
streaming_runner.py           # Canonical runner: all 8 phases, cached, parallel
crawl.py                      # Phase 1: FETCH raw data (no parsing)
extract.py                    # Phase 2: PARSE raw_html → parsed_json
synthesize.py                 # Phase 4: Aggregate + derive (phase 3 discover = streaming_runner only)
baseline.py                   # Phase 5: GMG scores + narratives
rich_phase.py                 # Phase 6: Rich narratives (+ rich_strategic_phase.py)
judge_phase.py                # Phase 7: LLM-judge validation
export.py                     # Phase 8: Export to website (judge-gated)
src/db/repository.py          # Repository pattern (Charity/RawData/CharityData/Evaluation/…)
src/db/dolt_client.py         # Git-like operations (commit, branch, diff, tables_for_phases)
src/collectors/               # ProPublica, CN, Candid, Web (fetch + parse methods)
src/scorers/v2_scorers.py     # Impact, Alignment, Risk, DataConfidence (rubric v5.2.0)
src/parsers/charity_metrics_aggregator.py  # Data aggregation
```

## Scoring Dimensions (GMG Score, rubric v5.2.0, 100 pts total)

1. **Impact** (50 pts): Weights vary by archetype (DIRECT_SERVICE, SYSTEMIC_CHANGE, EDUCATION, COMMUNITY, MULTIPLIER). See `config/rubric_archetypes.yaml`.
2. **Alignment** (50 pts): Muslim donor fit(19) + cause urgency(13) + underserved space(7) + track record(6) + funding gap(5)
3. **Risk** (-10 pts max): Deductions for red flags (low program spending, small board, low reserves, etc.)
4. **Data Confidence** (0.0-1.0, outside score): verification(0.50) + transparency(0.35) + data quality(0.15)

### Rubric Versioning

Rubric versions use semver: major=structural break, minor=reweight, patch=bug fix.
DoltDB tags (`rubric-v4.0.0`) cross-reference git tags with the same name.
`RUBRIC_VERSION` constant lives in `src/scorers/v2_scorers.py`.

## Wallet Tags

- `ZAKAT-ELIGIBLE`: Charity claims zakat eligibility on website
- `SADAQAH-ELIGIBLE`: All other charities (default)

## Hallucination-Prone Fields

These fields are known to be unreliable when extracted by LLMs. **Actual
enforcement is cross-source corroboration + ensemble verification** during
extraction (`CrossSourceCorroborator` in `src/parsers/charity_metrics_aggregator.py`;
multi-model ensemble checks in `src/collectors/web_collector.py` /
`src/llm/website_extractor.py`) — not `src/validators/hallucination_denylist.py`.
`synthesize.py` calls `flag_unverified_fields()` from that module and logs
which fields lack corroboration, but the result is informational only: it is
not attached to the synthesized data and does not block scoring or export.

| Field | Why Prone | Verification |
|-------|-----------|--------------|
| `accepts_zakat` | LLMs infer from generic "donate" buttons | Require explicit zakat page/calculator |
| `populations_served` | Defaults to "underserved communities" | Require specific population descriptions |
| `external_evaluations` | Fabricates evaluation sources | Cross-reference with actual evaluator APIs |
| `scholarly_endorsements` | Generates plausible but fake names | Require verifiable source (fatwa, letter) |
| `third_party_evaluated` | Infers from website badges | Verify via CN/Candid/GiveWell APIs |
| `cost_per_beneficiary` | Calculates from incomplete data | Require verified financials + beneficiary count |
| `impact_multiplier` | Assigns based on cause stereotypes | Only accept from GiveWell/Open Phil |
| `evidence_quality` | Assigns grades from marketing copy | Require citation to actual studies |

Usage (informational logging only — does not gate scoring or export):
```python
from src.validators import flag_unverified_fields, is_hallucination_prone

# Check if field is prone to hallucination
if is_hallucination_prone("accepts_zakat"):
    print("Requires verification")

# synthesize.py logs unverified fields; nothing downstream blocks on this
flagged = flag_unverified_fields({"accepts_zakat": True})
# Returns: {"accepts_zakat_unverified": True}
```

## Anti-Patterns

- **Don't run all charities first** - Test 1 → 5 → 10 → all
- **Don't fabricate data** - Missing fields stay NULL
- **Don't hardcode EINs** - Use `pilot_charities.txt`
- **Don't trust LLM-extracted hallucination-prone fields** - Always verify via corroboration

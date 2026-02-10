# Data Pipeline

Charity evaluation pipeline with 2 scored dimensions + data confidence signal. Uses **DoltDB** for version-controlled data storage.

## Pipeline Phases

```bash
# Phase 1: Crawl - FETCH raw data (no parsing)
uv run python crawl.py --ein 95-4453134
uv run python crawl.py --charities pilot_charities.txt

# Phase 2: Extract - PARSE raw_html into validated schemas
uv run python extract.py --ein 95-4453134
uv run python extract.py --charities pilot_charities.txt

# Phase 3: Synthesize - Aggregate and derive fields
uv run python synthesize.py --ein 95-4453134
uv run python synthesize.py --charities pilot_charities.txt

# Phase 4: Baseline - Generate AMAL scores and narratives
uv run python baseline.py --ein 95-4453134
uv run python baseline.py --charities pilot_charities.txt --workers 10

# Phase 5: Export - Export to website
uv run python export.py
```

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

## Data Quality Check

Run between pipeline phases to validate scraped data:

```bash
uv run python data_quality_check.py                     # Check all charities
uv run python data_quality_check.py --ein 95-4453134   # Check single charity
uv run python data_quality_check.py --source propublica # Check single source
uv run python data_quality_check.py --verbose           # Show per-field details
uv run python data_quality_check.py --json              # Output JSON report
```

Reports: field coverage, validation errors, success rates by source.

## Testing

```bash
uv run pytest                           # All tests
uv run pytest tests/test_v2_scorers.py  # Scorer tests
ruff check . --fix                      # Lint
```

## Key Files

```
pilot_charities.txt           # Source of truth for EINs (173 charities, organized by category)
crawl.py                      # Phase 1: FETCH raw data (no parsing)
extract.py                    # Phase 2: PARSE raw_html → parsed_json
synthesize.py                 # Phase 3: Aggregate + derive
baseline.py                   # Phase 4: AMAL scores + narratives
export.py                     # Phase 5: Export to website
data_quality_check.py         # Validate scraped data quality between phases
src/db/                       # DoltDB repositories + version control
src/db/dolt_client.py         # Git-like operations (commit, branch, diff)
src/collectors/               # ProPublica, CN, Candid, Web (fetch + parse methods)
src/scorers/v2_scorers.py     # Impact, Alignment, Risk, DataConfidence (rubric v5.0.0)
src/parsers/charity_metrics_aggregator.py  # Data aggregation
```

## Scoring Dimensions (GMG Score, rubric v5.0.0, 100 pts total)

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

These fields are known to be unreliable when extracted by LLMs. They require
explicit verification before being used in scoring. See `src/validators/hallucination_denylist.py`.

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

Usage:
```python
from src.validators import flag_unverified_fields, is_hallucination_prone

# Check if field is prone to hallucination
if is_hallucination_prone("accepts_zakat"):
    print("Requires verification")

# Flag unverified fields in extracted data
flagged = flag_unverified_fields({"accepts_zakat": True})
# Returns: {"accepts_zakat_unverified": True}
```

## Anti-Patterns

- **Don't run all charities first** - Test 1 → 5 → 10 → all
- **Don't fabricate data** - Missing fields stay NULL
- **Don't hardcode EINs** - Use `pilot_charities.txt`
- **Don't trust LLM-extracted hallucination-prone fields** - Always verify via corroboration

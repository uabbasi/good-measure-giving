# Good Measure Giving Data Pipeline

Python pipeline for collecting, parsing, scoring, and exporting Muslim charity data.

## Pipeline Stages

The default V2 pipeline runs 5 stages:

1. `crawl.py` - Fetch raw data from sources
2. `extract.py` - Parse raw content into validated source schemas
3. `synthesize.py` - Reconcile sources and derive canonical fields
4. `baseline.py` - Generate baseline scores and narratives
5. `export.py` - Export website ready JSON datasets

## Quick Start

```bash
cd data-pipeline
uv sync

# Run all stages
./run_v2.sh --charities pilot_charities.txt --workers 10
```

## Run Individual Stages

```bash
# Stage 1: crawl
uv run python crawl.py --charities pilot_charities.txt --workers 10

# Stage 2: extract
uv run python extract.py --charities pilot_charities.txt --workers 5

# Stage 3: synthesize
uv run python synthesize.py --charities pilot_charities.txt

# Stage 4: baseline scoring and narratives
uv run python baseline.py --charities pilot_charities.txt

# Stage 5: export to website data
uv run python export.py --charities pilot_charities.txt
```

## Required Environment Variables

Set these in root `.env`:

- `GEMINI_API_KEY` for LLM powered extraction and narrative work
- `CN_API_KEY` optional, if using Charity Navigator API paths
- Dolt connection settings (`DOLT_HOST`, `DOLT_PORT`, `DOLT_DATABASE`, etc.)

See root `.env.example` for full configuration.

## Data Source and Compliance Notes

This pipeline can collect and process data from third party systems.

Before running in production:
- Confirm each source allows your usage pattern
- Respect robots.txt and rate limits
- Preserve required attribution where applicable
- Do not commit proprietary raw HTML snapshots from third party sites

## Testing

```bash
cd data-pipeline
uv run pytest tests/test_parsers.py
```

## Output

Primary export target:
- `website/data/charities.json`
- `website/data/charities/` per charity JSON files

## Related Docs

- `../README.md`
- `../SECURITY.md`
- `../website/README.md`

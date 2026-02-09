# Good Measure Giving

Charity evaluation website informed by evidence-based altruism and long-term thinking.

## Two-Tier Narratives
- **Baseline**: Facts + quantitative/qualitative analysis. Goal: essentials + prompt login.
- **Rich**: Detailed analysis providing real value to donors.

## Stack
- **Backend**: Python 3.13, DoltDB (MySQL-compatible, version-controlled)
- **Frontend**: TypeScript 5.8, React 19, Vite 6
- **LLM**: Gemini 3.0 Flash (primary) with fallback chain
- **Auth**: Supabase (user auth only, not charity data)

## Commands
```bash
uv sync                        # Setup Python deps
uv run z                       # Interactive pipeline wizard
ruff check . --fix             # Lint
cd website && npm run dev      # Frontend dev server
```

## DoltDB (Version-Controlled Database)

All charity data is stored in DoltDB, which provides Git-like version control:

```bash
# Database location
~/.amal-metric-data/dolt/zakaat

# Start the database server
cd ~/.amal-metric-data/dolt/zakaat && dolt sql-server

# View commit history
dolt log --oneline

# See what changed in last pipeline run
dolt diff HEAD~1 HEAD
```

Every pipeline run creates a commit. See `data-pipeline/CLAUDE.md` for details.

## Development Workflow
Always use `pilot_charities.txt` as source. Test incrementally: 1 → 5 → 10 → all.

See `data-pipeline/CLAUDE.md` for pipeline details.
See `website/CLAUDE.md` for frontend details (if exists).

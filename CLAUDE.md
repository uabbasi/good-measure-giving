# Good Measure Giving

Charity evaluation website informed by evidence-based altruism and long-term thinking.

## Two-Tier Narratives
- **Baseline**: Facts + quantitative/qualitative analysis. Goal: essentials + prompt login.
- **Rich**: Detailed analysis providing real value to donors.

## Stack
- **Backend**: Python 3.13, DoltDB (MySQL-compatible, version-controlled)
- **Frontend**: TypeScript 5.8, React 19, Vite 6
- **LLM**: Gemini 3.0 Flash (primary) with fallback chain
- **Auth**: Firebase (user auth only, not charity data)

## Commands
```bash
uv sync                        # Setup Python deps
cd data-pipeline && uv run python streaming_runner.py --charities pilot_charities.txt   # Full pipeline
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

## Issue Tracking: Linear

Track work in **Linear**, not beads. Beads is frozen: `.beads/` is kept as read-only
history. Read it if you need old context; never write to it (`bd create`, `bd update`,
`bd close`, `bd remember` are all off-limits).

- Where: workspace "weeklies", team "Roshni" (issue prefix ONYX), project "GMG", label `gmg`.
- Tools: the Linear MCP tools (`mcp__plugin_design_linear__*`; load with ToolSearch "linear").
- Before starting work: find or create its issue (project GMG, label `gmg`) and set it
  **In Progress**.
- When it lands: set it **Done** and comment with the PR number.
- The 7 open beads were copied to Linear on 2026-09-29: ONYX-11 = xo2, ONYX-10 = qpv,
  ONYX-9 = kg3, ONYX-8 = 9kl, ONYX-7 = 9ee, ONYX-6 = 69t, ONYX-195 = 600
  (bead ids are `good-measure-giving-<suffix>`).
- Keep issues about the work: no personal details.

## Git Policy

Do not commit, push, or open PRs unless the current request asks for it. At handoff,
report changed files, validation, and suggested next commands.

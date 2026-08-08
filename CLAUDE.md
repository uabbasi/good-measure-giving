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
See `website/CLAUDE.md` for frontend details (if exists).

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

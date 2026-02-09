# Pipeline Orchestration Policy

This document defines the execution contract for pipeline phases.

## Standard Runner

- `streaming_runner.py` is the canonical orchestrator.
- Standalone phase scripts (`synthesize.py`, `baseline.py`, `rich_phase.py`, `export.py`) must conform to the same failure semantics and data-flow assumptions.

## Hard-Failure Principle

- A phase failure is terminal for that EIN.
- Downstream phases must not run after upstream failure.
- ERROR-severity quality-judge findings are hard failures.
- Batch commands must exit non-zero if any EIN fails processing or fails quality gates.
- Cache must not remain valid for a phase that failed quality checks.

## Data-Flow Rules

- Baseline and rich are serial, not independent.
- When baseline is regenerated, previously stored rich narrative fields are invalidated.
- Rich generation must consume baseline/evaluation context, not just partial narrative fragments.

## Practical Guidance

- Use `streaming_runner.py` for production and full pipeline runs.
- Use standalone scripts for targeted reruns/debugging, but expect identical pass/fail behavior.

"""Phase fingerprinting for smart caching.

Computes code fingerprints to detect when phase logic has changed,
enabling the pipeline to skip expensive LLM calls when code is unchanged.
"""

import hashlib
from pathlib import Path

# Map phases to the code files that define their behavior
# Changes to these files should trigger re-running the phase
#
# Philosophy: Include files that define OUTPUT behavior, not infrastructure.
# - Validators: Included (transform/validate data)
# - Schemas: Included (define LLM response structure)
# - LLM prompts: Included (define what's generated)
# - Base classes: Include if they have behavior logic
# - DB/utilities: Exclude (infrastructure, doesn't affect output)
#
PHASE_CODE_FILES: dict[str, list[str]] = {
    "crawl": [
        # Orchestrator
        "src/collectors/orchestrator.py",
        "src/collectors/base.py",
        # All collectors (fetch methods)
        "src/collectors/propublica.py",
        "src/collectors/charity_navigator.py",
        "src/collectors/candid_beautifulsoup.py",
        "src/collectors/form990_grants.py",
        "src/collectors/web_collector.py",
        "src/collectors/bbb_collector.py",
        # Web collector dependencies
        "src/llm/website_extractor.py",
        "src/extractors/page_classifier.py",
        "src/utils/playwright_renderer.py",
    ],
    "extract": [
        # Standalone runner
        "extract.py",
        # All collectors (parse methods)
        "src/collectors/base.py",
        "src/collectors/propublica.py",
        "src/collectors/charity_navigator.py",
        "src/collectors/candid_beautifulsoup.py",
        "src/collectors/form990_grants.py",
        "src/collectors/bbb_collector.py",
        # Validators (define data transformation/validation)
        "src/validators/base_validator.py",
        "src/validators/propublica_validator.py",
        "src/validators/candid_validator.py",
        "src/validators/charity_navigator_validator.py",
        "src/validators/bbb_validator.py",
        "src/validators/form990_grants_validator.py",
    ],
    "discover": [
        # Discovery services
        "src/services/zakat_verification_service.py",
        "src/services/evidence_discovery_service.py",
        "src/services/outcome_discovery_service.py",
        "src/services/toc_discovery_service.py",
        "src/services/awards_discovery_service.py",
        # Search agent (defines how search works)
        "src/agents/gemini_search.py",
    ],
    "synthesize": [
        # Main files
        "synthesize.py",
        "src/parsers/charity_metrics_aggregator.py",
        # Dependencies that affect output
        "src/services/zakat_eligibility_service.py",
        "src/llm/category_classifier.py",
        "src/validators/source_required_validator.py",
    ],
    "baseline": [
        # Main files
        "baseline.py",
        "src/scorers/v2_scorers.py",
        # Baseline prompt is now inline in baseline.py (lines 324-412)
        # Schemas
        "src/llm/schemas/baseline.py",
        "src/llm/schemas/common.py",
        # Services
        "src/services/citation_service.py",
        "src/utils/scoring_audit.py",
    ],
    "rich": [
        # Main files
        "rich_phase.py",
        "src/services/rich_narrative_generator.py",
        # LLM prompts (rich_narrative.txt superseded by v2)
        "src/llm/prompts/rich_narrative_v2.txt",
        # Schemas
        "src/llm/schemas/rich.py",
        "src/llm/schemas/rich_v2.py",
        # Services
        "src/services/citation_service.py",
        "src/validators/consistency_validator.py",
    ],
    "judge": [
        # Main file
        "judge_phase.py",
        # Judge orchestrator and base
        "src/judges/orchestrator.py",
        "src/judges/base_judge.py",
        # LLM-based semantic judges
        "src/judges/basic_info_judge.py",
        "src/judges/citation_judge.py",
        "src/judges/data_completeness_judge.py",
        "src/judges/diff_validator.py",
        "src/judges/factual_judge.py",
        "src/judges/recognition_judge.py",
        "src/judges/score_judge.py",
        "src/judges/url_verifier.py",
        "src/judges/zakat_judge.py",
        # Deterministic phase quality judges
        "src/judges/crawl_quality_judge.py",
        "src/judges/extract_quality_judge.py",
        "src/judges/discover_quality_judge.py",
        "src/judges/synthesize_quality_judge.py",
        "src/judges/baseline_quality_judge.py",
        "src/judges/export_quality_judge.py",
        # Judge prompts (define what judges check for)
        "src/judges/prompts/citation_judge.txt",
        "src/judges/prompts/factual_judge.txt",
        "src/judges/prompts/score_judge.txt",
        "src/judges/prompts/zakat_judge.txt",
        # Judge schemas
        "src/judges/schemas/verdict.py",
        "src/judges/schemas/config.py",
    ],
}

# Default TTLs in days (float('inf') means code-only, no time expiry)
DEFAULT_TTLS: dict[str, float] = {
    "crawl": 30,           # External data changes infrequently
    "extract": float("inf"),  # Pure transform, code-only
    "discover": 90,        # Search results change slowly
    "synthesize": float("inf"),  # Deterministic, code-only
    "baseline": float("inf"),    # Only rerun if scoring logic changes
    "rich": float("inf"),        # Only rerun if narrative code changes
    "judge": float("inf"),       # Only rerun if judge criteria change
}

# Phase dependency graph - downstream phases auto-invalidate when upstream runs
PHASE_DEPENDENCIES: dict[str, list[str]] = {
    "crawl": [],
    "extract": ["crawl"],
    "discover": ["crawl"],
    "synthesize": ["extract", "discover"],
    "baseline": ["synthesize"],
    "rich": ["baseline"],
    "judge": ["baseline", "rich"],
    "export": ["judge"],
}

# Reverse lookup: which phases depend on this one
PHASE_DEPENDENTS: dict[str, list[str]] = {}
for phase, deps in PHASE_DEPENDENCIES.items():
    for dep in deps:
        if dep not in PHASE_DEPENDENTS:
            PHASE_DEPENDENTS[dep] = []
        PHASE_DEPENDENTS[dep].append(phase)


def compute_code_fingerprint(phase: str, base_path: Path | None = None) -> str:
    """Compute SHA256 fingerprint of all code files for a phase.

    Args:
        phase: The phase name (crawl, extract, discover, etc.)
        base_path: Base path for resolving file patterns (defaults to cwd)

    Returns:
        16-character hex fingerprint (truncated SHA256)
    """
    if phase not in PHASE_CODE_FILES:
        raise ValueError(f"Unknown phase: {phase}")

    base = base_path or Path.cwd()

    # Handle case where we're in the data-pipeline directory
    if base.name != "data-pipeline" and (base / "data-pipeline").exists():
        base = base / "data-pipeline"

    hasher = hashlib.sha256()
    files_found = 0

    for pattern in PHASE_CODE_FILES[phase]:
        # Handle glob patterns and direct files
        if "*" in pattern:
            paths = sorted(base.glob(pattern))
        else:
            path = base / pattern
            paths = [path] if path.exists() else []

        for path in paths:
            if path.is_file():
                try:
                    hasher.update(path.read_bytes())
                    files_found += 1
                except OSError:
                    # Skip unreadable files
                    pass

    if files_found == 0:
        # Return a sentinel value if no files found
        # This ensures the fingerprint changes if files are added later
        return "0" * 16

    return hasher.hexdigest()[:16]


def get_downstream_phases(phase: str) -> list[str]:
    """Get all phases that depend on this one (transitively).

    Used for cascade invalidation when a phase re-runs.

    Args:
        phase: The phase that ran

    Returns:
        List of downstream phase names in dependency order
    """
    downstream = []
    queue = [phase]
    visited = {phase}

    while queue:
        current = queue.pop(0)
        dependents = PHASE_DEPENDENTS.get(current, [])
        for dep in dependents:
            if dep not in visited:
                visited.add(dep)
                downstream.append(dep)
                queue.append(dep)

    return downstream


def get_ttl_days(phase: str, ttl_overrides: dict[str, float] | None = None) -> float:
    """Get TTL in days for a phase.

    Args:
        phase: Phase name
        ttl_overrides: Optional dict to override default TTLs

    Returns:
        TTL in days (float('inf') for code-only phases)
    """
    if ttl_overrides and phase in ttl_overrides:
        return ttl_overrides[phase]
    return DEFAULT_TTLS.get(phase, float("inf"))

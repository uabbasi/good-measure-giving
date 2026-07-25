"""Read-only blast-radius measurement for the newly-activated citation/factual judges.

Task D4b added a `narrative` key to the dict `judge_phase.py` passes to the
judges (commit be43699). That key is read by four judges, and two of them —
FactualJudge and CitationJudge — have been complete no-ops for the entire
life of this codebase, because the key never existed before:

  - factual_judge.py: `if not narrative: return create_verdict(passed=True, ...)`
  - citation_judge.py: `citations = narrative.get("all_citations", [])`

Both are registered in the active publication gate and both emit
Severity.ERROR. The next fleet run will, for the first time, actually
evaluate every charity against them. This script measures how many charities
would newly fail *before* that run is authorized.

This is report-only: it makes NO LLM calls and NO network requests, and
writes nothing to DoltDB. It reuses judge_phase.judge_charity()'s real
charity_dict/context construction unchanged — the only thing swapped in is
which orchestrator that data is handed to (monkeypatched to run only
citation+factual, with the LLM/network-dependent branches of each disabled).

## What is and isn't measured

Neither judge is fully deterministic; only part of each can be measured here.

FactualJudge.validate():
  - `_quick_checks` (deterministic, pure Python) — RUN by this harness. But
    every check in it compares `output["evaluation"]` against
    `output["financials"]` / `context["metrics"]`, and judge_phase.py's real
    charity_dict/context NEVER populates `"financials"` or `"metrics"` keys
    (see JUDGE_PROJECTION_FIELDS in judge_phase.py — no such fields; context
    only carries raw_sources/source_data/charity_data/charity). So this is
    not merely "safe to run" — it is *structurally incapable of firing* for
    any charity, given how the real caller builds its input. That is a
    finding in its own right, reported in `check_classification`.
  - LLM claim extraction/verification (`_verify_claims_with_llm`) — this is
    the actual substance of the judge (matching narrative prose against
    source data). NOT measured; requires an LLM call. Patched to a no-op
    that returns None (matching the judge's own "nothing found" shape)
    rather than skipped/raised, so no spurious issue is manufactured.

CitationJudge.validate():
  - Structural marker validation (`_validate_structure`) — deterministic,
    RUN by this harness. Flags a `[N]` marker in narrative text with no
    matching citation entry (ERROR).
  - Missing-URL-on-a-citation-entry check — deterministic, RUN.
  - Trusted-domain skip (`should_skip`) — deterministic (domain string
    match), RUN as real production logic.
  - URL reachability (`URLVerifier.fetch`) — network-dependent. NOT
    measured; stubbed to fail closed without any network call. The
    resulting WARNING issues are an artifact of the stub (not a real
    signal) and are dropped from the report; only the count of skipped
    checks is kept.
  - LLM claim-vs-content verification (`_verify_claims_with_llm`) — NOT
    measured; requires an LLM call. Disabled two ways: `verify_all_citations
    =False` in the harness config (so the judge's own code never reaches
    that branch) and a defensive monkeypatch to a no-op, in case that ever
    changes.

Usage:
    uv run python bin/judge_activation_blast_radius.py
    uv run python bin/judge_activation_blast_radius.py --ein 95-4453134
    uv run python bin/judge_activation_blast_radius.py --limit 10
"""

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import judge_phase  # noqa: E402
from export import partition_by_judge_gate  # noqa: E402
from src.db import (  # noqa: E402
    CharityDataRepository,
    CharityRepository,
    EvaluationRepository,
    RawDataRepository,
)
from src.db.client import execute_query  # noqa: E402
from src.judges import citation_judge as citation_judge_module  # noqa: E402
from src.judges import factual_judge as factual_judge_module  # noqa: E402
from src.judges.orchestrator import JudgeOrchestrator  # noqa: E402
from src.judges.schemas.config import JudgeConfig  # noqa: E402
from src.judges.url_verifier import FetchResult, URLVerifier  # noqa: E402

REPORTS_DIR = Path(__file__).parent.parent / "reports"
WEBSITE_CHARITIES_DIR = Path(__file__).parent.parent.parent / "website" / "data" / "charities"

# Pattern used in the sanity checks (Step 4): a mangled Charity Navigator
# score in prose, e.g. "98.98.66666666666667/100" — two decimal points.
_MANGLED_CN_SCORE_RE = re.compile(r"\d+\.\d+\.\d+/100")
# The hallucinated fundraising-efficiency claim, in its several observed
# phrasings ("$0.00 per $1 raised", "$0.00 to raise every $1", "$0.00 on
# fundraising for every $1 raised", "fundraising efficiency of $0.00", ...).
_ZERO_FUNDRAISING_RE = re.compile(r"\$0\.00")

# Check-by-check classification (Step 1). Feeds the report so it states
# plainly what could and couldn't be evaluated — see module docstring.
CHECK_CLASSIFICATION: dict[str, dict[str, dict[str, str]]] = {
    "factual": {
        "quick_checks.amal_score_mismatch": {
            "status": "deterministic",
            "note": "Never fires: requires context['metrics'], which judge_phase.py's charity_dict never sets.",
        },
        "quick_checks.wallet_tag_mismatch": {
            "status": "deterministic",
            "note": "Never fires: same context['metrics'] gap.",
        },
        "quick_checks.program_expense_ratio_bounds": {
            "status": "deterministic",
            "note": "Never fires: requires output['financials'], which judge_phase.py's charity_dict never sets.",
        },
        "quick_checks.strategic_score_mismatch": {
            "status": "deterministic",
            "note": "Never fires: requires context['metrics']['strategic_score'].",
        },
        "quick_checks.archetype_mismatch": {
            "status": "deterministic",
            "note": "Never fires: requires context['metrics']['archetype'].",
        },
        "quick_checks.strategic_dimension_mismatch": {
            "status": "deterministic",
            "note": "Never fires: requires context['metrics']['strategic_dimensions'].",
        },
        "llm_claim_extraction_and_verification": {
            "status": "llm-dependent",
            "note": "The judge's actual substance (matching narrative prose to source data). Not measured.",
        },
    },
    "citation": {
        "structural_marker_validation": {
            "status": "deterministic",
            "note": "[N] marker in narrative text with no matching citation entry. Measured.",
        },
        "missing_url_on_citation_entry": {
            "status": "deterministic",
            "note": "Citation entry with an empty url/source_url field. Measured.",
        },
        "trusted_domain_skip": {
            "status": "deterministic",
            "note": "Not itself issue-emitting; gates whether a citation needs a network fetch. Measured.",
        },
        "url_reachability_fetch": {
            "status": "network-dependent",
            "note": "Stubbed to fail closed with no network call. Resulting WARNINGs are a stub artifact, dropped.",
        },
        "llm_content_supports_claim": {
            "status": "llm-dependent",
            "note": "Not measured. Disabled via verify_all_citations=False plus a defensive monkeypatch.",
        },
    },
}

_STUB_FETCH_ERROR = "NETWORK DISABLED for blast-radius measurement (unmeasured)"


class _StubURLVerifier(URLVerifier):
    """URLVerifier that never makes a network request.

    `should_skip()` (trusted-domain check) is real, deterministic, no-network
    logic and is inherited unchanged. `fetch()` is replaced with a synthetic
    failure so CitationJudge's per-citation loop runs to completion without
    ever calling httpx. Reachability itself is NOT measured (see module
    docstring / CHECK_CLASSIFICATION).
    """

    def __init__(self, cache_dir: Path):
        super().__init__(cache_dir=cache_dir, timeout=1, ttl_days=1)
        self.calls_blocked = 0

    def fetch(self, url: str, skip_cache: bool = False) -> FetchResult:  # noqa: ARG002
        self.calls_blocked += 1
        return FetchResult(success=False, error=_STUB_FETCH_ERROR)


# Defense-in-depth: even though the harness config disables the branches
# that would call these, patch both judges' LLM methods to a no-op that
# returns None (the judge's own "nothing found" shape) rather than leaving
# any path that could reach a real LLMClient. Global (class-level) patch —
# fine for a single-purpose measurement script.
def _no_llm_factual(self, output: dict, context: dict) -> None:  # noqa: ARG001
    return None


def _no_llm_citation(self, output: dict, citations: list, url_content: dict, context: dict) -> None:  # noqa: ARG001
    return None


factual_judge_module.FactualJudge._verify_claims_with_llm = _no_llm_factual
citation_judge_module.CitationJudge._verify_claims_with_llm = _no_llm_citation


class _BlastRadiusOrchestrator:
    """Drop-in replacement for JudgeOrchestrator, injected by monkeypatching
    `judge_phase.JudgeOrchestrator` for the duration of this script.

    judge_charity() builds its charity_dict/context and then does
    `with JudgeOrchestrator(config) as orchestrator: orchestrator.validate_single(...)`.
    Swapping the class this way reuses that construction completely
    unchanged; only which orchestrator processes the result is different —
    this one runs only citation + factual, with no LLM calls, no network
    access, and persist_verdicts=False (no DB writes).
    """

    def __init__(self, _config: JudgeConfig, *args, **kwargs):  # noqa: ARG002
        # `_config` is judge_charity()'s hardcoded all-judges-enabled
        # config — ignored; this harness only ever runs citation + factual.
        harness_config = JudgeConfig(
            sample_rate=1.0,
            verify_all_citations=False,  # never take CitationJudge's LLM branch
            enable_citation_judge=True,
            enable_factual_judge=True,
            enable_score_judge=False,
            enable_zakat_judge=False,
            enable_data_completeness_judge=False,
            enable_basic_info_judge=False,
            enable_recognition_judge=False,
            enable_crawl_quality_judge=False,
            enable_extract_quality_judge=False,
            enable_discover_quality_judge=False,
            enable_synthesize_quality_judge=False,
            enable_baseline_quality_judge=False,
            enable_export_quality_judge=False,
            enable_narrative_quality_judge=False,
            enable_cross_lens_judge=False,
        )
        self._tmp_cache_dir = tempfile.TemporaryDirectory(prefix="judge_blast_radius_")
        self._real = JudgeOrchestrator(harness_config, persist_verdicts=False)
        self._real._url_verifier = _StubURLVerifier(Path(self._tmp_cache_dir.name))

    def __enter__(self) -> "_BlastRadiusOrchestrator":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._real.close()
        self._tmp_cache_dir.cleanup()
        return False

    def validate_single(self, charity_dict: dict, context: dict):
        return self._real.validate_single(charity_dict, context)


def load_eins_with_baseline_narrative() -> list[str]:
    """Every EIN in `evaluations` that currently has a baseline_narrative."""
    rows = execute_query("SELECT charity_ein FROM evaluations WHERE baseline_narrative IS NOT NULL") or []
    return [r["charity_ein"] for r in rows]


def find_zero_fundraising_candidates() -> list[str]:
    """EINs whose exported narrative claims a $0.00 fundraising-efficiency
    figure (any phrasing). Scans website/data/charities/*.json, read-only."""
    candidates = []
    for path in sorted(WEBSITE_CHARITIES_DIR.glob("charity-*.json")):
        text = path.read_text()
        if _ZERO_FUNDRAISING_RE.search(text):
            candidates.append(path.stem.removeprefix("charity-"))
    return candidates


def find_mangled_cn_score_candidates() -> list[str]:
    """EINs whose exported narrative contains a mangled CN score like
    '98.98.66666666666667/100'. Scans website/data/charities/*.json, read-only."""
    candidates = []
    for path in sorted(WEBSITE_CHARITIES_DIR.glob("charity-*.json")):
        text = path.read_text()
        if _MANGLED_CN_SCORE_RE.search(text):
            candidates.append(path.stem.removeprefix("charity-"))
    return candidates


def is_true_zero_fundraising_hallucination(charity_data: Optional[dict]) -> bool:
    """True when the $0.00 claim cannot be a real computed value.

    Mirrors baseline.py's own guard for rendering fundraising_efficiency
    (`fundraising_expenses is not None and total_revenue > 0`): when that
    guard is satisfied AND fundraising_expenses is a real 0, "$0.00 per $1
    raised" is a correct claim, not a hallucination. Otherwise the source
    has no basis for the specific figure the narrative states.
    """
    if not charity_data:
        return True
    fundraising_expenses = charity_data.get("fundraising_expenses")
    total_revenue = charity_data.get("total_revenue")
    has_real_basis = fundraising_expenses is not None and total_revenue and total_revenue > 0
    return not has_real_basis


def _drop_stub_artifacts(issues: list[dict]) -> tuple[list[dict], int]:
    """Strip citation WARNINGs generated by the fetch() stub (not real
    signal — see module docstring). Returns (clean_issues, dropped_count)."""
    clean = []
    dropped = 0
    for issue in issues:
        if issue["judge"] == "citation" and _STUB_FETCH_ERROR in issue["message"]:
            dropped += 1
            continue
        clean.append(issue)
    return clean, dropped


def run(eins: list[str]) -> dict[str, Any]:
    eval_repo = EvaluationRepository()
    data_repo = CharityDataRepository()
    raw_repo = RawDataRepository()
    charity_repo = CharityRepository()

    # Swap in the harness orchestrator for the duration of this run only.
    # judge_charity() looks up `JudgeOrchestrator` in judge_phase's module
    # globals at call time, so this reassignment is picked up immediately.
    real_orchestrator_cls = judge_phase.JudgeOrchestrator
    judge_phase.JudgeOrchestrator = _BlastRadiusOrchestrator
    try:
        per_charity = []
        failed_eins = []
        stub_url_warnings_dropped = 0

        for ein in eins:
            result = judge_phase.judge_charity(ein, eval_repo, data_repo, raw_repo, charity_repo)
            if not result.get("success"):
                failed_eins.append({"ein": ein, "error": result.get("error")})
                continue

            issues, dropped = _drop_stub_artifacts(result.get("issues", []))
            stub_url_warnings_dropped += dropped

            charity = charity_repo.get(ein)
            errors_by_judge: dict[str, int] = {}
            for issue in issues:
                if issue["severity"] == "error":
                    errors_by_judge[issue["judge"]] = errors_by_judge.get(issue["judge"], 0) + 1

            per_charity.append(
                {
                    "ein": ein,
                    "name": charity.get("name") if charity else ein,
                    "newly_fails": bool(errors_by_judge),
                    "judges_with_errors": sorted(errors_by_judge),
                    "issues": issues,
                }
            )
    finally:
        judge_phase.JudgeOrchestrator = real_orchestrator_cls

    # "Currently publishes" — the real production gate (export.py), not a
    # reimplementation of it.
    publishable, _excluded = partition_by_judge_gate(eins, eval_repo)
    publishable_set = set(publishable)
    for row in per_charity:
        row["currently_publishes"] = row["ein"] in publishable_set

    # Aggregate
    newly_failing = [r for r in per_charity if r["newly_fails"]]
    by_judge: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for row in newly_failing:
        for judge in row["judges_with_errors"]:
            by_judge[judge] = by_judge.get(judge, 0) + 1
        for issue in row["issues"]:
            if issue["severity"] == "error":
                by_category[issue["field"]] = by_category.get(issue["field"], 0) + 1

    # Step 4: sanity checks
    zero_fundraising_eins = find_zero_fundraising_candidates()
    zero_fundraising_true_hallucinations = [
        ein for ein in zero_fundraising_eins if is_true_zero_fundraising_hallucination(data_repo.get(ein))
    ]
    mangled_cn_eins = find_mangled_cn_score_candidates()

    per_charity_by_ein = {r["ein"]: r for r in per_charity}

    def _flagged_any(eins_: list[str]) -> list[str]:
        return [e for e in eins_ if per_charity_by_ein.get(e, {}).get("newly_fails")]

    sanity_checks = {
        "zero_fundraising_claim": {
            "description": "Narrative states a $0.00 fundraising-efficiency figure (any phrasing).",
            "candidates_found": len(zero_fundraising_eins),
            "confirmed_hallucinations": len(zero_fundraising_true_hallucinations),
            "confirmed_hallucination_note": (
                "Of the candidates, this many have fundraising_expenses NULL or total_revenue<=0 in "
                "charity_data — i.e. the source has no basis for the specific $0.00 figure stated. The "
                "rest have a real fundraising_expenses=0 and total_revenue>0, matching baseline.py's own "
                "render guard, so '$0.00 per $1 raised' is a correct claim for those, not a hallucination."
            ),
            "flagged_by_newly_active_judges": _flagged_any(zero_fundraising_true_hallucinations),
            "eins_confirmed_hallucinations": zero_fundraising_true_hallucinations,
        },
        "mangled_cn_score": {
            "description": "Narrative contains a mangled Charity Navigator score, e.g. '98.98.66666666666667/100'.",
            "candidates_found": len(mangled_cn_eins),
            "flagged_by_newly_active_judges": _flagged_any(mangled_cn_eins),
            "eins": mangled_cn_eins,
        },
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": {
            "charities_scanned": len(eins),
            "source_query": "SELECT charity_ein FROM evaluations WHERE baseline_narrative IS NOT NULL",
            "failed_to_evaluate": failed_eins,
        },
        "check_classification": CHECK_CLASSIFICATION,
        "unmeasured": {
            "factual_llm_claim_verification": "not run — requires an LLM call",
            "citation_url_reachability": (
                f"not run — {stub_url_warnings_dropped} URL-fetch checks across all charities were "
                "stubbed to avoid network calls; the resulting WARNINGs were dropped as stub artifacts"
            ),
            "citation_llm_content_verification": "not run — requires an LLM call",
        },
        "aggregate": {
            "newly_failing_charities": len(newly_failing),
            "of_charities_scanned": len(eins),
            "by_judge": by_judge,
            "by_issue_category": by_category,
        },
        "sanity_checks": sanity_checks,
        "per_charity": per_charity,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure blast radius of the newly-activated citation/factual judges.")
    parser.add_argument("--ein", help="Limit to one EIN (debugging).")
    parser.add_argument("--limit", type=int, help="Limit to the first N EINs (debugging).")
    args = parser.parse_args()

    if args.ein:
        eins = [args.ein]
    else:
        eins = load_eins_with_baseline_narrative()
        if args.limit:
            eins = eins[: args.limit]

    report = run(eins)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "judge-activation-blast-radius.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    agg = report["aggregate"]
    print(
        f"judge-activation-blast-radius: {agg['newly_failing_charities']} of "
        f"{agg['of_charities_scanned']} charities would newly fail the gate."
    )
    print(f"  by judge: {agg['by_judge']}")
    print(f"  by issue category: {agg['by_issue_category']}")
    zf = report["sanity_checks"]["zero_fundraising_claim"]
    print(
        f"  sanity check ($0.00 fundraising): {zf['candidates_found']} candidates, "
        f"{zf['confirmed_hallucinations']} confirmed hallucinations, "
        f"{len(zf['flagged_by_newly_active_judges'])} flagged by the newly-active judges"
    )
    cn = report["sanity_checks"]["mangled_cn_score"]
    print(
        f"  sanity check (mangled CN score): {cn['candidates_found']} candidates, "
        f"{len(cn['flagged_by_newly_active_judges'])} flagged by the newly-active judges"
    )
    if report["scope"]["failed_to_evaluate"]:
        print(f"  WARNING: {len(report['scope']['failed_to_evaluate'])} EINs failed to evaluate", file=sys.stderr)
    print(f"  full report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Inline quality checks for standalone pipeline scripts.

Provides the same quality gates that streaming_runner.py uses, so that
standalone scripts (extract.py, synthesize.py, baseline.py) halt on
ERROR-severity judge findings instead of silently propagating bad data.

Usage:
    from src.judges.inline_quality import run_quality_gate

    # After extract phase, check a charity's data:
    passed, issues = run_quality_gate("extract", ein)
    if not passed:
        print(f"Quality gate failed for {ein}")
        for issue in issues:
            print(f"  {issue['severity']}: {issue['field']} - {issue['message']}")
"""

from ..db.repository import CharityDataRepository, EvaluationRepository, RawDataRepository
from .base_judge import JudgeConfig
from .baseline_quality_judge import BaselineQualityJudge
from .crawl_quality_judge import CrawlQualityJudge
from .extract_quality_judge import ExtractQualityJudge
from .schemas.verdict import Severity
from .synthesize_quality_judge import SynthesizeQualityJudge

# Lightweight config — deterministic judges only, no LLM
_judge_config = JudgeConfig(sample_rate=1.0)

# Phase → judge class mapping (only deterministic judges that run inline)
_PHASE_JUDGES = {
    "crawl": CrawlQualityJudge,
    "extract": ExtractQualityJudge,
    "synthesize": SynthesizeQualityJudge,
    "baseline": BaselineQualityJudge,
}

_raw_repo = None
_charity_data_repo = None
_eval_repo = None


def _get_raw_repo() -> RawDataRepository:
    global _raw_repo
    if _raw_repo is None:
        _raw_repo = RawDataRepository()
    return _raw_repo


def _get_charity_data_repo() -> CharityDataRepository:
    global _charity_data_repo
    if _charity_data_repo is None:
        _charity_data_repo = CharityDataRepository()
    return _charity_data_repo


def _get_eval_repo() -> EvaluationRepository:
    global _eval_repo
    if _eval_repo is None:
        _eval_repo = EvaluationRepository()
    return _eval_repo


def _get_source_data(ein: str) -> dict:
    """Get parsed_json keyed by source name for a charity."""
    raw_data = _get_raw_repo().get_for_charity(ein)
    return {rd["source"]: rd["parsed_json"] for rd in raw_data if rd.get("parsed_json")}


def _build_phase_context(phase: str, ein: str) -> tuple[dict, dict]:
    """Build output and context dicts for a phase's quality judge.

    Mirrors the context that streaming_runner.py passes to each judge.

    Returns:
        (output, context) suitable for judge.validate(output, context)
    """
    if phase in ("crawl", "extract"):
        source_data = _get_source_data(ein)
        output = {"ein": ein, "parsed_sources": source_data}
        context = {"source_data": source_data}
        return output, context

    if phase == "synthesize":
        charity_data = _get_charity_data_repo().get(ein) or {}
        source_data = _get_source_data(ein)
        output = {"ein": ein, "charity_data": charity_data}
        context = {"source_data": source_data}
        return output, context

    if phase == "baseline":
        evaluation = _get_eval_repo().get(ein) or {}
        charity_data = _get_charity_data_repo().get(ein) or {}
        output = {"ein": ein, "evaluation": evaluation}
        context = {"charity_data": charity_data}
        return output, context

    return {"ein": ein}, {}


def run_quality_gate_batch(phase: str, eins: list[str]) -> list[str]:
    """Run quality gate for multiple EINs, printing failures.

    Encapsulates the loop+print pattern that was duplicated across
    extract.py, synthesize.py, and baseline.py.

    Args:
        phase: Pipeline phase name (crawl, extract, synthesize, baseline)
        eins: List of charity EINs to check

    Returns:
        List of EINs that failed the quality gate (empty if all passed).
    """
    failed_eins = []
    for ein in eins:
        passed, issues = run_quality_gate(phase, ein)
        errors_only = [i for i in issues if i["severity"] == "error"]
        if not passed:
            failed_eins.append(ein)
            print(f"  ✗ Quality gate FAILED for {ein}:")
            for issue in errors_only:
                print(f"      {issue['field']}: {issue['message'][:120]}")
    return failed_eins


def run_quality_gate(phase: str, ein: str) -> tuple[bool, list[dict]]:
    """Run the inline quality judge for a phase and return pass/fail.

    Args:
        phase: Pipeline phase name (crawl, extract, synthesize, baseline)
        ein: Charity EIN

    Returns:
        (passed, issues) — passed is False if any ERROR-severity issues found.
        Issues is a list of dicts with keys: judge, severity, field, message.
    """
    judge_class = _PHASE_JUDGES.get(phase)
    if not judge_class:
        return True, []

    try:
        judge = judge_class(_judge_config)
        output, context = _build_phase_context(phase, ein)
        verdict = judge.validate(output, context)

        issues = []
        for issue in verdict.issues:
            issues.append(
                {
                    "judge": verdict.judge_name,
                    "severity": issue.severity.value,
                    "field": issue.field,
                    "message": issue.message,
                }
            )

        has_errors = any(i.severity == Severity.ERROR for i in verdict.issues)
        return not has_errors, issues

    except Exception as e:
        # Judge execution failures are hard failures for strict data guarantees.
        return False, [
            {
                "judge": f"{phase}_quality",
                "severity": "error",
                "field": "judge_execution",
                "message": f"Quality judge failed: {str(e)[:100]}",
            }
        ]

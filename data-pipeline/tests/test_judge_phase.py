"""Tests for judge_phase: lens projection completeness + CLI persistence/exit codes."""

from unittest.mock import Mock

import judge_phase
import rich_phase
from src.judges.schemas.verdict import (
    CharityValidationResult,
    JudgeVerdict,
    Severity,
    ValidationIssue,
)

EIN = "13-5660870"


def _w(field: str, msg: str) -> ValidationIssue:
    return ValidationIssue(Severity.WARNING, field, msg)

FULL_EVALUATION = {
    "amal_score": 82,
    "wallet_tag": "ZAKAT-ELIGIBLE",
    "confidence_tier": "high",
    "impact_tier": "gold",
    "zakat_classification": "ELIGIBLE",
    "baseline_narrative": {"summary": "Baseline summary."},
    "rich_narrative": {"summary": "Rich summary."},
    # Orphaned March-era lens artifacts: never exported, no active generator —
    # must stay OUT of the judged/hashed surface.
    "strategic_narrative": {"summary": "Strategic summary."},
    "zakat_narrative": {"summary": "Zakat summary."},
    "rich_strategic_narrative": {"summary": "Rich strategic."},
    "strategic_score": 71,
    "zakat_score": 76,
    "score_details": {},
}


def _mock_repos(evaluation):
    eval_repo = Mock()
    eval_repo.get.return_value = evaluation
    data_repo = Mock()
    data_repo.get.return_value = {}
    raw_repo = Mock()
    raw_repo.get_for_charity.return_value = []
    charity_repo = Mock()
    charity_repo.get.return_value = {"name": "Test Charity"}
    return eval_repo, data_repo, raw_repo, charity_repo


class FakeOrchestrator:
    """Captures the charity_dict that judge_charity projects."""

    captured: dict = {}

    def __init__(self, config):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def validate_single(self, charity_dict, context):
        FakeOrchestrator.captured = charity_dict
        return CharityValidationResult(
            ein=charity_dict["ein"], name="Test Charity", passed=True, verdicts=[]
        )


class TestLensProjection:
    def test_projection_is_the_published_surface(self, monkeypatch):
        """Projection = what export.py ships: baseline + rich narratives, no orphaned lenses."""
        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", FakeOrchestrator)
        repos = _mock_repos(dict(FULL_EVALUATION))

        result = judge_phase.judge_charity(EIN, *repos)

        assert result["success"] is True
        projected = FakeOrchestrator.captured["evaluation"]
        assert projected["baseline_narrative"] == {"summary": "Baseline summary."}
        assert projected["rich_narrative"] == {"summary": "Rich summary."}
        assert projected["wallet_tag"] == "ZAKAT-ELIGIBLE"
        # Unpublished orphaned lens artifacts must not be judged or hashed:
        assert "strategic_narrative" not in projected
        assert "zakat_narrative" not in projected
        assert "rich_strategic_narrative" not in projected
        assert "strategic_score" not in projected
        assert "zakat_score" not in projected

    def test_judge_charity_returns_content_hash(self, monkeypatch):
        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", FakeOrchestrator)
        repos = _mock_repos(dict(FULL_EVALUATION))

        result = judge_phase.judge_charity(EIN, *repos)

        assert result["content_hash"] == judge_phase.compute_judge_content_hash(FULL_EVALUATION)

    def test_projection_matches_judge_surface(self, monkeypatch):
        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", FakeOrchestrator)
        repos = _mock_repos(dict(FULL_EVALUATION))

        judge_phase.judge_charity(EIN, *repos)

        assert FakeOrchestrator.captured["evaluation"] == judge_phase.build_judge_projection(FULL_EVALUATION)


class TestJudgeScoreDedupe:
    def test_judge_score_uses_deduped_warning_count(self, monkeypatch):
        """A verdict with per-lens copy-paste duplicates counts them once (score 85, not 80)."""

        class DupeOrchestrator:
            def __init__(self, config):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def validate_single(self, charity_dict, context):
                return CharityValidationResult(
                    ein=charity_dict["ein"],
                    name="Test Charity",
                    passed=True,
                    verdicts=[
                        JudgeVerdict(
                            passed=True,
                            judge_name="narrative_quality",
                            issues=[
                                _w("strategic.strengths", "Strengths are generic — could apply to any charity"),
                                _w("zakat.strengths", "Strengths are generic — could apply to any charity"),
                                _w(
                                    "strategic_narrative.jargon",
                                    "Jargon detected in strategic narrative: 'multiplier effect'",
                                ),
                            ],
                        ),
                        JudgeVerdict(
                            passed=True,
                            judge_name="synthesize_quality",
                            issues=[
                                _w(
                                    "hallucination_denylist.third_party_evaluated",
                                    "Hallucination-prone field 'third_party_evaluated' lacks cross-source corroboration",
                                )
                            ],
                        ),
                    ],
                )

        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", DupeOrchestrator)
        repos = _mock_repos(dict(FULL_EVALUATION))

        result = judge_phase.judge_charity(EIN, *repos)

        assert result["judge_score"] == 85
        assert result["warning_count"] == 3
        assert result["error_count"] == 0
        assert len(result["issues"]) == 4


def _verdict_result(passed: bool, judge_issues: list[tuple[str, list[ValidationIssue]]]) -> CharityValidationResult:
    return CharityValidationResult(
        ein=EIN,
        name="Test Charity",
        passed=passed,
        verdicts=[JudgeVerdict(passed=not issues, judge_name=name, issues=issues) for name, issues in judge_issues],
    )


class TestRichNarrativeAutoRetry:
    """score_judge checks whether the LLM-written rationale (incl. directional
    program-ratio comparisons) matches the data — a nondeterministic prose
    check. When it's the ONLY judge with errors, judge_charity regenerates
    the rich narrative once and re-judges before giving up."""

    def test_retries_and_succeeds_when_only_score_judge_errors(self, monkeypatch):
        responses = [
            _verdict_result(False, [("score", [ValidationIssue(Severity.ERROR, "amal_score_rationale", "backwards")])]),
            _verdict_result(True, []),
        ]

        class SeqOrchestrator:
            def __init__(self, config):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def validate_single(self, charity_dict, context):
                return responses.pop(0)

        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", SeqOrchestrator)
        rich_retry_calls = []
        monkeypatch.setattr(
            rich_phase,
            "generate_rich_for_pipeline",
            lambda ein, eval_repo, force=False: rich_retry_calls.append(ein) or {"success": True, "cost_usd": 0.02},
        )
        repos = _mock_repos(dict(FULL_EVALUATION))

        result = judge_phase.judge_charity(EIN, *repos)

        assert rich_retry_calls == [EIN]
        assert result["success"] is True
        assert result["passed"] is True
        assert result["error_count"] == 0
        assert result["rich_retried"] is True
        assert result["cost_usd"] == 0.02  # retry's rich-generation cost folded into the total

    def test_no_retry_when_other_judges_also_error(self, monkeypatch):
        class OnceOrchestrator:
            def __init__(self, config):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def validate_single(self, charity_dict, context):
                return _verdict_result(
                    False,
                    [
                        ("score", [ValidationIssue(Severity.ERROR, "f", "m")]),
                        ("crawl_quality", [ValidationIssue(Severity.ERROR, "f2", "m2")]),
                    ],
                )

        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", OnceOrchestrator)
        rich_retry_calls = []
        monkeypatch.setattr(
            rich_phase,
            "generate_rich_for_pipeline",
            lambda *a, **kw: rich_retry_calls.append(1) or {"success": True, "cost_usd": 0.02},
        )
        repos = _mock_repos(dict(FULL_EVALUATION))

        result = judge_phase.judge_charity(EIN, *repos)

        assert rich_retry_calls == []
        assert result["error_count"] == 2
        assert "rich_retried" not in result

    def test_retry_is_bounded_to_one_attempt(self, monkeypatch):
        call_count = {"n": 0}

        class AlwaysScoreErrorOrchestrator:
            def __init__(self, config):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def validate_single(self, charity_dict, context):
                call_count["n"] += 1
                return _verdict_result(False, [("score", [ValidationIssue(Severity.ERROR, "f", "m")])])

        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", AlwaysScoreErrorOrchestrator)
        rich_retry_calls = []
        monkeypatch.setattr(
            rich_phase,
            "generate_rich_for_pipeline",
            lambda *a, **kw: rich_retry_calls.append(1) or {"success": True, "cost_usd": 0.02},
        )
        repos = _mock_repos(dict(FULL_EVALUATION))

        result = judge_phase.judge_charity(EIN, *repos)

        assert rich_retry_calls == [1]  # exactly one retry, not a loop
        assert call_count["n"] == 2  # original judge run + one re-judge after retry
        assert result["passed"] is False
        assert result["rich_retried"] is True


class TestMainPersistenceAndExitCode:
    def _patch_environment(self, monkeypatch, eval_repo_cls, judge_result):
        monkeypatch.setattr(judge_phase, "EvaluationRepository", eval_repo_cls)
        monkeypatch.setattr(judge_phase, "CharityDataRepository", Mock)
        monkeypatch.setattr(judge_phase, "RawDataRepository", Mock)
        monkeypatch.setattr(judge_phase, "CharityRepository", Mock)
        monkeypatch.setattr(judge_phase, "PhaseCacheRepository", Mock)
        monkeypatch.setattr(judge_phase, "check_phase_cache", lambda *a, **kw: (True, "forced"))
        monkeypatch.setattr(judge_phase, "update_phase_cache", lambda *a, **kw: [])
        monkeypatch.setattr(judge_phase, "judge_charity", lambda ein, *repos: dict(judge_result))
        monkeypatch.setattr("src.db.dolt_client.dolt.commit", lambda msg, **kw: None)

    def test_main_exits_nonzero_when_any_ein_fails(self, monkeypatch):
        persisted = []

        class FakeEvalRepo:
            def update_judge_result(
                self, ein, judge_score, issues, content_hash=None, error_count=None, warning_count=None
            ):
                persisted.append((ein, judge_score, issues, content_hash, error_count, warning_count))

        self._patch_environment(
            monkeypatch, FakeEvalRepo, {"success": False, "error": "boom", "cost_usd": 0.0}
        )

        exit_code = judge_phase.main(["--ein", EIN])

        assert exit_code == 1
        assert persisted == []

    def test_main_persists_judge_score_on_success(self, monkeypatch):
        persisted = []

        class FakeEvalRepo:
            def update_judge_result(
                self, ein, judge_score, issues, content_hash=None, error_count=None, warning_count=None
            ):
                persisted.append((ein, judge_score, issues, content_hash, error_count, warning_count))

        self._patch_environment(
            monkeypatch,
            FakeEvalRepo,
            {
                "success": True,
                "judge_score": 85,
                "issues": [],
                "passed": True,
                "error_count": 0,
                "warning_count": 3,
                "cost_usd": 0.01,
                "content_hash": "abc123abc123abc1",
            },
        )

        exit_code = judge_phase.main(["--ein", EIN])

        assert exit_code == 0
        assert persisted == [(EIN, 85, [], "abc123abc123abc1", 0, 3)]

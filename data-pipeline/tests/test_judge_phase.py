"""Tests for judge_phase: lens projection completeness + CLI persistence/exit codes."""

from unittest.mock import Mock

import judge_phase
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
    def test_projection_includes_all_lens_fields(self, monkeypatch):
        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", FakeOrchestrator)
        repos = _mock_repos(dict(FULL_EVALUATION))

        result = judge_phase.judge_charity(EIN, *repos)

        assert result["success"] is True
        projected = FakeOrchestrator.captured["evaluation"]
        assert projected["strategic_narrative"] == {"summary": "Strategic summary."}
        assert projected["strategic_score"] == 71
        assert projected["zakat_narrative"] == {"summary": "Zakat summary."}
        assert projected["zakat_score"] == 76
        assert projected["rich_strategic_narrative"] == {"summary": "Rich strategic."}
        assert projected["wallet_tag"] == "ZAKAT-ELIGIBLE"


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
            def update_judge_result(self, ein, judge_score, issues):
                persisted.append((ein, judge_score, issues))

        self._patch_environment(
            monkeypatch, FakeEvalRepo, {"success": False, "error": "boom", "cost_usd": 0.0}
        )

        exit_code = judge_phase.main(["--ein", EIN])

        assert exit_code == 1
        assert persisted == []

    def test_main_persists_judge_score_on_success(self, monkeypatch):
        persisted = []

        class FakeEvalRepo:
            def update_judge_result(self, ein, judge_score, issues):
                persisted.append((ein, judge_score, issues))

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
            },
        )

        exit_code = judge_phase.main(["--ein", EIN])

        assert exit_code == 0
        assert persisted == [(EIN, 85, [])]

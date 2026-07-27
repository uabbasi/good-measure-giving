"""Tests for judge_phase: lens projection completeness + CLI persistence/exit codes."""

from unittest.mock import Mock

import judge_phase
import rich_phase
from src.judges.factual_judge import FactualJudge
from src.judges.schemas.config import JudgeConfig
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
    """Captures the charity_dict (and context) that judge_charity projects."""

    captured: dict = {}
    captured_context: dict = {}

    def __init__(self, config):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def validate_single(self, charity_dict, context):
        FakeOrchestrator.captured = charity_dict
        FakeOrchestrator.captured_context = context
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

    def test_charity_dict_carries_the_narrative_key(self, monkeypatch):
        """score_judge (and factual/citation/zakat judges) read
        output["narrative"] — both in their prompt template's
        '## Narrative Rationale' section and, for score_judge, in the
        deterministic _quick_tone_checks backstop. Without this key the
        prompt renders that section as a literal '{}' and the tone check
        never sees real text."""
        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", FakeOrchestrator)
        repos = _mock_repos(dict(FULL_EVALUATION))

        judge_phase.judge_charity(EIN, *repos)

        assert FakeOrchestrator.captured["narrative"] == {"summary": "Baseline summary."}


class TestFactualQuickCheckInputsWiring:
    """D4c: FactualJudge._quick_checks reads context['metrics'] and
    output['financials'], neither of which judge_charity ever populated
    (verified: it never has). This wires up the two checks that have a
    genuinely independent source — wallet_tag (from charity_data.claims_
    zakat_eligible, written by synthesize.py, a different phase/row/time
    than evaluations.wallet_tag, written by baseline.py) and the program_
    expense_ratio bounds check (a self-contained sanity check, not a
    source-vs-output comparison). amal_score/strategic_score/archetype/
    strategic_dimensions stay unfed — see the "metrics" comment in
    judge_phase.py's judge_charity() or .superpowers/sdd/task-D4c-report.md
    for why.
    """

    def _run_and_capture(self, monkeypatch, evaluation, charity_data):
        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", FakeOrchestrator)
        eval_repo, data_repo, raw_repo, charity_repo = _mock_repos(dict(evaluation))
        data_repo.get.return_value = charity_data
        judge_phase.judge_charity(EIN, eval_repo, data_repo, raw_repo, charity_repo)
        return FakeOrchestrator.captured, FakeOrchestrator.captured_context

    def test_wallet_tag_mismatch_is_caught(self, monkeypatch):
        """Output says ZAKAT-ELIGIBLE; the independently-written source
        (charity_data.claims_zakat_eligible) says False -- a real drift the
        judge should catch."""
        evaluation = {**FULL_EVALUATION, "wallet_tag": "ZAKAT-ELIGIBLE"}
        charity_dict, context = self._run_and_capture(
            monkeypatch, evaluation, {"claims_zakat_eligible": False}
        )

        issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert any("wallet_tag" in i.field for i in errors)

    def test_wallet_tag_match_produces_no_issue(self, monkeypatch):
        """Same output, source now agrees -- must NOT fire (rules out an
        always-firing check)."""
        evaluation = {**FULL_EVALUATION, "wallet_tag": "ZAKAT-ELIGIBLE"}
        charity_dict, context = self._run_and_capture(
            monkeypatch, evaluation, {"claims_zakat_eligible": True}
        )

        issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        assert not [i for i in issues if i.severity == Severity.ERROR and "wallet_tag" in i.field]

    def test_null_claims_zakat_eligible_matches_sadaqah(self, monkeypatch):
        """A charity_data row with claims_zakat_eligible=NULL (never
        determined) must not spuriously mismatch a SADAQAH-ELIGIBLE output --
        mirrors the scorer's own `metrics.zakat_claim_detected or False`
        null-handling (src/scorers/v2_scorers.py)."""
        evaluation = {**FULL_EVALUATION, "wallet_tag": "SADAQAH-ELIGIBLE"}
        charity_dict, context = self._run_and_capture(
            monkeypatch, evaluation, {"claims_zakat_eligible": None}
        )

        issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        assert not [i for i in issues if i.severity == Severity.ERROR and "wallet_tag" in i.field]

    def test_perturbing_only_the_source_changes_the_verdict(self, monkeypatch):
        """Structural guard against a tautology: hold the OUTPUT
        (evaluation.wallet_tag) fixed and change only the SOURCE
        (charity_data.claims_zakat_eligible). If the verdict didn't change,
        context['metrics'] would have been fed from the same object the
        output was derived from."""
        evaluation = {**FULL_EVALUATION, "wallet_tag": "ZAKAT-ELIGIBLE"}

        charity_dict, context = self._run_and_capture(
            monkeypatch, evaluation, {"claims_zakat_eligible": True}
        )
        passing_issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        charity_dict, context = self._run_and_capture(
            monkeypatch, evaluation, {"claims_zakat_eligible": False}
        )
        failing_issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        assert not [i for i in passing_issues if i.severity == Severity.ERROR and "wallet_tag" in i.field]
        assert any(i.severity == Severity.ERROR and "wallet_tag" in i.field for i in failing_issues)

    def test_program_expense_ratio_out_of_bounds_is_caught(self, monkeypatch):
        charity_dict, context = self._run_and_capture(
            monkeypatch, FULL_EVALUATION, {"program_expense_ratio": 1.5}
        )

        issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert any("program_expense_ratio" in i.field for i in errors)

    def test_program_expense_ratio_in_bounds_produces_no_issue(self, monkeypatch):
        charity_dict, context = self._run_and_capture(
            monkeypatch, FULL_EVALUATION, {"program_expense_ratio": 0.82}
        )

        issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        assert not [i for i in issues if i.severity == Severity.ERROR and "program_expense_ratio" in i.field]

    def test_missing_charity_data_row_does_not_crash(self, monkeypatch):
        """charity_data can be None (nullable) -- must use the `or {}` idiom,
        not crash on .get(). And, since there is no source row at all,
        claims_zakat_eligible is unknown -- this must NOT be coalesced into a
        false SADAQAH-ELIGIBLE assertion that then mismatches the real
        ZAKAT-ELIGIBLE output and gates publication on invented data."""
        charity_dict, context = self._run_and_capture(monkeypatch, FULL_EVALUATION, None)

        issues = FactualJudge(JudgeConfig())._quick_checks(charity_dict, context)

        assert isinstance(issues, list)
        assert not [i for i in issues if i.severity == Severity.ERROR and "wallet_tag" in i.field]

    def test_unfed_checks_stay_unfed(self, monkeypatch):
        """amal_score/strategic_score/archetype/strategic_dimensions have no
        genuinely independent source (amal_score) or can never appear in the
        judged evaluation projection at all (the strategic fields -- see
        JUDGE_PROJECTION_FIELDS). Feeding them would either be a tautology or
        inert; context['metrics'] must not carry those keys."""
        _charity_dict, context = self._run_and_capture(
            monkeypatch, FULL_EVALUATION, {"claims_zakat_eligible": True, "program_expense_ratio": 0.5}
        )

        metrics = context["metrics"]
        for unfed_key in ("amal_score", "strategic_score", "archetype", "strategic_dimensions"):
            assert unfed_key not in metrics


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

    def test_failed_rich_retry_rereads_evaluation_and_reports(self, monkeypatch, capsys):
        """A failed retry can NULL the rich narrative; hashing the pre-retry
        evaluation persisted a hash that could never match the stored row."""
        with_rich = dict(FULL_EVALUATION)
        without_rich = {**with_rich, "rich_narrative": None}

        class ScoreErrorOrchestrator:
            def __init__(self, config):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def validate_single(self, charity_dict, context):
                return _verdict_result(False, [("score", [ValidationIssue(Severity.ERROR, "f", "m")])])

        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", ScoreErrorOrchestrator)
        monkeypatch.setattr(
            rich_phase,
            "generate_rich_for_pipeline",
            lambda *a, **kw: {"success": False, "cost_usd": 0.0, "error": "consistency validation failed"},
        )

        eval_repo, data_repo, raw_repo, charity_repo = _mock_repos(with_rich)
        eval_repo.get.side_effect = [with_rich, without_rich]

        result = judge_phase.judge_charity(EIN, eval_repo, data_repo, raw_repo, charity_repo)

        assert result["content_hash"] == judge_phase.compute_judge_content_hash(without_rich), (
            "hash must describe the row as it stands AFTER the retry"
        )
        assert result["rich_retry_failed"]
        assert "retry failed" in capsys.readouterr().out

    def test_failed_rich_retry_cost_survives_into_result(self, monkeypatch):
        """The retry spends LLM money whether or not the regenerated
        narrative ends up passing. Before the fix, `result["cost_usd"]` was
        unconditionally overwritten with only the original judge run's cost
        on the failure path, silently dropping the failed retry's spend."""
        with_rich = dict(FULL_EVALUATION)
        without_rich = {**with_rich, "rich_narrative": None}

        class ScoreErrorOrchestrator:
            def __init__(self, config):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def validate_single(self, charity_dict, context):
                return _verdict_result(False, [("score", [ValidationIssue(Severity.ERROR, "f", "m")])])

        monkeypatch.setattr(judge_phase, "JudgeOrchestrator", ScoreErrorOrchestrator)
        monkeypatch.setattr(
            rich_phase,
            "generate_rich_for_pipeline",
            lambda *a, **kw: {"success": False, "cost_usd": 0.37, "error": "consistency validation failed"},
        )

        eval_repo, data_repo, raw_repo, charity_repo = _mock_repos(with_rich)
        eval_repo.get.side_effect = [with_rich, without_rich]

        result = judge_phase.judge_charity(EIN, eval_repo, data_repo, raw_repo, charity_repo)

        assert result["cost_usd"] == 0.37


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

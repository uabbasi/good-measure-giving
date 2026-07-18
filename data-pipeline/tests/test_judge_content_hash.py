"""Content-bound judge verdicts: canonical projection hash + migration guard + persistence."""

import re
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import judge_phase
from judge_phase import (
    JUDGE_PROJECTION_FIELDS,
    build_judge_projection,
    compute_judge_content_hash,
)

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
    "score_details": {"impact": {"score": 40}, "judge_issues": [{"judge": "old", "severity": "warning"}]},
}


class TestContentHash:
    def test_hash_is_16_hex_chars(self):
        assert re.fullmatch(r"[0-9a-f]{16}", compute_judge_content_hash(FULL_EVALUATION))

    def test_hash_deterministic_across_key_order(self):
        reordered = {
            "score_details": {"judge_issues": [{"judge": "old", "severity": "warning"}], "impact": {"score": 40}},
            "zakat_score": 76,
            "strategic_score": 71,
            "rich_strategic_narrative": {"summary": "Rich strategic."},
            "zakat_narrative": {"summary": "Zakat summary."},
            "strategic_narrative": {"summary": "Strategic summary."},
            "baseline_narrative": {"summary": "Baseline summary."},
            "zakat_classification": "ELIGIBLE",
            "impact_tier": "gold",
            "confidence_tier": "high",
            "wallet_tag": "ZAKAT-ELIGIBLE",
            "amal_score": 82,
        }
        assert compute_judge_content_hash(reordered) == compute_judge_content_hash(FULL_EVALUATION)

    def test_hash_changes_when_judged_content_changes(self):
        base = compute_judge_content_hash(FULL_EVALUATION)

        diff_narr = dict(FULL_EVALUATION, baseline_narrative={"summary": "Different."})
        assert compute_judge_content_hash(diff_narr) != base

        diff_score = dict(FULL_EVALUATION, amal_score=83)
        assert compute_judge_content_hash(diff_score) != base

        diff_zakat = dict(FULL_EVALUATION, zakat_score=77)
        assert compute_judge_content_hash(diff_zakat) != base

    def test_hash_ignores_non_projection_fields(self):
        base = compute_judge_content_hash(FULL_EVALUATION)
        with_extras = dict(
            FULL_EVALUATION,
            judge_score=40,
            state="approved",
            llm_cost_usd=9.9,
            information_density=0.5,
            rubric_version="5.2.0",
            rich_narrative={"x": 1},
            judge_content_hash="deadbeefdeadbeef",
        )
        assert compute_judge_content_hash(with_extras) == base

    def test_hash_ignores_judge_issues_in_score_details(self):
        removed = dict(FULL_EVALUATION, score_details={"impact": {"score": 40}})
        present = dict(FULL_EVALUATION, score_details={"impact": {"score": 40}, "judge_issues": [{"a": 1}]})
        different = dict(FULL_EVALUATION, score_details={"impact": {"score": 40}, "judge_issues": [{"b": 2}]})
        h1 = compute_judge_content_hash(removed)
        h2 = compute_judge_content_hash(present)
        h3 = compute_judge_content_hash(different)
        assert h1 == h2 == h3

    def test_hash_handles_missing_and_none_fields(self):
        empty = compute_judge_content_hash({})
        assert re.fullmatch(r"[0-9a-f]{16}", empty)
        all_none = compute_judge_content_hash({f: None for f in JUDGE_PROJECTION_FIELDS})
        assert empty == all_none

    def test_projection_strips_only_judge_issues(self):
        projection = build_judge_projection(FULL_EVALUATION)
        assert projection["score_details"] == {"impact": {"score": 40}}
        assert set(projection.keys()) == set(JUDGE_PROJECTION_FIELDS)
        assert len(projection) == 12
        # input dict not mutated
        assert "judge_issues" in FULL_EVALUATION["score_details"]


class TestMigrationGuard:
    def _run(self, monkeypatch, count):
        import migrations.add_judge_content_hash as mig

        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            if "information_schema" in sql:
                return {"n": count}
            return None

        commit_mock = Mock()
        monkeypatch.setattr(mig, "execute_query", fake_execute_query)
        monkeypatch.setattr(mig, "dolt", Mock(commit=commit_mock))
        exit_code = mig.main()
        return exit_code, calls, commit_mock

    def test_skips_when_column_exists(self, monkeypatch):
        exit_code, calls, commit_mock = self._run(monkeypatch, count=1)
        assert exit_code == 0
        assert not any("ALTER TABLE" in sql for sql, _, _ in calls)
        commit_mock.assert_not_called()

    def test_adds_column_when_absent(self, monkeypatch):
        exit_code, calls, commit_mock = self._run(monkeypatch, count=0)
        assert exit_code == 0
        alters = [sql for sql, _, _ in calls if "ALTER TABLE" in sql]
        assert len(alters) == 1
        assert "judge_content_hash" in alters[0]
        commit_mock.assert_called_once()
        assert commit_mock.call_args.kwargs["tables"] == ("evaluations",)


class TestUpdateJudgeResultPersistsHash:
    def test_update_judge_result_writes_hash(self, monkeypatch):
        from src.db.repository import EvaluationRepository

        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            return None

        monkeypatch.setattr("src.db.repository.execute_query", fake_execute_query)

        EvaluationRepository().update_judge_result(
            "12-3456789", 85, None, content_hash="a1b2c3d4e5f60718"
        )

        assert len(calls) == 1
        sql, params, _ = calls[0]
        assert "judge_content_hash = %s" in sql
        assert "a1b2c3d4e5f60718" in params

    def test_update_judge_result_defaults_hash_to_null(self, monkeypatch):
        from src.db.repository import EvaluationRepository

        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            return None

        monkeypatch.setattr("src.db.repository.execute_query", fake_execute_query)

        EvaluationRepository().update_judge_result("12-3456789", 85)

        assert len(calls) == 1
        sql, params, _ = calls[0]
        assert "judge_content_hash = %s" in sql
        assert None in params


# Re-export for other test modules / readability
assert judge_phase.compute_judge_content_hash is compute_judge_content_hash

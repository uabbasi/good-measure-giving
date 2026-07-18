"""Option A: deduped-count migration idempotency + update_judge_result persistence."""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCountsMigrationGuard:
    def _run(self, monkeypatch, existing_cols):
        import migrations.add_judge_error_warning_counts as mig

        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            if "information_schema" in sql:
                return [{"cn": c} for c in existing_cols]
            return None

        commit_mock = Mock()
        monkeypatch.setattr(mig, "execute_query", fake_execute_query)
        monkeypatch.setattr(mig, "dolt", Mock(commit=commit_mock))
        return mig.main(), calls, commit_mock

    def test_skips_when_both_columns_exist(self, monkeypatch):
        code, calls, commit_mock = self._run(
            monkeypatch, ["judge_error_count", "judge_warning_count"]
        )
        assert code == 0
        assert not any("ALTER TABLE" in sql for sql, _, _ in calls)
        commit_mock.assert_not_called()

    def test_adds_both_when_absent(self, monkeypatch):
        code, calls, commit_mock = self._run(monkeypatch, [])
        assert code == 0
        alters = [sql for sql, _, _ in calls if "ALTER TABLE" in sql]
        assert len(alters) == 2
        assert any("judge_error_count" in sql for sql in alters)
        assert any("judge_warning_count" in sql for sql in alters)
        commit_mock.assert_called_once()
        assert commit_mock.call_args.kwargs["tables"] == ("evaluations",)

    def test_adds_only_missing_column(self, monkeypatch):
        code, calls, commit_mock = self._run(monkeypatch, ["judge_error_count"])
        assert code == 0
        alters = [sql for sql, _, _ in calls if "ALTER TABLE" in sql]
        assert len(alters) == 1
        assert "judge_warning_count" in alters[0]
        commit_mock.assert_called_once()


class TestUpdateJudgeResultPersistsCounts:
    def _capture(self, monkeypatch):
        from src.db.repository import EvaluationRepository

        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            return None

        monkeypatch.setattr("src.db.repository.execute_query", fake_execute_query)
        return EvaluationRepository(), calls

    def test_writes_both_counts(self, monkeypatch):
        repo, calls = self._capture(monkeypatch)
        repo.update_judge_result(
            "12-3456789", 85, None, content_hash="a1b2c3d4e5f60718", error_count=0, warning_count=7
        )
        assert len(calls) == 1
        sql, params, _ = calls[0]
        assert "judge_error_count = %s" in sql
        assert "judge_warning_count = %s" in sql
        assert 0 in params
        assert 7 in params

    def test_counts_default_to_null(self, monkeypatch):
        repo, calls = self._capture(monkeypatch)
        repo.update_judge_result("12-3456789", 85)
        assert len(calls) == 1
        sql, params, _ = calls[0]
        assert "judge_error_count = %s" in sql
        assert "judge_warning_count = %s" in sql
        # content_hash + error_count + warning_count all default to NULL.
        assert params.count(None) >= 3

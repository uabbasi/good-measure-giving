"""Publish-gate and prune-safety tests for export.py (contract #5)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from export import build_arg_parser, exclusion_reason, partition_by_judge_gate
from src.db.repository import ExportExclusionRepository

DATA_PIPELINE_DIR = Path(__file__).parent.parent


class FakeEvalRepo:
    def __init__(self, scores):
        self._scores = scores

    def get(self, ein):
        if ein not in self._scores:
            return None
        return {"charity_ein": ein, "judge_score": self._scores[ein]}


class TestArgParser:
    def test_defaults(self):
        args = build_arg_parser().parse_args([])
        assert args.judge_threshold == 80
        assert args.no_judge_gate is False
        assert args.prune is False

    def test_prune_conflicts_with_ein(self):
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args(["--ein", "12-3456789", "--prune"])

    def test_prune_allowed_with_charities(self):
        args = build_arg_parser().parse_args(["--charities", "pilot_charities.txt", "--prune"])
        assert args.prune is True


class TestJudgeGate:
    def test_partitions_by_threshold(self):
        repo = FakeEvalRepo({"A": 90, "B": 79, "C": 80})
        kept, excluded = partition_by_judge_gate(["A", "B", "C"], repo, 80)
        assert kept == ["A", "C"]
        assert excluded == [("B", 79)]

    def test_missing_score_fails_closed(self):
        repo = FakeEvalRepo({"A": None})
        kept, excluded = partition_by_judge_gate(["A", "B"], repo, 80)
        assert kept == []
        assert excluded == [("A", None), ("B", None)]


class TestExclusionReason:
    def test_below_threshold(self):
        assert exclusion_reason(42, 80) == "judge_score 42 < threshold 80"

    def test_missing_score_fails_closed(self):
        assert exclusion_reason(None, 80) == "judge_score missing (fails closed, threshold 80)"


class TestExportExclusionRepository:
    def test_record_creates_table_and_inserts(self, monkeypatch):
        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            return None

        monkeypatch.setattr("src.db.repository.execute_query", fake_execute_query)
        monkeypatch.setattr(ExportExclusionRepository, "_table_ensured", False)

        ExportExclusionRepository().record("12-3456789", 42, "judge_score 42 < threshold 80")

        assert any("CREATE TABLE IF NOT EXISTS export_exclusions" in sql for sql, _, _ in calls)
        insert_calls = [c for c in calls if c[0].strip().upper().startswith("INSERT")]
        assert len(insert_calls) == 1
        sql, params, fetch = insert_calls[0]
        assert params == ("12-3456789", 42, "judge_score 42 < threshold 80")
        assert fetch == "none"

    def test_ensure_table_memoized_across_records(self, monkeypatch):
        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            return None

        monkeypatch.setattr("src.db.repository.execute_query", fake_execute_query)
        monkeypatch.setattr(ExportExclusionRepository, "_table_ensured", False)

        ExportExclusionRepository().record("12-3456789", 42, "judge_score 42 < threshold 80")
        ExportExclusionRepository().record("98-7654321", None, "judge_score missing (fails closed, threshold 80)")

        create_calls = [c for c in calls if "CREATE TABLE IF NOT EXISTS export_exclusions" in c[0]]
        assert len(create_calls) == 1
        insert_calls = [c for c in calls if c[0].strip().upper().startswith("INSERT")]
        assert len(insert_calls) == 2


class TestStreamingRunnerCLI:
    def test_prune_conflicts_with_ein_exits_2(self):
        """streaming_runner's parser is built inline in main(); verify the guard via subprocess.

        Argparse rejects the combination before any pipeline work runs.
        """
        result = subprocess.run(
            [sys.executable, str(DATA_PIPELINE_DIR / "streaming_runner.py"), "--ein", "12-3456789", "--prune"],
            capture_output=True,
            text=True,
            cwd=DATA_PIPELINE_DIR,
            timeout=120,
        )
        assert result.returncode == 2
        assert "--prune cannot be combined with --ein" in result.stderr

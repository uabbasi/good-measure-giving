"""Publish-gate, prune-safety, and editorial-queue tests for export.py (Option A).

Publication gate = deduped judge_error_count == 0 AND fresh judge_content_hash.
Warnings never gate; judge_score is an internal metric only.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from export import (
    build_arg_parser,
    build_editorial_queue,
    exclusion_reason,
    partition_by_judge_gate,
)
from judge_phase import compute_judge_content_hash
from src.db.repository import ExportExclusionRepository

DATA_PIPELINE_DIR = Path(__file__).parent.parent


def fresh_row(ein, score=90, error_count=0, warning_count=0):
    """A full evaluations row whose judge_content_hash matches its judged content.

    judge_error_count/judge_warning_count are judge OUTPUT (not in the hashed
    projection), so setting them here never changes the content hash.
    """
    row = {
        "charity_ein": ein,
        "judge_score": score,
        "judge_error_count": error_count,
        "judge_warning_count": warning_count,
        "amal_score": 80,
        "baseline_narrative": {"summary": "s"},
        "score_details": {},
    }
    row["judge_content_hash"] = compute_judge_content_hash(row)
    return row


class FakeEvalRepo:
    def __init__(self, rows):
        self._rows = rows

    def get(self, ein):
        return self._rows.get(ein)


class FakeCharityRepo:
    def __init__(self, charities):
        self._charities = charities

    def get_all(self):
        return self._charities


class TestArgParser:
    def test_defaults(self):
        args = build_arg_parser().parse_args([])
        assert args.no_judge_gate is False
        assert args.prune is False

    def test_judge_threshold_flag_removed(self):
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args(["--judge-threshold", "80"])

    def test_prune_conflicts_with_ein(self):
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args(["--ein", "12-3456789", "--prune"])

    def test_prune_allowed_with_charities(self):
        args = build_arg_parser().parse_args(["--charities", "pilot_charities.txt", "--prune"])
        assert args.prune is True


class TestJudgeGate:
    def test_partitions_by_error_count(self):
        repo = FakeEvalRepo(
            {
                "A": fresh_row("A", error_count=0),
                "B": fresh_row("B", error_count=3),
                "C": fresh_row("C", error_count=0),
            }
        )
        kept, excluded = partition_by_judge_gate(["A", "B", "C"], repo)
        assert kept == ["A", "C"]
        assert excluded == [("B", 90, 3, False)]

    def test_missing_counts_fails_closed(self):
        repo = FakeEvalRepo({"A": {"charity_ein": "A", "judge_score": 90, "judge_error_count": None}})
        kept, excluded = partition_by_judge_gate(["A", "B"], repo)
        assert kept == []
        assert excluded == [("A", 90, None, False), ("B", None, None, False)]

    def test_gate_keeps_fresh_zero_errors(self):
        repo = FakeEvalRepo({"A": fresh_row("A", error_count=0)})
        kept, excluded = partition_by_judge_gate(["A"], repo)
        assert kept == ["A"]
        assert excluded == []

    def test_warnings_never_gate(self):
        repo = FakeEvalRepo({"A": fresh_row("A", error_count=0, warning_count=99)})
        kept, excluded = partition_by_judge_gate(["A"], repo)
        assert kept == ["A"]
        assert excluded == []

    def test_gate_excludes_null_hash_as_stale(self):
        row = fresh_row("A", error_count=0)
        row["judge_content_hash"] = None
        repo = FakeEvalRepo({"A": row})
        kept, excluded = partition_by_judge_gate(["A"], repo)
        assert kept == []
        assert excluded == [("A", 90, 0, True)]

    def test_gate_excludes_mismatched_hash_as_stale(self):
        row = fresh_row("A", error_count=0)
        row["judge_content_hash"] = "0" * 16
        repo = FakeEvalRepo({"A": row})
        kept, excluded = partition_by_judge_gate(["A"], repo)
        assert kept == []
        assert excluded == [("A", 90, 0, True)]

    def test_gate_excludes_mutated_content_as_stale(self):
        row = fresh_row("A", error_count=0)
        row["baseline_narrative"] = {"summary": "MUTATED AFTER JUDGING"}
        repo = FakeEvalRepo({"A": row})
        kept, excluded = partition_by_judge_gate(["A"], repo)
        assert kept == []
        assert excluded == [("A", 90, 0, True)]

    def test_gate_hash_ignores_judge_issues_mutation(self):
        row = fresh_row("A", error_count=0)
        row["score_details"]["judge_issues"] = [{"judge": "x", "severity": "warning"}]
        repo = FakeEvalRepo({"A": row})
        kept, excluded = partition_by_judge_gate(["A"], repo)
        assert kept == ["A"]
        assert excluded == []

    def test_error_check_precedes_stale(self):
        # errors > 0 AND stale hash → blocked on errors (not stale); hash is not even checked.
        row = fresh_row("A", error_count=5)
        row["judge_content_hash"] = None
        repo = FakeEvalRepo({"A": row})
        kept, excluded = partition_by_judge_gate(["A"], repo)
        assert kept == []
        assert excluded == [("A", 90, 5, False)]


class TestExclusionReason:
    def test_errors_blocked(self):
        assert exclusion_reason(3) == "judge errors: 3 (publication blocked)"

    def test_missing_counts_fails_closed(self):
        assert exclusion_reason(None) == "judge counts missing (fails closed)"

    def test_stale_reason(self):
        assert exclusion_reason(0, stale=True) == "judge verdict stale (content changed since judged)"


class TestEditorialQueue:
    def test_sorted_by_warnings_desc_fresh_only(self):
        charity_repo = FakeCharityRepo(
            [
                {"ein": "A", "name": "Alpha"},
                {"ein": "B", "name": "Beta"},
                {"ein": "C", "name": "Gamma"},
                {"ein": "D", "name": "Delta"},
            ]
        )
        rows = {
            "A": fresh_row("A", error_count=0, warning_count=5),
            "B": fresh_row("B", error_count=0, warning_count=12),
            "C": fresh_row("C", error_count=2, warning_count=3),  # errors are still queued
            "D": {"charity_ein": "D", "judge_error_count": None, "judge_warning_count": None},
        }
        rows["A"]["updated_at"] = "2026-07-17T00:00:00"
        eval_repo = FakeEvalRepo(rows)

        queue = build_editorial_queue(charity_repo, eval_repo)

        assert [q["ein"] for q in queue] == ["B", "A", "C"]
        assert queue[0] == {
            "ein": "B",
            "name": "Beta",
            "judge_warning_count": 12,
            "judge_error_count": 0,
            "judge_score": 90,
            "judged_at": None,
        }
        assert queue[1]["judged_at"] == "2026-07-17T00:00:00"

    def test_stale_counts_excluded_from_queue(self):
        charity_repo = FakeCharityRepo([{"ein": "A", "name": "Alpha"}])
        row = fresh_row("A", error_count=0, warning_count=9)
        row["judge_content_hash"] = None  # stale → counts don't describe current content
        eval_repo = FakeEvalRepo({"A": row})

        queue = build_editorial_queue(charity_repo, eval_repo)

        assert queue == []


class TestPhaseArtifactsJudgeHash:
    def test_phase_artifacts_judge_requires_fresh_hash(self):
        from unittest.mock import Mock

        import streaming_runner

        eval_repo = Mock()

        eval_repo.get.return_value = fresh_row("A", 90)
        ok, reason = streaming_runner._phase_artifacts_exist("A", "judge", Mock(), Mock(), eval_repo)
        assert ok is True
        assert reason == ""

        stale_row = fresh_row("A", 90)
        stale_row["judge_content_hash"] = None
        eval_repo.get.return_value = stale_row
        ok, reason = streaming_runner._phase_artifacts_exist("A", "judge", Mock(), Mock(), eval_repo)
        assert ok is False
        assert reason == "evaluations row has stale/missing judge_content_hash"


class TestExportExclusionRepository:
    def test_record_creates_table_and_inserts(self, monkeypatch):
        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            return None

        monkeypatch.setattr("src.db.repository.execute_query", fake_execute_query)
        monkeypatch.setattr(ExportExclusionRepository, "_table_ensured", False)

        ExportExclusionRepository().record("12-3456789", 42, "judge errors: 1 (publication blocked)")

        assert any("CREATE TABLE IF NOT EXISTS export_exclusions" in sql for sql, _, _ in calls)
        insert_calls = [c for c in calls if c[0].strip().upper().startswith("INSERT")]
        assert len(insert_calls) == 1
        sql, params, fetch = insert_calls[0]
        assert params == ("12-3456789", 42, "judge errors: 1 (publication blocked)")
        assert fetch == "none"

    def test_ensure_table_memoized_across_records(self, monkeypatch):
        calls = []

        def fake_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params, fetch))
            return None

        monkeypatch.setattr("src.db.repository.execute_query", fake_execute_query)
        monkeypatch.setattr(ExportExclusionRepository, "_table_ensured", False)

        ExportExclusionRepository().record("12-3456789", 42, "judge errors: 1 (publication blocked)")
        ExportExclusionRepository().record("98-7654321", None, "judge counts missing (fails closed)")

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

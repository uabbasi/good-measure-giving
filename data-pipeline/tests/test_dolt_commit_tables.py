"""Tests for phase-scoped Dolt staging (explicit DOLT_ADD table lists)."""

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.dolt_client import PHASE_TABLES, VALID_TABLES, DoltVersionControl, tables_for_phases


class TestPhaseTables:
    def test_every_mapped_table_is_whitelisted(self):
        for phase, tables in PHASE_TABLES.items():
            for table in tables:
                assert table in VALID_TABLES, f"{phase}: {table!r} not in VALID_TABLES"

    def test_pinned_phase_contracts(self):
        assert tables_for_phases("crawl") == ("raw_scraped_data", "charities", "phase_cache")
        assert tables_for_phases("extract") == ("raw_scraped_data", "phase_cache")
        assert tables_for_phases("synthesize") == ("charity_data", "citations", "phase_cache")
        assert tables_for_phases("baseline") == ("evaluations", "judge_verdicts", "phase_cache")
        assert tables_for_phases("judge") == ("evaluations", "judge_verdicts", "phase_cache")
        assert tables_for_phases("rich") == ("evaluations", "citations", "phase_cache")
        assert tables_for_phases("export") == ("export_exclusions",)

    def test_union_dedupes_preserving_order(self):
        assert tables_for_phases("baseline", "judge") == (
            "evaluations", "judge_verdicts", "phase_cache",
        )

    def test_streaming_union_covers_all_run_phases(self):
        tables = tables_for_phases(
            "crawl", "extract", "discover", "synthesize", "baseline", "rich", "judge"
        )
        assert set(tables) >= {
            "raw_scraped_data", "charities", "charity_data",
            "citations", "evaluations", "judge_verdicts", "phase_cache",
        }
        assert len(tables) == len(set(tables))

    def test_unknown_phase_raises(self):
        with pytest.raises(ValueError, match="Unknown pipeline phase"):
            tables_for_phases("exprot")

    def test_export_exclusions_whitelisted(self):
        assert "export_exclusions" in VALID_TABLES


class FakeDoltCursor:
    """Scripted cursor for dolt.commit(); records every execute call in order."""

    def __init__(self, calls, status_rows):
        self.calls = calls
        self.status_rows = status_rows
        self._last = ""

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self._last = sql

    def fetchall(self):
        if self._last.strip() == "SELECT * FROM dolt_status":
            return list(self.status_rows)
        if "dolt_status" in self._last and "staged = 0" in self._last:
            return []  # everything requested got staged
        return []

    def fetchone(self):
        if "staged = 1" in self._last:
            return {"n": 1}
        if "DOLT_COMMIT" in self._last:
            return {"hash": "fakehash1"}
        return None


def _index_where(calls, predicate):
    for i, call in enumerate(calls):
        if predicate(call):
            return i
    return None


class TestCommitStagesOnlyModifiedTables:
    def test_tables_absent_from_dolt_status_are_not_added(self, monkeypatch):
        """DOLT_ADD on a table missing from dolt_status (unmodified, or lazily
        created and absent, like export_exclusions) must be skipped — Dolt
        errors on adding a nonexistent table."""
        calls = []
        status = [{"table_name": "evaluations", "staged": 0, "status": "modified"}]

        @contextmanager
        def fake_get_cursor():
            yield FakeDoltCursor(calls, status)

        monkeypatch.setattr("src.db.dolt_client.get_cursor", fake_get_cursor)

        vc = DoltVersionControl(author="test", email="test@test")
        commit_hash = vc.commit("msg", tables=("evaluations", "export_exclusions"))

        assert commit_hash == "fakehash1"
        assert ("CALL DOLT_ADD(%s)", ("evaluations",)) in calls
        assert ("CALL DOLT_ADD(%s)", ("export_exclusions",)) not in calls


class TestExportCommitsExclusionsBeforeStamp:
    def test_export_main_commits_exclusions_then_stamps_clean_head(self, monkeypatch, tmp_path):
        """export.py must commit export_exclusions BEFORE head_commit_if_clean(),
        so the provenance stamp sees a clean tree and records a real hash."""
        import export as export_module

        calls = []  # shared, ordered: cursor.execute + execute_query calls
        status = [{"table_name": "export_exclusions", "staged": 0, "status": "new table"}]

        @contextmanager
        def fake_get_cursor():
            yield FakeDoltCursor(calls, status)

        def fake_dolt_execute_query(sql, params=None, fetch="all"):
            calls.append((sql, params))
            if "COUNT(*)" in sql and "dolt_status" in sql:
                return {"n": 0}  # clean at stamp time
            if "HASHOF" in sql:
                return {"commit_hash": "cleanhead1"}
            return []

        monkeypatch.setattr("src.db.dolt_client.get_cursor", fake_get_cursor)
        monkeypatch.setattr("src.db.dolt_client.execute_query", fake_dolt_execute_query)
        # Exclusion audit writes go through the repository layer; absorb them.
        monkeypatch.setattr(
            "src.db.repository.execute_query", lambda sql, params=None, fetch="all": None
        )

        # Neutralize the heavy/irrelevant parts of export.main().
        monkeypatch.setattr(
            export_module, "partition_by_judge_gate",
            lambda eins, repo, thr: (["11-1111111"], [("22-2222222", 50, False)]),
        )
        monkeypatch.setattr(
            export_module, "export_charity",
            lambda *a, **kw: {"success": False, "error": "mocked"},
        )
        monkeypatch.setattr(
            export_module, "export_prompts",
            lambda outdir: {"exported": 0, "output_dir": str(outdir)},
        )
        monkeypatch.setattr(export_module, "_mirror_export_to_public_data", lambda outdir: None)
        monkeypatch.setattr(export_module, "_build_calibration_report", lambda **kw: {})
        monkeypatch.setattr(
            sys, "argv", ["export.py", "--ein", "11-1111111", "--output", str(tmp_path)]
        )

        with pytest.raises(SystemExit):  # mocked export_charity failure exits 1
            export_module.main()

        add_idx = _index_where(
            calls, lambda c: c[0] == "CALL DOLT_ADD(%s)" and c[1] == ("export_exclusions",)
        )
        commit_idx = _index_where(calls, lambda c: "DOLT_COMMIT" in c[0])
        stamp_idx = _index_where(
            calls, lambda c: c[0] == "SELECT COUNT(*) AS n FROM dolt_status"
        )
        assert add_idx is not None, "export never staged export_exclusions"
        assert commit_idx is not None, "export never committed the exclusions"
        assert stamp_idx is not None, "export never ran the clean-check stamp"
        assert add_idx < commit_idx < stamp_idx, (
            f"wrong order: add={add_idx}, commit={commit_idx}, stamp={stamp_idx}"
        )
        # The exclusion commit message names the run's exclusion count.
        assert "1 gate exclusions" in calls[commit_idx][1][1]

        # The stamp saw a clean tree → real hash in charities.json.
        data = json.loads((tmp_path / "charities.json").read_text())
        assert data["source_commit"] == "cleanhead1"

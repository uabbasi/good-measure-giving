"""Tests for phase-scoped Dolt staging (explicit DOLT_ADD table lists)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.dolt_client import PHASE_TABLES, VALID_TABLES, tables_for_phases


class TestPhaseTables:
    def test_every_mapped_table_is_whitelisted(self):
        for phase, tables in PHASE_TABLES.items():
            for table in tables:
                assert table in VALID_TABLES, f"{phase}: {table!r} not in VALID_TABLES"

    def test_pinned_phase_contracts(self):
        assert tables_for_phases("crawl") == ("raw_scraped_data", "charities")
        assert tables_for_phases("synthesize") == ("charity_data", "citations")
        assert tables_for_phases("baseline") == ("evaluations", "judge_verdicts")
        assert tables_for_phases("judge") == ("evaluations", "judge_verdicts")
        assert tables_for_phases("export") == ("export_exclusions",)

    def test_union_dedupes_preserving_order(self):
        assert tables_for_phases("baseline", "judge") == ("evaluations", "judge_verdicts")

    def test_streaming_union_covers_all_run_phases(self):
        tables = tables_for_phases(
            "crawl", "extract", "discover", "synthesize", "baseline", "rich", "judge"
        )
        assert set(tables) >= {
            "raw_scraped_data", "charities", "charity_data",
            "citations", "evaluations", "judge_verdicts",
        }
        assert len(tables) == len(set(tables))

    def test_unknown_phase_raises(self):
        with pytest.raises(ValueError, match="Unknown pipeline phase"):
            tables_for_phases("exprot")

    def test_export_exclusions_whitelisted(self):
        assert "export_exclusions" in VALID_TABLES

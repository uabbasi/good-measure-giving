"""Export display-layer tests: names, causeArea, beneficiary gate, asnaf sanitization."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import export
from export import build_charity_detail, build_charity_summary

EIN = "12-3456789"

EMPTY_OVERRIDES = {"names": {}, "cause_areas": {}, "beneficiaries_suppress": []}


def _charity(name="HELPING HANDS FOR RELIEF AND DEVELOPMENT INC"):
    return {"ein": EIN, "name": name, "mission": "Test mission", "category": None, "website": None}


def _charity_data(**overrides):
    data = {
        "primary_category": "HUMANITARIAN",
        "program_expenses": 1_000_000,
        "beneficiaries_served_annually": None,
        "source_attribution": None,
    }
    data.update(overrides)
    return data


def _evaluation(**overrides):
    evaluation = {
        "amal_score": 70,
        "wallet_tag": "SADAQAH-ELIGIBLE",
        "baseline_narrative": {"headline": "Test headline"},
        "score_details": {},
        "confidence_tier": "HIGH",
    }
    evaluation.update(overrides)
    return evaluation


@pytest.fixture
def empty_overrides(monkeypatch):
    monkeypatch.setattr(export, "_CURATION_OVERRIDES", dict(EMPTY_OVERRIDES), raising=False)


class TestDisplayName:
    def test_summary_detail_and_amal_agree_on_title_cased_name(self, empty_overrides):
        summary = build_charity_summary(_charity(), _charity_data(), _evaluation())
        detail = build_charity_detail(_charity(), _charity_data(), _evaluation(), {})
        assert summary["name"] == "Helping Hands for Relief and Development Inc"
        assert detail["name"] == summary["name"]
        assert detail["amalEvaluation"]["charity_name"] == summary["name"]

    def test_mixed_case_name_passes_through_unchanged(self, empty_overrides):
        summary = build_charity_summary(
            _charity(name="Helping Hand for Relief and Development"), _charity_data(), _evaluation()
        )
        assert summary["name"] == "Helping Hand for Relief and Development"

    def test_name_override_wins(self, monkeypatch):
        monkeypatch.setattr(
            export,
            "_CURATION_OVERRIDES",
            {"names": {EIN: "Curated Name"}, "cause_areas": {}, "beneficiaries_suppress": []},
            raising=False,
        )
        summary = build_charity_summary(_charity(), _charity_data(), _evaluation())
        detail = build_charity_detail(_charity(), _charity_data(), _evaluation(), {})
        assert summary["name"] == "Curated Name"
        assert detail["name"] == "Curated Name"


class TestCurationLoader:
    def test_missing_file_yields_empty_overlay(self, tmp_path, monkeypatch):
        monkeypatch.setattr(export, "CURATION_OVERRIDES_FILE", tmp_path / "nope.yaml", raising=False)
        assert export.load_curation_overrides() == EMPTY_OVERRIDES

    def test_committed_file_loads_with_all_keys(self):
        overlay = export.load_curation_overrides()
        assert set(overlay) == {"names", "cause_areas", "beneficiaries_suppress"}
        assert overlay["cause_areas"].get("13-1760110") == "HUMANITARIAN"

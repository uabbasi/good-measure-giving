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


class TestCauseArea:
    def test_derived_from_primary_category(self, empty_overrides):
        summary = build_charity_summary(_charity(), _charity_data(primary_category="HUMANITARIAN"), _evaluation())
        assert summary["causeArea"] == "HUMANITARIAN"

    def test_extreme_poverty_refinement_from_narrative(self, empty_overrides):
        evaluation = _evaluation(
            rich_narrative={"headline": "x", "donor_fit_matrix": {"cause_area": "EXTREME_POVERTY"}}
        )
        summary = build_charity_summary(_charity(), _charity_data(primary_category="HUMANITARIAN"), evaluation)
        assert summary["causeArea"] == "EXTREME_POVERTY"

    def test_unknown_category_maps_to_general(self, empty_overrides):
        summary = build_charity_summary(_charity(), _charity_data(primary_category=None), _evaluation())
        assert summary["causeArea"] == "GENERAL"

    def test_cause_area_override_wins(self, monkeypatch):
        monkeypatch.setattr(
            export,
            "_CURATION_OVERRIDES",
            {"names": {}, "cause_areas": {EIN: "EDUCATION"}, "beneficiaries_suppress": []},
            raising=False,
        )
        summary = build_charity_summary(_charity(), _charity_data(primary_category="HUMANITARIAN"), _evaluation())
        assert summary["causeArea"] == "EDUCATION"

    def test_legacy_cause_area_overrides_dict_deleted(self):
        assert not hasattr(export, "_CAUSE_AREA_OVERRIDES")


CITED_ATTR = {
    "beneficiaries_served_annually": {
        "source_url": "https://example.org/impact",
        "source_name": "Charity Website",
        "source_path": "website_profile.impact_metrics.metrics.people_served",
    }
}


class TestBeneficiaryGate:
    def test_cited_and_plausible_is_cited(self):
        conf = export._derive_beneficiary_confidence(10_000, CITED_ATTR, _charity_data())
        assert conf == "cited"

    def test_uncited_is_unverified(self):
        assert export._derive_beneficiary_confidence(10_000, {}, _charity_data()) == "unverified"

    def test_blacklisted_source_path_needs_review(self):
        attribution = {
            "beneficiaries_served_annually": {
                "source_url": "https://example.org/impact",
                "source_path": "website_profile.impact_metrics.metrics.meals_served_cumulative",
            }
        }
        assert export._derive_beneficiary_confidence(10_000, attribution, _charity_data()) == "needs_review"

    def test_year_suffixed_source_path_needs_review(self):
        attribution = {
            "beneficiaries_served_annually": {
                "source_url": "https://example.org/impact",
                "source_path": "website_profile.impact_metrics.metrics.people_reached_2023",
            }
        }
        assert export._derive_beneficiary_confidence(10_000, attribution, _charity_data()) == "needs_review"

    def test_over_10k_dollars_per_beneficiary_needs_review(self):
        # $1M program expenses / 50 beneficiaries = $20k/beneficiary
        conf = export._derive_beneficiary_confidence(50, CITED_ATTR, _charity_data(program_expenses=1_000_000))
        assert conf == "needs_review"


class TestBeneficiaryPublication:
    def test_non_cited_count_nulled_in_index_and_detail(self, empty_overrides):
        data = _charity_data(beneficiaries_served_annually=10_000, source_attribution={})
        summary = build_charity_summary(_charity(), data, _evaluation())
        detail = build_charity_detail(_charity(), data, _evaluation(), {})
        assert summary["beneficiariesConfidence"] == "unverified"
        assert summary["beneficiariesServedAnnually"] is None
        assert detail["beneficiariesConfidence"] == "unverified"
        assert detail["beneficiariesServedAnnually"] is None
        assert summary["beneficiariesExcludedFromScoring"] is True

    def test_cited_count_published(self, empty_overrides):
        data = _charity_data(beneficiaries_served_annually=10_000, source_attribution=CITED_ATTR)
        summary = build_charity_summary(_charity(), data, _evaluation())
        assert summary["beneficiariesConfidence"] == "cited"
        assert summary["beneficiariesServedAnnually"] == 10_000
        assert summary["beneficiariesExcludedFromScoring"] is False

    def test_suppress_overlay_nulls_even_cited(self, monkeypatch):
        monkeypatch.setattr(
            export,
            "_CURATION_OVERRIDES",
            {"names": {}, "cause_areas": {}, "beneficiaries_suppress": [EIN]},
            raising=False,
        )
        data = _charity_data(beneficiaries_served_annually=10_000, source_attribution=CITED_ATTR)
        summary = build_charity_summary(_charity(), data, _evaluation())
        detail = build_charity_detail(_charity(), data, _evaluation(), {})
        assert summary["beneficiariesServedAnnually"] is None
        assert detail["beneficiariesServedAnnually"] is None
        assert summary["beneficiariesConfidence"] == "cited"

    def test_detail_source_present_when_cited(self, empty_overrides):
        data = _charity_data(beneficiaries_served_annually=10_000, source_attribution=CITED_ATTR)
        detail = build_charity_detail(_charity(), data, _evaluation(), {})
        assert detail["beneficiariesServedAnnually"] == 10_000
        assert detail["beneficiariesSource"] is not None

    def test_detail_source_suppressed_when_count_gated(self, empty_overrides):
        # cited citation present but $20k/beneficiary -> needs_review -> count AND source nulled
        data = _charity_data(
            beneficiaries_served_annually=50, program_expenses=1_000_000, source_attribution=CITED_ATTR
        )
        detail = build_charity_detail(_charity(), data, _evaluation(), {})
        assert detail["beneficiariesConfidence"] == "needs_review"
        assert detail["beneficiariesServedAnnually"] is None
        assert detail["beneficiariesSource"] is None

    def test_detail_source_suppressed_when_overlay_suppresses(self, monkeypatch):
        monkeypatch.setattr(
            export,
            "_CURATION_OVERRIDES",
            {"names": {}, "cause_areas": {}, "beneficiaries_suppress": [EIN]},
            raising=False,
        )
        data = _charity_data(beneficiaries_served_annually=10_000, source_attribution=CITED_ATTR)
        detail = build_charity_detail(_charity(), data, _evaluation(), {})
        assert detail["beneficiariesServedAnnually"] is None
        assert detail["beneficiariesSource"] is None

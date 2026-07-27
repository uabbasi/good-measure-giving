"""Tests for export.py awards building logic."""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from export import _build_awards, EXCLUDED_BEACONS, run_export_quality_check


class TestBuildAwards:
    """Tests for _build_awards function."""

    def test_no_awards_when_all_empty(self):
        """Should return None when no awards data exists."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={},
            candid_profile={},
            bbb_profile={},
            cn_is_rated=False
        )
        assert result is None

    def test_no_cn_beacons_when_not_rated(self):
        """CN beacons should be excluded when cn_is_rated is False."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": ["Give with Confidence", "Four Star"]},
            candid_profile={},
            bbb_profile={},
            cn_is_rated=False
        )
        # Should return None since CN beacons are filtered out
        assert result is None

    def test_cn_beacons_included_when_rated(self):
        """CN beacons should be included when cn_is_rated is True."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": ["Give with Confidence"]},
            candid_profile={},
            bbb_profile={},
            cn_is_rated=True
        )
        assert result is not None
        assert result["cnBeacons"] == ["Give with Confidence"]

    def test_profile_managed_excluded(self):
        """Profile Managed beacon should be filtered out."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": ["Give with Confidence", "Profile Managed"]},
            candid_profile={},
            bbb_profile={},
            cn_is_rated=True
        )
        assert result is not None
        assert "Profile Managed" not in result["cnBeacons"]
        assert "Give with Confidence" in result["cnBeacons"]

    def test_star_rating_added_when_3_or_higher(self):
        """Star rating should be added as beacon when >= 3."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": [], "star_rating": 4},
            candid_profile={},
            bbb_profile={},
            cn_is_rated=True
        )
        assert result is not None
        assert "4-Star Rating" in result["cnBeacons"]

    def test_star_rating_not_added_when_below_4(self):
        """Star rating below 4 should not be added."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": ["Give with Confidence"], "star_rating": 3},
            candid_profile={},
            bbb_profile={},
            cn_is_rated=True
        )
        assert result is not None
        assert "3-Star Rating" not in result["cnBeacons"]

    def test_star_rating_not_added_when_not_rated(self):
        """Star rating should not be added when cn_is_rated is False."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": [], "star_rating": 4},
            candid_profile={},
            bbb_profile={},
            cn_is_rated=False
        )
        # Should return None since all CN data is filtered
        assert result is None

    def test_candid_seal_included(self):
        """Candid transparency seal should be included."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={},
            candid_profile={"candid_seal": "gold"},
            bbb_profile={},
            cn_is_rated=False
        )
        assert result is not None
        assert result["candidSeal"] == "Gold"

    def test_candid_seal_independent_of_cn_rating(self):
        """Candid seal should show regardless of cn_is_rated."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": ["Give with Confidence"]},
            candid_profile={"candid_seal": "platinum"},
            bbb_profile={},
            cn_is_rated=False
        )
        assert result is not None
        # CN beacons filtered out, but Candid seal remains
        assert result["cnBeacons"] is None
        assert result["candidSeal"] == "Platinum"

    def test_bbb_meets_standards(self):
        """BBB Meets Standards should be included."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={},
            candid_profile={},
            bbb_profile={"meets_standards": True},
            cn_is_rated=False
        )
        assert result is not None
        assert result["bbbStatus"] == "Meets Standards"

    def test_bbb_does_not_meet_standards_excluded(self):
        """BBB that doesn't meet standards should not show."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={},
            candid_profile={},
            bbb_profile={"meets_standards": False},
            cn_is_rated=False
        )
        # Should return None since BBB doesn't meet standards
        assert result is None

    def test_bbb_none_profile(self):
        """Should handle None bbb_profile gracefully."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={},
            candid_profile={},
            bbb_profile=None,
            cn_is_rated=False
        )
        assert result is None

    def test_all_awards_combined(self):
        """All award types should be combined correctly."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": ["Give with Confidence"], "star_rating": 4},
            candid_profile={"candid_seal": "gold"},
            bbb_profile={"meets_standards": True},
            cn_is_rated=True
        )
        assert result is not None
        assert "Give with Confidence" in result["cnBeacons"]
        assert "4-Star Rating" in result["cnBeacons"]
        assert result["candidSeal"] == "Gold"
        assert result["bbbStatus"] == "Meets Standards"

    def test_empty_beacons_list_returns_none_for_cn(self):
        """Empty beacons list should result in None for cnBeacons."""
        result = _build_awards(
            ein="12-3456789",
            cn_profile={"beacons": []},
            candid_profile={"candid_seal": "silver"},
            bbb_profile={},
            cn_is_rated=True
        )
        assert result is not None
        assert result["cnBeacons"] is None
        assert result["candidSeal"] == "Silver"


class TestExcludedBeacons:
    """Tests for EXCLUDED_BEACONS constant."""

    def test_profile_managed_in_excluded(self):
        """Profile Managed should be in excluded beacons."""
        assert "Profile Managed" in EXCLUDED_BEACONS


def test_run_export_quality_check_fails_closed_when_judge_crashes(monkeypatch):
    class ExplodingJudge:
        def __init__(self, _config):
            pass

        def validate(self, _summary, _context):
            raise RuntimeError("boom")

    monkeypatch.setattr("export.ExportQualityJudge", ExplodingJudge)

    passed, issues = run_export_quality_check({"ein": "12-3456789"})

    assert passed is False
    assert issues
    assert issues[0]["severity"] == "error"
    assert issues[0]["field"] == "judge_execution"


class TestPruneOrphanedSourceAttribution:
    """Source attribution must never outlive the value it describes.

    Income-statement fields are elected from ONE fiscal-year-coherent source
    (charity_metrics_aggregator._INCOME_STMT_FIELDS). When ProPublica wins that
    election and has no value for a field, a Charity Navigator attribution
    written earlier survives while the value it describes is nulled — so the
    export publishes provenance ("Charity Navigator said 0") for a number that
    is absent from the file. 35 live charities carried exactly this for
    fundraising_expenses.
    """

    def test_drops_attribution_when_elected_value_is_none(self):
        from export import _prune_orphaned_source_attribution
        attribution = {
            "fundraising_expenses": {"source_name": "Charity Navigator", "value": 0},
            "total_revenue": {"source_name": "ProPublica", "value": 141261},
        }
        charity_data = {"fundraising_expenses": None, "total_revenue": 141261}
        result = _prune_orphaned_source_attribution(attribution, charity_data)
        assert result == {
            "total_revenue": {"source_name": "ProPublica", "value": 141261}
        }

    def test_keeps_attribution_for_a_surviving_zero(self):
        """A real elected 0 is data, not absence — the guard must test None, not falsiness."""
        from export import _prune_orphaned_source_attribution
        attribution = {"fundraising_expenses": {"source_name": "ProPublica", "value": 0}}
        charity_data = {"fundraising_expenses": 0}
        result = _prune_orphaned_source_attribution(attribution, charity_data)
        assert result == attribution

    def test_keeps_attribution_keys_that_are_not_charity_data_fields(self):
        """candid_seal / claims_zakat_eligible are not metrics keys — never prune them."""
        from export import _prune_orphaned_source_attribution
        attribution = {
            "candid_seal": {"source_name": "Candid", "value": "platinum"},
            "claims_zakat_eligible": {"source_name": "Charity Website", "value": True},
        }
        charity_data = {"total_revenue": 500}
        result = _prune_orphaned_source_attribution(attribution, charity_data)
        assert result == attribution

    def test_passes_through_non_dict_inputs_unchanged(self):
        from export import _prune_orphaned_source_attribution
        assert _prune_orphaned_source_attribution(None, {"a": 1}) is None
        attribution = {"total_revenue": {"value": 1}}
        assert _prune_orphaned_source_attribution(attribution, None) == attribution

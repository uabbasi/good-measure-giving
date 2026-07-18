"""Tests for export.py beneficiary publish gate (contract #4).

The gate runs on the ORIGINAL source_attribution (pre URL-normalization) and
publishes a count only when confidence == 'cited'.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports (convention from tests/test_export.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

from export import (
    _beneficiary_cost_exceeds_upper_bound,
    _beneficiary_source_path_is_suspect,
    _derive_beneficiary_confidence,
    _public_beneficiary_fields,
)


def _attr(
    source_path="website_profile.impact_metrics.metrics.people_served_annually",
    source_url="https://example.org/annual-report",
):
    return {
        "beneficiaries_served_annually": {
            "method": "pattern_match",
            "source_name": "Charity Website",
            "source_path": source_path,
            "source_url": source_url,
        }
    }


class TestDeriveBeneficiaryConfidence:
    def test_healthy_cited_plausible_is_cited(self):
        charity_data = {"program_expenses": 100_000}
        assert _derive_beneficiary_confidence(1_000, _attr(), charity_data) == "cited"

    def test_upper_bound_unrwa_case_needs_review(self):
        # UNRWA shape: 100 beneficiaries vs $46.6M program spend -> $466k/beneficiary
        charity_data = {"program_expenses": 46_600_000}
        assert _derive_beneficiary_confidence(100, _attr(), charity_data) == "needs_review"

    def test_semantic_blacklist_bloom_case_needs_review(self):
        # Bloom shape: source_path names a dollar figure, not a headcount
        attr = _attr(
            source_path="website_profile.impact_metrics.metrics.orphanage_infrastructure_value_added_usd"
        )
        charity_data = {"program_expenses": 2_000_000}
        assert _derive_beneficiary_confidence(1_500_000, attr, charity_data) == "needs_review"

    def test_year_suffix_source_path_needs_review(self):
        attr = _attr(source_path="website_profile.impact_metrics.metrics.scholarship_beneficiaries_2021")
        charity_data = {"program_expenses": 500_000}
        assert _derive_beneficiary_confidence(1_000, attr, charity_data) == "needs_review"

    def test_cumulative_source_path_needs_review(self):
        attr = _attr(source_path="website_profile.impact_metrics.metrics.students_impacted_to_date")
        charity_data = {"program_expenses": 500_000}
        assert _derive_beneficiary_confidence(1_000, attr, charity_data) == "needs_review"

    def test_uncited_is_unverified(self):
        attr = {"beneficiaries_served_annually": {"source_url": None, "source_name": "Charity Website"}}
        assert _derive_beneficiary_confidence(1_000, attr, {"program_expenses": 100_000}) == "unverified"

    def test_missing_attribution_is_unverified(self):
        assert _derive_beneficiary_confidence(1_000, None, {"program_expenses": 100_000}) == "unverified"

    def test_grounding_redirect_url_still_counts_as_citation(self):
        # Contract: gate on the ORIGINAL URL; redirect URLs are real citations.
        attr = _attr(source_url="https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc")
        assert _derive_beneficiary_confidence(1_000, attr, {"program_expenses": 100_000}) == "cited"

    def test_no_count_is_none(self):
        assert _derive_beneficiary_confidence(None, _attr(), {}) is None


class TestGateHelpers:
    def test_suspect_path_regex_matches_dollar_paths(self):
        assert _beneficiary_source_path_is_suspect(
            _attr(source_path="website_profile.impact_metrics.metrics.value_added_usd")
        )

    def test_clean_path_not_suspect(self):
        assert not _beneficiary_source_path_is_suspect(_attr())

    def test_upper_bound_trips_above_10k_per_beneficiary(self):
        assert _beneficiary_cost_exceeds_upper_bound(100, {"program_expenses": 46_600_000})

    def test_upper_bound_ok_below_10k_per_beneficiary(self):
        assert not _beneficiary_cost_exceeds_upper_bound(1_000, {"program_expenses": 100_000})

    def test_upper_bound_no_expenses_data_passes(self):
        assert not _beneficiary_cost_exceeds_upper_bound(1_000, {})


class TestPublicBeneficiaryFields:
    def test_cited_count_is_published(self):
        charity_data = {
            "beneficiaries_served_annually": 1_000,
            "program_expenses": 100_000,
            "source_attribution": _attr(),
        }
        assert _public_beneficiary_fields(charity_data) == (1_000, "cited", False)

    def test_needs_review_count_is_nulled_but_confidence_kept(self):
        charity_data = {
            "beneficiaries_served_annually": 100,
            "program_expenses": 46_600_000,
            "source_attribution": _attr(),
        }
        assert _public_beneficiary_fields(charity_data) == (None, "needs_review", True)

    def test_unverified_count_is_nulled(self):
        charity_data = {
            "beneficiaries_served_annually": 5_000,
            "program_expenses": 1_000_000,
            "source_attribution": {},
        }
        assert _public_beneficiary_fields(charity_data) == (None, "unverified", True)

    def test_none_charity_data(self):
        assert _public_beneficiary_fields(None) == (None, None, False)

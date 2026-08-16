"""IRS Form 990 Part VI/VII wins on board size and populates governance
policy fields, per src/utils/source_trust.py's "board" ranking: the org's own
structured filing over Charity Navigator's regex-scraped page or Candid's
whitespace-split list parser (both already documented there as unreliable).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

EIN = "13-1685039"

GOVERNANCE_PROFILE = {
    "name": "SAMPLE CHARITY",
    "ein": EIN,
    "voting_board_members": 25,
    "independent_voting_board_members": 24,
    "has_conflict_of_interest_policy": True,
    "has_whistleblower_policy": True,
    "has_document_retention_policy": True,
    "form_990_provided_to_governing_body": True,
    "material_diversion_or_misuse": False,
    "family_or_business_relationships": False,
    "officers": [
        {"name": "CEO", "reportable_comp_from_org": 501805.0},
        {"name": "BOARD MEMBER", "reportable_comp_from_org": 0.0},
    ],
}


def _aggregate(cn=None, candid=None, governance=None):
    return CharityMetricsAggregator.aggregate(
        charity_id=0,
        ein=EIN,
        cn_profile=cn,
        candid_profile=candid,
        governance_profile=governance,
    )


class TestIRSWinsBoardSize:
    def test_irs_wins_over_a_disagreeing_charity_navigator_figure(self):
        metrics = _aggregate(cn={"board_size": 7}, governance=GOVERNANCE_PROFILE)
        assert metrics.board_size == 25

    def test_falls_back_to_max_across_sources_without_an_irs_figure(self):
        metrics = _aggregate(cn={"board_size": 7}, candid={"board_size": 5})
        assert metrics.board_size == 7

    def test_irs_independent_count_wins_over_candid(self):
        metrics = _aggregate(candid={"independent_board_members": 3}, governance=GOVERNANCE_PROFILE)
        assert metrics.independent_board_members == 24


class TestGovernancePolicyFields:
    def test_policy_flags_populated_from_irs(self):
        metrics = _aggregate(governance=GOVERNANCE_PROFILE)
        assert metrics.has_conflict_of_interest_policy is True
        assert metrics.has_whistleblower_policy is True
        assert metrics.has_document_retention_policy is True
        assert metrics.board_reviewed_990_before_filing is True
        assert metrics.material_diversion_of_assets_reported is False
        assert metrics.family_business_relationships_among_officers is False

    def test_top_officer_compensation_is_the_max_across_officers(self):
        metrics = _aggregate(governance=GOVERNANCE_PROFILE)
        assert metrics.top_officer_reported_compensation == 501805.0

    def test_no_governance_profile_leaves_fields_none(self):
        metrics = _aggregate(cn={"board_size": 7})
        assert metrics.has_conflict_of_interest_policy is None
        assert metrics.has_whistleblower_policy is None
        assert metrics.material_diversion_of_assets_reported is None
        assert metrics.top_officer_reported_compensation is None

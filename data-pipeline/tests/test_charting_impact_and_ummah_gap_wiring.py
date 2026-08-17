"""Candid's Charting Impact framework and the website extractor's
ummah_gap_data.gap_evidence field were both extracted (real LLM/scrape cost
paid) and then never consumed by the aggregator or scorer, despite the
website extractor's own prompt labeling ummah_gap_data "CRITICAL... for
scoring". Confirmed on real data: 19 charities had Charting Impact data but
has_theory_of_change read False; 40 had it but has_outcome_methodology read
False; 80 charities had real gap_evidence text sitting unused.

candid_profile.get("has_theory_of_change") was ALSO a dead check the whole
time -- the Candid collector (src/collectors/candid_beautifulsoup.py) never
emits a key by that literal name, only charting_impact_goal /
charting_impact_strategies / has_charting_impact.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator  # noqa: E402
from src.scorers.v2_scorers import AlignmentScorer  # noqa: E402

EIN = "13-1685039"


def _aggregate(candid=None, website=None):
    return CharityMetricsAggregator.aggregate(
        charity_id=0,
        ein=EIN,
        candid_profile=candid,
        website_profile=website,
    )


class TestCandidChartingImpactFeedsTheoryOfChange:
    def test_charting_impact_goal_sets_has_theory_of_change(self):
        metrics = _aggregate(candid={"charting_impact_goal": "Eliminate malaria by 2030 via bed nets."})
        assert metrics.has_theory_of_change is True
        assert metrics.theory_of_change == "Eliminate malaria by 2030 via bed nets."

    def test_charting_impact_strategies_alone_also_counts(self):
        metrics = _aggregate(candid={"charting_impact_strategies": "Distribute nets through local health clinics."})
        assert metrics.has_theory_of_change is True

    def test_candid_wins_over_website_when_both_present(self):
        metrics = _aggregate(
            candid={"charting_impact_goal": "Candid's stated goal."},
            website={"theory_of_change": "Website's guess at a theory of change."},
        )
        assert metrics.theory_of_change == "Candid's stated goal."

    def test_falls_back_to_website_without_charting_impact(self):
        metrics = _aggregate(website={"theory_of_change": "Website-sourced theory of change."})
        assert metrics.has_theory_of_change is True
        assert metrics.theory_of_change == "Website-sourced theory of change."

    def test_the_old_dead_key_never_worked_and_still_does_nothing(self):
        """Regression guard: candid_profile["has_theory_of_change"] is not a
        key the real collector ever emits -- proves the fix reads the real
        charting_impact_* fields, not a key that happens to be named right."""
        metrics = _aggregate(candid={"has_theory_of_change": True})
        assert metrics.has_theory_of_change is False


class TestCandidChartingImpactFeedsOutcomeMethodology:
    def test_has_charting_impact_sets_has_outcome_methodology(self):
        metrics = _aggregate(candid={"has_charting_impact": True})
        assert metrics.has_outcome_methodology is True

    def test_absent_charting_impact_does_not_set_it(self):
        metrics = _aggregate(candid={"has_charting_impact": False})
        assert metrics.has_outcome_methodology is None


class TestUmmahGapEvidenceReachesMetrics:
    def test_gap_evidence_populates_the_dedicated_field(self):
        metrics = _aggregate(
            website={"ummah_gap_data": {"gap_evidence": "Only 3 Islamic food banks serve 150K Muslims in Detroit."}}
        )
        assert metrics.underserved_gap_evidence == "Only 3 Islamic food banks serve 150K Muslims in Detroit."

    def test_gap_evidence_is_captured_even_when_beneficiary_count_already_known(self):
        """Regression guard: gap_evidence must not be coupled to the
        beneficiary-count resolution's 'still missing' gate."""
        metrics = _aggregate(
            website={
                "beneficiaries_served": 5000,
                "ummah_gap_data": {"gap_evidence": "Real gap evidence text."},
            }
        )
        assert metrics.beneficiaries_served_annually == 5000
        assert metrics.underserved_gap_evidence == "Real gap evidence text."

    def test_no_gap_evidence_stays_none(self):
        metrics = _aggregate(website={"ummah_gap_data": {}})
        assert metrics.underserved_gap_evidence is None


class TestUnderservedGapEvidenceScoresDirectly:
    def test_gap_evidence_alone_triggers_underserved_populations_credit(self):
        metrics = _aggregate(
            website={"ummah_gap_data": {"gap_evidence": "Only 3 Islamic food banks serve 150K Muslims."}}
        )
        # No mission/programs text at all -- the keyword scan has nothing to
        # match. gap_evidence must still carry the +3 on its own.
        pts, evidence = AlignmentScorer()._score_underserved_space(metrics)
        assert "Serves underserved populations (+3)" in evidence

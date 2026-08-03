"""The recorded divergence has to survive the trip to the exported file.

Picking a canonical source silently would leave a donor unable to reconcile our
figure against one they can look up themselves. financial_source_discrepancies
rides metrics_json into keyConcerns; these assert the three shapes render and
that nothing else in the concern pipeline chokes on them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from export import _build_key_concerns


def _concerns(discrepancies):
    return _build_key_concerns({}, {"metrics_json": {"financial_source_discrepancies": discrepancies}})


class TestSameYearDisagreement:
    ENTRY = {
        "field": "total_expenses", "fiscal_year": 2023,
        "canonical_source": "propublica", "canonical_value": 102250,
        "other_source": "charity_navigator", "other_value": 900000,
        "reason": "same_fiscal_year_disagreement",
    }

    def test_both_figures_reach_the_reader(self):
        c = _concerns([self.ENTRY])
        assert len(c) == 1
        assert "102,250" in c[0]["detail"] and "900,000" in c[0]["detail"]

    def test_it_says_which_one_we_publish(self):
        c = _concerns([self.ENTRY])
        assert "Form 990" in c[0]["headline"] or "filing" in c[0]["detail"]

    def test_a_non_numeric_pair_does_not_crash_the_export(self):
        entry = dict(self.ENTRY, canonical_value=None, other_value=None)
        c = _concerns([entry])
        assert len(c) == 1 and c[0]["detail"]


class TestStaleAlternate:
    def test_the_missing_breakdown_names_both_years(self):
        c = _concerns([{
            "field": "income_statement", "fiscal_year": 2023,
            "canonical_source": "propublica", "other_source": "charity_navigator",
            "other_fiscal_year": 2019, "reason": "alternate_source_is_staler",
        }])
        assert len(c) == 1
        assert "2023" in c[0]["headline"] and "2019" in c[0]["detail"]


class TestWorkingCapitalYearGap:
    def test_it_explains_why_the_reserves_figure_will_not_divide_out(self):
        c = _concerns([{
            "field": "working_capital_months", "fiscal_year": 2023,
            "canonical_source": "propublica", "canonical_value": 4.6,
            "other_source": "charity_navigator", "other_fiscal_year": 2024,
            "reason": "derived_from_a_different_filing_year",
        }])
        assert len(c) == 1
        assert "2023" in c[0]["headline"] and "2024" in c[0]["headline"]


class TestScope:
    def test_an_unrecognized_reason_is_not_invented_into_a_concern(self):
        assert _concerns([{"reason": "something_new", "field": "x"}]) == []

    def test_junk_entries_are_skipped_rather_than_raising(self):
        assert _concerns(["not a dict", None]) == []

    def test_no_discrepancies_adds_nothing(self):
        assert _concerns([]) == []

"""Tests for surfacing the cash-adjusted Program Ratio to the rich-narrative
prompt: for GIK-heavy charities (e.g. UMR, 27-3175543) the score is computed
from a cash-adjusted ratio the narrative never saw, so it kept citing the raw
filed ratio as "high" while the score used a different, lower number —
tripping score_judge's rationale-consistency check every time. The narrative
prompt must be told which ratio actually drove the score.
"""

from types import SimpleNamespace

from src.services.rich_narrative_generator import RichNarrativeGenerator

EIN = "27-3175543"


def _generator():
    return object.__new__(RichNarrativeGenerator)


def _financials(program_expense_ratio=0.83, total_revenue=149_888_609):
    return SimpleNamespace(
        total_revenue=total_revenue,
        program_expense_ratio=program_expense_ratio,
    )


class _FakeBundle:
    """charity_bundle stand-in: only `financials` is real, everything else
    the formatter probes (ratings, trends, etc.) reads back as falsy."""

    def __init__(self, financials):
        self.financials = financials

    def __getattr__(self, name):
        return None


def _charity_bundle(financials):
    return _FakeBundle(financials)


class TestProgramRatioScoreSurfaced:
    def test_cash_adjusted_ratio_included_when_it_differs_from_raw_ratio(self):
        baseline = {
            "amal_score": 68,
            "score_details": {
                "impact": {
                    "components": [
                        {
                            "name": "Program Ratio",
                            "possible": 5,
                            "scored": 0,
                            "evidence": "Cash-adjusted program ratio: 48%",
                        }
                    ]
                }
            },
        }
        gen = _generator()

        text = gen._format_charity_data(baseline, _charity_bundle(_financials()), None)

        assert "Cash-adjusted program ratio: 48%" in text
        assert "Program Ratio score (0/5 pts)" in text

    def test_no_extra_line_when_no_program_ratio_component(self):
        baseline = {"amal_score": 68, "score_details": {"impact": {"components": []}}}
        gen = _generator()

        text = gen._format_charity_data(baseline, _charity_bundle(_financials()), None)

        assert "Program Ratio score" not in text

    def test_no_crash_when_score_details_missing(self):
        baseline = {"amal_score": 68}
        gen = _generator()

        text = gen._format_charity_data(baseline, _charity_bundle(_financials()), None)

        assert "Program Ratio score" not in text
        assert "Program Expense Ratio: 83.0%" in text

    def test_no_crash_when_score_details_is_explicitly_null(self):
        """score_details is a nullable json column; .get(k, {}) returns None for an
        explicit SQL NULL, so the default never applies."""
        baseline = {"amal_score": 68, "score_details": None}
        gen = _generator()

        text = gen._format_charity_data(baseline, _charity_bundle(_financials()), None)

        assert "Program Ratio score" not in text
        assert "Program Expense Ratio: 83.0%" in text

"""A per-beneficiary cost is only as good as its denominator.

When the beneficiary count the pipeline found describes one program or one
country rather than the whole organization, it marks the charity
beneficiaries_excluded_from_scoring, sets confidence to needs_review, and
publishes no beneficiary number. score_details.impact.cost_per_beneficiary --
computed from that same rejected count -- went out anyway.

28 of the 74 charities carrying the figure were in that state. International
Rescue Committee published $218,740 per beneficiary: $1.54B of expense over
roughly seven thousand people, for an organization that reaches millions.
Southern Poverty Law Center published $187,785. The page shows no beneficiary
count beside the figure, so a donor cannot see that the denominator was thrown
away.
"""

from export import _suppress_untrusted_cost_per_beneficiary


def _evaluation(cpb):
    return {"score_details": {"impact": {"cost_per_beneficiary": cpb, "score": 40}}}


class TestARejectedDenominatorSuppressesTheFigure:
    def test_it_removes_the_cost_when_beneficiaries_are_excluded(self):
        ev = _evaluation(218739.75)

        assert _suppress_untrusted_cost_per_beneficiary(ev, True) is True
        assert ev["score_details"]["impact"]["cost_per_beneficiary"] is None

    def test_it_leaves_the_rest_of_the_impact_block_alone(self):
        ev = _evaluation(218739.75)
        _suppress_untrusted_cost_per_beneficiary(ev, True)

        assert ev["score_details"]["impact"]["score"] == 40


class TestATrustedCountStillPublishes:
    def test_a_trusted_cost_survives(self):
        ev = _evaluation(353.70)

        assert _suppress_untrusted_cost_per_beneficiary(ev, False) is False
        assert ev["score_details"]["impact"]["cost_per_beneficiary"] == 353.70

    def test_none_for_excluded_is_treated_as_trusted(self):
        """The flag is absent for most charities; absence must not suppress."""
        ev = _evaluation(353.70)

        assert _suppress_untrusted_cost_per_beneficiary(ev, None) is False
        assert ev["score_details"]["impact"]["cost_per_beneficiary"] == 353.70


class TestItNeverRaisesOnOddShapes:
    def test_missing_impact_block(self):
        ev = {"score_details": {}}

        assert _suppress_untrusted_cost_per_beneficiary(ev, True) is False

    def test_impact_is_not_a_dict(self):
        ev = {"score_details": {"impact": "n/a"}}

        assert _suppress_untrusted_cost_per_beneficiary(ev, True) is False

    def test_no_score_details_at_all(self):
        assert _suppress_untrusted_cost_per_beneficiary({}, True) is False

    def test_already_null_reports_no_change(self):
        assert _suppress_untrusted_cost_per_beneficiary(_evaluation(None), True) is False


class TestTheDisplayStringsAreScrubbedToo:
    """Nulling the numeric field alone still left the figure on the page.

    The scorer writes it into score_details.impact.rationale and into the
    Cost Per Beneficiary component's evidence string. IRC's page went on
    reading "$218739.75/beneficiary" after the field was already null.
    """

    def _evaluation_with_strings(self):
        return {
            "score_details": {
                "impact": {
                    "cost_per_beneficiary": 218739.75,
                    "rationale": "$218739.75/beneficiary; Impact 37/50",
                    "components": [
                        {
                            "name": "Cost Per Beneficiary",
                            "evidence": "$218739.75/beneficiary (average for EXTREME_POVERTY)",
                        },
                        {"name": "Evidence & Outcomes", "evidence": "Randomised trials cited."},
                    ],
                }
            }
        }

    def test_the_rationale_no_longer_states_a_figure(self):
        ev = self._evaluation_with_strings()
        _suppress_untrusted_cost_per_beneficiary(ev, True)

        assert ev["score_details"]["impact"]["rationale"] == (
            "cost per beneficiary unavailable; Impact 37/50"
        )

    def test_the_component_evidence_keeps_its_benchmark_note(self):
        ev = self._evaluation_with_strings()
        _suppress_untrusted_cost_per_beneficiary(ev, True)

        assert ev["score_details"]["impact"]["components"][0]["evidence"] == (
            "cost per beneficiary unavailable (average for EXTREME_POVERTY)"
        )

    def test_unrelated_evidence_is_untouched(self):
        ev = self._evaluation_with_strings()
        _suppress_untrusted_cost_per_beneficiary(ev, True)

        assert ev["score_details"]["impact"]["components"][1]["evidence"] == (
            "Randomised trials cited."
        )

    def test_the_comma_and_per_spelling_is_matched(self):
        ev = {
            "score_details": {
                "impact": {
                    "cost_per_beneficiary": 86746.42,
                    "rationale": "Spending reaches $86,746.42 per beneficiary here.",
                    "components": [],
                }
            }
        }
        _suppress_untrusted_cost_per_beneficiary(ev, True)

        assert "86,746" not in ev["score_details"]["impact"]["rationale"]

    def test_a_trusted_charity_keeps_its_strings(self):
        ev = self._evaluation_with_strings()

        assert _suppress_untrusted_cost_per_beneficiary(ev, False) is False
        assert "$218739.75/beneficiary" in ev["score_details"]["impact"]["rationale"]

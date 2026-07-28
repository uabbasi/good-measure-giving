"""Cash reserves / working capital belong to Financial Health, not Alignment.

The baseline prompt's own output schema says dimension_explanations.impact
covers "program effectiveness, financial health, and evidence quality" and
.alignment covers "donor fit, cause urgency, and track record" -- but the
model sometimes writes a reserves aside into the alignment text anyway.

Real occurrence, EIN 27-3625796 (Heart Women & Girls): dimension_explanations
.alignment read "The organization serves a specific need within Muslim
communities and is zakat-eligible [2]. It has a established track record in
domestic advocacy, though its high level of cash reserves--25.6 months of
working capital--is a notable factor for donors to consider [1]." The 25.6
months figure is correct and the concern is real -- it's just filed under the
wrong rubric heading; areas_for_improvement already states it separately
("Holds 25.6 months of working capital, which may delay the distribution of
zakat funds"), so removing the misplaced aside drops a duplicate, not
information.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline import strip_financial_reserves_from_alignment

REAL_ALIGNMENT_TEXT = (
    "The organization serves a specific need within Muslim communities and is "
    "zakat-eligible [2]. It has a established track record in domestic "
    "advocacy, though its high level of cash reserves—25.6 months of "
    "working capital—is a notable factor for donors to consider [1]."
)


class TestRealObservedCase:
    def test_reserves_aside_is_dropped_from_alignment(self):
        narrative = {"dimension_explanations": {"alignment": REAL_ALIGNMENT_TEXT}}
        out = strip_financial_reserves_from_alignment(narrative)
        alignment = out["dimension_explanations"]["alignment"]
        assert "cash reserves" not in alignment.lower()
        assert "working capital" not in alignment.lower()

    def test_the_true_claims_in_the_same_sentence_survive(self):
        """Only the reserves aside goes -- the real track-record claim in
        the SAME sentence, and the whole first sentence, must survive."""
        narrative = {"dimension_explanations": {"alignment": REAL_ALIGNMENT_TEXT}}
        out = strip_financial_reserves_from_alignment(narrative)
        alignment = out["dimension_explanations"]["alignment"]
        assert "zakat-eligible" in alignment
        assert "established track record in domestic advocacy" in alignment

    def test_impact_dimension_is_untouched(self):
        """The concern belongs in impact -- if it's already there, leave it."""
        narrative = {
            "dimension_explanations": {
                "alignment": REAL_ALIGNMENT_TEXT,
                "impact": "Maintains 25.6 months of working capital, a strong reserve position [1].",
            }
        }
        out = strip_financial_reserves_from_alignment(narrative)
        assert "working capital" in out["dimension_explanations"]["impact"]

    def test_areas_for_improvement_is_untouched(self):
        """The same fact correctly stated elsewhere in the narrative must
        not be swept up just because it shares the trigger phrase."""
        narrative = {
            "dimension_explanations": {"alignment": REAL_ALIGNMENT_TEXT},
            "areas_for_improvement": [
                "Holds 25.6 months of working capital, which may delay the "
                "distribution of zakat funds [1]."
            ],
        }
        out = strip_financial_reserves_from_alignment(narrative)
        assert "working capital" in out["areas_for_improvement"][0]


class TestGeneralBehavior:
    def test_alignment_with_no_reserves_mention_is_untouched(self):
        text = "This charity serves Muslim donors well and has a strong track record [1]."
        narrative = {"dimension_explanations": {"alignment": text}}
        out = strip_financial_reserves_from_alignment(narrative)
        assert out["dimension_explanations"]["alignment"] == text

    def test_sentence_entirely_about_reserves_is_dropped_whole(self):
        narrative = {
            "dimension_explanations": {
                "alignment": (
                    "This charity is a strong fit for Muslim donors [2]. "
                    "Cash reserves are 30 months of working capital."
                )
            }
        }
        out = strip_financial_reserves_from_alignment(narrative)
        alignment = out["dimension_explanations"]["alignment"]
        assert "reserves" not in alignment.lower()
        assert "strong fit for Muslim donors" in alignment

    def test_missing_dimension_explanations_is_a_no_op(self):
        narrative = {"headline": "x"}
        out = strip_financial_reserves_from_alignment(narrative)
        assert out == {"headline": "x"}

    def test_non_string_alignment_is_a_no_op(self):
        narrative = {"dimension_explanations": {"alignment": None}}
        out = strip_financial_reserves_from_alignment(narrative)
        assert out["dimension_explanations"]["alignment"] is None

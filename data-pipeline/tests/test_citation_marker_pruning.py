"""A citation marker must not contradict the claim it is attached to.

The baseline prompt's Citation Rules only ever governed numbering validity --
"ONLY use citation numbers that exist", "include a matching entry", "Format:
[N]" -- and its output template modelled scattering ("2-3 sentences with
citations like [1] and [2]"). Nothing required a marker to support the
sentence it sat on, and the model duly decorated claims with extra markers.

Real output, EIN 83-3464851:

    "In FY2024, the organization managed $7,254,154 in total revenue to
     support healthcare systems and hunger relief in Sudan and Chad [1][6]."

  [6]  Form 990 (2023)     "reported $7,254,154 in total revenue"   -> supports
  [1]  Charity Navigator   "90.0/100 score and 81.2% program ratio" -> does not

The score judge flagged exactly this on three claims for that charity alone.

The rule here is deliberately narrow and mechanical: when a sentence asserts
numbers, a marker whose own declared claim asserts DIFFERENT numbers is not
supporting it. A citation whose claim carries no numbers is always allowed --
qualitative sources legitimately support numeric sentences. And a marker is
only ever dropped when another marker on the same claim survives, so pruning
can never turn a cited claim into an uncited one.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline import prune_unsupported_citation_markers

CITATIONS = [
    {"id": "[1]", "claim": "The charity has a 90.0/100 score and an 81.2% program expense ratio"},
    {"id": "[5]", "claim": "The charity is zakat-eligible and follows specific asnaf categories"},
    {"id": "[6]", "claim": "The organization reported $7,254,154 in total revenue for FY2024"},
]


def _prune(text):
    return prune_unsupported_citation_markers({"summary": text}, CITATIONS)["summary"]


class TestTheRealCase:
    def test_a_marker_asserting_other_numbers_is_dropped(self):
        out = _prune(
            "In FY2024, the organization managed $7,254,154 in total revenue "
            "to support healthcare in Sudan and Chad [1][6]."
        )
        assert "[6]" in out
        assert "[1]" not in out

    def test_a_compound_claim_keeps_both_relevant_markers(self):
        """Both sources genuinely support parts of this sentence."""
        out = _prune(
            "The charity is zakat-eligible and maintains a Charity Navigator "
            "score of 90.0/100 for its financial health [1][5]."
        )
        assert "[1]" in out and "[5]" in out


class TestItNeverStrandsAClaim:
    def test_a_lone_mismatched_marker_is_kept(self):
        """Dropping it would leave the claim uncited, which is worse than
        leaving it cited to something imperfect."""
        out = _prune("The organization managed $7,254,154 in revenue [1].")
        assert "[1]" in out

    def test_the_last_surviving_marker_is_never_removed(self):
        out = _prune("Revenue reached $7,254,154 and margins improved [1][1].")
        assert "[1]" in out


class TestQualitativeSourcesAreLeftAlone:
    def test_a_numberless_claim_may_support_a_numeric_sentence(self):
        out = _prune(
            "The charity is zakat-eligible and reported $7,254,154 in revenue [5][6]."
        )
        assert "[5]" in out and "[6]" in out

    def test_a_sentence_without_numbers_is_untouched(self):
        text = "The organization works with local health providers [1][5][6]."
        assert _prune(text) == text


class TestMechanics:
    def test_commas_and_currency_do_not_defeat_matching(self):
        out = _prune("Total revenue was $7254154 last year [1][6].")
        assert "[6]" in out and "[1]" not in out

    def test_unknown_marker_is_left_alone(self):
        """A marker with no registry entry is the structural validator's
        problem, not this function's."""
        out = _prune("Revenue was $7,254,154 [6][99].")
        assert "[99]" in out

    def test_non_string_fields_pass_through(self):
        payload = {"strengths": ["a", "b"], "count": 3, "summary": "No numbers here [1]."}
        out = prune_unsupported_citation_markers(payload, CITATIONS)
        assert out["strengths"] == ["a", "b"] and out["count"] == 3

    def test_nested_lists_of_prose_are_pruned_too(self):
        out = prune_unsupported_citation_markers(
            {"strengths": ["Revenue of $7,254,154 was reported [1][6]."]}, CITATIONS
        )
        assert "[6]" in out["strengths"][0] and "[1]" not in out["strengths"][0]

    def test_empty_citations_is_a_no_op(self):
        text = "Revenue was $7,254,154 [1][6]."
        assert prune_unsupported_citation_markers({"s": text}, [])["s"] == text

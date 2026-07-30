"""An ERROR has to be self-consistent to gate publication.

`numeric_agreement` exists because "$205,225 vs $205,225" came back as a blocking
error -- its docstring says "A deterministic check does not have moods." It only
compares NUMBERS, so the same failure recurred in prose form and sailed straight
through the gate:

    23-7065716  board_size   claim='two members'  source='two members'
        "...but Candid lists two board members, WHICH IS NOT A CONTRADICTION."
    27-3175543  noncash      claim='much of which is non-cash' source='143021451'
        "...WHICH IS SUPPORTED BY THE SOURCE DATA indicating noncash contributions
         of $143,021,451 out of $149,888,609 total revenue."
    20-1799252  citation_1   claim=None  source=None
        "citation states ... Zakat eligible, but the claim states it is recognized
         as zakat-eligible."

None of these is a source disagreement. In each the model wrote a verification note
and tagged it `severity=error`, so its severity contradicts its own message and,
where present, its own claim/source pair. The prompt already forbids exactly this
("If claim_value and source_value are the same number, do not report an issue at
all"; "Only report actual issues") and is ignored.

Three deterministic shapes, mirroring how numeric_agreement already works:

  1. both values present and textually identical  -> provable agreement
  2. neither value present                        -> nothing to verify against
  3. exactly one value parses as a number         -> a prose claim cannot be
                                                     numerically falsified

Scope is deliberately narrow. A claim with a missing SOURCE still blocks: that is
what a fabrication finding looks like. Two differing prose values still block. Two
numbers that genuinely disagree still block -- Humaniti's -6.1 vs -0.23 months of
working capital is a real data bug and must keep its page withheld.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import (
    _prose_claim_against_a_number,
    _unnamed_claim_against_a_source,
    _values_are_textually_identical,
    numeric_agreement,
)


class TestIdenticalValues:
    def test_the_board_size_pair_is_recognized(self):
        assert _values_are_textually_identical("two members", "two members")

    def test_case_and_whitespace_do_not_hide_agreement(self):
        assert _values_are_textually_identical("Two  Members", "two members ")

    def test_the_existing_numeric_guard_still_cannot_see_it(self):
        """Why this rule is needed at all."""
        assert numeric_agreement("two members", "two members") is None

    def test_genuinely_different_prose_is_not_identical(self):
        assert not _values_are_textually_identical("accepts zakat", "does not accept zakat")

    def test_a_missing_side_is_not_identical(self):
        assert not _values_are_textually_identical("two members", None)
        assert not _values_are_textually_identical(None, None)


class TestAnUnnamedClaimAgainstASource:
    """One-directional by design. The first draft of this rule downgraded whenever
    NEITHER value was present, which quietly gutted fabrication findings: the model
    states real contradictions in prose without filling the structured fields, and
    `test_an_unrelated_zakat_claim_still_blocks` caught it.
    """

    def test_the_umr_ratio_shape_is_recognized(self):
        """claim=None, source='0.475' -- the judge never named the narrative's claim."""
        assert _unnamed_claim_against_a_source(None, "0.475")

    def test_an_empty_claim_counts_as_unnamed(self):
        assert _unnamed_claim_against_a_source("   ", "0.475")

    def test_a_claim_with_no_source_still_blocks(self):
        """The mirror shape is what a fabrication looks like."""
        assert not _unnamed_claim_against_a_source("$4.2M distributed as zakat", None)

    def test_neither_side_named_still_blocks(self):
        """The model states genuine contradictions in prose alone."""
        assert not _unnamed_claim_against_a_source(None, None)

    def test_both_present_is_not_this_rule(self):
        assert not _unnamed_claim_against_a_source("two members", "two members")


class TestProseAgainstANumber:
    def test_the_umr_noncash_pair_is_recognized(self):
        assert _prose_claim_against_a_number("much of which is non-cash", "143021451")

    def test_several_years_old_against_a_fiscal_year_is_recognized(self):
        assert _prose_claim_against_a_number("several years old", "FY2022")

    def test_two_real_numbers_are_left_to_the_numeric_guard(self):
        """Humaniti's working capital: a genuine data bug that must keep blocking."""
        assert not _prose_claim_against_a_number("-6.1 months", "-0.23 months")
        assert numeric_agreement("-6.1 months", "-0.23 months") is False

    def test_two_prose_values_are_not_this_rule(self):
        assert not _prose_claim_against_a_number("accepts zakat", "does not accept zakat")

    def test_a_missing_side_is_not_this_rule(self):
        assert not _prose_claim_against_a_number("much of which is non-cash", None)


class TestTheGuardsDoNotSwallowRealFindings:
    def test_a_real_numeric_disagreement_survives_every_new_rule(self):
        claim, source = "$5,000,000", "$3,200,000"
        assert not _values_are_textually_identical(claim, source)
        assert not _unnamed_claim_against_a_source(claim, source)
        assert not _prose_claim_against_a_number(claim, source)
        assert numeric_agreement(claim, source) is False

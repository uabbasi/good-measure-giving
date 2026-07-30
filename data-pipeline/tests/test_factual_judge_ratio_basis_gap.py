"""The program ratio now carries two legitimate values, but only within a bound.

This run introduced the second value. Before it we published Charity Navigator's
filed ratio and matched them; `e60549b`/`f0b7764` made the narrative publish the
CASH-ADJUSTED ratio whenever gifts-in-kind materially inflate the filed one, because
that is what the scorer scores. CN still reports the filed figure, so the factual
judge began reading our own methodology as a contradiction:

    36-4787320 Justice Defenders  claim='58.5%'  source='65.13%'   (6.6 points)
    27-3175543 UMR                claim='96.48%' source='47.5%'   (49.0 points)

Those two are NOT the same case. A 6.6-point gap is a basis difference and a donor
reads them as the same story. 96.5% versus 47.5% is "nearly all spending reaches
programs" versus "less than half" — the exact gap we decided donors must see, and
the reason the scorer gave UMR 0/5 on Program Ratio. So the tolerance is measured in
PERCENTAGE POINTS, not the 60% relative divergence `_same_story` allows, which would
have swallowed UMR.

Deliberately NOT added to the shared METHODOLOGY_DIVERGENT_FIELD_RE. The score judge
defers on that list UNBOUNDED (it has only prose and cannot recover operands), so
adding the program ratio there would stop it blocking narratives that tout the filed
ratio as an efficiency strength — undoing the fix that introduced this duality in the
first place. The factual judge has structured claim/source values and can bound the
call; the score judge keeps blocking prose conflation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import _is_ratio_basis_gap
from src.judges.materiality import is_methodology_divergent

FIELD = "program_expense_ratio"


class TestABasisSizedGapIsTolerated:
    def test_justice_defenders_is_a_basis_difference(self):
        assert _is_ratio_basis_gap(FIELD, "58.5%", "65.13%")

    def test_scale_mismatch_is_normalized(self):
        """One side may arrive as a fraction (0.585) and the other as a percent."""
        assert _is_ratio_basis_gap(FIELD, "0.585", "65.13%")


class TestTheGapWeWantDonorsToSeeStillBlocks:
    def test_umr_filed_versus_cash_adjusted_is_not_tolerated(self):
        assert not _is_ratio_basis_gap(FIELD, "96.48%", "47.5%")

    def test_umr_holds_across_the_scale_mismatch_too(self):
        """The same pair has appeared as '0.475' and as '47.5%'."""
        assert not _is_ratio_basis_gap(FIELD, "96.48%", "0.475")

    def test_a_sign_flip_is_never_the_same_story(self):
        assert not _is_ratio_basis_gap(FIELD, "12%", "-12%")


class TestScope:
    def test_non_ratio_fields_are_untouched(self):
        """Two revenue figures 6 apart are not a basis gap."""
        assert not _is_ratio_basis_gap("total_revenue", "58.5", "65.13")

    def test_unparseable_values_do_not_downgrade_blind(self):
        assert not _is_ratio_basis_gap(FIELD, "most of its budget", "65.13%")


class TestTheScoreJudgeIsDeliberatelyNotWidened:
    def test_program_ratio_is_absent_from_the_shared_divergent_list(self):
        """Regression guard for the design decision. The score judge defers on
        that list without any bound, so putting the program ratio there would let
        a narrative tout the filed 96.5% as an efficiency strength again."""
        assert not is_methodology_divergent("program_expense_ratio")
        assert not is_methodology_divergent("program expense ratio of 96.5%")

    def test_the_list_still_covers_what_it_did_before(self):
        assert is_methodology_divergent("fundraising_efficiency")
        assert is_methodology_divergent("working capital")

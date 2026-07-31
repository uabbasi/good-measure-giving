"""The financial block must come from ONE source for ONE fiscal year.

ProPublica reports the Form 990 itself but exposes only the top line: for 158
of 169 charities it supplies exactly two income-statement fields (total_revenue,
total_expenses) and nothing else. Charity Navigator supplies all five and is a
year newer for 134 of 168 -- but it is LLM-extracted from scraped HTML, so where
the two describe the SAME filing it is CN that goes wrong, in a recognizable
way: PP reports $11,189,635 and $102,250, CN reports $5,400,000 and $900,000.

The old election mixed them, and produced published figures that belong to no
source at all:

  83-1171525 Link Outside     total_expenses  102,250 (PP)   <- live, and the
                              program_expenses 800,000 (CN)     program figure
                              program ratio       0.88 (CN)     is 7.8x total
  92-1198452 The Intercept    total_expenses 11,189,635 (PP)
                              program_expenses 4,500,000 (CN, whose own total
                              was 5,400,000) -- a 40% ratio matching neither

and it elected by field COUNT with no regard for recency, so five charities
published a staler income statement than the one we already held:

  83-1794093 Hikma Health     PP=2023  published CN's FY2019
  90-0327815 Morocco Fdn      PP=2023  published CN's FY2022
  82-1670588 BASMAH, 88-3709826 Saylani, 81-2566656 Rohingya Muslim Relief

Separately, working_capital_months was computed from ProPublica unconditionally
-- assets, liabilities AND expenses -- even when the published income statement
came from CN for a different year. The stored figure was internally coherent but
did not divide out against the numbers printed beside it, so a donor recomputing
"months of reserves" from the page got a different answer on 103 of 169 pages.
Humaniti stored -6.10 months against -0.2 recomputed; The Mecca Center stored
124 against 3,149. The factual judge was right to block on it.

Canonical rule, in one line: elect the whole income statement from the most
RECENT source, break ties toward ProPublica (it is the filing), never splice
two sources that disagree about the filing they claim to share, and derive
nothing across a fiscal-year boundary.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import (
    elect_income_statement,
    shared_income_fields_agree,
)

PP = "propublica"
CN = "charity_navigator"
GAP = "gap_fill"


def _elect(pp_year, cn_year, pp_count=2, cn_count=5, agree=True):
    return elect_income_statement(
        pp_tax_year=pp_year,
        cn_fiscal_year=cn_year,
        pp_income_count=pp_count,
        cn_income_count=cn_count,
        shared_fields_agree=agree,
    )


class TestRecencyWins:
    def test_the_common_case_cn_a_year_newer_and_complete(self):
        """134 of 168 charities. PP has 2 fields, CN has 5 and is newer."""
        assert _elect(2023, 2024) == CN

    def test_a_stale_cn_never_wins_however_complete(self):
        """Hikma Health: CN's FY2019 has all five fields, PP's FY2023 has two.
        Five complete years-old figures presented as current is misinformation;
        two current ones are merely incomplete."""
        assert _elect(2023, 2019) == PP

    def test_morocco_publishes_its_newer_filing(self):
        assert _elect(2023, 2022) == PP

    def test_cn_newer_but_too_thin_leaves_pp_alone(self):
        """Recency does not override having nothing to say."""
        assert _elect(2023, 2024, cn_count=1) == PP

    def test_a_complete_pp_is_not_displaced(self):
        """When PP already breaks out functional expenses there is nothing to gain."""
        assert _elect(2023, 2024, pp_count=5) == PP


class TestSameYearDisagreementIsNotSpliced:
    def test_agreeing_sources_may_still_gap_fill(self):
        """13 of 15 same-year pairs agree within 1%; CN fills what PP omits."""
        assert _elect(2023, 2023, agree=True) == GAP

    def test_link_outside_shape_falls_back_to_the_filing(self):
        """Same claimed year, incompatible numbers -- CN is not describing this
        filing, so splicing its program_expenses onto PP's total produces the
        7.8x impossibility. Keep PP whole."""
        assert _elect(2023, 2023, agree=False) == PP

    def test_an_unknown_pp_year_still_requires_agreement(self):
        assert _elect(None, 2024, agree=True) == GAP
        assert _elect(None, 2024, agree=False) == PP


class TestDegenerateInputs:
    def test_no_cn_at_all(self):
        assert _elect(2023, None, cn_count=0) == PP

    def test_no_pp_at_all(self):
        assert _elect(None, 2024, pp_count=0) == CN

    def test_neither_source_has_an_income_statement(self):
        assert _elect(None, None, pp_count=0, cn_count=0) == PP


class TestSharedFieldAgreement:
    def test_the_intercept_pair_disagrees(self):
        assert not shared_income_fields_agree(
            {"total_revenue": 18961623, "total_expenses": 11189635},
            {"total_revenue": 18961623, "total_expenses": 5400000},
        )

    def test_the_link_outside_pair_disagrees(self):
        assert not shared_income_fields_agree(
            {"total_expenses": 102250}, {"total_expenses": 900000}
        )

    def test_rounding_noise_is_not_disagreement(self):
        assert shared_income_fields_agree(
            {"total_expenses": 11189635}, {"total_expenses": 11189000}
        )

    def test_fields_only_one_source_reports_are_not_compared(self):
        """PP almost never breaks out program_expenses; its absence is not a
        disagreement, it is the whole reason CN is consulted."""
        assert shared_income_fields_agree(
            {"total_expenses": 500000, "program_expenses": None},
            {"total_expenses": 500000, "program_expenses": 400000},
        )

    def test_no_overlap_at_all_is_not_disagreement(self):
        assert shared_income_fields_agree({}, {"total_expenses": 400000})

    def test_a_zero_against_a_real_figure_disagrees(self):
        assert not shared_income_fields_agree(
            {"total_expenses": 500000}, {"total_expenses": 0}
        )

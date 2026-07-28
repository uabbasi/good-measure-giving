"""board_size may only come from a source that reports governance.

Two defects, found via EIN 87-2410117, whose narrative claimed a "two-member
board" and was correctly flagged by the factual judge:

1. Charity Navigator was absent from the candidate list, despite being the
   source most likely to carry a reviewed board size. The election's own
   comment says "take max across sources (parsing bugs can undercount)" --
   and then omitted the source with the number. CN said 6 with 100%
   independence; nothing else had anything. 47 of 154 charities disagreed
   with CN, 21 of them undercounts.

2. When no source reported a board size, the code substituted
   len(website_profile["leadership"]). For 87-2410117 that list was
   [Chief Executive Officer, Deputy CEO] -- two executives, not a board.
   51 charities had a board_size that was really an executive headcount,
   and it feeds a governance risk tier worth up to 2 points.

Dropping the proxy leaves 35 charities with board_size = None. That is the
correct outcome: "no governance source reports this" is not the same as "the
board is small", and the pipeline's own rule is that missing fields stay NULL.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

EIN = "87-2410117"


def _aggregate(cn=None, candid=None, pp=None, website=None):
    return CharityMetricsAggregator.aggregate(
        charity_id=0,
        ein=EIN,
        cn_profile=cn,
        candid_profile=candid,
        propublica_990=pp,
        website_profile=website,
    )


class TestCharityNavigatorCounts:
    def test_cn_board_size_is_used_when_it_is_the_only_source(self):
        m = _aggregate(cn={"name": "T", "board_size": 6})
        assert m.board_size == 6

    def test_cn_participates_in_the_max(self):
        m = _aggregate(cn={"name": "T", "board_size": 11}, candid={"board_size": 4})
        assert m.board_size == 11

    def test_a_larger_other_source_still_wins(self):
        m = _aggregate(cn={"name": "T", "board_size": 3}, candid={"board_size": 9})
        assert m.board_size == 9

    def test_attribution_names_charity_navigator_when_it_wins(self):
        m = _aggregate(cn={"name": "T", "board_size": 6})
        attr = (m.source_attribution or {}).get("board_size", {})
        assert attr.get("source_name") == "charity_navigator", (
            f"board_size came from CN but was attributed to {attr.get('source_name')!r}"
        )


class TestLeadershipIsNotABoard:
    def test_executive_roster_does_not_become_a_board_size(self):
        m = _aggregate(
            website={
                "leadership": [
                    {"name": "Dr Mohamed Ashmawey", "title": "Chief Executive Officer"},
                    {"name": "Owais Khan", "title": "Deputy CEO"},
                ]
            }
        )
        assert m.board_size is None, (
            f"Counted {m.board_size} executives as board members"
        )

    def test_the_real_case_prefers_cn_over_the_executive_count(self):
        m = _aggregate(
            cn={"name": "Human Appeal", "board_size": 6},
            website={
                "leadership": [
                    {"name": "A", "title": "Chief Executive Officer"},
                    {"name": "B", "title": "Deputy CEO"},
                ]
            },
        )
        assert m.board_size == 6

    def test_an_explicit_website_board_size_is_still_honoured(self):
        m = _aggregate(website={"board_size": 8, "leadership": [{"name": "A", "title": "CEO"}]})
        assert m.board_size == 8

    def test_no_governance_source_leaves_it_unknown(self):
        m = _aggregate(website={"leadership": []})
        assert m.board_size is None

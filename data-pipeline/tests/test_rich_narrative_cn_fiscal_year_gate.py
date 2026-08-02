"""CN income-statement figures must not reach the narrative prompt when they
describe a fiscal year the pipeline did not publish.

The aggregator elects income-statement fields from ONE fiscal-year-coherent
source (charity_metrics_aggregator._INCOME_STMT_FIELDS). When ProPublica wins
that election, CN's figures belong to a year absent from the published record,
yet they were still handed to the LLM — which would then write a
correctly-cited claim about a number the pipeline deliberately declined to use.

SCOPE: this does not explain the 34 live "$0.00 per $1 raised" narratives. 27
of those 35 charities have dataSource=charity_navigator (CN won the election),
so no year mismatch was involved. That defect remains open.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.rich_narrative_generator import RichNarrativeGenerator

_match = RichNarrativeGenerator._financials_match_elected_year


class TestCnFiscalYearGate:
    def test_same_year_is_publishable(self):
        assert _match(2024, 2024) is True

    def test_differing_years_are_withheld(self):
        assert _match(2024, 2023) is False

    def test_string_and_int_years_compare_by_value(self):
        assert _match("2024", 2024) is True
        assert _match("2023", 2024) is False

    def test_unknown_cn_year_stays_permissive(self):
        """Only a provable mismatch withholds data."""
        assert _match(None, 2024) is True

    def test_unknown_elected_year_stays_permissive(self):
        assert _match(2024, None) is True

    def test_unparseable_year_stays_permissive(self):
        assert _match("FY2024", 2024) is True

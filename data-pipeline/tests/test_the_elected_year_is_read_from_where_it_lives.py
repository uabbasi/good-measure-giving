"""The fiscal-year guards were comparing against a column nothing writes.

Both income-statement guards in the rich narrative prompt ask
_financials_match_elected_year(source_year, elected_year), and that predicate
is deliberately permissive: unknown on either side means "do not withhold".
Both read the elected year from `charity_data.financial_data_tax_year`.

That column is populated for **0 of 166** published charities. The same field
inside `charity_data.metrics_json` is populated for 160. So elected_year was
always None, the predicate always returned True, and neither guard ever
withheld anything — the Charity Navigator one included, since it was written.

Measured consequence on 2026-08-02: 57 published charities state a total
revenue in their rich narrative that is not the figure the site publishes,
and every one of those figures traces to a source that lost the election —
54 to ProPublica, 3 to Charity Navigator. Examples:

    13-1685039  CARE USA   narrative $909,098,267   published $832,911,696
    13-6213516  ACLU Fdn   narrative $185,146,988   published $306,750,536
    20-0942434  Baitulmaal narrative  $23,687,125   published  $77,434,379

CARE USA was regenerated the same day with the ProPublica guard in place and
still quoted ProPublica, which is what exposed the guard as inert.

The elected year has to be read from where it actually lives.
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.rich_narrative_generator import RichNarrativeGenerator  # noqa: E402

EIN = "13-1685039"


def _generator(row):
    gen = object.__new__(RichNarrativeGenerator)
    gen.charity_data_repo = Mock()
    gen.charity_data_repo.get.return_value = row
    return gen


def test_it_reads_the_year_out_of_metrics_json():
    """Where synthesize actually writes it."""
    gen = _generator({"metrics_json": {"financial_data_tax_year": 2025}})

    assert gen._elected_tax_year(EIN) == 2025


def test_metrics_json_may_arrive_as_a_string():
    gen = _generator({"metrics_json": json.dumps({"financial_data_tax_year": 2024})})

    assert gen._elected_tax_year(EIN) == 2024


def test_the_column_is_still_honoured_when_something_sets_it():
    gen = _generator({"metrics_json": {}, "financial_data_tax_year": 2023})

    assert gen._elected_tax_year(EIN) == 2023


def test_metrics_json_wins_over_the_column():
    gen = _generator({"metrics_json": {"financial_data_tax_year": 2025}, "financial_data_tax_year": 2019})

    assert gen._elected_tax_year(EIN) == 2025


def test_nothing_anywhere_is_none_not_a_crash():
    for row in ({}, {"metrics_json": None}, {"metrics_json": "not json"}, None):
        gen = _generator(row)
        assert gen._elected_tax_year(EIN) is None


def test_the_guard_now_actually_withholds():
    """End of the chain: ProPublica FY2023 against an elected FY2025."""
    gen = _generator({"metrics_json": {"financial_data_tax_year": 2025}})

    assert gen._financials_match_elected_year(2023, gen._elected_tax_year(EIN)) is False

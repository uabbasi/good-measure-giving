"""A figure the IRS filing won must be cited to the IRS filing.

realign_income_statement_attribution exists because two elections run over
the same charity and the aggregator's decision never reached the citations.
It handled the two winners that existed when it was written --
"charity_navigator" and "mixed" -- and returns early for anything else.

Making the IRS filing canonical added a third winner and did not teach this
function about it, so an irs_990 election falls straight through. Where
another source also published the figure, the citation names the source that
LOST. Where none did, the field ends up with a value and no attribution at
all, which is what the synthesize quality gate refuses to publish:

    Institute for Understanding Anti-Palestinian Racism (99-3032347)
    "IRS filing is canonical: FY2024 (3 fields) supersedes propublica FYNone (0)"
    total_revenue = 84465, source_attribution = {} for that field
    -> "Field 'total_revenue' has value but no source attribution"

That charity was the one outright synthesize failure of the 87-charity run
on 2026-08-02.

The aggregator already tracked the right provenance while electing --
_track(field, "irs_990", value) -- so this is a matter of moving what it
recorded onto the column, not of minting a new claim.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthesize import (  # noqa: E402
    INCOME_STATEMENT_COLUMNS,
    realign_income_statement_attribution,
)

EIN = "99-3032347"


def _metrics(**kw):
    base = {
        "financial_data_source": "irs_990",
        "total_revenue": 84465,
        "total_expenses": 61200,
        "program_expenses": 50000,
        "admin_expenses": None,
        "fundraising_expenses": None,
        "source_attribution": {
            "total_revenue": {"source_name": "IRS Form 990", "value": 84465},
            "total_expenses": {"source_name": "IRS Form 990", "value": 61200},
            "program_expenses": {"source_name": "IRS Form 990", "value": 50000},
        },
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_an_irs_elected_figure_gets_an_attribution():
    """The 99-3032347 shape: nothing else published these figures."""
    attribution: dict[str, dict] = {}

    realign_income_statement_attribution(attribution, _metrics(), EIN, None)

    assert "total_revenue" in attribution, "an elected figure was published with no provenance"
    assert attribution["total_revenue"]["value"] == 84465


def test_it_names_the_filing_that_won_not_the_source_that_lost():
    attribution = {
        "total_revenue": {"source_name": "Form 990 (2023)", "value": 71000, "section": "financials"},
    }

    realign_income_statement_attribution(attribution, _metrics(), EIN, None)

    assert attribution["total_revenue"]["value"] == 84465
    assert "2023" not in str(attribution["total_revenue"].get("display_name", ""))


def test_fields_the_filing_did_not_supply_are_left_alone():
    """Do not mint provenance for a figure the election never set."""
    attribution: dict[str, dict] = {}

    realign_income_statement_attribution(attribution, _metrics(), EIN, None)

    assert "admin_expenses" not in attribution
    assert "fundraising_expenses" not in attribution


def test_every_elected_income_statement_field_is_covered():
    attribution: dict[str, dict] = {}

    realign_income_statement_attribution(attribution, _metrics(), EIN, None)

    for field in INCOME_STATEMENT_COLUMNS:
        if getattr(_metrics(), field, None) is not None:
            assert field in attribution, f"{field} was elected but left uncited"


def test_the_other_winners_still_behave():
    """Regression: charity_navigator keeps rewriting every field."""
    attribution: dict[str, dict] = {}
    metrics = _metrics(financial_data_source="charity_navigator")

    realign_income_statement_attribution(attribution, metrics, EIN, None)

    assert attribution["total_revenue"]["source_name"] == "Charity Navigator"

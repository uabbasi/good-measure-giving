"""Gap-fill requires positive evidence that both sources describe one filing.

`shared_income_fields_agree` exists to stop CN's figures being spliced into
ProPublica's statement when the two disagree about the filing they claim to
share. The caller gated it on:

    same_claimed_year = pp_tax_year is None or pp_tax_year == cn_fiscal_year

which is False when CN reports NO fiscal year at all -- and the caller reads
False as "different years, so a gap between them is a real year-over-year
change, not a transcription error", and gap-fills without checking anything.
So the one case where we have the LEAST evidence that the two describe the
same filing was the case that skipped the check entirely.

EIN 82-1670588 (BASMAH) went live with the result: CN's program_expenses of
105,872 -- the whole of CN's own total_expenses, 105,872 -- published against
ProPublica's FY2023 total_expenses of 4,541,420. A page reporting that a
charity spent 2.3% of its money on programs, assembled from two filings that
were never the same filing. The same splice on 45-5637293 left 24.8% of
expenses unaccounted for.

An unknown year is not a shared year. Unless we positively know the two years
differ, the numbers have to agree before either may be spliced into the other.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import (
    CharityMetricsAggregator,
    sources_may_share_a_filing,
)


def _aggregate(pp=None, cn=None, ein="00-0000000"):
    return CharityMetricsAggregator.aggregate(
        charity_id=1, ein=ein, propublica_990=pp, cn_profile=cn
    )


class TestTheYearPredicate:
    def test_a_known_shared_year_is_shared(self):
        assert sources_may_share_a_filing(2023, 2023) is True

    def test_known_different_years_are_not(self):
        """Hikma Health FY2019 vs FY2023 -- a real change, not a conflict."""
        assert sources_may_share_a_filing(2023, 2019) is False

    def test_an_unknown_propublica_year_still_demands_agreement(self):
        assert sources_may_share_a_filing(None, 2023) is True

    def test_an_unknown_charity_navigator_year_demands_agreement_too(self):
        """The bug: this returned False, which skipped the agreement check."""
        assert sources_may_share_a_filing(2023, None) is True

    def test_neither_year_known(self):
        assert sources_may_share_a_filing(None, None) is True


class TestBasmahIsNotAssembledFromTwoFilings:
    """EIN 82-1670588 — live, publishing 105,872 against 4,541,420."""

    PP = {
        "tax_year": 2023,
        "total_revenue": 4195860,
        "total_expenses": 4541420,
    }
    CN = {
        # No fiscal_year: this is what let the splice through.
        "total_revenue": 141974,
        "total_expenses": 105872,
        "program_expenses": 105872,
        "program_expense_ratio": 1.0,
    }

    def test_the_filing_wins_whole(self):
        m = _aggregate(self.PP, self.CN)
        assert m.financial_data_source == "propublica"
        assert m.total_expenses == 4541420

    def test_the_disagreeing_program_figure_is_not_spliced_in(self):
        m = _aggregate(self.PP, self.CN)
        assert m.program_expenses is None

    def test_no_ratio_is_invented_from_two_filings(self):
        """2.3% would be a defamatory number to publish, and 100% a false one.
        Neither is derivable, so neither is published."""
        m = _aggregate(self.PP, self.CN)
        assert m.program_expense_ratio is None


class TestAnAgreeingUnknownYearMayStillGapFill:
    """4 of the 6 published charities with no CN year are fine — CN plainly
    describes the same filing. Refusing those too would cost real breakdowns."""

    PP = {"tax_year": 2023, "total_revenue": 1000000, "total_expenses": 900000}
    CN = {
        "total_revenue": 1000000,
        "total_expenses": 900000,
        "program_expenses": 720000,
        "admin_expenses": 120000,
        "fundraising_expenses": 60000,
    }

    def test_the_breakdown_is_still_filled_in(self):
        m = _aggregate(self.PP, self.CN)
        assert m.program_expenses == 720000
        assert round(m.program_expense_ratio, 4) == 0.8

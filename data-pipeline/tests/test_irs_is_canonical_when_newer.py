"""The primary source wins the income statement when it is newer and complete.

Charity Navigator and ProPublica are both downstream of the IRS e-file XML.
Until the bundle fixes landed most of that XML was unreadable, so the election
ran between the two mirrors and the question never arose. It arises now: for
EIN 36-4476244 both mirrors report FY2023 at $29,498,054 -- agreeing with each
other exactly -- while the filing itself reports FY2024 at $34,923,926. We were
publishing a two-year-old figure while holding the newer one.

Measured across the 40 charities of batch80 on 2026-07-31: the IRS is ahead on
6, level on 32. The gap appears where a charity's fiscal year ends mid-calendar
-- the mirrors lag there and the filing does not.

Two guards, both of which cost a page real information if they are wrong:

  NEWER ONLY. A filing that is not newer than what we already elected changes
  nothing and must not displace it. The election is recency-first everywhere
  else and stays so here.

  COMPLETE ONLY. The IRS 990-EZ has no Part IX, so it carries revenue and
  total expenses and no breakdown. Taking it whole would strip the
  program/admin/fundraising split that program_expense_ratio and the Financial
  Health score are computed from -- trading a stale complete statement for a
  current mutilated one. It supersedes only when it gives up at least as many
  fields as the source it replaces.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import elect_primary_filing


class TestWhenTheFilingSupersedesTheMirrors:
    def test_newer_and_complete_wins(self):
        """Zakat Foundation: IRS FY2024 with all five fields over the mirrors'
        FY2023."""
        assert elect_primary_filing(
            elected_year=2023, elected_count=3, irs_tax_year=2024, irs_income_count=5
        ) is True

    def test_same_year_does_not_displace(self):
        """32 of the 40. Nothing to gain, and the mirrors may carry revenue
        detail the grants parse does not."""
        assert elect_primary_filing(
            elected_year=2024, elected_count=5, irs_tax_year=2024, irs_income_count=5
        ) is False

    def test_an_older_filing_never_displaces(self):
        assert elect_primary_filing(
            elected_year=2024, elected_count=3, irs_tax_year=2023, irs_income_count=5
        ) is False

    def test_a_newer_but_thinner_filing_does_not_displace(self):
        """The 990-EZ case: newer, but two fields against five. Recency does
        not buy the right to delete the expense breakdown."""
        assert elect_primary_filing(
            elected_year=2023, elected_count=5, irs_tax_year=2024, irs_income_count=2
        ) is False

    def test_newer_and_equally_thin_still_wins(self):
        """Both thin: recency decides, which is the standing rule."""
        assert elect_primary_filing(
            elected_year=2023, elected_count=2, irs_tax_year=2024, irs_income_count=2
        ) is True

    def test_it_carries_a_charity_the_mirrors_missed_entirely(self):
        assert elect_primary_filing(
            elected_year=None, elected_count=0, irs_tax_year=2024, irs_income_count=5
        ) is True

    def test_no_filing_changes_nothing(self):
        assert elect_primary_filing(
            elected_year=2023, elected_count=3, irs_tax_year=None, irs_income_count=0
        ) is False

    def test_a_filing_with_no_income_statement_changes_nothing(self):
        """A grants-only parse must not blank out a working income statement."""
        assert elect_primary_filing(
            elected_year=2023, elected_count=3, irs_tax_year=2024, irs_income_count=0
        ) is False


class TestTheTrustTableNamesIt:
    def test_the_filing_leads_the_income_statement(self):
        from src.utils.source_trust import IRS_990, TRUST_ORDER

        assert TRUST_ORDER["income_statement"][0] == IRS_990

    def test_the_mirrors_keep_their_order_behind_it(self):
        from src.utils.source_trust import CHARITY_NAVIGATOR, PROPUBLICA, TRUST_ORDER

        assert TRUST_ORDER["income_statement"][1:] == (CHARITY_NAVIGATOR, PROPUBLICA)

    def test_the_balance_sheet_is_untouched(self):
        """Not in scope: the IRS balance sheet is read from a different part of
        the return and has not been measured against ProPublica's."""
        from src.utils.source_trust import PROPUBLICA, TRUST_ORDER

        assert TRUST_ORDER["balance_sheet"][0] == PROPUBLICA


class TestTheRatiosBelongToTheStatementTheyDescribe:
    """A ratio outlives the figures it was computed from.

    program_expense_ratio is taken from Charity Navigator's own reported ratio
    whenever one exists, and only computed from components when it does not.
    So electing the IRS statement replaced the numerator and the denominator
    and left the quotient behind: EIN 36-4476244 published FY2024 program
    expenses of 34,365,532 against total expenses of 36,818,000 -- a ratio of
    0.9334 -- under Charity Navigator's FY2023 ratio of 0.9159.

    That is the exact defect the canonical-source work exists to prevent, a
    numerator from one source over a denominator from another, arriving by the
    back door as a precomputed quotient. Whoever wins the income statement owns
    its ratios.
    """

    from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

    PP = {"tax_year": 2023, "total_revenue": 29498054, "total_expenses": 19207320}
    CN = {
        "fiscal_year": 2023, "total_revenue": 29498054, "total_expenses": 19207320,
        "program_expenses": 17349000, "program_expense_ratio": 0.9159,
        "admin_expense_ratio": 0.05, "fundraising_expense_ratio": 0.03,
    }
    IRS = {
        "tax_year": 2024, "total_revenue": 34923926, "total_expenses": 36818000,
        "program_expenses": 34365532, "admin_expenses": 1198626,
        "fundraising_expenses": 1253842,
    }

    def _metrics(self):
        return self.CharityMetricsAggregator.aggregate(
            charity_id=1, ein="36-4476244", propublica_990=self.PP,
            cn_profile=self.CN, grants_profile=self.IRS,
        )

    def test_the_filing_won_the_statement(self):
        m = self._metrics()
        assert m.financial_data_tax_year == 2024
        assert m.total_revenue == 34923926

    def test_the_program_ratio_is_the_filing_s_own(self):
        m = self._metrics()
        assert m.program_expense_ratio == round(34365532 / 36818000, 4)

    def test_the_stale_quotient_is_gone(self):
        assert self._metrics().program_expense_ratio != 0.9159

    def test_admin_and_fundraising_ratios_follow_too(self):
        m = self._metrics()
        assert m.admin_expense_ratio == round(1198626 / 36818000, 4)
        assert m.fundraising_expense_ratio == round(1253842 / 36818000, 4)

    def test_the_ratio_divides_the_published_figures(self):
        """The invariant a reader can check with a calculator."""
        m = self._metrics()
        assert abs(m.program_expenses / m.total_expenses - m.program_expense_ratio) < 0.0001

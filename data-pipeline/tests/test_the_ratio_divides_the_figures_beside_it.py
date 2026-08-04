"""A published program-expense ratio must be the quotient of the components
printed above it.

Charity Navigator's `avg_program_expense_ratio` is POOLED across the filings it
uses in its rating -- sum(program) / sum(total) over (usually) three years --
while the `program_expenses` / `total_expenses` we publish beside it are a
single year. Confirmed against CN's own raw `taxReturns` block for every
published charity where both are recoverable: 81 of 81 match the pooled
formula exactly, 0 of 81 match the most recent year alone.

So the two disagree by construction, and 65 of 166 published pages showed a
ratio that was not the quotient of the two figures above it:

  22-3382037   published  5,460,382 / 5,544,311  = 0.9849
               under a ratio of                    0.7154
               because CN pools in its 2023 filing, where the program figure
               is 152,166 against a total of 4,281,367 -- a breakdown CN never
               had, averaged in as though the charity had spent 3.5% on
               programs that year.

  85-3547280   0.9997 published as 0.8414   (CN's 2023: program 0 of 74,502)
  56-2620244   1.0000 published as 0.6780   (CN's 2023: program 0 of 2,449,720)

The pooled figure is not wrong -- it is a different statistic, and where no
components exist it is the only thing known about how the money was split.
Dropping it there collapses program-ratio scoring the way Al-Furqaan went
0.85 -> None -> impact 8/50. It may stand alone. It may not contradict.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator
from synthesize import elected_program_expense_ratio


def _aggregate(pp=None, cn=None, ein="00-0000000"):
    return CharityMetricsAggregator.aggregate(
        charity_id=1, ein=ein, propublica_990=pp, cn_profile=cn
    )


class TestPooledRatioNeverOutranksItsOwnComponents:
    """EIN 22-3382037 — live, showing 0.7154 over figures dividing to 0.9849."""

    PP = {"tax_year": 2023, "total_revenue": 4281367, "total_expenses": 4281367}
    CN = {
        "fiscal_year": 2025,
        "total_revenue": 5631488,
        "total_expenses": 5544311,
        "program_expenses": 5460382,
        "admin_expenses": 83929,
        "fundraising_expenses": 0,
        # CN's pooled 3-year figure, dragged down by a year it has no
        # breakdown for.
        "program_expense_ratio": 0.7154,
    }

    def test_the_ratio_is_recomputed_from_the_published_components(self):
        m = _aggregate(self.PP, self.CN)
        assert m.program_expenses == 5460382
        assert m.total_expenses == 5544311
        assert round(m.program_expense_ratio, 4) == 0.9849

    def test_a_donor_recomputing_from_the_page_gets_the_published_ratio(self):
        m = _aggregate(self.PP, self.CN)
        recomputed = m.program_expenses / m.total_expenses
        assert abs(recomputed - m.program_expense_ratio) <= 0.01


class TestTheRefusedStatementDoesNotReturnThroughTheOtherElection:
    """Fixing the aggregator is not enough to fix the page.

    Two elections run over the same charity. `aggregate()` decides
    `metrics.program_expense_ratio`; `extract_financials()` independently
    decides `financials["program_expense_ratio"]`, and it takes Charity
    Navigator's whenever CN has one. `elected_program_expense_ratio` picks
    between them, and the published COLUMN is whatever it returns.

    So after the aggregator correctly refused CN's incompatible statement for
    82-1670588 and left the ratio None, the column still read 1.0 — CN's
    figure, arriving through the second election. A fix verified only at the
    aggregator would have looked complete while the page was unchanged.
    """

    def _metrics(self, **kw):
        base = dict(
            program_expenses=None,
            total_expenses=4541420,
            program_expense_ratio=None,
            financial_source_discrepancies=[
                {"field": "total_expenses", "reason": "same_fiscal_year_disagreement"}
            ],
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_charity_navigators_ratio_does_not_come_back_via_extract_financials(self):
        elected = elected_program_expense_ratio(
            self._metrics(), {"program_expense_ratio": 1.0}
        )
        assert elected is None

    def test_a_ratio_from_an_uncontested_statement_is_still_a_fallback(self):
        """No refusal recorded — extract_financials' value is all we have."""
        metrics = self._metrics(financial_source_discrepancies=[])
        assert elected_program_expense_ratio(metrics, {"program_expense_ratio": 0.85}) == 0.85

    def test_the_aggregators_own_ratio_still_wins_outright(self):
        metrics = self._metrics(program_expense_ratio=0.9849, financial_source_discrepancies=[])
        assert elected_program_expense_ratio(metrics, {"program_expense_ratio": 0.7154}) == 0.9849

    def test_a_ratio_declined_on_unreliable_expenses_is_not_refilled(self):
        """EIN 47-5015710. The aggregator nulls every expense ratio when
        expenses exceed 3x revenue -- $2,539,788 against $510,635 revenue is
        5.0x, so the breakdown is not trustworthy. It nulls the RATIO and
        keeps the components, and the column was then refilled from CN with
        0.902 against components dividing to 0.9364.

        Holding both components and no ratio is a decision, not a gap. The
        only thing extract_financials may fill is an absence."""
        metrics = self._metrics(
            program_expenses=2378373,
            total_expenses=2539788,
            financial_source_discrepancies=[],
        )
        assert elected_program_expense_ratio(metrics, {"program_expense_ratio": 0.902}) is None


class TestAStandaloneRatioStillStands:
    """Al-Furqaan: no components to contradict, so CN's is all we know."""

    PP = {"tax_year": 2023, "total_revenue": 900000}
    CN = {"fiscal_year": 2023, "total_revenue": 900000, "program_expense_ratio": 0.85}

    def test_the_external_ratio_survives_when_nothing_can_contradict_it(self):
        m = _aggregate(self.PP, self.CN)
        assert m.program_expenses is None
        assert m.program_expense_ratio == 0.85

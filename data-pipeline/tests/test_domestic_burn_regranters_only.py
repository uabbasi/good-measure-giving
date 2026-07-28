"""domestic_burn_rate only means something for charities that regrant.

domestic_burn_rate = 1 - (Schedule F foreign grants / total expenses) claims
to measure "share of expenses staying in the US". It only sees grants MADE TO
foreign organizations. A charity that runs its own overseas programs -- its
own staff and logistics delivering aid abroad -- makes no foreign grants, so
this reports ~100% domestic. It cannot tell "spends abroad directly" apart
from "spends nothing abroad": both look like domestic_burn_rate == 1.0.

Real occurrence: 87-2410117 (Human Appeal, which delivers aid directly in
Gaza) was published as "98% of expenses stay in the US". The same shape hits
large international implementers: 04-2535767 (rate 1.0 on $25k foreign
grants against $50.3M total expenses) and 13-2654926 (93.7% on $220M).

The metric is only meaningful for a charity whose spending model IS
regranting -- where grants (domestic + foreign) are a substantial share of
total expenses, so "no foreign grants" actually implies "nothing left the
country". For a direct implementer, most of the money never shows up as a
grant at all, so Schedule F is silent on where it went. The fix withholds
the metric (and therefore the high_domestic_burn risk flag it drives, which
_check_domestic_burn already skips when the metric is None) rather than
publish a geographic claim the data cannot support.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator


def _metrics(*, foreign_grants, domestic_grants=0, total_expenses):
    return CharityMetricsAggregator.aggregate(
        charity_id=1,
        ein="12-3456789",
        propublica_990={"total_expenses": total_expenses},
        grants_profile={
            "domestic_grants": [{"amount": domestic_grants}] if domestic_grants else [],
            "foreign_grants": [{"amount": foreign_grants}] if foreign_grants else [],
            "total_domestic_grants": domestic_grants,
            "total_foreign_grants": foreign_grants,
        },
    )


class TestDirectImplementersGetNoDomesticBurnClaim:
    def test_human_appeal_shaped_org_gets_no_domestic_burn_figure(self):
        """87-2410117 shape: delivers aid directly, near-zero Schedule F
        grants against real program spend. Must not publish "98% domestic"."""
        metrics = _metrics(foreign_grants=50_000, total_expenses=25_000_000)
        assert metrics.domestic_burn_rate is None

    def test_large_implementer_with_token_foreign_grants_gets_no_figure(self):
        """04-2535767 shape: $25k foreign grants against $50.3M expenses --
        the grants are a rounding error, not how this org spends abroad."""
        metrics = _metrics(foreign_grants=25_000, total_expenses=50_300_000)
        assert metrics.domestic_burn_rate is None

    def test_implementer_with_some_regranting_still_withheld_if_minority(self):
        """13-2654926 shape: real foreign grants ($13.86M) but still a small
        slice of $220M total expenses -- most spending isn't grants at all."""
        metrics = _metrics(foreign_grants=13_860_000, total_expenses=220_000_000)
        assert metrics.domestic_burn_rate is None


class TestGenuineRegrantersStillGetTheFigure:
    def test_a_grantmaking_foundation_gets_a_domestic_burn_figure(self):
        """A charity whose spending model IS regranting -- grants are most of
        its budget -- gets a meaningful domestic_burn_rate."""
        metrics = _metrics(
            foreign_grants=3_000_000, domestic_grants=6_000_000, total_expenses=10_000_000
        )
        assert metrics.domestic_burn_rate is not None
        assert round(metrics.domestic_burn_rate, 2) == 0.70

    def test_no_foreign_grants_at_all_still_yields_none(self):
        """No Schedule F data means no evidence either way, regranter or not."""
        metrics = _metrics(foreign_grants=0, total_expenses=10_000_000)
        assert metrics.domestic_burn_rate is None

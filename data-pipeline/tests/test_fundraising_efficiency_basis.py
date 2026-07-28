"""Cost to raise $1 is fundraising expense over CONTRIBUTIONS, not revenue.

baseline._fundraising_ratio_str divided fundraising_expenses by total_revenue.
Total revenue includes program service revenue, government grants and
investment income -- money fundraising did not raise -- so the published
figure systematically flattered any charity with substantial non-donation
income. Of 143 charities with both figures, 31 understated the true cost by
more than half and 24 by more than five cents per dollar:

  27-4155655   published $0.30, actually $1.32 per donated dollar
  87-2410117   published $0.31, actually $0.99
  46-2431099   published $0.24, actually $0.89

The first of those spends more on fundraising than it raises in
contributions, and the site described that as thirty cents.

This also drove judge errors: the narrative quoted our ratio and cited
Charity Navigator, which publishes its own. The value and its citation now
both belong to the Form 990.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline import _format_fundraising_efficiency, _fundraising_ratio_str


class TestDenominatorIsContributions:
    def test_non_donation_revenue_does_not_dilute_the_ratio(self):
        """$344,086 raised against $3,975,200 of contributions is $0.09.

        The charity's other $19.3M of revenue was not raised by fundraising,
        and including it produced "$0.01" -- a tenfold understatement.
        """
        assert _fundraising_ratio_str(344_086, 3_975_200) == "$0.09"

    def test_a_charity_spending_more_than_it_raises_is_shown_as_such(self):
        assert _fundraising_ratio_str(1_000_000, 755_000) == "$1.32"

    def test_a_genuine_zero_is_still_zero(self):
        assert _fundraising_ratio_str(0, 100_000) == "$0.00"

    def test_a_real_but_tiny_ratio_never_renders_as_zero(self):
        assert _fundraising_ratio_str(241, 100_000) == "<$0.01"

    def test_missing_contributions_yields_no_figure(self):
        assert _fundraising_ratio_str(10_000, None) is None
        assert _fundraising_ratio_str(10_000, 0) is None
        assert _format_fundraising_efficiency(10_000, None) == "N/A"

    def test_missing_expenses_yields_no_figure(self):
        assert _fundraising_ratio_str(None, 100_000) is None


class TestCallSitesPassContributions:
    """Every caller must hand over contributions, not revenue.

    Guarding the call sites rather than only the helper: the helper's
    signature cannot tell the two apart, so a caller left on total_revenue
    would silently keep the old behaviour.
    """

    # Real EIN 13-3626299: revenue dwarfs contributions, so the two
    # denominators give visibly different answers ($0.01 vs $0.09).
    EXPENSES = 344_086
    CONTRIBUTIONS = 3_975_200
    REVENUE = 23_259_494

    def _metrics(self):
        from src.parsers.charity_metrics_aggregator import CharityMetrics

        return CharityMetrics(
            charity_id=0,
            ein="13-3626299",
            name="Test",
            fundraising_expenses=self.EXPENSES,
            total_contributions=self.CONTRIBUTIONS,
            total_revenue=self.REVENUE,
        )

    def test_the_baseline_prompt_carries_the_contributions_based_figure(self):
        """The prompt tells the model to 'use this exact value', so whatever
        lands here is what donors read."""
        import baseline

        from tests.test_baseline_prompt import _fake_scores

        kwargs = baseline._baseline_prompt_kwargs(self._metrics(), _fake_scores(), 4, "CN, PP")
        assert kwargs["fundraising_efficiency"] == "$0.09 per $1 raised", (
            f"got {kwargs['fundraising_efficiency']!r} -- $0.01 means the "
            "call site is still dividing by total revenue"
        )

    def test_the_sanitizer_corrects_toward_the_contributions_based_figure(self):
        """The sanitizer rewrites a wrong ratio in generated prose; it must
        not 'correct' text to the old revenue-based number."""
        from unittest.mock import Mock

        from baseline import sanitize_narrative_metrics

        scores = Mock()
        scores.wallet_tag = "SADAQAH-ELIGIBLE"
        out = sanitize_narrative_metrics(
            {"summary": "The charity spends $0.55 per $1 raised on fundraising."},
            self._metrics(),
            scores,
        )
        text = str(out)
        assert "$0.09" in text, f"sanitizer produced: {text!r}"
        assert "$0.01" not in text

"""A figure that is ours is not a fabrication, however the judge labels it.

The published-value rule settles "the sources disagree": which source a field
comes from is decided before the judge runs, so a narrative reporting our
published figure is correct by construction. It resolves the judge's field name
to a column and compares. Two whole classes of correct claim never reach it,
because the field name does not resolve:

DERIVED FIGURES have no column. EIN 20-0942434 was blocked on "The narrative
states a cost per beneficiary of $76,612.48, but the source data has no such
figure." Literally true — and the figure is program_expenses 68,185,104 divided
by beneficiaries_served_annually 890, both of which we publish, to the cent. It
is arithmetic on our own data. This one has now blocked the charity twice, and
it was the same objection that made gemini-3.1-flash-lite unusable.

NARRATIVE LOCATIONS are not data fields. EIN 81-2169685 was blocked on
baseline_narrative.summary: the narrative said FY2025 revenue of $3,851,438 --
exactly what we published, from the IRS filing that supersedes both mirrors --
and the judge cited the mirrors' FY2023 $4,520,145 against it. "summary" names
a place in the page, not a datum, so there is no column to compare and the rule
stayed silent while a correct page was withheld.

The strictness that matters is kept: a field that DOES resolve is still checked
against its own column, so a narrative quoting the expenses figure under
"revenue" still blocks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import (
    claim_matches_published_value,
    demote_published_figure_errors,
)
from src.judges.schemas.verdict import Severity

BAITULMAAL = {
    "total_revenue": 77434379,
    "total_expenses": 72801062,
    "program_expenses": 68185104,
    "metrics_json": {"beneficiaries_served_annually": 890, "program_expenses": 68185104},
}

ICNAB = {
    "total_revenue": 3851438,
    "total_expenses": 3402000,
    "metrics_json": {"total_revenue": 3851438, "financial_data_tax_year": 2025},
}


class TestADerivedFigureThatReconciles:
    def test_cost_per_beneficiary_is_ours(self):
        assert claim_matches_published_value(
            "cost_per_beneficiary", 76612.48, BAITULMAAL,
            "The narrative states a cost per beneficiary of $76,612.48, but the "
            "source data has no such figure.",
        )

    def test_the_total_expense_basis_is_also_ours(self):
        """Which expense line to divide by is an editorial choice, not a
        fabrication -- the same way the program ratio carries two legitimate
        bases since the GIK fix."""
        assert claim_matches_published_value(
            "cost_per_beneficiary", 81798.95, BAITULMAAL,
            "The narrative states a cost per beneficiary of $81,798.95.",
        )

    def test_a_figure_that_reconciles_to_nothing_still_blocks(self):
        """The rule must not become "any number attached to a derived metric"."""
        assert not claim_matches_published_value(
            "cost_per_beneficiary", 12500.00, BAITULMAAL,
            "The narrative states a cost per beneficiary of $12,500.00.",
        )

    def test_without_a_beneficiary_count_nothing_is_verified(self):
        published = {**BAITULMAAL, "metrics_json": {"program_expenses": 68185104}}
        assert not claim_matches_published_value(
            "cost_per_beneficiary", 76612.48, published,
            "The narrative states a cost per beneficiary of $76,612.48.",
        )


class TestAFigureCitedAgainstANarrativeLocation:
    MESSAGE = (
        "The narrative states total revenue of $3,851,438 in FY2025, but the rich "
        "narrative and source data show total revenue of $4,520,145 in FY2023."
    )

    def test_the_published_figure_is_ours_wherever_it_is_quoted(self):
        assert claim_matches_published_value(
            "baseline_narrative.summary", None, ICNAB, self.MESSAGE
        )

    def test_other_narrative_locations_too(self):
        for field in ("strengths", "amal_score_rationale",
                      "rich_narrative.case_for.summary", "dimension_explanations.impact"):
            assert claim_matches_published_value(field, 3851438, ICNAB, ""), field

    def test_a_figure_we_never_published_still_blocks(self):
        assert not claim_matches_published_value(
            "baseline_narrative.summary", None, ICNAB,
            "The narrative states total revenue of $9,900,000.",
        )


class TestTheStrictnessThatMattersIsKept:
    def test_a_resolvable_field_is_still_checked_against_its_own_column(self):
        """The whole point of the per-column check: quoting our expenses figure
        under 'revenue' is a real error and must stay one."""
        assert not claim_matches_published_value(
            "revenue", 72801062, BAITULMAAL,
            "The narrative states revenue of $72,801,062.",
        )

    def test_a_resolvable_field_still_passes_on_its_own_value(self):
        assert claim_matches_published_value(
            "revenue", 77434379, BAITULMAAL,
            "The narrative states revenue of $77,434,379.",
        )


class TestTheRuleReachesTheScoreJudgeToo:
    """The governing rule lived only in the factual judge.

    EIN 81-2169685 was blocked by the SCORE judge, on
    baseline_narrative.summary, for reporting the FY2025 revenue we publish.
    The factual judge would have waved it through; the score judge had never
    heard of the rule. A page withheld over our own provenance is the same
    defect whichever judge writes it down.
    """


    def _issue(self, severity, field, message):
        from types import SimpleNamespace

        return SimpleNamespace(
            severity=severity, field=field, message=message, claim_value=None
        )

    def test_the_icnab_error_is_demoted(self):
        issues = [self._issue(
            Severity.ERROR, "baseline_narrative.summary",
            "The narrative states total revenue of $3,851,438 in FY2025, but the "
            "source data shows $4,520,145 in FY2023.",
        )]
        assert demote_published_figure_errors(issues, ICNAB) == 1
        assert issues[0].severity == Severity.WARNING

    def test_a_real_contradiction_survives(self):
        issues = [self._issue(
            Severity.ERROR, "baseline_narrative.summary",
            "The narrative states total revenue of $9,900,000.",
        )]
        assert demote_published_figure_errors(issues, ICNAB) == 0
        assert issues[0].severity == Severity.ERROR

    def test_warnings_are_left_alone(self):
        issues = [self._issue(
            Severity.WARNING, "baseline_narrative.summary",
            "The narrative states total revenue of $3,851,438.",
        )]
        assert demote_published_figure_errors(issues, ICNAB) == 0
        assert issues[0].severity == Severity.WARNING

    def test_no_charity_data_demotes_nothing(self):
        """Fail closed: with nothing to compare against, nothing is verified."""
        issues = [self._issue(
            Severity.ERROR, "baseline_narrative.summary",
            "The narrative states total revenue of $3,851,438.",
        )]
        assert demote_published_figure_errors(issues, None) == 0
        assert issues[0].severity == Severity.ERROR

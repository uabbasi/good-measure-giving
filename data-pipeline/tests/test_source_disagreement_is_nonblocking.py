"""Sources disagreeing is a fact to publish, not a reason to withhold a page.

The gate used to work the other way. Eight separate downgrade rules had
accumulated in factual_judge, each one carving out a shape of disagreement that
turned out not to be a defect — units, fiscal years, ratio bases, dollars
against percentages — and each new regeneration found a shape none of them
covered. Two consecutive runs over the same 40 charities blocked 3 and then 7,
barely overlapping, because which shape surfaced depended on the roll.

The rule underneath all of them: the narrative's job is to report what we
published. Whether what we published matches every raw source is a question the
trust hierarchy already answered, deterministically, before the judge ran.

  45-5637293 Noor Project    ProPublica FY2023 revenue $1,759,964 against
                             Charity Navigator's $100,000 for the same year.
                             The election detected the conflict and published
                             the filing — correctly. crawl_quality then blocked
                             the page for "revenue diverges >80% across
                             sources - likely wrong org".

  92-3079413 Humaniti        reserves of -6.1 months on the FY2023 basis we
                             publish and disclose, against -0.23 recomputed by
                             the judge from FY2024 expenses.

So: a claim that matches our published value is never a narrative fault. A
claim that does NOT match it still blocks — that is fabrication, and no
hierarchy excuses it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import claim_matches_published_value
from src.utils.source_trust import (
    canonical_source_for,
    field_group,
    is_adjudicated,
    more_trusted,
)

PUBLISHED = {
    "total_revenue": 1759964,
    "total_expenses": 1530084,
    "working_capital_months": -6.1,
    "board_size": None,
    "metrics_json": {"program_expense_ratio": 0.878, "financial_data_tax_year": 2023},
}


class TestTheTrustHierarchy:
    def test_charity_navigator_leads_the_income_statement(self):
        """ProPublica supplies 2 of 5 fields for 158 of 169 charities."""
        assert canonical_source_for("total_revenue") == "charity_navigator"
        assert canonical_source_for("program_expenses") == "charity_navigator"

    def test_propublica_leads_the_balance_sheet(self):
        """18 of 123 CN balance sheets are visibly corrupt against 2 of PP's."""
        assert canonical_source_for("total_assets") == "propublica"
        assert canonical_source_for("working_capital_months") == "propublica"

    def test_charity_navigator_leads_board_size(self):
        assert canonical_source_for("board_size") == "charity_navigator"

    def test_the_two_financial_groups_are_kept_apart(self):
        assert field_group("total_revenue") == "income_statement"
        assert field_group("total_assets") == "balance_sheet"

    def test_qualified_field_names_still_resolve(self):
        """Judges write field names like 'financials.total_revenue'."""
        assert field_group("financials.total_revenue") == "income_statement"
        assert field_group("narrative.working_capital_months") == "balance_sheet"

    def test_an_unranked_field_is_not_adjudicated(self):
        assert not is_adjudicated("mission_statement")
        assert canonical_source_for("mission_statement") is None

    def test_pairwise_comparison(self):
        assert more_trusted("total_revenue", "propublica", "charity_navigator") == "charity_navigator"
        assert more_trusted("total_assets", "propublica", "charity_navigator") == "propublica"
        assert more_trusted("mission", "propublica", "charity_navigator") is None


class TestAClaimMatchingWhatWePublished:
    def test_the_noor_project_revenue(self):
        """We published ProPublica's figure; CN's $100,000 is the loser of an
        election, not evidence against the narrative."""
        assert claim_matches_published_value("total_revenue", "1759964", PUBLISHED)

    def test_formatting_does_not_hide_the_match(self):
        assert claim_matches_published_value("total_revenue", "$1,759,964", PUBLISHED)
        assert claim_matches_published_value("revenue", "$1.76M", PUBLISHED) is False

    def test_the_humaniti_reserves(self):
        assert claim_matches_published_value("working_capital_months", "-6.1", PUBLISHED)

    def test_a_ratio_published_inside_metrics_json(self):
        assert claim_matches_published_value("program_expense_ratio", "87.8%", PUBLISHED)

    def test_rounding_is_allowed(self):
        assert claim_matches_published_value("total_expenses", "1530000", PUBLISHED)


class TestFabricationStillBlocks:
    def test_a_figure_we_never_published(self):
        assert not claim_matches_published_value("total_revenue", "5000000", PUBLISHED)

    def test_a_value_from_the_losing_source_is_not_a_match(self):
        """CN's $100,000 is precisely what we declined to publish."""
        assert not claim_matches_published_value("total_revenue", "100000", PUBLISHED)

    def test_a_field_we_published_as_null(self):
        assert not claim_matches_published_value("board_size", "2", PUBLISHED)

    def test_a_field_we_do_not_publish_at_all(self):
        assert not claim_matches_published_value("beneficiaries", "40000", PUBLISHED)

    def test_an_unadjudicated_field_never_qualifies(self):
        """The hierarchy only speaks for fields it ranks; everything else is
        left to the ordinary checks."""
        assert not claim_matches_published_value("mission", "1759964", PUBLISHED)

    def test_a_non_numeric_claim(self):
        assert not claim_matches_published_value("total_revenue", "about a million", PUBLISHED)

    def test_no_published_data_at_all(self):
        assert not claim_matches_published_value("total_revenue", "1759964", {})
        assert not claim_matches_published_value("total_revenue", "1759964", None)


class TestTheFigureStatedOnlyInProse:
    """The model routinely leaves claim_value null and puts both numbers in the
    message. EIN 56-2620244: "The narrative claims FY2025 revenue of $3,145,617,
    but the source data for FY2025 shows $3,572,587" — where $3,145,617 is what
    we published and $3,572,587 is ProPublica's FY2024, mislabelled.
    """

    ORLANDO = {"total_revenue": 3145617}

    def test_the_orlando_message(self):
        assert claim_matches_published_value(
            "revenue", None, self.ORLANDO,
            "The narrative claims FY2025 revenue of $3,145,617, but the source data "
            "for FY2025 shows $3,572,587.",
        )

    def test_the_number_cited_against_the_narrative_is_not_read_as_the_claim(self):
        """The decisive case. Matching ANY number in the message would wave
        through a real fabrication whenever the judge quotes our figure as the
        correct one."""
        assert not claim_matches_published_value(
            "revenue", None, self.ORLANDO,
            "The narrative claims revenue of $9,900,000, but the source data shows "
            "$3,145,617.",
        )

    def test_prose_with_no_figure_attributed_to_the_narrative(self):
        assert not claim_matches_published_value(
            "revenue", None, self.ORLANDO, "Revenue could not be verified against any source."
        )

    def test_an_explicit_claim_value_still_takes_precedence(self):
        assert claim_matches_published_value(
            "revenue", "3145617", self.ORLANDO, "unrelated prose mentioning 42"
        )

"""What a narrative may say about zakat and sadaqah.

Sadaqah is the default every charity qualifies for, so stating it tells the
donor nothing and reads as a finding we made. The narrative says nothing about
it at all. Zakat is the higher bar, and the most we know is what the charity's
own site says -- so the strongest permitted form is attributed to that site.
We report the claim; we do not certify it.

The old prompt did the opposite. `_ZAKAT_CONSTRAINT_SADAQAH` ended with "Only
mention sadaqah or general charitable giving", which is an instruction to
assert sadaqah, and the assertions it produced were then flagged as
unsupported claims and cost real charities their pages (63-0598743,
13-1685039). The rich prompt meanwhile offered "verified zakat eligibility" as
a worked example, which is the overclaim in the other direction.
"""

from types import SimpleNamespace

from baseline import (
    _ZAKAT_CONSTRAINT_SADAQAH,
    _ZAKAT_CONSTRAINT_ZAKAT,
    sanitize_narrative_metrics,
)


def _sanitize(text: str, wallet_tag: str = "ZAKAT-ELIGIBLE") -> str:
    """Run one narrative field through the sanitizer with everything present."""
    metrics = SimpleNamespace(
        working_capital_ratio=5.0,
        program_expense_ratio=0.75,
        cn_overall_score=88.0,
        founded_year=1980,
        total_revenue=1_000_000,
        fundraising_expenses=50_000,
        total_contributions=1_000_000,
        name="Test Charity",
        ein="00-0000000",
    )
    scores = SimpleNamespace(wallet_tag=wallet_tag, amal_score=None)
    return sanitize_narrative_metrics({"rationale": text}, metrics, scores)["rationale"]


class TestTheSadaqahConstraintStopsAskingForSadaqah:
    def test_it_no_longer_instructs_the_model_to_mention_sadaqah(self):
        """The line that caused the whole problem."""
        assert "only mention sadaqah" not in _ZAKAT_CONSTRAINT_SADAQAH.lower()

    def test_it_still_forbids_zakat_language(self):
        assert "zakat" in _ZAKAT_CONSTRAINT_SADAQAH.lower()

    def test_it_forbids_sadaqah_language_too(self):
        assert "sadaqah" in _ZAKAT_CONSTRAINT_SADAQAH.lower()


class TestTheZakatConstraintRequiresAttribution:
    def test_it_asks_for_the_website_as_the_source_of_the_claim(self):
        assert "website" in _ZAKAT_CONSTRAINT_ZAKAT.lower()

    def test_it_forbids_certifying_language(self):
        text = _ZAKAT_CONSTRAINT_ZAKAT.lower()
        assert "verified" in text and "confirmed" in text

    def test_it_does_not_invite_sadaqah_language(self):
        assert "only mention sadaqah" not in _ZAKAT_CONSTRAINT_ZAKAT.lower()


class TestTheSanitizerRemovesSadaqahAssertions:
    """Defence in depth: the prompt asks for silence, this enforces it."""

    def test_a_sadaqah_eligible_assertion_is_removed_from_a_sadaqah_narrative(self):
        out = _sanitize(
            "The organization is sadaqah-eligible. It runs food programs.",
            wallet_tag="SADAQAH-ELIGIBLE",
        )

        assert "sadaqah" not in out.lower()
        assert "food programs" in out

    def test_a_sadaqah_assertion_is_removed_from_a_zakat_narrative_too(self):
        """We never assert sadaqah, whatever the tag says."""
        out = _sanitize(
            "Donations are considered sadaqah-eligible. It runs food programs.",
            wallet_tag="ZAKAT-ELIGIBLE",
        )

        assert "sadaqah" not in out.lower()
        assert "food programs" in out

    def test_sadaqah_only_phrasing_is_removed(self):
        out = _sanitize(
            "This charity is sadaqah-only. It runs food programs.",
            wallet_tag="SADAQAH-ELIGIBLE",
        )

        assert "sadaqah" not in out.lower()

    def test_a_mid_sentence_sadaqah_clause_is_removed_without_wrecking_the_rest(self):
        out = _sanitize(
            "It runs food programs, is sadaqah-eligible, and files on time.",
            wallet_tag="SADAQAH-ELIGIBLE",
        )

        assert "sadaqah" not in out.lower()
        assert "food programs" in out
        assert "files on time" in out


class TestExistingZakatStrippingStillHolds:
    def test_zakat_language_is_still_stripped_from_a_sadaqah_narrative(self):
        out = _sanitize(
            "The charity is zakat-eligible. It runs food programs.",
            wallet_tag="SADAQAH-ELIGIBLE",
        )

        assert "zakat" not in out.lower()
        assert "food programs" in out

    def test_attributed_zakat_language_survives_for_a_zakat_charity(self):
        """The permitted form must not be sanitized away."""
        out = _sanitize(
            "The charity's website indicates it is zakat-eligible.",
            wallet_tag="ZAKAT-ELIGIBLE",
        )

        assert "zakat" in out.lower()

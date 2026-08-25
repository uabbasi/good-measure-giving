"""Zakat-eligibility findings must never withhold a charity's page.

The fiqh sets the asymmetry: sadaqah is the default and needs no
substantiation, zakat is the higher bar that does. So neither direction of
disagreement justifies blocking publication.

  - Saying sadaqah when we cannot substantiate zakat is not a defect at all.
    It is the floor, and the floor is always true.
  - Saying sadaqah when the charity does claim zakat understates it. Safe for
    the donor, worth an editorial upgrade, still not a reason to withhold.
  - Saying zakat without substantiation overstates it. That one is a real
    donor-facing problem, and the answer is to fall back to sadaqah and
    publish -- not to withhold the page.

Two things still block, because neither is the eligibility question: a
quantity claim ABOUT zakat (a fabricated "$4.2M distributed as zakat") and an
asnaf-category contradiction, which is about WHICH of the eight categories a
charity serves, not whether it takes zakat at all.

Every message below is a real one taken from judge_verdicts.
"""

from src.judges.zakat_claim_findings import (
    is_zakat_eligibility_finding,
    zakat_claim_overstates,
)


class TestSadaqahClaimsNeverBlock:
    """Shape 1: the narrative says sadaqah and the judge demands proof."""

    def test_splc_sadaqah_tag_read_as_contradicted_by_absent_zakat(self):
        # 63-0598743, factual, 2026-08-16. Cost SPLC its page. The pairing it
        # objects to (SADAQAH-ELIGIBLE + claims_zakat_eligible false) is the
        # default that 71 published charities share.
        assert is_zakat_eligibility_finding(
            "alignment",
            "The narrative claims the charity is SADAQAH-ELIGIBLE based on website "
            "donation pages, but the source data indicates the organization is not "
            "zakat-eligible and claims_zakat_eligible is false.",
        )

    def test_care_usa_same_error_worded_without_the_tag_name(self):
        # 13-1685039, factual, 2026-08-02. Documented in RUN_LEDGER as recurring.
        assert is_zakat_eligibility_finding(
            "claims_zakat_eligible",
            "The narrative claims donations to CARE USA are considered "
            "sadaqah-eligible, but website profile indicates no Zakat/Sadaqah "
            "eligibility claims are explicitly made and data marks it as not "
            "claiming Zakat eligibility.",
        )


class TestUnderstatingNeverBlocks:
    """Shape 2: we say sadaqah, the charity actually claims zakat."""

    def test_bayan_citation_says_zakat_accepted_narrative_says_otherwise(self):
        # 46-2431099, citation, 2026-08-16. The judge was RIGHT -- our data is
        # wrong -- but understating eligibility harms no donor, so it must not
        # withhold the page. Never matched the old `zakat[- ]?eligib` regex:
        # the words are "Zakat is accepted and eligible contributions".
        assert is_zakat_eligibility_finding(
            "alignment",
            "The citation text explicitly states that Zakat is accepted and eligible "
            "contributions support students and programs aligned with zakat "
            "requirements, which contradicts the claim that the charity does not "
            "process zakat payments.",
        )

    def test_website_claims_zakat_but_wallet_tag_does_not(self):
        # 82-2995347, factual.
        assert is_zakat_eligibility_finding(
            "alignment",
            "The charity claims Zakat eligibility on its website, but the wallet tag "
            "is not set to ZAKAT-ELIGIBLE.",
        )

    def test_website_silent_on_zakat_while_tag_says_eligible(self):
        # 99-3032347, factual.
        assert is_zakat_eligibility_finding(
            "alignment",
            "The charity's website does not mention accepting zakat donations, but "
            "the wallet tag indicates it is zakat-eligible.",
        )


class TestOverstatingNeverBlocksEither:
    """Shape 3: we say zakat without support. Downgraded, not withheld."""

    def test_narrative_claims_zakat_eligible_against_the_data(self):
        # 45-5637293, factual, 2026-07-29.
        message = (
            "The narrative claims the charity is zakat-eligible, but the source data "
            "indicates it does not accept zakat."
        )
        assert is_zakat_eligibility_finding("alignment", message)
        assert zakat_claim_overstates("ZAKAT-ELIGIBLE", message)

    def test_narrative_says_charity_accepts_zakat_but_source_denies_it(self):
        # 13-5660870, factual.
        assert is_zakat_eligibility_finding(
            "alignment",
            "The narrative claims the IRC accepts Zakat donations, but the source "
            "data indicates that the charity does not claim zakat eligibility.",
        )


class TestOverstatingIsDistinguishedFromUnderstating:
    """The downgrade only fires when WE are the ones claiming zakat."""

    def test_a_sadaqah_claim_does_not_overstate(self):
        assert not zakat_claim_overstates(
            "SADAQAH-ELIGIBLE",
            "The narrative claims the charity is SADAQAH-ELIGIBLE, but the source "
            "data indicates the organization is not zakat-eligible.",
        )

    def test_understating_does_not_overstate(self):
        # Bayan: the CITATION asserts zakat, our narrative denies it. Nothing
        # to downgrade -- we are already at the floor.
        assert not zakat_claim_overstates(
            "SADAQAH-ELIGIBLE",
            "The citation text explicitly states that Zakat is accepted, which "
            "contradicts the claim that the charity does not process zakat payments.",
        )

    def test_claim_value_may_be_a_bare_boolean(self):
        """claim_value is sometimes 'true'/'false'; fall back to the message."""
        assert zakat_claim_overstates(
            "true",
            "The narrative claims the organization is Zakat-eligible, but the source "
            "data indicates it is not.",
        )


class TestWhatMustStillBlock:
    def test_a_fabricated_zakat_amount_still_blocks(self):
        assert not is_zakat_eligibility_finding(
            "zakat_distributed",
            "The narrative states $4.2 million was distributed as zakat, but the "
            "Form 990 reports no such program.",
        )

    def test_an_asnaf_category_contradiction_still_blocks(self):
        # 20-0310701, score. Which of the eight categories, not whether zakat.
        assert not is_zakat_eligibility_finding(
            "donor_fit_matrix",
            "The Zakat asnaf category in 'donor_fit_matrix' ('fisabilillah') "
            "contradicts the 'zakat_classification' ('riqab').",
        )

    def test_a_miscounted_asnaf_list_still_blocks(self):
        # 38-2846307, score.
        assert not is_zakat_eligibility_finding(
            "narrative",
            "The narrative claims the charity serves 'eight categories of needy "
            "recipients', but the provided data (zakat_asnaf) lists three.",
        )

    def test_an_unrelated_financial_error_is_untouched(self):
        # 27-3175543, factual.
        assert not is_zakat_eligibility_finding(
            "cost_per_beneficiary",
            "The narrative claims a low cost per beneficiary of $7.44 for direct "
            "services, but the provided source data indicates otherwise.",
        )

    def test_a_zakat_amount_wins_over_eligibility_wording(self):
        """Both shapes present: the quantity claim is the blocking one."""
        assert not is_zakat_eligibility_finding(
            "zakat_distributed",
            "The narrative says the charity is zakat-eligible and distributed "
            "$4.2 million in zakat last year, which the filing does not support.",
        )

"""A zakat claim we cannot substantiate is published as sadaqah, not withheld.

Zakat is the higher bar and needs support; sadaqah is the default and needs
none. So the safe correction for an unsupported zakat tag is downward, and the
page still ships. Withholding it helps nobody -- the charity is real and every
other fact about it is fine.

The tag is only half of it. The page renders eligibility from two independent
places: the badge reads wallet_tag, and the prose reads
rich_narrative.donor_fit_matrix.zakat_status. Correcting one and not the other
leaves a SADAQAH badge above a paragraph still asserting zakat, which is worse
than either alone.

Today the corpus is fully consistent (90 ZAKAT-ELIGIBLE, all with
claims_zakat_eligible true), so this is a guard against a future run, not a
repair of current data.
"""

from export import substantiate_wallet_tag


def _evaluation(tag: str, zakat_status: str = "Zakat-eligible under fisabilillah") -> dict:
    return {
        "wallet_tag": tag,
        "amal_score": 61,
        "rich_narrative": {
            "donor_fit_matrix": {
                "zakat_status": zakat_status,
                "cause_area": "EDUCATION",
            }
        },
    }


class TestSubstantiatedZakatIsLeftAlone:
    def test_a_supported_zakat_tag_survives_untouched(self):
        ev = _evaluation("ZAKAT-ELIGIBLE")

        out = substantiate_wallet_tag(ev, {"claims_zakat_eligible": True})

        assert out["wallet_tag"] == "ZAKAT-ELIGIBLE"
        assert out["rich_narrative"]["donor_fit_matrix"]["zakat_status"]

    def test_a_truthy_integer_counts_as_substantiation(self):
        """MySQL hands back 1/0 rather than True/False."""
        out = substantiate_wallet_tag(_evaluation("ZAKAT-ELIGIBLE"), {"claims_zakat_eligible": 1})

        assert out["wallet_tag"] == "ZAKAT-ELIGIBLE"


class TestUnsupportedZakatIsCorrectedDown:
    def test_a_false_claim_downgrades_the_tag(self):
        out = substantiate_wallet_tag(
            _evaluation("ZAKAT-ELIGIBLE"), {"claims_zakat_eligible": False}
        )

        assert out["wallet_tag"] == "SADAQAH-ELIGIBLE"

    def test_a_null_claim_downgrades_the_tag(self):
        """NULL is an absence of evidence, which is not substantiation."""
        out = substantiate_wallet_tag(
            _evaluation("ZAKAT-ELIGIBLE"), {"claims_zakat_eligible": None}
        )

        assert out["wallet_tag"] == "SADAQAH-ELIGIBLE"

    def test_missing_charity_data_downgrades_the_tag(self):
        out = substantiate_wallet_tag(_evaluation("ZAKAT-ELIGIBLE"), None)

        assert out["wallet_tag"] == "SADAQAH-ELIGIBLE"

    def test_the_downgrade_also_clears_the_zakat_prose(self):
        """Otherwise a SADAQAH badge sits above prose still claiming zakat."""
        out = substantiate_wallet_tag(
            _evaluation("ZAKAT-ELIGIBLE"), {"claims_zakat_eligible": False}
        )

        assert not out["rich_narrative"]["donor_fit_matrix"]["zakat_status"]

    def test_the_downgrade_keeps_the_rest_of_the_narrative(self):
        out = substantiate_wallet_tag(
            _evaluation("ZAKAT-ELIGIBLE"), {"claims_zakat_eligible": False}
        )

        assert out["rich_narrative"]["donor_fit_matrix"]["cause_area"] == "EDUCATION"
        assert out["amal_score"] == 61

    def test_the_downgrade_does_not_mutate_the_caller_s_dict(self):
        """Copy-on-write: the summary builder reads this same dict."""
        ev = _evaluation("ZAKAT-ELIGIBLE")

        substantiate_wallet_tag(ev, {"claims_zakat_eligible": False})

        assert ev["wallet_tag"] == "ZAKAT-ELIGIBLE"
        assert ev["rich_narrative"]["donor_fit_matrix"]["zakat_status"]


class TestSadaqahIsNeverUpgraded:
    def test_a_sadaqah_tag_stays_sadaqah_even_when_the_charity_claims_zakat(self):
        """Understating is safe. Upgrading is an editorial call, not export's."""
        out = substantiate_wallet_tag(
            _evaluation("SADAQAH-ELIGIBLE", zakat_status=""),
            {"claims_zakat_eligible": True},
        )

        assert out["wallet_tag"] == "SADAQAH-ELIGIBLE"


class TestDegenerateInputs:
    def test_a_missing_evaluation_is_returned_as_is(self):
        assert substantiate_wallet_tag(None, {"claims_zakat_eligible": True}) is None

    def test_an_evaluation_without_a_narrative_downgrades_cleanly(self):
        out = substantiate_wallet_tag({"wallet_tag": "ZAKAT-ELIGIBLE"}, None)

        assert out["wallet_tag"] == "SADAQAH-ELIGIBLE"

    def test_an_absent_wallet_tag_is_left_alone(self):
        out = substantiate_wallet_tag({"amal_score": 40}, None)

        assert out.get("wallet_tag") is None

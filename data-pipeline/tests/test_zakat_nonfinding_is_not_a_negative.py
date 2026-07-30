"""A zakat search that found nothing has not established that zakat is refused.

The Noor Project (EIN 45-5637293) stored this discovered zakat record:

    accepts_zakat: false
    accepts_zakat_evidence: null
    accepts_zakat_url: null
    direct_page_verified: false
    zakat_verification_confidence: 0
    zakat_verification_sources: 0

Zero sources, zero confidence, no evidence, no URL -- the verification established
nothing at all -- yet it asserts `false`. The factual judge then read that as
evidence against the website, and blocked publication: "The charity claims to be
zakat-eligible on its website, but the source data indicates it does not accept
zakat" (claim_value true, source_value false), while its own evidence line noted
"the website explicitly states it accepts zakat and provides a calculator".

This is the same shape as the BBB bug fixed earlier in this run, and the codebase
already holds the principle explicitly for BBB: a verified negative must never be
readable as a failed check, and a non-finding must never be readable as a negative.
`accepts_zakat: bool` cannot express "unknown", so the non-finding path had no
honest value to return.

Emitting null is logic-neutral: the aggregator reads it as
`discovered_zakat.get("accepts_zakat", False)` in a truthiness context, where None
and False behave identically, and `web_collector.py` already uses None for this same
field. What changes is only that the payload stops ASSERTING a negative it never
measured -- matching the project's own rule that missing data stays NULL.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.zakat_verification_service import ZakatVerification


def _nonfinding():
    """Exactly the Noor Project shape."""
    return ZakatVerification(
        accepts_zakat=False,
        accepts_zakat_evidence=None,
        accepts_zakat_url=None,
        zakat_categories_served=[],
        confidence=0.0,
        source_count=0,
        cost_usd=0.0,
        direct_page_verified=False,
    )


class TestANonFindingIsStoredAsUnknown:
    def test_zero_sources_zero_confidence_no_evidence_is_not_a_false(self):
        assert _nonfinding().to_dict()["accepts_zakat"] is None, (
            "a search that established nothing must not assert that zakat is refused"
        )

    def test_it_stays_falsy_so_downstream_logic_is_unchanged(self):
        """The aggregator branches on truthiness; None must not flip any of it."""
        assert not _nonfinding().to_dict()["accepts_zakat"]


class TestRealVerdictsAreUntouched:
    def test_a_genuine_positive_is_preserved(self):
        v = ZakatVerification(
            accepts_zakat=True,
            accepts_zakat_evidence="Give your Zakat",
            accepts_zakat_url="https://example.org/zakat",
            zakat_categories_served=["fuqara"],
            confidence=0.9,
            source_count=3,
            cost_usd=0.001,
            direct_page_verified=True,
        )
        assert v.to_dict()["accepts_zakat"] is True

    def test_a_measured_negative_is_still_a_negative(self):
        """The judge SHOULD be able to contradict a narrative when we actually
        looked and found the charity does not accept zakat."""
        v = ZakatVerification(
            accepts_zakat=False,
            accepts_zakat_evidence="Donations fund UK operations only",
            accepts_zakat_url="https://example.org/donate",
            zakat_categories_served=[],
            confidence=0.8,
            source_count=4,
            cost_usd=0.001,
            direct_page_verified=False,
        )
        assert v.to_dict()["accepts_zakat"] is False

    def test_a_negative_backed_by_sources_but_no_evidence_string_is_kept(self):
        """Evidence text can be absent while the search still had grounding."""
        v = ZakatVerification(
            accepts_zakat=False,
            accepts_zakat_evidence=None,
            accepts_zakat_url=None,
            zakat_categories_served=[],
            confidence=0.6,
            source_count=5,
            cost_usd=0.001,
            direct_page_verified=False,
        )
        assert v.to_dict()["accepts_zakat"] is False

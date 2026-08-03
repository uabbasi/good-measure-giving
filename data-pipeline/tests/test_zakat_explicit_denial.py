"""An explicit "we looked, and no" outranks a keyword we cannot find again.

corroborate_zakat_claim treats a website keyword hit as self-corroborating:

    has_website_zakat_evidence = accepts_zakat and "zakat" in zakat_evidence

but zakat_evidence is written BY the keyword scanner — web_collector.py builds
it as f"Found '{keyword}' on {url}", and every keyword in the list contains the
word "zakat". So the test asks whether a string the signal generated mentions
the term the signal matched on. It is always true, and a single unverified
signal passes corroboration by restating itself.

Nothing in the function ever consults the discovery agent's finding. On EIN
20-3060929 (Texas Muslim Women's Foundation) the agent searched and wrote:

    "there is no explicit mention on their website or in the provided snippets
     that they accept zakat donations... A mention of 'Zakat ministry' in one
     search result refers to a different Islamic Association in Garland, TX"

while the website signal claimed "Found 'give zakat' on tmwf.org/ways-to-give/".
The 182,124 bytes of website content we stored contain the word "zakat" zero
times, and direct_page_verified was False at 0.3 confidence. The organization
is tagged ZAKAT-ELIGIBLE on the live site.

A donor whose zakat goes to an ineligible recipient may not have discharged the
obligation, so the two errors are not symmetric and the weak signal should lose.
CLAUDE.md already says so — accepts_zakat is on the hallucination-prone list and
its stated rule is "Require explicit zakat page/calculator."

Narrow on purpose. Direct page verification and a definitive name ("Zakat
Foundation") still win: those are not keyword guesses. And a discovery result
that simply found nothing is NOT a denial — recording a non-finding as a
negative finding is the exact mistake this pipeline has made repeatedly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CrossSourceCorroborator

SITE = "https://tmwf.org"
KEYWORD_ONLY_WEBSITE = {
    "accepts_zakat": True,
    "zakat_evidence": "Found 'give zakat' on https://tmwf.org/ways-to-give/",
    "zakat_url": "https://tmwf.org/ways-to-give/",
}
AGENT_DENIAL = {
    "zakat": {
        "accepts_zakat": False,
        "accepts_zakat_evidence": (
            "There is no explicit mention on their website that they accept zakat "
            "donations. A mention of 'Zakat ministry' in one search result refers to "
            "a different Islamic Association in Garland, TX."
        ),
        "zakat_verification_confidence": 0.3,
        "direct_page_verified": False,
    }
}


def _corroborate(discovered, website, name="Texas Muslim Womens Foundation Inc"):
    return CrossSourceCorroborator.corroborate_zakat_claim(
        ein="20-3060929", name=name, discovered_profile=discovered,
        website_profile=website, charity_website=SITE,
    )


class TestTheDenialWins:
    def test_the_tmwf_case_no_longer_passes(self):
        assert not _corroborate(AGENT_DENIAL, KEYWORD_ONLY_WEBSITE).passed

    def test_the_reason_records_why(self):
        result = _corroborate(AGENT_DENIAL, KEYWORD_ONLY_WEBSITE)
        assert "search" in result.reason.lower() or "contradict" in result.reason.lower()


class TestStrongSignalsStillWin:
    def test_direct_page_verification_beats_the_denial(self):
        discovered = {
            "zakat": {
                **AGENT_DENIAL["zakat"],
                "direct_page_verified": True,
                "accepts_zakat_url": "https://tmwf.org/zakat/",
            }
        }
        assert _corroborate(discovered, KEYWORD_ONLY_WEBSITE).passed

    def test_a_definitive_name_beats_the_denial(self):
        assert _corroborate(AGENT_DENIAL, KEYWORD_ONLY_WEBSITE, name="Zakat Foundation of America").passed


class TestANonFindingIsNotADenial:
    """The recurring mistake in this pipeline: recording "we found nothing" as
    "we found that it is false"."""

    def test_no_discovery_data_at_all(self):
        assert _corroborate(None, KEYWORD_ONLY_WEBSITE).passed

    def test_an_empty_zakat_section(self):
        assert _corroborate({"zakat": {}}, KEYWORD_ONLY_WEBSITE).passed

    def test_false_with_no_evidence_text_is_not_a_denial(self):
        discovered = {"zakat": {"accepts_zakat": False, "accepts_zakat_evidence": ""}}
        assert _corroborate(discovered, KEYWORD_ONLY_WEBSITE).passed

    def test_a_null_accepts_zakat_is_not_a_denial(self):
        discovered = {"zakat": {"accepts_zakat": None, "accepts_zakat_evidence": "unclear"}}
        assert _corroborate(discovered, KEYWORD_ONLY_WEBSITE).passed


class TestUnrelatedChargesAreUnaffected:
    def test_a_charity_with_real_multi_source_evidence_still_passes(self):
        website = {
            "accepts_zakat": True,
            "zakat_evidence": "Zakat policy page states funds are distributed to the eight asnaf",
            "zakat_url": "https://example.org/zakat-policy/",
            "donation_methods": ["Zakat", "Sadaqah"],
            "mission": "We distribute zakat to those in need",
        }
        discovered = {
            "zakat": {
                "accepts_zakat": True,
                "accepts_zakat_evidence": "The organization accepts zakat donations",
                "zakat_verification_confidence": 0.9,
                "accepts_zakat_url": "https://example.org/zakat-policy/",
            }
        }
        assert _corroborate(discovered, website, name="Example Relief").passed

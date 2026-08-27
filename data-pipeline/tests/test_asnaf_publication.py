"""A stale value gets suppressed. A good one gets published.

The asnaf matcher once did a bare substring test, so 'amil' matched inside
'Family' and 17 charities were filed as zakat administrators -- The Family &
Youth Institute, Palestine Children's Relief Fund and World Central Kitchen
among them. The response was to ship zakatClassification and asnafServed as
null for EVERY charity until the matcher was fixed and the corpus re-baselined.

The matcher was fixed (ZakatScorer now word-boundary matches and takes the
highest-hit category). The blanket null was never lifted, so 96 charities carry
a classification in DoltDB and 0 of 169 published pages show one. 75 of those
96 are values the bug never touched: fuqara 38, fi_sabilillah 25, masakin 5,
ibn_sabil 5, riqab 2.

Re-running the fixed matcher over the stored text turns 17 of 17 'amil' rows
into None and leaves 2 of 4 'muallaf' standing, so the stale set is real and
narrow. _sanitize_stale_asnaf already suppresses exactly that set at the export
boundary. The blanket null is the part with no remaining justification: it
discards 75 good values to hide 21 bad ones the targeted guard already catches.
"""

from export import _STALE_ASNAF_VALUES, _sanitize_stale_asnaf, build_charity_summary


def _summary(classification):
    """Minimal inputs for build_charity_summary; only the asnaf path is asserted."""
    charity = {"ein": "12-3456789", "name": "Test Charity"}
    evaluation = {
        "state": "generated",
        "amal_score": 61,
        "wallet_tag": "ZAKAT-ELIGIBLE",
        "confidence_tier": "HIGH",
        "zakat_classification": classification,
    }
    charity_data = {"primary_category": "HUMANITARIAN", "cause_tags": ["fuqara"]}
    return build_charity_summary(charity, charity_data, evaluation, {}, False, {})


class TestGoodClassificationsReachTheIndex:
    def test_fuqara_is_published(self):
        assert _summary("fuqara")["zakatClassification"] == "fuqara"

    def test_fi_sabilillah_is_published(self):
        assert _summary("fi_sabilillah")["zakatClassification"] == "fi_sabilillah"

    def test_a_charity_with_no_classification_publishes_none(self):
        assert _summary(None)["zakatClassification"] is None


class TestStaleClassificationsStaySuppressed:
    def test_amil_is_withheld_until_the_corpus_is_rebaselined(self):
        """17 of 17 stored 'amil' rows are the substring bug, not real amil."""
        assert _summary("amil")["zakatClassification"] is None

    def test_muallaf_is_withheld(self):
        """2 of 4 are legitimate, but we cannot tell which without re-baselining."""
        assert _summary("muallaf")["zakatClassification"] is None

    def test_the_stale_set_is_exactly_the_two_bug_affected_values(self):
        assert _STALE_ASNAF_VALUES == {"amil", "muallaf"}


class TestTheDetailBoundaryGuardStillWorks:
    def test_it_nulls_a_stale_nested_asnaf_category(self):
        ev = {"score_details": {"zakat": {"asnaf_category": "amil"}}}
        _sanitize_stale_asnaf(ev)

        assert ev["score_details"]["zakat"]["asnaf_category"] is None

    def test_it_leaves_a_good_nested_asnaf_category_alone(self):
        ev = {"score_details": {"zakat": {"asnaf_category": "fuqara"}}}
        _sanitize_stale_asnaf(ev)

        assert ev["score_details"]["zakat"]["asnaf_category"] == "fuqara"


class TestAsnafServedComesFromTheFilterData:
    """It must agree with /browse, which filters on cause_tags."""

    def test_it_publishes_the_asnaf_subset_of_cause_tags(self):
        from export import _asnaf_from_cause_tags

        got = _asnaf_from_cause_tags(
            {"cause_tags": ["fuqara", "masakin", "usa", "muslim-led", "palestine"]}
        )

        assert got == ["fuqara", "masakin"]

    def test_a_charity_with_no_asnaf_tag_publishes_none_not_empty(self):
        """The frontend types this string[] | null and reads [] as 'serves none'."""
        from export import _asnaf_from_cause_tags

        assert _asnaf_from_cause_tags({"cause_tags": ["usa", "muslim-led"]}) is None

    def test_missing_charity_data_is_none(self):
        from export import _asnaf_from_cause_tags

        assert _asnaf_from_cause_tags(None) is None

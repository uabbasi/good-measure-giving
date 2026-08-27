"""A discovery run that finds no asnaf categories must not erase the ones we had.

Asnaf tags reach cause_tags through a non-deterministic step:

    cause_tags  <- detect_cause_tags(zakat_categories=...)
                <- discovered_profile["zakat"]["zakat_categories_served"]
                <- the DISCOVER phase (agent search)

detect_cause_tags itself is a deterministic filter against ZAKAT_ASNAF_TAGS.
The instability is upstream, and nothing carried the previous answer forward, so
a run where discovery came back empty silently dropped the tags.

That is what the v6.0.0 regen did to 15 charities -- Palestine Children's Relief
Fund, IRUSA Waqf, Maristan, Qalam Education Fund and others lost every asnaf tag
and vanished from every Zakat asnaf facet on /browse. Corpus totals fell fuqara
89->81, masakin 88->81, fisabilillah 50->43. Nothing errored; the lists just got
shorter. Regenerating IRUSA Waqf later restored all four tags, which confirms
the tags were recoverable and the loss was a bad discovery run, not a decision.

Losing a known tag is a downgrade, and this pipeline already refuses downgrades
elsewhere -- apply_regression_guard restores financial fields that recomputed
non-null -> null, and the raw layer carries content forward rather than letting
a thin re-observation overwrite a good one. Asnaf tags get the same treatment.

Region and other cause tags are deliberately NOT carried forward: they derive
from geographic_coverage and mission text rather than from agent discovery, so
their movement is usually a real re-derivation.
"""

from synthesize import carry_forward_asnaf_tags


class TestAsnafTagsSurviveAnEmptyDiscovery:
    def test_an_empty_run_keeps_the_tags_we_already_had(self):
        kept, restored = carry_forward_asnaf_tags(
            new_tags=["muslim-led", "faith-based"],
            prior_tags=["fuqara", "masakin", "muslim-led"],
        )

        assert set(kept) >= {"fuqara", "masakin"}
        assert sorted(restored) == ["fuqara", "masakin"]

    def test_pcrf_case_all_four_asnaf_recovered(self):
        """Palestine Children's Relief Fund lost fisabilillah/fuqara/masakin."""
        kept, restored = carry_forward_asnaf_tags(
            new_tags=["palestine", "muslim-led"],
            prior_tags=["fisabilillah", "fuqara", "masakin", "palestine"],
        )

        assert set(kept) == {"fisabilillah", "fuqara", "masakin", "palestine", "muslim-led"}
        assert sorted(restored) == ["fisabilillah", "fuqara", "masakin"]


class TestItOnlyRestoresWhatWasLost:
    def test_a_run_that_found_its_own_asnaf_is_untouched(self):
        kept, restored = carry_forward_asnaf_tags(
            new_tags=["fuqara", "masakin", "usa"],
            prior_tags=["fuqara", "masakin"],
        )

        assert sorted(kept) == ["fuqara", "masakin", "usa"]
        assert restored == []

    def test_a_newly_discovered_asnaf_is_kept_alongside_the_old(self):
        kept, restored = carry_forward_asnaf_tags(
            new_tags=["fuqara", "muallaf"],
            prior_tags=["fuqara", "masakin"],
        )

        assert set(kept) == {"fuqara", "masakin", "muallaf"}
        assert restored == ["masakin"]

    def test_no_prior_data_means_nothing_to_restore(self):
        kept, restored = carry_forward_asnaf_tags(new_tags=["usa"], prior_tags=None)

        assert kept == ["usa"]
        assert restored == []


class TestNonAsnafTagsAreLeftAlone:
    def test_a_dropped_region_tag_is_not_restored(self):
        """Region tags derive from geographic_coverage; their churn is usually real."""
        kept, restored = carry_forward_asnaf_tags(
            new_tags=["muslim-led"],
            prior_tags=["kashmir", "india", "muslim-led"],
        )

        assert "kashmir" not in kept
        assert "india" not in kept
        assert restored == []

    def test_a_dropped_intervention_tag_is_not_restored(self):
        kept, restored = carry_forward_asnaf_tags(
            new_tags=["faith-based"],
            prior_tags=["systemic-change", "scalable-model", "faith-based"],
        )

        assert sorted(kept) == ["faith-based"]
        assert restored == []


class TestDegenerateInputs:
    def test_empty_new_tags_still_recovers_asnaf(self):
        kept, restored = carry_forward_asnaf_tags(new_tags=[], prior_tags=["fuqara"])

        assert kept == ["fuqara"]
        assert restored == ["fuqara"]

    def test_both_empty_is_empty(self):
        assert carry_forward_asnaf_tags(new_tags=None, prior_tags=None) == ([], [])

    def test_output_is_sorted_and_deduplicated(self):
        kept, _ = carry_forward_asnaf_tags(
            new_tags=["usa", "usa", "fuqara"], prior_tags=["fuqara", "masakin"]
        )

        assert kept == sorted(set(kept))

    def test_case_is_normalised_so_a_cased_prior_tag_is_not_double_added(self):
        kept, restored = carry_forward_asnaf_tags(new_tags=["Fuqara"], prior_tags=["fuqara"])

        assert kept == ["fuqara"]
        assert restored == []

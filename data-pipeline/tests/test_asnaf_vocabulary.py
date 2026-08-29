"""asnafServed must be spelled the way /browse filters, or it cannot match.

Three spellings of the eight asnaf exist in this codebase:

  website/src/components/gmg/adapters/regions.ts  ASNAF_TAGS
      the display authority -- owns the labels and the /browse facet keys
  data-pipeline/synthesize.py                     ZAKAT_ASNAF_TAGS
      the producer -- what detect_cause_tags is allowed to keep
  data-pipeline/export.py                         _ASNAF_TAG_VALUES
      the publication filter -- what reaches charities.json

The first version of the export set was written from memory rather than read
off the frontend. It had six values: it omitted ibn-sabil and amilin entirely,
so those two categories could never have reached the site, and it spelled the
indebted "gharimin" while synthesize emits "gharimeen".

No charity carries any of the mismatched spellings today, so nothing was
actually lost -- but a single discovery run returning one would have produced a
tag stored in the database and invisible on the site, with no error anywhere.
"""

import re
from pathlib import Path

REGIONS_TS = Path(__file__).parents[2] / "website/src/components/gmg/adapters/regions.ts"


def frontend_asnaf_keys() -> set[str]:
    """The facet keys, read out of regions.ts so drift fails here."""
    block = re.search(
        r"export const ASNAF_TAGS: Record<string, string> = \{(.*?)\n\}",
        REGIONS_TS.read_text(),
        re.S,
    )
    assert block, "ASNAF_TAGS not found in regions.ts"
    return {m.group(1) for m in re.finditer(r"^\s*'?([a-z-]+)'?\s*:", block.group(1), re.M)}


class TestExportAgreesWithTheFacet:
    def test_it_publishes_exactly_the_facet_keys(self):
        from export import _ASNAF_TAG_VALUES

        assert _ASNAF_TAG_VALUES == frontend_asnaf_keys()

    def test_all_eight_asnaf_are_covered(self):
        from export import _ASNAF_TAG_VALUES

        assert len(_ASNAF_TAG_VALUES) == 8

    def test_ibn_sabil_and_amilin_reach_the_index(self):
        """Neither was in the first version of the set."""
        from export import _asnaf_from_cause_tags

        got = _asnaf_from_cause_tags({"cause_tags": ["ibn-sabil", "amilin", "usa"]})

        assert got == ["amilin", "ibn-sabil"]

    def test_a_non_asnaf_tag_is_never_published_as_one(self):
        from export import _asnaf_from_cause_tags

        assert _asnaf_from_cause_tags({"cause_tags": ["orphans", "refugees"]}) is None

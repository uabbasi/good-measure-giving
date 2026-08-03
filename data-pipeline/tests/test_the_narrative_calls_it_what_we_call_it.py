"""The narrative must call the organisation by the name we publish.

CARE USA was blocked from publication on 2026-08-02 by a single judge error:
the narrative called it "CAREHQ" eleven times. That name is not a typo we
introduced — it is what Candid's profile page yields, and
CharityMetricsAggregator.aggregate() rebuilds `metrics.name` from scratch on
every synth run with a hardcoded Candid-first priority. So the system carried
two independent names: `charities.name` ("CARE USA"), which the index, the
detail page header and the judge's ground truth all use, and
`metrics_json.name` ("CAREHQ"), which only the narrative prompt read.

84 of 169 charities differ between the two. Most differences are harmless
(legal name vs. curated short name), but several are plainly wrong —
"Oxfam AmericaHQ", "Feeding AmericaHQ", "Muslim Bar Association of New Yorkinc".
Any of them can strand a page: the judge compares the narrative against the
authoritative record, and a name mismatch is an error, and errors fail closed.

The curated record wins, exactly as it does for the website URL. A scraped
profile does not get to rename a charity in prose we publish under its name.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline import build_charity_metrics  # noqa: E402

EIN = "13-1685039"


def _metrics_json(name: str) -> dict:
    return {"ein": EIN, "name": name}


def test_the_curated_name_beats_the_scraped_one():
    """The stored blob says CAREHQ; we publish CARE USA."""
    metrics = build_charity_metrics(
        ein=EIN,
        charity={"ein": EIN, "name": "CARE USA"},
        charity_data={"metrics_json": _metrics_json("CAREHQ")},
        raw_sources={},
    )

    assert metrics.name == "CARE USA"


def test_it_holds_on_the_re_aggregation_path_too():
    """No metrics_json — the aggregator runs Candid-first and still must not win."""
    metrics = build_charity_metrics(
        ein=EIN,
        charity={"ein": EIN, "name": "CARE USA"},
        charity_data=None,
        raw_sources={"candid": {"candid_profile": {"name": "CAREHQ"}}},
    )

    assert metrics.name == "CARE USA"


def test_a_charity_row_with_no_real_name_does_not_clobber():
    """Some rows carry the EIN as a placeholder name. Those defer to the sources.

    Guards the inverse failure: overriding unconditionally would publish
    narratives that call the organisation "13-1685039".
    """
    for placeholder in ("", None, EIN, f"EIN {EIN}", "Unknown"):
        metrics = build_charity_metrics(
            ein=EIN,
            charity={"ein": EIN, "name": placeholder},
            charity_data={"metrics_json": _metrics_json("Cooperative For Assistance")},
            raw_sources={},
        )

        assert metrics.name == "Cooperative For Assistance", f"placeholder {placeholder!r} clobbered the source name"


def test_a_missing_charity_row_is_survivable():
    """build_charity_metrics is called with whatever the repo returned, including {}."""
    metrics = build_charity_metrics(
        ein=EIN,
        charity={},
        charity_data={"metrics_json": _metrics_json("CAREHQ")},
        raw_sources={},
    )

    assert metrics.name == "CAREHQ"

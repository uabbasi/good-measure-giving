"""Deciding a rich narrative is stale must actually replace it.

`generate_rich_for_pipeline` compares the stored narrative's embedded
amal_score against the evaluation and, on disagreement, sets `stale_reason`
and falls through to generation. But it then called
`generator.generate(ein, force=force)` with the ORIGINAL force — False —
and RichNarrativeGenerator.generate has its own existence check that returns
the stored narrative untouched whenever force is falsy. So the staleness
verdict was reached and then thrown away: the same stale copy came back,
reported as a success with cost 0.

test_rich_reentrancy_staleness.py does not catch this. It asserts only that
`skipped` is unset, and `skipped` is never set on the stale path — the
assertion holds whether or not anything is regenerated.

Found while tracing why CARE USA's rich narrative still called the
organisation "CAREHQ" after a full clean regeneration on 2026-08-02.
"""

from unittest.mock import Mock, patch

import rich_phase
from rich_phase import generate_rich_for_pipeline

EIN = "13-1685039"


def _run(existing):
    """Call the phase with a mocked generator; return (result, generator_mock)."""
    repo = Mock()
    repo.get.return_value = existing
    generator = Mock()
    generator.generate.return_value = {"all_citations": []}
    generator.last_generation_cost = 0.0
    with patch.object(rich_phase, "RichNarrativeGenerator", return_value=generator):
        result = generate_rich_for_pipeline(EIN, repo, force=False)
    return result, generator


def test_a_stale_score_actually_reaches_the_generator_as_a_force():
    """Otherwise the generator's own existence check vetoes our own verdict."""
    result, generator = _run(
        {
            "amal_score": 58,
            "rich_narrative": {"amal_scores": {"amal_score": 47}, "headline": "x"},
        }
    )

    assert not result.get("skipped")
    generator.generate.assert_called_once()
    assert generator.generate.call_args.kwargs.get("force") is True, (
        "staleness was detected but the generator was asked not to regenerate, "
        "so it handed back the stale narrative unchanged"
    )


def test_an_explicit_force_still_reaches_the_generator():
    repo = Mock()
    repo.get.return_value = {"amal_score": 58, "rich_narrative": {"amal_scores": {"amal_score": 58}}}
    generator = Mock()
    generator.generate.return_value = {"all_citations": []}
    generator.last_generation_cost = 0.0
    with patch.object(rich_phase, "RichNarrativeGenerator", return_value=generator):
        result = generate_rich_for_pipeline(EIN, repo, force=True)

    assert not result.get("skipped")
    assert generator.generate.call_args.kwargs.get("force") is True


def test_a_current_narrative_still_short_circuits():
    """Regression: re-running a converged charity must stay free."""
    result, generator = _run(
        {
            "amal_score": 75,
            "rich_narrative": {"amal_scores": {"amal_score": 75}, "headline": "x"},
        }
    )

    assert result.get("skipped") is True
    assert result["cost_usd"] == 0.0
    generator.generate.assert_not_called()

"""A rich narrative that exists is not necessarily a rich narrative that is CURRENT.

`generate_rich_for_pipeline`'s re-entrancy check skipped regeneration whenever a
rich narrative was present, asking only whether one EXISTS -- never whether it
still matches the evaluation it embeds.

`rich_content["amal_scores"]` is stamped deterministically from the evaluation row
(not written by the LLM), so once baseline re-scores a charity, the stored rich
narrative carries the OLD score until it is regenerated. streaming_runner's phase
gate correctly decides rich must re-run when baseline ran, but it only passes
force=True for --force-all/--force-phase, so this inner check silently overrode
the gate's decision.

Observed on International Institute of Islamic Thought (EIN 23-2202414) in
batch10: evaluations.amal_score = 58 while rich_narrative.amal_scores.amal_score =
47 with impact_tier "BELOW_AVERAGE". The score judge blocked publication for the
contradiction and was correct to -- the narrative really did disagree with the
score. The charity had passed the previous run, so the failure appears and
disappears with whether the score happens to move.

Fixing the check itself (rather than the streaming_runner call site) means every
caller benefits, including rich_phase.py's standalone entry point.
"""

from unittest.mock import Mock, patch

import pytest
import rich_phase
from rich_phase import generate_rich_for_pipeline

EIN = "23-2202414"


@pytest.fixture(autouse=True)
def _no_live_generation():
    """Keep these tests off the real database.

    eval_repo is mocked, but RichNarrativeGenerator was not: it loads the
    baseline through its OWN repository and writes what it generates. While
    the stale path asked for force=False the generator's existence check made
    that a harmless read. Once the stale path started forcing (as it must, or
    the staleness verdict is discarded), the suite began regenerating EIN
    23-2202414's rich narrative for real — rewriting live content without the
    judge re-running, so the content hash no longer matched and the export
    gate dropped a published charity out of the index.
    """
    generator = Mock()
    generator.generate.return_value = {"all_citations": []}
    generator.last_generation_cost = 0.0
    with patch.object(rich_phase, "RichNarrativeGenerator", return_value=generator):
        yield generator


def _eval_repo(existing):
    repo = Mock()
    repo.get.return_value = existing
    return repo


def _rich(score, tier="AVERAGE"):
    return {"amal_scores": {"amal_score": score, "impact_tier": tier}}


class TestStaleRichNarrativeIsRegenerated:
    def test_embedded_score_disagreeing_with_the_evaluation_forces_regeneration(self):
        """The IIIT shape: stored rich says 47, evaluation says 58."""
        repo = _eval_repo({"amal_score": 58, "rich_narrative": _rich(47, "BELOW_AVERAGE")})
        result = generate_rich_for_pipeline(EIN, repo, force=False)
        assert not result.get("skipped"), (
            "a rich narrative embedding a stale amal_score must be regenerated, "
            "not skipped as 'already has rich narrative'"
        )

    def test_matching_score_still_short_circuits(self):
        """Regression: genuine re-entrancy must survive. A current narrative is
        not regenerated, so re-running a converged charity stays free."""
        repo = _eval_repo({"amal_score": 58, "rich_narrative": _rich(58)})
        result = generate_rich_for_pipeline(EIN, repo, force=False)
        assert result.get("skipped") is True
        assert result["success"] is True
        assert result["cost_usd"] == 0.0

    def test_absent_rich_narrative_is_generated(self):
        repo = _eval_repo({"amal_score": 58, "rich_narrative": None})
        result = generate_rich_for_pipeline(EIN, repo, force=False)
        assert not result.get("skipped")

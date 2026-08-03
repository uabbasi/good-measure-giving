"""A third consensus roll that cannot change the verdict is not worth buying.

The score and factual judges each run CONSENSUS_ROLLS=3 independent LLM
rolls and gate on a MAJORITY of rolls reporting at least one error. The
signal each roll contributes is binary: "did this roll find any error".

With three rolls the majority is two, so once the first two rolls agree the
third cannot move the outcome:

    both rolls found errors    -> count is already 2 >= 2, errors stand
    neither roll found errors  -> count can reach at most 1 < 2, they do not

Measured over 107 judge runs on 2026-08-02, the score judge averaged $0.2571
per charity — 79% of all judge spend and about two thirds of the cost of a
whole pipeline run. Two of its three rolls is the floor for a majority; the
third is only informative when the first two disagree, which is exactly the
flip-flopping case the consensus exists to absorb.

Stopping early when the first two agree leaves the publication gate's
decision identical by construction and drops a third of the dominant cost on
the common path, where a charity passes cleanly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.consensus import rolls_can_still_matter  # noqa: E402


def test_two_clean_rolls_settle_it():
    """Neither found an error; a third could reach at most 1 of 3."""
    assert rolls_can_still_matter([False, False], total_rolls=3) is False


def test_two_erroring_rolls_settle_it():
    """Both found errors; the majority is already reached."""
    assert rolls_can_still_matter([True, True], total_rolls=3) is False


def test_disagreement_buys_the_third_roll():
    """1-1 is exactly the flip-flop the consensus exists to resolve."""
    assert rolls_can_still_matter([True, False], total_rolls=3) is True
    assert rolls_can_still_matter([False, True], total_rolls=3) is True


def test_one_roll_is_never_enough():
    assert rolls_can_still_matter([True], total_rolls=3) is True
    assert rolls_can_still_matter([False], total_rolls=3) is True


def test_no_rolls_yet():
    assert rolls_can_still_matter([], total_rolls=3) is True


def test_a_completed_set_is_done():
    assert rolls_can_still_matter([True, False, True], total_rolls=3) is False


def test_it_generalises_beyond_three():
    """k=5 needs 3 for a majority; 3 agreeing settles it, 2-1 does not."""
    assert rolls_can_still_matter([True, True, True], total_rolls=5) is False
    assert rolls_can_still_matter([False, False, False], total_rolls=5) is False
    assert rolls_can_still_matter([True, True, False], total_rolls=5) is True


def test_the_decision_is_unchanged_by_stopping():
    """The property that makes this safe, stated directly.

    For every way the remaining rolls could land, the majority verdict is the
    same as the one already determined.
    """
    import itertools

    for total in (3, 5):
        for taken in range(1, total + 1):
            for seen in itertools.product([True, False], repeat=taken):
                if rolls_can_still_matter(list(seen), total_rolls=total):
                    continue
                settled = sum(seen) >= (total // 2) + 1
                remaining = total - taken
                for rest in itertools.product([True, False], repeat=remaining):
                    full = list(seen) + list(rest)
                    assert (sum(full) >= (len(full) // 2) + 1) == settled, (
                        f"stopping after {seen} changed the verdict when the rest were {rest}"
                    )

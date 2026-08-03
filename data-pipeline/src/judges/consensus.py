"""When a majority consensus has already been settled.

The score and factual judges each run k independent LLM rolls and gate on a
MAJORITY of rolls reporting at least one error. Each roll contributes a
single binary signal, so the verdict is often decided before every roll has
been bought — with k=3 the majority is 2, and two agreeing rolls fix the
outcome whatever the third would have said.

The score judge averaged $0.2571 per charity over 107 runs on 2026-08-02,
79% of all judge spend. A third of that is spent on rolls that cannot change
anything.
"""

from typing import Sequence


def rolls_can_still_matter(seen: Sequence[bool], total_rolls: int) -> bool:
    """Whether any remaining roll could still change the majority verdict.

    `seen` is one bool per completed roll: did that roll report an error.
    Returns False once the outcome is fixed, so the caller can stop.

    Assumes the caller gates on `sum(all_rolls) >= len(all_rolls) // 2 + 1`,
    which is what both judges do. Note the majority is computed over the rolls
    that COMPLETE, so stopping early also lowers the threshold — two clean
    rolls give majority 2 and count 0, and two erroring rolls give majority 2
    and count 2. Both agree with the k-roll answer.
    """
    remaining = total_rolls - len(seen)
    if remaining <= 0:
        return False

    errors = sum(1 for roll in seen if roll)
    majority_of_all = (total_rolls // 2) + 1

    # Already enough error-rolls that the rest cannot take it back.
    if errors >= majority_of_all:
        return False
    # Not enough rolls left to reach a majority even if every one errored.
    if errors + remaining < majority_of_all:
        return False
    return True

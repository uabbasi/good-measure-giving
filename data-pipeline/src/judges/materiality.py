"""Which metrics legitimately carry two different values.

Some figures we publish have a second, equally defensible value: ours,
computed from IRS data, and Charity Navigator's own, computed on a different
basis and often over a different fiscal year. Fundraising efficiency and
working capital are the two that keep surfacing. A donor reads "$0.09 per $1
raised" and "$0.04 per $1 raised" as the same story, so the gap is not a fact
anyone got wrong and must not withhold a charity's page.

Shared by the factual and score judges so the two cannot drift apart -- they
already did once, and it cost five charities their publication: eb8ef36 moved
fundraising efficiency onto a contributions denominator, widening the gap
against CN; 205b206 taught the factual judge to tolerate that, but the score
judge kept blocking on the same disagreement.

The two judges act on this differently, by design. The factual judge has
structured claim_value/source_value, so it can compare the numbers and still
block when they tell opposite stories (a sign flip, an order of magnitude).
The score judge has only prose and cannot recover the operands reliably --
"$0.10 to raise every $1 ... indicates $0.05" offers [0.10, 1, 0.05, 1] with
no way to tell the "per $1" from a real value of 1 -- so it defers instead of
ruling blind.
"""

import re

METHODOLOGY_DIVERGENT_FIELD_RE = re.compile(
    r"fundraising.{0,3}efficienc|cost.{0,20}raise|"
    r"\$\d[\d.]*\s*(?:for|to|per)\s+(?:every\s+)?\$?1|working.{0,3}capital",
    re.IGNORECASE,
)


def is_methodology_divergent(text: str) -> bool:
    """Does this finding concern a metric with two legitimate values?"""
    return bool(METHODOLOGY_DIVERGENT_FIELD_RE.search(text or ""))

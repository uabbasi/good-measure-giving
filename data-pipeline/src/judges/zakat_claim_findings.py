"""Whether a judge finding is about zakat/sadaqah ELIGIBILITY, and which way.

The fiqh sets an asymmetry the gate has to respect. Sadaqah is the default:
any charity may receive it, so a sadaqah claim needs no substantiation and
cannot be contradicted by the absence of a zakat claim. Zakat is the higher
bar and does need support. Neither direction of disagreement justifies
withholding a page:

  understating (we say sadaqah, they claim zakat)  -> safe for the donor
  overstating  (we say zakat, unsubstantiated)     -> fall back to sadaqah

Two earlier attempts at this lived as phrase lists -- factual_judge's
`wallet.{0,3}tag` and citation_judge's `zakat[- ]?eligib` -- and each kept
missing paraphrases. `zakat[- ]?eligib` never matched Bayan's "Zakat is
accepted and eligible contributions" because the two words are not adjacent,
and that one blocking error cost the charity its page. Matching the SHAPE of
the assertion rather than a fixed phrase is what this module does instead.
"""

import re

# A quantity assertion ABOUT zakat is a different claim than eligibility and
# must keep blocking: a fabricated "$4.2M distributed as zakat" is exactly the
# kind of number a donor would act on.
_ZAKAT_QUANTITY_RE = re.compile(
    r"\$\s?[\d,.]+|\b\d[\d,.]*\s*(?:million|m\b|billion)", re.IGNORECASE
)

# Which of the eight asnaf a charity serves is a separate question from
# whether it takes zakat at all, and needs no rule of its own: an asnaf
# finding ("the asnaf category 'fisabilillah' contradicts 'riqab'") asserts
# nothing about eligibility, so it matches none of the patterns below and
# keeps blocking. A finding that asserts BOTH is treated as the eligibility
# question, since that is the part that would otherwise cost a page.
_Z = r"(?:zakat|sadaqah)"

# The ways a finding asserts that a charity is (or is not) zakat/sadaqah
# eligible. Each alternative is a shape, not a phrase.
_ELIGIBILITY_PATTERNS = [
    # "zakat-eligible", "sadaqah eligible", "ZAKAT-ELIGIBLE"
    rf"{_Z}[-\s]?eligib",
    # "eligible for zakat"
    rf"eligible\s+for\s+{_Z}",
    # "zakat eligibility", "Zakat/Sadaqah eligibility claims"
    rf"{_Z}[\w/]*\s+eligibilit",
    # "accepts zakat", "accepting zakat donations", "process zakat payments",
    # "claim zakat eligibility" -- the verb close to the noun.
    rf"(?:accept|process|claim|solicit|take)\w*\s+(?:\w+\s+){{0,3}}{_Z}",
    # "Zakat is accepted", "sadaqah is claimed" -- the noun close to the verb.
    rf"{_Z}\s+(?:\w+\s+){{0,3}}(?:accepted|claimed|processed|solicited)",
    # The column and the tag that encode the answer.
    r"claims_zakat_eligible",
    r"wallet.{0,3}tag",
]
_ELIGIBILITY_RE = re.compile("|".join(_ELIGIBILITY_PATTERNS), re.IGNORECASE)

# "we say zakat" -- used to tell overstating from understating.
_ZAKAT_ELIGIBLE_RE = re.compile(r"zakat[-\s]?eligib|eligible\s+for\s+zakat", re.IGNORECASE)
_SADAQAH_RE = re.compile(r"sadaqah", re.IGNORECASE)


def is_zakat_eligibility_finding(
    field: str,
    message: str,
    claim_value: str | None = None,
    source_value: str | None = None,
) -> bool:
    """Is this finding about whether the charity is zakat/sadaqah eligible?

    True means it must not block publication, whichever way it points. False
    leaves the finding exactly as the judge filed it.
    """
    text = " ".join(str(p) for p in (field, message, claim_value, source_value) if p)
    if _ZAKAT_QUANTITY_RE.search(text):
        return False
    if _ELIGIBILITY_RE.search(text):
        return True
    # No eligibility assertion: an asnaf finding is about categories, not
    # eligibility, and is none of this module's business either way.
    return False


def _claim_clause(message: str) -> str:
    """The part of the message stating what WE claimed, before the rebuttal."""
    return re.split(r"\bbut\b|\bwhich contradicts\b|\bhowever\b", message or "", maxsplit=1)[0]


def zakat_claim_overstates(claim_value: str | None, message: str) -> bool:
    """Did WE assert zakat eligibility that the finding says is unsupported?

    Only this direction warrants the downgrade to sadaqah. Understating (we
    said sadaqah, the charity claims zakat) needs an editorial upgrade, not a
    correction, and the floor is already true in the meantime.
    """
    claim = str(claim_value or "")
    # claim_value is authoritative when it names a tag.
    if _ZAKAT_ELIGIBLE_RE.search(claim):
        return True
    if _SADAQAH_RE.search(claim):
        return False
    # Otherwise it is a bare "true"/"false" and the message carries the claim.
    head = _claim_clause(message)
    if _SADAQAH_RE.search(head):
        return False
    return bool(_ZAKAT_ELIGIBLE_RE.search(head))

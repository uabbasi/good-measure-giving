"""Deterministic display-name normalization for exported charity names.

Bounded scope (curation overlay contract #2): only ALL-CAPS raw names (no
lowercase letters anywhere) get normalized; anything already mixed-case passes
through unchanged so hand-entered names are never mangled. Exceptions the
derivation cannot infer live in config/curation_overrides.yaml.
"""

import re

# Verified acronyms that must stay uppercase when title-casing.
ACRONYMS = frozenset(
    {
        "USA", "US", "UK", "UN", "UNRWA", "IMRC", "IMANA", "ICNA", "CAIR",
        "PCRF", "HHRD", "IRUSA", "LLC", "DBA", "II", "III", "IV",
    }
)

# Tokens with a fixed casing that is neither an acronym nor plain title-case.
SPECIAL = {"INC": "Inc", "INC.": "Inc."}

# Particles kept lowercase when they are not the first token.
PARTICLES = frozenset({"of", "the", "for", "and", "in", "a", "al", "bin"})


def _title_segment(segment: str) -> str:
    """Title-case one hyphen/apostrophe-delimited segment at its first letter."""
    for i, ch in enumerate(segment):
        if ch.isalpha():
            return segment[:i] + ch.upper() + segment[i + 1 :].lower()
    return segment


def _convert_token(token: str, is_first: bool) -> str:
    upper = token.upper()
    if upper in SPECIAL:
        return SPECIAL[upper]
    if upper in ACRONYMS:
        return upper
    # Tokens with digits (501(C)(3)) or internal periods (U.S.) pass through.
    if any(ch.isdigit() for ch in token):
        return token
    if "." in token.rstrip("."):
        return token
    if not is_first and token.lower() in PARTICLES:
        return token.lower()
    # Title-case hyphen/apostrophe segments separately (Al-Anon, O'Brien).
    parts = re.split(r"([-'])", token)
    return "".join(part if part in {"-", "'"} else _title_segment(part) for part in parts)


def to_display_name(raw: str) -> str:
    """Normalize an ALL-CAPS raw charity name into display casing.

    Input containing any lowercase letter is returned UNCHANGED — only
    ALL-CAPS (or caps + punctuation/digits) raw names are normalized.
    """
    if not raw:
        return raw
    if any(ch.islower() for ch in raw):
        return raw
    return " ".join(_convert_token(token, i == 0) for i, token in enumerate(raw.split()))

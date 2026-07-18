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


# Punctuation stripped from a token's edges before the ACRONYMS lookup.
_EDGE_PUNCT = '()[]{}",;:.'


def _convert_token(token: str, is_first: bool) -> str:
    upper = token.upper()
    if upper in SPECIAL:
        return SPECIAL[upper]
    # Acronyms match even when wrapped in punctuation: (HHRD), USA.
    if upper.strip(_EDGE_PUNCT) in ACRONYMS:
        return upper
    # Tokens with digits (501(C)(3)) or internal periods (U.S.) pass through.
    if any(ch.isdigit() for ch in token):
        return token
    if "." in token.rstrip("."):
        return token
    if not is_first and token.lower() in PARTICLES:
        return token.lower()
    # Title-case hyphen/apostrophe segments separately (Al-Anon, O'Brien),
    # except a single letter after an apostrophe is possessive: CHILDREN'S -> Children's.
    parts = re.split(r"([-'])", token)
    out = []
    for i, part in enumerate(parts):
        if part in {"-", "'"}:
            out.append(part)
        elif i > 0 and parts[i - 1] == "'" and len(part) == 1 and part.isalpha():
            out.append(part.lower())
        else:
            out.append(_title_segment(part))
    return "".join(out)


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

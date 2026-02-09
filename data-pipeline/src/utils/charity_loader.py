"""
Shared utility for loading charity lists from pilot_charities.txt.

Consolidates the duplicated load_pilot_charities / load_charities_from_file
functions that existed across crawl.py, baseline.py, synthesize.py, export.py,
rich_strategic_phase.py, streaming_runner.py, and benchmarks/runner.py.
"""

from dataclasses import dataclass
from typing import Optional

from .ein_utils import normalize_ein, validate_and_format


@dataclass
class CharityEntry:
    """A parsed charity entry from pilot_charities.txt."""

    name: str
    ein: str  # Normalized XX-XXXXXXX format
    website: Optional[str] = None
    flags_text: str = ""  # Raw flags string (e.g., "HIDE:TRUE")


def load_charity_entries(file_path: str) -> list[CharityEntry]:
    """Load full charity entries from pilot_charities.txt.

    Format: Name | EIN | URL | Flags | Comments
    Lines starting with # are ignored.

    Returns:
        List of CharityEntry with normalized EINs, deduped.
    """
    entries = []
    seen_eins: set[str] = set()

    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue

            ein_raw = parts[1]
            normalized = normalize_ein(ein_raw)
            if not normalized or normalized in seen_eins:
                continue

            seen_eins.add(normalized)
            entries.append(
                CharityEntry(
                    name=parts[0],
                    ein=normalized,
                    website=parts[2] if len(parts) >= 3 and parts[2] else None,
                    flags_text=" ".join(parts[3:]) if len(parts) > 3 else "",
                )
            )

    return entries


def load_pilot_eins(file_path: str) -> list[str]:
    """Load just the EINs from pilot_charities.txt.

    Convenience wrapper for the common case where only EINs are needed.
    """
    return [e.ein for e in load_charity_entries(file_path)]


def load_charities_from_file(file_path: str, logger=None) -> list[dict]:
    """Load charity list from file with strict EIN validation.

    Unlike load_charity_entries (which silently skips bad EINs), this raises
    ValueError on malformed EINs to force input cleanup before pipeline runs.

    Format: Name | EIN | URL | Flags | Comments
    Lines starting with # are ignored.

    Returns:
        List of dicts with keys: name, ein, website.
    """
    charities = []
    seen_eins: set[str] = set()

    with open(file_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue

            name = parts[0]
            ein = parts[1]
            website = parts[2] if len(parts) >= 3 and parts[2] else None

            if not ein or ein == "N/A" or ein.startswith("N/A"):
                continue

            is_valid, normalized_ein, error = validate_and_format(ein)
            if not is_valid:
                raise ValueError(f"Line {line_num}: Invalid EIN '{ein}' for {name}: {error}")

            if normalized_ein in seen_eins:
                msg = f"Line {line_num}: Duplicate EIN {normalized_ein} for {name}, skipping"
                if logger:
                    logger.warning(msg)
                else:
                    print(f"Warning: {msg}")
                continue

            seen_eins.add(normalized_ein)
            charities.append({"name": name, "ein": normalized_ein, "website": website})

    return charities

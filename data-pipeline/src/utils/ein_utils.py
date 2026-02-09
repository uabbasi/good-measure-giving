"""
EIN (Employer Identification Number) utilities.

Provides consistent formatting and validation for EIN numbers.
EIN format: XX-XXXXXXX (9 digits with hyphen after first 2)
"""

import re
from typing import Optional, Tuple

# EIN regex patterns for extraction
EIN_PATTERNS = [
    # Standard format with hyphen: 12-3456789
    r"\b(\d{2})-(\d{7})\b",
    # No hyphen: 123456789
    r"\b(\d{9})\b",
    # With context (EIN:, Tax ID:, etc.)
    r"(?:EIN|Tax\s*ID|Federal\s*Tax\s*ID|Tax\s*Identification\s*Number)\s*[:#]?\s*(\d{2})-?(\d{7})",
]


def normalize_ein(ein: str) -> Optional[str]:
    """
    Normalize EIN to standard XX-XXXXXXX format.

    Args:
        ein: EIN string in any format (with or without hyphen)

    Returns:
        Normalized EIN in XX-XXXXXXX format, or None if invalid

    Examples:
        >>> normalize_ein("123456789")
        '12-3456789'
        >>> normalize_ein("12-3456789")
        '12-3456789'
        >>> normalize_ein("12 3456789")
        '12-3456789'
        >>> normalize_ein("invalid")
        None
    """
    if not ein:
        return None

    # Remove all non-digit characters
    digits = re.sub(r"\D", "", str(ein))

    # Must be exactly 9 digits
    if len(digits) != 9:
        return None

    # Basic validation: first two digits should be valid IRS prefixes
    # Valid prefixes are generally 01-99, with some reserved ranges
    prefix = int(digits[:2])
    if prefix < 1 or prefix > 99:
        return None

    # Format as XX-XXXXXXX
    return f"{digits[:2]}-{digits[2:]}"


def is_valid_ein(ein: str) -> bool:
    """
    Check if EIN is valid.

    Args:
        ein: EIN string to validate

    Returns:
        True if valid EIN format, False otherwise
    """
    return normalize_ein(ein) is not None


def extract_ein_from_text(text: str) -> Optional[str]:
    """
    Extract and normalize EIN from text content.

    Looks for EIN patterns in text and returns the first valid one found.

    Args:
        text: Text content to search

    Returns:
        Normalized EIN if found, None otherwise
    """
    if not text:
        return None

    # Try patterns in order of specificity
    # First try patterns with context (EIN:, Tax ID:, etc.)
    context_pattern = r"(?:EIN|Tax\s*ID|Federal\s*Tax\s*ID|Tax\s*Identification\s*Number)[:\s#]*(\d{2})-?(\d{7})"
    match = re.search(context_pattern, text, re.IGNORECASE)
    if match:
        ein = match.group(1) + match.group(2)
        return normalize_ein(ein)

    # Try pattern with 501(c)(3) context
    c3_pattern = r"501\s*\(\s*c\s*\)\s*\(\s*3\s*\)[^\d]*(\d{2})-?(\d{7})"
    match = re.search(c3_pattern, text, re.IGNORECASE)
    if match:
        ein = match.group(1) + match.group(2)
        return normalize_ein(ein)

    # Try standard format with hyphen
    hyphen_pattern = r"\b(\d{2})-(\d{7})\b"
    match = re.search(hyphen_pattern, text)
    if match:
        ein = match.group(1) + match.group(2)
        return normalize_ein(ein)

    return None


def compare_eins(ein1: str, ein2: str) -> bool:
    """
    Compare two EINs for equality (normalizes both first).

    Args:
        ein1: First EIN
        ein2: Second EIN

    Returns:
        True if EINs match after normalization
    """
    norm1 = normalize_ein(ein1)
    norm2 = normalize_ein(ein2)

    if norm1 is None or norm2 is None:
        return False

    return norm1 == norm2


def ein_to_digits(ein: str) -> Optional[str]:
    """
    Convert EIN to digits-only format (for database lookups, API calls).

    Args:
        ein: EIN in any format

    Returns:
        9-digit string without hyphen, or None if invalid
    """
    normalized = normalize_ein(ein)
    if normalized:
        return normalized.replace("-", "")
    return None


def validate_and_format(ein: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate EIN and return formatted version with error message.

    Args:
        ein: EIN to validate

    Returns:
        Tuple of (is_valid, formatted_ein, error_message)

    Examples:
        >>> validate_and_format("123456789")
        (True, '12-3456789', None)
        >>> validate_and_format("12345")
        (False, None, 'EIN must be exactly 9 digits')
    """
    if not ein:
        return False, None, "EIN is required"

    # Remove whitespace
    ein = str(ein).strip()

    # Remove all non-digit characters for validation
    digits = re.sub(r"\D", "", ein)

    if len(digits) < 9:
        return False, None, f"EIN must be exactly 9 digits (got {len(digits)})"

    if len(digits) > 9:
        return False, None, f"EIN must be exactly 9 digits (got {len(digits)})"

    # Check for obviously invalid patterns
    if digits == "000000000":
        return False, None, "EIN cannot be all zeros"

    if len(set(digits)) == 1:
        return False, None, "EIN cannot be all same digit"

    formatted = f"{digits[:2]}-{digits[2:]}"
    return True, formatted, None

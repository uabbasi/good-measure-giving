"""
Base validation utilities shared across source validators.
"""


def normalize_ein(v: str) -> str:
    """
    Normalize EIN to XX-XXXXXXX format.

    Accepts XXXXXXXXX or XX-XXXXXXX format and normalizes to XX-XXXXXXX.

    Args:
        v: EIN string in either format

    Returns:
        Normalized EIN in XX-XXXXXXX format

    Raises:
        ValueError: If EIN is invalid (wrong length, non-digits, empty)
    """
    if not v:
        raise ValueError("EIN is required")

    # Remove any existing hyphens
    ein_digits = v.replace("-", "").strip()

    if len(ein_digits) != 9:
        raise ValueError("EIN must be 9 digits")

    if not ein_digits.isdigit():
        raise ValueError("EIN must contain only digits")

    # Format as XX-XXXXXXX
    return f"{ein_digits[:2]}-{ein_digits[2:]}"

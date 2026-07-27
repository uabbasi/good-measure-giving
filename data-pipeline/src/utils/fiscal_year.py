"""Shared fiscal-year age arithmetic used by scorers, prompts, and judges."""

from datetime import date
from typing import Optional


def filing_age_years(fiscal_year: Optional[int], today_year: Optional[int] = None) -> Optional[int]:
    """Age in whole years of a fiscal-year filing, or None if fiscal_year is unknown."""
    if not isinstance(fiscal_year, int):
        return None
    if today_year is None:
        today_year = date.today().year
    return today_year - fiscal_year

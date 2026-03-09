from datetime import datetime, timezone


NEW_ORG_YEARS = 5


def current_utc_year() -> int:
    return datetime.now(timezone.utc).year


def is_new_org(founded_year: int | None, *, current_year: int | None = None) -> bool:
    """Return True when an org is within the NEW_ORG window."""
    if not founded_year:
        return False
    year = current_year if current_year is not None else current_utc_year()
    return year - founded_year <= NEW_ORG_YEARS

"""A figure from a year the charity did not elect must not reach the narrative.

The rich narrative prompt already withholds Charity Navigator's income
statement when CN's fiscal_year disagrees with the elected
financial_data_tax_year (_cn_financials_match_elected_year / _fy_bound). The
same prompt hands over ProPublica's form_990 block unguarded, and once the
IRS filing became canonical ProPublica stopped being the source that decides
the year — so a charity can elect FY2025 from its IRS filing while
ProPublica is still on FY2023.

Both years then arrive in one prompt, one of them framed as "the" fiscal
year by data_vintage_note(financial_data_tax_year), and the model pairs the
wrong amount with it:

    ICNAB (81-2169685), 2026-08-02
      elected IRS FY2025 total_revenue  3,851,438   <- baseline said this
      ProPublica    FY2023 total_revenue 4,520,145
      rich narrative: "total revenue of $4,520,145 in FY2025 filings"

The score judge caught the contradiction between the two tiers and blocked
publication, which is the system working. But the two narratives should not
have been able to disagree: this is a figure from one source published under
another source's year label, the defect the canonical-source rule exists to
prevent, arriving through a prompt rather than through a column.

Guarding it the same way CN is guarded — withhold the income statement when
the years disagree, keep the non-financial fields, which are not
year-bound — is what this asserts.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.rich_narrative_generator import RichNarrativeGenerator  # noqa: E402

match = RichNarrativeGenerator._financials_match_elected_year


def test_a_disagreeing_year_is_withheld():
    """The ICNAB shape: ProPublica on 2023, charity elected 2025."""
    assert match(2023, 2025) is False


def test_the_same_year_is_publishable():
    assert match(2025, 2025) is True


def test_string_years_still_compare():
    """tax_year arrives as a string from some sources."""
    assert match("2025", 2025) is True
    assert match(2025, "2025") is True
    assert match("2023", "2025") is False


def test_an_unknown_year_on_either_side_is_permissive():
    """Mirrors the CN guard: absent a year to compare, do not withhold.

    Withholding on unknown would strip figures from every charity whose
    elected year is not recorded, which is a larger harm than the one being
    prevented.
    """
    assert match(None, 2025) is True
    assert match(2023, None) is True
    assert match(None, None) is True


def test_ungarbled_by_junk():
    assert match("not-a-year", 2025) is True

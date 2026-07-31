"""Which source wins when sources disagree, and why.

Two sources reporting different numbers for the same organization is the normal
case, not a fault. It happens because they transcribe different filings, cover
different fiscal years, and extract with different reliability. The pipeline
therefore does not ask "do the sources agree" — it picks one, says so, and
publishes the disagreement.

Nothing here may gate publication. A source disagreement is resolved by this
table and recorded as a discrepancy; the only thing that blocks a page is a
narrative that misreports what we ourselves published.

The rankings are measured, not assumed. Across the 169 charities in the index:

  income statement    ProPublica supplies exactly two of five fields for 158 of
                      169 charities and is a year behind on 134 of 168. It
                      cannot carry the page. Charity Navigator has the full
                      functional-expense breakdown and the newer year, so it
                      leads — but only when its year is actually newer, since
                      five charities were publishing CN figures OLDER than the
                      filing already in hand (Hikma Health showed FY2019 over
                      FY2023).

  balance sheet       The reverse. Of the 123 charities where both carry one,
                      18 of Charity Navigator's are visibly corrupt against 2
                      of ProPublica's: $100,000 and $500,000 asset figures
                      appearing four times over, and lost magnitudes (EIN
                      11-3013369 reads $113,404 where the 990 reads
                      $27,427,805). ProPublica leads.

  same-year ties      To ProPublica. When both describe the same filing, PP is
                      exact to the dollar and CN's errors are recognizably
                      round — $5,400,000 against PP's $11,189,635, $900,000
                      against $102,250. They agree within 1% on 13 of the 15
                      same-year pairs; the two misses are both CN's.

  board size          Charity Navigator leads. Candid's list is parsed by
                      splitting each entry on whitespace, which lands inside
                      people's names ({"name": "Ayman", "title": "Khalil"}) and
                      undercounts: every Candid board under three shows the
                      misparse, and CN is larger in all four cases where it has
                      a figure.

  zakat eligibility   A verified zakat page on the charity's own domain, then a
                      definitive name ("Zakat Foundation"), then an explicit
                      search finding, and last a bare keyword match — which is
                      the weakest signal and the one most often wrong. A donor
                      whose zakat reaches an ineligible recipient may not have
                      discharged the obligation, so on this field the ordering
                      is deliberately conservative rather than merely accurate.
"""

from typing import Optional

PROPUBLICA = "propublica"
CHARITY_NAVIGATOR = "charity_navigator"
CANDID = "candid"
WEBSITE = "website"
DISCOVERY = "discovered"

# Field group -> sources, most trusted first.
TRUST_ORDER: dict[str, tuple[str, ...]] = {
    "income_statement": (CHARITY_NAVIGATOR, PROPUBLICA),
    "balance_sheet": (PROPUBLICA, CHARITY_NAVIGATOR),
    "board": (CHARITY_NAVIGATOR, CANDID),
    "governance": (PROPUBLICA, CHARITY_NAVIGATOR, CANDID),
    "zakat_eligibility": (WEBSITE, DISCOVERY),
}

_FIELD_GROUPS: dict[str, str] = {
    "total_revenue": "income_statement",
    "total_expenses": "income_statement",
    "program_expenses": "income_statement",
    "admin_expenses": "income_statement",
    "administrative_expenses": "income_statement",
    "fundraising_expenses": "income_statement",
    "program_expense_ratio": "income_statement",
    "revenue": "income_statement",
    "expenses": "income_statement",
    "total_assets": "balance_sheet",
    "total_liabilities": "balance_sheet",
    "net_assets": "balance_sheet",
    "working_capital_months": "balance_sheet",
    "working_capital_ratio": "balance_sheet",
    "working_capital": "balance_sheet",
    "reserves_months": "balance_sheet",
    "board_size": "board",
    "independent_board_members": "board",
    "board_members": "board",
    "claims_zakat_eligible": "zakat_eligibility",
    "accepts_zakat": "zakat_eligibility",
    "ceo_compensation": "governance",
    "employees_count": "governance",
}


# Judges name fields in their own words ("revenue", "rating", "working
# capital"); these are the columns those names refer to.
_FIELD_COLUMNS: dict[str, str] = {
    "revenue": "total_revenue",
    "expenses": "total_expenses",
    "administrative_expenses": "admin_expenses",
    "working_capital": "working_capital_months",
    "working_capital_ratio": "working_capital_months",
    "reserves_months": "working_capital_months",
    "assets": "total_assets",
    "liabilities": "total_liabilities",
    "board_members": "board_size",
    "accepts_zakat": "claims_zakat_eligible",
}


def published_column_for(field: Optional[str]) -> Optional[str]:
    """The charity_data column a judge's field name refers to."""
    if not field:
        return None
    key = str(field).strip().lower().replace(" ", "_").replace("-", "_")
    key = key.rsplit(".", 1)[-1]
    if key in _FIELD_COLUMNS:
        return _FIELD_COLUMNS[key]
    if key in _FIELD_GROUPS:
        return key
    for known in sorted(_FIELD_COLUMNS, key=len, reverse=True):
        if known in key:
            return _FIELD_COLUMNS[known]
    for known in sorted(_FIELD_GROUPS, key=len, reverse=True):
        if known in key:
            return known
    return None


def field_group(field: Optional[str]) -> Optional[str]:
    """The trust group a field belongs to, or None if it is not adjudicated."""
    if not field:
        return None
    key = str(field).strip().lower().replace(" ", "_").replace("-", "_")
    if key in _FIELD_GROUPS:
        return _FIELD_GROUPS[key]
    # LLM-written field names arrive qualified ("financials.total_revenue",
    # "narrative.revenue_claim"); match on the longest known suffix/substring
    # rather than failing closed, since failing closed here means blocking.
    for known, group in sorted(_FIELD_GROUPS.items(), key=lambda kv: -len(kv[0])):
        if known in key:
            return group
    return None


def canonical_source_for(field: Optional[str]) -> Optional[str]:
    """The source that wins this field when sources disagree."""
    group = field_group(field)
    order = TRUST_ORDER.get(group or "")
    return order[0] if order else None


def is_adjudicated(field: Optional[str]) -> bool:
    """Is this a field where a source disagreement is resolved by the table?

    True means a disagreement about it is a provenance fact to publish, not a
    defect to block on.
    """
    return field_group(field) is not None


def more_trusted(field: Optional[str], left: str, right: str) -> Optional[str]:
    """Which of two sources wins for this field. None if neither is ranked."""
    order = TRUST_ORDER.get(field_group(field) or "")
    if not order:
        return None
    ranks = {source: index for index, source in enumerate(order)}
    if left not in ranks or right not in ranks:
        return None
    return left if ranks[left] <= ranks[right] else right

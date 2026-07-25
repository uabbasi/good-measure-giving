"""Deterministic coherence checks on a charity's financial columns.

Shared by synthesize's regression guard and the recovery tool: both restore a
historical value onto a row whose other fields came from a different run, and
both must refuse a restore that produces a balance sheet which cannot exist.
"""

from typing import Optional

FINANCIAL_FIELDS = frozenset(
    {"total_revenue", "total_expenses", "total_assets", "total_liabilities", "net_assets"}
)

# Sources round and restate; only flag a gap too large to be rounding.
_IDENTITY_TOLERANCE_RATIO = 0.01


def balance_sheet_violations(
    total_assets: Optional[float],
    total_liabilities: Optional[float],
    net_assets: Optional[float],
) -> list[str]:
    """Names of balance-sheet invariants this triple breaks. Empty == coherent.

    Unknown (None) values cannot violate anything — absence is not a
    contradiction. A genuine 0 IS evaluated (Task A2 made zeros survive).
    """
    out: list[str] = []
    if total_assets is not None and net_assets is not None and net_assets > total_assets:
        out.append("net_assets_exceeds_total_assets")
    if total_assets is not None and total_liabilities is not None and total_liabilities > total_assets:
        out.append("total_liabilities_exceeds_total_assets")
    if total_assets is not None and total_liabilities is not None and net_assets is not None:
        expected = total_assets - total_liabilities
        slack = max(abs(total_assets), 1.0) * _IDENTITY_TOLERANCE_RATIO
        if abs(expected - net_assets) > slack:
            out.append("assets_minus_liabilities_not_net_assets")
    return out


def restore_breaks_balance_sheet(row: dict, field: str, value) -> bool:
    """True if writing `value` into `row[field]` would create a violation the
    row does not already have.

    Only NEW violations block a restore — a row that is already incoherent for
    reasons of its own is a separate problem, and refusing to restore would not
    fix it.
    """
    if field not in {"total_assets", "total_liabilities", "net_assets"}:
        return False
    current = {k: row.get(k) for k in ("total_assets", "total_liabilities", "net_assets")}
    before = set(balance_sheet_violations(**current))
    after = set(balance_sheet_violations(**{**current, field: value}))
    return bool(after - before)

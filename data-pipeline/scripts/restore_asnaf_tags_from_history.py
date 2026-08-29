"""Restore asnaf cause_tags that a bad discovery run erased, using Dolt history.

The v6.0.0 regen stripped every asnaf tag from 15 zakat-eligible charities.
Asnaf tags come from the DISCOVER phase, an agent search that answers
differently run to run, and nothing carried the prior answer forward -- so an
empty discovery overwrote a good set with nothing, silently, because a shorter
facet list raises no error. A zakat donor filtering on "fuqara" simply stopped
being shown Palestine Children's Relief Fund.

carry_forward_asnaf_tags (synthesize.py) stops NEW losses but cannot undo past
ones: by the time it runs, the prior row is already empty. The bead proposed
regenerating the 15 (~$4). Dolt history makes that unnecessary and better --
the pre-loss tags are still there, so the repair is free, deterministic, and
restores exactly what the pipeline previously derived rather than whatever a
fresh non-deterministic discovery happens to return this time.

This applies the SAME rule retroactively, reusing carry_forward_asnaf_tags
itself rather than reimplementing it, with history standing in for the prior
row. Only asnaf tags are carried; region, intervention and identity tags are
left exactly as they are, since those derive from geographic_coverage and
mission text and their movement is usually a real re-derivation.

    uv run python scripts/restore_asnaf_tags_from_history.py           # dry run
    uv run python scripts/restore_asnaf_tags_from_history.py --apply   # write
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.client import execute_query  # noqa: E402
from synthesize import ZAKAT_ASNAF_TAGS, carry_forward_asnaf_tags  # noqa: E402


def _tags(raw) -> list[str]:
    """cause_tags is a JSON column; the driver may hand back str or list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return [str(t) for t in raw] if isinstance(raw, list) else []


def charities_missing_asnaf() -> list[dict]:
    """Zakat-eligible charities whose current cause_tags contain no asnaf tag."""
    rows = execute_query(
        """
        SELECT d.charity_ein, c.name, d.cause_tags
        FROM charity_data d
        JOIN evaluations e ON e.charity_ein = d.charity_ein
        LEFT JOIN charities c ON c.ein = d.charity_ein
        WHERE e.wallet_tag = 'ZAKAT-ELIGIBLE' AND e.state = 'generated'
        """
    )
    return [r for r in rows or [] if not (set(_tags(r["cause_tags"])) & ZAKAT_ASNAF_TAGS)]


def last_known_asnaf(ein: str) -> tuple[list[str], str | None]:
    """The most recent historical cause_tags for this EIN that had asnaf tags."""
    rows = execute_query(
        """
        SELECT cause_tags, commit_hash, commit_date
        FROM dolt_history_charity_data
        WHERE charity_ein = %s
        ORDER BY commit_date DESC
        """,
        (ein,),
    )
    for row in rows or []:
        tags = _tags(row["cause_tags"])
        if set(tags) & ZAKAT_ASNAF_TAGS:
            return tags, row["commit_hash"]
    return [], None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the restored tags (default: dry run)")
    args = ap.parse_args(argv)

    affected = charities_missing_asnaf()
    print(f"{len(affected)} zakat-eligible charities have no asnaf tag\n")

    repairs, unrecoverable = [], []
    for row in affected:
        ein = row["charity_ein"]
        current = _tags(row["cause_tags"])
        prior, commit = last_known_asnaf(ein)
        merged, restored = carry_forward_asnaf_tags(current, prior)
        name = (row.get("name") or "?")[:38]
        if not restored:
            unrecoverable.append((ein, name))
            print(f"  [no history] {ein}  {name}")
            continue
        repairs.append((ein, merged))
        source = commit[:8] if commit else "?"
        print(f"  [restore]    {ein}  {name:40} + {', '.join(restored)}  (from {source})")

    print(f"\nrecoverable: {len(repairs)}   unrecoverable: {len(unrecoverable)}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return 0

    for ein, merged in repairs:
        execute_query(
            "UPDATE charity_data SET cause_tags = %s WHERE charity_ein = %s",
            (json.dumps(merged), ein),
            fetch="none",
        )
    print(f"\nWrote {len(repairs)} rows. Re-run export to publish, then dolt commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

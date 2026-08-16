"""Coverage dry run for the IRS-governance-collector plan.

For every charity in pilot_charities.txt, checks whether an e-filed Form 990
(full, not EZ/PF) is available via the IRS index -- the return type that
carries Part VI (Governance) and Part VII (officers/board). Zero LLM cost,
zero writes: reuses Form990GrantsCollector._irs_filings(), which itself
caches the IRS submission-year index CSVs to disk on first use.

Usage: uv run python scripts/irs_governance_coverage_dryrun.py
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.form990_grants import Form990GrantsCollector  # noqa: E402

logging.basicConfig(level=logging.WARNING)

PILOT_FILE = Path(__file__).parent.parent / "pilot_charities.txt"


def load_governance_gap_eins() -> set[str]:
    """Charities whose Governance component evidence currently reads 'unknown'."""
    import json

    import pymysql

    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="", database="zakaat")
    cur = conn.cursor()
    cur.execute("SELECT charity_ein, score_details FROM evaluations WHERE score_details IS NOT NULL")
    gap = set()
    for ein, sd_raw in cur.fetchall():
        sd = json.loads(sd_raw) if isinstance(sd_raw, str) else sd_raw
        comps = (sd.get("impact") or {}).get("components") or []
        gov = next((c for c in comps if c.get("name") == "Governance"), None)
        if gov and "unknown" in (gov.get("evidence") or "").lower():
            gap.add(ein)
    conn.close()
    return gap


GOVERNANCE_GAP_EINS = load_governance_gap_eins()


def load_charities(path: Path) -> list[tuple[str, str]]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        name, ein = parts[0], parts[1]
        ein = re.sub(r"[^\d-]", "", ein)
        if re.match(r"^\d{2}-\d{7}$", ein):
            out.append((name, ein))
    return out


def main() -> None:
    charities = load_charities(PILOT_FILE)
    print(f"Loaded {len(charities)} charities from pilot_charities.txt")

    collector = Form990GrantsCollector()

    has_990 = []
    has_only_ez_or_pf = []
    no_filing_found = []

    for name, ein in charities:
        ein_clean = ein.replace("-", "")
        filings = collector._irs_filings(ein_clean, max_filings=3)
        if not filings:
            no_filing_found.append((ein, name))
            continue
        types = {(f.return_type or "").upper() for f in filings}
        if "990" in types:
            has_990.append((ein, name, filings[0].tax_period))
        else:
            has_only_ez_or_pf.append((ein, name, sorted(types)))

    total = len(charities)
    print()
    print(f"Full 990 (Part VI/VII available):  {len(has_990)}/{total}")
    print(f"Only 990-EZ / 990-PF (no Part VI):  {len(has_only_ez_or_pf)}/{total}")
    print(f"No IRS e-file record found at all:  {len(no_filing_found)}/{total}")

    gap_has_990 = [x for x in has_990 if x[0] in GOVERNANCE_GAP_EINS]
    gap_no_990 = [x for x in (has_only_ez_or_pf + no_filing_found) if x[0] in GOVERNANCE_GAP_EINS]
    print()
    print(f"Of the {len(GOVERNANCE_GAP_EINS)} known governance-gap EINs:")
    print(f"  Full 990 available: {len(gap_has_990)}")
    for ein, name, tp in gap_has_990:
        print(f"    {ein}  {name}  (tax period {tp})")
    print(f"  NOT resolvable via full 990: {len(gap_no_990)}")
    for row in gap_no_990:
        print(f"    {row[0]}  {row[1]}")

    if has_only_ez_or_pf:
        print()
        print("Charities with only EZ/PF filings (no Part VI):")
        for ein, name, types in has_only_ez_or_pf[:20]:
            print(f"    {ein}  {name}  {types}")

    if no_filing_found:
        print()
        print("Charities with NO IRS e-file record in the last 3 submission years:")
        for ein, name in no_filing_found[:20]:
            print(f"    {ein}  {name}")


if __name__ == "__main__":
    main()

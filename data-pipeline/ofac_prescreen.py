#!/usr/bin/env python3
"""
OFAC SDN List Prescreen for Charity List

Checks all charities in pilot_charities.txt against the OFAC Specially Designated
Nationals (SDN) list to identify any potential matches.

Usage:
    uv run python ofac_prescreen.py
    uv run python ofac_prescreen.py --threshold 80  # Adjust fuzzy match threshold
    uv run python ofac_prescreen.py --refresh       # Force re-download SDN list

Output:
    - Console report of any matches/near-matches
    - ofac_prescreen_report.json with full results
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import httpx

# OFAC SDN list URL (CSV format)
SDN_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

# Cache the SDN list locally
CACHE_DIR = Path(__file__).parent / ".cache"
SDN_CACHE_FILE = CACHE_DIR / "sdn_list.csv"
REPORT_FILE = Path(__file__).parent / "ofac_prescreen_report.json"


def download_sdn_list(force_refresh: bool = False) -> Path:
    """Download the OFAC SDN list if not cached or if refresh requested."""
    CACHE_DIR.mkdir(exist_ok=True)

    if SDN_CACHE_FILE.exists() and not force_refresh:
        # Check if cache is less than 7 days old
        age_days = (datetime.now().timestamp() - SDN_CACHE_FILE.stat().st_mtime) / 86400
        if age_days < 7:
            print(f"Using cached SDN list (age: {age_days:.1f} days)")
            return SDN_CACHE_FILE

    print("Downloading OFAC SDN list...")
    response = httpx.get(SDN_CSV_URL, timeout=60, follow_redirects=True)
    response.raise_for_status()

    SDN_CACHE_FILE.write_bytes(response.content)
    print(f"Downloaded SDN list ({len(response.content):,} bytes)")
    return SDN_CACHE_FILE


def parse_sdn_list(csv_path: Path) -> list[dict]:
    """
    Parse the SDN CSV file.

    The SDN CSV has these columns (no header row):
    0: ent_num - Entity number
    1: SDN_Name - Name of SDN
    2: SDN_Type - Type (individual, entity, vessel, aircraft)
    3: Program - Sanctions program
    4: Title - Title
    5: Call_Sign - Call sign
    6: Vess_type - Vessel type
    7: Tonnage - Tonnage
    8: GRT - Gross registered tonnage
    9: Vess_flag - Vessel flag
    10: Vess_owner - Vessel owner
    11: Remarks - Remarks (often contains aliases)
    """
    entities = []

    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 4:
                continue

            name = row[1].strip() if len(row) > 1 else ""
            sdn_type = row[2].strip() if len(row) > 2 else ""
            program = row[3].strip() if len(row) > 3 else ""
            remarks = row[11].strip() if len(row) > 11 else ""

            if name:
                entities.append({
                    "name": name,
                    "type": sdn_type,
                    "program": program,
                    "remarks": remarks,
                    "name_normalized": normalize_name(name),
                })

    return entities


def normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    # Remove common suffixes
    name = re.sub(r'\s+(Inc\.?|LLC|Corp\.?|Foundation|USA|U\.S\.A\.?)$', '', name, flags=re.IGNORECASE)
    # Remove punctuation and extra whitespace
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name.lower()


def similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings (0-100)."""
    return SequenceMatcher(None, a, b).ratio() * 100


def parse_pilot_charities(filepath: Path) -> list[dict]:
    """Parse pilot_charities.txt and return list of charities."""
    charities = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2:
                name = parts[0]
                ein = parts[1]
                url = parts[2] if len(parts) > 2 else ""
                comments = parts[3] if len(parts) > 3 else ""

                # Skip HIDE:TRUE charities? No, check them all for safety
                charities.append({
                    "name": name,
                    "ein": ein,
                    "url": url,
                    "comments": comments,
                    "name_normalized": normalize_name(name),
                })

    return charities


def check_charity_against_sdn(
    charity: dict,
    sdn_entities: list[dict],
    threshold: int = 85
) -> list[dict]:
    """
    Check a single charity against the SDN list.

    Returns list of potential matches above threshold.
    """
    matches = []
    charity_name = charity["name_normalized"]

    for entity in sdn_entities:
        # Skip individuals - we're checking organizations
        if entity["type"] == "individual":
            continue

        entity_name = entity["name_normalized"]

        # Exact match
        if charity_name == entity_name:
            matches.append({
                "sdn_name": entity["name"],
                "sdn_type": entity["type"],
                "program": entity["program"],
                "match_type": "EXACT",
                "similarity": 100,
            })
            continue

        # Fuzzy match
        sim = similarity(charity_name, entity_name)
        if sim >= threshold:
            matches.append({
                "sdn_name": entity["name"],
                "sdn_type": entity["type"],
                "program": entity["program"],
                "match_type": "FUZZY",
                "similarity": round(sim, 1),
            })

    return matches


def run_prescreen(threshold: int = 85, force_refresh: bool = False) -> dict:
    """Run the full OFAC prescreen and return results."""

    # Download/load SDN list
    sdn_path = download_sdn_list(force_refresh)
    sdn_entities = parse_sdn_list(sdn_path)
    print(f"Loaded {len(sdn_entities):,} SDN entities")

    # Parse pilot charities
    pilot_path = Path(__file__).parent / "pilot_charities.txt"
    charities = parse_pilot_charities(pilot_path)
    print(f"Checking {len(charities)} charities against SDN list...")

    # Check each charity
    results = {
        "run_date": datetime.now().isoformat(),
        "sdn_entities_count": len(sdn_entities),
        "charities_checked": len(charities),
        "threshold": threshold,
        "matches": [],
        "clean": [],
    }

    for charity in charities:
        matches = check_charity_against_sdn(charity, sdn_entities, threshold)

        if matches:
            results["matches"].append({
                "charity_name": charity["name"],
                "ein": charity["ein"],
                "potential_matches": matches,
            })
        else:
            results["clean"].append({
                "charity_name": charity["name"],
                "ein": charity["ein"],
            })

    return results


def print_report(results: dict) -> None:
    """Print a human-readable report."""
    print("\n" + "=" * 70)
    print("OFAC SDN PRESCREEN REPORT")
    print("=" * 70)
    print(f"Run date: {results['run_date']}")
    print(f"SDN entities checked: {results['sdn_entities_count']:,}")
    print(f"Charities checked: {results['charities_checked']}")
    print(f"Similarity threshold: {results['threshold']}%")
    print()

    if results["matches"]:
        print("⚠️  POTENTIAL MATCHES FOUND:")
        print("-" * 70)
        for match in results["matches"]:
            print(f"\n  {match['charity_name']} (EIN: {match['ein']})")
            for m in match["potential_matches"]:
                print(f"    → {m['match_type']} match ({m['similarity']}%): {m['sdn_name']}")
                print(f"      Type: {m['sdn_type']}, Program: {m['program']}")
    else:
        print("✅ NO MATCHES FOUND")
        print("-" * 70)
        print("All charities passed the OFAC SDN prescreen.")

    print()
    print(f"Clean charities: {len(results['clean'])}/{results['charities_checked']}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="OFAC SDN prescreen for charity list")
    parser.add_argument(
        "--threshold",
        type=int,
        default=85,
        help="Fuzzy match threshold (0-100, default: 85)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-download of SDN list"
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output JSON only, no console report"
    )
    args = parser.parse_args()

    results = run_prescreen(threshold=args.threshold, force_refresh=args.refresh)

    # Save JSON report
    with open(REPORT_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nFull report saved to: {REPORT_FILE}")

    if not args.json_only:
        print_report(results)

    # Exit with error code if matches found
    if results["matches"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

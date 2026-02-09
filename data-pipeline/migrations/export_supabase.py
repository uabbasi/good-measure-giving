#!/usr/bin/env python3
"""Export all data from Supabase to JSON files.

This script exports all charity data from Supabase to JSON files
for migration to DoltDB.

Usage:
    uv run python migrations/export_supabase.py --output-dir ./supabase_export

Output structure:
    supabase_export/
    ├── charities.json
    ├── raw_scraped_data.json
    ├── charity_data.json
    ├── evaluations.json
    ├── agent_discoveries.json
    ├── citations.json
    └── pdf_documents.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import Client, create_client


def get_supabase_client() -> Client:
    """Get Supabase client from environment variables."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")

    if not url or not key:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_SECRET_KEY environment variables.\n"
            "Set these in .env or export them."
        )

    return create_client(url, key)


def export_table(client: Client, table_name: str, output_dir: Path) -> int:
    """Export a table to JSON file.

    Args:
        client: Supabase client
        table_name: Name of the table to export
        output_dir: Directory to write JSON file

    Returns:
        Number of rows exported
    """
    print(f"Exporting {table_name}...")

    # Fetch all rows (Supabase paginates at 1000 by default, we need to handle large tables)
    all_rows = []
    offset = 0
    page_size = 1000

    while True:
        result = (
            client.table(table_name)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )

        if not result.data:
            break

        all_rows.extend(result.data)
        offset += page_size

        if len(result.data) < page_size:
            break

    # Write to JSON file
    output_file = output_dir / f"{table_name}.json"
    with open(output_file, "w") as f:
        json.dump(all_rows, f, indent=2, default=str)

    print(f"  Exported {len(all_rows)} rows to {output_file}")
    return len(all_rows)


def main():
    parser = argparse.ArgumentParser(description="Export Supabase data to JSON files")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./supabase_export",
        help="Directory to write JSON files (default: ./supabase_export)",
    )
    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Tables to export
    tables = [
        "charities",
        "raw_scraped_data",
        "charity_data",
        "evaluations",
        "agent_discoveries",
        "citations",
        "pdf_documents",
    ]

    print("=" * 60)
    print("Supabase Export")
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"Output directory: {output_dir.absolute()}")
    print("=" * 60)

    # Get Supabase client
    try:
        client = get_supabase_client()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Export each table
    total_rows = 0
    stats = {}

    for table in tables:
        try:
            count = export_table(client, table, output_dir)
            stats[table] = count
            total_rows += count
        except Exception as e:
            print(f"  Warning: Failed to export {table}: {e}")
            stats[table] = 0

    # Write export manifest
    manifest = {
        "exported_at": datetime.now().isoformat(),
        "tables": stats,
        "total_rows": total_rows,
    }
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print("=" * 60)
    print("Export Summary")
    print("-" * 60)
    for table, count in stats.items():
        print(f"  {table}: {count:,} rows")
    print("-" * 60)
    print(f"Total: {total_rows:,} rows")
    print(f"Manifest: {manifest_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()

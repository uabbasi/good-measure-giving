#!/usr/bin/env python3
"""Import JSON data into DoltDB.

This script imports charity data from JSON files (exported from Supabase)
into a DoltDB database.

Prerequisites:
    1. DoltDB must be installed: https://docs.dolthub.com/introduction/installation
    2. Database must be initialized:
       $ dolt init zakaat
       $ dolt sql-server  # Start SQL server

Usage:
    uv run python migrations/import_dolt.py --input-dir ./supabase_export

This will:
    1. Create all tables from dolt_schema.sql
    2. Import data from JSON files
    3. Create initial commit: "Initial data migration from Supabase"
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pymysql
from pymysql.cursors import DictCursor


def get_connection() -> pymysql.Connection:
    """Get MySQL connection to DoltDB."""
    config = {
        "host": os.environ.get("DOLT_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DOLT_PORT", "3306")),
        "user": os.environ.get("DOLT_USER", "root"),
        "password": os.environ.get("DOLT_PASSWORD", ""),
        "database": os.environ.get("DOLT_DATABASE", "zakaat"),
        "autocommit": True,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
    }
    return pymysql.connect(**config)


def execute_schema(conn: pymysql.Connection, schema_path: Path) -> None:
    """Execute the schema SQL file."""
    print(f"Executing schema from {schema_path}...")

    with open(schema_path) as f:
        schema_sql = f.read()

    cursor = conn.cursor()

    # Split by semicolon and execute each statement
    statements = [s.strip() for s in schema_sql.split(";") if s.strip()]

    for stmt in statements:
        # Skip comments and empty statements
        if stmt.startswith("--") or not stmt:
            continue

        # Skip DOLT-specific comments
        if "DOLT" in stmt and stmt.startswith("--"):
            continue

        try:
            cursor.execute(stmt)
        except pymysql.Error as e:
            # Ignore "already exists" errors
            if e.errno == 1050:  # Table already exists
                continue
            if e.errno == 1065:  # Query was empty
                continue
            raise

    cursor.close()
    print("  Schema created successfully")


def import_table(
    conn: pymysql.Connection,
    table_name: str,
    data: list[dict[str, Any]],
    primary_key: str,
) -> int:
    """Import data into a table.

    Args:
        conn: MySQL connection
        table_name: Target table name
        data: List of row dictionaries
        primary_key: Primary key column name

    Returns:
        Number of rows imported
    """
    if not data:
        print(f"  {table_name}: No data to import")
        return 0

    cursor = conn.cursor()
    imported = 0

    # Get column names from first row
    sample_row = data[0]

    # Insert each row
    for row in data:
        columns = list(row.keys())

        # Serialize any dict/list values to JSON
        values = []
        for col in columns:
            val = row[col]
            if isinstance(val, (dict, list)):
                values.append(json.dumps(val))
            else:
                values.append(val)

        placeholders = ", ".join(["%s"] * len(columns))
        update_clause = ", ".join([f"{col} = VALUES({col})" for col in columns if col != primary_key])

        sql = f"""
            INSERT INTO {table_name} ({", ".join(columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause if update_clause else f"{primary_key} = {primary_key}"}
        """

        try:
            cursor.execute(sql, values)
            imported += 1
        except pymysql.Error as e:
            print(f"    Warning: Failed to import row: {e}")
            continue

    cursor.close()
    print(f"  {table_name}: Imported {imported}/{len(data)} rows")
    return imported


def create_dolt_commit(conn: pymysql.Connection, message: str) -> str | None:
    """Create a Dolt commit.

    Args:
        conn: MySQL connection
        message: Commit message

    Returns:
        Commit hash if successful, None otherwise
    """
    cursor = conn.cursor()

    # Check if there are changes to commit
    cursor.execute("SELECT * FROM dolt_status")
    status = cursor.fetchall()

    if not status:
        print("  No changes to commit")
        return None

    # Add all changes
    cursor.execute("CALL DOLT_ADD('-A')")

    # Commit
    author = os.environ.get("DOLT_AUTHOR", "migration")
    email = os.environ.get("DOLT_EMAIL", "migration@zakaat.local")

    cursor.execute(
        "CALL DOLT_COMMIT('--author', %s, '-m', %s)",
        (f"{author} <{email}>", message),
    )

    # Get commit hash - Dolt returns it in the result of DOLT_COMMIT
    cursor.execute("SELECT DOLT_HASHOF('HEAD') AS hash")
    result = cursor.fetchone()

    cursor.close()
    return result["hash"] if result else None


def main():
    parser = argparse.ArgumentParser(description="Import JSON data into DoltDB")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="./supabase_export",
        help="Directory containing JSON files (default: ./supabase_export)",
    )
    parser.add_argument(
        "--schema-file",
        type=str,
        default=None,
        help="Path to dolt_schema.sql (default: auto-detect)",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip schema creation (tables already exist)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)

    # Find schema file
    if args.schema_file:
        schema_path = Path(args.schema_file)
    else:
        schema_path = Path(__file__).parent.parent / "dolt_schema.sql"

    if not args.skip_schema and not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}")
        sys.exit(1)

    # Tables to import with their primary keys
    tables = [
        ("charities", "ein"),
        ("raw_scraped_data", "id"),
        ("charity_data", "charity_ein"),
        ("evaluations", "charity_ein"),
        ("agent_discoveries", "id"),
        ("citations", "id"),
        ("pdf_documents", "id"),
    ]

    print("=" * 60)
    print("DoltDB Import")
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"Input directory: {input_dir.absolute()}")
    print("=" * 60)

    # Connect to Dolt
    try:
        conn = get_connection()
        print("Connected to DoltDB")
    except pymysql.Error as e:
        print(f"Error connecting to DoltDB: {e}")
        print("\nMake sure DoltDB is running:")
        print("  $ cd path/to/dolt/repo")
        print("  $ dolt sql-server")
        sys.exit(1)

    # Create schema
    if not args.skip_schema:
        execute_schema(conn, schema_path)

    # Import each table
    total_imported = 0
    stats = {}

    for table_name, primary_key in tables:
        json_file = input_dir / f"{table_name}.json"

        if not json_file.exists():
            print(f"  {table_name}: No JSON file found, skipping")
            stats[table_name] = 0
            continue

        with open(json_file) as f:
            data = json.load(f)

        count = import_table(conn, table_name, data, primary_key)
        stats[table_name] = count
        total_imported += count

    # Create initial commit
    print("\nCreating Dolt commit...")
    commit_hash = create_dolt_commit(
        conn,
        f"Initial data migration from Supabase\n\nMigrated {total_imported:,} rows across {len(tables)} tables."
    )

    conn.close()

    print("=" * 60)
    print("Import Summary")
    print("-" * 60)
    for table, count in stats.items():
        print(f"  {table}: {count:,} rows")
    print("-" * 60)
    print(f"Total: {total_imported:,} rows")
    if commit_hash:
        print(f"Commit: {commit_hash}")
    print("=" * 60)


if __name__ == "__main__":
    main()

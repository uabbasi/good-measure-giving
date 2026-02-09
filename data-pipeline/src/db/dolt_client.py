"""Dolt version control operations.

Provides Git-like versioning for the charity database.
Wraps Dolt stored procedures (DOLT_COMMIT, DOLT_BRANCH, etc.)
for use in the data pipeline.

Replaces the PostgreSQL audit_log table with native Dolt history.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from .client import execute_query, get_cursor

# Whitelist of valid table names for SQL interpolation
VALID_TABLES = frozenset({
    "charities", "raw_scraped_data", "charity_data", "evaluations",
    "pdf_documents", "agent_discoveries", "citations", "phase_cache",
    "judge_verdicts",
})

# Pattern for valid Dolt refs: commit hashes, branch names, HEAD~N, tags
_VALID_REF_PATTERN = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_.~^/-]*$")
# Pattern for valid column names
_VALID_COLUMN_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_table_name(table: str) -> str:
    """Validate table name against whitelist. Raises ValueError if invalid."""
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table name: {table!r}. Must be one of: {sorted(VALID_TABLES)}")
    return table


def _validate_ref(ref: str) -> str:
    """Validate a Dolt ref (commit hash, branch, HEAD~N). Raises ValueError if invalid."""
    if not ref or not _VALID_REF_PATTERN.match(ref):
        raise ValueError(f"Invalid Dolt ref: {ref!r}. Must match pattern: alphanumeric, _, ., ~, ^, /, -")
    return ref


def _validate_column_name(col: str) -> str:
    """Validate a column name. Raises ValueError if invalid."""
    if not col or not _VALID_COLUMN_PATTERN.match(col):
        raise ValueError(f"Invalid column name: {col!r}. Must be alphanumeric/underscore.")
    return col


@dataclass
class Commit:
    """A Dolt commit."""

    hash: str
    message: str
    author: str
    date: datetime


@dataclass
class DiffRow:
    """A row change in a Dolt diff."""

    diff_type: str  # 'added', 'removed', 'modified'
    table: str
    primary_key: dict  # Primary key columns
    from_values: dict | None  # Values before change (None for added)
    to_values: dict | None  # Values after change (None for removed)


class DoltVersionControl:
    """Git-like version control for Dolt.

    Exposes:
        - commit(message): Commit all staged changes
        - log(limit): Get commit history
        - diff(from_ref, to_ref, table): Show changes between refs
        - create_branch(name): Create a new branch
        - checkout(branch): Switch to a branch
        - merge(branch): Merge a branch into current
        - status(): Show uncommitted changes
        - current_branch(): Get current branch name
    """

    def __init__(self, author: str | None = None, email: str | None = None):
        """Initialize version control.

        Args:
            author: Commit author name (default: from DOLT_AUTHOR env var or 'pipeline')
            email: Commit author email (default: from DOLT_EMAIL env var or 'pipeline@zakaat.local')
        """
        self.author = author or os.environ.get("DOLT_AUTHOR", "pipeline")
        self.email = email or os.environ.get("DOLT_EMAIL", "pipeline@zakaat.local")

    def commit(self, message: str, add_all: bool = True) -> str | None:
        """Commit all changes.

        Args:
            message: Commit message
            add_all: If True, automatically add all changes (default: True)

        Returns:
            Commit hash if changes were committed, None if no changes

        Example:
            hash = dolt.commit("Crawl: 25 charities updated")
        """
        with get_cursor() as cursor:
            # Check if there are changes to commit
            cursor.execute("SELECT * FROM dolt_status")
            status = cursor.fetchall()

            if not status:
                return None  # No changes to commit

            # Add all changes if requested
            if add_all:
                cursor.execute("CALL DOLT_ADD('-A')")

            # Commit and get the hash from the result
            # DOLT_COMMIT returns a table with the commit hash
            cursor.execute(
                "CALL DOLT_COMMIT('--author', %s, '-m', %s)",
                (f"{self.author} <{self.email}>", message),
            )
            result = cursor.fetchone()

            # Result is a dict with 'hash' key
            return result["hash"] if result else None

    def log(self, limit: int = 10) -> list[Commit]:
        """Get commit history.

        Args:
            limit: Maximum number of commits to return

        Returns:
            List of Commit objects, newest first

        Example:
            for commit in dolt.log(5):
                print(f"{commit.hash[:8]} - {commit.message}")
        """
        rows = execute_query(
            """
            SELECT commit_hash, message, committer, date
            FROM dolt_log
            ORDER BY date DESC
            LIMIT %s
            """,
            (limit,),
        )

        return [
            Commit(
                hash=row["commit_hash"],
                message=row["message"],
                author=row["committer"],
                date=row["date"],
            )
            for row in (rows or [])
        ]

    def diff(
        self,
        from_ref: str,
        to_ref: str,
        table: str | None = None,
    ) -> list[dict[str, Any]]:
        """Show changes between two refs.

        Args:
            from_ref: Starting commit/branch (e.g., 'main~1', 'abc123', 'main')
            to_ref: Ending commit/branch (e.g., 'main', 'HEAD')
            table: Optional table name to filter (shows all tables if None)

        Returns:
            List of diff rows with change details

        Example:
            # Changes in last commit for charities table
            changes = dolt.diff('main~1', 'main', 'charities')

            # All changes between two branches
            changes = dolt.diff('main', 'feature-branch')
        """
        if table:
            # Diff specific table
            rows = execute_query(
                "SELECT * FROM dolt_diff(%s, %s, %s)",
                (from_ref, to_ref, table),
            )
        else:
            # Get list of changed tables first
            rows = execute_query(
                """
                SELECT table_name, data_change, schema_change
                FROM dolt_diff_summary(%s, %s)
                """,
                (from_ref, to_ref),
            )

        return rows or []

    def create_branch(self, name: str, from_ref: str | None = None) -> bool:
        """Create a new branch.

        Args:
            name: Branch name
            from_ref: Optional ref to branch from (default: current HEAD)

        Returns:
            True if branch was created

        Example:
            dolt.create_branch("experiment-scoring")
        """
        with get_cursor() as cursor:
            if from_ref:
                cursor.execute("CALL DOLT_BRANCH(%s, %s)", (name, from_ref))
            else:
                cursor.execute("CALL DOLT_BRANCH(%s)", (name,))
            return True

    def checkout(self, branch: str) -> bool:
        """Switch to a branch.

        Args:
            branch: Branch name to switch to

        Returns:
            True if checkout succeeded

        Example:
            dolt.checkout("experiment-scoring")
        """
        with get_cursor() as cursor:
            cursor.execute("CALL DOLT_CHECKOUT(%s)", (branch,))
            return True

    def merge(self, branch: str, squash: bool = False) -> dict[str, Any]:
        """Merge a branch into current branch.

        Args:
            branch: Branch to merge
            squash: If True, squash all commits into one

        Returns:
            Merge result with 'fast_forward', 'conflicts', 'hash' keys

        Example:
            result = dolt.merge("experiment-scoring")
            if result["conflicts"]:
                print("Merge had conflicts!")
        """
        with get_cursor() as cursor:
            if squash:
                cursor.execute("CALL DOLT_MERGE('--squash', %s)", (branch,))
            else:
                cursor.execute("CALL DOLT_MERGE(%s)", (branch,))

            # Check merge result
            cursor.execute("SELECT @@dolt_merge_conflicts AS conflicts")
            conflicts_result = cursor.fetchone()

            cursor.execute("SELECT @@dolt_merge_fast_forward AS ff")
            ff_result = cursor.fetchone()

            return {
                "fast_forward": ff_result["ff"] if ff_result else False,
                "conflicts": conflicts_result["conflicts"] if conflicts_result else False,
            }

    def delete_branch(self, name: str, force: bool = False) -> bool:
        """Delete a branch.

        Args:
            name: Branch name to delete
            force: Force delete even if not merged

        Returns:
            True if branch was deleted
        """
        with get_cursor() as cursor:
            if force:
                cursor.execute("CALL DOLT_BRANCH('-D', %s)", (name,))
            else:
                cursor.execute("CALL DOLT_BRANCH('-d', %s)", (name,))
            return True

    def status(self) -> list[dict[str, Any]]:
        """Show uncommitted changes.

        Returns:
            List of dicts with 'table_name', 'staged', 'status' keys

        Example:
            for change in dolt.status():
                print(f"{change['table_name']}: {change['status']}")
        """
        return execute_query("SELECT * FROM dolt_status") or []

    def current_branch(self) -> str:
        """Get current branch name.

        Returns:
            Current branch name (e.g., 'main')
        """
        row = execute_query(
            "SELECT active_branch() AS branch",
            fetch="one",
        )
        return row["branch"] if row else "main"

    def branches(self) -> list[str]:
        """List all branches.

        Returns:
            List of branch names
        """
        rows = execute_query("SELECT name FROM dolt_branches ORDER BY name")
        return [row["name"] for row in (rows or [])]

    def tag(self, name: str, message: str | None = None, ref: str | None = None) -> bool:
        """Create a tag at a commit.

        Args:
            name: Tag name (e.g., 'run-2026-01-25-143052', 'v1.0.0')
            message: Optional tag message
            ref: Commit ref to tag (default: HEAD)

        Returns:
            True if tag was created

        Example:
            dolt.tag("run-2026-01-25-143052", "Pipeline run: 10/10 charities")
        """
        with get_cursor() as cursor:
            args = []
            if message:
                args.extend(["-m", message])
            args.append(name)
            if ref:
                args.append(ref)

            # Build CALL DOLT_TAG(...) with variable args
            placeholders = ", ".join(["%s"] * len(args))
            cursor.execute(f"CALL DOLT_TAG({placeholders})", tuple(args))
            return True

    def delete_tag(self, name: str) -> bool:
        """Delete a tag.

        Args:
            name: Tag name to delete

        Returns:
            True if tag was deleted
        """
        with get_cursor() as cursor:
            cursor.execute("CALL DOLT_TAG('-d', %s)", (name,))
            return True

    def tags(self) -> list[dict[str, Any]]:
        """List all tags.

        Returns:
            List of dicts with 'tag_name', 'tag_hash', 'tagger', 'date', 'message' keys

        Example:
            for tag in dolt.tags():
                print(f"{tag['tag_name']}: {tag['message']}")
        """
        return execute_query("SELECT * FROM dolt_tags ORDER BY date DESC") or []

    def history(self, table: str, primary_key: dict, limit: int = 10) -> list[dict]:
        """Get history of a specific row.

        Args:
            table: Table name
            primary_key: Dict of primary key column(s) and value(s)
            limit: Maximum number of versions

        Returns:
            List of row versions, newest first

        Example:
            # Get history of a specific charity
            history = dolt.history("charities", {"ein": "12-3456789"})
        """
        # Validate inputs to prevent SQL injection
        _validate_table_name(table)
        for col in primary_key.keys():
            _validate_column_name(col)

        # Build WHERE clause for primary key
        pk_conditions = " AND ".join(f"`{k}` = %s" for k in primary_key.keys())
        pk_values = tuple(primary_key.values())

        rows = execute_query(
            f"""
            SELECT *
            FROM dolt_history_{table}
            WHERE {pk_conditions}
            ORDER BY dolt_commit_timestamp DESC
            LIMIT %s
            """,
            (*pk_values, limit),
        )
        return rows or []

    def time_travel_query(self, table: str, as_of: str, where: str = "") -> list[dict]:
        """Query table at a specific point in time.

        Args:
            table: Table name
            as_of: Commit hash or ref (e.g., 'main~5', 'abc123')
            where: Optional WHERE clause (without 'WHERE' keyword)

        Returns:
            Query results from that point in time

        Example:
            # Get all charities as of 5 commits ago
            old_charities = dolt.time_travel_query("charities", "main~5")

            # Get specific charity at a commit
            charity = dolt.time_travel_query("charities", "abc123", "ein = '12-3456789'")
        """
        # Validate inputs to prevent SQL injection
        _validate_table_name(table)
        _validate_ref(as_of)

        sql = f"SELECT * FROM `{table}` AS OF %s"
        params = [as_of]

        if where:
            # 'where' should use parameterized conditions; validate it contains no semicolons
            if ";" in where:
                raise ValueError("WHERE clause must not contain semicolons")
            sql += f" WHERE {where}"

        return execute_query(sql, tuple(params)) or []


# Module-level singleton for convenience
@lru_cache(maxsize=1)
def get_dolt() -> DoltVersionControl:
    """Get Dolt version control client (cached singleton).

    Returns:
        DoltVersionControl instance
    """
    return DoltVersionControl()


# Convenience alias for pipeline scripts
dolt = get_dolt()

"""DoltDB client.

Thread-local connection reuse for DoltDB (MySQL-compatible protocol).
Each thread gets a persistent connection that reconnects on failure.
Dolt handles concurrency natively; versioning is via stored procedures.
"""

import os
import threading
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Generator

import pymysql
from pymysql.cursors import DictCursor

_thread_local = threading.local()


@lru_cache(maxsize=1)
def _get_config() -> dict:
    """Get connection configuration.

    Environment variables:
        DOLT_HOST: Database host (default: 127.0.0.1)
        DOLT_PORT: Database port (default: 3306)
        DOLT_USER: Database user (default: root)
        DOLT_PASSWORD: Database password (default: empty)
        DOLT_DATABASE: Database name (default: zakaat)

    Returns:
        Connection config dict
    """
    return {
        "host": os.environ.get("DOLT_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DOLT_PORT", "3306")),
        "user": os.environ.get("DOLT_USER", "root"),
        "password": os.environ.get("DOLT_PASSWORD", ""),
        "database": os.environ.get("DOLT_DATABASE", "zakaat"),
        "autocommit": True,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
    }


def get_connection() -> pymysql.Connection:
    """Get a thread-local database connection, reusing if alive.

    Returns:
        PyMySQL connection (reused per thread, reconnects on failure)

    Example:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM charities")
            results = cursor.fetchall()
    """
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.ping(reconnect=False)
            return conn
        except Exception:
            # Connection is dead, close and reconnect
            try:
                conn.close()
            except Exception:
                pass
    conn = pymysql.connect(**_get_config())
    _thread_local.conn = conn
    return conn


@contextmanager
def get_cursor(dictionary: bool = True) -> Generator[Any, None, None]:
    """Context manager for database cursor.

    Uses thread-local connection reuse. Reconnects transparently on failure.

    Args:
        dictionary: If True, returns rows as dicts (default). Ignored for pymysql (always dict).

    Yields:
        PyMySQL cursor

    Example:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM charities WHERE ein = %s", (ein,))
            row = cursor.fetchone()
    """
    # autocommit=True means each statement is its own transaction.
    # Dolt versioning uses DOLT_COMMIT stored procedures, not SQL transactions.
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
    except pymysql.OperationalError:
        # Connection may have gone stale between ping and use; retry once
        _thread_local.conn = None
        conn = get_connection()
        with conn.cursor() as cursor:
            yield cursor


def execute_query(sql: str, params: tuple | None = None, fetch: str = "all") -> list[dict] | dict | None:
    """Execute a query and return results.

    Args:
        sql: SQL query with %s placeholders
        params: Query parameters
        fetch: 'all' for fetchall(), 'one' for fetchone(), 'none' for no fetch

    Returns:
        Query results as list of dicts, single dict, or None

    Example:
        # Fetch all
        rows = execute_query("SELECT * FROM charities")

        # Fetch one
        row = execute_query("SELECT * FROM charities WHERE ein = %s", (ein,), fetch="one")

        # No fetch (INSERT/UPDATE)
        execute_query("UPDATE charities SET name = %s WHERE ein = %s", (name, ein), fetch="none")
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params or ())

        if fetch == "all":
            return cursor.fetchall()
        elif fetch == "one":
            return cursor.fetchone()
        return None


def execute_many(sql: str, params_list: list[tuple]) -> int:
    """Execute a query with multiple parameter sets.

    Args:
        sql: SQL query with %s placeholders
        params_list: List of parameter tuples

    Returns:
        Number of rows affected

    Example:
        execute_many(
            "INSERT INTO charities (ein, name) VALUES (%s, %s)",
            [("12-3456789", "Charity A"), ("98-7654321", "Charity B")]
        )
    """
    with get_cursor() as cursor:
        cursor.executemany(sql, params_list)
        return cursor.rowcount


def check_connection() -> bool:
    """Test database connectivity.

    Returns:
        True if connection succeeds, False otherwise
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception:
        return False


# Wrapper class for convenience
class DoltClient:
    """Wrapper class for Dolt database operations."""

    def execute(self, sql: str, params: tuple | None = None) -> list[dict]:
        """Execute query and return all results."""
        return execute_query(sql, params, fetch="all") or []

    def execute_one(self, sql: str, params: tuple | None = None) -> dict | None:
        """Execute query and return single result."""
        return execute_query(sql, params, fetch="one")

    def execute_write(self, sql: str, params: tuple | None = None) -> None:
        """Execute write query (INSERT/UPDATE/DELETE)."""
        execute_query(sql, params, fetch="none")


@lru_cache(maxsize=1)
def get_client() -> DoltClient:
    """Get DoltDB client (cached).

    Returns:
        DoltClient instance
    """
    return DoltClient()

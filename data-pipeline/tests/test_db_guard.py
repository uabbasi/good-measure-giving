"""The test suite must not be able to reach the real DoltDB.

Two tests in test_judge_phase.py used to write phase_cache rows for a real
published charity, and could not pass at all unless a dolt sql-server happened
to be running. conftest.forbid_live_database closes that path for every test;
these assert the guard is actually armed, so removing it fails loudly here
rather than silently somewhere that writes.
"""

import pytest


def test_opening_a_connection_is_refused():
    from src.db import client

    with pytest.raises(RuntimeError, match="real DoltDB connection"):
        client.get_connection()


def test_a_query_cannot_reach_the_server():
    """get_cursor() calls get_connection() per query, so this closes every path."""
    from src.db.client import execute_query

    with pytest.raises(RuntimeError, match="real DoltDB connection"):
        execute_query("SELECT 1")


@pytest.mark.live_db
def test_the_marker_opts_back_in():
    """A test that genuinely needs a server gets the real function back.

    Asserts the guard stepped aside without opening a connection, so this
    passes whether or not a server is running.
    """
    from src.db import client

    assert client.get_connection.__name__ == "get_connection"

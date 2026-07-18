"""Tests for RawDataRepository failure-write semantics (C1 data preservation).

A failed crawl must never clobber parsed_json/raw_content from a previous
successful crawl. Failures record success=False, error_message,
last_failure_reason, and an incremented retry_count instead.

These tests mock src.db.repository.execute_query (no live Dolt needed):
call 1 = the get_by_source SELECT, call 2 = the UPDATE/INSERT under test.
NOTE: the patch target is src.db.repository.execute_query (the name as
imported into the repository module), NOT src.db.client.execute_query.
"""

import json
from unittest.mock import patch

from src.db.repository import RawDataRepository

EIN = "12-3456789"


def _set_clause_map(sql: str, params: tuple) -> dict:
    """Map UPDATE set-clause column names to their bound values."""
    set_part = sql.split(" SET ", 1)[1].split(" WHERE ", 1)[0]
    cols = [seg.split("=")[0].strip() for seg in set_part.split(",") if "%s" in seg]
    return dict(zip(cols, params))


def _insert_map(sql: str, params: tuple) -> dict:
    """Map INSERT column names to their bound values."""
    cols_part = sql.split("(", 1)[1].split(")", 1)[0]
    cols = [c.strip() for c in cols_part.split(",")]
    return dict(zip(cols, params))


def _success_row() -> dict:
    return {
        "id": "uuid-1",
        "charity_ein": EIN,
        "source": "website",
        "parsed_json": '{"website_profile": {"mission": "Feed people"}}',
        "raw_content": "<html>good</html>",
        "success": 1,
        "error_message": None,
        "retry_count": 0,
        "last_failure_reason": None,
    }


def _failed_row(retry_count: int = 1) -> dict:
    return {
        "id": "uuid-1",
        "charity_ein": EIN,
        "source": "website",
        "parsed_json": "{}",
        "raw_content": None,
        "success": 0,
        "error_message": "old error",
        "retry_count": retry_count,
        "last_failure_reason": "old error",
    }


def test_failure_update_preserves_previous_success_content():
    """_store_failed_crawl-style write must not clobber last-good parsed_json."""
    repo = RawDataRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        mock_execute.side_effect = [_success_row(), None]
        repo.upsert(
            charity_ein=EIN,
            source="website",
            parsed_json={},
            success=False,
            error_message="captcha_blocked",
        )
        sql, params = mock_execute.call_args_list[1][0][0], mock_execute.call_args_list[1][0][1]
        assert sql.startswith("UPDATE raw_scraped_data")
        m = _set_clause_map(sql, params)
        assert "parsed_json" not in m
        assert "raw_content" not in m
        assert m["success"] is False
        assert m["error_message"] == "captcha_blocked"


def test_failure_update_records_reason_and_increments_retry():
    repo = RawDataRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        mock_execute.side_effect = [_success_row(), None]
        repo.upsert(
            charity_ein=EIN,
            source="website",
            parsed_json={},
            success=False,
            error_message="captcha_blocked",
        )
        sql, params = mock_execute.call_args_list[1][0][0], mock_execute.call_args_list[1][0][1]
        m = _set_clause_map(sql, params)
        assert m["last_failure_reason"] == "captcha_blocked"
        assert m["retry_count"] == 1  # previous successful row had retry_count 0


def test_failure_over_failure_still_writes_parsed_json():
    """Chosen semantics: partial parsed data may replace a previous failure's
    empty payload — only a previous SUCCESS is protected."""
    repo = RawDataRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        mock_execute.side_effect = [_failed_row(retry_count=1), None]
        repo.upsert(
            charity_ein=EIN,
            source="charity_navigator",
            parsed_json={"cn_profile": {"score": 90}},
            success=False,
            error_message="Empty or failed data",
        )
        sql, params = mock_execute.call_args_list[1][0][0], mock_execute.call_args_list[1][0][1]
        m = _set_clause_map(sql, params)
        assert json.loads(m["parsed_json"]) == {"cn_profile": {"score": 90}}
        assert m["retry_count"] == 2


def test_failure_insert_sets_reason_and_retry():
    repo = RawDataRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        mock_execute.side_effect = [None, None]
        repo.upsert(
            charity_ein=EIN,
            source="website",
            parsed_json={},
            success=False,
            error_message="Unknown error",
        )
        sql, params = mock_execute.call_args_list[1][0][0], mock_execute.call_args_list[1][0][1]
        assert sql.startswith("INSERT INTO raw_scraped_data")
        m = _insert_map(sql, params)
        assert m["last_failure_reason"] == "Unknown error"
        assert m["retry_count"] == 1


def test_success_update_still_writes_content_and_resets_retry():
    """Regression guard: the success path is unchanged."""
    repo = RawDataRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        mock_execute.side_effect = [_failed_row(retry_count=2), None]
        repo.upsert(
            charity_ein=EIN,
            source="website",
            parsed_json={"website_profile": {"mission": "x"}},
            success=True,
            raw_content="<html>fresh</html>",
        )
        sql, params = mock_execute.call_args_list[1][0][0], mock_execute.call_args_list[1][0][1]
        m = _set_clause_map(sql, params)
        assert json.loads(m["parsed_json"]) == {"website_profile": {"mission": "x"}}
        assert m["raw_content"] == "<html>fresh</html>"
        assert m["retry_count"] == 0
        assert "last_failure_reason" not in m


def test_increment_retry_count_writes_last_failure_reason():
    repo = RawDataRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        mock_execute.side_effect = [_failed_row(retry_count=1), None]
        new_count = repo.increment_retry_count(EIN, "bbb", "BBB profile not found")
        assert new_count == 2
        sql, params = mock_execute.call_args_list[1][0][0], mock_execute.call_args_list[1][0][1]
        assert "last_failure_reason = %s" in sql
        assert "BBB profile not found" in params

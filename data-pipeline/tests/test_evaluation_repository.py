"""Tests for EvaluationRepository preserve-unless-provided semantics (C6).

Baseline re-writes must not NULL rich_narrative/rich_strategic_narrative
(they are expensive LLM artifacts), and the Evaluation dataclass must not
implicitly reset `state` to 'pending' on writes that never set it.

Mocks src.db.repository.execute_query — upsert issues exactly one
INSERT ... ON DUPLICATE KEY UPDATE query, so call_args is that query.
"""

from unittest.mock import patch

from src.db.repository import Evaluation, EvaluationRepository

EIN = "12-3456789"


def _upsert_sql(mock_execute):
    args = mock_execute.call_args[0]
    return args[0], args[1]


def test_baseline_write_does_not_null_rich_narratives():
    repo = EvaluationRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        repo.upsert(
            {
                "charity_ein": EIN,
                "amal_score": 82,
                "baseline_narrative": {"verdict": "solid"},
                "state": "generated",
            }
        )
        sql, _ = _upsert_sql(mock_execute)
        assert "`rich_narrative`" not in sql
        assert "`rich_strategic_narrative`" not in sql


def test_rich_write_touches_only_rich_narrative():
    """Regression guard: rich phase writes keep working and stay narrow."""
    repo = EvaluationRepository()
    with patch("src.db.repository.execute_query") as mock_execute:
        repo.upsert({"charity_ein": EIN, "rich_narrative": {"summary": "deep dive"}})
        sql, _ = _upsert_sql(mock_execute)
        assert "`rich_narrative`" in sql
        assert "`baseline_narrative`" not in sql
        assert "`state`" not in sql


def test_dataclass_without_explicit_state_does_not_write_state():
    repo = EvaluationRepository()
    evaluation = Evaluation(charity_ein=EIN, rich_narrative={"summary": "x"})
    with patch("src.db.repository.execute_query") as mock_execute:
        repo.upsert(evaluation)
        sql, _ = _upsert_sql(mock_execute)
        assert "`state`" not in sql


def test_explicit_state_still_written():
    """Regression guard: baseline's state='generated' still lands."""
    repo = EvaluationRepository()
    evaluation = Evaluation(
        charity_ein=EIN,
        amal_score=75,
        baseline_narrative={"verdict": "ok"},
        state="generated",
    )
    with patch("src.db.repository.execute_query") as mock_execute:
        repo.upsert(evaluation)
        sql, params = _upsert_sql(mock_execute)
        assert "`state`" in sql
        assert "generated" in params

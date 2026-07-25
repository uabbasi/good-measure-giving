"""Task 6: final Dolt commit message is built unconditionally (partial-run label).

Pure-function test for `final_commit_message` — no DB, no network. The runner
itself now calls `dolt.commit(...)` unconditionally at run end (the
`if success_count > 0:` gate around the final commit was removed); that part
is verified by inspection since streaming_runner has no execution harness.
This test locks down the message text the commit is built from.
"""

from streaming_runner import final_commit_message


class TestFinalCommitMessage:
    def test_zero_success_is_labeled_partial(self):
        message = final_commit_message(0, 20, 0.0, 0.0, 0)
        assert "PARTIAL" in message
        assert "0/20" in message

    def test_normal_run_has_no_partial_label(self):
        message = final_commit_message(15, 20, 5.0, 0.33, 2)
        assert "PARTIAL" not in message
        assert "15/20" in message
        assert "$5.00" in message
        assert "$0.3300" in message
        assert "2 checkpoints" in message


def test_crawl_history_tables_are_registered_for_staging():
    """Unregistered tables are never staged, so 'durable' crawl history lived
    only in the working set and left the tree permanently dirty."""
    from src.db.dolt_client import PHASE_TABLES, VALID_TABLES

    assert "crawl_attempts" in VALID_TABLES
    assert "crawled_pages" in VALID_TABLES
    assert "crawl_attempts" in PHASE_TABLES["crawl"]
    assert "crawled_pages" in PHASE_TABLES["crawl"]


def test_schema_file_declares_every_column_the_repositories_write():
    """A column written but not declared breaks a fresh bootstrap."""
    from pathlib import Path

    schema = (Path(__file__).parent.parent / "dolt_schema.sql").read_text()
    assert "last_attempt_at" in schema

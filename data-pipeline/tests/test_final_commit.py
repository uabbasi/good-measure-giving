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

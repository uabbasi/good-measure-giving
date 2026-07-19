import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFindRegressions:
    def test_finds_currently_null_with_historical_value(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "program_expense_ratio": None, "total_revenue": 1000}
        history = [
            {"program_expense_ratio": None, "total_revenue": 1000, "commit_hash": "c3"},
            {"program_expense_ratio": 0.85, "total_revenue": 1000, "commit_hash": "c2"},
        ]
        fields = {"program_expense_ratio", "total_revenue"}
        out = find_regressions(current, history, fields)
        assert out == [
            {
                "charity_ein": "12-3456789",
                "field": "program_expense_ratio",
                "current_value": None,
                "last_good_value": 0.85,
                "last_good_commit": "c2",
            }
        ]

    def test_no_regression_when_current_present(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "program_expense_ratio": 0.9}
        history = [{"program_expense_ratio": 0.85, "commit_hash": "c2"}]
        assert find_regressions(current, history, {"program_expense_ratio"}) == []


class _FakeDataRepo:
    """Records upsert calls; returns a fixed current row per EIN."""

    def __init__(self, current_by_ein: dict):
        self._current = current_by_ein
        self.upserts: list[dict] = []

    def get(self, ein):
        row = self._current.get(ein)
        return dict(row) if row is not None else None

    def upsert(self, row):
        self.upserts.append(dict(row))


class TestApplyAccumulation:
    def test_multi_field_apply_persists_both_fields_in_single_upsert(self):
        # Critical 1 regression guard: a charity with TWO regressed fields must
        # land BOTH in ONE upsert. The old per-field upsert (rebuilding
        # dict(current) each iteration) clobbered all but the last field.
        from bin.reconcile_charity_data import reconcile

        current = {
            "charity_ein": "12-3456789",
            "program_expense_ratio": None,
            "total_revenue": None,
            "net_assets": 5,  # present -> not a regression
        }
        history = [
            {
                "program_expense_ratio": 0.85,
                "total_revenue": 2000,
                "net_assets": 5,
                "commit_hash": "c2",
            }
        ]
        repo = _FakeDataRepo({"12-3456789": current})
        all_flags, skipped, processed = reconcile(
            ["12-3456789"], repo, lambda ein: list(history), apply=True
        )

        assert len(repo.upserts) == 1  # single upsert, NOT one-per-field
        persisted = repo.upserts[0]
        assert persisted["program_expense_ratio"] == 0.85
        assert persisted["total_revenue"] == 2000
        assert len(all_flags) == 2
        assert skipped == 0
        assert processed == 1


class TestSystemicFailure:
    def test_history_load_failure_counts_as_skip_not_clean(self):
        # Critical 2 core: a history-query failure must be counted as a SKIP
        # (so main can distinguish "queried, found nothing" from "never queried"),
        # and must never trigger an upsert.
        from bin.reconcile_charity_data import reconcile

        repo = _FakeDataRepo(
            {
                "12-3456789": {"charity_ein": "12-3456789", "program_expense_ratio": None},
                "98-7654321": {"charity_ein": "98-7654321", "program_expense_ratio": None},
            }
        )

        def boom(ein):
            raise RuntimeError("dolt down")

        all_flags, skipped, processed = reconcile(
            list(repo._current), repo, boom, apply=True
        )
        assert all_flags == []
        assert skipped == 2
        assert processed == 0
        assert repo.upserts == []  # never upsert when we could not query history

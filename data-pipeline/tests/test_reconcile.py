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

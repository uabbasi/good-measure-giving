import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFindRegressions:
    def test_finds_currently_null_with_historical_value(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "program_expense_ratio": None, "total_revenue": 1000}
        history = [
            {"program_expense_ratio": None, "total_revenue": 1000, "commit_hash": "c3", "commit_date": "2026-07-01"},
            {"program_expense_ratio": 0.85, "total_revenue": 1000, "commit_hash": "c2", "commit_date": "2026-06-01"},
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
                "last_good_commit_date": "2026-06-01",
                "last_good_attribution": None,
            }
        ]

    def test_no_regression_when_current_present(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "program_expense_ratio": 0.9}
        history = [{"program_expense_ratio": 0.85, "commit_hash": "c2"}]
        assert find_regressions(current, history, {"program_expense_ratio"}) == []

    def test_find_regressions_skips_field_when_current_metrics_json_has_a_value(self):
        """After the zero-coercion fix, a NULL column with metrics_json=0 is not a
        regression — it's a correctly-observed zero. Restoring would fabricate debt."""
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "26-3342933", "total_liabilities": None,
                   "metrics_json": {"total_liabilities": 0}}
        history = [{"total_liabilities": 861467, "commit_hash": "abc", "commit_date": "2026-03-09"}]

        assert find_regressions(current, history, {"total_liabilities"}) == []

    def test_find_regressions_rejects_a_candidate_older_than_the_confidence_window(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "93-2136609", "total_revenue": None, "metrics_json": {}}
        history = [{"total_revenue": 100000, "commit_hash": "old", "commit_date": "2019-01-25"}]

        assert find_regressions(current, history, {"total_revenue"}) == []

    def test_find_regressions_reports_the_candidate_age_for_human_review(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "total_revenue": None, "metrics_json": {}}
        history = [{"total_revenue": 5_000_000, "commit_hash": "abc123", "commit_date": "2026-07-01"}]

        flags = find_regressions(current, history, {"total_revenue"})

        assert len(flags) == 1
        assert flags[0]["last_good_value"] == 5_000_000
        assert flags[0]["last_good_commit_date"] == "2026-07-01"

    def test_find_regressions_scans_past_the_twentieth_history_row(self):
        """The real last-good value sat at depth 437-1017 on live data; a 20-row
        window found 0 of 25 genuine candidates."""
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "total_revenue": None, "metrics_json": {}}
        history = [{"total_revenue": None, "commit_hash": f"h{i}", "commit_date": "2026-07-01"}
                   for i in range(30)]
        history[25] = {"total_revenue": 7_000_000, "commit_hash": "deep", "commit_date": "2026-06-01"}

        flags = find_regressions(current, history, {"total_revenue"})

        assert len(flags) == 1 and flags[0]["last_good_commit"] == "deep"

    def test_restore_carries_source_attribution_from_the_same_commit(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "total_revenue": None, "metrics_json": {},
                   "source_attribution": {}}
        history = [{"total_revenue": 5_000_000, "commit_hash": "abc", "commit_date": "2026-07-01",
                    "source_attribution": {"total_revenue": {"source_name": "ProPublica"}}}]

        flags = find_regressions(current, history, {"total_revenue"})

        assert flags[0]["last_good_attribution"] == {"source_name": "ProPublica"}

    def test_no_filings_org_gets_no_financial_restore(self):
        """An org ProPublica shows as never having filed has no financials to restore."""
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "93-2136609", "total_revenue": None,
                   "metrics_json": {}, "no_filings": 1}
        history = [{"total_revenue": 100000, "commit_hash": "cn",
                    "commit_date": "2026-01-25"}]

        assert find_regressions(current, history, {"total_revenue"}) == []

    def test_candidate_exceeding_current_total_assets_is_rejected(self):
        """net_assets > total_assets is impossible with non-negative liabilities."""
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "81-2566656", "net_assets": None,
                   "metrics_json": {}, "no_filings": 0, "total_assets": 23205}
        history = [{"net_assets": 100000, "commit_hash": "cn", "commit_date": "2026-02-08"}]

        assert find_regressions(current, history, {"net_assets"}) == []

    def test_a_coherent_in_window_candidate_still_survives(self):
        """The guards must not reject everything — one real candidate must get through."""
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "83-1794093", "net_assets": None,
                   "metrics_json": {}, "no_filings": 0, "total_assets": 116544}
        history = [{"net_assets": 10222, "commit_hash": "real", "commit_date": "2026-03-07"}]

        flags = find_regressions(current, history, {"net_assets"})
        assert len(flags) == 1 and flags[0]["last_good_value"] == 10222


def test_report_is_stamped_with_run_scope_and_time():
    from bin.reconcile_charity_data import build_report

    report = build_report(flags=[{"field": "total_revenue"}], scope=["12-3456789"], run_at="2026-07-24T12:00:00")

    assert report["scope"] == ["12-3456789"]
    assert report["run_at"] == "2026-07-24T12:00:00"
    assert report["rows"] == [{"field": "total_revenue"}]


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
            "total_expenses": None,
            "total_revenue": None,
            "net_assets": 5,  # present -> not a regression
        }
        history = [
            {
                "total_expenses": 800_000,
                "total_revenue": 2000,
                "net_assets": 5,
                "commit_hash": "c2",
                "commit_date": "2026-06-01",
            }
        ]
        repo = _FakeDataRepo({"12-3456789": current})
        all_flags, skipped, processed = reconcile(
            ["12-3456789"], repo, lambda ein: list(history), apply=True
        )

        assert len(repo.upserts) == 1  # single upsert, NOT one-per-field
        persisted = repo.upserts[0]
        assert persisted["total_expenses"] == 800_000
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

    def test_processed_zero_is_systemic_failure(self):
        from bin.reconcile_charity_data import is_systemic_failure

        assert is_systemic_failure(processed=0, skipped=3) is True

    def test_skipped_greater_than_processed_is_systemic_failure(self):
        # A mostly-broken run (more EINs failed history-load than succeeded)
        # must not read as clean, even though processed > 0.
        from bin.reconcile_charity_data import is_systemic_failure

        assert is_systemic_failure(processed=2, skipped=3) is True

    def test_skipped_less_than_or_equal_processed_is_partial_not_systemic(self):
        from bin.reconcile_charity_data import is_systemic_failure

        assert is_systemic_failure(processed=5, skipped=2) is False
        assert is_systemic_failure(processed=5, skipped=5) is False

    def test_no_skips_is_clean(self):
        from bin.reconcile_charity_data import is_systemic_failure

        assert is_systemic_failure(processed=5, skipped=0) is False

    def test_processed_zero_is_systemic_even_with_no_skips(self):
        """--ein with a typo queried nothing; exiting 0 read as a clean bill of health."""
        from bin.reconcile_charity_data import is_systemic_failure

        assert is_systemic_failure(processed=0, skipped=0) is True
        assert is_systemic_failure(processed=0, skipped=5) is True
        assert is_systemic_failure(processed=1, skipped=5) is True
        assert is_systemic_failure(processed=10, skipped=0) is False
        assert is_systemic_failure(processed=10, skipped=2) is False

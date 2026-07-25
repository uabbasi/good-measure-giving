"""Tests for the crawl-attempt/page-history logging added to track crawl
robustness over time: raw_scraped_data only stores current state (one row
per charity+source, overwritten on each attempt), so a failed-then-recovered
attempt or a page that silently disappears between crawls leaves no trace
once a later attempt succeeds. crawl_attempts and crawled_pages are the
durable, append-only history for that.

These tests mock src.db.repository.execute_query (no live Dolt needed).
"""

from unittest.mock import patch

from src.db.repository import CrawlAttemptRepository, CrawledPageRepository

EIN = "12-3456789"


class TestCrawlAttemptRepository:
    def test_ensure_table_creates_expected_schema(self):
        repo = CrawlAttemptRepository()
        CrawlAttemptRepository._table_ensured = False
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.ensure_table()
        sql = mock_exec.call_args.args[0]
        assert "CREATE TABLE IF NOT EXISTS crawl_attempts" in sql
        assert "PRIMARY KEY (charity_ein, source, attempted_at)" in sql

    def test_ensure_table_only_runs_once_per_process(self):
        repo = CrawlAttemptRepository()
        CrawlAttemptRepository._table_ensured = False
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.ensure_table()
            repo.ensure_table()
        assert mock_exec.call_count == 1

    def test_record_success_inserts_expected_row(self):
        repo = CrawlAttemptRepository()
        CrawlAttemptRepository._table_ensured = True  # skip ensure_table's own call
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.record(EIN, "website", success=True, pages_found=12, pages_with_data=9)
        sql, params = mock_exec.call_args.args
        assert "INSERT INTO crawl_attempts" in sql
        assert params == (EIN, "website", True, None, 12, 9)

    def test_record_failure_includes_reason(self):
        repo = CrawlAttemptRepository()
        CrawlAttemptRepository._table_ensured = True
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.record(EIN, "website", success=False, failure_reason="CAPTCHA_BLOCKED: HTTP 403")
        _, params = mock_exec.call_args.args
        assert params == (EIN, "website", False, "CAPTCHA_BLOCKED: HTTP 403", None, None)

    def test_record_non_website_source_has_no_page_counts(self):
        repo = CrawlAttemptRepository()
        CrawlAttemptRepository._table_ensured = True
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.record(EIN, "propublica", success=True)
        _, params = mock_exec.call_args.args
        assert params[4] is None and params[5] is None  # pages_found, pages_with_data


class TestCrawledPageRepository:
    def test_ensure_table_creates_expected_schema(self):
        repo = CrawledPageRepository()
        CrawledPageRepository._table_ensured = False
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.ensure_table()
        sql = mock_exec.call_args.args[0]
        assert "CREATE TABLE IF NOT EXISTS crawled_pages" in sql
        assert "PRIMARY KEY (charity_ein, url)" in sql

    def test_record_pages_upserts_one_row_per_page(self):
        repo = CrawledPageRepository()
        CrawledPageRepository._table_ensured = True
        pages = [
            {"url": "https://x.org/", "had_data": True},
            {"url": "https://x.org/about", "had_data": False},
        ]
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.record_pages(EIN, pages)
        assert mock_exec.call_count == 1
        sql, params = mock_exec.call_args_list[0].args
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert params == (EIN, "https://x.org/", True, EIN, "https://x.org/about", False)

    def test_record_pages_skips_entries_without_url(self):
        repo = CrawledPageRepository()
        CrawledPageRepository._table_ensured = True
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.record_pages(EIN, [{"had_data": True}])
        mock_exec.assert_not_called()

    def test_record_pages_empty_list_is_a_noop(self):
        repo = CrawledPageRepository()
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.record_pages(EIN, [])
        mock_exec.assert_not_called()

    def test_record_pages_skips_a_url_too_long_for_the_column(self):
        """crawled_pages.url is VARCHAR(500); a long sitemap query string must not
        raise into the crawl's success path."""
        repo = CrawledPageRepository()
        CrawledPageRepository._table_ensured = True
        pages = [
            {"url": "https://x.org/" + "a" * 600, "had_data": True},
            {"url": "https://x.org/ok", "had_data": True},
        ]
        with patch("src.db.repository.execute_query") as mock_exec:
            repo.record_pages(EIN, pages)
        _, params = mock_exec.call_args.args
        assert params == (EIN, "https://x.org/ok", True)

    def test_get_missing_since_last_crawl_filters_on_last_seen_at(self):
        repo = CrawledPageRepository()
        with patch("src.db.repository.execute_query", return_value=[]) as mock_exec:
            repo.get_missing_since_last_crawl(EIN, "2026-07-23 12:00:00")
        sql, params = mock_exec.call_args.args
        assert "last_seen_at < %s" in sql
        assert params == (EIN, "2026-07-23 12:00:00")

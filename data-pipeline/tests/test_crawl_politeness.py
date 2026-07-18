"""H5: crawl politeness + terminal failure classification (pure-function tests)."""

import threading
from unittest.mock import MagicMock

from src.collectors.orchestrator import (
    DataCollectionOrchestrator,
    classify_failure,
    is_optional_website_failure,
)
from src.collectors.web_collector import WebsiteCollector
from src.constants import PER_DOMAIN_CONCURRENCY, TERMINAL_FAILURE_TTL_DAYS


class TestClassifyFailure:
    def test_captcha_is_terminal(self):
        assert classify_failure("CAPTCHA_BLOCKED: challenge page (HTTP 200)") == "captcha_blocked"

    def test_not_found_is_terminal(self):
        assert classify_failure("Organization not found for EIN 12-3456789") == "not found"

    def test_timeout_is_transient(self):
        assert classify_failure("Timeout") is None

    def test_none_and_empty(self):
        assert classify_failure(None) is None
        assert classify_failure("") is None

    def test_no_data_found_is_not_terminal(self):
        # "No data found on any pages" must NOT match the "not found" marker
        assert classify_failure("No data found on any pages") is None


class TestOptionalDemotion:
    def test_captcha_no_longer_demotes_website(self):
        assert is_optional_website_failure(["CAPTCHA_BLOCKED: challenge page (HTTP 200)"]) is False

    def test_http_429_no_longer_demotes(self):
        assert is_optional_website_failure(["CAPTCHA_BLOCKED: HTTP 429"]) is False

    def test_genuine_no_data_still_demotes(self):
        assert is_optional_website_failure(["No data found on any pages"]) is True

    def test_empty(self):
        assert is_optional_website_failure([]) is False


class TestPerDomainSemaphores:
    def test_same_domain_shares_semaphore(self):
        get_sem = WebsiteCollector._per_domain_semaphores(limit=2)
        a1 = get_sem("https://example.org/a")
        a2 = get_sem("https://example.org/b")
        b = get_sem("https://other.org/")
        assert a1 is a2
        assert a1 is not b
        assert a1._value == 2

    def test_default_limit_is_constant(self):
        assert PER_DOMAIN_CONCURRENCY == 2


def test_terminal_ttl_is_180_days():
    assert TERMINAL_FAILURE_TTL_DAYS == 180


class TestSingleRetryIncrementPerWebsiteFailure:
    """H5 follow-up: exactly ONE retry-count-advancing DB write per website failure.

    On the fetch path, _store_failed_crawl -> upsert(success=False) already
    increments retry_count (Task 1 semantics), so that path must NOT also call
    increment_retry_count — otherwise website backs off twice as fast as every
    other source.
    """

    def _make_orchestrator(self):
        orch = DataCollectionOrchestrator.__new__(DataCollectionOrchestrator)
        orch.logger = MagicMock()
        # Skip every non-website source so only the website block runs
        orch.skip_sources = {"propublica", "charity_navigator", "candid", "form990_grants", "bbb"}
        orch.frozen_sources = set()  # H12: not testing the freeze label here
        orch.blocked_sites = []
        orch._blocked_sites_lock = threading.Lock()
        orch.raw_data_repo = MagicMock()
        # No prior row: not fresh, no backoff skip
        orch.raw_data_repo.get_by_source.return_value = None
        orch.charity_repo = MagicMock()
        orch.website = MagicMock()
        orch._get_or_create_charity = lambda ein, name=None, website=None: ein
        return orch

    @staticmethod
    def _retry_advancing_writes(repo) -> int:
        """Count DB writes that advance retry_count: failure upserts + explicit increments."""
        failure_upserts = sum(
            1 for c in repo.upsert.call_args_list if c.kwargs.get("success") is False
        )
        return failure_upserts + repo.increment_retry_count.call_count

    def test_fetch_path_failure_advances_retry_count_once(self):
        orch = self._make_orchestrator()
        orch.website.collect_multi_page.return_value = (
            False,
            None,
            "CAPTCHA_BLOCKED: challenge page (HTTP 200)",
        )
        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")
        assert success is False
        assert self._retry_advancing_writes(orch.raw_data_repo) == 1

    def test_fetch_path_exception_advances_retry_count_once(self):
        orch = self._make_orchestrator()
        orch.website.collect_multi_page.side_effect = RuntimeError("boom")
        success, report = orch.fetch_charity_data("12-3456789", website_url="https://example.org")
        assert success is False
        assert self._retry_advancing_writes(orch.raw_data_repo) == 1

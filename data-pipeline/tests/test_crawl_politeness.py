"""H5: crawl politeness + terminal failure classification (pure-function tests)."""

from src.collectors.orchestrator import classify_failure, is_optional_website_failure
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

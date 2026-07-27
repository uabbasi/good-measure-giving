"""A charity BBB doesn't review is a verified negative, not a fetch failure.

BBB Wise Giving Alliance reviews only a subset of US charities. Of this
pipeline's 168 BBB rows, 119 failed — and every single one with the same
message, "Charity not found on BBB WGA". Zero scraping errors, zero blocking,
zero timeouts: the scraper works, it just correctly reports that most charities
aren't in the registry.

Recording that correct answer as success=False made BBB — a REQUIRED source —
fail for 71% of charities and take each one's entire crawl down with it. That
is what got the source frozen (H12). The workaround, orchestrator's
_is_bbb_not_found(), sniffed the error text to strip bbb from required_sources
after the fact. This fixes the root instead: the lookup succeeds and reports
what it found, which is nothing.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.bbb_collector import BBBCollector


class TestNotReviewedIsAVerifiedNegative:
    def _collector(self, review_url):
        c = BBBCollector()
        c._search_charity = lambda ein, name=None: review_url
        return c

    def test_fetch_succeeds_when_the_charity_is_not_in_the_registry(self):
        """The old behavior returned success=False here, failing a required source."""
        result = self._collector(None).fetch("12-3456789", name="Example Charity")
        assert result.success is True
        assert result.error is None
        payload = json.loads(result.raw_data)
        assert payload["bbb_not_reviewed"] is True

    def test_parse_marks_the_profile_not_reviewed_without_inventing_a_verdict(self):
        raw = json.dumps({"bbb_not_reviewed": True, "ein": "12-3456789"})
        result = self._collector(None).parse(raw, "12-3456789")
        assert result.success is True
        profile = result.parsed_data["bbb_profile"]
        assert profile["not_reviewed"] is True
        # Critically: absence of a review is NOT a failed review.
        assert profile["meets_standards"] is None
        assert profile["accredited"] is None
        assert profile["standards_not_met"] == []

    def test_a_reviewed_charity_is_unaffected(self):
        """Regression: the sentinel must not swallow real BBB HTML."""
        c = self._collector("https://give.org/charity-reviews/example")
        result = c.parse("<html><body><h1>Example</h1></body></html>", "12-3456789")
        assert result.success is True
        assert result.parsed_data["bbb_profile"].get("not_reviewed") is False

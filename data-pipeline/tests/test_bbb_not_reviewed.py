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


class TestTheVerifiedNegativeSurvivesTheSubstanceGate:
    """fetch() returning success was only half the fix — the payload still has
    to survive being stored.

    `_store_raw_content_only` rejects bodies below a per-source floor (bbb: 200
    bytes). The not-reviewed sentinel is ~47 bytes by design, so the substance
    gate rejected it, the orchestrator recorded
    sources_failed["bbb"] = "empty or failed to store content", bbb stayed in
    required_sources, and the whole crawl died — the exact H12 failure the
    sentinel was introduced to prevent.

    It survived review because `_is_bbb_not_found()` masked it: that helper
    sniffs for the LEGACY text "not found on BBB", which pre-fix rows still
    carried, so those charities got bbb stripped from required_sources and
    passed. Charities whose legacy row had since been reset (last_failure_reason
    "reset: failure TTL expired") carried no such string and failed. Whether a
    charity crawled at all came down to which error text it happened to have on
    file, and the failures grow as those legacy rows age out.

    Precedent for the fix: `_has_content_substance` already waves through
    form990_grants' NO_XML_SENTINEL as a legitimately short body.
    """

    def _orch(self, existing=None):
        from unittest.mock import MagicMock

        from src.collectors.orchestrator import DataCollectionOrchestrator

        orch = object.__new__(DataCollectionOrchestrator)
        orch.logger = None
        orch.raw_data_repo = MagicMock()
        orch.raw_data_repo.get_by_source.return_value = existing
        orch.crawl_attempt_repo = MagicMock()
        return orch

    def _sentinel(self, ein="12-3456789"):
        return json.dumps({"bbb_not_reviewed": True, "ein": ein})

    def test_the_not_reviewed_sentinel_counts_as_substance(self):
        orch = self._orch()
        assert orch._has_content_substance(self._sentinel(), "bbb") is True

    def test_storing_the_sentinel_succeeds_so_bbb_is_not_a_failed_source(self):
        """Returning False here is what set sources_failed["bbb"] and killed the crawl."""
        orch = self._orch(existing=None)
        stored = orch._store_raw_content_only("12-3456789", "bbb", self._sentinel(), "json")
        assert stored is True, "the verified negative must store, not be rejected as empty"
        assert orch.raw_data_repo.upsert.called

    def test_a_genuinely_empty_bbb_body_is_still_rejected(self):
        """Regression: the fix must recognize the sentinel, NOT lower the floor."""
        orch = self._orch()
        assert orch._has_content_substance("", "bbb") is False
        assert orch._has_content_substance("<html><body></body></html>", "bbb") is False

    def test_an_unrelated_short_json_body_is_still_rejected(self):
        """Only the not-reviewed sentinel is privileged, not any small JSON."""
        orch = self._orch()
        assert orch._has_content_substance(json.dumps({"ein": "12-3456789"}), "bbb") is False


class TestStandardsNotMetIsAVerdict:
    """BBB renders a failure as "Standards Not Met". None of the text-branch
    checks matched that wording — "does not meet" is not a substring of
    "standards not met" — so status_text was set while meets_standards stayed
    None. Result: 5 charities BBB judged to FAIL were stored as unevaluated,
    indistinguishable downstream from a charity BBB never reviewed.
    """

    def _status(self, label, classes="evaluation-status"):
        from bs4 import BeautifulSoup
        from src.collectors.bbb_collector import BBBCollector
        html = (f'<div class="{classes}"><span class="status-value">{label}</span></div>')
        soup = BeautifulSoup(html, "html.parser")
        return BBBCollector()._extract_overall_status(soup)

    def test_standards_not_met_is_recorded_as_a_failure(self):
        d = self._status("Standards Not Met")
        assert d["meets_standards"] is False
        assert d["status_text"] == "Standards Not Met"

    def test_does_not_meet_standards_phrasing_still_works(self):
        d = self._status("Does Not Meet Standards")
        assert d["meets_standards"] is False

    def test_meets_standards_is_unaffected(self):
        d = self._status("Meets Standards")
        assert d["meets_standards"] is True

    def test_did_not_disclose_has_no_verdict_but_keeps_its_status(self):
        """Non-participation is neither pass nor fail — but it must not vanish."""
        d = self._status("Did Not Disclose")
        assert d["meets_standards"] is None
        assert d["status_text"] == "Did Not Disclose"

    def test_review_in_progress_has_no_verdict_but_keeps_its_status(self):
        d = self._status("Review in Progress")
        assert d["meets_standards"] is None
        assert d["status_text"] == "Review in Progress"

"""The citation judge may only block publication on an observed contradiction.

Root cause of the 2026-07-26 trial's export collapse: 19 of 25 charities were
blocked, 92 of their 130 blocking errors coming from this judge. Nearly all of
them said some version of "the claim is not present in the fetched content" --
because the judge had not actually put the content in front of the model.

Four defects compounded, all pushing the same direction (absence of
confirmation -> blocking error):

1. `should_skip` marks irs.gov / propublica.org / charitynavigator.org as
   trusted, then stored the literal string "[Trusted source - ...]" in
   `url_content` and asked the LLM whether the claim was supported by it.
   57% of citations (2,263 of the first 4,000) point at those three domains.
   "Trust it, don't check it" became "check it against a placeholder."
2. Content was fetched with a 10,000-char cap and then re-truncated to
   `content[:2000]` when building the prompt -- for a charity profile page,
   the page chrome, not the data.
3. The prompt's severity guide made `error` cover "citation doesn't support
   the claim" as well as "content contradicts the claim".
4. Its only softer tier was for unreachable URLs, which are handled in Python
   and never reach the model -- so "I cannot confirm this from what you gave
   me" had nowhere to go but `error`.

The invariant these tests pin: a blocking error requires the model to have
positively observed a contradiction. Everything else is a warning.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.citation_judge import CitationJudge
from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import Severity
from src.judges.url_verifier import FetchResult


def _output(urls):
    markers = " ".join(f"Claim {i+1}.[{i+1}]" for i in range(len(urls)))
    return {
        "narrative": {
            "content": markers,
            "all_citations": [
                {"id": f"[{i+1}]", "source_url": u, "label": f"Source {i+1}"}
                for i, u in enumerate(urls)
            ],
        }
    }


def _real_verifier(fetch_result=None):
    """A real URLVerifier -- so should_skip uses the actual SKIP_DOMAINS
    logic under test -- with only the network call stubbed out."""
    import tempfile

    from src.judges.url_verifier import URLVerifier

    v = URLVerifier(cache_dir=Path(tempfile.mkdtemp()))
    v.fetch = Mock(return_value=fetch_result or FetchResult(success=True, content="x" * 50, status_code=200))
    return v


class TestTrustedSourcesAreNotJudged:
    """A source we deliberately chose not to fetch must not be judged."""

    def test_only_fetched_citations_reach_the_model(self):
        """The realistic mix: citation 1 trusted, citation 2 actually fetched.

        Citation 1 must be absent from the evidence handed to the model --
        not present as a placeholder it can then report as unsupported.
        """
        judge = CitationJudge(JudgeConfig(), url_verifier=_real_verifier())
        captured = {}

        def fake_verify(output, citations, url_content, context):
            captured["url_content"] = url_content
            return None

        with patch.object(judge, "_verify_claims_with_llm", side_effect=fake_verify):
            judge.validate(
                _output(
                    [
                        "https://www.charitynavigator.org/ein/272725150",
                        "https://example.org/annual-report",
                    ]
                ),
                {},
            )

        assert list(captured["url_content"]) == [2], (
            "A trusted-skipped citation was handed to the LLM as evidence. "
            f"Got keys: {list(captured['url_content'])}"
        )
        assert "Trusted source" not in str(captured["url_content"])

    def test_trusted_citation_is_not_counted_as_a_failed_fetch(self):
        judge = CitationJudge(JudgeConfig(), url_verifier=_real_verifier())
        with patch.object(judge, "_verify_claims_with_llm", return_value=None):
            verdict = judge.validate(
                _output(["https://projects.propublica.org/nonprofits/organizations/1"]), {}
            )
        assert verdict.metadata.get("urls_failed") == 0
        assert verdict.metadata.get("urls_skipped_trusted") == 1

    def test_no_llm_call_when_every_citation_is_trusted(self):
        judge = CitationJudge(JudgeConfig(), url_verifier=_real_verifier())
        with patch.object(judge, "_verify_claims_with_llm") as m:
            judge.validate(_output(["https://www.irs.gov/pub/990.pdf"]), {})
        assert not m.called, "Asked the LLM to verify with no content to verify against"


class TestFetchedContentReachesTheModelWhole:
    def test_content_is_not_re_truncated_below_the_fetch_cap(self):
        """The prompt must carry what the verifier fetched, not a 2k prefix.

        Asserts against the prompt the LLM client actually receives -- the
        truncation lives in prompt assembly, so checking url_content instead
        would pass whether or not the bug is present.
        """
        body = "PAGE CHROME " * 200 + "PROGRAM EXPENSE RATIO 71.4%" + " tail" * 400
        assert body.index("PROGRAM EXPENSE RATIO") > 2000  # past the old cutoff

        verifier = _real_verifier(FetchResult(success=True, content=body, status_code=200))

        judge = CitationJudge(JudgeConfig(), url_verifier=verifier)
        client = Mock()
        client.generate.return_value = Mock(text='{"issues":[]}', cost_usd=0.0)

        with patch.object(judge, "get_llm_client", return_value=client):
            judge.validate(_output(["https://example.org/financials"]), {})

        prompt = client.generate.call_args.kwargs["prompt"]
        assert "PROGRAM EXPENSE RATIO 71.4%" in prompt, (
            "The claim's supporting text was truncated away before the model saw it"
        )


class TestOnlyContradictionsBlock:
    """The LLM's severity is advisory; only an observed contradiction blocks."""

    def _issue(self, **kw):
        base = {
            "citation_index": 1,
            "field": "citation_1",
            "severity": "error",
            "message": "m",
            "claim": "c",
            "evidence": "e",
        }
        base.update(kw)
        return base

    def _run(self, issue_dict):
        from src.judges.citation_judge import CitationVerificationResult

        judge = CitationJudge(JudgeConfig(), url_verifier=_real_verifier())

        result = CitationVerificationResult(issues=[issue_dict], verified_count=0, failed_count=1)
        client = Mock()
        client.generate.return_value = Mock(text=result.model_dump_json(), cost_usd=0.0)

        with patch.object(judge, "get_llm_client", return_value=client):
            verdict = judge.validate(_output(["https://example.org/a"]), {})
        return verdict

    def test_unconfirmed_claim_is_a_warning_not_an_error(self):
        verdict = self._run(
            self._issue(
                contradicted=False,
                message="The provided URL does not contain the claimed score.",
            )
        )
        sev = [i.severity for i in verdict.issues if i.field == "citation_1"]
        assert Severity.ERROR not in sev, (
            "An unconfirmed claim blocked publication. Only a contradiction may."
        )
        assert Severity.WARNING in sev

    def test_unparseable_pdf_is_a_warning_not_an_error(self):
        verdict = self._run(
            self._issue(
                contradicted=False,
                message="The provided PDF content is corrupted and cannot be parsed.",
            )
        )
        assert Severity.ERROR not in [i.severity for i in verdict.issues]

    def test_real_contradiction_still_blocks(self):
        verdict = self._run(
            self._issue(
                contradicted=True,
                message="Content states a four-star rating, not a score of 91.0/100.",
            )
        )
        assert Severity.ERROR in [i.severity for i in verdict.issues]
        assert verdict.passed is False

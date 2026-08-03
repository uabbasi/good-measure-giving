"""Two ways the factual judge withheld a correct charity's page.

Both were failures on our side recorded as verdicts about the charity -- the
same pattern the citation judge and the S-005 synthesize guard already taught.

1. EIN 99-3032347 (Institute for Understanding Anti-Palestinian Racism).
   claims_zakat_eligible=0, wallet_tag=SADAQAH-ELIGIBLE, and the crawl evidence
   says the site never mentions zakat. Every source agrees. The model still
   emitted `error`: "the website does not mention accepting zakat donations,
   but the wallet tag indicates it is zakat-eligible" -- SADAQAH-ELIGIBLE is
   the tag for a charity that does NOT claim zakat, so it read "eligible" and
   inverted the meaning. factual_judge.txt line 115 spells this exact case out
   as CORRECT; the model violated an explicit instruction, so more prompt text
   is not the fix. _quick_checks already settles wallet-tag agreement
   deterministically against an independently derived source tag
   (judge_phase._wallet_tag_from_zakat_claim), so the model's opinion on that
   one question is redundant -- and it is the redundant copy that fabricates.

2. EIN 01-0548371 (Muslim Legal Fund of America). The model's structured
   response was cut off mid-string: "Invalid JSON: EOF while parsing a string".
   The retry loop only recognised rate limits, so a truncated generation fell
   straight through to "Could not complete LLM verification" -- an unpublishable
   charity because one response got clipped. A clipped response is transient in
   exactly the way a 429 is.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import CONSENSUS_ROLLS, FactualJudge, FactualVerificationResult
from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import Severity


def _issue_severity(field: str, message: str) -> Severity:
    """Severity the judge lands on for one model-reported ERROR."""
    payload = FactualVerificationResult(
        issues=[
            {
                "field": field,
                "severity": "error",
                "discrepancy_kind": "contradiction",
                "message": message,
            }
        ],
        claims_checked=1,
        claims_verified=0,
    )
    judge = FactualJudge(JudgeConfig())
    client = Mock()
    client.generate.return_value = Mock(text=payload.model_dump_json(), cost_usd=0.0)
    with patch.object(judge, "get_llm_client", return_value=client):
        result = judge._verify_claims_with_llm({"narrative": {"content": "x"}}, {})
    return result.issues[0].severity


class TestWalletTagZakatAgreementIsDeterministic:
    """_quick_checks owns this comparison. The model must not re-litigate it."""

    def test_the_verdict_that_blocked_99_3032347_does_not_block(self):
        assert (
            _issue_severity(
                "claims_zakat_eligible",
                "The charity's website does not mention accepting zakat "
                "donations, but the wallet tag indicates it is zakat-eligible.",
            )
            != Severity.ERROR
        )

    def test_wallet_tag_field_complaint_does_not_block(self):
        assert (
            _issue_severity(
                "wallet_tag",
                "wallet_tag is SADAQAH-ELIGIBLE but the zakat evidence is absent",
            )
            != Severity.ERROR
        )

    def test_an_unrelated_zakat_claim_still_blocks(self):
        """Narrowness guard: only the wallet-tag agreement question is deferred.

        A fabricated zakat figure has no deterministic check behind it and must
        keep blocking.
        """
        assert (
            _issue_severity(
                "zakat_narrative",
                "The narrative states $4.2M was distributed as zakat; the "
                "Form 990 reports no such program.",
            )
            == Severity.ERROR
        )

    def test_a_real_wallet_tag_mismatch_is_still_caught_deterministically(self):
        """The deterministic check is what we are deferring TO -- prove it fires."""
        judge = FactualJudge(JudgeConfig())
        issues = judge._quick_checks(
            {"evaluation": {"wallet_tag": "ZAKAT-ELIGIBLE"}, "financials": {}},
            {"metrics": {"wallet_tag": "SADAQAH-ELIGIBLE"}},
        )
        assert [i for i in issues if i.severity == Severity.ERROR and i.field == "wallet_tag"]


class TestTruncatedResponseIsRetried:
    def test_a_clipped_response_is_retried_and_the_charity_survives(self):
        """First call returns truncated JSON, second returns a clean verdict.

        validate() takes up to CONSENSUS_ROLLS independent rolls (the gate
        flipped on identical content at temperature 0), and stops once the
        remaining rolls cannot move the majority. Two clean rolls settle it,
        so the cost here is: the truncated first roll (2 calls, one of them
        the retry) plus one more clean roll.
        """
        good = FactualVerificationResult(
            issues=[], claims_checked=3, claims_verified=3
        ).model_dump_json()
        judge = FactualJudge(JudgeConfig())
        client = Mock()
        client.generate.side_effect = [
            Mock(text='{"issues": [{"field": "revenue", "messa', cost_usd=0.0),
            Mock(text=good, cost_usd=0.0),
        ] + [Mock(text=good, cost_usd=0.0) for _ in range(CONSENSUS_ROLLS - 1)]
        with patch.object(judge, "get_llm_client", return_value=client), patch.object(
            judge, "_escalated_client", return_value=client
        ), patch("src.judges.factual_judge.time.sleep"):
            verdict = judge.validate({"narrative": {"content": "x"}}, {})

        # truncated roll (2 calls, incl. the retry) + 1 clean roll, at which
        # point two agreeing rolls fix the majority and the third is not bought
        assert client.generate.call_count == 3
        assert client.generate.call_count < CONSENSUS_ROLLS + 1, (
            "the roll that cannot change the verdict was paid for anyway"
        )
        assert not [
            i
            for i in verdict.issues
            if i.severity == Severity.ERROR and i.field == "llm_verification"
        ], "a truncated response still cost the charity its page"
        assert verdict.passed

    def test_an_unparseable_response_escalates_to_the_stronger_model(self):
        """Retrying the same model is useless when the failure is deterministic.

        On 01-0548371 the factual judge's response was 67,719 chars, 64,000+ of
        them a literal '0' repeated inside one JSON string -- byte-identical
        across three attempts at temperature 0, from a prompt containing no
        such run. flash-lite degenerates into a repetition loop on this
        charity, so the same model cannot produce a different answer.
        score_judge.py already escalates to gemini-2.5-flash for the same
        class of flash-lite failure.
        """
        good = FactualVerificationResult(
            issues=[], claims_checked=3, claims_verified=3
        ).model_dump_json()
        judge = FactualJudge(JudgeConfig())
        weak = Mock()
        weak.generate.return_value = Mock(text='{"issues": [{"f' + "0" * 500, cost_usd=0.0)
        strong = Mock()
        strong.generate.return_value = Mock(text=good, cost_usd=0.0)

        with patch.object(judge, "get_llm_client", return_value=weak), patch.object(
            judge, "_escalated_client", return_value=strong
        ), patch("src.judges.factual_judge.time.sleep"):
            verdict = judge.validate({"narrative": {"content": "x"}}, {})

        assert strong.generate.called, "never escalated off the degenerating model"
        assert verdict.passed
        assert not [
            i
            for i in verdict.issues
            if i.severity == Severity.ERROR and i.field == "llm_verification"
        ]

    def test_persistent_truncation_still_fails_closed(self):
        """Retrying is not the same as ignoring. An unverified narrative
        must not publish -- exhausting the retries still blocks."""
        judge = FactualJudge(JudgeConfig())
        client = Mock()
        client.generate.return_value = Mock(text='{"issues": [{"fiel', cost_usd=0.0)
        with patch.object(judge, "get_llm_client", return_value=client), patch.object(
            judge, "_escalated_client", return_value=client
        ), patch("src.judges.factual_judge.time.sleep"):
            verdict = judge.validate({"narrative": {"content": "x"}}, {})

        assert not verdict.passed
        assert [
            i
            for i in verdict.issues
            if i.severity == Severity.ERROR and i.field == "llm_verification"
        ]

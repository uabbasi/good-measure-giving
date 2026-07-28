"""The factual judge may only block on a contradiction or a fabrication.

Its prompt already forbade what it did -- "warning: Claim can't be verified
(no corresponding source data)", "CRITICAL: Do NOT Report as Errors ...
Percentage differences under 1 percentage point" -- and the model emitted
`error` anyway. That is the same lesson the citation judge taught: prompt
guidance is advisory, so the gate belongs in code.

Observed on EIN 87-2410117 and the 2026-07-26 trial:
  - "program expense ratio is 50.3%, but the source data shows 50.29%"
    -> a 0.01pp difference, blocking publication, and the model's own text
       calls it "a minor discrepancy"
  - "total revenue of $205,225, but the source data shows $205,225"
    -> identical values reported as a mismatch
  - "claims 98% of expenses are domestic, but the source data does not
    provide this specific breakdown" -> absence of data, not a false claim

The prompt also contradicted itself: a value absent from the source was an
`error` under one rule ("This is fabrication") and a `warning` under another
("Claim can't be verified"). The model had to guess. It now reports which one
it means, and only those two kinds may block.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import numeric_agreement


class TestNumericAgreement:
    """Deterministic tolerance -- not left to the model's judgement."""

    def test_rounding_to_two_decimals_agrees(self):
        assert numeric_agreement("50.3%", "50.29") is True

    def test_identical_values_agree(self):
        assert numeric_agreement("$205,225", "205225") is True

    def test_working_capital_months_rounding_agrees(self):
        assert numeric_agreement("1.3", "1.32") is True

    def test_percentage_point_rounding_agrees(self):
        assert numeric_agreement("30%", "30.2") is True

    def test_large_dollar_amounts_within_one_percent_agree(self):
        assert numeric_agreement("$816K", "816038") is None or numeric_agreement("816000", "816038") is True

    def test_a_real_financial_discrepancy_does_not_agree(self):
        assert numeric_agreement("$35,399,389", "10889699") is False

    def test_a_real_working_capital_discrepancy_does_not_agree(self):
        assert numeric_agreement("10.7", "12.84") is False

    def test_board_counts_do_not_agree(self):
        assert numeric_agreement("2", "6") is False

    def test_non_numeric_returns_none(self):
        assert numeric_agreement("a two-member board", "six") is None
        assert numeric_agreement(None, "6") is None


class TestOnlyContradictionsAndFabricationsBlock:
    def _severity(self, kind, sev="error", claim=None, source=None):
        from unittest.mock import Mock, patch

        from src.judges.factual_judge import FactualJudge, FactualVerificationResult
        from src.judges.schemas.config import JudgeConfig

        payload = FactualVerificationResult(
            issues=[
                {
                    "field": "program_expense_ratio",
                    "severity": sev,
                    "discrepancy_kind": kind,
                    "message": "m",
                    "claim_value": claim,
                    "source_value": source,
                }
            ],
            claims_checked=1,
            claims_verified=0,
        )
        judge = FactualJudge(JudgeConfig())
        client = Mock()
        client.generate.return_value = Mock(text=payload.model_dump_json(), cost_usd=0.0)
        with patch.object(judge, "get_llm_client", return_value=client):
            res = judge._verify_claims_with_llm({"narrative": {"content": "x"}}, {})
        return res.issues[0].severity

    def test_contradiction_blocks(self):
        from src.judges.schemas.verdict import Severity

        assert self._severity("contradiction", claim="35399389", source="10889699") == Severity.ERROR

    def test_fabrication_blocks(self):
        from src.judges.schemas.verdict import Severity

        assert self._severity("fabrication") == Severity.ERROR

    def test_unverifiable_does_not_block(self):
        from src.judges.schemas.verdict import Severity

        assert self._severity("unverifiable") == Severity.WARNING

    def test_rounding_kind_does_not_block(self):
        from src.judges.schemas.verdict import Severity

        assert self._severity("rounding") != Severity.ERROR

    def test_numbers_within_tolerance_never_block_whatever_the_model_said(self):
        from src.judges.schemas.verdict import Severity

        sev = self._severity("contradiction", claim="50.3%", source="50.29")
        assert sev != Severity.ERROR, (
            "A 0.01pp difference blocked publication despite the model calling "
            "it a contradiction"
        )


class TestMethodologyDivergentMetricsDoNotBlock:
    """fundraising_efficiency and working_capital have two legitimate values:
    OUR figure (Form 990 expenses / IRS-reported contributions) and Charity
    Navigator's own published figure, which uses a different basis and often
    a different fiscal year. A donor reads "$0.09 per $1 raised" and "$0.04
    per $1 raised" as the same story -- efficient fundraising -- so a real
    numeric gap here is not a fact anyone got wrong. Withholding a charity's
    page over it is the actual defect.

    Observed: 13-3626299 ours $0.09 vs CN $0.04; 01-0548371 ours $0.18 vs CN
    $0.15; 87-2410117 ours $0.31 vs CN $0.25 fundraising efficiency, and 10.7
    vs CN's 12.84 months working capital.

    This must NOT become a blanket "contradiction never blocks" rule --
    test_contradiction_blocks (a real revenue mismatch) must keep blocking.
    """

    def test_fundraising_efficiency_disagreement_does_not_block(self):
        from unittest.mock import Mock, patch

        from src.judges.factual_judge import FactualJudge, FactualVerificationResult
        from src.judges.schemas.config import JudgeConfig
        from src.judges.schemas.verdict import Severity

        payload = FactualVerificationResult(
            issues=[
                {
                    "field": "fundraising_efficiency",
                    "severity": "error",
                    "discrepancy_kind": "contradiction",
                    "message": "Narrative states $0.09 per $1 raised, but Charity "
                    "Navigator reports $0.04.",
                    "claim_value": "$0.09",
                    "source_value": "$0.04",
                }
            ],
            claims_checked=1,
            claims_verified=0,
        )
        judge = FactualJudge(JudgeConfig())
        client = Mock()
        client.generate.return_value = Mock(text=payload.model_dump_json(), cost_usd=0.0)
        with patch.object(judge, "get_llm_client", return_value=client):
            res = judge._verify_claims_with_llm({"narrative": {"content": "x"}}, {})

        assert res.issues[0].severity != Severity.ERROR, (
            "A real but immaterial fundraising-efficiency basis gap (ours vs "
            "CN's own figure) blocked publication"
        )

    def test_working_capital_disagreement_does_not_block(self):
        from unittest.mock import Mock, patch

        from src.judges.factual_judge import FactualJudge, FactualVerificationResult
        from src.judges.schemas.config import JudgeConfig
        from src.judges.schemas.verdict import Severity

        payload = FactualVerificationResult(
            issues=[
                {
                    "field": "working_capital",
                    "severity": "error",
                    "discrepancy_kind": "contradiction",
                    "message": "Narrative states 10.7 months of working capital, but "
                    "Charity Navigator reports 12.84 months.",
                    "claim_value": "10.7",
                    "source_value": "12.84",
                }
            ],
            claims_checked=1,
            claims_verified=0,
        )
        judge = FactualJudge(JudgeConfig())
        client = Mock()
        client.generate.return_value = Mock(text=payload.model_dump_json(), cost_usd=0.0)
        with patch.object(judge, "get_llm_client", return_value=client):
            res = judge._verify_claims_with_llm({"narrative": {"content": "x"}}, {})

        assert res.issues[0].severity != Severity.ERROR, (
            "A real but immaterial working-capital basis gap (10.7 vs CN's "
            "12.84 months) blocked publication"
        )

    def test_unrelated_revenue_contradiction_still_blocks(self):
        """Regression guard: the methodology-divergent carve-out must be
        narrow, not a general amnesty for any 'contradiction'."""
        from unittest.mock import Mock, patch

        from src.judges.factual_judge import FactualJudge, FactualVerificationResult
        from src.judges.schemas.config import JudgeConfig
        from src.judges.schemas.verdict import Severity

        payload = FactualVerificationResult(
            issues=[
                {
                    "field": "total_revenue",
                    "severity": "error",
                    "discrepancy_kind": "contradiction",
                    "message": "Narrative states $35,399,389 in revenue, but the "
                    "source data shows $10,889,699.",
                    "claim_value": "35399389",
                    "source_value": "10889699",
                }
            ],
            claims_checked=1,
            claims_verified=0,
        )
        judge = FactualJudge(JudgeConfig())
        client = Mock()
        client.generate.return_value = Mock(text=payload.model_dump_json(), cost_usd=0.0)
        with patch.object(judge, "get_llm_client", return_value=client):
            res = judge._verify_claims_with_llm({"narrative": {"content": "x"}}, {})

        assert res.issues[0].severity == Severity.ERROR


class TestMalformedSeverityIsNotTheCharitysFault:
    """A model typo in OUR schema must not block a charity's publication.

    Real occurrence: after `discrepancy_kind` was added, the model began
    putting kind values into the severity field. `Severity("unverifiable")`
    raised, the whole verification was abandoned, and the judge recorded
    "Could not complete LLM verification" as a blocking error -- our tooling
    failing, charged to the charity. Same shape as every other bug in this
    class.
    """

    def test_unknown_severity_string_does_not_abandon_the_verification(self):
        from unittest.mock import Mock, patch

        from src.judges.factual_judge import FactualJudge, FactualVerificationResult
        from src.judges.schemas.config import JudgeConfig
        from src.judges.schemas.verdict import Severity

        payload = FactualVerificationResult(
            issues=[
                {
                    "field": "domestic_burn_rate",
                    "severity": "unverifiable",  # a kind, not a severity
                    "discrepancy_kind": "unverifiable",
                    "message": "source data does not cover this",
                }
            ],
            claims_checked=1,
            claims_verified=0,
        )
        judge = FactualJudge(JudgeConfig())
        client = Mock()
        client.generate.return_value = Mock(text=payload.model_dump_json(), cost_usd=0.0)
        with patch.object(judge, "get_llm_client", return_value=client):
            res = judge._verify_claims_with_llm({"narrative": {"content": "x"}}, {})

        assert res is not None, "One bad severity string discarded every finding"
        assert res.issues[0].severity == Severity.WARNING

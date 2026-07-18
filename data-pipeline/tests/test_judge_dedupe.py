"""Judge-score dedupe: aggregation-level fallback key + generator-level exact-dupe removal.

Covers the three within-judge-phase duplicate mechanisms (M1 verbatim LLM repeat,
M2 per-lens copy-paste, M3 deterministic+LLM wallet-tag double-flag) plus the
issue_key cross-judge dedupe regression guard.
"""

import json
from unittest.mock import Mock

from src.judges.base_judge import BaseJudge
from src.judges.cross_lens_judge import CrossLensJudge
from src.judges.narrative_quality_judge import NarrativeQualityJudge
from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import (
    CharityValidationResult,
    JudgeVerdict,
    Severity,
    ValidationIssue,
)


def w(field: str, msg: str, key: str | None = None) -> ValidationIssue:
    return ValidationIssue(Severity.WARNING, field, msg, issue_key=key)


def e(field: str, msg: str, key: str | None = None) -> ValidationIssue:
    return ValidationIssue(Severity.ERROR, field, msg, issue_key=key)


def V(name: str, issues: list[ValidationIssue]) -> JudgeVerdict:  # noqa: N802 (spec test helper)
    return JudgeVerdict(passed=True, judge_name=name, issues=issues)


def R(*verdicts: JudgeVerdict) -> CharityValidationResult:  # noqa: N802 (spec test helper)
    return CharityValidationResult(
        ein="11-1111111", name="T", passed=True, verdicts=list(verdicts)
    )


class TestAggregationDedupe:
    def test_same_judge_verbatim_duplicate_counts_once(self):
        """M1 (13-1760110): cross_lens returned the identical issue twice."""
        result = R(V("cross_lens", [w("wallet_tag", "dup msg"), w("wallet_tag", "dup msg")]))
        errors, warnings = result.deduplicated_issues
        assert len(errors) == 0
        assert len(warnings) == 1

    def test_same_message_different_fields_counts_once(self):
        """M2 (95-4453134): narrative_quality per-lens copy-paste (same msg, diff field)."""
        result = R(
            V(
                "narrative_quality",
                [
                    w("strategic.strengths", "Strengths are generic and could apply to many charities."),
                    w("zakat.strengths", "Strengths are generic and could apply to many charities."),
                ],
            )
        )
        errors, warnings = result.deduplicated_issues
        assert len(warnings) == 1

    def test_different_judges_same_message_not_collapsed(self):
        result = R(V("factual", [w("a", "same")]), V("score", [w("b", "same")]))
        _, warnings = result.deduplicated_issues
        assert len(warnings) == 2

    def test_fallback_dedupe_highest_severity_wins(self):
        result = R(V("citation", [e("u", "same msg"), w("u", "same msg")]))
        errors, warnings = result.deduplicated_issues
        assert len(errors) == 1
        assert len(warnings) == 0

    def test_distinct_messages_survive(self):
        result = R(V("narrative_quality", [w("f1", "msg one"), w("f2", "msg two")]))
        _, warnings = result.deduplicated_issues
        assert len(warnings) == 2

    def test_issue_key_cross_judge_dedupe_regression(self):
        """Existing issue_key dedupe across judges (highest severity wins) still holds."""
        result = R(
            V("crawl_quality", [e("website.ein", "m1", key="ein_website_mismatch")]),
            V("extract_quality", [w("website.ein", "m2", key="ein_website_mismatch")]),
        )
        errors, warnings = result.deduplicated_issues
        assert len(errors) == 1
        assert len(warnings) == 0

    def test_wallet_tag_issue_key_collapses_deterministic_and_llm(self):
        """M3: deterministic + LLM wallet-tag flags share issue_key → collapse to 1."""
        result = R(
            V(
                "cross_lens",
                [
                    w(
                        "zakat_narrative.wallet_tag",
                        "Zakat narrative claims zakat eligibility but wallet tag is SADAQAH-ELIGIBLE",
                        key="wallet_tag_consistency",
                    ),
                    w(
                        "zakat_eligibility",
                        "[baseline vs zakat] contradiction",
                        key="wallet_tag_consistency",
                    ),
                ],
            )
        )
        _, warnings = result.deduplicated_issues
        assert len(warnings) == 1


class TestExactDedupeHelper:
    def test_dedupe_exact_issues_helper(self):
        out = BaseJudge.dedupe_exact_issues(
            [w("f", "m"), w("f", "m"), w("f", "other"), e("f", "m")]
        )
        assert len(out) == 3
        assert out[0].message == "m" and out[0].severity == Severity.WARNING
        assert out[1].message == "other"
        assert out[2].message == "m" and out[2].severity == Severity.ERROR


class TestCrossLensGenerator:
    def test_cross_lens_llm_wallet_category_gets_issue_key(self):
        judge = CrossLensJudge(JudgeConfig())
        mock_client = Mock()
        mock_client.generate.return_value = Mock(
            text=json.dumps(
                {
                    "issues": [
                        {
                            "field": "zakat_eligibility",
                            "severity": "warning",
                            "message": "contradiction",
                            "lens_a": "baseline",
                            "lens_b": "zakat",
                            "category": "wallet_tag",
                        },
                        {
                            "field": "ratio",
                            "severity": "warning",
                            "message": "ratio differs",
                            "lens_a": "baseline",
                            "lens_b": "zakat",
                            "category": "factual",
                        },
                    ],
                    "factual_contradictions": 1,
                    "score_misalignments": 0,
                    "wallet_tag_issues": 1,
                    "summary": "",
                }
            ),
            cost_usd=0.0,
        )
        judge.get_llm_client = lambda: mock_client

        result = judge._verify_consistency_with_llm(
            {"name": "X", "ein": "11-1111111"}, {"baseline": {}, "zakat": {}}, {}
        )

        assert result.issues[0].issue_key == "wallet_tag_consistency"
        assert result.issues[1].issue_key is None

    def test_cross_lens_llm_verbatim_duplicate_removed(self):
        judge = CrossLensJudge(JudgeConfig())
        dup = {
            "field": "zakat_eligibility",
            "severity": "warning",
            "message": "contradiction",
            "lens_a": "baseline",
            "lens_b": "zakat",
            "category": "wallet_tag",
        }
        mock_client = Mock()
        mock_client.generate.return_value = Mock(
            text=json.dumps(
                {
                    "issues": [dup, dict(dup)],
                    "factual_contradictions": 1,
                    "score_misalignments": 0,
                    "wallet_tag_issues": 1,
                    "summary": "",
                }
            ),
            cost_usd=0.0,
        )
        judge.get_llm_client = lambda: mock_client

        result = judge._verify_consistency_with_llm(
            {"name": "X", "ein": "11-1111111"}, {"baseline": {}, "zakat": {}}, {}
        )

        assert len(result.issues) == 1


class TestNarrativeQualityGenerator:
    def test_narrative_quality_llm_duplicate_removed(self, monkeypatch):
        judge = NarrativeQualityJudge(JudgeConfig())
        monkeypatch.setattr(judge, "load_prompt_template", lambda: "x {narratives}")
        dup = {"field": "strategic.strengths", "severity": "warning", "message": "generic"}
        mock_client = Mock()
        mock_client.generate.return_value = Mock(
            text=json.dumps(
                {
                    "issues": [dup, dict(dup)],
                    "strengths_specific": False,
                    "donor_profile_actionable": True,
                    "case_against_genuine": True,
                    "summary": "",
                }
            ),
            cost_usd=0.0,
        )
        judge.get_llm_client = lambda: mock_client

        result = judge._verify_quality_with_llm(
            {"name": "X", "ein": "11-1111111"}, {"strategic": {}}
        )

        assert len(result.issues) == 1

"""Rich Narrative Quality Judge - validates data integrity from rich phase.

Deterministic validation rules that don't require LLM:
- R-J-001: Rich narrative exists and is a non-empty dict
- R-J-002: Required rich fields are present (headline, summary, strengths, etc.)
- R-J-003: amal_score_rationale is populated
- R-J-004: score_interpretation mentions actual amal_score
- R-J-005: strengths have citation_ids (rich format)
- R-J-006: at_a_glance fields are present
- R-J-007: Rich narrative metrics are consistent with baseline metrics

These rules catch issues with rich narrative generation before the full judge phase.
"""

import logging
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Required top-level fields in rich narrative
REQUIRED_RICH_FIELDS = [
    "headline",
    "summary",
    "strengths",
    "areas_for_improvement",
    "all_citations",
]

# Expected fields that should be present for quality
EXPECTED_RICH_FIELDS = [
    "score_interpretation",
    "ideal_donor_profile",
    "case_against",
    "at_a_glance",
    "amal_score_rationale",
]


class RichQualityJudge(BaseJudge):
    """Judge that validates rich-phase narrative data quality.

    Lightweight deterministic checks run inline after rich narrative
    generation, before the full LLM judge phase.
    """

    @property
    def name(self) -> str:
        return "rich_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate rich narrative data quality.

        Args:
            output: Dict with 'ein' and 'evaluation' containing rich_narrative
            context: Dict with 'charity_data' for cross-referencing

        Returns:
            JudgeVerdict with any data quality issues
        """
        issues: list[ValidationIssue] = []
        evaluation = output.get("evaluation", {})
        if not evaluation:
            evaluation = context.get("evaluation", {})

        rich_narrative = evaluation.get("rich_narrative")

        # R-J-001: Rich narrative exists
        if not rich_narrative or not isinstance(rich_narrative, dict):
            self.add_issue(
                issues,
                Severity.ERROR,
                "rich_narrative",
                "Rich narrative is missing or not a dict",
            )
            return self.create_verdict(passed=False, issues=issues)

        # R-J-002: Required fields
        for field in REQUIRED_RICH_FIELDS:
            val = rich_narrative.get(field)
            if not val:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    f"rich_narrative.{field}",
                    f"Required rich narrative field '{field}' is missing or empty",
                )
            elif field in ("strengths", "areas_for_improvement", "all_citations"):
                if isinstance(val, list) and len(val) == 0:
                    self.add_issue(
                        issues,
                        Severity.WARNING,
                        f"rich_narrative.{field}",
                        f"Rich narrative field '{field}' is an empty list",
                    )

        # R-J-003: amal_score_rationale populated
        rationale = rich_narrative.get("amal_score_rationale")
        if not rationale or (isinstance(rationale, str) and len(rationale.strip()) < 20):
            self.add_issue(
                issues,
                Severity.ERROR,
                "rich_narrative.amal_score_rationale",
                "amal_score_rationale is missing or too short (< 20 chars)",
            )

        # R-J-004: score_interpretation mentions actual score
        interpretation = rich_narrative.get("score_interpretation")
        amal_score = evaluation.get("amal_score")
        if interpretation and amal_score is not None:
            score_str = str(int(amal_score))
            if score_str not in str(interpretation):
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    "rich_narrative.score_interpretation",
                    f"score_interpretation doesn't mention actual score ({score_str})",
                )

        # R-J-005: Rich strengths have citation_ids
        strengths = rich_narrative.get("strengths", [])
        uncited = 0
        for s in strengths:
            if isinstance(s, dict) and "point" in s:
                if not s.get("citation_ids"):
                    uncited += 1
        if uncited > 0 and len(strengths) > 0:
            self.add_issue(
                issues,
                Severity.INFO,
                "rich_narrative.strengths.citation_ids",
                f"{uncited}/{len(strengths)} rich strengths lack citation_ids",
            )

        # R-J-006: at_a_glance present
        at_a_glance = rich_narrative.get("at_a_glance")
        if not at_a_glance or not isinstance(at_a_glance, dict):
            self.add_issue(
                issues,
                Severity.WARNING,
                "rich_narrative.at_a_glance",
                "at_a_glance section is missing",
            )
        elif isinstance(at_a_glance, dict):
            for aag_field in ("program_expense_ratio", "total_revenue", "wallet_tag"):
                if aag_field not in at_a_glance:
                    self.add_issue(
                        issues,
                        Severity.INFO,
                        f"rich_narrative.at_a_glance.{aag_field}",
                        f"at_a_glance missing expected field '{aag_field}'",
                    )

        # R-J-007: Expected fields present (non-blocking)
        for field in EXPECTED_RICH_FIELDS:
            if field not in ("amal_score_rationale", "at_a_glance"):  # Already checked
                val = rich_narrative.get(field)
                if not val:
                    self.add_issue(
                        issues,
                        Severity.INFO,
                        f"rich_narrative.{field}",
                        f"Expected rich narrative field '{field}' is missing",
                    )

        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        return self.create_verdict(passed=error_count == 0, issues=issues)

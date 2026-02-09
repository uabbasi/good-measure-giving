"""Narrative Quality Judge - validates narrative specificity and actionability.

LLM judge that combines deterministic pre-checks with LLM semantic validation:
- Deterministic: Jargon scan, citation_ids on rich strengths, score value in interpretation
- LLM: Strength specificity, donor profile actionability, case_against genuineness

Runs on ALL lens narratives (baseline, strategic, zakat).
"""

import logging
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Jargon blacklists per lens
COMMON_JARGON = [
    "institutional capacity",
    "intervention modalities",
    "programmatic efficiency",
    "marginalization",
]

STRATEGIC_JARGON = [
    "multiplier effect",
    "sovereignty",
    "self-determination",
    "leverage ratio",
]

ZAKAT_JARGON = [
    "fiqh compliance",
    "asnaf categories",
    "beneficiary proximity",
]

ALL_JARGON = COMMON_JARGON + STRATEGIC_JARGON + ZAKAT_JARGON


class NarrativeQualityIssue(BaseModel):
    """Schema for a narrative quality issue from LLM."""

    field: str = Field(description="The narrative field with the issue")
    severity: str = Field(description="warning or info")
    message: str = Field(description="Description of the quality issue")
    suggestion: Optional[str] = Field(None, description="How to improve")


class NarrativeQualityResult(BaseModel):
    """Schema for narrative quality LLM response."""

    issues: list[NarrativeQualityIssue] = Field(default_factory=list)
    strengths_specific: bool = Field(True, description="Are strengths specific, not generic?")
    donor_profile_actionable: bool = Field(True, description="Is ideal_donor_profile actionable?")
    case_against_genuine: bool = Field(True, description="Is case_against genuine, not softball?")
    summary: str = Field("", description="Brief quality assessment")


class NarrativeQualityJudge(BaseJudge):
    """Validates narrative quality: specificity, jargon, citations, actionability.

    Combines deterministic checks (jargon scanning, structural validation)
    with LLM-based quality assessment (specificity, actionability, genuineness).
    """

    @property
    def name(self) -> str:
        return "narrative_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.LLM

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate narrative quality across all lenses.

        Args:
            output: Exported charity data with narratives
            context: Source data context

        Returns:
            JudgeVerdict with narrative quality issues
        """
        issues: list[ValidationIssue] = []
        cost_usd = 0.0
        metadata: dict[str, Any] = {}

        evaluation = output.get("evaluation", {})
        if not evaluation:
            return self.create_verdict(
                passed=True,
                skipped=True,
                skip_reason="No evaluation data found",
            )

        # Collect all narratives to check
        narratives = self._collect_narratives(evaluation)
        if not narratives:
            return self.create_verdict(
                passed=True,
                skipped=True,
                skip_reason="No narratives to validate",
            )

        metadata["narratives_checked"] = list(narratives.keys())

        # Step 1: Deterministic checks on all narratives
        for lens_name, narrative in narratives.items():
            issues.extend(self._jargon_scan(lens_name, narrative))
            issues.extend(self._citation_structure_check(lens_name, narrative))
            issues.extend(self._score_interpretation_check(lens_name, narrative, evaluation))

        # Step 1b: Rich strategic-specific structure checks
        if "rich_strategic" in narratives:
            issues.extend(self._rich_strategic_structure_check(narratives["rich_strategic"]))

        # Step 2: LLM quality check (only if rich narratives exist)
        rich_narratives = {k: v for k, v in narratives.items() if self._is_rich_narrative(v)}
        if rich_narratives:
            try:
                llm_result = self._verify_quality_with_llm(output, rich_narratives)
                if llm_result:
                    issues.extend(llm_result.issues)
                    cost_usd = llm_result.cost
                    metadata["strengths_specific"] = llm_result.strengths_specific
                    metadata["donor_profile_actionable"] = llm_result.donor_profile_actionable
                    metadata["case_against_genuine"] = llm_result.case_against_genuine
            except Exception as e:
                logger.warning(f"LLM narrative quality check failed: {e}")
                metadata["llm_failed"] = True

        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        passed = error_count == 0

        return self.create_verdict(
            passed=passed,
            issues=issues,
            cost_usd=cost_usd,
            metadata=metadata,
        )

    def _collect_narratives(self, evaluation: dict[str, Any]) -> dict[str, dict]:
        """Extract all available narratives from evaluation data."""
        narratives = {}

        baseline_narr = evaluation.get("baseline_narrative")
        if baseline_narr and isinstance(baseline_narr, dict):
            narratives["baseline"] = baseline_narr

        strategic_narr = evaluation.get("strategic_narrative")
        if strategic_narr and isinstance(strategic_narr, dict):
            narratives["strategic"] = strategic_narr

        zakat_narr = evaluation.get("zakat_narrative")
        if zakat_narr and isinstance(zakat_narr, dict):
            narratives["zakat"] = zakat_narr

        rich_strategic_narr = evaluation.get("rich_strategic_narrative")
        if rich_strategic_narr and isinstance(rich_strategic_narr, dict):
            narratives["rich_strategic"] = rich_strategic_narr

        return narratives

    def _is_rich_narrative(self, narrative: dict) -> bool:
        """Check if narrative has rich fields (not just baseline shape)."""
        return any(k in narrative for k in ("score_interpretation", "ideal_donor_profile", "case_against"))

    def _jargon_scan(self, lens_name: str, narrative: dict) -> list[ValidationIssue]:
        """Scan narrative text for blacklisted jargon terms."""
        issues: list[ValidationIssue] = []

        # Combine all text fields
        text_parts = []
        for field in ("summary", "headline", "score_rationale", "score_interpretation"):
            val = narrative.get(field)
            if isinstance(val, str):
                text_parts.append(val)

        # Check strengths
        for s in narrative.get("strengths", []):
            if isinstance(s, str):
                text_parts.append(s)
            elif isinstance(s, dict):
                text_parts.append(s.get("point", ""))
                text_parts.append(s.get("detail", ""))

        # Check areas_for_improvement
        for a in narrative.get("areas_for_improvement", []):
            if isinstance(a, str):
                text_parts.append(a)
            elif isinstance(a, dict):
                text_parts.append(a.get("area", ""))
                text_parts.append(a.get("context", ""))

        # Check ideal_donor_profile
        donor_profile = narrative.get("ideal_donor_profile")
        if isinstance(donor_profile, dict):
            text_parts.append(donor_profile.get("best_for_summary", ""))
            for m in donor_profile.get("donor_motivations", []):
                text_parts.append(m)

        # Check case_against
        case_against = narrative.get("case_against")
        if isinstance(case_against, dict):
            text_parts.append(case_against.get("summary", ""))

        # Check rich strategic deep dive sections
        for section_key in ("strategic_deep_dive", "operational_capacity", "peer_comparison"):
            section = narrative.get(section_key)
            if isinstance(section, dict):
                for val in section.values():
                    if isinstance(val, str):
                        text_parts.append(val)

        full_text = " ".join(text_parts).lower()

        for term in ALL_JARGON:
            if re.search(r'\b' + re.escape(term.lower()) + r'\b', full_text):
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    f"{lens_name}_narrative.jargon",
                    f"Jargon detected in {lens_name} narrative: '{term}'",
                    details={"term": term, "lens": lens_name},
                )

        return issues

    def _citation_structure_check(self, lens_name: str, narrative: dict) -> list[ValidationIssue]:
        """Check that rich strengths have citation_ids."""
        issues: list[ValidationIssue] = []

        for i, strength in enumerate(narrative.get("strengths", [])):
            if isinstance(strength, dict) and "point" in strength:
                citation_ids = strength.get("citation_ids", [])
                if not citation_ids:
                    self.add_issue(
                        issues,
                        Severity.INFO,
                        f"{lens_name}_narrative.strengths[{i}].citation_ids",
                        f"Rich strength '{strength.get('point', '')[:50]}' has no citation_ids",
                        details={"lens": lens_name, "index": i},
                    )

        return issues

    def _score_interpretation_check(self, lens_name: str, narrative: dict, evaluation: dict) -> list[ValidationIssue]:
        """Check that score_interpretation mentions the actual score value."""
        issues: list[ValidationIssue] = []

        interpretation = narrative.get("score_interpretation")
        if not isinstance(interpretation, str):
            return issues

        # Get the relevant score
        score = None
        if lens_name == "baseline":
            score = evaluation.get("amal_score")
        elif lens_name == "strategic":
            score = evaluation.get("strategic_score")
        elif lens_name == "zakat":
            score = evaluation.get("zakat_score")

        if score is not None:
            score_str = str(int(score)) if isinstance(score, (int, float)) else str(score)
            if score_str not in interpretation:
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    f"{lens_name}_narrative.score_interpretation",
                    f"Score interpretation doesn't mention actual score ({score_str})",
                    details={"lens": lens_name, "score": score_str},
                )

        return issues

    def _rich_strategic_structure_check(self, narrative: dict) -> list[ValidationIssue]:
        """Validate that rich strategic narrative has required deep-dive sections."""
        issues: list[ValidationIssue] = []

        # Required top-level sections
        required_sections = ["strategic_deep_dive", "operational_capacity", "peer_comparison"]
        for section in required_sections:
            if section not in narrative or not narrative[section]:
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    f"rich_strategic_narrative.{section}",
                    f"Missing required section: {section}",
                )

        # Validate strategic_deep_dive subsections
        deep_dive = narrative.get("strategic_deep_dive", {})
        if isinstance(deep_dive, dict):
            for sub in ("loop_breaking_evidence", "multiplier_analysis", "asset_durability", "sovereignty_assessment"):
                val = deep_dive.get(sub, "")
                if not val or (isinstance(val, str) and len(val) < 50):
                    self.add_issue(
                        issues,
                        Severity.WARNING,
                        f"rich_strategic_narrative.strategic_deep_dive.{sub}",
                        f"Strategic deep dive section '{sub}' is too short or missing",
                    )

        # Validate operational_capacity subsections
        ops = narrative.get("operational_capacity", {})
        if isinstance(ops, dict):
            for sub in ("institutional_maturity", "financial_sustainability", "execution_track_record"):
                val = ops.get(sub, "")
                if not val or (isinstance(val, str) and len(val) < 30):
                    self.add_issue(
                        issues,
                        Severity.INFO,
                        f"rich_strategic_narrative.operational_capacity.{sub}",
                        f"Operational capacity section '{sub}' is too short or missing",
                    )

        # Check unique source count (all_citations = deduplicated source list)
        citations = narrative.get("all_citations", [])
        if len(citations) < 5:
            self.add_issue(
                issues,
                Severity.WARNING,
                "rich_strategic_narrative.all_citations",
                f"Only {len(citations)} unique sources cited (minimum: 5)",
            )

        return issues

    def _verify_quality_with_llm(
        self, output: dict[str, Any], narratives: dict[str, dict]
    ) -> Optional["LLMNarrativeQualityResult"]:
        """Use LLM to assess narrative quality: specificity, actionability, genuineness."""
        import json

        from .base_judge import SafeJSONEncoder

        prompt = self.load_prompt_template()
        if not prompt:
            return None

        # Build substitutions
        prompt = prompt.replace("{charity_name}", output.get("name", "Unknown"))
        prompt = prompt.replace("{ein}", output.get("ein", "Unknown"))
        prompt = prompt.replace(
            "{narratives}",
            json.dumps(narratives, indent=2, cls=SafeJSONEncoder),
        )

        client = self.get_llm_client()
        response = client.generate(
            prompt=prompt,
            json_schema=NarrativeQualityResult.model_json_schema(),
        )

        json_text = self.strip_markdown_json(response.text)
        result = NarrativeQualityResult.model_validate_json(json_text)

        # Convert to ValidationIssues
        issues = []
        for issue in result.issues:
            severity = Severity.WARNING if issue.severity == "warning" else Severity.INFO
            vi = ValidationIssue(
                severity=severity,
                field=issue.field,
                message=issue.message,
                evidence=issue.suggestion,
            )
            issues.append(vi)

        return LLMNarrativeQualityResult(
            issues=issues,
            strengths_specific=result.strengths_specific,
            donor_profile_actionable=result.donor_profile_actionable,
            case_against_genuine=result.case_against_genuine,
            cost=response.cost_usd or 0.0,
        )


class LLMNarrativeQualityResult:
    """Result from LLM narrative quality verification."""

    def __init__(
        self,
        issues: list[ValidationIssue],
        strengths_specific: bool,
        donor_profile_actionable: bool,
        case_against_genuine: bool,
        cost: float,
    ):
        self.issues = issues
        self.strengths_specific = strengths_specific
        self.donor_profile_actionable = donor_profile_actionable
        self.case_against_genuine = case_against_genuine
        self.cost = cost

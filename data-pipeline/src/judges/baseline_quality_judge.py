"""Baseline Quality Judge - validates data integrity from baseline phase.

Deterministic validation rules that don't require LLM:
- B-J-001: Score bounds - amal_score must be in [0, 100]
- B-J-002: Dimension consistency - dimension scores + risk = amal_score
- B-J-003: Wallet tag consistency - ZAKAT-ELIGIBLE requires zakat_claim_detected=True
- B-J-004: Citation validity - all_citations must have valid id and source_name
- B-J-005: Narrative structure - baseline_narrative has required fields
- B-J-006: Strategic score bounds - strategic_score must be in [0, 100]
- B-J-007: Zakat score bounds - zakat_score must be in [0, 100]
- B-J-008: Strategic dimension consistency - dimensions sum to strategic_score
- B-J-009: Zakat dimension consistency - dimensions sum to zakat_score
- B-J-010: Strategic narrative structure - required/expected fields
- B-J-011: Strategic narrative consistency - cross-lens agreement

These rules catch issues with scored/generated data before export.
"""

import logging
import re
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Required fields in baseline_narrative
REQUIRED_NARRATIVE_FIELDS = [
    "headline",
    "summary",
    "all_citations",
]


class BaselineQualityJudge(BaseJudge):
    """Judge that validates baseline-phase data quality.

    Unlike LLM-based judges, this judge runs deterministic checks
    on the evaluation data to catch scoring and narrative issues.
    """

    @property
    def name(self) -> str:
        return "baseline_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate baseline-phase data quality.

        Args:
            output: The exported charity data (includes evaluation)
            context: Source data context

        Returns:
            JudgeVerdict with any data quality issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")

        # Get evaluation data from output
        evaluation = output.get("evaluation", {})
        if not evaluation:
            # Try alternate locations
            evaluation = context.get("evaluation", {})

        if not evaluation:
            return JudgeVerdict(
                judge_name=self.name,
                passed=True,
                issues=[],
                skipped=True,
                skip_reason="No evaluation data found",
            )

        # B-J-001: Score bounds validation
        issues.extend(self._check_score_bounds(ein, evaluation))

        # B-J-002: Dimension consistency
        issues.extend(self._check_dimension_consistency(ein, evaluation))

        # B-J-003: Wallet tag consistency
        issues.extend(self._check_wallet_tag_consistency(ein, evaluation, context))

        # B-J-004: Citation validity
        issues.extend(self._check_citation_validity(ein, evaluation))

        # B-J-005: Narrative structure
        issues.extend(self._check_narrative_structure(ein, evaluation))

        # B-J-006/007: Multi-lens score bounds
        issues.extend(self._check_multi_lens_score_bounds(ein, evaluation))

        # B-J-008/009: Multi-lens dimension consistency
        issues.extend(self._check_multi_lens_dimension_consistency(ein, evaluation))

        # B-J-010: Strategic narrative structure
        issues.extend(self._check_strategic_narrative_structure(ein, output))

        # B-J-011: Strategic narrative consistency
        issues.extend(self._check_strategic_narrative_consistency(ein, output))

        # Determine pass/fail - ERROR severity fails
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return JudgeVerdict(
            judge_name=self.name,
            passed=not has_errors,
            issues=issues,
        )

    def _check_score_bounds(self, ein: str, evaluation: dict) -> list[ValidationIssue]:
        """B-J-001: Verify amal_score is within valid bounds [0, 100]."""
        issues = []

        amal_score = evaluation.get("amal_score")
        if amal_score is not None:
            if not isinstance(amal_score, (int, float)):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="amal_score",
                        message=f"amal_score must be numeric, got {type(amal_score).__name__}",
                        details={"value": str(amal_score), "rule": "B-J-001"},
                    )
                )
            elif amal_score < 0 or amal_score > 100:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="amal_score",
                        message=f"amal_score={amal_score} outside valid range [0, 100]",
                        details={
                            "value": amal_score,
                            "valid_range": [0, 100],
                            "rule": "B-J-001",
                        },
                    )
                )

        return issues

    def _check_dimension_consistency(self, ein: str, evaluation: dict) -> list[ValidationIssue]:
        """B-J-002: Verify dimension scores sum to amal_score (with risk deduction)."""
        issues = []

        amal_score = evaluation.get("amal_score")
        score_details = evaluation.get("score_details", {})

        if amal_score is None or not score_details:
            return issues

        # Extract dimension scores (2-dimension GMG framework)
        impact_score = score_details.get("impact", {}).get("score")
        alignment_score = score_details.get("alignment", {}).get("score")
        risk_deduction = score_details.get("risk_deduction", 0)

        # Both dimensions must be present
        if any(s is None for s in [impact_score, alignment_score]):
            missing = []
            if impact_score is None:
                missing.append("impact")
            if alignment_score is None:
                missing.append("alignment")

            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="score_details",
                    message=f"Missing dimension scores: {', '.join(missing)}",
                    details={"missing_dimensions": missing, "rule": "B-J-002"},
                )
            )
            return issues

        # B-J-002b: Validate risk_deduction bounds [-10, 0]
        if risk_deduction is not None and (risk_deduction < -10 or risk_deduction > 0):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="risk_deduction",
                    message=f"risk_deduction={risk_deduction} outside valid range [-10, 0]",
                    details={
                        "value": risk_deduction,
                        "valid_range": [-10, 0],
                        "rule": "B-J-002b",
                    },
                )
            )

        # Calculate expected total (2-dimension: impact + alignment + risk)
        expected_score = impact_score + alignment_score + risk_deduction
        # Clamp to [0, 100] as the scorer does
        expected_score = max(0, min(100, expected_score))

        # Allow small tolerance for floating point
        if abs(amal_score - expected_score) > 0.01:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="amal_score",
                    message=f"amal_score={amal_score} doesn't match dimension sum={expected_score}",
                    details={
                        "amal_score": amal_score,
                        "impact": impact_score,
                        "alignment": alignment_score,
                        "risk_deduction": risk_deduction,
                        "expected_total": expected_score,
                        "rule": "B-J-002",
                    },
                )
            )

        return issues

    def _check_wallet_tag_consistency(self, ein: str, evaluation: dict, context: dict) -> list[ValidationIssue]:
        """B-J-003: Verify ZAKAT-ELIGIBLE only appears when zakat_claim_detected=True."""
        issues = []

        wallet_tag = evaluation.get("wallet_tag")
        score_details = evaluation.get("score_details", {})
        zakat_data = score_details.get("zakat", {})

        # Get zakat claim status
        charity_claims_zakat = zakat_data.get("charity_claims_zakat", False)

        # Also check context for charity_data
        charity_data = context.get("charity_data", {})
        claims_zakat_from_context = charity_data.get("claims_zakat_eligible", False)

        # Either source can indicate zakat claim
        has_zakat_claim = charity_claims_zakat or claims_zakat_from_context

        if wallet_tag == "ZAKAT-ELIGIBLE" and not has_zakat_claim:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="wallet_tag",
                    message="ZAKAT-ELIGIBLE wallet tag without zakat claim detected",
                    details={
                        "wallet_tag": wallet_tag,
                        "charity_claims_zakat": charity_claims_zakat,
                        "claims_zakat_from_context": claims_zakat_from_context,
                        "rule": "B-J-003",
                    },
                )
            )

        if wallet_tag == "SADAQAH-ELIGIBLE" and has_zakat_claim:
            # This is a warning - charity claims zakat but tagged as sadaqah
            # Could be intentional if claim failed corroboration
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="wallet_tag",
                    message="Charity claims zakat eligibility but tagged as SADAQAH-ELIGIBLE",
                    details={
                        "wallet_tag": wallet_tag,
                        "charity_claims_zakat": charity_claims_zakat,
                        "rule": "B-J-003",
                    },
                )
            )

        return issues

    def _check_citation_validity(self, ein: str, evaluation: dict) -> list[ValidationIssue]:
        """B-J-004: Verify all_citations have valid id format and source_name."""
        issues = []

        narrative = evaluation.get("baseline_narrative", {})
        if not narrative:
            return issues

        all_citations = narrative.get("all_citations", [])

        if not isinstance(all_citations, list):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="all_citations",
                    message=f"all_citations must be a list, got {type(all_citations).__name__}",
                    details={"rule": "B-J-004"},
                )
            )
            return issues

        # Check each citation
        citation_ids_seen = set()
        for i, citation in enumerate(all_citations):
            if not isinstance(citation, dict):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"all_citations[{i}]",
                        message=f"Citation must be a dict, got {type(citation).__name__}",
                        details={"rule": "B-J-004"},
                    )
                )
                continue

            # Check id format [N]
            cid = citation.get("id", "")
            if not cid:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"all_citations[{i}].id",
                        message="Citation missing id field",
                        details={"citation": citation, "rule": "B-J-004"},
                    )
                )
            elif not re.match(r"^\[\d+\]$", cid):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"all_citations[{i}].id",
                        message=f"Citation id '{cid}' doesn't match format [N]",
                        details={"citation_id": cid, "rule": "B-J-004"},
                    )
                )
            else:
                # Check for duplicate IDs
                if cid in citation_ids_seen:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field=f"all_citations[{i}].id",
                            message=f"Duplicate citation id: {cid}",
                            details={"citation_id": cid, "rule": "B-J-004"},
                        )
                    )
                citation_ids_seen.add(cid)

            # Check source_name
            source_name = citation.get("source_name", "")
            if not source_name or not source_name.strip():
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"all_citations[{i}].source_name",
                        message="Citation missing or empty source_name",
                        details={"citation": citation, "rule": "B-J-004"},
                    )
                )

        return issues

    def _check_narrative_structure(self, ein: str, evaluation: dict) -> list[ValidationIssue]:
        """B-J-005: Verify baseline_narrative has required fields."""
        issues = []

        narrative = evaluation.get("baseline_narrative")

        if narrative is None:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="baseline_narrative",
                    message="Missing baseline_narrative field",
                    details={"rule": "B-J-005"},
                )
            )
            return issues

        if not isinstance(narrative, dict):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="baseline_narrative",
                    message=f"baseline_narrative must be a dict, got {type(narrative).__name__}",
                    details={"rule": "B-J-005"},
                )
            )
            return issues

        # Check required fields
        for field in REQUIRED_NARRATIVE_FIELDS:
            value = narrative.get(field)
            if value is None:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"baseline_narrative.{field}",
                        message=f"Missing required field: {field}",
                        details={"rule": "B-J-005"},
                    )
                )
            elif isinstance(value, str) and not value.strip():
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"baseline_narrative.{field}",
                        message=f"Required field '{field}' is empty",
                        details={"rule": "B-J-005"},
                    )
                )

        return issues

    def _check_multi_lens_score_bounds(
        self,
        ein: str,
        evaluation: dict,  # noqa: ARG002
    ) -> list[ValidationIssue]:
        """B-J-006/007: Verify strategic_score and zakat_score are within [0, 100]."""
        issues = []

        for field, rule in [("strategic_score", "B-J-006"), ("zakat_score", "B-J-007")]:
            score = evaluation.get(field)
            if score is None:
                continue  # Optional — not all charities have these yet

            if not isinstance(score, (int, float)):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=field,
                        message=f"{field} must be numeric, got {type(score).__name__}",
                        details={"value": str(score), "rule": rule},
                    )
                )
            elif score < 0 or score > 100:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=field,
                        message=f"{field}={score} outside valid range [0, 100]",
                        details={"value": score, "valid_range": [0, 100], "rule": rule},
                    )
                )

        return issues

    def _check_multi_lens_dimension_consistency(
        self,
        ein: str,
        evaluation: dict,  # noqa: ARG002
    ) -> list[ValidationIssue]:
        """B-J-008/009: Verify multi-lens dimension scores sum to total."""
        issues = []

        score_profiles = evaluation.get("score_profiles")
        if not score_profiles or not isinstance(score_profiles, dict):
            return issues

        # B-J-008: Strategic Believer dimensions
        strategic = score_profiles.get("strategic", {})
        strategic_total = evaluation.get("strategic_score")
        if strategic and strategic_total is not None:
            dims = ["resilience", "leverage", "future_proofing", "competence"]
            dim_scores = {}
            for d in dims:
                dim_data = strategic.get(d, {})
                if isinstance(dim_data, dict):
                    dim_scores[d] = dim_data.get("score", 0)
                else:
                    dim_scores[d] = 0

            expected = min(100, sum(dim_scores.values()))
            if abs(strategic_total - expected) > 0.01:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="strategic_score",
                        message=f"strategic_score={strategic_total} doesn't match dimension sum={expected}",
                        details={
                            "strategic_score": strategic_total,
                            "dimensions": dim_scores,
                            "expected_total": expected,
                            "rule": "B-J-008",
                        },
                    )
                )

        # B-J-009: Traditional Zakat dimensions
        zakat = score_profiles.get("zakat", {})
        zakat_total = evaluation.get("zakat_score")
        if zakat and zakat_total is not None:
            dims = ["fiqh_compliance", "directness", "community_identity", "speed_of_delivery"]
            dim_scores = {}
            for d in dims:
                dim_data = zakat.get(d, {})
                if isinstance(dim_data, dict):
                    dim_scores[d] = dim_data.get("score", 0)
                else:
                    dim_scores[d] = 0

            expected = min(100, sum(dim_scores.values()))
            if abs(zakat_total - expected) > 0.01:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="zakat_score",
                        message=f"zakat_score={zakat_total} doesn't match dimension sum={expected}",
                        details={
                            "zakat_score": zakat_total,
                            "dimensions": dim_scores,
                            "expected_total": expected,
                            "rule": "B-J-009",
                        },
                    )
                )

        return issues

    def _check_strategic_narrative_structure(
        self,
        ein: str,
        output: dict,  # noqa: ARG002
    ) -> list[ValidationIssue]:
        """B-J-010: Verify strategic narrative has required and expected fields."""
        issues = []

        strat_narr = output.get("strategic_narrative")
        if not strat_narr:
            return issues  # No strategic narrative — skip (optional lens)

        # Required fields — ERROR if missing
        required = ["headline", "summary", "all_citations"]
        for field in required:
            value = strat_narr.get(field)
            if value is None:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"strategic_narrative.{field}",
                        message=f"Missing required field: {field}",
                        details={"rule": "B-J-010"},
                    )
                )
            elif isinstance(value, str) and not value.strip():
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field=f"strategic_narrative.{field}",
                        message=f"Required field '{field}' is empty",
                        details={"rule": "B-J-010"},
                    )
                )

        # Expected fields — WARNING if missing (enriched narratives should have these)
        expected = ["score_interpretation", "ideal_donor_profile"]
        for field in expected:
            value = strat_narr.get(field)
            if not value:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field=f"strategic_narrative.{field}",
                        message=f"Expected field '{field}' is missing or empty",
                        details={"rule": "B-J-010"},
                    )
                )

        # Rich format check: strengths should be [{point, detail, citation_ids}] not string[]
        strengths = strat_narr.get("strengths", [])
        if strengths and isinstance(strengths, list) and len(strengths) > 0:
            first = strengths[0]
            if isinstance(first, str):
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field="strategic_narrative.strengths",
                        message="strengths are plain strings; expected [{point, detail, citation_ids}] rich format",
                        details={"rule": "B-J-010", "first_item_type": "string"},
                    )
                )

        return issues

    def _check_strategic_narrative_consistency(
        self,
        ein: str,
        output: dict,  # noqa: ARG002
    ) -> list[ValidationIssue]:
        """B-J-011: Verify strategic and baseline narratives are consistent but distinct."""
        issues = []

        strat_narr = output.get("strategic_narrative")
        baseline_narr = output.get("narrative")

        if not strat_narr or not baseline_narr:
            return issues  # Need both to check consistency

        if not strat_narr.get("summary") or not baseline_narr.get("summary"):
            return issues

        # Headline differentiation: different lens = different perspective
        strat_headline = strat_narr.get("headline", "")
        baseline_headline = baseline_narr.get("headline", "")
        if strat_headline and baseline_headline and strat_headline.strip().lower() == baseline_headline.strip().lower():
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="strategic_narrative.headline",
                    message="Strategic headline is identical to baseline headline; "
                    "different lenses should offer different perspectives",
                    details={
                        "strategic_headline": strat_headline,
                        "baseline_headline": baseline_headline,
                        "rule": "B-J-011",
                    },
                )
            )

        return issues

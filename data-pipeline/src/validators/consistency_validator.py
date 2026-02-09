"""
Consistency Validator - Validates data quality at export time.

Three validation modes:
1. Rich vs Baseline validation - ensures rich narratives don't contradict baseline facts
2. Export validation - catches data quality issues before shipping
3. Financial sanity checks - validates financial metrics are mathematically sound

Export validations include:
- Impossible math checks (ratios > 1, expenses > total, etc.)
- Required field checks (zakat claims require evidence)
- Cross-system consistency (baseline vs rich narrative alignment)
- Financial sanity (revenue/expense relationships)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationViolation:
    """A specific consistency violation."""

    field: str
    baseline_value: Any
    rich_value: Any
    severity: str  # "error" or "warning"
    message: str


@dataclass
class ValidationResult:
    """Result of consistency validation."""

    is_valid: bool
    violations: list[ValidationViolation] = field(default_factory=list)
    warnings: list[ValidationViolation] = field(default_factory=list)

    def add_error(self, field: str, baseline_value: Any, rich_value: Any, message: str) -> None:
        """Add an error violation (blocks approval)."""
        self.violations.append(
            ValidationViolation(
                field=field,
                baseline_value=baseline_value,
                rich_value=rich_value,
                severity="error",
                message=message,
            )
        )
        self.is_valid = False

    def add_warning(self, field: str, baseline_value: Any, rich_value: Any, message: str) -> None:
        """Add a warning (doesn't block approval)."""
        self.warnings.append(
            ValidationViolation(
                field=field,
                baseline_value=baseline_value,
                rich_value=rich_value,
                severity="warning",
                message=message,
            )
        )


class ConsistencyValidator:
    """Validates rich narrative consistency with baseline."""

    def validate(self, rich: dict, baseline: dict) -> ValidationResult:
        """
        Validate that rich narrative is consistent with baseline.

        Args:
            rich: Rich narrative dict (or RichNarrativeV2.model_dump())
            baseline: Baseline narrative dict (or BaselineNarrative.model_dump())

        Returns:
            ValidationResult with any violations or warnings
        """
        result = ValidationResult(is_valid=True)

        # 1. AMAL scores must be identical
        self._validate_amal_scores(rich, baseline, result)

        # 2. Wallet tag must match
        self._validate_wallet_tag(rich, baseline, result)

        # 3. Annual revenue must match
        self._validate_revenue(rich, baseline, result)

        # 4. Baseline strengths should be subset of rich strengths
        self._validate_strengths(rich, baseline, result)

        # 5. Headline should be identical (immutable)
        self._validate_headline(rich, baseline, result)

        logger.info(
            f"Validation result: valid={result.is_valid}, "
            f"errors={len(result.violations)}, warnings={len(result.warnings)}"
        )
        return result

    def _validate_amal_scores(self, rich: dict, baseline: dict, result: ValidationResult) -> None:
        """Validate AMAL scores are identical.

        Note: Scores may be injected from evaluation-level data after generation,
        so we only validate if baseline has scores to compare against.
        """
        rich_scores = rich.get("amal_scores", {})
        baseline_scores = baseline.get("amal_scores", {})

        # Check overall score (skip if baseline doesn't have it - scores may come from evaluation level)
        rich_total = rich_scores.get("amal_score")
        baseline_total = baseline_scores.get("amal_score")

        if baseline_total is not None and rich_total != baseline_total:
            result.add_error(
                field="amal_scores.amal_score",
                baseline_value=baseline_total,
                rich_value=rich_total,
                message=f"AMAL score mismatch: baseline={baseline_total}, rich={rich_total}",
            )

        # Check wallet tag in scores
        rich_wallet = rich_scores.get("wallet_tag")
        baseline_wallet = baseline_scores.get("wallet_tag")

        if rich_wallet and baseline_wallet and rich_wallet != baseline_wallet:
            result.add_error(
                field="amal_scores.wallet_tag",
                baseline_value=baseline_wallet,
                rich_value=rich_wallet,
                message=f"Wallet tag mismatch in scores: baseline={baseline_wallet}, rich={rich_wallet}",
            )

    def _validate_wallet_tag(self, rich: dict, baseline: dict, result: ValidationResult) -> None:
        """Validate zakat guidance wallet tag matches."""
        rich_guidance = rich.get("zakat_guidance", {})
        baseline_guidance = baseline.get("zakat_guidance", {})

        rich_eligibility = rich_guidance.get("eligibility")
        baseline_eligibility = baseline_guidance.get("eligibility")

        if rich_eligibility and baseline_eligibility and rich_eligibility != baseline_eligibility:
            result.add_error(
                field="zakat_guidance.eligibility",
                baseline_value=baseline_eligibility,
                rich_value=rich_eligibility,
                message=f"Zakat eligibility mismatch: baseline={baseline_eligibility}, rich={rich_eligibility}",
            )

    def _validate_revenue(self, rich: dict, baseline: dict, result: ValidationResult) -> None:
        """Validate annual revenue is consistent."""
        rich_glance = rich.get("at_a_glance", {})
        baseline_glance = baseline.get("at_a_glance", {})

        rich_revenue = rich_glance.get("annual_revenue")
        baseline_revenue = baseline_glance.get("annual_revenue")

        if rich_revenue and baseline_revenue:
            # Normalize for comparison (remove $ and formatting)
            def normalize_revenue(rev: str) -> Optional[float]:
                try:
                    rev_str = str(rev).replace("$", "").replace(",", "").strip()
                    # Handle M/B suffixes
                    if rev_str.upper().endswith("M"):
                        return float(rev_str[:-1]) * 1_000_000
                    elif rev_str.upper().endswith("B"):
                        return float(rev_str[:-1]) * 1_000_000_000
                    return float(rev_str)
                except (ValueError, TypeError) as e:
                    # E-005: Log warning on parse error instead of silently returning None
                    import logging

                    logging.getLogger(__name__).debug(f"Failed to parse revenue '{rev}': {e}")
                    return None

            rich_val = normalize_revenue(rich_revenue)
            baseline_val = normalize_revenue(baseline_revenue)

            if rich_val and baseline_val:
                # Allow 1% tolerance for rounding
                diff_pct = abs(rich_val - baseline_val) / baseline_val if baseline_val else 0
                if diff_pct > 0.01:
                    result.add_error(
                        field="at_a_glance.annual_revenue",
                        baseline_value=baseline_revenue,
                        rich_value=rich_revenue,
                        message=f"Revenue mismatch: baseline={baseline_revenue}, rich={rich_revenue} ({diff_pct * 100:.1f}% diff)",
                    )

    def _validate_strengths(self, rich: dict, baseline: dict, result: ValidationResult) -> None:
        """Validate baseline strengths are covered in rich."""
        rich_strengths = rich.get("strengths", [])
        baseline_strengths = baseline.get("strengths", [])

        def extract_point(s: Any) -> str:
            """Extract point from string or dict."""
            if isinstance(s, str):
                return s.lower().strip()
            elif isinstance(s, dict):
                return s.get("point", "").lower().strip()
            return ""

        # Extract strength points (handle both string and dict formats)
        rich_points = {extract_point(s) for s in rich_strengths if extract_point(s)}
        baseline_points = [extract_point(s) for s in baseline_strengths if extract_point(s)]

        # Check each baseline strength has a reasonable match in rich
        for bp in baseline_points:
            if bp and not any(self._similar_strength(bp, rp) for rp in rich_points):
                result.add_warning(
                    field="strengths",
                    baseline_value=bp,
                    rich_value=None,
                    message=f"Baseline strength '{bp[:50]}...' not clearly covered in rich narrative",
                )

    def _similar_strength(self, baseline: str, rich: str) -> bool:
        """Check if two strength descriptions are similar enough."""
        if not baseline or not rich:
            return False

        # Simple word overlap check
        baseline_words = set(baseline.lower().split())
        rich_words = set(rich.lower().split())

        # Remove common words
        common_words = {"the", "a", "an", "and", "or", "is", "are", "has", "have", "with", "for", "to", "of", "in"}
        baseline_words -= common_words
        rich_words -= common_words

        if not baseline_words:
            return True  # Empty after filtering

        overlap = len(baseline_words & rich_words) / len(baseline_words)
        return overlap >= 0.3  # 30% word overlap is considered similar

    def _validate_headline(self, rich: dict, baseline: dict, result: ValidationResult) -> None:
        """Validate headline is identical (immutable field)."""
        rich_headline = rich.get("headline", "")
        baseline_headline = baseline.get("headline", "")

        if rich_headline and baseline_headline and rich_headline != baseline_headline:
            result.add_warning(
                field="headline",
                baseline_value=baseline_headline,
                rich_value=rich_headline,
                message="Headline differs from baseline (should be immutable)",
            )

    def validate_cn_score_citations(
        self,
        rich: dict,
        source_attribution: Optional[dict],
        result: ValidationResult,
        cn_is_rated: Optional[bool] = None,
    ) -> None:
        """
        Validate that CN score claims in citations match actual collected data.

        This catches the common LLM error of confusing cn_financial_score (beacon)
        with overall_score (aggregate rating).
        """
        import re

        if not source_attribution:
            source_attribution = {}

        # Get actual CN overall score from source attribution.
        # Backward-compatible fallback: older rows may store this under cn_overall_score.
        cn_attr = source_attribution.get("charity_navigator_score", {})
        if not cn_attr:
            cn_attr = source_attribution.get("cn_overall_score", {})
        actual_cn_score = cn_attr.get("value")

        # Get cn_financial_score if present (the beacon score LLM often confuses)
        financial_deep_dive = rich.get("financial_deep_dive", {})
        cn_financial_score = financial_deep_dive.get("cn_financial_score")

        # Check all citations for CN score claims
        citations = rich.get("all_citations", [])
        for citation in citations:
            if not isinstance(citation, dict):
                # Defensive: malformed citation entries should not crash rich generation
                continue
            claim = str(citation.get("claim", "")).lower()
            quote = str(citation.get("quote", "")).lower()

            # Look for CN rating claims
            if "charity navigator" in claim or "charity navigator" in quote:
                # Extract any score mentioned (patterns like "100/100", "92/100", "100 score")
                combined_text = f"{claim} {quote}"
                score_patterns = [
                    r"(\d+(?:\.\d+)?)\s*/\s*100",  # "100/100" or "92/100"
                    r"(\d+(?:\.\d+)?)\s*out of\s*100",  # "100 out of 100"
                    r"score[:\s]+(\d+(?:\.\d+)?)",  # "score: 100" or "score 92"
                    r"rating[:\s]+(\d+(?:\.\d+)?)",  # "rating: 100"
                ]

                for pattern in score_patterns:
                    match = re.search(pattern, combined_text)
                    if match:
                        cited_score = float(match.group(1))

                        # Check if cited score matches actual overall score
                        if actual_cn_score is not None:
                            if abs(cited_score - actual_cn_score) > 1:  # Allow 1 point tolerance
                                # Check if they're confusing with financial score
                                if cn_financial_score and abs(cited_score - cn_financial_score) <= 1:
                                    result.add_error(
                                        field="citations.cn_score",
                                        baseline_value=actual_cn_score,
                                        rich_value=cited_score,
                                        message=(
                                            f"CN score confusion: citation claims {cited_score}/100 "
                                            f"(likely cn_financial_score), but overall_score is {actual_cn_score}. "
                                            f"Do not cite cn_financial_score as the overall CN rating."
                                        ),
                                    )
                                else:
                                    result.add_error(
                                        field="citations.cn_score",
                                        baseline_value=actual_cn_score,
                                        rich_value=cited_score,
                                        message=(
                                            f"CN score mismatch: citation claims {cited_score}/100, "
                                            f"but actual collected score is {actual_cn_score}"
                                        ),
                                    )
                        elif cited_score > 0:
                            if cn_is_rated is False:
                                result.add_error(
                                    field="citations.cn_score",
                                    baseline_value=None,
                                    rich_value=cited_score,
                                    message=(
                                        f"CN score hallucination: citation claims {cited_score}/100, "
                                        "but this charity is not fully CN rated (cn_is_rated=false)"
                                    ),
                                )
                                break
                            # No actual CN score but citation claims one
                            result.add_error(
                                field="citations.cn_score",
                                baseline_value=None,
                                rich_value=cited_score,
                                message=(
                                    f"CN score hallucination: citation claims {cited_score}/100, "
                                    f"but no CN score was collected for this charity"
                                ),
                            )
                        break  # Only check first score match per citation


def validate_rich_vs_baseline(rich: dict, baseline: dict) -> ValidationResult:
    """Convenience function to validate rich narrative against baseline."""
    validator = ConsistencyValidator()
    return validator.validate(rich, baseline)


# =============================================================================
# EXPORT VALIDATION
# =============================================================================


class ExportValidator:
    """Validates data quality before export.

    Performs four categories of checks:
    1. Impossible math - ratios > 1, expenses > totals
    2. Required fields - zakat claims need evidence
    3. Cross-system consistency - baseline/rich alignment
    4. Financial sanity - revenue/expense relationships
    """

    # Tolerance for floating point comparisons
    FLOAT_TOLERANCE = 0.05  # 5% tolerance for expense sum checks
    SCORE_TOLERANCE = 5  # Points tolerance for score comparison (warning only)

    def validate_for_export(
        self,
        data: dict,
        baseline: dict | None = None,
        rich: dict | None = None,
    ) -> ValidationResult:
        """
        Validate charity data for export.

        Args:
            data: The synthesized charity data (CharityData fields)
            baseline: Optional baseline narrative dict
            rich: Optional rich narrative dict

        Returns:
            ValidationResult with errors (block export) and warnings (log only)
        """
        result = ValidationResult(is_valid=True)

        # 1. Impossible math checks (hard failures)
        self._validate_ratio_bounds(data, result)
        self._validate_expense_math(data, result)

        # 2. Required field checks (hard failures)
        if baseline:
            self._validate_required_fields(baseline, result)

        # 3. Cross-system consistency (mixed: some hard, some soft)
        if baseline and rich:
            self._validate_cross_system_consistency(baseline, rich, result)

        # 4. Financial sanity checks (hard failures)
        self._validate_financial_sanity(data, result)

        logger.info(
            f"Export validation: valid={result.is_valid}, "
            f"errors={len(result.violations)}, warnings={len(result.warnings)}"
        )
        return result

    def _validate_ratio_bounds(self, data: dict, result: ValidationResult) -> None:
        """Validate all ratios are between 0 and 1.

        Hard failure: ratios outside 0-1 are mathematically impossible.
        """
        ratio_fields = [
            "program_expense_ratio",
            "admin_ratio",
            "fundraising_ratio",
            "admin_expense_ratio",
            "fundraising_expense_ratio",
        ]

        for field_name in ratio_fields:
            value = data.get(field_name)
            if value is not None:
                if value < 0:
                    result.add_error(
                        field=field_name,
                        baseline_value=None,
                        rich_value=value,
                        message=f"Impossible ratio: {field_name}={value} is negative",
                    )
                elif value > 1.0:
                    result.add_error(
                        field=field_name,
                        baseline_value=None,
                        rich_value=value,
                        message=f"Impossible ratio: {field_name}={value} exceeds 1.0 (100%)",
                    )

    def _validate_expense_math(self, data: dict, result: ValidationResult) -> None:
        """Validate expense relationships are mathematically sound.

        Hard failures:
        - programExpenses > totalExpenses
        - program_expense_ratio > 1.0
        """
        program_expenses = data.get("program_expenses")
        total_expenses = data.get("total_expenses")

        # Check program expenses don't exceed total
        if program_expenses is not None and total_expenses is not None:
            if total_expenses > 0 and program_expenses > total_expenses:
                result.add_error(
                    field="program_expenses",
                    baseline_value=total_expenses,
                    rich_value=program_expenses,
                    message=f"Impossible: program_expenses ({program_expenses:,}) > total_expenses ({total_expenses:,})",
                )

        # Check admin expenses don't exceed total
        admin_expenses = data.get("admin_expenses")
        if admin_expenses is not None and total_expenses is not None:
            if total_expenses > 0 and admin_expenses > total_expenses:
                result.add_error(
                    field="admin_expenses",
                    baseline_value=total_expenses,
                    rich_value=admin_expenses,
                    message=f"Impossible: admin_expenses ({admin_expenses:,}) > total_expenses ({total_expenses:,})",
                )

        # Check fundraising expenses don't exceed total
        fundraising_expenses = data.get("fundraising_expenses")
        if fundraising_expenses is not None and total_expenses is not None:
            if total_expenses > 0 and fundraising_expenses > total_expenses:
                result.add_error(
                    field="fundraising_expenses",
                    baseline_value=total_expenses,
                    rich_value=fundraising_expenses,
                    message=f"Impossible: fundraising_expenses ({fundraising_expenses:,}) > total_expenses ({total_expenses:,})",
                )

    def _validate_required_fields(self, baseline: dict, result: ValidationResult) -> None:
        """Validate required field combinations.

        Hard failures:
        - wallet_tag == "ZAKAT-ELIGIBLE" but asnaf_category is null
        - charity_claims_zakat == true but claim_evidence is null
        """
        # Get wallet_tag from various possible locations
        wallet_tag = None
        asnaf_category = None
        charity_claims_zakat = None
        claim_evidence = None

        # Check amal_scores for wallet_tag and zakat_bonus
        amal_scores = baseline.get("amal_scores", {})
        wallet_tag = amal_scores.get("wallet_tag")

        zakat_bonus = amal_scores.get("zakat_bonus", {})
        if zakat_bonus:
            asnaf_category = zakat_bonus.get("asnaf_category")
            charity_claims_zakat = zakat_bonus.get("charity_claims_zakat")
            claim_evidence = zakat_bonus.get("claim_evidence")

        # Also check zakat_claim (legacy structure)
        zakat_claim = amal_scores.get("zakat_claim", {})
        if zakat_claim:
            if asnaf_category is None:
                asnaf_category = zakat_claim.get("asnaf_category")
            if charity_claims_zakat is None:
                charity_claims_zakat = zakat_claim.get("charity_claims_zakat")
            if claim_evidence is None:
                claim_evidence = zakat_claim.get("claim_evidence")

        # Check zakat_guidance for additional data
        zakat_guidance = baseline.get("zakat_guidance", {})
        if zakat_guidance:
            # Handle both dict and string formats
            if isinstance(zakat_guidance, str):
                eligibility = zakat_guidance  # e.g., "sadaqah_only"
            else:
                eligibility = zakat_guidance.get("eligibility")
            if eligibility and wallet_tag is None:
                wallet_tag = eligibility
            categories_served = zakat_guidance.get("categories_served", []) if isinstance(zakat_guidance, dict) else []
            if categories_served and asnaf_category is None:
                asnaf_category = categories_served[0] if categories_served else None

        # Rule: If ZAKAT-ELIGIBLE, must have asnaf_category
        if wallet_tag == "ZAKAT-ELIGIBLE" and not asnaf_category:
            result.add_error(
                field="asnaf_category",
                baseline_value=wallet_tag,
                rich_value=asnaf_category,
                message="ZAKAT-ELIGIBLE charities must specify an asnaf_category",
            )

        # Rule: If charity claims zakat, must have evidence
        if charity_claims_zakat is True and not claim_evidence:
            result.add_error(
                field="claim_evidence",
                baseline_value=charity_claims_zakat,
                rich_value=claim_evidence,
                message="charity_claims_zakat=true requires claim_evidence",
            )

    def _validate_cross_system_consistency(self, baseline: dict, rich: dict, result: ValidationResult) -> None:
        """Validate baseline and rich narrative are consistent.

        Hard failures:
        - wallet_tag mismatch between baseline and rich

        Soft warnings:
        - amal_score differs by more than 5 points
        """
        # Get wallet tags from both
        baseline_wallet = self._extract_wallet_tag(baseline)
        rich_wallet = self._extract_wallet_tag(rich)

        # Hard failure: wallet tag must match
        if baseline_wallet and rich_wallet and baseline_wallet != rich_wallet:
            result.add_error(
                field="wallet_tag",
                baseline_value=baseline_wallet,
                rich_value=rich_wallet,
                message=f"Wallet tag mismatch: baseline={baseline_wallet}, rich={rich_wallet}",
            )

        # Get AMAL scores from both
        baseline_score = self._extract_amal_score(baseline)
        rich_score = self._extract_amal_score(rich)

        # Soft warning: scores should be within tolerance
        if baseline_score is not None and rich_score is not None:
            diff = abs(baseline_score - rich_score)
            if diff > self.SCORE_TOLERANCE:
                result.add_warning(
                    field="amal_score",
                    baseline_value=baseline_score,
                    rich_value=rich_score,
                    message=f"AMAL score differs by {diff} points (tolerance: {self.SCORE_TOLERANCE})",
                )

    def _validate_financial_sanity(self, data: dict, result: ValidationResult) -> None:
        """Validate financial relationships make sense.

        Hard failures:
        - totalRevenue > 0 but totalExpenses == 0 or null

        Soft warnings:
        - program + admin + fundraising expenses differ significantly from total
        """
        total_revenue = data.get("total_revenue")
        total_expenses = data.get("total_expenses")

        # If they have revenue, they should have expenses
        if total_revenue is not None and total_revenue > 0:
            if total_expenses is None or total_expenses == 0:
                result.add_error(
                    field="total_expenses",
                    baseline_value=total_revenue,
                    rich_value=total_expenses,
                    message=f"Financial inconsistency: total_revenue={total_revenue:,} but total_expenses is {total_expenses or 'null'}",
                )

        # Check expense sum approximately equals total (warning only)
        program_expenses = data.get("program_expenses")
        admin_expenses = data.get("admin_expenses")
        fundraising_expenses = data.get("fundraising_expenses")

        if all(v is not None for v in [program_expenses, admin_expenses, fundraising_expenses, total_expenses]):
            if total_expenses > 0:
                expense_sum = program_expenses + admin_expenses + fundraising_expenses
                diff_ratio = abs(expense_sum - total_expenses) / total_expenses

                if diff_ratio > self.FLOAT_TOLERANCE:
                    result.add_warning(
                        field="expense_sum",
                        baseline_value=total_expenses,
                        rich_value=expense_sum,
                        message=(
                            f"Expense components ({program_expenses:,} + {admin_expenses:,} + {fundraising_expenses:,} = {expense_sum:,}) "
                            f"differ from total_expenses ({total_expenses:,}) by {diff_ratio * 100:.1f}%"
                        ),
                    )

    def _extract_wallet_tag(self, narrative: dict) -> str | None:
        """Extract wallet_tag from narrative structure."""
        # Try amal_scores first
        amal_scores = narrative.get("amal_scores", {})
        if amal_scores.get("wallet_tag"):
            return amal_scores["wallet_tag"]

        # Try zakat_guidance
        zakat_guidance = narrative.get("zakat_guidance", {})
        if zakat_guidance.get("eligibility"):
            return zakat_guidance["eligibility"]

        return None

    def _extract_amal_score(self, narrative: dict) -> int | None:
        """Extract amal_score from narrative structure."""
        amal_scores = narrative.get("amal_scores", {})
        return amal_scores.get("amal_score")


def validate_for_export(
    data: dict,
    baseline: dict | None = None,
    rich: dict | None = None,
) -> ValidationResult:
    """Convenience function to validate data for export."""
    validator = ExportValidator()
    return validator.validate_for_export(data, baseline, rich)

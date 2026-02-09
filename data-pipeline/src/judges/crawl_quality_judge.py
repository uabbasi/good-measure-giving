"""Crawl Quality Judge - validates data integrity from crawl phase.

Deterministic validation rules that don't require LLM:
- J-001: ProPublica EIN mismatch detection
- J-002: Financial sanity checks (non-negative, plausible ranges)
- J-003: Charity Navigator score consistency
- J-004: Candid seal-evidence match
- J-006: Website-EIN cross-validation
- J-007: BBB name exact-match check
- J-008: Multi-source revenue divergence
- J-010: Zakat claim verification

These rules catch systemic issues that could recur despite code fixes.
"""

import logging
import re
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


# Financial sanity check constants
MAX_PLAUSIBLE_REVENUE = 100_000_000_000  # $100B (largest US nonprofits ~$50B)

# Revenue divergence thresholds
REVENUE_DIVERGENCE_WARNING = 0.5  # >50% divergence = WARNING
REVENUE_DIVERGENCE_ERROR = 0.8  # >80% divergence = ERROR (likely wrong org)

# Expense/revenue ratio thresholds (nonprofits drawing down reserves)
# Deficits up to 15% are common due to grant timing, multi-year spending, end-of-year outlays
EXPENSE_RATIO_WARNING = 1.15  # >115% = WARNING (significant deficit year)
EXPENSE_RATIO_ERROR = 1.35  # >135% = WARNING (severe deficit, may be drawing reserves)


class CrawlQualityJudge(BaseJudge):
    """Judge that validates crawl-phase data quality.

    Unlike LLM-based judges, this judge runs deterministic checks
    on the raw scraped data to catch data integrity issues.
    """

    @property
    def name(self) -> str:
        return "crawl_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate crawl-phase data quality.

        Args:
            output: The exported charity data
            context: Source data context (includes raw_scraped_data)

        Returns:
            JudgeVerdict with any data quality issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")

        # Get source data from context
        source_data = context.get("source_data", {})
        # raw_scraped_data available in context if needed for additional checks

        # J-001: ProPublica EIN mismatch
        issues.extend(self._check_propublica_ein(ein, source_data))

        # J-002: Financial sanity check
        issues.extend(self._check_financial_sanity(ein, output, source_data))

        # J-003: CN score consistency
        issues.extend(self._check_cn_score_consistency(ein, source_data))

        # J-004: Candid seal-evidence match
        issues.extend(self._check_candid_seal_evidence(ein, source_data))

        # J-006: Website-EIN cross-validation
        issues.extend(self._check_website_ein(ein, source_data))

        # J-007: BBB name exact-match check
        issues.extend(self._check_bbb_name_match(ein, output.get("name", ""), source_data))

        # J-008: Multi-source revenue divergence
        issues.extend(self._check_revenue_divergence(ein, source_data))

        # J-010: Zakat claim verification
        issues.extend(self._check_zakat_claim(ein, output, source_data))

        # J-011: Uncorroborated website evidence claims
        issues.extend(self._check_uncorroborated_evidence_claims(ein, source_data))

        # Determine pass/fail
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return JudgeVerdict(
            judge_name=self.name,
            passed=not has_errors,
            issues=issues,
        )

    def _check_propublica_ein(self, expected_ein: str, source_data: dict) -> list[ValidationIssue]:
        """J-001: Verify ProPublica returned data for the correct EIN."""
        issues = []
        propublica = source_data.get("propublica", {}).get("propublica_990", {})

        if not propublica:
            return []

        returned_ein = propublica.get("ein", "")
        if not returned_ein:
            return []

        # Normalize EINs for comparison
        expected_clean = expected_ein.replace("-", "")
        returned_clean = returned_ein.replace("-", "")

        if expected_clean != returned_clean:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="propublica.ein",
                    message=f"ProPublica EIN mismatch: expected {expected_ein}, got {returned_ein}",
                    details={
                        "expected_ein": expected_ein,
                        "returned_ein": returned_ein,
                        "rule": "J-001",
                    },
                )
            )

        return issues

    def _check_financial_sanity(self, ein: str, output: dict, source_data: dict) -> list[ValidationIssue]:
        """J-002: Check financial figures are non-negative and plausible."""
        issues = []

        # Check financials from output and all sources
        financial_sources = [
            ("output", output.get("financials", {})),
            ("propublica", source_data.get("propublica", {}).get("propublica_990", {})),
            ("charity_navigator", source_data.get("charity_navigator", {}).get("cn_profile", {})),
            ("candid", source_data.get("candid", {}).get("candid_profile", {})),
        ]

        for source_name, financials in financial_sources:
            if not financials:
                continue

            # Check revenue
            revenue = financials.get("total_revenue") or financials.get("revenue")
            if revenue is not None:
                try:
                    rev_val = float(revenue)
                    if rev_val < 0:
                        issues.append(
                            ValidationIssue(
                                severity=Severity.ERROR,
                                field=f"{source_name}.total_revenue",
                                message=f"Negative revenue: ${rev_val:,.0f}",
                                details={"source": source_name, "value": rev_val, "rule": "J-002"},
                            )
                        )
                    elif rev_val > MAX_PLAUSIBLE_REVENUE:
                        issues.append(
                            ValidationIssue(
                                severity=Severity.WARNING,
                                field=f"{source_name}.total_revenue",
                                message=f"Implausibly high revenue: ${rev_val:,.0f}",
                                details={"source": source_name, "value": rev_val, "rule": "J-002"},
                            )
                        )
                except (ValueError, TypeError):
                    pass

            # Check assets
            assets = financials.get("total_assets") or financials.get("assets")
            if assets is not None:
                try:
                    assets_val = float(assets)
                    if assets_val < 0:
                        issues.append(
                            ValidationIssue(
                                severity=Severity.ERROR,
                                field=f"{source_name}.total_assets",
                                message=f"Negative assets: ${assets_val:,.0f}",
                                details={"source": source_name, "value": assets_val, "rule": "J-002"},
                            )
                        )
                except (ValueError, TypeError):
                    pass

            # Check expense/revenue ratio for deficit years
            # Note: Deficit spending can be legitimate (drawing down reserves, grant timing)
            # so this is always WARNING severity, not ERROR
            expenses = financials.get("total_expenses") or financials.get("expenses")
            if expenses is not None and revenue is not None:
                try:
                    exp_val = float(expenses)
                    rev_val = float(revenue)
                    if rev_val > 0:
                        ratio = exp_val / rev_val
                        if ratio > EXPENSE_RATIO_ERROR:
                            # >125% = WARNING (severe deficit, but could be drawing down reserves)
                            issues.append(
                                ValidationIssue(
                                    severity=Severity.WARNING,
                                    field=f"{source_name}.expense_ratio",
                                    message=f"Expenses (${exp_val:,.0f}) exceed revenue (${rev_val:,.0f}) by {(ratio - 1) * 100:.0f}% - may be drawing down reserves",
                                    details={
                                        "source": source_name,
                                        "expenses": exp_val,
                                        "revenue": rev_val,
                                        "ratio": ratio,
                                        "rule": "J-002",
                                    },
                                    issue_key="expense_ratio_deficit",
                                )
                            )
                        elif ratio > EXPENSE_RATIO_WARNING:
                            # >100% = WARNING (deficit year)
                            issues.append(
                                ValidationIssue(
                                    severity=Severity.WARNING,
                                    field=f"{source_name}.expense_ratio",
                                    message=f"Expenses (${exp_val:,.0f}) exceed revenue (${rev_val:,.0f}) by {(ratio - 1) * 100:.0f}%",
                                    details={
                                        "source": source_name,
                                        "expenses": exp_val,
                                        "revenue": rev_val,
                                        "ratio": ratio,
                                        "rule": "J-002",
                                    },
                                    issue_key="expense_ratio_deficit",
                                )
                            )
                except (ValueError, TypeError):
                    pass

        return issues

    def _check_cn_score_consistency(self, ein: str, source_data: dict) -> list[ValidationIssue]:
        """J-003: Check CN overall rating matches beacon scores."""
        issues = []
        cn = source_data.get("charity_navigator", {}).get("cn_profile", {})

        if not cn:
            return []

        overall_rating = cn.get("overall_rating")
        beacon_scores = cn.get("beacon_scores", {})

        if overall_rating is None or not beacon_scores:
            return []

        # Note: Star rating to beacon average mapping for reference:
        # 4 stars = ~80%+, 3 stars = ~60-79%, 2 stars = ~40-59%, 1 star = <40%

        # Calculate average beacon score
        beacon_values = [v for v in beacon_scores.values() if isinstance(v, (int, float)) and v is not None]

        if not beacon_values:
            return []

        avg_beacon = sum(beacon_values) / len(beacon_values)

        # Flag if 4-star rating but low beacon average
        if overall_rating == 4 and avg_beacon < 60:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="charity_navigator.rating_consistency",
                    message=f"4-star rating but beacon average is {avg_beacon:.0f}%",
                    details={
                        "overall_rating": overall_rating,
                        "beacon_average": avg_beacon,
                        "beacon_scores": beacon_scores,
                        "rule": "J-003",
                    },
                )
            )

        return issues

    def _check_candid_seal_evidence(self, ein: str, source_data: dict) -> list[ValidationIssue]:
        """J-004: Check Candid platinum seal has outcomes data."""
        issues = []
        candid = source_data.get("candid", {}).get("candid_profile", {})

        if not candid:
            return []

        seal = candid.get("candid_seal")
        outcomes = candid.get("outcomes", [])
        metrics = candid.get("metrics", [])

        # Platinum seal requires demonstrated outcomes
        if seal == "platinum" and not outcomes and not metrics:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="candid.seal_evidence",
                    message="Platinum seal claimed but no outcomes or metrics found",
                    details={
                        "seal": seal,
                        "outcomes_count": len(outcomes),
                        "metrics_count": len(metrics),
                        "rule": "J-004",
                    },
                )
            )

        return issues

    def _check_website_ein(self, expected_ein: str, source_data: dict) -> list[ValidationIssue]:
        """J-006: Check website-extracted EIN matches expected."""
        issues = []
        website = source_data.get("website", {}).get("website_profile", {})

        if not website:
            return []

        # If web_collector stored a related_ein, the mismatch was already detected
        # and the EIN was preserved as a likely parent/subsidiary — downgrade to INFO
        related_ein = website.get("related_ein")
        if related_ein:
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    field="website.ein",
                    message=f"Website shows related EIN ({related_ein}), likely parent/subsidiary of {expected_ein}",
                    details={
                        "expected_ein": expected_ein,
                        "related_ein": related_ein,
                        "rule": "J-006",
                    },
                    issue_key="ein_website_mismatch",
                )
            )
            return issues

        website_ein = website.get("ein", "")
        # Skip if no EIN or LLM returned "null" string
        if not website_ein or str(website_ein).lower() in ("null", "none"):
            return []

        # Normalize for comparison
        expected_clean = expected_ein.replace("-", "")
        website_clean = website_ein.replace("-", "")

        if expected_clean != website_clean:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="website.ein",
                    message=f"Website EIN ({website_ein}) doesn't match expected ({expected_ein})",
                    details={
                        "expected_ein": expected_ein,
                        "website_ein": website_ein,
                        "rule": "J-006",
                    },
                    issue_key="ein_website_mismatch",
                )
            )

        return issues

    def _check_bbb_name_match(self, ein: str, expected_name: str, source_data: dict) -> list[ValidationIssue]:
        """J-007: Check BBB result matches expected charity name."""
        issues = []
        bbb = source_data.get("bbb", {}).get("bbb_profile", {})

        if not bbb or not expected_name:
            return []

        bbb_name = bbb.get("name", "")
        if not bbb_name:
            return []

        # Calculate name similarity
        similarity = self._calculate_name_similarity(expected_name, bbb_name)

        # Require 85% similarity for BBB data (stricter than crawl-time 60%)
        if similarity < 0.85:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="bbb.name_match",
                    message=f"BBB name '{bbb_name}' may not match '{expected_name}' (similarity: {similarity:.0%})",
                    details={
                        "expected_name": expected_name,
                        "bbb_name": bbb_name,
                        "similarity": similarity,
                        "rule": "J-007",
                    },
                )
            )

        return issues

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate word-overlap similarity between two names."""
        if not name1 or not name2:
            return 0.0

        # Normalize names
        def normalize(name):
            name = name.lower()
            # Remove common suffixes
            for suffix in ["inc", "inc.", "incorporated", "llc", "corp", "corporation", "foundation"]:
                name = name.replace(suffix, "")
            # Extract words (3+ chars)
            words = set(re.findall(r"\b[a-z]{3,}\b", name))
            # Remove stopwords
            stopwords = {"the", "and", "for", "usa", "international", "organization", "org"}
            return words - stopwords

        words1 = normalize(name1)
        words2 = normalize(name2)

        if not words1 or not words2:
            return 0.0

        overlap = len(words1 & words2)
        max_words = max(len(words1), len(words2))

        return overlap / max_words if max_words > 0 else 0.0

    def _check_revenue_divergence(self, ein: str, source_data: dict) -> list[ValidationIssue]:
        """J-008: Check revenue consistency across sources.

        Only compares revenues from the same or adjacent fiscal years.
        Different fiscal years can legitimately have very different revenues.
        """
        issues = []

        # Collect revenue AND fiscal year from all sources
        revenue_data: dict[str, dict] = {}  # {source: {revenue, year}}

        propublica = source_data.get("propublica", {}).get("propublica_990", {})
        if propublica:
            rev = propublica.get("total_revenue")
            year = propublica.get("tax_year")
            if rev is not None:
                try:
                    revenue_data["propublica"] = {"revenue": float(rev), "year": year}
                except (ValueError, TypeError):
                    pass

        cn = source_data.get("charity_navigator", {}).get("cn_profile", {})
        if cn:
            rev = cn.get("total_revenue")
            year = cn.get("fiscal_year") or cn.get("tax_year")
            if rev is not None:
                try:
                    revenue_data["charity_navigator"] = {"revenue": float(rev), "year": year}
                except (ValueError, TypeError):
                    pass

        candid = source_data.get("candid", {}).get("candid_profile", {})
        if candid:
            rev = candid.get("total_revenue")
            year = candid.get("fiscal_year") or candid.get("tax_year")
            if rev is not None:
                try:
                    revenue_data["candid"] = {"revenue": float(rev), "year": year}
                except (ValueError, TypeError):
                    pass

        # Need at least 2 sources to compare
        if len(revenue_data) < 2:
            return []

        # Check fiscal year alignment
        years = [d["year"] for d in revenue_data.values() if d.get("year")]
        year_spread = 0
        if len(years) >= 2:
            year_spread = max(years) - min(years)
            if year_spread > 1:
                # Years differ by more than 1 - not comparable, skip divergence check
                logger.debug(
                    f"J-008: Skipping revenue divergence check for {ein} - "
                    f"fiscal years differ by {year_spread} years: "
                    f"{dict((s, d['year']) for s, d in revenue_data.items() if d.get('year'))}"
                )
                return []

        # Extract just revenues for comparison
        revenues = {s: d["revenue"] for s, d in revenue_data.items()}
        values = list(revenues.values())
        max_rev = max(values)
        min_rev = min(values)

        if max_rev > 0 and min_rev > 0:
            divergence = (max_rev - min_rev) / max_rev

            # Build details with year info
            details = {
                "revenues": revenues,
                "fiscal_years": {s: d.get("year") for s, d in revenue_data.items()},
                "divergence": divergence,
                "year_spread": year_spread,
                "rule": "J-008",
            }

            # Determine severity based on year alignment:
            # - Same fiscal year (spread=0): Large divergence = ERROR (likely wrong org)
            # - Adjacent years (spread=1): Large divergence = WARNING (could be year-over-year change)
            same_fiscal_year = year_spread == 0

            if divergence > REVENUE_DIVERGENCE_ERROR:
                if same_fiscal_year:
                    # Same year, >80% divergence = ERROR (likely wrong org)
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field="multi_source.revenue_divergence",
                            message=f"Revenue diverges >{REVENUE_DIVERGENCE_ERROR:.0%} across sources (${min_rev:,.0f} - ${max_rev:,.0f}) in same fiscal year - likely wrong org",
                            details=details,
                        )
                    )
                else:
                    # Different years, large divergence = WARNING (could be legitimate year-over-year change)
                    issues.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            field="multi_source.revenue_divergence",
                            message=f"Revenue diverges >{REVENUE_DIVERGENCE_ERROR:.0%} across sources (${min_rev:,.0f} - ${max_rev:,.0f}) - different fiscal years ({year_spread} year spread)",
                            details=details,
                        )
                    )
            elif divergence > REVENUE_DIVERGENCE_WARNING:
                # >50% divergence = WARNING regardless of year alignment
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field="multi_source.revenue_divergence",
                        message=f"Revenue diverges >{REVENUE_DIVERGENCE_WARNING:.0%} across sources (${min_rev:,.0f} - ${max_rev:,.0f})",
                        details=details,
                    )
                )

        return issues

    def _check_zakat_claim(self, ein: str, output: dict, source_data: dict) -> list[ValidationIssue]:
        """J-010: Verify zakat eligibility claims have evidence."""
        issues = []

        evaluation = output.get("evaluation", {})
        wallet_tag = evaluation.get("wallet_tag") or ""

        # Only check if zakat-eligible is claimed
        if "ZAKAT" not in wallet_tag.upper():
            return []

        # Check website for zakat evidence
        website = source_data.get("website", {}).get("website_profile", {})

        zakat_evidence = False
        if website:
            # Check for explicit zakat indicators
            accepts_zakat = website.get("accepts_zakat")
            zakat_calculator = website.get("zakat_calculator_url")
            zakat_page = website.get("zakat_page_url")

            if accepts_zakat or zakat_calculator or zakat_page:
                zakat_evidence = True

            # Also check for zakat mentions in programs or mission
            programs = website.get("programs", []) or []
            mission = website.get("mission", "") or ""

            zakat_keywords = ["zakat", "zakaat", "zakah"]
            for keyword in zakat_keywords:
                if keyword in mission.lower():
                    zakat_evidence = True
                    break
                for prog in programs:
                    if keyword in prog.lower():
                        zakat_evidence = True
                        break

        # Also check zakat_metadata from synthesize phase (persisted evidence)
        if not zakat_evidence:
            raw = output.get("_raw", {})
            zakat_eval = raw.get("zakatEvaluation") or {}
            zakat_meta = zakat_eval.get("metadata") or {}
            if zakat_meta.get("asnaf_categories_served") or zakat_meta.get("zakat_policy_url"):
                zakat_evidence = True
            if zakat_meta.get("direct_page_verified"):
                zakat_evidence = True

        if not zakat_evidence:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="zakat.evidence",
                    message="ZAKAT-ELIGIBLE claimed but no explicit zakat evidence found on website",
                    details={
                        "wallet_tag": wallet_tag,
                        "accepts_zakat": website.get("accepts_zakat") if website else None,
                        "has_zakat_calculator": bool(website.get("zakat_calculator_url")) if website else False,
                        "rule": "J-010",
                    },
                )
            )

        return issues

    def _check_uncorroborated_evidence_claims(self, ein: str, source_data: dict) -> list[ValidationIssue]:
        """J-011: Detect website evidence claims not supported by authoritative sources.

        When website claims RCTs or third-party evaluations but no authoritative
        source (CN, Candid, BBB) confirms it, this is a high-confidence
        hallucination indicator — escalate to ERROR.
        """
        issues = []

        website = source_data.get("website", {}).get("website_profile", {})
        if not website:
            return issues

        # Check claims_rcts
        if website.get("claims_rcts"):
            # Look for corroboration from authoritative sources
            cn = source_data.get("charity_navigator", {}).get("cn_profile", {})
            candid = source_data.get("candid", {}).get("candid_profile", {})

            has_corroboration = (
                cn.get("third_party_evaluated")
                or candid.get("third_party_evaluated")
                or candid.get("has_external_evaluation")
            )
            if not has_corroboration:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="website.claims_rcts",
                        message="Website claims RCTs but no authoritative source confirms third-party evaluation",
                        details={"rule": "J-011", "claim": "claims_rcts"},
                    )
                )

        # Check claims_third_party_eval
        if website.get("claims_third_party_eval"):
            cn = source_data.get("charity_navigator", {}).get("cn_profile", {})
            candid = source_data.get("candid", {}).get("candid_profile", {})
            bbb = source_data.get("bbb", {}).get("bbb_profile", {})

            has_corroboration = (
                cn.get("third_party_evaluated")
                or candid.get("third_party_evaluated")
                or candid.get("has_external_evaluation")
                or bbb.get("meets_standards")
            )
            if not has_corroboration:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="website.claims_third_party_eval",
                        message="Website claims third-party evaluation but no authoritative source confirms it",
                        details={"rule": "J-011", "claim": "claims_third_party_eval"},
                    )
                )

        return issues

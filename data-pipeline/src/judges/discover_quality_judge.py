"""Discover Quality Judge - validates data integrity from discover phase.

Deterministic validation rules that don't require LLM:
- D-J-001: Confidence threshold (discoveries below 0.75 confidence flagged)
- D-J-002: Source domain validation (evidence should cite trusted sources)
- D-J-003: Cross-discovery consistency (zakat claims need evidence, evaluations need evaluators)

These rules catch issues with LLM-discovered data before downstream phases.
"""

import logging
from typing import Any
from urllib.parse import urlparse

from ..schemas.discovery import (
    SECTION_AWARDS,
    SECTION_EVALUATIONS,
    SECTION_OUTCOMES,
    SECTION_THEORY_OF_CHANGE,
    SECTION_ZAKAT,
)
from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Minimum confidence threshold for discovery results
# User specified 0.7-0.8; using 0.75 as middle ground
CONFIDENCE_THRESHOLD = 0.75

# Trusted domains for third-party evaluations
TRUSTED_EVALUATOR_DOMAINS = {
    "charitynavigator.org",
    "guidestar.org",
    "candid.org",
    "give.org",  # BBB Wise Giving Alliance
    "givewell.org",
    "povertyactionlab.org",  # J-PAL
    "idinsight.org",
    "ipa-usa.org",  # Innovations for Poverty Action
    "openphilanthropy.org",
}


class DiscoverQualityJudge(BaseJudge):
    """Judge that validates discover-phase data quality.

    Unlike LLM-based judges, this judge runs deterministic checks
    on the discovered_profile data to catch discovery issues.
    """

    @property
    def name(self) -> str:
        return "discover_quality"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate discover-phase data quality.

        Args:
            output: The exported charity data
            context: Source data context (includes discovered_profile)

        Returns:
            JudgeVerdict with any data quality issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")

        # Get discovered profile from context
        source_data = context.get("source_data", {})
        discovered = source_data.get("discovered", {})
        discovered_profile = discovered.get("discovered_profile", {})

        if not discovered_profile:
            # No discover phase data - skip validation
            return JudgeVerdict(
                judge_name=self.name,
                passed=True,
                issues=[],
                skipped=True,
                skip_reason="No discovered_profile data found",
            )

        # D-J-001: Confidence threshold validation
        issues.extend(self._check_confidence_threshold(ein, discovered_profile))

        # D-J-002: Source domain validation
        issues.extend(self._check_source_domains(ein, discovered_profile))

        # D-J-003: Cross-discovery consistency
        issues.extend(self._check_cross_discovery_consistency(ein, discovered_profile, context))

        # Determine pass/fail - ERROR severity fails, WARNING doesn't
        has_errors = any(i.severity == Severity.ERROR for i in issues)

        return JudgeVerdict(
            judge_name=self.name,
            passed=not has_errors,
            issues=issues,
        )

    def _check_confidence_threshold(self, ein: str, discovered_profile: dict) -> list[ValidationIssue]:
        """D-J-001: Flag discoveries with confidence below threshold."""
        issues = []

        # Check each discovery type for confidence
        discovery_types = [
            (SECTION_ZAKAT, "zakat_verification_confidence"),
            (SECTION_EVALUATIONS, "confidence"),
            (SECTION_OUTCOMES, "confidence"),
            (SECTION_THEORY_OF_CHANGE, "confidence"),
            (SECTION_AWARDS, "confidence"),
        ]

        for discovery_key, confidence_field in discovery_types:
            discovery = discovered_profile.get(discovery_key)
            if not discovery:
                continue

            confidence = discovery.get(confidence_field, 0.0)
            if confidence is None:
                confidence = 0.0

            # Only flag if there's a positive claim with low confidence
            has_positive_claim = self._has_positive_claim(discovery_key, discovery)

            if has_positive_claim and confidence < CONFIDENCE_THRESHOLD:
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,  # Informational - LLM uncertainty shouldn't penalize score
                        field=f"discovered.{discovery_key}.confidence",
                        message=f"Low confidence ({confidence:.2f}) for {discovery_key} discovery (threshold: {CONFIDENCE_THRESHOLD})",
                        details={
                            "confidence": confidence,
                            "threshold": CONFIDENCE_THRESHOLD,
                            "discovery_type": discovery_key,
                            "rule": "D-J-001",
                        },
                    )
                )

        return issues

    def _has_positive_claim(self, discovery_key: str, discovery: dict) -> bool:
        """Check if discovery makes a positive claim that needs confidence."""
        if discovery_key == SECTION_ZAKAT:
            return discovery.get("accepts_zakat", False)
        elif discovery_key == SECTION_EVALUATIONS:
            return discovery.get("third_party_evaluated", False)
        elif discovery_key == SECTION_OUTCOMES:
            return bool(discovery.get("has_reported_outcomes", False) or discovery.get("metrics", []))
        elif discovery_key == SECTION_THEORY_OF_CHANGE:
            return bool(discovery.get("has_theory_of_change", False))
        elif discovery_key == SECTION_AWARDS:
            return bool(discovery.get("awards", []))
        return False

    def _check_source_domains(self, ein: str, discovered_profile: dict) -> list[ValidationIssue]:
        """D-J-002: Validate source domains for evaluation claims."""
        issues = []

        # Get charity's own domain for comparison
        website_url = discovered_profile.get("website_url")
        charity_domain = None
        if website_url:
            parsed = urlparse(website_url)
            charity_domain = parsed.netloc.lower().replace("www.", "")

        # Check evaluations for source domain validity
        evaluations = discovered_profile.get(SECTION_EVALUATIONS, {})
        if evaluations and evaluations.get("third_party_evaluated"):
            evaluators = evaluations.get("evaluators", [])
            for i, evaluator in enumerate(evaluators):
                url = evaluator.get("url")
                if not url:
                    continue

                parsed = urlparse(url)
                domain = parsed.netloc.lower().replace("www.", "")

                # Check if domain is trusted or charity's own
                is_trusted = any(domain.endswith(trusted) for trusted in TRUSTED_EVALUATOR_DOMAINS)
                is_charity_domain = charity_domain and (
                    domain == charity_domain or domain.endswith("." + charity_domain)
                )

                if not is_trusted and not is_charity_domain:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.INFO,  # Informational - untrusted source isn't necessarily wrong
                            field=f"discovered.evaluations.evaluators[{i}].url",
                            message=f"Evaluation source domain '{domain}' is not a known trusted evaluator",
                            details={
                                "url": url,
                                "domain": domain,
                                "evaluator_name": evaluator.get("name"),
                                "trusted_domains": list(TRUSTED_EVALUATOR_DOMAINS),
                                "rule": "D-J-002",
                            },
                        )
                    )

        return issues

    def _check_cross_discovery_consistency(
        self, ein: str, discovered_profile: dict, context: dict[str, Any] | None = None
    ) -> list[ValidationIssue]:
        """D-J-003: Verify consistency across discovery results.

        This rule is ERROR severity per user request - inconsistent
        discoveries indicate data quality issues that should block export.
        """
        context = context or {}
        issues = []

        # Check 1: Zakat acceptance without evidence
        zakat = discovered_profile.get(SECTION_ZAKAT, {})
        if zakat and zakat.get("accepts_zakat"):
            evidence = zakat.get("accepts_zakat_evidence")
            url = zakat.get("accepts_zakat_url")
            direct_verified = zakat.get("direct_page_verified", False)
            confidence = zakat.get("zakat_verification_confidence", 0)

            # Need either evidence text, source URL, or direct page verification
            if not evidence and not url and not direct_verified:
                # If confidence is high (>= threshold) but no evidence, that's an error
                # If confidence is low, the LLM itself is uncertain - just warn
                severity = Severity.ERROR if confidence >= CONFIDENCE_THRESHOLD else Severity.WARNING
                issues.append(
                    ValidationIssue(
                        severity=severity,
                        field="discovered.zakat",
                        message="Zakat acceptance claimed but no evidence, URL, or direct verification provided",
                        details={
                            "accepts_zakat": True,
                            "has_evidence": bool(evidence),
                            "has_url": bool(url),
                            "direct_page_verified": direct_verified,
                            "confidence": confidence,
                            "rule": "D-J-003",
                        },
                    )
                )

        # Check 2: Third-party evaluated without evaluators is ERROR
        evaluations = discovered_profile.get(SECTION_EVALUATIONS, {})
        if evaluations and evaluations.get("third_party_evaluated"):
            evaluators = evaluations.get("evaluators", [])
            if not evaluators:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="discovered.evaluations",
                        message="Third-party evaluation claimed but no evaluators listed",
                        details={
                            "third_party_evaluated": True,
                            "evaluators_count": 0,
                            "rule": "D-J-003",
                        },
                    )
                )

        # Check 3: Awards claimed but no awards list is ERROR
        awards = discovered_profile.get(SECTION_AWARDS, {})
        if awards:
            has_awards_flag = awards.get("has_awards", False)
            awards_list = awards.get("awards", [])
            if has_awards_flag and not awards_list:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="discovered.awards",
                        message="Awards claimed but no awards listed",
                        details={
                            "has_awards": True,
                            "awards_count": 0,
                            "rule": "D-J-003",
                        },
                    )
                )

        # Check 4: Theory of change claimed but empty
        # ERROR if no content AND no URL AND aggregator still trusts the claim
        # INFO if the aggregator already filtered it out (phantom ToC handled)
        # INFO if no content but has URL (partial evidence)
        toc = discovered_profile.get(SECTION_THEORY_OF_CHANGE, {})
        if toc:
            has_toc = toc.get("has_theory_of_change", False)
            toc_content = toc.get("evidence")
            toc_url = toc.get("url")
            if has_toc and not toc_content:
                if toc_url:
                    # Has URL but no description - partial evidence, informational only
                    issues.append(
                        ValidationIssue(
                            severity=Severity.INFO,
                            field="discovered.theory_of_change",
                            message="Theory of change URL found but description not extracted",
                            details={
                                "has_theory_of_change": True,
                                "has_url": True,
                                "url": toc_url,
                                "has_content": False,
                                "rule": "D-J-003",
                            },
                        )
                    )
                else:
                    # No URL and no description — check if aggregator filtered it out
                    synth_data = context.get("charity_data", {})
                    synth_has_toc = synth_data.get("has_theory_of_change") if synth_data else None
                    if synth_has_toc:
                        # Aggregator still trusts the claim — real problem
                        severity = Severity.ERROR
                        message = "Theory of change claimed but no description or URL provided"
                    else:
                        # Aggregator already filtered this phantom ToC — no scoring impact
                        severity = Severity.INFO
                        message = "Discovery claimed theory of change but no evidence; aggregator filtered it out"
                    issues.append(
                        ValidationIssue(
                            severity=severity,
                            field="discovered.theory_of_change",
                            message=message,
                            details={
                                "has_theory_of_change": True,
                                "has_url": False,
                                "has_content": False,
                                "synth_has_toc": synth_has_toc,
                                "rule": "D-J-003",
                            },
                        )
                    )

        return issues

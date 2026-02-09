"""Recognition Data Judge - validates awards/recognition data accuracy.

Catches issues like:
1. Fake CN beacons (e.g., "Encompass Award" which is just CN's rating system name)
2. CN beacons for unrated charities (cn_is_rated=False but beacons present)
3. CN scores without proper rated status
4. False Candid seals from CSS class artifacts
5. Low star ratings being shown (only 4-star should be displayed)
6. BBB status without supporting data

These issues were identified from production bugs fixed on 2025-01-25.
"""

import logging
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Known false positive beacons that are NOT actual awards
FAKE_BEACON_PATTERNS = {
    "Encompass Award": "Encompass is CN's rating system name, not an award",
    "Profile Managed": "Just means nonprofit manages their CN profile",
}

# Candid seal levels that are valid (anything else is suspicious)
VALID_CANDID_SEALS = {"platinum", "gold", "silver", "bronze"}

# Minimum star rating to display
MIN_DISPLAY_STAR_RATING = 4


class RecognitionDataJudge(BaseJudge):
    """Judge that validates recognition/awards data accuracy.

    This is a non-LLM judge that performs deterministic checks on
    recognition data to catch false positives and inconsistencies.
    """

    @property
    def name(self) -> str:
        return "recognition_data"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate recognition data for a charity.

        Args:
            output: The exported charity data
            context: Source data context including raw_sources

        Returns:
            JudgeVerdict with any recognition data issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")
        charity_name = output.get("name", "Unknown")

        # Get raw source data for validation
        raw_sources = context.get("raw_sources", {})
        cn_profile = raw_sources.get("charity_navigator", {})
        candid_profile = raw_sources.get("candid", {})

        # Get exported awards data
        awards = output.get("awards", {}) or {}
        cn_beacons = awards.get("cnBeacons", []) or []
        candid_seal = awards.get("candidSeal")
        bbb_status = awards.get("bbbStatus")
        bbb_review_url = awards.get("bbbReviewUrl")

        # === Check 1: Fake CN Beacons ===
        for beacon in cn_beacons:
            for fake_beacon, reason in FAKE_BEACON_PATTERNS.items():
                if fake_beacon.lower() in beacon.lower():
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field="awards.cnBeacons",
                            message=f"Fake beacon detected: '{beacon}' - {reason}",
                            details={
                                "ein": ein,
                                "charity_name": charity_name,
                                "beacon": beacon,
                                "pattern": fake_beacon,
                            },
                        )
                    )

        # === Check 2: CN beacons without cn_is_rated ===
        cn_is_rated = cn_profile.get("cn_is_rated")  # Can be True, False, or None
        if cn_beacons and cn_is_rated is not True:
            # cn_is_rated could be False (not rated) or None (stale data)
            issue_type = "stale data" if cn_is_rated is None else "not rated"
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="awards.cnBeacons",
                    message=f"CN beacons present but cn_is_rated={cn_is_rated} ({issue_type}) - may need re-crawl",
                    details={
                        "ein": ein,
                        "charity_name": charity_name,
                        "beacons": cn_beacons,
                        "cn_is_rated": cn_is_rated,
                        "issue_type": issue_type,
                    },
                )
            )

        # === Check 3: CN score without rated status ===
        cn_overall_score = cn_profile.get("overall_score")
        if cn_overall_score and cn_is_rated is not True:
            # Check if it's just an Encompass Award (culture_score only)
            cn_has_encompass_award = cn_profile.get("cn_has_encompass_award", False)
            cn_beacon_count = cn_profile.get("cn_beacon_count", 0)

            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="cn_overall_score",
                    message=f"CN score {cn_overall_score} present but charity is not fully rated",
                    details={
                        "ein": ein,
                        "charity_name": charity_name,
                        "cn_overall_score": cn_overall_score,
                        "cn_is_rated": cn_is_rated,
                        "cn_has_encompass_award": cn_has_encompass_award,
                        "cn_beacon_count": cn_beacon_count,
                        "note": "May be Encompass Award only, not full rating",
                    },
                )
            )

        # === Check 4: Low star rating being displayed ===
        star_rating_beacons = [b for b in cn_beacons if "Star Rating" in b]
        for beacon in star_rating_beacons:
            # Extract star count from "4-Star Rating"
            try:
                stars = int(beacon.split("-")[0])
                if stars < MIN_DISPLAY_STAR_RATING:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            field="awards.cnBeacons",
                            message=f"Low star rating displayed: {beacon} (only {MIN_DISPLAY_STAR_RATING}+ should be shown)",
                            details={
                                "ein": ein,
                                "charity_name": charity_name,
                                "star_rating": stars,
                                "min_display": MIN_DISPLAY_STAR_RATING,
                            },
                        )
                    )
            except (ValueError, IndexError):
                pass

        # === Check 5: Candid seal without URL ===
        if candid_seal and not awards.get("candidUrl"):
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="awards.candidSeal",
                    message=f"Candid seal '{candid_seal}' displayed without profile URL",
                    details={
                        "ein": ein,
                        "charity_name": charity_name,
                        "candid_seal": candid_seal,
                    },
                )
            )

        # === Check 6: Only Platinum seals should be displayed ===
        # Gold/Silver/Bronze are too common to be meaningful - we only show Platinum
        if candid_seal and candid_seal.lower() != "platinum":
            # Non-Platinum seal leaked through the filter - this is a problem
            raw_candid_seal = candid_profile.get("candid_seal") or candid_profile.get("transparency_seal")
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="awards.candidSeal",
                    message=f"Non-Platinum Candid seal being displayed: {candid_seal}",
                    details={
                        "ein": ein,
                        "charity_name": charity_name,
                        "displayed_seal": candid_seal,
                        "raw_seal": raw_candid_seal,
                        "note": "Only Platinum seals should be displayed",
                    },
                )
            )

        # === Check 7: BBB status consistency ===
        if bbb_status and not bbb_review_url:
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    field="awards.bbbStatus",
                    message=f"BBB status '{bbb_status}' without review URL",
                    details={
                        "ein": ein,
                        "charity_name": charity_name,
                        "bbb_status": bbb_status,
                    },
                )
            )

        # === Check 8: Raw beacons contain excluded items that leaked through ===
        raw_beacons = cn_profile.get("beacons", []) or []
        for beacon in raw_beacons:
            if beacon in FAKE_BEACON_PATTERNS and beacon in cn_beacons:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        field="awards.cnBeacons",
                        message=f"Excluded beacon leaked through: '{beacon}'",
                        details={
                            "ein": ein,
                            "charity_name": charity_name,
                            "beacon": beacon,
                            "source": "raw_beacons",
                        },
                    )
                )

        # === Check 9: Candid seal value validity ===
        if candid_seal and candid_seal.lower() not in VALID_CANDID_SEALS:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    field="awards.candidSeal",
                    message=f"Invalid Candid seal value: '{candid_seal}'",
                    details={
                        "ein": ein,
                        "charity_name": charity_name,
                        "candid_seal": candid_seal,
                        "valid_seals": list(VALID_CANDID_SEALS),
                    },
                )
            )

        # === Check 10: Suspiciously high transparency score without seal ===
        # If we calculated 100 for transparency but no Candid seal, something's off
        source_attribution = output.get("sourceAttribution", {}) or {}
        candid_attrs = source_attribution.get("candid_seal", {})
        if candid_attrs.get("value") and not candid_seal:
            raw_seal_value = candid_attrs.get("value")
            if raw_seal_value and raw_seal_value.lower() in VALID_CANDID_SEALS:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field="awards.candidSeal",
                        message=f"Candid seal '{raw_seal_value}' in sourceAttribution but not in awards",
                        details={
                            "ein": ein,
                            "charity_name": charity_name,
                            "source_attribution_seal": raw_seal_value,
                            "awards_seal": candid_seal,
                        },
                    )
                )

        # Determine pass/fail
        has_errors = any(issue.severity == Severity.ERROR for issue in issues)

        return JudgeVerdict(
            passed=not has_errors,
            judge_name=self.name,
            issues=issues,
            metadata={
                "ein": ein,
                "charity_name": charity_name,
                "cn_is_rated": cn_is_rated,
                "has_cn_beacons": len(cn_beacons) > 0,
                "has_candid_seal": candid_seal is not None,
                "has_bbb_status": bbb_status is not None,
            },
        )

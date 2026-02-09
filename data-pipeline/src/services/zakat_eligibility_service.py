"""
Zakat Eligibility Service - Check if charity claims to accept zakat.

Simple approach: Does the charity claim to accept zakat?
- If yes → ZAKAT-ELIGIBLE
- If no → SADAQAH-ELIGIBLE

We're not in the business of determining zakat eligibility ourselves.
We just check if the charity explicitly claims to collect zakat.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Minimum confidence to trust the discover service's finding
# This filters out obvious LLM hallucinations (very low confidence results)
DEFAULT_MIN_CONFIDENCE = 0.5

# Names that definitively imply zakat acceptance (no verification needed)
DEFAULT_DEFINITIVE_NAMES = {
    "baitulmaal", "baytulmaal", "bait ul maal",
    "zakat foundation", "zakat fund", "zakaat",
}

# Charities that partner with zakat orgs but don't directly collect zakat
# These are false positives from LLM search that should be rejected
# Also includes all non-Muslim HIDE:TRUE charities from pilot_charities.txt
ZAKAT_DENYLIST = {
    # === EA Benchmark ===
    "13-5562162",  # Helen Keller International
    "20-3069841",  # Against Malaria Foundation
    # === Major Humanitarian (Non-Muslim) ===
    "53-0196605",  # American Red Cross
    "95-1831116",  # Direct Relief
    "13-1685039",  # CARE USA
    "06-0726487",  # Save the Children Federation
    "36-3673599",  # Feeding America
    "13-1760110",  # UNICEF USA - partners with Zakat Foundation, doesn't collect directly
    "58-1454716",  # The Carter Center
    "27-3521132",  # World Central Kitchen
    "91-1914868",  # Habitat for Humanity International
    "23-7069110",  # Oxfam America
    "27-1661997",  # GiveDirectly
    "22-3936753",  # Charity Water
    "13-1837442",  # Cancer Research Institute
    "13-3327220",  # Action Against Hunger
    "13-2875808",  # Human Rights Watch
    "20-2622550",  # Fight Colorectal Cancer
    "92-1198452",  # The Intercept
    # === Civil Rights & Justice ===
    "13-6213516",  # ACLU Foundation
    "63-1135091",  # Equal Justice Initiative
    "32-0077563",  # Innocence Project
    "63-0598743",  # Southern Poverty Law Center
    "58-1956686",  # Project South
    "26-1140201",  # Dream.Org
    "47-5015710",  # Chicago Community Bond Fund - partners with Believers Bail Out
    # === Environment & Climate ===
    "26-1150699",  # 350.org
    "94-6069890",  # Sierra Club Foundation
    "13-2654926",  # Natural Resources Defense Council
    "94-1730465",  # Earthjustice
    "13-3377893",  # Rainforest Alliance
    "04-2535767",  # Union of Concerned Scientists
}


@dataclass
class ZakatEligibilityResult:
    """Result of zakat eligibility check."""

    claims_zakat: bool
    evidence: Optional[str]
    confidence: float


class ZakatEligibilityService:
    """
    Check if a charity claims to accept zakat donations.

    This service does NOT determine if a charity SHOULD be zakat-eligible.
    It only checks if the charity CLAIMS to accept zakat.

    Example:
        service = ZakatEligibilityService()
        result = service.check_zakat_claim(
            name="Islamic Relief USA",
            discovered_zakat={
                "accepts_zakat": True,
                "accepts_zakat_evidence": "Give your Zakat to help...",
                "zakat_verification_confidence": 0.85,
                "accepts_zakat_url": "https://irusa.org/zakat"
            }
        )
        print(result.claims_zakat)  # True
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize with optional config from scoring_weights.yaml."""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "scoring_weights.yaml"

        self._load_config(config_path)

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from YAML file."""
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            zakat_config = config.get("zakat", {}).get("eligibility_verification", {})

            # Minimum confidence to trust the claim
            self.min_confidence = zakat_config.get("min_confidence", DEFAULT_MIN_CONFIDENCE)

            # Names that definitively imply zakat acceptance
            self.definitive_names = set(
                name.lower() for name in zakat_config.get("definitive_names", DEFAULT_DEFINITIVE_NAMES)
            )

            logger.debug(f"Loaded zakat config: min_confidence={self.min_confidence}")

        except Exception as e:
            logger.warning(f"Failed to load zakat config, using defaults: {e}")
            self.min_confidence = DEFAULT_MIN_CONFIDENCE
            self.definitive_names = DEFAULT_DEFINITIVE_NAMES

    def check_zakat_claim(
        self,
        name: str,
        discovered_zakat: Optional[dict],
        ein: Optional[str] = None,
    ) -> ZakatEligibilityResult:
        """
        Check if charity claims to accept zakat.

        Args:
            name: Charity name
            discovered_zakat: Zakat data from discover service (optional)
                Expected keys: accepts_zakat, accepts_zakat_evidence,
                               zakat_verification_confidence, accepts_zakat_url
            ein: Charity EIN for denylist checking (optional)

        Returns:
            ZakatEligibilityResult with claim status and evidence
        """
        # 0. Check denylist first - these are known false positives
        if ein and ein in ZAKAT_DENYLIST:
            logger.debug(f"Rejecting zakat claim for '{name}' (EIN {ein}): in denylist")
            return ZakatEligibilityResult(
                claims_zakat=False,
                evidence="Organization is in zakat denylist (partners but doesn't collect directly)",
                confidence=0.0,
            )

        name_lower = name.lower()

        # 1. Check for names that definitively imply zakat acceptance
        #    (e.g., "Baitulmaal" = zakat treasury, "Zakat Foundation")
        for definitive_name in self.definitive_names:
            if definitive_name in name_lower:
                return ZakatEligibilityResult(
                    claims_zakat=True,
                    evidence=f"Organization name implies zakat acceptance ('{definitive_name}')",
                    confidence=1.0,
                )

        # 2. Check if discover service found the charity claims zakat
        if not discovered_zakat:
            return ZakatEligibilityResult(
                claims_zakat=False,
                evidence=None,
                confidence=0.0,
            )

        accepts = discovered_zakat.get("accepts_zakat", False)
        evidence = discovered_zakat.get("accepts_zakat_evidence")
        confidence = discovered_zakat.get("zakat_verification_confidence", 0.0)
        source_url = discovered_zakat.get("accepts_zakat_url")

        # If discover service didn't find zakat claim, return false
        if not accepts:
            return ZakatEligibilityResult(
                claims_zakat=False,
                evidence=evidence,
                confidence=confidence,
            )

        # 3. Apply minimum confidence threshold to filter obvious hallucinations
        if confidence < self.min_confidence:
            logger.debug(
                f"Rejecting zakat claim for '{name}': "
                f"confidence {confidence:.2f} < min {self.min_confidence}"
            )
            return ZakatEligibilityResult(
                claims_zakat=False,
                evidence=evidence,
                confidence=confidence,
            )

        # 4. Charity claims zakat - build evidence string
        evidence_str = evidence or "Charity claims to accept zakat"
        if source_url:
            evidence_str += f" (Source: {source_url})"

        return ZakatEligibilityResult(
            claims_zakat=True,
            evidence=evidence_str,
            confidence=confidence,
        )


# Singleton instance
_service_instance: Optional[ZakatEligibilityService] = None


def get_zakat_eligibility_service() -> ZakatEligibilityService:
    """Get or create the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ZakatEligibilityService()
    return _service_instance


def determine_zakat_eligibility(
    name: str,
    mission: Optional[str],  # Kept for API compatibility, but not used
    discovered_zakat: Optional[dict],
    ein: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Check if charity claims to accept zakat.

    Args:
        name: Charity name
        mission: Not used (kept for API compatibility)
        discovered_zakat: Zakat data from discover service
        ein: Charity EIN for denylist checking (optional)

    Returns:
        Tuple of (claims_zakat: bool, evidence: Optional[str])
    """
    del mission  # Explicitly mark as unused
    service = get_zakat_eligibility_service()
    result = service.check_zakat_claim(name, discovered_zakat, ein)
    return result.claims_zakat, result.evidence

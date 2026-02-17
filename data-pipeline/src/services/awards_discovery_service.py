"""
Awards Discovery Service using Gemini Search Grounding.

Discovers awards, recognition, and certifications received by charities
from philanthropic organizations, foundations, or charity evaluators.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from ..agents.gemini_search import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    GeminiSearchClient,
    SearchGroundingResult,
    calculate_grounding_confidence,
    extract_json_from_response,
)
from ..schemas.discovery import AwardsDict

logger = logging.getLogger(__name__)


@dataclass
class AwardsDiscovery:
    """Result of awards/recognition discovery."""

    has_awards: bool
    awards: list[dict] = field(default_factory=list)  # [{name, issuer, year}]
    awards_evidence: Optional[str] = None
    confidence: float = 0.0
    source_count: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None  # Set when JSON parsing fails

    def to_dict(self) -> AwardsDict:
        """Convert to dictionary for storage."""
        return {
            "has_awards": self.has_awards,
            "awards": self.awards,
            "evidence": self.awards_evidence,
            "confidence": self.confidence,
        }


AWARDS_DISCOVERY_PROMPT = """You are discovering awards and recognition received by a US-based charity.

IMPORTANT REQUIREMENTS:
1. Only consider awards given to the SPECIFIC US organization being evaluated
2. International affiliates or parent organizations are DIFFERENT entities
3. If recognition is about an international branch (e.g., UK, Australia, Switzerland),
   this does NOT apply to the US organization

Look for:
- Charity ratings: Platinum/Gold Seal from Candid/GuideStar, 4-star from Charity Navigator
- Awards: Top-Rated Nonprofit from GreatNonprofits, MacArthur Grant
- Certifications: BBB Accredited Charity, ECFA certified
- Recognition: Featured in media, government recognition, foundation awards
- Rankings: Listed in "Top 100 nonprofits", Best Places to Work for Nonprofits

Based on your search results, answer these questions about {charity_name}:

1. Has this charity received any awards or recognition? (true/false)
2. List each award with issuing organization and year if available
3. What evidence describes their recognition?

IMPORTANT: You MUST respond with valid JSON only. No other text before or after the JSON.

If awards are found:
{{
    "has_awards": true,
    "awards": [
        {{"name": "Top-Rated Nonprofit", "issuer": "GreatNonprofits", "year": 2023}},
        {{"name": "Platinum Seal", "issuer": "Candid/GuideStar", "year": 2023}}
    ],
    "evidence": "Description of their awards and recognition"
}}

If NO awards are found, respond with exactly:
{{
    "has_awards": false,
    "awards": [],
    "evidence": null
}}

Only include verified awards with credible issuers. Always respond with valid JSON."""


class AwardsDiscoveryService:
    """
    Service to discover awards and recognition using Gemini Search Grounding.

    Example:
        service = AwardsDiscoveryService()
        result = service.discover("Islamic Relief USA", "https://irusa.org")
        print(result.has_awards)  # True
        print(result.awards)  # [{name: "Platinum Seal", issuer: "GuideStar"}]
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        """Initialize with Gemini search client."""
        self.client = GeminiSearchClient(model=model)
        self.model = model

    def discover(
        self,
        charity_name: str,
        website_url: Optional[str] = None,
    ) -> AwardsDiscovery:
        """
        Discover awards and recognition for a charity.

        Args:
            charity_name: Name of the charity
            website_url: Optional website URL for context

        Returns:
            AwardsDiscovery with award details
        """
        # Build the search query
        query = f'Has the US nonprofit "{charity_name}" received any awards, recognition, or certifications from philanthropic organizations, foundations, or charity evaluators? Include year and issuing organization.'
        if website_url:
            domain = urlparse(website_url).netloc
            query = f'Has the US nonprofit "{charity_name}" ({domain}) received any awards, recognition, or certifications from philanthropic organizations, foundations, or charity evaluators? Include year and issuing organization.'

        logger.info(f"Discovering awards for: {charity_name}")

        try:
            system_prompt = AWARDS_DISCOVERY_PROMPT.format(charity_name=charity_name)
            result: SearchGroundingResult = self.client.search(
                query=query,
                system_prompt=system_prompt,
                temperature=0.1,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )

            discovery = self._parse_response(result, charity_name)

            logger.info(
                f"Awards discovery for {charity_name}: "
                f"has_awards={discovery.has_awards}, "
                f"awards={len(discovery.awards)}, "
                f"cost=${discovery.cost_usd:.4f}"
            )

            return discovery

        except Exception as e:
            error_msg = f"Awards discovery failed for {charity_name}: {e}"
            logger.error(error_msg)
            return AwardsDiscovery(
                has_awards=False,
                awards=[],
                awards_evidence=None,
                confidence=0.0,
                source_count=0,
                cost_usd=0.0,
                error=error_msg,
            )

    def _parse_response(
        self,
        result: SearchGroundingResult,
        charity_name: str,
    ) -> AwardsDiscovery:
        """Parse Gemini response into AwardsDiscovery."""
        # Use shared JSON extraction (handles markdown, truncation, etc.)
        json_str = extract_json_from_response(result.text)

        if not json_str:
            # If no search sources AND no JSON, this is expected "no data found"
            # Only error if we HAD sources but couldn't parse the response
            if result.source_count == 0:
                logger.info(f"No awards found for {charity_name} (0 search sources)")
                return AwardsDiscovery(
                    has_awards=False,
                    awards=[],
                    awards_evidence=None,
                    confidence=0.0,
                    source_count=0,
                    cost_usd=result.cost_usd,
                    error=None,  # Not an error - just no data found
                )
            else:
                error_msg = f"No JSON found in awards response for {charity_name} ({result.source_count} sources)"
                logger.error(error_msg)
                logger.debug(f"Raw response (first 500 chars): {result.text[:500]}")
                return AwardsDiscovery(
                    has_awards=False,
                    awards=[],
                    awards_evidence=None,
                    confidence=0.0,
                    source_count=result.source_count,
                    cost_usd=result.cost_usd,
                    error=error_msg,
                )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse awards response JSON for {charity_name}: {e}"
            logger.error(error_msg)
            logger.debug(f"Extracted JSON (first 500 chars): {json_str[:500]}")
            return AwardsDiscovery(
                has_awards=False,
                awards=[],
                awards_evidence=None,
                confidence=0.0,
                source_count=result.source_count,
                cost_usd=result.cost_usd,
                error=error_msg,
            )

        # Extract fields
        has_awards = data.get("has_awards", False)
        awards = data.get("awards", [])
        evidence = data.get("evidence")

        # Use shared confidence calculation
        confidence = calculate_grounding_confidence(result)

        # Reject phantom claims: LLM says has_awards=True but awards list is empty
        if has_awards and not awards:
            logger.warning(
                f"Rejecting phantom awards claim for {charity_name}: has_awards=True but awards list is empty"
            )
            has_awards = False

        return AwardsDiscovery(
            has_awards=has_awards,
            awards=awards,
            awards_evidence=evidence,
            confidence=confidence,
            source_count=result.source_count,
            cost_usd=result.cost_usd,
        )


def discover_awards(
    charity_name: str,
    website_url: Optional[str] = None,
) -> AwardsDiscovery:
    """Quick awards discovery for a charity."""
    service = AwardsDiscoveryService()
    return service.discover(charity_name, website_url)

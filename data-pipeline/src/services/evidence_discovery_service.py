"""
Evidence Discovery Service using Gemini Search Grounding.

Discovers whether a charity has been evaluated by third-party organizations
like J-PAL, GiveWell, IDinsight, Charity Navigator, BBB Wise Giving Alliance,
or independent auditors.
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
from ..schemas.discovery import EvaluationsDict

logger = logging.getLogger(__name__)


@dataclass
class EvidenceDiscovery:
    """Result of third-party evaluation discovery."""

    third_party_evaluated: bool
    evaluators: list[dict] = field(default_factory=list)  # [{name, rating, year, url, firm}]
    evaluation_evidence: Optional[str] = None
    confidence: float = 0.0
    source_count: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None  # Set when JSON parsing fails

    def to_dict(self) -> EvaluationsDict:
        """Convert to dictionary for storage."""
        return {
            "third_party_evaluated": self.third_party_evaluated,
            "evaluators": self.evaluators,
            "evidence": self.evaluation_evidence,
            "confidence": self.confidence,
        }


EVIDENCE_DISCOVERY_PROMPT = """You are discovering whether a charity has been evaluated by third-party organizations.

Third-party evaluators include:
- Research organizations: J-PAL, IDinsight, Innovations for Poverty Action (IPA)
- Charity evaluators: GiveWell, Charity Navigator, BBB Wise Giving Alliance, Candid/GuideStar
- Independent auditors: Deloitte, PwC, KPMG, EY, or other auditing firms
- Academic institutions conducting impact studies

Based on your search results, answer these questions about {charity_name}:

1. Has this charity been evaluated by any external organization? (true/false)
2. List each evaluator with their rating/finding and year if available
3. What evidence describes their evaluations?

IMPORTANT: You MUST respond with valid JSON only. No other text before or after the JSON.

If evaluations are found:
{{
    "third_party_evaluated": true,
    "evaluators": [
        {{"name": "Charity Navigator", "rating": "4-star", "year": 2023, "url": null}},
        {{"name": "External auditor", "firm": "Deloitte", "year": 2023, "url": null}}
    ],
    "evidence": "Quote or description of evaluation findings"
}}

If NO evaluations are found, respond with exactly:
{{
    "third_party_evaluated": false,
    "evaluators": [],
    "evidence": null
}}

Always respond with valid JSON."""


class EvidenceDiscoveryService:
    """
    Service to discover third-party evaluations using Gemini Search Grounding.

    Example:
        service = EvidenceDiscoveryService()
        result = service.discover("Islamic Relief USA", "https://irusa.org")
        print(result.third_party_evaluated)  # True
        print(result.evaluators)  # [{name: "Charity Navigator", ...}]
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        """Initialize with Gemini search client."""
        self.client = GeminiSearchClient(model=model)
        self.model = model

    def discover(
        self,
        charity_name: str,
        website_url: Optional[str] = None,
    ) -> EvidenceDiscovery:
        """
        Discover third-party evaluations for a charity.

        Args:
            charity_name: Name of the charity
            website_url: Optional website URL for context

        Returns:
            EvidenceDiscovery with evaluator details
        """
        # Build the search query
        query = f'Has "{charity_name}" been evaluated by external organizations like J-PAL, GiveWell, IDinsight, Charity Navigator, BBB Wise Giving Alliance, or independent auditors? Include any published evaluations or assessments.'
        if website_url:
            domain = urlparse(website_url).netloc
            query = f'Has "{charity_name}" ({domain}) been evaluated by external organizations like J-PAL, GiveWell, IDinsight, Charity Navigator, BBB Wise Giving Alliance, or independent auditors? Include any published evaluations or assessments.'

        logger.info(f"Discovering evaluations for: {charity_name}")

        try:
            system_prompt = EVIDENCE_DISCOVERY_PROMPT.format(charity_name=charity_name)
            result: SearchGroundingResult = self.client.search(
                query=query,
                system_prompt=system_prompt,
                temperature=0.1,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )

            discovery = self._parse_response(result, charity_name)

            logger.info(
                f"Evidence discovery for {charity_name}: "
                f"evaluated={discovery.third_party_evaluated}, "
                f"evaluators={len(discovery.evaluators)}, "
                f"cost=${discovery.cost_usd:.4f}"
            )

            return discovery

        except Exception as e:
            logger.error(f"Evidence discovery failed for {charity_name}: {e}")
            return EvidenceDiscovery(
                third_party_evaluated=False,
                evaluators=[],
                evaluation_evidence=None,
                confidence=0.0,
                source_count=0,
                cost_usd=0.0,
            )

    def _parse_response(
        self,
        result: SearchGroundingResult,
        charity_name: str,
    ) -> EvidenceDiscovery:
        """Parse Gemini response into EvidenceDiscovery."""
        # Log token count for debugging large responses
        if result.output_tokens > 1000:
            logger.warning(f"Large response for {charity_name}: {result.output_tokens} output tokens")

        # Use shared JSON extraction (handles markdown, truncation, etc.)
        json_str = extract_json_from_response(result.text)

        if not json_str:
            # If no search sources AND no JSON, this is expected "no data found"
            # Only error if we HAD sources but couldn't parse the response
            if result.source_count == 0:
                logger.info(f"No evaluations found for {charity_name} (0 search sources)")
                return EvidenceDiscovery(
                    third_party_evaluated=False,
                    evaluators=[],
                    evaluation_evidence=None,
                    confidence=0.0,
                    source_count=0,
                    cost_usd=result.cost_usd,
                    error=None,  # Not an error - just no data found
                )
            else:
                error_msg = f"No JSON found in evidence response for {charity_name} ({result.source_count} sources)"
                logger.error(error_msg)
                logger.debug(f"Raw response (first 500 chars): {result.text[:500]}")
                return EvidenceDiscovery(
                    third_party_evaluated=False,
                    evaluators=[],
                    evaluation_evidence=None,
                    confidence=0.0,
                    source_count=result.source_count,
                    cost_usd=result.cost_usd,
                    error=error_msg,
                )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse evidence response JSON for {charity_name}: {e}"
            logger.error(error_msg)
            logger.debug(f"Extracted JSON (first 500 chars): {json_str[:500]}")
            return EvidenceDiscovery(
                third_party_evaluated=False,
                evaluators=[],
                evaluation_evidence=None,
                confidence=0.0,
                source_count=result.source_count,
                cost_usd=result.cost_usd,
                error=error_msg,
            )

        # Extract fields
        third_party_evaluated = data.get("third_party_evaluated", False)
        evaluators = data.get("evaluators", [])
        evidence = data.get("evidence")

        # Use shared confidence calculation
        confidence = calculate_grounding_confidence(result)

        return EvidenceDiscovery(
            third_party_evaluated=third_party_evaluated,
            evaluators=evaluators,
            evaluation_evidence=evidence,
            confidence=confidence,
            source_count=result.source_count,
            cost_usd=result.cost_usd,
        )


def discover_evidence(
    charity_name: str,
    website_url: Optional[str] = None,
) -> EvidenceDiscovery:
    """Quick evidence discovery for a charity."""
    service = EvidenceDiscoveryService()
    return service.discover(charity_name, website_url)

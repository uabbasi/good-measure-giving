"""
Outcome Discovery Service using Gemini Search Grounding.

Discovers reported outcomes and impact metrics for charities,
including beneficiary numbers, meals distributed, students educated, etc.
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
from ..schemas.discovery import OutcomesDict

logger = logging.getLogger(__name__)


@dataclass
class OutcomeDiscovery:
    """Result of outcome/impact metrics discovery."""

    has_reported_outcomes: bool
    discovered_metrics: list[dict] = field(default_factory=list)  # [{metric, value, year}]
    outcome_evidence: Optional[str] = None
    confidence: float = 0.0
    source_count: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None  # Set when JSON parsing fails

    def to_dict(self) -> OutcomesDict:
        """Convert to dictionary for storage."""
        return {
            "has_reported_outcomes": self.has_reported_outcomes,
            "metrics": self.discovered_metrics,
            "evidence": self.outcome_evidence,
            "confidence": self.confidence,
        }


OUTCOME_DISCOVERY_PROMPT = """You are discovering reported outcomes and impact metrics for a charity.

Impact metrics include:
- Beneficiary numbers (people served, families helped)
- Service outputs (meals distributed, medical treatments provided)
- Educational outcomes (students educated, schools built)
- Financial metrics (grants distributed, microloans issued)
- Geographic reach (countries served, communities reached)

Based on your search results, answer these questions about {charity_name}:

1. Does this charity report outcomes or impact metrics? (true/false)
2. List specific metrics with values and years if available
3. What evidence describes their impact?

IMPORTANT: You MUST respond with valid JSON only. No other text before or after the JSON.

If outcomes are found:
{{
    "has_outcomes": true,
    "metrics": [
        {{"metric": "beneficiaries served", "value": 1200000, "year": 2023}},
        {{"metric": "meals distributed", "value": 5000000, "year": 2023}}
    ],
    "evidence": "Quote describing their reported outcomes"
}}

If NO outcomes or metrics are found, respond with exactly:
{{
    "has_outcomes": false,
    "metrics": [],
    "evidence": null
}}

Only include metrics with specific numbers. Always respond with valid JSON."""


class OutcomeDiscoveryService:
    """
    Service to discover impact metrics using Gemini Search Grounding.

    Example:
        service = OutcomeDiscoveryService()
        result = service.discover("Islamic Relief USA", "https://irusa.org")
        print(result.has_reported_outcomes)  # True
        print(result.discovered_metrics)  # [{metric: "beneficiaries", value: 1200000}]
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        """Initialize with Gemini search client."""
        self.client = GeminiSearchClient(model=model)
        self.model = model

    def discover(
        self,
        charity_name: str,
        website_url: Optional[str] = None,
    ) -> OutcomeDiscovery:
        """
        Discover reported outcomes for a charity.

        Args:
            charity_name: Name of the charity
            website_url: Optional website URL for context

        Returns:
            OutcomeDiscovery with metrics and evidence
        """
        # Build the search query
        query = f'What are "{charity_name}"\'s reported outcomes, impact metrics, and beneficiary numbers for the past 3 years? Include specific numbers like people served, meals distributed, students educated, etc.'
        if website_url:
            domain = urlparse(website_url).netloc
            query = f'What are "{charity_name}"\'s ({domain}) reported outcomes, impact metrics, and beneficiary numbers for the past 3 years? Include specific numbers like people served, meals distributed, students educated, etc.'

        logger.info(f"Discovering outcomes for: {charity_name}")

        try:
            system_prompt = OUTCOME_DISCOVERY_PROMPT.format(charity_name=charity_name)
            result: SearchGroundingResult = self.client.search(
                query=query,
                system_prompt=system_prompt,
                temperature=0.1,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )

            discovery = self._parse_response(result, charity_name)

            logger.info(
                f"Outcome discovery for {charity_name}: "
                f"has_outcomes={discovery.has_reported_outcomes}, "
                f"metrics={len(discovery.discovered_metrics)}, "
                f"cost=${discovery.cost_usd:.4f}"
            )

            return discovery

        except Exception as e:
            error_msg = f"Outcome discovery failed for {charity_name}: {e}"
            logger.error(error_msg)
            return OutcomeDiscovery(
                has_reported_outcomes=False,
                discovered_metrics=[],
                outcome_evidence=None,
                confidence=0.0,
                source_count=0,
                cost_usd=0.0,
                error=error_msg,
            )

    def _parse_response(
        self,
        result: SearchGroundingResult,
        charity_name: str,
    ) -> OutcomeDiscovery:
        """Parse Gemini response into OutcomeDiscovery."""
        # Use shared JSON extraction (handles markdown, truncation, etc.)
        json_str = extract_json_from_response(result.text)

        if not json_str:
            # If no search sources AND no JSON, this is expected "no data found"
            # Only error if we HAD sources but couldn't parse the response
            if result.source_count == 0:
                logger.info(f"No outcomes found for {charity_name} (0 search sources)")
                return OutcomeDiscovery(
                    has_reported_outcomes=False,
                    discovered_metrics=[],
                    outcome_evidence=None,
                    confidence=0.0,
                    source_count=0,
                    cost_usd=result.cost_usd,
                    error=None,  # Not an error - just no data found
                )
            else:
                error_msg = f"No JSON found in outcome response for {charity_name} ({result.source_count} sources)"
                logger.error(error_msg)
                logger.debug(f"Raw response (first 500 chars): {result.text[:500]}")
                return OutcomeDiscovery(
                    has_reported_outcomes=False,
                    discovered_metrics=[],
                    outcome_evidence=None,
                    confidence=0.0,
                    source_count=result.source_count,
                    cost_usd=result.cost_usd,
                    error=error_msg,
                )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse outcome response JSON for {charity_name}: {e}"
            logger.error(error_msg)
            logger.debug(f"Extracted JSON (first 500 chars): {json_str[:500]}")
            return OutcomeDiscovery(
                has_reported_outcomes=False,
                discovered_metrics=[],
                outcome_evidence=None,
                confidence=0.0,
                source_count=result.source_count,
                cost_usd=result.cost_usd,
                error=error_msg,
            )

        # Extract fields
        has_outcomes = data.get("has_outcomes", False)
        metrics = data.get("metrics", [])
        evidence = data.get("evidence")

        # Use shared confidence calculation
        confidence = calculate_grounding_confidence(result)

        return OutcomeDiscovery(
            has_reported_outcomes=has_outcomes,
            discovered_metrics=metrics,
            outcome_evidence=evidence,
            confidence=confidence,
            source_count=result.source_count,
            cost_usd=result.cost_usd,
        )


def discover_outcomes(
    charity_name: str,
    website_url: Optional[str] = None,
) -> OutcomeDiscovery:
    """Quick outcome discovery for a charity."""
    service = OutcomeDiscoveryService()
    return service.discover(charity_name, website_url)

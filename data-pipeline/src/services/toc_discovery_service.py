"""
Theory of Change Discovery Service using Gemini Search Grounding.

Discovers whether a charity has a published theory of change,
logic model, impact framework, or documented approach to measuring change.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from ..agents.gemini_search import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    GeminiSearchClient,
    SearchGroundingResult,
    calculate_grounding_confidence,
    extract_json_from_response,
)
from ..schemas.discovery import TheoryOfChangeDict

logger = logging.getLogger(__name__)


@dataclass
class TheoryOfChangeDiscovery:
    """Result of theory of change discovery."""

    has_theory_of_change: bool
    theory_of_change_url: Optional[str] = None
    theory_of_change_type: Optional[str] = None  # "theory_of_change", "logic_model", "impact_framework"
    toc_evidence: Optional[str] = None
    confidence: float = 0.0
    source_count: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None  # Set when JSON parsing fails

    def to_dict(self) -> TheoryOfChangeDict:
        """Convert to dictionary for storage."""
        return {
            "has_theory_of_change": self.has_theory_of_change,
            "url": self.theory_of_change_url,
            "type": self.theory_of_change_type,
            "evidence": self.toc_evidence,
            "confidence": self.confidence,
        }


TOC_DISCOVERY_PROMPT = """You are discovering whether a charity has a published theory of change or similar strategic framework.

Look for:
- Theory of Change (ToC) - explicit document explaining how activities lead to impact
- Logic Model - visual/textual representation of inputs -> activities -> outputs -> outcomes
- Impact Framework - structured approach to measuring and tracking impact
- Results Framework - similar to logic model with measurable indicators
- Program Strategy documents - detailed plans linking activities to goals

Based on your search results, answer these questions about {charity_name}:

1. Does this charity have a published theory of change or similar framework? (true/false)
2. What is the URL where it can be found? (if available)
3. What type is it? (theory_of_change, logic_model, impact_framework, results_framework)
4. What evidence describes their approach?

IMPORTANT: You MUST respond with valid JSON only. No other text before or after the JSON.

If a theory of change or framework is found:
{{
    "has_theory_of_change": true,
    "toc_url": "https://example.org/our-impact/theory-of-change",
    "toc_type": "logic_model or theory_of_change or impact_framework",
    "evidence": "Description of their strategic framework"
}}

If NO theory of change or framework is found, respond with exactly:
{{
    "has_theory_of_change": false,
    "toc_url": null,
    "toc_type": null,
    "evidence": null
}}

Only return has_theory_of_change=true if there is explicit evidence of a documented framework. Always respond with valid JSON."""


class TheoryOfChangeDiscoveryService:
    """
    Service to discover theory of change using Gemini Search Grounding.

    Example:
        service = TheoryOfChangeDiscoveryService()
        result = service.discover("GiveDirectly", "https://givedirectly.org")
        print(result.has_theory_of_change)  # True
        print(result.theory_of_change_type)  # "theory_of_change"
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        """Initialize with Gemini search client."""
        self.client = GeminiSearchClient(model=model)
        self.model = model

    def discover(
        self,
        charity_name: str,
        website_url: Optional[str] = None,
    ) -> TheoryOfChangeDiscovery:
        """
        Discover theory of change for a charity.

        Args:
            charity_name: Name of the charity
            website_url: Optional website URL for context

        Returns:
            TheoryOfChangeDiscovery with framework details
        """
        # Build the search query
        query = f'Does "{charity_name}" have a published theory of change, logic model, impact framework, or documented approach to measuring change? Look for strategic documents explaining how their programs create impact.'
        if website_url:
            domain = urlparse(website_url).netloc
            query = f'Does "{charity_name}" ({domain}) have a published theory of change, logic model, impact framework, or documented approach to measuring change? Look for strategic documents explaining how their programs create impact.'

        logger.info(f"Discovering theory of change for: {charity_name}")

        try:
            system_prompt = TOC_DISCOVERY_PROMPT.format(charity_name=charity_name)
            result: SearchGroundingResult = self.client.search(
                query=query,
                system_prompt=system_prompt,
                temperature=0.1,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )

            discovery = self._parse_response(result, charity_name)

            logger.info(
                f"ToC discovery for {charity_name}: "
                f"has_toc={discovery.has_theory_of_change}, "
                f"type={discovery.theory_of_change_type}, "
                f"cost=${discovery.cost_usd:.4f}"
            )

            return discovery

        except Exception as e:
            error_msg = f"ToC discovery failed for {charity_name}: {e}"
            logger.error(error_msg)
            return TheoryOfChangeDiscovery(
                has_theory_of_change=False,
                theory_of_change_url=None,
                theory_of_change_type=None,
                toc_evidence=None,
                confidence=0.0,
                source_count=0,
                cost_usd=0.0,
                error=error_msg,
            )

    def _parse_response(
        self,
        result: SearchGroundingResult,
        charity_name: str,
    ) -> TheoryOfChangeDiscovery:
        """Parse Gemini response into TheoryOfChangeDiscovery."""
        # Use shared JSON extraction (handles markdown, truncation, etc.)
        json_str = extract_json_from_response(result.text)

        if not json_str:
            # If no search sources AND no JSON, this is expected "no data found"
            # Only error if we HAD sources but couldn't parse the response
            if result.source_count == 0:
                logger.info(f"No ToC found for {charity_name} (0 search sources)")
                return TheoryOfChangeDiscovery(
                    has_theory_of_change=False,
                    theory_of_change_url=None,
                    theory_of_change_type=None,
                    toc_evidence=None,
                    confidence=0.0,
                    source_count=0,
                    cost_usd=result.cost_usd,
                    error=None,  # Not an error - just no data found
                )
            else:
                error_msg = f"No JSON found in ToC response for {charity_name} ({result.source_count} sources)"
                logger.error(error_msg)
                logger.debug(f"Raw response (first 500 chars): {result.text[:500]}")
                return TheoryOfChangeDiscovery(
                    has_theory_of_change=False,
                    theory_of_change_url=None,
                    theory_of_change_type=None,
                    toc_evidence=None,
                    confidence=0.0,
                    source_count=result.source_count,
                    cost_usd=result.cost_usd,
                    error=error_msg,
                )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse ToC response JSON for {charity_name}: {e}"
            logger.error(error_msg)
            logger.debug(f"Extracted JSON (first 500 chars): {json_str[:500]}")
            return TheoryOfChangeDiscovery(
                has_theory_of_change=False,
                theory_of_change_url=None,
                theory_of_change_type=None,
                toc_evidence=None,
                confidence=0.0,
                source_count=result.source_count,
                cost_usd=result.cost_usd,
                error=error_msg,
            )

        # Extract fields
        has_toc = data.get("has_theory_of_change", False)
        toc_url = data.get("toc_url")
        toc_type = data.get("toc_type")
        evidence = data.get("evidence")

        # Use shared confidence calculation
        confidence = calculate_grounding_confidence(result)

        # Reject phantom claims: LLM says has_toc=True but provides no evidence
        if has_toc and not toc_url and not evidence and confidence == 0:
            logger.warning(
                f"Rejecting phantom ToC claim for {charity_name}: has_toc=True but no URL, no evidence, confidence=0"
            )
            has_toc = False

        return TheoryOfChangeDiscovery(
            has_theory_of_change=has_toc,
            theory_of_change_url=toc_url,
            theory_of_change_type=toc_type,
            toc_evidence=evidence,
            confidence=confidence,
            source_count=result.source_count,
            cost_usd=result.cost_usd,
        )


def discover_theory_of_change(
    charity_name: str,
    website_url: Optional[str] = None,
) -> TheoryOfChangeDiscovery:
    """Quick theory of change discovery for a charity."""
    service = TheoryOfChangeDiscoveryService()
    return service.discover(charity_name, website_url)

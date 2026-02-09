"""
Zakat Verification Service using Gemini Search Grounding.

Uses Google Search to verify whether a charity accepts zakat donations,
extracting evidence and source URLs directly from search results.

This replaces the brittle page-crawling approach with a single search query.

IMPORTANT: Also performs direct URL check for /zakat pages as a fallback,
since LLM search can be non-deterministic and miss obvious evidence.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

from ..agents.gemini_search import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    GeminiSearchClient,
    SearchGroundingResult,
)
from ..schemas.discovery import ZakatDict

logger = logging.getLogger(__name__)

# Common zakat page URL patterns to check directly
# Order matters - check dedicated zakat pages first, then general donate pages
ZAKAT_URL_PATTERNS = [
    "/zakat",
    "/zakat/",
    "/donate/zakat",
    "/giving/zakat",
    "/zakaat",
    "/zakaat/",
    "/donate",  # Many charities mention zakat on general donate page
    "/donate/",
    "/ways-to-give",
    "/ways-to-give/",
]

# Keywords that indicate a page is about accepting zakat
ZAKAT_PAGE_KEYWORDS = [
    "zakat eligible",
    "zakat-eligible",
    "give zakat",
    "donate zakat",
    "pay zakat",
    "your zakat",
    "accept zakat",
    "accepts zakat",
    "zakat donation",
    "zakat fund",
]


@dataclass
class ZakatVerification:
    """Result of zakat eligibility verification."""

    accepts_zakat: bool
    accepts_zakat_evidence: Optional[str]
    accepts_zakat_url: Optional[str]
    zakat_categories_served: list[str]
    confidence: float  # 0-1 based on grounding support
    source_count: int
    cost_usd: float
    direct_page_verified: bool = False  # True if verified via direct HTTP check (not LLM)

    def to_dict(self) -> ZakatDict:
        """Convert to dictionary for storage."""
        return {
            "accepts_zakat": self.accepts_zakat,
            "accepts_zakat_evidence": self.accepts_zakat_evidence,
            "accepts_zakat_url": self.accepts_zakat_url,
            "zakat_categories_served": self.zakat_categories_served,
            "zakat_verification_confidence": self.confidence,
            "zakat_verification_sources": self.source_count,
            "direct_page_verified": self.direct_page_verified,
        }


ZAKAT_VERIFICATION_PROMPT = """You are verifying whether a US-based charity accepts zakat donations.

Zakat is the Islamic obligatory charity. Charities that accept zakat typically:
- Explicitly mention "zakat" on their website or donation pages
- Have dedicated zakat funds or campaigns
- Serve zakat-eligible recipients (the 8 asnaf categories)

IMPORTANT REQUIREMENTS:
1. Only consider evidence from the SPECIFIC US organization being evaluated
2. International affiliates or parent organizations are DIFFERENT entities
3. If evidence is about an international branch (e.g., "MSF Switzerland", "UK branch"),
   this does NOT apply to the US organization
4. If evidence mentions other countries (Switzerland, UAE, UK), return accepts_zakat=false

NEGATIVE indicators that mean zakat is NOT accepted:
- "We do not accept zakat"
- "Not zakat compliant" or "not zakat eligible"
- No mention of zakat on donation pages
- Zakat only accepted by international affiliates, not the US organization

Based on your search results, answer these questions about {charity_name}:

1. Does THIS SPECIFIC US charity explicitly accept zakat donations? (true/false)
2. What evidence proves they accept OR reject zakat? (exact quote or description)
3. Which asnaf categories do they serve? (from: fuqara, masakin, amil, muallaf, riqab, gharimin, fisabilillah, ibn_sabil)

Respond in JSON format only:
{{
    "accepts_zakat": true or false,
    "evidence": "exact quote proving acceptance OR rejection, or null if not found",
    "categories": ["list", "of", "asnaf", "categories"] or []
}}

Be conservative - only return accepts_zakat=true if there is clear evidence the US organization explicitly accepts zakat.
Do not infer zakat acceptance from international affiliates or general Islamic charity work."""


class ZakatVerificationService:
    """
    Service to verify zakat eligibility using Gemini Search Grounding.

    Example:
        service = ZakatVerificationService()
        result = service.verify("Islamic Relief USA", "https://irusa.org")
        print(result.accepts_zakat)  # True
        print(result.accepts_zakat_evidence)  # "Give your Zakat..."
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        """Initialize with Gemini search client."""
        self.client = GeminiSearchClient(model=model)
        self.model = model

    def _check_zakat_page_directly(self, website_url: Optional[str]) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if the charity website has a dedicated zakat page.

        This is a deterministic fallback that doesn't rely on LLM interpretation.
        If a /zakat page exists and contains zakat keywords, the charity
        definitively accepts zakat.

        Returns:
            Tuple of (accepts_zakat, evidence, zakat_url)
        """
        if not website_url:
            return False, None, None

        # Normalize the base URL
        parsed = urlparse(website_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        for pattern in ZAKAT_URL_PATTERNS:
            zakat_url = urljoin(base_url, pattern)
            try:
                # D-003: Retry transient failures (connection errors, timeouts)
                response = None
                for attempt in range(2):  # Try twice
                    try:
                        response = requests.get(
                            zakat_url,
                            timeout=10,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; ZakatVerifier/1.0)"},
                            allow_redirects=True,
                        )
                        break  # Success, exit retry loop
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as retry_err:
                        if attempt == 0:
                            logger.debug(f"Transient error on {zakat_url}, retrying: {retry_err}")
                            continue
                        raise  # Re-raise on second failure

                if response is None:
                    continue  # All retries failed, try next pattern

                # Check if page exists and contains zakat keywords
                if response.status_code == 200:
                    content_lower = response.text.lower()

                    # Verify this is actually a zakat page (not a 404 soft-redirect)
                    for keyword in ZAKAT_PAGE_KEYWORDS:
                        if keyword in content_lower:
                            logger.info(f"Found zakat page at {zakat_url} with keyword '{keyword}'")
                            return True, f"Dedicated zakat page found at {zakat_url}", zakat_url

            except requests.RequestException as e:
                logger.debug(f"Failed to check {zakat_url}: {e}")
                continue

        return False, None, None

    def verify(
        self,
        charity_name: str,
        website_url: Optional[str] = None,
    ) -> ZakatVerification:
        """
        Verify whether a charity accepts zakat donations.

        Uses a two-stage approach:
        1. LLM-based search grounding (primary)
        2. Direct URL check for /zakat pages (fallback)

        The fallback catches cases where the LLM misses obvious evidence,
        which can happen due to non-deterministic search results.

        Args:
            charity_name: Name of the charity
            website_url: Optional website URL for context

        Returns:
            ZakatVerification with evidence and source URL
        """
        # Build the search query - search for charity name + zakat
        # The prompt instructs the LLM to only consider evidence from the US organization
        query = f'"{charity_name}" zakat donation'

        logger.info(f"Verifying zakat eligibility for: {charity_name}")

        llm_cost = 0.0
        verification = None

        try:
            # Stage 1: Perform search-grounded query
            system_prompt = ZAKAT_VERIFICATION_PROMPT.format(charity_name=charity_name)
            result: SearchGroundingResult = self.client.search(
                query=query,
                system_prompt=system_prompt,
                temperature=0.1,  # Low temperature for factual response
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )

            # Parse the JSON response
            verification = self._parse_response(result, charity_name, website_url)
            llm_cost = verification.cost_usd

            logger.info(
                f"Zakat verification (LLM) for {charity_name}: "
                f"accepts={verification.accepts_zakat}, "
                f"confidence={verification.confidence}, "
                f"sources={verification.source_count}"
            )

        except Exception as e:
            logger.error(f"Zakat verification (LLM) failed for {charity_name}: {e}")

        # Stage 2: Direct URL check
        # Run always when we have a website URL:
        # - If LLM said no/low confidence: fallback to find zakat page
        # - If LLM said yes: confirm and set direct_page_verified for corroboration
        should_check_directly = website_url is not None

        if should_check_directly:
            direct_accepts, direct_evidence, direct_url = self._check_zakat_page_directly(website_url)

            if direct_accepts:
                logger.info(f"Zakat verification (direct) for {charity_name}: Found zakat page at {direct_url}")

                # Override with direct evidence (higher confidence)
                return ZakatVerification(
                    accepts_zakat=True,
                    accepts_zakat_evidence=direct_evidence,
                    accepts_zakat_url=direct_url,
                    zakat_categories_served=verification.zakat_categories_served if verification else [],
                    confidence=0.95,  # Very high confidence for direct page check
                    source_count=1,
                    cost_usd=llm_cost,
                    direct_page_verified=True,  # Verified via direct HTTP check
                )

        # Return LLM result if we have one
        if verification:
            return verification

        # Return negative result if everything failed
        return ZakatVerification(
            accepts_zakat=False,
            accepts_zakat_evidence=None,
            accepts_zakat_url=None,
            zakat_categories_served=[],
            confidence=0.0,
            source_count=0,
            cost_usd=0.0,
            direct_page_verified=False,
        )

    def _parse_response(
        self,
        result: SearchGroundingResult,
        charity_name: str,
        website_url: Optional[str] = None,
    ) -> ZakatVerification:
        """Parse Gemini response into ZakatVerification.

        IMPORTANT: Only trusts zakat claims from the charity's own domain.
        Third-party claims (e.g., MSF UAE claiming zakat for all MSF entities)
        are rejected to prevent false positives.
        """
        # Extract charity's domain for validation
        # D-004: Removed redundant import (urlparse already imported at module level)
        charity_domain = None
        if website_url:
            parsed = urlparse(website_url)
            charity_domain = parsed.netloc.lower().replace("www.", "")

        # Extract JSON from response text
        text = result.text.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse zakat response JSON: {e}")
            logger.debug(f"Raw response: {result.text[:500]}")
            # D-005: Safer heuristic - require explicit "accepts_zakat": true pattern
            # to avoid misinterpreting negations like "does not accept zakat is true"
            import re

            accepts = bool(re.search(r'"accepts_zakat"\s*:\s*true', text.lower()))
            return ZakatVerification(
                accepts_zakat=accepts,
                accepts_zakat_evidence=None,
                accepts_zakat_url=None,
                zakat_categories_served=[],
                confidence=0.3,
                source_count=result.source_count,
                cost_usd=result.cost_usd,
            )

        # Extract fields
        accepts_zakat = data.get("accepts_zakat", False)
        evidence = data.get("evidence")
        categories = data.get("categories", [])

        # Get the best source URL from grounding metadata
        # CRITICAL: Only trust sources from the charity's own domain
        source_url = None
        source_from_charity_domain = False

        # Foreign country TLDs to reject for US charities
        # These often have different zakat policies than the US branch
        # Include two-part TLDs (.org.uk, .co.uk, .com.au) to avoid false negatives
        foreign_country_tlds = {
            ".uk",
            ".co.uk",
            ".org.uk",
            ".ca",
            ".au",
            ".com.au",
            ".org.au",
            ".nz",
            ".co.nz",
            ".org.nz",
            ".za",
            ".co.za",
            ".org.za",
            ".ae",
            ".pk",
            ".com.pk",
            ".org.pk",
            ".in",
            ".co.in",
            ".org.in",
            ".my",
            ".com.my",
            ".org.my",
            ".sg",
            ".com.sg",
            ".org.sg",
        }

        if result.grounding_metadata.grounding_chunks:
            for chunk in result.grounding_metadata.grounding_chunks:
                if chunk.uri and chunk.domain:
                    chunk_domain = chunk.domain.lower().replace("www.", "")

                    # GUARD: Reject foreign country TLD sources for US charities
                    # e.g., actionagainsthunger.org.uk should NOT count for US org
                    is_foreign_tld = any(chunk_domain.endswith(tld) for tld in foreign_country_tlds)
                    if is_foreign_tld:
                        logger.info(f"Rejecting zakat source from foreign TLD: {chunk_domain}")
                        continue

                    # Check if this source is from the charity's own domain
                    # Use exact match or subdomain match, not substring
                    if charity_domain:
                        is_exact_match = chunk_domain == charity_domain
                        is_subdomain = chunk_domain.endswith("." + charity_domain)
                        if is_exact_match or is_subdomain:
                            source_url = chunk.uri
                            source_from_charity_domain = True
                            break
            # Fall back to first source (but mark as third-party)
            if not source_url and result.grounding_metadata.grounding_chunks[0].uri:
                source_url = result.grounding_metadata.grounding_chunks[0].uri

        # Calculate confidence from evidence quality + grounding supports
        #
        # The Gemini grounding API often returns empty confidence_scores even
        # when grounding_supports exists, causing confidence to stay at 0.0.
        # This fix uses evidence-based confidence as the primary signal.
        confidence = 0.0

        # Try to get grounding confidence scores if available
        grounding_confidence = 0.0
        if result.grounding_metadata.grounding_supports:
            scores = []
            for support in result.grounding_metadata.grounding_supports:
                if support.confidence_scores:
                    scores.extend(support.confidence_scores)
            if scores:
                grounding_confidence = sum(scores) / len(scores)

        # Primary confidence: evidence-based assessment
        if accepts_zakat and evidence:
            # Boost if evidence came from charity's own domain (most reliable)
            if source_from_charity_domain:
                confidence = 0.8
            elif source_url:
                # Evidence from third-party site - lower confidence
                confidence = 0.5
            else:
                # No valid source URL (all rejected as foreign TLDs)
                # This is likely a foreign branch claiming zakat, not the US org
                logger.warning(f"Zakat claim found but no valid US source for {charity_name}")
                confidence = 0.3
                accepts_zakat = False  # Reject the claim
        elif result.has_grounding:
            # Has search results but no zakat claim found
            confidence = 0.3

        # Use grounding confidence if it's higher (rare but possible)
        confidence = max(confidence, grounding_confidence)

        # Log source domain info for transparency
        # The prompt instructs the LLM to only consider the specific US organization
        # and reject international affiliate claims
        if accepts_zakat:
            if source_from_charity_domain:
                logger.info(
                    f"Zakat verification for {charity_name}: evidence from charity's own domain ({charity_domain})"
                )
            else:
                logger.info(
                    f"Zakat verification for {charity_name}: evidence from search results (prompt filtered for US org)"
                )

        return ZakatVerification(
            accepts_zakat=accepts_zakat,
            accepts_zakat_evidence=evidence,
            accepts_zakat_url=source_url,
            zakat_categories_served=categories,
            confidence=confidence,
            source_count=result.source_count,
            cost_usd=result.cost_usd,
        )


# Convenience function for quick verification
def verify_zakat_eligibility(
    charity_name: str,
    website_url: Optional[str] = None,
) -> ZakatVerification:
    """
    Quick verification of zakat eligibility.

    Args:
        charity_name: Name of the charity
        website_url: Optional website URL

    Returns:
        ZakatVerification result
    """
    service = ZakatVerificationService()
    return service.verify(charity_name, website_url)

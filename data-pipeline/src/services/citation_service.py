"""
Citation Service - Build citation registry from agent discoveries.

Collects all available sources for a charity and creates a citation
registry that can be used to support claims in rich narratives.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..db.repository import AgentDiscoveryRepository, CharityRepository, RawDataRepository
from ..llm.schemas.rich_v2 import Citation, CitationStats, SourceType
from ..schemas.discovery import SECTION_ZAKAT
from ..utils.deep_link_resolver import upgrade_source_url

logger = logging.getLogger(__name__)

# URL path segments that indicate non-substantive pages (legal, admin, liturgical)
_JUNK_URL_PATTERNS = re.compile(
    r"/(privacy|terms[-_]?(of[-_]?service|of[-_]?use)?|legal|cookie[-_]?policy"
    r"|disclaimer|refund|return[-_]?policy|shipping"
    r"|prayer[-_]?time|salah|iqamah|jummah[-_]?time|prayer[-_]?schedule"
    r"|wire[-_]?transfer|check[-_]?instruction|gift[-_]?transfer"
    r"|job|career|employment|hiring|vacancy"
    r"|student[-_]?handbook|staff[-_]?directory"
    r"|wp[-_]?admin|login|checkout|cart"
    r"|gofundme\.com/terms|gofundme\.com/privacy"
    r"|vertexaisearch\.cloud\.google\.com|google\.com/search)",
    re.IGNORECASE,
)

_CURRENT_YEAR = datetime.now(timezone.utc).year


@dataclass
class CitationSource:
    """A potential citation source before assignment."""

    source_name: str
    source_url: Optional[str]
    source_type: SourceType
    claim_topic: str  # What topic this source can support (e.g., "financial", "rating", "impact")
    raw_content: Optional[str] = None
    confidence: float = 0.8
    access_date: str = field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())


class CitationRegistry:
    """Registry of all available citations for a charity."""

    def __init__(self):
        self.sources: list[CitationSource] = []
        self._assigned_citations: dict[str, Citation] = {}  # marker -> Citation
        self._next_id = 1

    def add_source(self, source: CitationSource) -> None:
        """Add a potential citation source."""
        self.sources.append(source)

    def assign_citation(self, claim: str, source_name: Optional[str] = None) -> str:
        """
        Assign a citation marker for a claim.

        Args:
            claim: The claim being made
            source_name: Optional specific source to use

        Returns:
            Citation marker like "[1]"
        """
        # Find matching source
        matching_source = None
        if source_name:
            for s in self.sources:
                if source_name.lower() in s.source_name.lower():
                    matching_source = s
                    break

        if not matching_source and self.sources:
            # Use first available source with highest confidence
            sorted_sources = sorted(self.sources, key=lambda s: s.confidence, reverse=True)
            matching_source = sorted_sources[0]

        if not matching_source:
            # Create a generic citation
            marker = f"[{self._next_id}]"
            self._assigned_citations[marker] = Citation(
                id=marker,
                claim=claim,
                source_name="Unknown",
                source_type=SourceType.WEBSITE,
                confidence=0.5,
            )
            self._next_id += 1
            return marker

        marker = f"[{self._next_id}]"
        self._assigned_citations[marker] = Citation(
            id=marker,
            claim=claim,
            source_name=matching_source.source_name,
            source_url=matching_source.source_url,
            source_type=matching_source.source_type,
            confidence=matching_source.confidence,
            access_date=matching_source.access_date,
        )
        self._next_id += 1
        return marker

    def get_all_citations(self) -> list[Citation]:
        """Get all assigned citations."""
        return list(self._assigned_citations.values())

    def get_citation_stats(self) -> CitationStats:
        """Calculate citation statistics."""
        citations = self.get_all_citations()
        by_type: dict[str, int] = {}
        unique_urls: set[str] = set()
        high_confidence = 0

        for c in citations:
            type_key = c.source_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            if c.source_url:
                unique_urls.add(c.source_url)
            if c.confidence >= 0.8:
                high_confidence += 1

        return CitationStats(
            total_count=len(citations),
            by_source_type=by_type,
            high_confidence_count=high_confidence,
            unique_sources=len(unique_urls),
        )

    def get_sources_for_prompt(self) -> str:
        """Format sources for inclusion in LLM prompt.

        Includes content snippets when available so the LLM can make
        informed citation choices instead of guessing from topic labels.
        """
        lines = ["Available sources for citations:"]
        for i, source in enumerate(self.sources, 1):
            url_part = f" ({source.source_url})" if source.source_url else ""
            line = f"  [{i}] {source.source_name}{url_part} - {source.claim_topic}"
            if source.raw_content:
                # Truncate snippet to keep prompt manageable
                snippet = source.raw_content[:200].replace("\n", " ").strip()
                line += f"\n      Content: {snippet}"
            lines.append(line)
        return "\n".join(lines)


class CitationService:
    """Service for building citation registries from stored data."""

    def __init__(self):
        self.raw_repo = RawDataRepository()
        self.discovery_repo = AgentDiscoveryRepository()
        self._charity_repo = CharityRepository()

    # Blocklist of sources known to be hostile/propaganda against Muslim charities
    # This list is shared across all discovery services
    BLOCKED_SOURCES = {
        # Israeli-linked propaganda organizations
        "ngo-monitor.org",
        "ngo-monitor",
        "ngo monitor",  # Text match
        "canarymission.org",
        "canary mission",
        "canarymission",
        "fdd.org",  # Foundation for Defense of Democracies
        "meforum.org",  # Middle East Forum
        "investigativeproject.org",  # IPT - Steve Emerson
        "theisraelproject.org",  # Defunct but archives exist
        # Anti-Muslim propaganda
        "jihadwatch.org",
        "clarionproject.org",
        "counterextremism.com",  # CEP - funded by problematic sources
        # Selective translation/framing
        "memri.org",
        # Broken URLs
        "guidestar.org",  # Candid rebranded, old URLs don't work
    }

    def build_registry(self, ein: str) -> CitationRegistry:
        """
        Build a citation registry from all available sources for a charity.

        Args:
            ein: Charity EIN

        Returns:
            CitationRegistry with all available sources
        """
        registry = CitationRegistry()

        # Normalize EIN for URL construction
        ein_clean = ein.replace("-", "")

        # Fetch charity name for PDF relevance filtering
        charity_record = self._charity_repo.get(ein)
        charity_name = (charity_record or {}).get("name", "")

        # Load from raw scraped data (structured sources)
        self._add_raw_data_sources(ein, ein_clean, registry, charity_name=charity_name)

        # Load from agent discoveries (excluding news - too unreliable for Muslim charities)
        self._add_agent_discoveries(ein, registry, include_news=False)
        self._canonicalize_registry_urls(registry)

        logger.info(f"Built citation registry for {ein}: {len(registry.sources)} sources")
        return registry

    @staticmethod
    def _canonicalize_registry_urls(registry: CitationRegistry) -> None:
        """Upgrade homepage-like source URLs to deeper links when same-domain evidence exists."""
        context = [
            {
                "source_name": source.source_name,
                "source_url": source.source_url,
                "claim": source.claim_topic,
            }
            for source in registry.sources
            if source.source_url
        ]

        for source in registry.sources:
            if not source.source_url:
                continue
            source.source_url = upgrade_source_url(
                source.source_url,
                source_name=source.source_name,
                claim=source.claim_topic,
                context=context,
            )

    def _add_raw_data_sources(
        self, ein: str, ein_clean: str, registry: CitationRegistry, charity_name: str = ""
    ) -> None:
        """Add sources from raw scraped data with proper deep links."""
        raw_data = self.raw_repo.get_for_charity(ein)

        for record in raw_data:
            if not record.get("success"):
                continue

            source = record.get("source", "").lower()
            parsed = record.get("parsed_json") or {}
            original_parsed = parsed  # Keep reference to original for page_extractions

            # Handle nested data structure
            nested_keys = {
                "propublica": "propublica_990",
                "charity_navigator": "cn_profile",
                "candid": "candid_profile",
                "website": "website_profile",
            }
            if source in nested_keys and nested_keys[source] in parsed:
                parsed = parsed[nested_keys[source]]

            if source == "propublica":
                # ProPublica Form 990 data - link to org page (filing-specific URLs are unreliable)
                # Default to previous year if tax_year not available (990s filed ~9 months after fiscal year end)
                default_tax_year = str(datetime.now(timezone.utc).year - 1)
                tax_year = parsed.get("tax_year") or default_tax_year
                filing_url = f"https://projects.propublica.org/nonprofits/organizations/{ein_clean}"

                registry.add_source(
                    CitationSource(
                        source_name=f"Form 990 ({tax_year})",
                        source_url=filing_url,
                        source_type=SourceType.FORM_990,
                        claim_topic="financial data, revenue, expenses, assets, compensation",
                        confidence=0.95,
                    )
                )

                # Also add direct PDF link if available
                pdf_url = parsed.get("pdf_url")
                if pdf_url:
                    registry.add_source(
                        CitationSource(
                            source_name=f"Form 990 PDF ({tax_year})",
                            source_url=pdf_url,
                            source_type=SourceType.FORM_990,
                            claim_topic="official IRS filing, schedules, detailed financials",
                            confidence=0.98,
                        )
                    )

            elif source == "charity_navigator":
                # Charity Navigator profile.
                # Only advertise rating claims when the profile is fully rated.
                cn_is_rated = parsed.get("cn_is_rated") is True
                claim_topic = (
                    "ratings, accountability, financial health"
                    if cn_is_rated
                    else "profile metadata and financial fields (do not claim CN rating score)"
                )
                registry.add_source(
                    CitationSource(
                        source_name="Charity Navigator",
                        source_url=f"https://www.charitynavigator.org/ein/{ein_clean}",
                        source_type=SourceType.RATING,
                        claim_topic=claim_topic,
                        confidence=0.9,
                    )
                )

            elif source == "candid":
                # Skip Candid - no reliable public URL format available
                # We still use the data but don't cite it with a link
                pass

            elif source == "website":
                # Charity's own website - use ONLY real URLs we actually crawled
                # Never construct URLs like /programs or /about-us that may not exist

                # parsed is already website_profile (from nested key handling above)
                website_profile = parsed
                base_url = (website_profile.get("url") or website_profile.get("website_url") or "").rstrip("/")

                # 0. Add real page URLs from page_extractions (new in this version)
                # Use URL patterns to determine what topics each page covers
                # page_extractions is at the original level, not inside website_profile
                page_extractions = original_parsed.get("page_extractions", [])
                seen_page_urls = set()
                for extraction in page_extractions:
                    page_url = extraction.get("url", "")
                    extracted_fields = extraction.get("extracted_fields", [])

                    # Skip if no LLM data was extracted (just basic regex fields)
                    if "llm_data" not in extracted_fields:
                        continue

                    # Skip homepage - we add it as fallback later
                    if page_url.rstrip("/") == base_url:
                        continue

                    # Avoid duplicates
                    if page_url in seen_page_urls:
                        continue
                    seen_page_urls.add(page_url)

                    # Skip non-substantive pages (legal, prayer schedules, admin)
                    if self._is_junk_url(page_url):
                        logger.debug(f"Skipping non-content URL for citations: {page_url}")
                        continue

                    # Use URL path to determine claim topic
                    url_lower = page_url.lower()

                    # Check URL patterns - order matters (more specific first)
                    # Only match if the pattern is a path segment, not part of a longer word
                    if any(x in url_lower for x in ["/impact/", "/our-impact", "/results/", "/outcomes/"]):
                        claim_topic = "impact data, beneficiary statistics, school counts, outcomes"
                        source_name = "Charity Website - Impact"
                    elif any(x in url_lower for x in ["/program", "/what-we-do", "/our-work", "/services/"]):
                        claim_topic = "programs, services, initiatives, beneficiaries"
                        source_name = "Charity Website - Programs"
                    elif any(x in url_lower for x in ["/about/", "/about-us", "/mission/", "/who-we-are", "/history/"]):
                        claim_topic = "mission, history, founding year, organizational overview"
                        source_name = "Charity Website - About"
                    elif any(x in url_lower for x in ["/financ", "/990", "/annual-report", "/transparency/"]):
                        claim_topic = "financials, transparency, annual reports, Form 990"
                        source_name = "Charity Website - Financials"
                    elif any(x in url_lower for x in ["/zakat/", "/zakat-", "/sadaqah/"]):
                        # Only match specific zakat paths, not news articles with "islamic" in URL
                        claim_topic = "zakat eligibility, zakat policy, Islamic giving"
                        source_name = "Charity Website - Zakat"
                    elif any(x in url_lower for x in ["/leadership/", "/team/", "/board/", "/staff/"]):
                        claim_topic = "leadership, board, team, governance"
                        source_name = "Charity Website - Leadership"
                    elif any(x in url_lower for x in ["/donate/", "/donate-", "/give/", "/support/"]):
                        claim_topic = "donation options, giving methods, support"
                        source_name = "Charity Website - Donate"
                    else:
                        # Skip pages that don't match known patterns
                        continue

                    registry.add_source(
                        CitationSource(
                            source_name=source_name,
                            source_url=page_url,
                            source_type=SourceType.WEBSITE,
                            claim_topic=claim_topic,
                            confidence=0.88,  # Higher than homepage since we know data came from here
                        )
                    )

                # 1. Add real PDF URLs from outcomes_data (these are actual crawled/downloaded PDFs)
                outcomes_data = website_profile.get("outcomes_data", [])
                for outcome in outcomes_data:
                    pdf_url = outcome.get("source_url")
                    if pdf_url and self._is_relevant_pdf(outcome, charity_name):
                        # Skip non-content URLs (legal docs, prayer schedules, admin forms)
                        if self._is_junk_url(pdf_url):
                            logger.debug(f"Skipping non-content PDF URL: {pdf_url}")
                            continue

                        pdf_type = outcome.get("type", "document")
                        anchor_text = outcome.get("anchor_text", "")
                        fiscal_year = outcome.get("fiscal_year")

                        # Drop future-dated fiscal years (LLM hallucination in anchor text)
                        if self._is_future_fiscal_year(fiscal_year):
                            logger.debug(f"Dropping future fiscal year {fiscal_year} for {pdf_url}")
                            fiscal_year = None

                        # Determine claim topic based on PDF type and content
                        if pdf_type == "annual_report":
                            claim_topic = "annual outcomes, programs, financials, beneficiary statistics"
                            source_name = f"Annual Report{f' ({fiscal_year})' if fiscal_year else ''}"
                        elif pdf_type == "form_990" or "990" in anchor_text.lower():
                            claim_topic = "IRS Form 990, revenue, expenses, compensation, financials"
                            source_name = f"Form 990{f' ({fiscal_year})' if fiscal_year else ''}"
                        elif pdf_type == "financial_statement":
                            claim_topic = "audited financials, revenue, expenses, assets"
                            source_name = f"Financial Statement{f' ({fiscal_year})' if fiscal_year else ''}"
                        elif pdf_type == "impact_report":
                            claim_topic = "impact data, outcomes, beneficiary counts, program results"
                            source_name = f"Impact Report{f' ({fiscal_year})' if fiscal_year else ''}"
                        else:
                            claim_topic = "organizational data, programs, outcomes"
                            source_name = anchor_text or "Document (PDF)"

                        # Build content snippet from extracted data
                        snippet = self._build_pdf_snippet(outcome)

                        registry.add_source(
                            CitationSource(
                                source_name=source_name,
                                source_url=pdf_url,
                                source_type=SourceType.FORM_990 if "990" in pdf_type else SourceType.WEBSITE,
                                claim_topic=claim_topic,
                                raw_content=snippet,
                                confidence=0.92,
                            )
                        )

                # 2. Add real PDF URLs from llm_extracted_pdfs
                llm_pdfs = website_profile.get("llm_extracted_pdfs", [])
                seen_urls = {o.get("source_url") for o in outcomes_data}  # Avoid duplicates
                for pdf in llm_pdfs:
                    pdf_url = pdf.get("source_url")
                    extracted = pdf.get("extracted_data", {})
                    if pdf_url and pdf_url not in seen_urls and self._is_relevant_pdf(extracted, charity_name):
                        if self._is_junk_url(pdf_url):
                            logger.debug(f"Skipping non-content PDF URL: {pdf_url}")
                            continue

                        pdf_type = pdf.get("pdf_type", "document")

                        # Use extracted org name or fiscal year for better naming
                        fiscal_year = extracted.get("governance", {}).get("fiscal_year")
                        if self._is_future_fiscal_year(fiscal_year):
                            fiscal_year = None

                        claim_topic = "organizational data, programs, financials"
                        source_name = f"PDF Document{f' ({fiscal_year})' if fiscal_year else ''}"

                        registry.add_source(
                            CitationSource(
                                source_name=source_name,
                                source_url=pdf_url,
                                source_type=SourceType.WEBSITE,
                                claim_topic=claim_topic,
                                confidence=0.88,
                            )
                        )
                        seen_urls.add(pdf_url)

                # 3. Add real page URLs we actually have stored (not constructed)
                # Only add URLs that were explicitly extracted and stored

                # Donate page - real URL
                donate_url = website_profile.get("donate_url") or website_profile.get("donation_page_url")
                if donate_url:
                    registry.add_source(
                        CitationSource(
                            source_name="Charity Website - Donate",
                            source_url=donate_url,
                            source_type=SourceType.WEBSITE,
                            claim_topic="donation options, giving methods",
                            confidence=0.85,
                        )
                    )

                # Note: Zakat URL now comes from discovered source, not website

                # Volunteer page - real URL if stored
                volunteer_url = website_profile.get("volunteer_page_url")
                if volunteer_url:
                    registry.add_source(
                        CitationSource(
                            source_name="Charity Website - Volunteer",
                            source_url=volunteer_url,
                            source_type=SourceType.WEBSITE,
                            claim_topic="volunteer opportunities, engagement",
                            confidence=0.85,
                        )
                    )

                # Annual report URL - real URL if stored
                annual_report = website_profile.get("annual_report_url")
                if annual_report:
                    registry.add_source(
                        CitationSource(
                            source_name="Annual Report",
                            source_url=annual_report,
                            source_type=SourceType.WEBSITE,
                            claim_topic="annual outcomes, financials, program highlights",
                            confidence=0.9,
                        )
                    )

                # Skip homepage - only use specific page URLs for citations
                # General claims should cite the specific page where info was found

            elif source == "givewell":
                # GiveWell evaluation
                registry.add_source(
                    CitationSource(
                        source_name="GiveWell",
                        source_url="https://www.givewell.org/",
                        source_type=SourceType.EVALUATION,
                        claim_topic="cost-effectiveness, impact evidence",
                        confidence=0.95,
                    )
                )

            elif source == "discovered":
                # Discovered data from web search verification (zakat, etc.)
                discovered_profile = parsed.get("discovered_profile", parsed)
                zakat_data = discovered_profile.get(SECTION_ZAKAT, {})

                # Zakat page URL from web search verification
                zakat_url = zakat_data.get("accepts_zakat_url")
                if zakat_url and zakat_data.get("accepts_zakat") and not self._is_junk_url(zakat_url):
                    registry.add_source(
                        CitationSource(
                            source_name="Charity Website - Zakat",
                            source_url=zakat_url,
                            source_type=SourceType.WEBSITE,
                            claim_topic="zakat eligibility, zakat policy, asnaf categories",
                            confidence=0.85,
                        )
                    )

    @staticmethod
    def _build_pdf_snippet(pdf_data: dict) -> str | None:
        """Build a brief content snippet from extracted PDF data."""
        parts = []
        org = pdf_data.get("organization_name")
        if org:
            parts.append(f"Org: {org}")

        outcomes = pdf_data.get("outcomes", {})
        key_outcomes = outcomes.get("key_outcomes", [])
        if key_outcomes:
            metrics = [o.get("metric", "") for o in key_outcomes[:3] if o.get("metric")]
            if metrics:
                parts.append(f"Metrics: {'; '.join(metrics)}")

        return ". ".join(parts) if parts else None

    @staticmethod
    def _is_junk_url(url: str) -> bool:
        """Return True if URL points to a non-substantive page (legal, admin, liturgical)."""
        return bool(_JUNK_URL_PATTERNS.search(url))

    @staticmethod
    def _is_future_fiscal_year(fiscal_year: str | int | None) -> bool:
        """Return True if fiscal_year is in the future."""
        if fiscal_year is None:
            return False
        try:
            return int(fiscal_year) > _CURRENT_YEAR
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _is_relevant_pdf(pdf_data: dict, charity_name: str) -> bool:
        """Check if a PDF belongs to the charity (not an unrelated third-party document).

        PDFs linked from a charity's website may be external reports, government
        documents, or research papers. We filter these by checking if the extracted
        organization_name matches the charity.
        """
        if not charity_name:
            return True  # Can't filter without a name

        pdf_org = pdf_data.get("organization_name", "")
        if not pdf_org:
            return True  # No org name extracted — keep it

        # Normalize for comparison
        charity_lower = charity_name.lower()
        pdf_org_lower = pdf_org.lower()

        # Check if either name contains the other (handles abbreviations)
        if charity_lower in pdf_org_lower or pdf_org_lower in charity_lower:
            return True

        # Check word overlap — at least 2 significant words in common
        stop_words = {"the", "of", "for", "and", "a", "an", "inc", "usa", "us", "foundation", "organization"}
        charity_words = {w for w in charity_lower.split() if w not in stop_words and len(w) > 2}
        pdf_words = {w for w in pdf_org_lower.split() if w not in stop_words and len(w) > 2}
        overlap = charity_words & pdf_words
        if len(overlap) >= 1:
            return True

        logger.debug(f"Filtering PDF: org '{pdf_org}' doesn't match charity '{charity_name}'")
        return False

    def _is_blocked_source(self, source_name: str, source_url: Optional[str]) -> bool:
        """Check if source is in the blocklist of hostile/propaganda sources."""
        check_str = f"{source_name} {source_url or ''}".lower()
        return any(blocked in check_str for blocked in self.BLOCKED_SOURCES)

    def _add_agent_discoveries(self, ein: str, registry: CitationRegistry, include_news: bool = False) -> None:
        """Add sources from agent discoveries.

        Args:
            ein: Charity EIN
            registry: Citation registry to add to
            include_news: If False (default), skip news/reputation sources.
                          News sources are unreliable for Muslim charities due to
                          widespread hostile propaganda from certain outlets.
        """
        discoveries = self.discovery_repo.get_for_charity(ein)

        for d in discoveries:
            agent_type = d.get("agent_type", "").lower()
            source_name = d.get("source_name", "Unknown")
            source_url = d.get("source_url")
            confidence = d.get("confidence", 0.7)
            parsed = d.get("parsed_data", {})

            # Skip blocked sources (hostile propaganda)
            if self._is_blocked_source(source_name, source_url):
                logger.debug(f"Skipping blocked source: {source_name}")
                continue

            # Determine source type and topic based on agent type
            if "rating" in agent_type:
                # Rating discovery
                rating_source = parsed.get("source_name", source_name)
                registry.add_source(
                    CitationSource(
                        source_name=rating_source,
                        source_url=source_url,
                        source_type=SourceType.RATING,
                        claim_topic="ratings, accreditation",
                        confidence=confidence,
                    )
                )

            elif "evidence" in agent_type:
                # Evidence discovery
                evidence_type = parsed.get("evidence_type", "evaluation")
                evaluator = parsed.get("evaluator", source_name)
                registry.add_source(
                    CitationSource(
                        source_name=evaluator,
                        source_url=source_url,
                        source_type=SourceType.EVALUATION if "eval" in evidence_type else SourceType.ACADEMIC,
                        claim_topic="impact evidence, outcomes",
                        confidence=confidence,
                    )
                )

            elif "reputation" in agent_type:
                # Skip news/reputation sources unless explicitly included
                if not include_news:
                    continue
                # Reputation/news discovery
                headline = parsed.get("headline") or ""
                sentiment = parsed.get("sentiment") or "neutral"
                headline_preview = headline[:50] if headline else "news coverage"
                registry.add_source(
                    CitationSource(
                        source_name=source_name,
                        source_url=source_url,
                        source_type=SourceType.NEWS,
                        claim_topic=f"reputation ({sentiment}): {headline_preview}",
                        confidence=confidence,
                    )
                )

            elif "profile" in agent_type:
                # Profile discovery
                registry.add_source(
                    CitationSource(
                        source_name=source_name,
                        source_url=source_url,
                        source_type=SourceType.WEBSITE,
                        claim_topic="organizational profile, programs",
                        confidence=confidence,
                    )
                )


def build_citation_registry(ein: str) -> CitationRegistry:
    """Convenience function to build citation registry for a charity."""
    service = CitationService()
    return service.build_registry(ein)

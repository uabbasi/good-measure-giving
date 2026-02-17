"""
Candid collector using pure BeautifulSoup (deterministic extraction).

This collector fetches Candid profile pages (formerly GuideStar) and extracts data using
deterministic HTML parsing instead of LLM-based extraction.

Note: GuideStar has rebranded to Candid. This collector works with Candid profile URLs.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from ..utils.logger import PipelineLogger
from ..utils.rate_limiter import global_rate_limiter
from ..validators.candid_validator import CandidProfile
from .base import BaseCollector, FetchResult, ParseResult


class CandidCollector(BaseCollector):
    """
    Collect Candid charity profile data using deterministic BeautifulSoup parsing.

    This collector fetches from Candid (formerly GuideStar) using either:
    1. Old GuideStar URLs (may stop working): www.guidestar.org/profile/{ein}
    2. New Candid URLs (preferred): app.candid.org/profile/{candid_id}/{slug}-{ein}
    """

    # No BASE_URL - we construct URLs dynamically based on available data

    # Candid placeholder patterns to detect and treat as null
    PLACEHOLDER_PATTERNS = [
        "This profile needs more info",
        "needs more info",
        "add a problem overview",
        "Login and update",
        "Claim your profile",
        "Learn about",
        # GuideStar UI text patterns (scraped instead of mission)
        "Find and check a charity",
        "Look up 501(c)(3) status",
        "search 990s",
        "GuideStar",
        "verify nonprofit information",
    ]

    def __init__(
        self,
        logger: Optional[PipelineLogger] = None,
        rate_limit_delay: float = 1.0,
        timeout: int = 30,
        save_debug_html: bool = False,
        debug_dir: Optional[str] = None,
    ):
        """
        Initialize Candid collector.

        Args:
            logger: Logger instance
            rate_limit_delay: Seconds to wait between requests (default 1.0)
            timeout: Request timeout in seconds
            save_debug_html: If True, save fetched HTML for debugging (default: False)
            debug_dir: Directory to save debug HTML files (default: ./candid_debug)
        """
        self.logger = logger
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time = 0
        self.save_debug_html = save_debug_html
        self.debug_dir = Path(debug_dir) if debug_dir else Path("./candid_debug")

        # Create debug directory if needed
        if self.save_debug_html:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

        # User agent to mimic browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

    @property
    def source_name(self) -> str:
        return "candid"

    @property
    def schema_key(self) -> str:
        return "candid_profile"

    def _rate_limit(self):
        """Enforce rate limiting (global, thread-safe)."""
        global_rate_limiter.wait("candid", self.rate_limit_delay)

    def _extract_organization_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract organization name from H1."""
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return None

    def _extract_ein(self, soup: BeautifulSoup, html: str) -> Optional[str]:
        """Extract EIN from page."""
        # Look for EIN pattern in HTML
        ein_pattern = r"(\d{2}-\d{7})"
        match = re.search(ein_pattern, html)
        if match:
            return match.group(1)
        return None

    def _is_placeholder(self, text: Optional[str]) -> bool:
        """Check if text contains Candid placeholder patterns."""
        if not text:
            return False
        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in self.PLACEHOLDER_PATTERNS)

    def _extract_mission(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract mission statement from programs section."""
        # Mission is typically in the "What we aim to solve" section
        prog_section = soup.find(id="programsAndAreasServed")
        if prog_section:
            # Look for mission text after "What we aim to solve"
            text = prog_section.get_text(separator=" ", strip=True)

            # Extract mission after "[Organization Name] is working" or similar
            # Pattern: capitalized org name (1-5 words) followed by mission verbs
            mission_pattern = r"(?:[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,4})\s+(?:is working|provides|aims|seeks|works|strives)[^.]*\."
            match = re.search(mission_pattern, text)
            if match:
                mission = match.group(0)
                # Check if it's a placeholder
                if not self._is_placeholder(mission):
                    return mission

            # Fallback: get text between "What we aim to solve" and next section
            if "What we aim to solve" in text:
                parts = text.split("What we aim to solve", 1)
                if len(parts) > 1:
                    # Get first few sentences
                    mission_text = parts[1].split("Our programs")[0] if "Our programs" in parts[1] else parts[1]
                    mission_text = mission_text.split("SOURCE:")[0] if "SOURCE:" in mission_text else mission_text
                    # Clean up
                    mission_text = re.sub(r"\s+", " ", mission_text).strip()
                    if len(mission_text) > 50 and len(mission_text) < 1000:
                        # Check if it's a placeholder
                        if not self._is_placeholder(mission_text):
                            return mission_text[:500]  # Limit length

        # Try meta description as fallback
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            content = meta.get("content")
            # Check if it's a placeholder
            if not self._is_placeholder(content):
                return content

        # If we got here, either no mission found or all were placeholders
        return None

    def _extract_tagline(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract tagline from H4 element or meta description."""
        # First try to get from H4 tagline element (more accurate)
        tagline_elem = soup.find("h4", class_="profile-org-tagline")
        if tagline_elem:
            tagline = tagline_elem.get_text(strip=True)
            if tagline and len(tagline) > 5:
                return tagline

        # Fallback to meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            tagline = meta.get("content").strip()
            # Limit to reasonable length
            if len(tagline) > 250:
                tagline = tagline[:247] + "..."
            return tagline

        return None

    def _extract_programs(self, soup: BeautifulSoup) -> List[str]:
        """Extract list of programs."""
        programs = []

        # Look in programsList section
        programs_section = soup.find(id="programsList")
        if programs_section:
            # Find all headings (h3, h4, h5) as program titles
            headings = programs_section.find_all(["h3", "h4", "h5"])

            for heading in headings:
                program_text = heading.get_text(strip=True)
                # Skip section headers
                if program_text and len(program_text) > 5 and len(program_text) < 200:
                    if not program_text.startswith("Our programs"):
                        programs.append(program_text)

        # If no programs found, look for any list items in the programs section
        if not programs and programs_section:
            list_items = programs_section.find_all("li")
            for li in list_items:
                text = li.get_text(strip=True)
                if text and len(text) > 10 and len(text) < 200:
                    programs.append(text)

        return programs[:50]  # Limit to 50 programs (increased from 10)

    def _extract_outcomes(self, soup: BeautifulSoup) -> List[str]:
        """Extract outcomes/results."""
        outcomes = []

        # Look in ourResults section
        results_section = soup.find(id="ourResults")
        if results_section:
            # Find paragraphs or list items
            paragraphs = results_section.find_all(["p", "li"])
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20 and len(text) < 500:
                    # Skip headers
                    if not any(skip in text for skip in ["Our results", "SOURCE:", "How does this"]):
                        outcomes.append(text)

        return outcomes[:50]  # Limit to 50 outcomes (increased from 10)

    def _extract_populations_served(self, soup: BeautifulSoup) -> List[str]:
        """Extract populations served."""
        populations = []

        # Look for text mentioning populations
        prog_section = soup.find(id="programsAndAreasServed")
        if prog_section:
            text = prog_section.get_text(separator=" ", strip=True)

            # Common population keywords
            population_keywords = [
                "children",
                "women",
                "men",
                "families",
                "refugees",
                "immigrants",
                "elderly",
                "youth",
                "adults",
                "orphans",
                "victims",
                "survivors",
                "communities",
                "poor",
                "needy",
            ]

            for keyword in population_keywords:
                if keyword in text.lower():
                    populations.append(keyword.capitalize())

        return list(set(populations))[:50]  # Remove duplicates, limit to 50 (increased from 10)

    def _extract_candid_seal(self, soup: BeautifulSoup, html: str) -> Optional[str]:
        """
        Extract Candid transparency seal level.

        Returns platinum, gold, silver, bronze, or None if no seal.

        Detection methods (in priority order):
        1. Title attribute: "platinum-level GuideStar participant"
        2. Section ID: "PlatinumMetricsDisplay"

        NOTE: CSS classes (bb-gold, bkg-gold) are NOT used because they are
        default styling applied to all profiles, not indicators of actual seals.
        See Muslim Advocates audit (EIN 30-0298794) - had bb-gold CSS but no seal.
        """
        seal_levels = ["platinum", "gold", "silver", "bronze"]
        html_lower = html.lower()

        for level in seal_levels:
            # Method 1: Check title attribute pattern (most reliable)
            # e.g., title="This organization is a platinum-level GuideStar participant"
            if f"{level}-level guidestar participant" in html_lower:
                return level

            # Method 2: Check for MetricsDisplay section ID
            # e.g., id="PlatinumMetricsDisplay"
            if f"{level}metricsdisplay" in html_lower:
                return level

        # CSS classes (bb-gold, bkg-gold) deliberately NOT used - they are
        # default styling, not seal indicators. Previously caused false positives.

        return None

    def _extract_candid_url(self, html: str) -> Optional[str]:
        """
        Extract the Candid profile URL for user-facing links.

        The guidestar.org page contains JavaScript that redirects to app.candid.org.
        We extract the orgID to construct the proper user-facing URL.

        Pattern in HTML: const orgID = "8460202";
        Result: https://app.candid.org/profile/8460202
        """
        # Look for the orgID JavaScript variable
        match = re.search(r'const\s+orgID\s*=\s*["\'](\d+)["\']', html)
        if match:
            org_id = match.group(1)
            return f"https://app.candid.org/profile/{org_id}"
        return None

    def _extract_areas_served(self, soup: BeautifulSoup) -> List[str]:
        """Extract geographic areas served."""
        areas = []

        # Primary: Extract from "Where we work" list (most accurate)
        where_we_work = soup.find(id="whereWeWorkList")
        if where_we_work:
            items = where_we_work.find_all("li")
            for item in items:
                text = item.get_text(strip=True)
                if text and len(text) > 2:
                    areas.append(text)

        # Fallback: Look for geographic mentions in text
        if not areas:
            prog_section = soup.find(id="programsAndAreasServed")
            if prog_section:
                text = prog_section.get_text(separator=" ", strip=True)

                # Look for country/region names
                # Common patterns: "in [Country]", "across [Region]"
                location_pattern = r"\b(?:in|across|throughout)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
                matches = re.findall(location_pattern, text)
                areas.extend(matches)

                # Also check for "International" or "Domestic"
                if "international" in text.lower():
                    areas.append("International")
                if "domestic" in text.lower() or "USA" in text or "United States" in text:
                    areas.append("United States")

        return list(set(areas))[:50]  # Remove duplicates, limit to 50

    def _extract_ceo_info(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[float]]:
        """Extract CEO name and compensation."""
        ceo_name = None
        ceo_compensation = None

        # Look for "Chief Executive Officer" header in report sections
        headers = soup.find_all("p", class_="report-section-header")
        for header in headers:
            if "Chief Executive Officer" in header.get_text():
                next_p = header.find_next_sibling("p", class_="report-section-text")
                if next_p:
                    ceo_name = next_p.get_text(strip=True)
                    break

        # Compensation is not available on free profiles

        return ceo_name, ceo_compensation

    def _extract_board_info(self, soup: BeautifulSoup) -> Tuple[Optional[int], Optional[int]]:
        """Extract board size and independent members count."""
        board_size = None
        independent_board_members = None

        # Look for board section
        text = soup.get_text(separator=" ", strip=True)

        # Pattern: "Board of directors: X members" or similar
        board_pattern = r"Board of directors.*?(\d+)\s+members"
        match = re.search(board_pattern, text, re.IGNORECASE)
        if match:
            board_size = int(match.group(1))

        return board_size, independent_board_members

    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Extract contact information (address, phone, email, website)."""
        contact = {
            "address": None,
            "city": None,
            "state": None,
            "zip": None,
            "phone": None,
            "email": None,
            "website": None,
        }

        # Look for contact section or address patterns
        text = soup.get_text(separator="\n", strip=True)

        # Improved address pattern to handle "3655 Wheeler Ave Alexandria, VA 22304-6404"
        # Pattern: number + street name (greedy to get full street) + city, state zip
        address_pattern = r"(\d+\s+[A-Za-z\s.]+?)\s+([A-Z][a-z]+),\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)"
        match = re.search(address_pattern, text)
        if match:
            contact["address"] = match.group(1).strip()
            contact["city"] = match.group(2).strip()
            contact["state"] = match.group(3).strip()
            contact["zip"] = match.group(4).strip()

        # If not found, try alternative pattern (just city, state, zip)
        if not contact["city"]:
            city_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)"
            match = re.search(city_pattern, text)
            if match:
                contact["city"] = match.group(1).strip()
                contact["state"] = match.group(2).strip()
                contact["zip"] = match.group(3).strip()

        # Phone pattern
        phone_pattern = r"(\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4})"
        match = re.search(phone_pattern, text)
        if match:
            contact["phone"] = match.group(1)

        # Email pattern - exclude mailto: links
        email_pattern = r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b"
        match = re.search(email_pattern, text)
        if match:
            email = match.group(1)
            # Validate email doesn't contain HTML artifacts
            if "@" in email and "." in email and len(email) < 100:
                contact["email"] = email

        # Website - look for organization's actual website
        # First try to find it in the structured page (near organization name)
        for element in soup.find_all(string=re.compile(r"https?://(?!.*guidestar|.*candid)", re.I)):
            text_content = str(element).strip()
            url_match = re.search(r'https?://[^\s<>"]+', text_content)
            if url_match:
                url = url_match.group(0)
                # Skip social media
                if not any(
                    social in url.lower() for social in ["facebook", "twitter", "linkedin", "instagram", "youtube"]
                ):
                    # E-007: Accept any non-social URL as potential org website
                    contact["website"] = url
                    break

        # If not found, look in links
        if not contact["website"]:
            links = soup.find_all("a", href=True)
            for link in links:
                href = link.get("href", "")
                if href.startswith("http") and "guidestar" not in href.lower() and "candid" not in href.lower():
                    # Skip social media links
                    if not any(
                        social in href.lower() for social in ["facebook", "twitter", "linkedin", "instagram", "youtube"]
                    ):
                        contact["website"] = href
                        break

        return contact

    def _extract_metadata(self, soup: BeautifulSoup, html: str) -> Dict[str, Optional[Any]]:
        """Extract metadata (NTEE code, vision, strategic goals, etc.)."""
        metadata = {
            "ntee_code": None,
            "ntee_description": None,
            "vision": None,
            "strategic_goals": None,
            "goals_strategy_text": None,
            "ruling_year": None,
            "irs_filing_requirement": None,
            "logo_url": None,
        }

        # E-009: Removed dead code (unused get_text call)

        # Ruling year (IRS tax-exempt status grant year)
        # Find all report section headers and look for "Ruling year"
        headers = soup.find_all("p", class_="report-section-header")
        for header in headers:
            if "Ruling year" in header.get_text():
                next_p = header.find_next_sibling("p", class_="report-section-text")
                if next_p:
                    ruling_text = next_p.get_text(strip=True)
                    try:
                        ruling_year = int(ruling_text)
                        if 1800 <= ruling_year <= 2100:
                            metadata["ruling_year"] = ruling_year
                            break
                    except ValueError:
                        pass

        # NTEE code and description
        ntee_section = soup.find(string=re.compile(r"NTEE code", re.IGNORECASE))
        if ntee_section:
            parent = ntee_section.find_parent()
            if parent:
                next_elem = parent.find_next_sibling()
                if next_elem:
                    ntee_text = next_elem.get_text(strip=True)
                    # Extract code pattern like "W12" from text like "Fund Raising and/or Fund Distribution (W12)"
                    ntee_match = re.search(r"\(([A-Z]\d{2})\)", ntee_text)
                    if ntee_match:
                        metadata["ntee_code"] = ntee_match.group(1)
                        # Get description (everything before the code)
                        desc = ntee_text.split("(")[0].strip()
                        if desc:
                            metadata["ntee_description"] = desc

        # IRS filing requirement
        irs_section = soup.find(string=re.compile(r"IRS filing requirement", re.IGNORECASE))
        if irs_section:
            parent = irs_section.find_parent()
            if parent:
                next_elem = parent.find_next_sibling()
                if next_elem:
                    metadata["irs_filing_requirement"] = next_elem.get_text(strip=True)

        # Logo URL
        logo_img = soup.find("img", class_="logo")
        if logo_img and logo_img.get("src"):
            metadata["logo_url"] = logo_img.get("src")

        # Extract vision if present (separate from mission)
        # Look in programs section
        prog_section = soup.find(id="programsAndAreasServed")
        if prog_section:
            prog_text = prog_section.get_text(separator=" ", strip=True)

            # Try to find vision statement
            if "vision" in prog_text.lower():
                vision_pattern = r"(?:Our\s+)?Vision[:\s]+([^.]+(?:\.[^.]*){0,2}\.)"
                match = re.search(vision_pattern, prog_text, re.IGNORECASE)
                if match:
                    vision = match.group(1).strip()
                    if len(vision) > 20 and len(vision) < 500:
                        metadata["vision"] = vision

            # Extract strategic goals or goals/strategy text
            if "goal" in prog_text.lower() or "strateg" in prog_text.lower():
                # Look for explicit strategic goals section
                goals_pattern = r"(?:Strategic\s+)?Goals?[:\s]+(.{50,400}?)(?:Our|Programs|SOURCE|$)"
                match = re.search(goals_pattern, prog_text, re.IGNORECASE | re.DOTALL)
                if match:
                    goals = match.group(1).strip()
                    goals = re.sub(r"\s+", " ", goals)  # Normalize whitespace
                    if len(goals) > 30:
                        metadata["strategic_goals"] = goals

                # Also save broader goals/strategy context
                # Find section between "What we aim to solve" and "Our programs"
                if "What we aim to solve" in prog_text:
                    parts = prog_text.split("What we aim to solve", 1)
                    if len(parts) > 1:
                        goals_text = parts[1].split("Our programs")[0] if "Our programs" in parts[1] else parts[1][:800]
                        goals_text = goals_text.split("SOURCE:")[0] if "SOURCE:" in goals_text else goals_text
                        goals_text = re.sub(r"\s+", " ", goals_text).strip()
                        if len(goals_text) > 50:
                            metadata["goals_strategy_text"] = goals_text[:600]

        return metadata

    def _extract_aka_names(self, soup: BeautifulSoup) -> List[str]:
        """Extract 'also known as' names."""
        aka_names = []

        # Look for "aka" section in header
        aka_elem = soup.find("strong", string="aka")
        if aka_elem:
            next_span = aka_elem.find_next_sibling("span")
            if next_span:
                aka_text = next_span.get_text(strip=True)
                # Split by slash or comma
                names = re.split(r"[/,]", aka_text)
                aka_names = [name.strip() for name in names if name.strip()]

        return aka_names

    def _extract_formerly_known_as(self, soup: BeautifulSoup) -> List[str]:
        """Extract former organization names."""
        formerly = []

        # Look for "Formerly known as" section
        section = soup.find(string="Formerly known as")
        if section:
            parent = section.find_parent()
            if parent:
                # Get all next siblings that are paragraph elements
                for sibling in parent.find_next_siblings():
                    if sibling.name == "p" and "report-section-text" in sibling.get("class", []):
                        name = sibling.get_text(strip=True)
                        if name:
                            formerly.append(name)

        return formerly

    def _extract_payment_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract payment/PO Box address."""
        # Look in contact modal
        section = soup.find(string="Payment Address")
        if section:
            parent = section.find_parent()
            if parent:
                address_parts = []
                for sibling in parent.find_next_siblings():
                    if sibling.name == "p" and "report-section-text" in sibling.get("class", []):
                        text = sibling.get_text(strip=True)
                        if text and "Payment Address" not in text:
                            address_parts.append(text)
                        if len(address_parts) >= 2:  # Got address line and city/state/zip
                            break
                if address_parts:
                    return " ".join(address_parts)

        return None

    def _extract_social_media(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Extract social media URLs."""
        social = {
            "facebook_url": None,
            "twitter_url": None,
            "linkedin_url": None,
            "youtube_url": None,
            "instagram_url": None,
        }

        # Find all social media links
        links = soup.find_all("a", class_="media-link")
        for link in links:
            href = link.get("href", "")
            if "facebook.com" in href:
                social["facebook_url"] = href
            elif "twitter.com" in href:
                social["twitter_url"] = href
            elif "linkedin.com" in href:
                social["linkedin_url"] = href
            elif "youtube.com" in href:
                social["youtube_url"] = href
            elif "instagram.com" in href:
                social["instagram_url"] = href

        return social

    def _extract_program_details(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract detailed program information including descriptions and populations served."""
        program_details = []

        # Look in programsList section
        programs_section = soup.find(id="programsList")
        if programs_section:
            # Find all program cards in accordion
            cards = programs_section.find_all("div", class_="card")

            for card in cards:
                program = {}

                # Get program name from header
                header = card.find("h4", class_="profile-accordion-header")
                if header:
                    program["name"] = header.get_text(strip=True)
                    # Remove expand/collapse icon text if present
                    program["name"] = re.sub(r"\s*\n\s*", " ", program["name"]).strip()

                # Get description from card body
                body = card.find("div", class_="card-body")
                if body:
                    desc_p = body.find("p", class_="description")
                    if desc_p:
                        program["description"] = desc_p.get_text(strip=True)

                    # Get populations served for this specific program
                    pop_box = body.find("div", class_="label-value-box")
                    if pop_box:
                        label = pop_box.find("div", class_="label")
                        if label and "Population" in label.get_text():
                            populations = []
                            for value_div in pop_box.find_all("div", class_="value"):
                                pop = value_div.get_text(strip=True)
                                if pop:
                                    populations.append(pop)
                            if populations:
                                program["populations_served"] = populations

                if "name" in program:  # Only add if we at least got a name
                    program_details.append(program)

        return program_details

    def _extract_metrics(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract metrics from 'Our results' section."""
        metrics = []

        # Look in ourResults section
        results_section = soup.find(id="platinumMetricsGrid")
        if results_section:
            # Find all metric cards
            cards = results_section.find_all("div", class_="card")

            for card in cards:
                metric = {}

                # Get metric name
                header = card.find("div", class_="card-header")
                if header:
                    h4 = header.find("h4")
                    if h4:
                        metric["name"] = h4.get_text(strip=True)

                # Extract year data from JavaScript
                script_tags = card.find_all("script")
                for script in script_tags:
                    script_text = script.get_text()
                    # Look for JSON data like: {"SelectedMeticId":"133992","MetricYearData":[["2023","5444975.0"],...]}
                    json_match = re.search(r"var myears = (\{[^}]+\});", script_text)
                    if json_match:
                        try:
                            import json

                            data = json.loads(json_match.group(1).replace("'", '"'))
                            if "MetricYearData" in data:
                                metric["year_data"] = data["MetricYearData"]
                                break
                        except (json.JSONDecodeError, KeyError, ValueError):
                            pass

                # Get type of metric
                type_box = card.find("h6", string="Type of Metric")
                if type_box:
                    next_p = type_box.find_next_sibling("p")
                    if next_p:
                        metric["type"] = next_p.get_text(strip=True)

                # Get direction of success
                direction_box = card.find("h6", string="Direction of Success")
                if direction_box:
                    next_p = direction_box.find_next_sibling("p")
                    if next_p:
                        metric["direction"] = next_p.get_text(strip=True)

                # Get context notes if available
                context_box = card.find("h6", string="Context Notes")
                if context_box:
                    next_p = context_box.find_next_sibling("p")
                    if next_p:
                        metric["context_notes"] = next_p.get_text(strip=True)

                if "name" in metric:
                    metrics.append(metric)

        return metrics

    def _extract_charting_impact(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Extract 'Charting Impact' / Goals & Strategy details."""
        charting_impact = {
            "goal": None,
            "strategies": None,
            "capabilities": None,
            "progress": None,
        }

        # Look for chartingImpact section
        section = soup.find(id="chartingImpactAccordion")
        if section:
            cards = section.find_all("div", class_="card")

            for card in cards:
                header = card.find("h4", class_="profile-accordion-header")
                if not header:
                    continue

                header_text = header.get_text(strip=True)
                body = card.find("div", class_="card-body")
                if not body:
                    continue

                description = body.find("p", class_="description")
                if not description:
                    continue

                desc_text = description.get_text(strip=True)

                # Map based on header text
                if "aiming to accomplish" in header_text.lower():
                    charting_impact["goal"] = desc_text
                elif "key strategies" in header_text.lower():
                    charting_impact["strategies"] = desc_text
                elif "capabilities" in header_text.lower():
                    charting_impact["capabilities"] = desc_text
                elif "accomplished" in header_text.lower() and "what's next" in header_text.lower():
                    charting_impact["progress"] = desc_text

        return charting_impact

    def _extract_board_members(self, soup: BeautifulSoup) -> Tuple[List[Dict[str, str]], Optional[int]]:
        """Extract board of directors information."""
        board_members = []

        # Look in boardOfDirectors section
        board_section = soup.find(id="boardOfDirectors")
        if board_section:
            # Find all board member paragraphs
            member_divs = board_section.find_all("div", class_="col-md-3")

            for div in member_divs:
                member_p = div.find("p", class_="boardofdirectors")
                if member_p:
                    member_text = member_p.get_text(strip=True)
                    # Text is like "Ahmed Azam SECRETARY THRU 11/1/23, CHAIRMAN"
                    # Split on multiple spaces to separate name from title
                    parts = re.split(r"\s{2,}", member_text)

                    member = {}
                    if len(parts) >= 1:
                        # First part is name
                        member["name"] = parts[0].strip()

                        # Second part (if exists) is title/role
                        if len(parts) >= 2:
                            member["title"] = parts[1].strip()

                        # Check for affiliation
                        affiliation_p = div.find("p", class_="boardofdirectors-small")
                        if affiliation_p:
                            affiliation = affiliation_p.get_text(strip=True)
                            if affiliation and affiliation != "No affiliation":
                                member["affiliation"] = affiliation

                        board_members.append(member)

        # Board size is just the count
        board_size = len(board_members) if board_members else None

        return board_members, board_size

    def _extract_media_flags(self, soup: BeautifulSoup) -> Dict[str, bool]:
        """Check if organization has uploaded photos and videos."""
        flags = {
            "has_photos": False,
            "has_videos": False,
        }

        # Check for photo carousel
        photo_section = soup.find(id="photoCarouselContainer")
        if photo_section:
            photos = photo_section.find_all("img")
            # Filter out placeholder images
            real_photos = [img for img in photos if img.get("src") and "docs.candid.org" in img.get("src", "")]
            if real_photos:
                flags["has_photos"] = True

        # Check for video carousel
        video_section = soup.find(id="videoCarouselContainer")
        if video_section:
            iframes = video_section.find_all("iframe")
            if iframes:
                flags["has_videos"] = True

        return flags

    def _extract_feedback_practices(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract "How We Listen" section - feedback practices data."""
        feedback_data = {
            "practices": [],
            "usage": None,
            "collection": None,
        }

        # Look for howWeListen section
        section = soup.find(id="howWeListen")
        if not section:
            return feedback_data

        # Extract practiced items (checkmarked items)
        responses = section.find(id="feedbackResponses")
        if responses:
            items = responses.find_all("span", class_="pl-2")
            for item in items:
                text = item.get_text(strip=True)
                if text and len(text) > 10:
                    feedback_data["practices"].append(text)

        # Extract Q&A responses
        qa_section = section.find(id="howWeListenResponses")
        if qa_section:
            items = qa_section.find_all("li")
            for item in items:
                question = item.find("p", class_="question")
                answer = item.find_all("p")[-1] if item.find_all("p") else None  # Last p is answer

                if question and answer and answer != question:
                    q_text = question.get_text(strip=True).lower()
                    a_text = answer.get_text(strip=True)

                    if "using feedback" in q_text:
                        feedback_data["usage"] = a_text
                    elif "routinely carry out" in q_text:
                        feedback_data["collection"] = a_text

        return feedback_data

    def _extract_evaluation_documents(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract links to evaluation documents."""
        documents = []

        # Look for platinumEvalDocs section
        section = soup.find(id="platinumEvalDocs")
        if not section:
            return documents

        # Find dropdown menu with document links
        dropdown = section.find("span", class_="dropdown-menu")
        if dropdown:
            links = dropdown.find_all("a")
            for link in links:
                href = link.get("href")
                name = link.get_text(strip=True)
                if href and name:
                    documents.append({"name": name, "url": href})

        return documents

    def _log_field_extraction_report(self, profile: Dict[str, Any]):
        """Log detailed field extraction report."""
        if not self.logger:
            return

        # Define critical fields
        critical_fields = {"name", "ein", "mission", "programs"}

        # Count extracted vs missing
        extracted = []
        missing_critical = []

        for key, value in profile.items():
            if value is not None and value != "" and value != []:
                # Truncate long values for display
                display_value = str(value)
                if len(display_value) > 50:
                    display_value = display_value[:47] + "..."
                extracted.append(f"  ✓ {key}: {display_value}")
            elif key in critical_fields:
                missing_critical.append(f"  ✗ {key}: MISSING (CRITICAL)")

        total_fields = len(profile)
        extracted_count = len(extracted)
        percentage = (extracted_count / total_fields * 100) if total_fields > 0 else 0

        # Log report
        self.logger.debug("[CANDID] Field Extraction Report:")
        for line in extracted:
            self.logger.debug(line)

        if missing_critical:
            for line in missing_critical:
                self.logger.warning(line)

        self.logger.debug(f"Summary: {extracted_count}/{total_fields} fields extracted ({percentage:.1f}%)")

    def _compute_max_years_tracked(self, metrics: List[Dict[str, Any]]) -> Optional[int]:
        """Compute maximum year span across all metrics.

        Args:
            metrics: List of metric dictionaries with 'years' or 'values' keys

        Returns:
            Maximum year span (e.g., 2020-2023 = 4), or None if no year data
        """
        if not metrics:
            return None

        max_span = 0
        for metric in metrics:
            # Metrics may have 'years' list or 'values' list with year keys
            years = metric.get("years", [])
            if not years and "values" in metric:
                # Try to extract years from values dict
                values = metric.get("values", {})
                if isinstance(values, dict):
                    years = [int(y) for y in values.keys() if str(y).isdigit()]

            if years and len(years) >= 2:
                try:
                    year_span = max(years) - min(years) + 1
                    max_span = max(max_span, year_span)
                except (TypeError, ValueError):
                    continue

        return max_span if max_span > 0 else None

    def _consolidate_social_media(self, social_media_dict: Dict[str, Any]) -> Dict[str, str]:
        """Consolidate social media URLs into spec-compliant object.

        Args:
            social_media_dict: Dict with keys like 'facebook_url', 'twitter_url', etc.

        Returns:
            Dict with keys like 'facebook', 'twitter' (without _url suffix), non-null values only
        """
        result = {}
        mapping = {
            "facebook_url": "facebook",
            "twitter_url": "twitter",
            "linkedin_url": "linkedin",
            "youtube_url": "youtube",
            "instagram_url": "instagram",
        }
        for old_key, new_key in mapping.items():
            url = social_media_dict.get(old_key)
            if url and isinstance(url, str) and url.strip():
                result[new_key] = url.strip()
        return result

    def fetch(self, ein: str, **kwargs) -> FetchResult:
        """
        Fetch raw HTML from Candid/GuideStar.

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX

        Returns:
            FetchResult with raw HTML
        """
        # Normalize EIN to XX-XXXXXXX format
        ein_clean = ein.replace("-", "")

        if len(ein_clean) != 9 or not ein_clean.isdigit():
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error=f"Invalid EIN format: {ein}",
            )

        ein_formatted = f"{ein_clean[:2]}-{ein_clean[2:]}"

        # IMPORTANT: Always use GuideStar URL format
        # The new Candid URLs (app.candid.org) are JavaScript-rendered SPAs
        # and do not contain the rich data in the HTML. The GuideStar URLs
        # (www.guidestar.org) still work and contain all data server-rendered.
        url = f"https://www.guidestar.org/profile/{ein_formatted}"
        if self.logger:
            self.logger.debug(f"Fetching Candid profile from GuideStar URL for EIN {ein}")

        # Rate limiting
        self._rate_limit()

        try:
            # Fetch HTML
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True,
            )

            # FIX #12: Detect URL deprecation via redirects.
            # If GuideStar URLs start redirecting to a different host (e.g., app.candid.org),
            # the server-rendered HTML we depend on will be replaced by a JS SPA.
            final_url = response.url
            if final_url and "guidestar.org" not in final_url:
                if self.logger:
                    self.logger.warning(
                        f"[CANDID URL DEPRECATION] GuideStar URL redirected to {final_url} "
                        f"for EIN {ein}. The www.guidestar.org endpoint may be deprecated. "
                        f"If this persists, migration to Playwright/API-based extraction is needed."
                    )

            if response.status_code == 404:
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="html",
                    error=f"Profile not found for EIN {ein}",
                )

            if response.status_code != 200:
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="html",
                    error=f"HTTP {response.status_code}",
                )

            html_content = response.text

            # FIX #12: Detect if response is a JS SPA shell instead of server-rendered HTML.
            # Candid's new SPA pages have minimal HTML with JS bundles — no server-rendered data.
            if ("__NEXT_DATA__" in html_content or "app.candid.org" in html_content) and "guidestar" not in html_content.lower():
                if self.logger:
                    self.logger.warning(
                        f"[CANDID URL DEPRECATION] Response for {ein} appears to be a JS SPA "
                        f"(Candid app) rather than server-rendered GuideStar HTML. "
                        f"Data extraction will be incomplete."
                    )

            # Basic validation - check for either guidestar or candid
            if "guidestar" not in html_content.lower() and "candid" not in html_content.lower():
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="html",
                    error="Response doesn't appear to be from Candid/GuideStar",
                )

            # Save debug HTML if requested
            if self.save_debug_html:
                debug_file = self.debug_dir / f"candid-{ein_formatted}.html"
                try:
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    if self.logger:
                        self.logger.debug(f"Saved debug HTML to {debug_file}")
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Failed to save debug HTML: {e}")

            return FetchResult(
                success=True,
                raw_data=html_content,
                content_type="html",
                error=None,
            )

        except requests.Timeout:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error=f"Request timeout after {self.timeout}s",
            )
        except requests.RequestException as e:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error=f"Request failed: {str(e)}",
            )

    def parse(self, raw_data: str, ein: str, **kwargs) -> ParseResult:
        """
        Parse Candid HTML into profile schema.

        Args:
            raw_data: Raw HTML from fetch()
            ein: EIN

        Returns:
            ParseResult with {"candid_profile": {...}}
        """
        ein_clean = ein.replace("-", "")
        ein_formatted = f"{ein_clean[:2]}-{ein_clean[2:]}"

        try:
            # Parse with BeautifulSoup
            soup = BeautifulSoup(raw_data, "html.parser")

            # Extract all fields
            org_name = self._extract_organization_name(soup)
            extracted_ein = self._extract_ein(soup, raw_data)
            mission = self._extract_mission(soup)
            tagline = self._extract_tagline(soup)
            aka_names = self._extract_aka_names(soup)
            formerly_known_as = self._extract_formerly_known_as(soup)
            programs = self._extract_programs(soup)
            program_details = self._extract_program_details(soup)
            outcomes = self._extract_outcomes(soup)
            populations_served = self._extract_populations_served(soup)
            areas_served = self._extract_areas_served(soup)
            metrics = self._extract_metrics(soup)
            charting_impact = self._extract_charting_impact(soup)
            ceo_name, _ = self._extract_ceo_info(soup)
            board_members, board_size = self._extract_board_members(soup)
            contact = self._extract_contact_info(soup)
            payment_address = self._extract_payment_address(soup)
            social_media = self._extract_social_media(soup)
            metadata = self._extract_metadata(soup, raw_data)
            candid_seal = self._extract_candid_seal(soup, raw_data)
            candid_url = self._extract_candid_url(raw_data)
            media_flags = self._extract_media_flags(soup)
            feedback = self._extract_feedback_practices(soup)
            eval_docs = self._extract_evaluation_documents(soup)

            # Build profile data
            profile_data = {
                "name": org_name or "Unknown",
                "ein": extracted_ein or ein_formatted,
                "tagline": tagline,
                "aka_names": aka_names,
                "mission": mission,
                "vision": metadata.get("vision"),
                "strategic_goals": metadata.get("strategic_goals"),
                "programs": programs,
                "program_details": program_details,
                "outcomes": outcomes,
                "populations_served": populations_served,
                "geographic_coverage": areas_served,
                "goals_strategy_text": metadata.get("goals_strategy_text"),
                "metrics": metrics,
                "charting_impact_goal": charting_impact.get("goal"),
                "charting_impact_strategies": charting_impact.get("strategies"),
                "charting_impact_capabilities": charting_impact.get("capabilities"),
                "charting_impact_progress": charting_impact.get("progress"),
                "ceo_name": ceo_name,
                "board_members": board_members,
                "board_size": board_size,
                "address": contact.get("address"),
                "payment_address": payment_address,
                "city": contact.get("city"),
                "state": contact.get("state"),
                "zip": contact.get("zip"),
                "website_url": contact.get("website"),
                "phone": contact.get("phone"),
                "email": contact.get("email"),
                "social_media": self._consolidate_social_media(social_media),
                "irs_ruling_year": metadata.get("ruling_year"),
                "formerly_known_as": formerly_known_as,
                "ntee_code": metadata.get("ntee_code"),
                "ntee_description": metadata.get("ntee_description"),
                "irs_filing_requirement": metadata.get("irs_filing_requirement"),
                "candid_seal": candid_seal,
                "candid_url": candid_url,
                "feedback_practices": feedback.get("practices", []),
                "feedback_usage": feedback.get("usage"),
                "feedback_collection": feedback.get("collection"),
                "evaluation_documents": eval_docs,
                "logo_url": metadata.get("logo_url"),
                "has_photos": media_flags.get("has_photos"),
                "has_videos": media_flags.get("has_videos"),
                # Derived evidence fields (per spec)
                "metrics_count": len(metrics) if metrics else 0,
                "max_years_tracked": self._compute_max_years_tracked(metrics),
                "has_charting_impact": bool(
                    charting_impact.get("goal")
                    or charting_impact.get("strategies")
                    or charting_impact.get("progress")
                ),
            }

            # Validate with Pydantic
            try:
                profile = CandidProfile(**profile_data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Validation error: {e}")
                    self.logger.debug(f"Profile data: {profile_data}")
                return ParseResult(
                    success=False,
                    parsed_data=None,
                    error=f"Validation failed: {e}",
                )

            # Log field extraction report
            if self.logger:
                self._log_field_extraction_report(profile.model_dump())
                self.logger.debug(f"Successfully parsed Candid data for {ein}")

            return ParseResult(
                success=True,
                parsed_data={self.schema_key: profile.model_dump()},
                error=None,
            )

        except Exception as e:
            if self.logger:
                self.logger.exception("Unexpected error in Candid parsing")
            return ParseResult(
                success=False,
                parsed_data=None,
                error=f"Parse error: {str(e)}",
            )

    def collect(
        self, ein: str, candid_profile_id: Optional[str] = None, slug: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Legacy method: fetch + parse in one call.

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX
            candid_profile_id: Ignored (kept for backward compatibility)
            slug: Ignored (kept for backward compatibility)

        Returns:
            Tuple of (success, data, error_message)
        """
        # Fetch
        fetch_result = self.fetch(ein)
        if not fetch_result.success:
            return False, None, fetch_result.error

        # Parse
        parse_result = self.parse(fetch_result.raw_data, ein)
        if not parse_result.success:
            return False, None, parse_result.error

        # Combine for backwards compatibility
        result = {
            **parse_result.parsed_data,
            "raw_content": fetch_result.raw_data,
            "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return True, result, None

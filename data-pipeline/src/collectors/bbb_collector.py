"""
BBB Wise Giving Alliance collector.

Collects charity evaluation data from give.org (BBB WGA):
- 20 Standards for Charity Accountability assessment
- Governance standards (board size, meetings, compensation, conflicts)
- Financial standards (program expense ratio, fundraising ratio, reserves)
- Effectiveness standards (audit status, effectiveness assessment)
- Solicitations and informational materials standards
- Donor privacy and annual report availability

BBB WGA evaluates primarily large national charities.
All 20 standards must be met for "Meets Standards" status.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from ..utils.logger import PipelineLogger
from ..utils.rate_limiter import global_rate_limiter
from ..validators.bbb_validator import BBBProfile
from .base import BaseCollector, FetchResult, ParseResult

# Map standard numbers to readable names for spec compliance
STANDARD_NAMES = {
    1: "Board Oversight",
    2: "Board Size",
    3: "Board Meetings",
    4: "Board Compensation",
    5: "Conflict of Interest",
    6: "Effectiveness Policy",
    7: "Effectiveness Report",
    8: "Program Expenses",
    9: "Fundraising Expenses",
    10: "Accumulating Funds",
    11: "Audit Report",
    12: "Detailed Expense Breakdown",
    13: "Accurate Expense Reporting",
    14: "Budget Plan",
    15: "Truthful Materials",
    16: "Annual Report",
    17: "Website Disclosures",
    18: "Donor Privacy",
    19: "Cause Marketing Disclosures",
    20: "Complaints",
}


class BBBCollector(BaseCollector):
    """
    Collector for BBB Wise Giving Alliance charity reports.

    Implements BaseCollector for 3-phase pipeline:
    - fetch(): Search for charity + fetch review page HTML
    - parse(): Parse HTML into bbb_profile schema

    BBB WGA evaluates charities against 20 Standards for Charity Accountability
    grouped into 4 categories:
    - Governance & Oversight (Standards 1-5)
    - Measuring Effectiveness (Standards 6-9)
    - Finances (Standards 10-15)
    - Solicitations & Informational Materials (Standards 16-20)

    A charity "meets standards" if it meets all 20, otherwise it "does not meet".
    """

    BASE_URL = "https://give.org"
    SEARCH_URL = "https://give.org/search"

    def __init__(
        self,
        logger: Optional[PipelineLogger] = None,
        rate_limit_delay: float = 2.0,
    ):
        """
        Initialize BBB WGA collector.

        Args:
            logger: Logger instance
            rate_limit_delay: Seconds between requests
        """
        self.logger = logger
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

    @property
    def source_name(self) -> str:
        return "bbb"

    @property
    def schema_key(self) -> str:
        return "bbb_profile"

    def _rate_limit(self):
        """Enforce rate limiting (global, thread-safe)."""
        global_rate_limiter.wait("bbb", self.rate_limit_delay)

    def _normalize_name(self, name: str) -> set:
        """Normalize charity name to set of significant words for comparison."""
        # Remove common suffixes and prefixes
        name = name.lower()
        stopwords = {
            'inc', 'incorporated', 'llc', 'corp', 'corporation', 'foundation',
            'the', 'a', 'an', 'of', 'for', 'and', 'usa', 'us', 'america',
            'american', 'national', 'international', 'global', 'project',
            # Location words - prevent false positives like "Greater Houston" matching
            'greater', 'north', 'south', 'east', 'west', 'central', 'metro',
            'houston', 'dallas', 'chicago', 'york', 'angeles', 'francisco',
            'atlanta', 'boston', 'denver', 'seattle', 'phoenix', 'detroit',
            'miami', 'philadelphia', 'washington', 'texas', 'california',
            'florida', 'virginia', 'maryland', 'jersey', 'carolina',
        }
        # Extract words, filter stopwords and short words
        words = set(re.findall(r'\b[a-z]{3,}\b', name))
        return words - stopwords

    def _names_match(self, expected_name: str, found_name: str) -> bool:
        """
        Check if two charity names refer to the same organization.

        Uses word overlap - requires significant meaningful word overlap.
        Stricter than before to avoid location-based false positives.
        """
        if not expected_name or not found_name:
            return False

        expected_words = self._normalize_name(expected_name)
        found_words = self._normalize_name(found_name)

        if not expected_words or not found_words:
            return False

        # Calculate overlap
        overlap = expected_words & found_words
        # Stricter: require 60% overlap AND at least 2 words
        min_matches = max(2, int(len(expected_words) * 0.6))
        return len(overlap) >= min_matches

    def _search_charity(
        self, ein: str, name: Optional[str] = None
    ) -> Optional[str]:
        """
        Search for a charity on BBB WGA and return the review page URL.

        Validates search results by comparing charity names to prevent
        returning wrong organizations.

        Args:
            ein: EIN to search for
            name: Charity name for search (used for validation)

        Returns:
            URL of charity review page if found and validated, None otherwise
        """
        # Try EIN search first
        ein_clean = ein.replace("-", "")
        search_terms = [ein, ein_clean]
        if name:
            search_terms.append(name)

        for term in search_terms:
            self._rate_limit()

            try:
                # BBB WGA uses /search?term= for search
                search_url = f"{self.SEARCH_URL}?term={term}"
                response = requests.get(search_url, headers=self.headers, timeout=30)

                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")

                # Look for charity review links in search results
                # Pattern: /charity-reviews/{category}/{charity-slug}-in-{city}-{state}-{bbb-id}
                review_links = soup.find_all("a", href=re.compile(r"/charity-reviews/[^/]+/[^/]+-in-"))

                for link in review_links:
                    href = link.get("href", "")
                    if "/charity-reviews/" not in href or "-in-" not in href:
                        continue

                    full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                    # Extract charity name from link text or URL slug
                    link_text = link.get_text(strip=True)
                    # Also try to extract from URL slug (e.g., "islamic-relief-usa-in-alexandria")
                    slug_match = re.search(r'/charity-reviews/[^/]+/([^/]+)-in-', href)
                    slug_name = slug_match.group(1).replace('-', ' ') if slug_match else ""

                    # Validate name if we have an expected name
                    if name:
                        if self._names_match(name, link_text) or self._names_match(name, slug_name):
                            if self.logger:
                                self.logger.debug(f"Found matching BBB review: {full_url}")
                            return full_url
                        else:
                            if self.logger:
                                self.logger.debug(
                                    f"BBB name mismatch: expected '{name}', found '{link_text}' - skipping"
                                )
                            continue
                    else:
                        # No name to validate against, return first result
                        if self.logger:
                            self.logger.debug(f"Found BBB review page: {full_url}")
                        return full_url

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"BBB search failed for '{term}': {e}")
                continue

        return None

    def fetch(self, ein: str, **kwargs) -> FetchResult:
        """
        Search for charity and fetch BBB review page HTML via AJAX API.

        BBB give.org loads charity reports dynamically via JavaScript.
        This method:
        1. Fetches the page shell to get nonce and charity IDs
        2. Calls the AJAX API to get the rendered report HTML

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX
            **kwargs: Can include 'name' for charity name search

        Returns:
            FetchResult with rendered HTML and review_url in metadata
        """
        name = kwargs.get("name") or kwargs.get("charity_name")

        if self.logger:
            self.logger.debug(f"Searching BBB WGA for EIN {ein}")

        # Search for charity
        review_url = self._search_charity(ein, name)
        if not review_url:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error=f"Charity not found on BBB WGA: {ein}",
            )

        # Step 1: Fetch review page shell to get nonce and IDs
        self._rate_limit()

        try:
            response = requests.get(review_url, headers=self.headers, timeout=30)

            if response.status_code != 200:
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="html",
                    error=f"HTTP {response.status_code} for {review_url}",
                )

            page_html = response.text

            # Extract nonce from giveCharityReportVars
            nonce_match = re.search(r'"nonce"\s*:\s*"([^"]+)"', page_html)
            if not nonce_match:
                # Fallback: return shell HTML (limited data)
                if self.logger:
                    self.logger.warning("Could not extract nonce, returning shell HTML")
                metadata = {"review_url": review_url}
                return FetchResult(
                    success=True,
                    raw_data=f"<!-- BBB_METADATA: {json.dumps(metadata)} -->\n{page_html}",
                    content_type="html",
                    error=None,
                )

            nonce = nonce_match.group(1)

            # Extract bureau_code and source_id from data attributes
            bureau_match = re.search(r'data-bureau-code="(\d+)"', page_html)
            source_match = re.search(r'data-source-id="(\d+)"', page_html)

            if not bureau_match or not source_match:
                if self.logger:
                    self.logger.warning("Could not extract bureau/source IDs")
                metadata = {"review_url": review_url}
                return FetchResult(
                    success=True,
                    raw_data=f"<!-- BBB_METADATA: {json.dumps(metadata)} -->\n{page_html}",
                    content_type="html",
                    error=None,
                )

            bureau_code = bureau_match.group(1)
            source_id = source_match.group(1)

            # Step 2: Call AJAX API to get rendered report
            self._rate_limit()

            ajax_data = {
                "action": "give_load_charity_report",
                "nonce": nonce,
                "bureau_code": bureau_code,
                "source_business_id": source_id,
            }

            ajax_response = requests.post(
                f"{self.BASE_URL}/wp-admin/admin-ajax.php",
                headers={
                    **self.headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
                data=ajax_data,
                timeout=30,
            )

            if ajax_response.status_code != 200:
                if self.logger:
                    self.logger.warning(f"AJAX call failed: {ajax_response.status_code}")
                metadata = {"review_url": review_url}
                return FetchResult(
                    success=True,
                    raw_data=f"<!-- BBB_METADATA: {json.dumps(metadata)} -->\n{page_html}",
                    content_type="html",
                    error=None,
                )

            try:
                ajax_json = ajax_response.json()
                if ajax_json.get("success") and ajax_json.get("data", {}).get("html"):
                    report_html = ajax_json["data"]["html"]
                    metadata = {"review_url": review_url, "bureau_code": bureau_code, "source_id": source_id}
                    return FetchResult(
                        success=True,
                        raw_data=f"<!-- BBB_METADATA: {json.dumps(metadata)} -->\n{report_html}",
                        content_type="html",
                        error=None,
                    )
            except (json.JSONDecodeError, KeyError):
                pass

            # Fallback to shell HTML
            metadata = {"review_url": review_url}
            return FetchResult(
                success=True,
                raw_data=f"<!-- BBB_METADATA: {json.dumps(metadata)} -->\n{page_html}",
                content_type="html",
                error=None,
            )

        except requests.Timeout:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error="Request timeout after 30s",
            )
        except requests.RequestException as e:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error=f"Request failed: {str(e)}",
            )

    # FIX #23: Content-substance markers that indicate real BBB report data.
    # Shell HTML (page template without AJAX content) won't have these.
    BBB_SUBSTANCE_MARKERS = [
        "evaluation-status",       # Overall status div
        "standard-item",           # Individual standard items
        "meets-standards",         # Standards CSS class
        "does-not-meet",           # Standards CSS class
        "Accredited Charity",      # Accredited badge text
        "Standards for Charity",   # Section heading
    ]

    def _check_content_substance(self, html: str, ein: str) -> bool:
        """
        FIX #23: Check if BBB HTML contains real report content vs shell template.

        Returns True if the content has substance, False if it's a shell.
        """
        matches = sum(1 for marker in self.BBB_SUBSTANCE_MARKERS if marker in html)

        if matches == 0:
            if self.logger:
                self.logger.warning(
                    f"[BBB SHELL HTML] Content for {ein} has no substance markers "
                    f"(0/{len(self.BBB_SUBSTANCE_MARKERS)} matched). "
                    f"This is likely a page shell without AJAX-loaded report data. "
                    f"Extracted data will be empty/incomplete."
                )
            return False

        if matches <= 1:
            if self.logger:
                self.logger.warning(
                    f"[BBB LOW SUBSTANCE] Content for {ein} has minimal substance "
                    f"({matches}/{len(self.BBB_SUBSTANCE_MARKERS)} markers matched). "
                    f"BBB report data may be incomplete."
                )

        return True

    def parse(self, raw_data: str, ein: str, **kwargs) -> ParseResult:
        """
        Parse BBB review page HTML into profile schema.

        Args:
            raw_data: Raw HTML from fetch() with metadata header
            ein: Charity EIN

        Returns:
            ParseResult with {"bbb_profile": {...}}
        """
        try:
            # Extract metadata from header
            review_url = None
            html = raw_data
            if raw_data.startswith("<!-- BBB_METADATA:"):
                first_line_end = raw_data.index("-->\n") + 4
                metadata_line = raw_data[:first_line_end]
                html = raw_data[first_line_end:]
                try:
                    metadata_json = metadata_line.replace("<!-- BBB_METADATA: ", "").replace(" -->", "").strip()
                    metadata = json.loads(metadata_json)
                    review_url = metadata.get("review_url")
                except (json.JSONDecodeError, ValueError):
                    pass

            # FIX #23: Check content substance before parsing
            self._check_content_substance(html, ein)

            soup = BeautifulSoup(html, "html.parser")

            # Extract data from page
            profile_dict = self._extract_profile(soup, ein, review_url or "")

            # Validate through Pydantic model
            # Name is required - if not found, use placeholder
            if not profile_dict.get("name"):
                profile_dict["name"] = "Unknown Organization"

            profile = BBBProfile(**profile_dict)

            if self.logger:
                self.logger.debug(f"Successfully parsed BBB data for {ein}")

            return ParseResult(
                success=True,
                parsed_data={self.schema_key: profile.model_dump()},
                error=None,
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"BBB parse failed: {e}")
            return ParseResult(
                success=False,
                parsed_data=None,
                error=f"Parse error: {str(e)}",
            )

    def collect(
        self, ein: str, name: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Legacy method: fetch + parse in one call.

        Returns:
            Tuple of (success, data, error_message)
        """
        # Fetch
        fetch_result = self.fetch(ein, name=name)
        if not fetch_result.success:
            return False, None, fetch_result.error

        # Parse
        parse_result = self.parse(fetch_result.raw_data, ein)
        if not parse_result.success:
            return False, None, parse_result.error

        # Extract review_url from raw_data for backwards compatibility
        review_url = None
        if fetch_result.raw_data and fetch_result.raw_data.startswith("<!-- BBB_METADATA:"):
            try:
                metadata_line = fetch_result.raw_data.split("-->\n")[0]
                metadata_json = metadata_line.replace("<!-- BBB_METADATA: ", "").strip()
                metadata = json.loads(metadata_json)
                review_url = metadata.get("review_url")
            except (json.JSONDecodeError, ValueError, IndexError):
                pass

        # Combine for backwards compatibility
        result = {
            **parse_result.parsed_data,
            "raw_content": fetch_result.raw_data,
            "fetch_timestamp": datetime.now().isoformat(),
            "review_url": review_url,
        }

        return True, result, None

    def _extract_profile(
        self, soup: BeautifulSoup, ein: str, url: str
    ) -> Dict[str, Any]:
        """
        Extract evaluation data from BBB charity review page.

        Args:
            soup: BeautifulSoup object
            ein: EIN
            url: Review page URL

        Returns:
            Profile dictionary with BBB assessment data
        """
        profile = {
            "ein": ein,
            "review_url": url,
        }

        # Extract charity name
        name_elem = soup.find("h1")
        if name_elem:
            profile["name"] = name_elem.get_text(strip=True)

        # Extract overall status (Meets Standards / Does Not Meet Standards)
        status = self._extract_overall_status(soup)
        profile.update(status)

        # Extract 20 Standards breakdown
        standards = self._extract_standards_breakdown(soup)
        profile.update(standards)

        # Extract category pass/fail status
        categories = self._extract_category_status(soup)
        profile.update(categories)

        # Extract governance details (Standards 1-5)
        governance = self._extract_governance_details(soup)
        profile.update(governance)

        # Extract financial metrics (Standards 8-14)
        financials = self._extract_financial_metrics(soup)
        profile.update(financials)

        # Extract effectiveness data (Standards 6-7)
        effectiveness = self._extract_effectiveness_data(soup)
        profile.update(effectiveness)

        # Extract solicitation/transparency details (Standards 15-20)
        transparency = self._extract_transparency_details(soup)
        profile.update(transparency)

        # Extract last review date
        review_date = self._extract_review_date(soup)
        if review_date:
            profile["last_review_date"] = review_date

        return profile

    def _extract_overall_status(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract overall "Meets Standards" status.

        BBB WGA has four possible statuses:
        - Meets Standards (all 20 standards met, eligible for seal)
        - Does Not Meet Standards (failed one or more after evaluation)
        - Did Not Disclose (charity refused to cooperate with evaluation)
        - Review in Progress (BBB currently evaluating)

        The status is indicated by:
        1. CSS class on evaluation-status div (most reliable)
        2. "Accredited Charity" badge with "Meets Standards" text
        3. CSS classes on standard-item elements (meets-standards, does-not-meet)
        """
        data = {"meets_standards": None, "status_text": None}

        # Method 1: Check CSS class on evaluation-status div (most reliable)
        # HTML structure: <div class="evaluation-status did-not-disclose">
        #                   <span class="status-value">Did Not Disclose</span>
        #                 </div>
        eval_status = soup.find("div", class_=re.compile(r"evaluation-status"))
        if eval_status:
            classes = " ".join(eval_status.get("class", []))
            status_span = eval_status.find("span", class_="status-value")
            status_text = status_span.get_text(strip=True) if status_span else None

            if "meets-standards" in classes or "accredited" in classes:
                data["meets_standards"] = True
                data["status_text"] = "Meets Standards"
            elif "did-not-disclose" in classes:
                data["meets_standards"] = None  # Not evaluated - charity refused
                data["status_text"] = "Did Not Disclose"
            elif "review-in-progress" in classes:
                data["meets_standards"] = None  # Pending evaluation
                data["status_text"] = "Review in Progress"
            elif "does-not-meet" in classes:
                data["meets_standards"] = False
                data["status_text"] = "Does Not Meet Standards"
            elif status_text:
                # Use actual status text from page as fallback
                data["status_text"] = status_text
                status_lower = status_text.lower()
                if "meets standards" in status_lower and "does not" not in status_lower:
                    data["meets_standards"] = True
                elif "does not meet" in status_lower:
                    data["meets_standards"] = False
                elif "did not disclose" in status_lower:
                    data["meets_standards"] = None
                elif "review in progress" in status_lower:
                    data["meets_standards"] = None

            # If we got a definitive status, return early
            if data["status_text"]:
                return data

        # Method 2: Look for "Accredited Charity" section with status text
        # Structure: <p>Meets Standards</p> near "Accredited Charity"
        accredited = soup.find(string=re.compile(r"Accredited\s+Charity", re.IGNORECASE))
        if accredited:
            # Look for nearby "Meets Standards" text
            parent = accredited.find_parent()
            if parent:
                # Check siblings and children for status
                container = parent.find_parent() or parent
                container_text = container.get_text().lower()
                if "meets standards" in container_text and "does not" not in container_text:
                    data["meets_standards"] = True
                    data["status_text"] = "Meets Standards"
                elif "does not meet" in container_text or "standards not met" in container_text:
                    data["meets_standards"] = False
                    data["status_text"] = "Does Not Meet Standards"

        # Method 3: Count CSS classes on standard-item elements
        # <li class="standard-item meets-standards">
        meets_items = soup.find_all(class_=re.compile(r"meets-standards"))
        not_meets_items = soup.find_all(class_=re.compile(r"does-not-meet|not-met|standards-not-met"))

        if meets_items and not not_meets_items:
            # All standards have meets-standards class
            if len(meets_items) >= 15:  # Most of the 20 standards
                data["meets_standards"] = True
                data["status_text"] = "Meets Standards"
        elif not_meets_items:
            data["meets_standards"] = False
            data["status_text"] = "Does Not Meet Standards"

        # Method 4: Fallback - look for status text patterns
        # Only if no status determined yet
        if data["meets_standards"] is None and data["status_text"] is None:
            text = soup.get_text().lower()
            # Check for non-evaluated statuses first (before generic text matching)
            if "did not disclose" in text:
                data["meets_standards"] = None
                data["status_text"] = "Did Not Disclose"
            elif "review in progress" in text:
                data["meets_standards"] = None
                data["status_text"] = "Review in Progress"
            elif "unable to verify" in text:
                data["meets_standards"] = None
                data["status_text"] = "Unable to Verify"
            elif "does not meet" in text or "standards not met" in text:
                data["meets_standards"] = False
                data["status_text"] = "Does Not Meet Standards"
            elif "meets standards" in text:
                data["meets_standards"] = True
                data["status_text"] = "Meets Standards"

        return data

    def _extract_standards_breakdown(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract individual standard pass/fail status.

        The 20 Standards are grouped into 4 categories:
        1. Governance & Oversight (Standards 1-5)
        2. Measuring Effectiveness (Standards 6-7)
        3. Finances (Standards 8-14)
        4. Fundraising & Info (Standards 15-20)

        The status is indicated by CSS classes on li elements:
        - class="standard-item meets-standards" = passed
        - class="standard-item does-not-meet" = failed
        """
        data = {
            "standards_met": [],  # List of standard names that passed (per spec)
            "standards_not_met": [],  # List of standard names that failed (per spec)
            "standards_met_count": 0,  # Count (extended field)
            "standards_not_met_count": 0,  # Count (extended field)
            "standards_details": {},  # Detailed breakdown (extended field)
        }

        # Map standard names to numbers
        standard_names = {
            "board oversight": 1,
            "board size": 2,
            "board meetings": 3,
            "board compensation": 4,
            "conflict of interest": 5,
            "effectiveness policy": 6,
            "effectiveness report": 7,
            "program expenses": 8,
            "fundraising expenses": 9,
            "accumulating funds": 10,
            "audit report": 11,
            "detailed expense breakdown": 12,
            "accurate expense reporting": 13,
            "budget plan": 14,
            "truthful materials": 15,
            "annual report": 16,
            "website disclosures": 17,
            "donor privacy": 18,
            "cause marketing disclosures": 19,
            "complaints": 20,
        }

        met_count = 0
        not_met_count = 0

        # Method 1: Look for li.standard-item elements with CSS class status
        standard_items = soup.find_all("li", class_=re.compile(r"standard-item"))

        for item in standard_items:
            # Get standard name from .standard-name span
            name_span = item.find(class_="standard-name")
            if name_span:
                name = name_span.get_text(strip=True).lower()
            else:
                name = item.get_text(strip=True).lower()

            # Find matching standard number
            std_num = None
            for std_name, num in standard_names.items():
                if std_name in name or name in std_name:
                    std_num = num
                    break

            if std_num is None:
                continue

            # Check CSS class for pass/fail
            classes = item.get("class", [])
            class_str = " ".join(classes).lower()

            if "meets-standards" in class_str or "meets-standard" in class_str:
                data["standards_details"][f"standard_{std_num}"] = True
                data["standards_met"].append(STANDARD_NAMES.get(std_num, f"Standard {std_num}"))
                met_count += 1
            elif "does-not-meet" in class_str or "not-met" in class_str:
                data["standards_details"][f"standard_{std_num}"] = False
                data["standards_not_met"].append(STANDARD_NAMES.get(std_num, f"Standard {std_num}"))
                not_met_count += 1

        # Method 2: Fallback - look for numbered standards with status text
        if met_count == 0 and not_met_count == 0:
            standard_pattern = r"Standard\s+(\d+)[:\s]+"
            standards = soup.find_all(string=re.compile(standard_pattern, re.IGNORECASE))

            for standard_elem in standards:
                match = re.search(standard_pattern, str(standard_elem), re.IGNORECASE)
                if not match:
                    continue

                std_num = int(match.group(1))
                parent = standard_elem.parent if hasattr(standard_elem, 'parent') else None
                if parent:
                    parent_text = parent.get_text().lower()
                    if "met" in parent_text and "not met" not in parent_text:
                        data["standards_details"][f"standard_{std_num}"] = True
                        data["standards_met"].append(STANDARD_NAMES.get(std_num, f"Standard {std_num}"))
                        met_count += 1
                    elif "not met" in parent_text:
                        data["standards_details"][f"standard_{std_num}"] = False
                        data["standards_not_met"].append(STANDARD_NAMES.get(std_num, f"Standard {std_num}"))
                        not_met_count += 1

        data["standards_met_count"] = met_count
        data["standards_not_met_count"] = not_met_count

        return data

    def _extract_category_status(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract pass/fail status for each of the 4 categories.
        """
        data = {
            "governance_pass": None,
            "effectiveness_pass": None,
            "finances_pass": None,
            "solicitations_pass": None,
        }

        text = soup.get_text().lower()

        # Category keywords
        categories = {
            "governance": "governance_pass",
            "oversight": "governance_pass",
            "measuring effectiveness": "effectiveness_pass",
            "effectiveness": "effectiveness_pass",
            "finances": "finances_pass",
            "financial": "finances_pass",
            "solicitations": "solicitations_pass",
            "informational materials": "solicitations_pass",
        }

        for keyword, field in categories.items():
            if keyword in text:
                # Find the category section
                section = soup.find(text=re.compile(keyword, re.IGNORECASE))
                if section and section.parent:
                    parent_text = section.parent.get_text().lower()
                    # Look for pass/fail indicators in this section
                    if "all met" in parent_text or ("met" in parent_text and "not met" not in parent_text):
                        data[field] = True
                    elif "not met" in parent_text or "fail" in parent_text:
                        data[field] = False

        return data

    def _extract_review_date(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the date of the last BBB review.
        """
        # Look for date patterns
        date_patterns = [
            r"(?:Last|Report)\s+(?:Updated|Reviewed|Date)[:\s]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
            r"(?:as of|updated)\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]

        text = soup.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def get_standards_summary(self, profile: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of the BBB assessment.

        Args:
            profile: BBB profile dictionary

        Returns:
            Summary string
        """
        if profile.get("meets_standards") is True:
            return "Meets all 20 BBB Wise Giving Alliance Standards for Charity Accountability"
        elif profile.get("meets_standards") is False:
            met = profile.get("standards_met", 0)
            not_met = profile.get("standards_not_met", 0)
            return f"Does not meet BBB standards ({met} met, {not_met} not met)"
        else:
            return "BBB unable to verify standards compliance"

    def _extract_governance_details(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract governance details from Standards 1-5.

        Standard 1: Board oversight (CEO review, budget approval, policies)
        Standard 2: Board size (minimum 5 voting members)
        Standard 3: Board meetings (minimum 3/year, 2 in-person)
        Standard 4: Board compensation (max 1 or 10% compensated)
        Standard 5: Conflict of interest (arm's-length procedures)
        """
        data = {}
        text = soup.get_text()

        # Board size patterns
        size_patterns = [
            r"(\d+)\s+(?:voting\s+)?board\s+members?",
            r"board\s+(?:of\s+)?(\d+)\s+(?:voting\s+)?members?",
            r"(\d+)\s+member\s+board",
        ]

        for pattern in size_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    size = int(match.group(1))
                    if 3 <= size <= 50:  # Reasonable board size range
                        data["board_size"] = size
                        data["board_size_meets_standard"] = size >= 5
                        break
                except ValueError:
                    pass

        # Board meeting frequency patterns
        meeting_patterns = [
            r"(\d+)\s+(?:board\s+)?meetings?\s+(?:per\s+year|annually|each\s+year)",
            r"board\s+meets?\s+(\d+)\s+times?\s+(?:per\s+year|annually)",
            r"meets?\s+(\d+)\s+times?\s+(?:per\s+year|a\s+year)",
        ]

        for pattern in meeting_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    meetings = int(match.group(1))
                    if 1 <= meetings <= 52:  # Reasonable range
                        data["board_meetings_per_year"] = meetings
                        data["board_meetings_meets_standard"] = meetings >= 3
                        break
                except ValueError:
                    pass

        # Compensated board members patterns
        comp_patterns = [
            r"(\d+)\s+(?:compensated|paid)\s+board\s+members?",
            r"(\d+)\s+board\s+members?\s+(?:receive|are)\s+compensat",
            r"no\s+(?:compensated|paid)\s+board\s+members?",
        ]

        for pattern in comp_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if "no" in pattern:
                    data["compensated_board_members"] = 0
                    data["board_compensation_meets_standard"] = True
                else:
                    try:
                        count = int(match.group(1))
                        data["compensated_board_members"] = count
                        # Standard 4: Max 1 or 10% of board
                        board_size = data.get("board_size", 10)
                        max_allowed = max(1, int(board_size * 0.1))
                        data["board_compensation_meets_standard"] = count <= max_allowed
                    except ValueError:
                        pass
                break

        # Conflict of interest policy
        if "conflict of interest" in text.lower():
            if "has a" in text.lower() or "adopted" in text.lower() or "policy" in text.lower():
                data["conflict_of_interest_policy"] = True
            elif "does not have" in text.lower() or "no policy" in text.lower():
                data["conflict_of_interest_policy"] = False

        return data

    def _extract_financial_metrics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract financial metrics from Standards 8-14.

        Standard 8: Program expenses (min 65% of total expenses)
        Standard 9: Fundraising expenses (max 35% of contributions)
        Standard 10: Reserves (max 3x annual expenses)
        Standard 11: Audit requirements
        Standard 12: Expense breakdown in financials
        Standard 13: Accurate expense reporting
        Standard 14: Board-approved budget
        """
        data = {}
        text = soup.get_text()

        # Program expense ratio patterns
        program_patterns = [
            r"(\d+(?:\.\d+)?)\s*%\s+(?:on|for|of\s+(?:total\s+)?expenses?\s+on)\s+program",
            r"program\s+(?:expense|spending)\s+(?:ratio|percentage)[:\s]+(\d+(?:\.\d+)?)\s*%",
            r"spends?\s+(\d+(?:\.\d+)?)\s*%\s+on\s+programs?",
        ]

        for pattern in program_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    ratio = float(match.group(1))
                    if 0 <= ratio <= 100:
                        data["program_expense_ratio"] = ratio / 100.0
                        data["program_expense_meets_standard"] = ratio >= 65
                        break
                except ValueError:
                    pass

        # Fundraising expense ratio patterns
        fundraising_patterns = [
            r"(\d+(?:\.\d+)?)\s*%\s+(?:on|for)\s+fundraising",
            r"fundraising\s+(?:expense|cost)\s+(?:ratio|percentage)[:\s]+(\d+(?:\.\d+)?)\s*%",
            r"cost\s+to\s+raise\s+\$100[:\s]+\$(\d+(?:\.\d+)?)",
        ]

        for pattern in fundraising_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if "cost to raise" in pattern:
                        # Convert cost to raise $100 to percentage
                        cost = float(match.group(1))
                        ratio = cost  # Already a percentage
                    else:
                        ratio = float(match.group(1))
                    if 0 <= ratio <= 100:
                        data["fundraising_expense_ratio"] = ratio / 100.0
                        data["fundraising_expense_meets_standard"] = ratio <= 35
                        break
                except ValueError:
                    pass

        # Reserves ratio patterns (unrestricted net assets / annual expenses)
        reserves_patterns = [
            r"(\d+(?:\.\d+)?)\s+(?:years?|times)\s+(?:of\s+)?(?:annual\s+)?expenses?\s+(?:in\s+)?reserves?",
            r"reserves?\s+(?:of\s+)?(\d+(?:\.\d+)?)\s+(?:years?|times)",
            r"unrestricted\s+(?:net\s+)?assets?\s+(?:of\s+)?(\d+(?:\.\d+)?)\s+times",
        ]

        for pattern in reserves_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    ratio = float(match.group(1))
                    if 0 <= ratio <= 20:  # Reasonable range
                        data["reserves_ratio"] = ratio
                        data["reserves_meets_standard"] = ratio <= 3.0
                        break
                except ValueError:
                    pass

        # Audit status patterns
        audit_patterns = [
            (r"audited\s+financial\s+statements?", "audited"),
            (r"independent\s+audit", "audited"),
            (r"reviewed\s+financial\s+statements?", "reviewed"),
            (r"compiled\s+financial\s+statements?", "compiled"),
            (r"internally[- ]produced\s+(?:financial\s+)?statements?", "internal"),
        ]

        for pattern, status in audit_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                data["audit_status"] = status
                # Standard 11 requirements based on revenue
                data["has_required_audit"] = status in ["audited", "reviewed"]
                break

        return data

    def _extract_effectiveness_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract effectiveness data from Standards 6-7.

        Standard 6: Board-approved effectiveness policy
        Standard 7: Written effectiveness report to board
        """
        data = {}
        text = soup.get_text().lower()

        # Effectiveness policy patterns
        if "effectiveness" in text:
            if any(x in text for x in ["policy adopted", "has a policy", "board-approved policy"]):
                data["effectiveness_policy"] = True
            elif "no policy" in text or "does not have" in text:
                data["effectiveness_policy"] = False

        # Effectiveness assessment/report patterns
        assessment_patterns = [
            r"effectiveness\s+(?:assessment|evaluation|report)",
            r"measures?\s+(?:its\s+)?effectiveness",
            r"outcome\s+measurement",
        ]

        for pattern in assessment_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                data["has_effectiveness_assessment"] = True
                break

        return data

    def _extract_transparency_details(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract transparency details from Standards 15-20.

        Standard 15: Accurate materials
        Standard 16: Annual report availability
        Standard 17: Website disclosures (990, annual report)
        Standard 18: Donor privacy policy
        Standard 19: Cause marketing disclosures
        Standard 20: Complaint response
        """
        data = {}
        text = soup.get_text().lower()

        # Annual report availability
        annual_report_patterns = [
            r"annual\s+report\s+(?:is\s+)?available",
            r"provides?\s+(?:an\s+)?annual\s+report",
            r"publishes?\s+(?:an\s+)?annual\s+report",
        ]

        for pattern in annual_report_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                data["annual_report_available"] = True
                break

        # Donor privacy policy
        privacy_patterns = [
            r"donor\s+privacy\s+policy",
            r"privacy\s+policy\s+(?:for\s+)?donors?",
            r"protects?\s+donor\s+(?:information|privacy)",
        ]

        for pattern in privacy_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                data["donor_privacy_policy"] = True
                break

        # 990 available on website
        if "form 990" in text or "990 available" in text or "irs form" in text:
            if "available" in text or "website" in text or "online" in text:
                data["form_990_on_website"] = True

        # Complaint response
        complaint_patterns = [
            r"responds?\s+to\s+complaints?",
            r"complaint\s+(?:response|handling)\s+(?:policy|procedure)",
        ]

        for pattern in complaint_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                data["complaint_response_policy"] = True
                break

        return data

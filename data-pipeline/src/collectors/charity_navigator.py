"""
Charity Navigator collector using comprehensive web scraping.

Extracts ALL available data including:
- 4 Beacon scores (Impact, Accountability, Culture, Leadership)
- Detailed accountability metrics
- Financial data and ratios
- Governance information
- Tax form disclosures
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from ..llm.llm_client import LLMClient, LLMTask
from ..llm.prompt_loader import load_prompt
from ..utils.logger import PipelineLogger
from ..utils.rate_limiter import global_rate_limiter
from ..validators.charity_navigator_validator import CharityNavigatorProfile
from .base import BaseCollector, FetchResult, ParseResult


class CharityNavigatorCollector(BaseCollector):
    """
    Comprehensive Charity Navigator web scraper.

    Extracts all available data from CN profile pages without requiring API access.
    Uses LLMTask.WEBSITE_EXTRACTION for financial data extraction.
    """

    BASE_URL = "https://www.charitynavigator.org/ein"

    def __init__(
        self,
        api_key: Optional[str] = None,
        logger: Optional[PipelineLogger] = None,
        rate_limit_delay: float = 1.0,
        use_llm_extraction: bool = True,
    ):
        """
        Initialize Charity Navigator collector.

        Args:
            api_key: Ignored (kept for backward compatibility)
            logger: Logger instance
            rate_limit_delay: Seconds between requests
            use_llm_extraction: Use LLM for financial extraction (default True)
        """
        self.logger = logger
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.use_llm_extraction = use_llm_extraction

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        # Initialize LLM client if needed
        if self.use_llm_extraction:
            try:
                # Use WEBSITE_EXTRACTION task for financial extraction
                self.llm_client = LLMClient(task=LLMTask.WEBSITE_EXTRACTION, logger=logger)
                # Load prompt with versioning
                self.prompt_info = load_prompt("charity_navigator_financials")
                self.financial_prompt = self.prompt_info.content
            except Exception as e:
                self.use_llm_extraction = False
                if self.logger:
                    self.logger.warning(f"Failed to initialize LLM client: {e}")

    @property
    def source_name(self) -> str:
        return "charity_navigator"

    @property
    def schema_key(self) -> str:
        return "cn_profile"

    def _rate_limit(self):
        """Enforce rate limiting (global, thread-safe)."""
        global_rate_limiter.wait("charity_navigator", self.rate_limit_delay)

    def _log_field_extraction_report(self, profile: Dict[str, Any], ein: str):
        """
        Log detailed field extraction report.

        Args:
            profile: Extracted profile dictionary
            ein: Charity EIN for logging context
        """
        if not self.logger:
            return

        # Define critical fields
        critical_fields = {
            "name",
            "ein",
            "mission",
            "total_revenue",
            "total_expenses",
            "program_expense_ratio",
            "overall_score",
            "impact_score",
            "accountability_score",
        }

        # Count extracted vs missing
        extracted = []
        missing_critical = []
        missing_optional = []

        for key, value in profile.items():
            if value is not None and value != "" and value != []:
                # Truncate long values for display
                display_value = str(value)
                if len(display_value) > 50:
                    display_value = display_value[:47] + "..."
                extracted.append(f"  ✓ {key}: {display_value}")
            elif key in critical_fields:
                missing_critical.append(f"  ✗ {key}: MISSING (CRITICAL)")
            else:
                missing_optional.append(f"  - {key}: missing")

        total_fields = len(profile)
        extracted_count = len(extracted)
        percentage = (extracted_count / total_fields * 100) if total_fields > 0 else 0

        # Log report
        self.logger.debug("[CHARITY NAVIGATOR] Field Extraction Report:")
        for line in extracted:
            self.logger.debug(line)

        if missing_critical:
            for line in missing_critical:
                self.logger.warning(f"[{ein}]{line}")

        self.logger.debug(f"Summary: {extracted_count}/{total_fields} fields extracted ({percentage:.1f}%)")

    def fetch(self, ein: str, **kwargs) -> FetchResult:
        """
        Fetch raw HTML from Charity Navigator.

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX

        Returns:
            FetchResult with raw HTML
        """
        # Normalize EIN - remove hyphen for URL
        ein_clean = ein.replace("-", "")

        if len(ein_clean) != 9 or not ein_clean.isdigit():
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="html",
                error=f"Invalid EIN format: {ein}",
            )

        # Format for URL (no hyphen)
        url = f"{self.BASE_URL}/{ein_clean}"

        if self.logger:
            self.logger.debug(f"Fetching Charity Navigator data for EIN {ein}")

        self._rate_limit()

        try:
            response = requests.get(url, headers=self.headers, timeout=30, allow_redirects=True)

            if response.status_code == 404:
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="html",
                    error=f"Organization not found for EIN {ein}",
                )

            if response.status_code != 200:
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="html",
                    error=f"HTTP {response.status_code}",
                )

            return FetchResult(
                success=True,
                raw_data=response.text,
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

    def parse(self, raw_data: str, ein: str, **kwargs) -> ParseResult:
        """
        Parse Charity Navigator HTML into profile schema.

        Args:
            raw_data: Raw HTML from fetch()
            ein: EIN

        Returns:
            ParseResult with {"cn_profile": {...}}
        """
        try:
            soup = BeautifulSoup(raw_data, "html.parser")

            # Extract all data
            profile_data = self._extract_all_data(soup, ein, raw_data)

            # Validate with Pydantic
            try:
                profile = CharityNavigatorProfile(**profile_data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Validation error: {e}")
                return ParseResult(
                    success=False,
                    parsed_data=None,
                    error=f"Validation failed: {e}",
                )

            # Log field extraction report
            if self.logger:
                self._log_field_extraction_report(profile.model_dump(), ein)
                self.logger.debug(f"Successfully parsed CN data for {ein}")

            return ParseResult(
                success=True,
                parsed_data={self.schema_key: profile.model_dump()},
                error=None,
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"CN parse failed: {e}")
            return ParseResult(
                success=False,
                parsed_data=None,
                error=f"Parse error: {str(e)}",
            )

    def collect(self, ein: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Legacy method: fetch + parse in one call.

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX

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
            "fetch_timestamp": datetime.now().isoformat(),
        }

        return True, result, None

    def _extract_all_data(self, soup: BeautifulSoup, ein: str, html: str = None) -> Dict[str, Any]:
        """
        Extract ALL available data from the page.

        Args:
            soup: BeautifulSoup object
            ein: EIN
            html: Full HTML (for LLM extraction)

        Returns:
            Complete profile data dictionary
        """
        profile = {
            "ein": ein.replace("-", "")[:2] + "-" + ein.replace("-", "")[2:],
        }

        # 1. Extract JSON-LD structured data (basic info)
        json_ld = soup.find("script", type="application/ld+json")
        star_rating = None  # Track star rating separately
        if json_ld:
            try:
                data = json.loads(json_ld.string)
                profile["name"] = data.get("name", "Unknown")
                profile["website_url"] = data.get("url")

                # Extract star rating from review (0-4 scale)
                reviews = data.get("review", [])
                if reviews and len(reviews) > 0:
                    rating_data = reviews[0].get("reviewRating", {})
                    rating_value = rating_data.get("ratingValue")
                    if rating_value is not None:
                        star_rating = float(rating_value)
                        profile["star_rating"] = star_rating
                        # Fallback: convert stars to percentage (will be overwritten if beacon data available)
                        profile["overall_score"] = (star_rating / 4.0) * 100
            except Exception:
                pass

        # 2. Extract 4 Beacon Scores (from progress bars)
        profile.update(self._extract_beacon_scores(soup))

        # 3. Extract mission statement
        profile.update(self._extract_mission(soup))

        # 4. Extract contact information
        profile.update(self._extract_contact_info(soup))

        # 5. Extract IRS ruling year
        profile.update(self._extract_irs_info(soup))

        # 6. Extract detailed accountability metrics
        profile.update(self._extract_accountability_metrics(soup))

        # 7. Extract financial metrics from Next.js embedded data (FIRST PRIORITY)
        if html:
            nextjs_financials = self._extract_nextjs_data(html)
            for key, value in nextjs_financials.items():
                if value is not None:
                    profile[key] = value

        # 8. Try LLM extraction for any missing fields (SECOND PRIORITY)
        if html and self.use_llm_extraction:
            llm_financials = self._extract_financials_with_llm(html)
            # Merge LLM results only if field is missing
            for key, value in llm_financials.items():
                if value is not None and (key not in profile or profile.get(key) is None):
                    profile[key] = value

        # 9. Fallback to regex for any remaining missing fields (LAST RESORT)
        regex_financials = self._extract_financial_metrics(soup)
        for key, value in regex_financials.items():
            if key not in profile or profile.get(key) is None:
                profile[key] = value

        # 10. Extract beacons/badges
        profile.update(self._extract_beacons(soup))

        return profile

    def _extract_beacon_scores(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract the 4 beacon scores from progress bars."""
        beacons = {}

        # Find all beacon progress bars
        # Pattern: <div class="tw-text-lg ...">Beacon Name</div> followed by <div style="width:X%">
        beacon_mapping = {
            "Impact &amp; Measurement": "impact_score",
            "Impact & Measurement": "impact_score",
            "Accountability &amp; Finance": "accountability_score",
            "Accountability & Finance": "accountability_score",
            "Culture &amp; Community": "culture_score",
            "Culture & Community": "culture_score",
            "Leadership &amp; Adaptability": "leadership_score",
            "Leadership & Adaptability": "leadership_score",
        }

        for beacon_name, field_name in beacon_mapping.items():
            # Find the beacon name div
            beacon_div = soup.find("div", string=re.compile(beacon_name, re.I))
            if beacon_div:
                # Look for the progress bar with width percentage
                parent = beacon_div.find_parent("div", class_=re.compile("tw-flex-col"))
                if parent:
                    width_div = parent.find("div", style=re.compile(r"width:\d+%"))
                    if width_div:
                        width_match = re.search(r"width:(\d+)%", width_div.get("style", ""))
                        if width_match:
                            beacons[field_name] = float(width_match.group(1))

        return beacons

    def _extract_mission(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract mission statement from CN's Impact & Measurement section."""
        result = {}

        # Strategy 1: New CN structure - find "Mission Statement" scoring section
        # The mission follows a generic explanation about why CN tracks this metric
        for div in soup.find_all("div"):
            text = div.get_text(strip=True)
            # Look for the Mission Statement section header
            if text.startswith("Mission Statement") and "out of" in text and "points" in text:
                # Find the actual mission text - it's in a descendant div after the generic explanation
                # Skip the generic "The nonprofit organization presents evidence..." text
                for desc_div in div.find_all("div"):
                    desc_text = desc_div.get_text(strip=True)
                    # The mission is the text that doesn't start with CN's generic explanation
                    if (len(desc_text) > 50 and
                        not desc_text.startswith("Mission Statement") and
                        not desc_text.startswith("The nonprofit organization presents")):
                        result["mission"] = desc_text
                        return result

        # Strategy 2: Legacy structure - "Organization Mission" heading
        mission_heading = soup.find("div", class_="tw-font-semibold", string="Organization Mission")
        if mission_heading:
            mission_span = mission_heading.find_next_sibling("span")
            if mission_span:
                mission_text = mission_span.get_text(strip=True)
                # Remove "... (More)" suffix
                mission_text = re.sub(r"\s*\.\.\.\s*\(More\)", "", mission_text)
                result["mission"] = mission_text

        return result

    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract address, phone, etc."""
        result = {}

        # Find address in grid layout
        for grid_div in soup.find_all("div", class_=re.compile(r"tw-grid.*tw-space-y-2")):
            spans = grid_div.find_all("span")
            if len(spans) >= 2:
                # First span is street address
                result["address"] = spans[0].get_text(strip=True)

                # Second span has city, state, zip
                location = spans[1].get_text(strip=True)
                parts = location.split()
                if len(parts) >= 2:
                    result["city"] = parts[0]
                    if len(parts) >= 3:
                        result["state"] = parts[1]
                        result["zip"] = parts[2]
                break

        # Phone number
        phone_link = soup.find("a", href=re.compile(r"^tel:"))
        if phone_link:
            result["phone"] = phone_link.get_text(strip=True)

        return result

    def _extract_irs_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract IRS ruling year and 501(c)(3) status."""
        result = {}

        # Look for "IRS ruling year: YYYY"
        irs_text = soup.find(text=re.compile(r"IRS ruling year:\s*\d{4}"))
        if irs_text:
            year_match = re.search(r"IRS ruling year:\s*(\d{4})", irs_text)
            if year_match:
                result["irs_ruling_year"] = int(year_match.group(1))

        # Check for 501(c)(3) status
        if soup.find(text=re.compile(r"501\(c\)\(3\)")):
            result["irs_subsection"] = "501(c)(3)"

        return result

    def _extract_accountability_metrics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract detailed accountability metrics from the page."""
        metrics = {}

        # These are shown as expandable items with points
        # Pattern: <span>Metric Name - Details</span> ... <span>X out of Y points</span>

        # Look for all accountability metric items
        for item in soup.find_all("div", {"data-key": True}):
            key = item.get("data-key", "")

            # Find the points awarded
            points_span = item.find("span", string=re.compile(r"\d+\s+out of\s+\d+\s+points"))
            if points_span:
                points_text = points_span.get_text(strip=True)
                points_match = re.search(r"(\d+)\s+out of\s+(\d+)\s+points", points_text)
                if points_match:
                    earned = int(points_match.group(1))
                    total = int(points_match.group(2))

                    # Store in a structured way
                    metric_name = key.lower().replace(" ", "_")
                    if "accountability_metrics" not in metrics:
                        metrics["accountability_metrics"] = {}
                    metrics["accountability_metrics"][metric_name] = {
                        "earned": earned,
                        "total": total,
                        "percentage": (earned / total * 100) if total > 0 else 0,
                    }

        # Extract specific important metrics
        # Independent board members
        board_text = soup.find(text=re.compile(r"(\d+)%\s+independent members"))
        if board_text:
            pct_match = re.search(r"(\d+)%", board_text)
            if pct_match:
                metrics["independent_board_percentage"] = int(pct_match.group(1))

        # Board size
        board_size_text = soup.find(text=re.compile(r"(\d+)\s+independent members"))
        if board_size_text:
            size_match = re.search(r"(\d+)\s+independent members", board_size_text)
            if size_match:
                metrics["board_size"] = int(size_match.group(1))

        return metrics

    def _extract_nextjs_data(self, html: str) -> Dict[str, Any]:
        """
        Extract embedded Next.js data from HTML.

        Next.js embeds data in self.__next_f.push() calls in the HTML.

        Args:
            html: Full page HTML

        Returns:
            Dictionary with extracted data
        """
        try:
            # Find all self.__next_f.push() calls
            pattern = r'self\.__next_f\.push\(\[1,"(.*?)"\]\)'
            matches = re.findall(pattern, html)

            if not matches:
                if self.logger:
                    self.logger.warning("No Next.js data found in HTML")
                return {}

            # Find the one containing financial metrics
            for match in matches:
                if "calc_fund_eff_ratio" in match or "ratioValue" in match:
                    # Unescape the JSON string
                    try:
                        # Decode unicode escapes
                        decoded = match.encode().decode("unicode_escape")

                        # Extract financial metrics using regex
                        metrics = {}

                        # Fundraising efficiency (CURRENCY type, value like 0.15)
                        fund_eff_match = re.search(
                            r'"slug":"calc_fund_eff_ratio"[^}]*"ratioValue":([0-9.]+),"ratioType":"CURRENCY"', decoded
                        )
                        if fund_eff_match:
                            metrics["fundraising_efficiency"] = float(fund_eff_match.group(1))

                        # Working capital ratio (YEARS type from CN, value like 0.5 = 6 months)
                        # Convert to MONTHS for consistency with scorers that expect months
                        work_cap_match = re.search(
                            r'"slug":"calc_wkg_cap_ratio"[^}]*"ratioValue":([0-9.]+),"ratioType":"YEARS"', decoded
                        )
                        if work_cap_match:
                            years = float(work_cap_match.group(1))
                            metrics["working_capital_ratio"] = years * 12  # Convert years to months

                        # Program expense ratio (PERCENTAGE type, value like 78.43)
                        prog_exp_match = re.search(
                            r'"slug":"avg_program_expense_ratio"[^}]*"ratioValue":([0-9.]+),"ratioType":"PERCENTAGE"',
                            decoded,
                        )
                        if prog_exp_match:
                            metrics["program_expense_ratio"] = float(prog_exp_match.group(1)) / 100

                        # Admin expense ratio
                        admin_exp_match = re.search(
                            r'"slug":"avg_admin_expense_ratio"[^}]*"ratioValue":([0-9.]+),"ratioType":"PERCENTAGE"',
                            decoded,
                        )
                        if admin_exp_match:
                            metrics["admin_expense_ratio"] = float(admin_exp_match.group(1)) / 100

                        # Fundraising expense ratio
                        fund_exp_match = re.search(
                            r'"slug":"avg_fundraising_expense_ratio"[^}]*"ratioValue":([0-9.]+),"ratioType":"PERCENTAGE"',
                            decoded,
                        )
                        if fund_exp_match:
                            metrics["fundraising_expense_ratio"] = float(fund_exp_match.group(1)) / 100

                        # Extract all 4 beacon scores from Charity Navigator's new rating system
                        # 1. Accountability & Finance -> financial_score
                        fin_score_match = re.search(r'"slug":"accountability_finance"[^}]*?"score":([0-9]+)', decoded)
                        if fin_score_match:
                            metrics["financial_score"] = float(fin_score_match.group(1))
                            metrics["accountability_score"] = float(fin_score_match.group(1))  # Same score

                        # 2. Impact & Measurement -> impact_score
                        impact_match = re.search(r'"slug":"impact_measurement"[^}]*?"score":([0-9]+)', decoded)
                        if impact_match:
                            metrics["impact_score"] = float(impact_match.group(1))

                        # 3. Culture & Community -> culture_score
                        culture_match = re.search(r'"slug":"culture_community"[^}]*?"score":([0-9]+)', decoded)
                        if culture_match:
                            metrics["culture_score"] = float(culture_match.group(1))

                        # 4. Leadership & Adaptability -> leadership_score
                        leadership_match = re.search(r'"slug":"leadership_adaptability"[^}]*?"score":([0-9]+)', decoded)
                        if leadership_match:
                            metrics["leadership_score"] = float(leadership_match.group(1))

                        # Total revenue
                        revenue_match = re.search(r'"totalRevenue":([0-9.]+)', decoded)
                        if revenue_match:
                            metrics["total_revenue"] = float(revenue_match.group(1))

                        # Total expenses (note: singular "totalExpense" in JSON)
                        expenses_match = re.search(r'"totalExpense":([0-9.]+)', decoded)
                        if expenses_match:
                            metrics["total_expenses"] = float(expenses_match.group(1))

                        # Program expenses (exact dollar amount)
                        prog_exp_match = re.search(r'"totalProgramExpense":([0-9.]+)', decoded)
                        if prog_exp_match:
                            metrics["program_expenses"] = float(prog_exp_match.group(1))

                        # Fundraising expenses (exact dollar amount)
                        fund_exp_match = re.search(r'"totalFundraisingExpense":([0-9.]+)', decoded)
                        if fund_exp_match:
                            metrics["fundraising_expenses"] = float(fund_exp_match.group(1))

                        # Admin expenses (exact dollar amount)
                        admin_exp_match = re.search(r'"totalAdministrativeExpense":([0-9.]+)', decoded)
                        if admin_exp_match:
                            metrics["admin_expenses"] = float(admin_exp_match.group(1))

                        # Fiscal year (extract from taxPeriodEndDate like "2023-12-31T00:00:00.000Z")
                        fy_match = re.search(r'"taxPeriodEndDate":"([0-9]{4})-', decoded)
                        if fy_match:
                            metrics["fiscal_year"] = int(fy_match.group(1))

                        # CEO/President name and compensation from keyPersons
                        ceo_match = re.search(
                            r'"keyPersons":\[.*?"name":"([^"]+)","title":"(President|CEO|Executive Director|Chief Executive)[^"]*","compensationReportable":([0-9]+)',
                            decoded,
                            re.DOTALL,
                        )
                        if ceo_match:
                            metrics["ceo_name"] = ceo_match.group(1)
                            metrics["ceo_compensation"] = float(ceo_match.group(3))

                        # Admin expense ratio (calculate from dollar amounts if available)
                        if metrics.get("admin_expenses") and metrics.get("total_expenses"):
                            metrics["admin_expense_ratio"] = metrics["admin_expenses"] / metrics["total_expenses"]

                        # Extract address fields (city, state, zip) from addressPhysical
                        address_match = re.search(
                            r'"addressPhysical":\{"type":"physical","street":"[^"]*","street2":[^,]*,"city":"([^"]*)","state":"([^"]*)","zip":"([^"]*)"',
                            decoded,
                        )
                        if address_match:
                            metrics["city"] = address_match.group(1)
                            metrics["state"] = address_match.group(2)
                            metrics["zip"] = address_match.group(3)

                        # IRS Ruling Year
                        ruling_match = re.search(r'"rulingYear":"([0-9]{4})"', decoded)
                        if ruling_match:
                            metrics["irs_ruling_year"] = int(ruling_match.group(1))

                        # Calculate overall_score from beacon scores if available
                        # CN uses 4 beacons: Impact, Accountability (Finance), Culture, Leadership
                        beacon_scores = {}
                        for key in ["impact_score", "accountability_score", "culture_score", "leadership_score"]:
                            if metrics.get(key) is not None:
                                beacon_scores[key] = metrics[key]

                        # Encompass Award = culture_score only, not a full rating
                        is_encompass_only = "culture_score" in beacon_scores and len(beacon_scores) == 1
                        has_financial = "accountability_score" in beacon_scores

                        # Rated = at least 2 beacons including financial, OR all 4
                        is_fully_rated = (len(beacon_scores) >= 2 and has_financial) or len(beacon_scores) == 4

                        if beacon_scores:
                            # Average of available beacon scores
                            metrics["overall_score"] = sum(beacon_scores.values()) / len(beacon_scores)
                            metrics["cn_is_rated"] = is_fully_rated
                            metrics["cn_has_encompass_award"] = is_encompass_only
                            metrics["cn_beacon_count"] = len(beacon_scores)
                            if self.logger:
                                self.logger.debug(
                                    f"Calculated overall_score={metrics['overall_score']:.1f} "
                                    f"from {len(beacon_scores)} beacon scores "
                                    f"(rated={is_fully_rated}, encompass_only={is_encompass_only})"
                                )
                        else:
                            # No beacon data - charity may not be fully rated
                            metrics["cn_is_rated"] = False
                            metrics["cn_has_encompass_award"] = False
                            metrics["cn_beacon_count"] = 0

                        if self.logger and metrics:
                            self.logger.debug(f"Extracted {len(metrics)} financial metrics from Next.js data")

                        return metrics

                    except Exception as e:
                        if self.logger:
                            self.logger.warning(f"Error parsing Next.js data: {e}")
                        continue

            return {}

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Next.js data extraction failed: {e}")
            return {}

    def _extract_financials_with_llm(self, html: str) -> Dict[str, Any]:
        """
        Extract financial data using LLM.

        Args:
            html: Full page HTML

        Returns:
            Dictionary with financial fields
        """
        if not self.use_llm_extraction:
            return {}

        try:
            # Prepare prompt
            prompt = (
                f"{self.financial_prompt}\n\nExtract financial data from this Charity Navigator HTML:\n\n{html[:50000]}"
            )

            # Generate using LLMClient (CHEAPEST tier)
            llm_response = self.llm_client.generate(prompt=prompt, temperature=0.1, max_tokens=1000, json_mode=True)

            response_text = llm_response.text

            # Parse JSON response
            try:
                # Handle markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()

                financials = json.loads(response_text)

                # C-004: Validate plausibility of LLM-extracted financial figures
                financials = self._validate_llm_financials(financials)

                if self.logger:
                    found_fields = [k for k, v in financials.items() if v is not None]
                    self.logger.debug(f"LLM extracted {len(found_fields)} financial fields")
                return financials
            except json.JSONDecodeError:
                if self.logger:
                    self.logger.warning("LLM response was not valid JSON")
                return {}

        except Exception as e:
            if self.logger:
                self.logger.warning(f"LLM financial extraction failed: {e}")
            return {}

    def _validate_llm_financials(self, financials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate plausibility of LLM-extracted financial figures.

        C-004 fix: LLM can hallucinate wildly implausible values.
        This filters out values that are clearly wrong.

        Validation rules:
        - Revenue/expenses/assets must be non-negative
        - Revenue should not exceed $100B (largest US nonprofits)
        - Ratios must be between 0 and 1 (or 0-100 if percentages)
        - Fiscal year must be reasonable (1900-2030)
        """
        validated = {}

        # Maximum plausible values (largest US nonprofits are ~$50B)
        max_financial_value = 100_000_000_000  # $100B
        min_financial_value = 0

        financial_fields = [
            "total_revenue", "total_expenses", "total_assets",
            "program_expenses", "admin_expenses", "fundraising_expenses",
            "total_contributions", "net_assets",
        ]

        ratio_fields = [
            "program_expense_ratio", "admin_expense_ratio",
            "fundraising_expense_ratio", "liabilities_to_assets_ratio",
        ]

        for key, value in financials.items():
            if value is None:
                validated[key] = None
                continue

            # Validate financial amounts
            if key in financial_fields:
                try:
                    num_value = float(value)
                    if min_financial_value <= num_value <= max_financial_value:
                        validated[key] = num_value
                    else:
                        if self.logger:
                            self.logger.warning(
                                f"LLM financial value out of range: {key}={value} (rejected)"
                            )
                        validated[key] = None
                except (ValueError, TypeError):
                    validated[key] = None

            # Validate ratios (should be 0-1 or 0-100)
            elif key in ratio_fields:
                try:
                    num_value = float(value)
                    # Convert percentages to decimals if needed
                    if num_value > 1:
                        num_value = num_value / 100
                    if 0 <= num_value <= 1:
                        validated[key] = num_value
                    else:
                        if self.logger:
                            self.logger.warning(
                                f"LLM ratio out of range: {key}={value} (rejected)"
                            )
                        validated[key] = None
                except (ValueError, TypeError):
                    validated[key] = None

            # Validate fiscal year
            elif key == "fiscal_year":
                try:
                    year = int(value)
                    if 1900 <= year <= 2030:
                        validated[key] = year
                    else:
                        validated[key] = None
                except (ValueError, TypeError):
                    validated[key] = None

            # Pass through other fields unchanged
            else:
                validated[key] = value

        return validated

    def _extract_financial_metrics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract financial data and ratios using regex (fallback)."""
        financials = {}

        # Look for fiscal year
        fy_text = soup.find(text=re.compile(r"FY\s*\d{4}"))
        if fy_text:
            year_match = re.search(r"FY\s*(\d{4})", fy_text)
            if year_match:
                financials["fiscal_year"] = int(year_match.group(1))

        # Financial data is often in the accountability section
        # Look for specific financial metric patterns in the HTML
        page_text = soup.get_text()

        # Program expense ratio
        prog_match = re.search(r"program.*?(\d+\.?\d*)%", page_text, re.I)
        if prog_match:
            financials["program_expense_ratio"] = float(prog_match.group(1)) / 100

        # Admin expense ratio
        admin_match = re.search(r"admin.*?(\d+\.?\d*)%", page_text, re.I)
        if admin_match:
            financials["admin_expense_ratio"] = float(admin_match.group(1)) / 100

        # Fundraising expense ratio
        fund_match = re.search(r"fundraising.*?(\d+\.?\d*)%", page_text, re.I)
        if fund_match:
            financials["fundraising_expense_ratio"] = float(fund_match.group(1)) / 100

        return financials

    def _extract_beacons(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract special beacons/badges.

        Note: "Encompass" is NOT an award - it's just CN's name for their rating system.
        We only extract actual badges/certifications here.
        """
        beacons_list = []

        # Seal of approval (actual certification)
        if soup.find(text=re.compile(r"Seal of Approval", re.I)):
            beacons_list.append("Seal of Approval")

        # Profile managed by nonprofit (informational, not an award)
        if soup.find(text=re.compile(r"Profile managed by nonprofit", re.I)):
            beacons_list.append("Profile Managed")

        return {"beacons": beacons_list} if beacons_list else {}

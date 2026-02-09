"""
CauseIQ collector using BeautifulSoup for deterministic extraction.

This collector fetches CauseIQ nonprofit profiles and extracts detailed program descriptions,
grantmaking data, and financial information using HTML parsing.

CauseIQ provides uniquely detailed data including:
- Program descriptions with beneficiary counts and geographic breakdowns
- Grants made to other organizations
- Grants received from foundations
- Financial trends and metrics
"""

import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from ..utils.logger import PipelineLogger
from ..validators.causeiq_validator import CauseIQProfile

# Load environment variables from .env file
load_dotenv()


class CauseIQCollector:
    """
    Collect CauseIQ nonprofit profile data using deterministic BeautifulSoup parsing.

    CauseIQ URLs follow the pattern: /organizations/{slug},{ein}/
    Example: /organizations/islamic-relief-usa,954453134/

    The slug is generated from the organization name or can be provided explicitly.
    """

    BASE_URL = "https://www.causeiq.com"

    def __init__(
        self,
        logger: Optional[PipelineLogger] = None,
        rate_limit_delay: float = 10.0,
        timeout: int = 30,
        save_debug_html: bool = False,
        debug_dir: Optional[str] = None,
    ):
        """
        Initialize CauseIQ collector.

        Args:
            logger: Logger instance
            rate_limit_delay: Seconds to wait between requests (default 10.0)
                             CauseIQ has aggressive rate limiting (~10 requests/burst even for authenticated users)
            timeout: Request timeout in seconds
            save_debug_html: If True, save fetched HTML for debugging
            debug_dir: Directory to save debug HTML files (default: ./causeiq_debug)
        """
        self.logger = logger
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time = 0
        self.save_debug_html = save_debug_html
        self.debug_dir = Path(debug_dir) if debug_dir else Path("./causeiq_debug")

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

        # Initialize session for persistent authentication
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.authenticated = False

        # Try to login if credentials are provided
        self._login()

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            if self.logger:
                self.logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _login(self) -> bool:
        """
        Attempt to login to CauseIQ using credentials from environment variables.

        Returns:
            True if login successful or no credentials provided, False on error
        """
        # Get credentials from environment
        email = os.getenv("CAUSEIQ_EMAIL")
        password = os.getenv("CAUSEIQ_PASSWORD")

        # Skip login if no credentials
        if not email or not password or email == "your-email@example.com":
            if self.logger:
                self.logger.debug(
                    "No CauseIQ credentials provided, skipping login (100 free views/month limit applies)"
                )
            return True

        try:
            if self.logger:
                self.logger.debug("Logging in to CauseIQ...")

            # Get login page to extract CSRF token
            login_url = f"{self.BASE_URL}/accounts/login/"
            response = self.session.get(login_url, timeout=self.timeout)

            if response.status_code != 200:
                if self.logger:
                    self.logger.warning(f"Failed to fetch login page: HTTP {response.status_code}")
                return False

            # Parse login page to extract CSRF token
            soup = BeautifulSoup(response.text, "html.parser")
            csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})

            if not csrf_input:
                if self.logger:
                    self.logger.warning("Could not find CSRF token on login page")
                return False

            csrf_token = csrf_input.get("value")

            # Prepare login data
            login_data = {
                "login": email,
                "password": password,
                "csrfmiddlewaretoken": csrf_token,
            }

            # Add Referer header for Django CSRF protection
            headers = {
                "Referer": login_url,
                "Origin": self.BASE_URL,
            }

            # Submit login form
            login_response = self.session.post(
                login_url,
                data=login_data,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True,
            )

            # Check if login was successful
            # Successful login should redirect to homepage or profile
            if login_response.status_code == 200:
                # Check if we're logged in by looking for user-specific elements
                if "logout" in login_response.text.lower() or "account" in login_response.text.lower():
                    self.authenticated = True
                    if self.logger:
                        self.logger.debug("Successfully logged in to CauseIQ")
                    return True
                else:
                    if self.logger:
                        self.logger.warning("Login form submitted but authentication unclear")
                    return False
            else:
                if self.logger:
                    self.logger.warning(f"Login failed: HTTP {login_response.status_code}")
                return False

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Login error: {e}")
            return False

    def _generate_slug(self, org_name: str) -> str:
        """
        Generate CauseIQ URL slug from organization name.

        Converts "Islamic Relief USA" → "islamic-relief-usa"

        Args:
            org_name: Organization name

        Returns:
            Slug for CauseIQ URL
        """
        # Convert to lowercase
        slug = org_name.lower()
        # Remove common suffixes
        slug = re.sub(r"\b(inc\.?|incorporated|llc|corp\.?|corporation|foundation|fund)\b", "", slug)
        # Replace special characters with spaces
        slug = re.sub(r"[^a-z0-9\s-]", " ", slug)
        # Replace multiple spaces with single space
        slug = re.sub(r"\s+", " ", slug)
        # Trim and replace spaces with hyphens
        slug = slug.strip().replace(" ", "-")
        # Remove multiple consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        return slug

    def _extract_organization_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract organization name from H1."""
        h1 = soup.find("h1", class_="text-red")
        if h1:
            return h1.get_text(strip=True)
        return None

    def _extract_ein(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract EIN from page."""
        # Look for EIN in the header section
        ein_div = soup.find("div", class_="text-muted", string=re.compile(r"EIN\s+\d{2}-\d{7}"))
        if ein_div:
            ein_text = ein_div.get_text(strip=True)
            match = re.search(r"(\d{2}-\d{7})", ein_text)
            if match:
                return match.group(1)
        return None

    def _extract_quick_fields(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract quick fields from the header section.

        Returns dict with: irs_subsection, num_employees, city, state, year_founded, ntee_code
        """
        fields = {}
        quick_fields = soup.find("div", class_="quick-fields")
        if quick_fields:
            items = quick_fields.find_all("div", class_="quick-field-item")
            for item in items:
                label_div = item.find("div", class_="qf-label")
                value_div = item.find("div", class_="qf-value")
                if label_div and value_div:
                    label = label_div.get_text(strip=True).lower()
                    value = value_div.get_text(strip=True)

                    if "501(c)" in label:
                        fields["irs_subsection"] = value
                    elif "employees" in label:
                        try:
                            fields["num_employees"] = int(value.replace(",", ""))
                        except ValueError:
                            pass
                    elif "city" in label:
                        fields["city"] = value
                    elif "state" in label:
                        fields["state"] = value
                    elif "year formed" in label:
                        try:
                            fields["year_founded"] = int(value)
                        except ValueError:
                            pass
                    elif "ntee" in label:
                        # Extract NTEE code and description
                        ntee_match = re.match(r"([A-Z]\d+):\s*(.+)", value)
                        if ntee_match:
                            fields["ntee_code"] = ntee_match.group(1)
                            fields["ntee_description"] = ntee_match.group(2)
        return fields

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract organization description."""
        # Description is in a lead paragraph within the first row
        desc_elem = soup.find("div", class_="lead")
        if desc_elem:
            return desc_elem.get_text(strip=True)
        return None

    def _extract_programs(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract detailed program descriptions with beneficiary counts.

        CauseIQ provides extensive program narratives with:
        - Program area name (e.g., "Food security and livelihoods")
        - Detailed description with examples, locations, beneficiary counts
        """
        programs = []
        programs_section = soup.find("div", id="programs")
        if programs_section:
            # Each program is in a div with class "m-b-md"
            program_divs = programs_section.find_all("div", class_="m-b-md")
            for div in program_divs:
                text = div.get_text(separator=" ", strip=True)
                # Program name is usually at the start before ":"
                if ":" in text:
                    parts = text.split(":", 1)
                    program_name = parts[0].strip()
                    program_desc = parts[1].strip()
                else:
                    program_name = "General Program"
                    program_desc = text

                # Extract beneficiary count if present
                beneficiaries = None
                beneficiary_match = re.search(r"[Bb]eneficiaries?:\s*approximately\s*([\d,]+)", program_desc)
                if beneficiary_match:
                    try:
                        beneficiaries = int(beneficiary_match.group(1).replace(",", ""))
                    except ValueError:
                        pass

                programs.append(
                    {
                        "name": program_name,
                        "description": program_desc[:2000],  # Limit length
                        "beneficiaries": beneficiaries,
                    }
                )
        return programs

    def _extract_grants_made(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract grants made to other organizations."""
        grants = []
        grantmaking_section = soup.find("div", id="grantmaking")
        if grantmaking_section:
            table = grantmaking_section.find("table")
            if table:
                rows = table.find("tbody").find_all("tr") if table.find("tbody") else []
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 4:
                        grantee_elem = cells[0].find("a")
                        grantee_name = (
                            grantee_elem.get_text(strip=True) if grantee_elem else cells[0].get_text(strip=True)
                        )
                        description = cells[1].get_text(strip=True)
                        year_text = cells[2].get_text(strip=True)
                        amount_text = cells[3].get_text(strip=True)

                        # Parse amount
                        amount = None
                        amount_match = re.search(r"\$([\d,]+)", amount_text)
                        if amount_match:
                            try:
                                amount = float(amount_match.group(1).replace(",", ""))
                            except ValueError:
                                pass

                        # Parse year
                        year = None
                        year_match = re.search(r"(\d{4})", year_text)
                        if year_match:
                            try:
                                year = int(year_match.group(1))
                            except ValueError:
                                pass

                        grants.append(
                            {
                                "grantee_name": grantee_name,
                                "description": description,
                                "amount": amount,
                                "year": year,
                            }
                        )
        return grants

    def _extract_grants_received(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract grants received from foundations and other nonprofits."""
        grants = []
        funding_section = soup.find("div", id="funding")
        if funding_section:
            table = funding_section.find("table")
            if table:
                rows = table.find("tbody").find_all("tr") if table.find("tbody") else []
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 4:
                        grantor_elem = cells[0].find("a")
                        grantor_name = (
                            grantor_elem.get_text(strip=True) if grantor_elem else cells[0].get_text(strip=True)
                        )
                        year_text = cells[1].get_text(strip=True)
                        description = cells[2].get_text(strip=True)
                        amount_text = cells[3].get_text(strip=True)

                        # Parse amount
                        amount = None
                        amount_match = re.search(r"\$([\d,]+)", amount_text)
                        if amount_match:
                            try:
                                amount = float(amount_match.group(1).replace(",", ""))
                            except ValueError:
                                pass

                        # Parse year
                        year = None
                        year_match = re.search(r"(\d{4})", year_text)
                        if year_match:
                            try:
                                year = int(year_match.group(1))
                            except ValueError:
                                pass

                        grants.append(
                            {
                                "grantor_name": grantor_name,
                                "description": description,
                                "amount": amount,
                                "year": year,
                            }
                        )
        return grants

    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract contact information from dt/dd definition lists."""
        contact = {}

        # Find all dt/dd pairs
        dt_elements = soup.find_all("dt")
        for dt in dt_elements:
            label = dt.get_text(strip=True).lower()
            dd = dt.find_next_sibling("dd")

            if not dd:
                continue

            if "address" in label:
                contact["address"] = dd.get_text(strip=True)
            elif "phone" in label:
                contact["phone"] = dd.get_text(strip=True)
            elif "website url" in label or "website" == label:
                # Get link href if available
                link = dd.find("a")
                if link and link.get("href"):
                    contact["website_url"] = link.get("href")
                else:
                    contact["website_url"] = dd.get_text(strip=True)
                # Ensure it has protocol
                if contact.get("website_url") and not contact["website_url"].startswith("http"):
                    contact["website_url"] = f"https://{contact['website_url']}"

        return contact

    def _extract_personnel(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract personnel information from the Personnel section."""
        personnel = {
            "key_personnel": [],
            "board_members": [],
        }

        # Find Personnel section
        personnel_section = soup.find("h2", string=lambda t: t and "Personnel" in str(t))
        if not personnel_section:
            return personnel

        # Find the table in the personnel section
        parent = personnel_section.find_parent()
        if not parent:
            return personnel

        table = parent.find("table")
        if not table:
            return personnel

        # Extract rows (skip header)
        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 3:  # Name, Title, Compensation
                name = cols[0].get_text(strip=True)
                title = cols[1].get_text(strip=True)
                compensation_text = cols[2].get_text(strip=True)

                # Parse compensation
                compensation = None
                if compensation_text and compensation_text != "-":
                    comp_match = re.search(r"\$([\d,]+)", compensation_text)
                    if comp_match:
                        try:
                            compensation = float(comp_match.group(1).replace(",", ""))
                        except ValueError:
                            pass

                person = {
                    "name": name,
                    "title": title,
                }
                if compensation is not None:
                    person["compensation"] = compensation

                # Classify as board member or key personnel based on title
                title_lower = title.lower()
                if any(term in title_lower for term in ["board", "director", "trustee"]):
                    personnel["board_members"].append(person)
                else:
                    personnel["key_personnel"].append(person)

        return personnel

    def _extract_financial_kpis(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract financial KPIs from the dashboard section."""
        financials = {}

        # Find KPI containers
        kpi_revenue = soup.find("div", id="kpi_rev_total")
        kpi_expenses = soup.find("div", id="kpi_exp_total")
        kpi_assets = soup.find("div", id="kpi_ass_total")

        def extract_kpi_value(kpi_elem):
            if kpi_elem:
                value_div = kpi_elem.find("div", class_="kpi-value")
                if value_div:
                    value_text = value_div.get_text(strip=True)
                    # Parse "$165,235,589" → 165235589.0
                    value_match = re.search(r"\$([\d,]+)", value_text)
                    if value_match:
                        try:
                            return float(value_match.group(1).replace(",", ""))
                        except ValueError:
                            pass
            return None

        financials["total_revenue"] = extract_kpi_value(kpi_revenue)
        financials["total_expenses"] = extract_kpi_value(kpi_expenses)
        financials["total_assets"] = extract_kpi_value(kpi_assets)

        # Extract total_liabilities from Financials section
        financials_section = soup.find("h2", string=lambda t: t and "Financials" in str(t))
        if financials_section:
            parent = financials_section.find_parent()
            if parent:
                text = parent.get_text()
                # Look for "Liabilities: $XXX" pattern
                liab_match = re.search(r"Liabilities[:\s]+\$?([\d,]+)", text, re.IGNORECASE)
                if liab_match:
                    try:
                        financials["total_liabilities"] = float(liab_match.group(1).replace(",", ""))
                    except ValueError:
                        pass

                # Look for program expense ratio
                prog_exp_match = re.search(r"Program\s+expense\s+ratio[:\s]+([\d.]+)%?", text, re.IGNORECASE)
                if prog_exp_match:
                    try:
                        ratio = float(prog_exp_match.group(1))
                        # If it's a percentage, convert to decimal
                        if ratio > 1:
                            ratio = ratio / 100
                        financials["program_expense_ratio"] = ratio
                    except ValueError:
                        pass

        return financials

    def _log_field_extraction_report(self, profile: Dict[str, Any]):
        """Log detailed field extraction report."""
        if not self.logger:
            return

        critical_fields = ["ein", "organization_name"]
        high_value_fields = ["programs", "grants_made", "grants_received"]
        optional_fields = [
            "mission",
            "total_revenue",
            "total_expenses",
            "total_assets",
            "year_founded",
            "ntee_code",
        ]

        # Count extracted fields
        total_fields = len(critical_fields) + len(high_value_fields) + len(optional_fields)
        extracted = 0
        missing = []

        for field in critical_fields + high_value_fields + optional_fields:
            value = profile.get(field)
            if value:
                if isinstance(value, list) and len(value) > 0:
                    extracted += 1
                elif not isinstance(value, list):
                    extracted += 1
                else:
                    missing.append(field)
            else:
                missing.append(field)

        extraction_rate = (extracted / total_fields) * 100

        self.logger.debug(f"CauseIQ extraction: {extracted}/{total_fields} fields ({extraction_rate:.1f}%)")
        self.logger.debug(f"  Programs: {len(profile.get('programs', []))}")
        self.logger.debug(f"  Grants made: {len(profile.get('grants_made', []))}")
        self.logger.debug(f"  Grants received: {len(profile.get('grants_received', []))}")

        if missing:
            self.logger.debug(f"  Missing fields: {', '.join(missing[:5])}")

    def collect(
        self, ein: str, org_name: Optional[str] = None, slug: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Collect CauseIQ data for a charity.

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX
            org_name: Optional organization name to generate slug
            slug: Optional pre-computed slug (e.g., "islamic-relief-usa")

        Returns:
            Tuple of (success, data, error_message)
            data contains:
                - causeiq_profile: Validated CauseIQProfile dict
                - raw_html: Full HTML
                - fetch_timestamp: When fetched
        """
        # Normalize EIN to XX-XXXXXXX format
        ein_clean = ein.replace("-", "").replace(" ", "")

        if len(ein_clean) != 9 or not ein_clean.isdigit():
            return False, None, f"Invalid EIN format: {ein}"

        ein_formatted = f"{ein_clean[:2]}-{ein_clean[2:]}"

        # Generate slug if not provided
        if not slug:
            if not org_name:
                return False, None, "Either org_name or slug must be provided for CauseIQ"
            slug = self._generate_slug(org_name)
            if self.logger:
                self.logger.debug(f"Generated slug '{slug}' from org name '{org_name}'")

        # Construct URL
        url = f"{self.BASE_URL}/organizations/{slug},{ein_clean}/"
        if self.logger:
            self.logger.debug(f"Fetching CauseIQ profile for EIN {ein_formatted}")

        # Rate limiting
        self._rate_limit()

        try:
            # Fetch HTML using authenticated session
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
            )

            if response.status_code == 404:
                return False, None, f"Profile not found for EIN {ein_formatted} (slug: {slug})"

            if response.status_code != 200:
                return False, None, f"HTTP {response.status_code}"

            html_content = response.text

            # Basic validation - check for CauseIQ
            if "causeiq" not in html_content.lower():
                return False, None, "Response doesn't appear to be from CauseIQ"

            # Check for rate limit / paywall
            if "reached your limit" in html_content.lower() or "create a free account" in html_content.lower():
                error_msg = (
                    "⚠️  CAUSEIQ RATE LIMIT EXCEEDED ⚠️\n"
                    "You've hit the 100 free profile views/month limit.\n"
                    "Solutions:\n"
                    "  1. Create a free CauseIQ account at https://www.causeiq.com/accounts/signup/\n"
                    "  2. Add credentials to .env file: CAUSEIQ_EMAIL and CAUSEIQ_PASSWORD\n"
                    "  3. Wait for monthly reset"
                )
                if self.logger:
                    self.logger.error(error_msg)
                return False, None, error_msg

            # Save debug HTML if requested
            if self.save_debug_html:
                debug_file = self.debug_dir / f"causeiq-{ein_formatted}.html"
                try:
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    if self.logger:
                        self.logger.debug(f"Saved debug HTML to {debug_file}")
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Failed to save debug HTML: {e}")

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            # Extract all fields
            org_name_extracted = self._extract_organization_name(soup)
            ein_extracted = self._extract_ein(soup)
            quick_fields = self._extract_quick_fields(soup)
            description = self._extract_description(soup)
            programs = self._extract_programs(soup)
            grants_made = self._extract_grants_made(soup)
            grants_received = self._extract_grants_received(soup)
            financials = self._extract_financial_kpis(soup)
            contact_info = self._extract_contact_info(soup)
            personnel = self._extract_personnel(soup)

            # Extract program area names
            program_areas = [p["name"] for p in programs if p.get("name")]

            # Calculate totals from grant lists
            total_grants_made = sum(g.get("amount", 0) for g in grants_made if g.get("amount"))
            total_grants_received = sum(g.get("amount", 0) for g in grants_received if g.get("amount"))

            # Calculate board size
            board_size = len(personnel.get("board_members", []))

            # Build profile data
            profile_data = {
                "organization_name": org_name_extracted or org_name or "Unknown",
                "ein": ein_extracted or ein_formatted,
                "description": description,
                "mission": description,  # CauseIQ description serves as mission
                "programs": programs,
                "program_areas": program_areas,
                "grants_made": grants_made,
                "grants_received": grants_received,
                "total_grants_made": total_grants_made if total_grants_made > 0 else None,
                "total_grants_received": total_grants_received if total_grants_received > 0 else None,
                "total_revenue": financials.get("total_revenue"),
                "total_expenses": financials.get("total_expenses"),
                "total_assets": financials.get("total_assets"),
                "total_liabilities": financials.get("total_liabilities"),
                "program_expense_ratio": financials.get("program_expense_ratio"),
                "year_founded": quick_fields.get("year_founded"),
                "ntee_code": quick_fields.get("ntee_code"),
                "ntee_description": quick_fields.get("ntee_description"),
                "irs_subsection": quick_fields.get("irs_subsection"),
                "number_of_employees": quick_fields.get("num_employees"),
                "city": quick_fields.get("city"),
                "state": quick_fields.get("state"),
                "address": contact_info.get("address"),
                "phone": contact_info.get("phone"),
                "website_url": contact_info.get("website_url"),
                "key_personnel": personnel.get("key_personnel"),
                "board_members": personnel.get("board_members"),
                "board_size": board_size if board_size > 0 else None,
                "causeiq_url": url,
                "slug": slug,
            }

            # Validate with Pydantic
            try:
                profile = CauseIQProfile(**profile_data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Validation error: {e}")
                    self.logger.debug(f"Profile data: {profile_data}")
                return False, None, f"Validation failed: {e}"

            result = {
                "causeiq_profile": profile.model_dump(),
                "raw_html": html_content,
                "fetch_timestamp": datetime.now().isoformat(),
            }

            # Log field extraction report
            if self.logger:
                self._log_field_extraction_report(profile.model_dump())
                self.logger.debug(f"Successfully collected CauseIQ data for {ein_formatted}")

            return True, result, None

        except requests.Timeout:
            return False, None, f"Request timeout after {self.timeout}s"
        except requests.RequestException as e:
            return False, None, f"Request failed: {str(e)}"
        except Exception as e:
            if self.logger:
                self.logger.exception("Unexpected error in CauseIQ collection")
            return False, None, f"Unexpected error: {str(e)}"

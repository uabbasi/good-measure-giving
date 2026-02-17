"""
Form 990 Grants collector using ProPublica XML downloads.

Fetches IRS Form 990 XML files from ProPublica and extracts Schedule I (domestic grants)
and Schedule F (foreign grants) data. This replaces CauseIQ for grants data.

Data flow:
1. Fetch organization page from ProPublica to get latest filing object_id
2. Download 990 XML file using object_id (with aggressive caching - 990s never change)
3. Parse Schedule I (grants to domestic organizations)
4. Parse Schedule F (grants to foreign organizations)
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from ..utils.logger import PipelineLogger
from ..utils.rate_limiter import global_rate_limiter
from ..validators.form990_grants_validator import Form990GrantsProfile
from .base import BaseCollector, FetchResult, ParseResult

# Default cache directory for 990 XML files
DEFAULT_CACHE_DIR = Path.home() / ".amal-metric-data" / "990_xml_cache"


class Form990GrantsCollector(BaseCollector):
    """
    Collect grants data from IRS Form 990 XML files via ProPublica.

    ProPublica provides free XML downloads of electronically filed 990s.
    This collector extracts:
    - Schedule I: Grants to domestic organizations/governments
    - Schedule F: Grants to foreign organizations
    """

    @property
    def source_name(self) -> str:
        return "form990_grants"

    @property
    def schema_key(self) -> str:
        return "grants_profile"

    PROPUBLICA_ORG_URL = "https://projects.propublica.org/nonprofits/organizations"
    PROPUBLICA_XML_URL = "https://projects.propublica.org/nonprofits/download-xml"

    # XML namespace for IRS e-file
    IRS_NS = {"irs": "http://www.irs.gov/efile"}

    def __init__(
        self,
        logger: Optional[PipelineLogger] = None,
        rate_limit_delay: float = 2.0,
        timeout: int = 60,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize Form 990 Grants collector.

        Args:
            logger: Logger instance
            rate_limit_delay: Seconds between requests (default 2.0 - shares ProPublica rate limit)
            timeout: Request timeout in seconds (default 60 for large XML files)
            cache_dir: Directory for caching 990 XML files (default: ~/.amal-metric-data/990_xml_cache)
        """
        self.logger = logger
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time = 0

        # Setup cache directory - 990s never change so cache indefinitely
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def _rate_limit(self):
        """Enforce rate limiting (global, thread-safe, shared with propublica collector)."""
        # Use same domain as propublica collector since both hit ProPublica servers
        global_rate_limiter.wait("propublica", self.rate_limit_delay)

    def _get_filing_object_ids(self, ein: str, max_filings: int = 3) -> List[Tuple[str, Optional[int]]]:
        """
        Get object_ids for up to `max_filings` most recent 990 XML filings.

        FIX #22: Support multi-year grant processing by returning multiple filings.

        Args:
            ein: EIN without dashes
            max_filings: Maximum number of filings to return (default 3)

        Returns:
            List of (object_id, tax_year) tuples, most recent first.
            tax_year may be None - extracted from XML during parse() instead.
        """
        url = f"{self.PROPUBLICA_ORG_URL}/{ein}"

        self._rate_limit()

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 404:
                return []
            response.raise_for_status()

            # Parse HTML to find XML download links
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all XML download links - they contain object_id
            xml_links = soup.find_all("a", href=re.compile(r"download-xml\?object_id="))

            if not xml_links:
                if self.logger:
                    self.logger.debug(f"No XML filings found for EIN {ein}")
                return []

            results = []
            for link in xml_links[:max_filings]:
                href = link.get("href", "")
                match = re.search(r"object_id=(\d+)", href)
                if match:
                    object_id = match.group(1)
                    # Tax year will be extracted from XML content during parse()
                    results.append((object_id, None))

            return results

        except requests.RequestException as e:
            if self.logger:
                self.logger.error(f"Error fetching ProPublica page: {e}")
            return []

    def _get_cache_path(self, object_id: str) -> Path:
        """Get cache file path for an object_id."""
        return self.cache_dir / f"{object_id}.xml"

    def _get_cached_xml(self, object_id: str) -> Optional[str]:
        """
        Get XML from cache if available.

        C-013 fix: Use try/except instead of exists() check to avoid TOCTOU race.

        Args:
            object_id: ProPublica object_id

        Returns:
            XML content or None if not cached
        """
        cache_path = self._get_cache_path(object_id)
        try:
            content = cache_path.read_text(encoding="utf-8")
            if self.logger:
                self.logger.debug(f"Cache hit for object_id {object_id}")
            return content
        except FileNotFoundError:
            return None
        except OSError as e:
            if self.logger:
                self.logger.warning(f"Error reading cache file {cache_path}: {e}")
            return None

    def _cache_xml(self, object_id: str, content: str) -> None:
        """
        Cache XML content to disk.

        Args:
            object_id: ProPublica object_id
            content: XML content to cache
        """
        cache_path = self._get_cache_path(object_id)
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(content, encoding="utf-8")
            if self.logger:
                self.logger.debug(f"Cached XML for object_id {object_id}")
        except OSError as e:
            if self.logger:
                self.logger.warning(f"Failed to cache XML for object_id {object_id}: {e}")

    def _download_990_xml(self, object_id: str) -> Optional[str]:
        """
        Download 990 XML file from ProPublica with caching.

        990 filings never change once filed, so we cache indefinitely.
        ProPublica returns a 302 redirect to S3. Rate limit is 1 download per minute.

        Args:
            object_id: ProPublica object_id for the filing

        Returns:
            XML content as string, or None on error
        """
        # Check cache first
        cached = self._get_cached_xml(object_id)
        if cached:
            return cached

        url = f"{self.PROPUBLICA_XML_URL}?object_id={object_id}"

        self._rate_limit()

        try:
            # Follow redirects to S3
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True,
            )

            # Handle rate limiting
            if response.status_code == 429:
                if self.logger:
                    self.logger.warning("Rate limited by ProPublica (429). Waiting 65s...")
                time.sleep(65)
                # Retry once
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )

            response.raise_for_status()

            # Verify we got XML
            content = response.text
            # Strip UTF-8 BOM if present (common in IRS XML files)
            # BOM can appear as \ufeff (proper decode) or ï»¿ (latin-1 decode of EF BB BF)
            if content.startswith("\ufeff"):
                content = content[1:]
            elif content.startswith("ï»¿"):
                content = content[3:]
            if not content.strip().startswith("<?xml"):
                if self.logger:
                    self.logger.warning(f"Response doesn't appear to be XML for object_id {object_id}")
                    self.logger.debug(f"Response content (first 200 chars): {content[:200]}")
                return None

            # Cache the XML - 990s never change
            self._cache_xml(object_id, content)

            return content

        except requests.RequestException as e:
            if self.logger:
                self.logger.error(f"Error downloading XML: {e}")
            return None

    def _parse_domestic_grants(self, root: ET.Element) -> List[Dict[str, Any]]:
        """
        Parse Schedule I - Grants to domestic organizations.

        Args:
            root: XML root element

        Returns:
            List of grant dictionaries
        """
        grants = []

        # Find Schedule I section
        for sched_i in root.findall(".//irs:IRS990ScheduleI", self.IRS_NS):
            # Find all grant groups
            for grant_grp in sched_i.findall(".//irs:GrantOrContributionPdDurYrGrp", self.IRS_NS):
                grant = self._extract_grant_info(grant_grp, is_foreign=False)
                if grant:
                    grants.append(grant)

            # Also check for RecipientTable entries (alternative structure)
            for recipient in sched_i.findall(".//irs:RecipientTable", self.IRS_NS):
                grant = self._extract_grant_info(recipient, is_foreign=False)
                if grant:
                    grants.append(grant)

        return grants

    def _parse_foreign_grants(self, root: ET.Element) -> List[Dict[str, Any]]:
        """
        Parse Schedule F - Grants to foreign organizations.

        Args:
            root: XML root element

        Returns:
            List of grant dictionaries
        """
        grants = []

        # Find Schedule F section
        for sched_f in root.findall(".//irs:IRS990ScheduleF", self.IRS_NS):
            # Part II - Grants to organizations
            for grant_grp in sched_f.findall(".//irs:GrantsToOrgOutsideUSGrp", self.IRS_NS):
                grant = self._extract_grant_info(grant_grp, is_foreign=True)
                if grant:
                    grants.append(grant)

            # Part III - Grants to individuals
            for grant_grp in sched_f.findall(".//irs:ForeignIndividualsGrantsGrp", self.IRS_NS):
                grant = self._extract_grant_info(grant_grp, is_foreign=True)
                if grant:
                    grants.append(grant)

        return grants

    def _extract_grant_info(self, grant_elem: ET.Element, is_foreign: bool) -> Optional[Dict[str, Any]]:
        """
        Extract grant information from a grant XML element.

        Args:
            grant_elem: XML element containing grant data
            is_foreign: Whether this is a foreign grant

        Returns:
            Grant dictionary or None
        """
        ns = self.IRS_NS

        # Try various paths for recipient name
        name = None
        name_paths = [
            ".//irs:RecipientBusinessName//irs:BusinessNameLine1Txt",
            ".//irs:RecipientPersonNm",
            ".//irs:RecipientNameBusiness//irs:BusinessNameLine1",
        ]
        for path in name_paths:
            elem = grant_elem.find(path, ns)
            if elem is not None and elem.text:
                name = elem.text.strip()
                break

        # Get EIN if available
        ein = None
        ein_elem = grant_elem.find(".//irs:RecipientEIN", ns)
        if ein_elem is not None and ein_elem.text:
            ein = ein_elem.text.strip()

        # Get amount
        amount = None
        amount_paths = [
            "irs:CashGrantAmt",
            "irs:AmountOfCashGrantAmt",
            ".//irs:CashGrantAmt",
        ]
        for path in amount_paths:
            elem = grant_elem.find(path, ns)
            if elem is not None and elem.text:
                try:
                    amount = float(elem.text)
                except ValueError:
                    pass
                break

        # Get purpose
        purpose = None
        purpose_paths = [
            "irs:PurposeOfGrantTxt",
            ".//irs:PurposeOfGrantTxt",
            "irs:GrantTypeTxt",
        ]
        for path in purpose_paths:
            elem = grant_elem.find(path, ns)
            if elem is not None and elem.text:
                purpose = elem.text.strip()
                break

        # Get region for foreign grants
        region = None
        if is_foreign:
            region_elem = grant_elem.find(".//irs:RegionTxt", ns)
            if region_elem is not None and region_elem.text:
                region = region_elem.text.strip()

        # Skip if no meaningful data
        if amount is None or amount == 0:
            return None

        # C-006: Validate grant amount plausibility
        # Reject negative amounts and absurdly large amounts (>$10B per grant)
        max_single_grant = 10_000_000_000  # $10B - larger than any real single grant
        if amount < 0:
            if self.logger:
                self.logger.warning(f"Rejecting negative grant amount: ${amount:,.0f} to {name}")
            return None
        if amount > max_single_grant:
            if self.logger:
                self.logger.warning(f"Rejecting implausible grant amount: ${amount:,.0f} to {name}")
            return None

        return {
            "recipient_name": name,
            "recipient_ein": ein,
            "amount": amount,
            "purpose": purpose,
            "region": region if is_foreign else None,
            "is_foreign": is_foreign,
        }

    def _extract_summary_financials(self, root: ET.Element) -> Dict[str, Any]:
        """
        Extract summary financial data from 990.

        Args:
            root: XML root element

        Returns:
            Dictionary of financial summary
        """
        ns = self.IRS_NS
        financials = {}

        # Total grants paid
        paths = {
            "total_grants_paid": [
                ".//irs:GrantsAndSimilarAmtsCYAmt",
                ".//irs:GrantsToDomesticOrgsGrp/irs:TotalAmt",
            ],
            "total_revenue": [".//irs:CYTotalRevenueAmt", ".//irs:TotalRevenueAmt"],
            "total_expenses": [".//irs:CYTotalExpensesAmt", ".//irs:TotalFunctionalExpensesAmt"],
            "program_expenses": [".//irs:CYProgramServiceExpenseAmt"],
        }

        for field, field_paths in paths.items():
            for path in field_paths:
                elem = root.find(path, ns)
                if elem is not None and elem.text:
                    try:
                        financials[field] = float(elem.text)
                        break
                    except ValueError:
                        pass

        return financials

    def fetch(self, ein: str, **kwargs) -> FetchResult:
        """
        Fetch Form 990 XML(s) from ProPublica.

        FIX #22: Downloads up to 3 most recent filings for multi-year trend analysis.

        Args:
            ein: EIN in format XX-XXXXXXX or XXXXXXXXX

        Returns:
            FetchResult with raw XML(s) and metadata header.
            Multi-filing format uses FORM990_MULTI header and FORM990_SEPARATOR delimiters.
        """
        # Normalize EIN
        ein_clean = ein.replace("-", "")
        if len(ein_clean) != 9 or not ein_clean.isdigit():
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="xml",
                error=f"Invalid EIN format: {ein}",
            )

        if self.logger:
            self.logger.info(f"Fetching 990 grants for EIN {ein}")

        # Step 1: Get filing object_ids (up to 3)
        filings = self._get_filing_object_ids(ein_clean, max_filings=3)
        if not filings:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="xml",
                error=f"No XML filings found for EIN {ein}",
            )

        if self.logger:
            self.logger.debug(f"Found {len(filings)} filing(s) for EIN {ein}")

        # Step 2: Download XMLs
        import json

        downloaded = []
        for object_id, tax_year in filings:
            xml_content = self._download_990_xml(object_id)
            if xml_content:
                downloaded.append({"object_id": object_id, "tax_year": tax_year, "xml": xml_content})
            else:
                if self.logger:
                    self.logger.warning(f"Failed to download XML for object_id {object_id}, skipping")

        if not downloaded:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="xml",
                error=f"Failed to download any XML filings for EIN {ein}",
            )

        # Pack into multi-filing format
        if len(downloaded) == 1:
            # Single filing: use legacy format for backward compatibility
            d = downloaded[0]
            metadata = {"object_id": d["object_id"], "tax_year": d["tax_year"]}
            raw_with_metadata = f"<!-- FORM990_METADATA: {json.dumps(metadata)} -->\n{d['xml']}"
        else:
            # Multi-filing format
            metadata_list = [{"object_id": d["object_id"], "tax_year": d["tax_year"]} for d in downloaded]
            xml_parts = [d["xml"] for d in downloaded]
            separator = "\n<!-- FORM990_SEPARATOR -->\n"
            raw_with_metadata = (
                f"<!-- FORM990_MULTI: {json.dumps(metadata_list)} -->\n"
                + separator.join(xml_parts)
            )

        return FetchResult(
            success=True,
            raw_data=raw_with_metadata,
            content_type="xml",
            error=None,
        )

    def _extract_tax_year(self, root: ET.Element) -> Optional[int]:
        """Extract tax year from XML root element."""
        tax_yr_elem = root.find(".//irs:TaxYr", self.IRS_NS)
        if tax_yr_elem is not None and tax_yr_elem.text:
            try:
                return int(tax_yr_elem.text)
            except ValueError:
                pass
        # Fallback: try TaxPeriodEndDt (format: YYYY-MM-DD)
        tax_period_elem = root.find(".//irs:TaxPeriodEndDt", self.IRS_NS)
        if tax_period_elem is not None and tax_period_elem.text:
            try:
                return int(tax_period_elem.text[:4])
            except (ValueError, IndexError):
                pass
        return None

    def _parse_single_filing(
        self, xml_content: str, object_id: Optional[str], tax_year: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single 990 XML filing into grants + financials.

        Returns dict with keys: tax_year, object_id, domestic_grants, foreign_grants,
        financials, org_name. Returns None on parse error.
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            if self.logger:
                self.logger.warning(f"XML parse error for object_id {object_id}: {e}")
            return None

        # Extract tax year from XML (more reliable than metadata)
        if tax_year is None:
            tax_year = self._extract_tax_year(root)

        domestic_grants = self._parse_domestic_grants(root)
        foreign_grants = self._parse_foreign_grants(root)
        financials = self._extract_summary_financials(root)

        # Tag each grant with tax_year
        for g in domestic_grants:
            g["tax_year"] = tax_year
        for g in foreign_grants:
            g["tax_year"] = tax_year

        org_name = None
        name_elem = root.find(".//irs:Filer//irs:BusinessNameLine1Txt", self.IRS_NS)
        if name_elem is not None:
            org_name = name_elem.text

        return {
            "tax_year": tax_year,
            "object_id": object_id,
            "domestic_grants": domestic_grants,
            "foreign_grants": foreign_grants,
            "financials": financials,
            "org_name": org_name,
        }

    def parse(self, raw_data: str, ein: str, **kwargs) -> ParseResult:
        """
        Parse Form 990 XML(s) into grants profile.

        FIX #22: Supports both single-filing (legacy) and multi-filing formats.
        Multi-year grants are merged with tax_year tags on each grant.

        Args:
            raw_data: Raw XML from fetch() with metadata header
            ein: EIN

        Returns:
            ParseResult with {"grants_profile": {...}}
        """
        import json

        ein_clean = ein.replace("-", "")
        ein_formatted = f"{ein_clean[:2]}-{ein_clean[2:]}"

        filings_data: List[Dict[str, Any]] = []

        if raw_data.startswith("<!-- FORM990_MULTI:"):
            # Multi-filing format
            try:
                first_line_end = raw_data.index("-->\n") + 4
                metadata_line = raw_data[:first_line_end]
                xml_block = raw_data[first_line_end:]
                metadata_json = metadata_line.replace("<!-- FORM990_MULTI: ", "").replace(" -->", "").strip()
                metadata_list = json.loads(metadata_json)
                xml_parts = xml_block.split("\n<!-- FORM990_SEPARATOR -->\n")

                for i, xml_content in enumerate(xml_parts):
                    meta = metadata_list[i] if i < len(metadata_list) else {}
                    result = self._parse_single_filing(
                        xml_content, meta.get("object_id"), meta.get("tax_year")
                    )
                    if result:
                        filings_data.append(result)
            except (json.JSONDecodeError, ValueError) as e:
                if self.logger:
                    self.logger.warning(f"Failed to parse multi-filing metadata: {e}")
        elif raw_data.startswith("<!-- FORM990_METADATA:"):
            # Legacy single-filing format
            try:
                first_line_end = raw_data.index("-->\n") + 4
                metadata_line = raw_data[:first_line_end]
                xml_content = raw_data[first_line_end:]
                metadata_json = metadata_line.replace("<!-- FORM990_METADATA: ", "").replace(" -->", "").strip()
                metadata = json.loads(metadata_json)
                result = self._parse_single_filing(
                    xml_content, metadata.get("object_id"), metadata.get("tax_year")
                )
                if result:
                    filings_data.append(result)
            except (json.JSONDecodeError, ValueError):
                pass
        else:
            # Raw XML without metadata header
            result = self._parse_single_filing(raw_data, None, None)
            if result:
                filings_data.append(result)

        if not filings_data:
            return ParseResult(
                success=False,
                parsed_data=None,
                error="No filings could be parsed",
            )

        # Merge grants across all filings (most recent first)
        all_domestic: List[Dict[str, Any]] = []
        all_foreign: List[Dict[str, Any]] = []
        filing_years: List[int] = []

        # Use most recent filing for financials and metadata
        latest = filings_data[0]
        tax_year = latest["tax_year"]
        object_id = latest["object_id"]
        org_name = latest["org_name"]
        financials = latest["financials"]

        for fd in filings_data:
            all_domestic.extend(fd["domestic_grants"])
            all_foreign.extend(fd["foreign_grants"])
            if fd["tax_year"] is not None:
                filing_years.append(fd["tax_year"])

        # Calculate totals
        total_domestic = sum(g["amount"] for g in all_domestic if g["amount"])
        total_foreign = sum(g["amount"] for g in all_foreign if g["amount"])

        # Build profile
        profile_data = {
            "name": org_name or "Unknown",
            "ein": ein_formatted,
            "tax_year": tax_year,
            "object_id": object_id,
            "filing_years": sorted(set(filing_years), reverse=True),
            "domestic_grants": all_domestic,
            "foreign_grants": all_foreign,
            "total_domestic_grants": total_domestic,
            "total_foreign_grants": total_foreign,
            "total_grants": total_domestic + total_foreign,
            "domestic_grant_count": len(all_domestic),
            "foreign_grant_count": len(all_foreign),
            "total_revenue": financials.get("total_revenue"),
            "total_expenses": financials.get("total_expenses"),
            "program_expenses": financials.get("program_expenses"),
        }

        # Validate
        try:
            profile = Form990GrantsProfile(**profile_data)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Validation error: {e}")
            return ParseResult(
                success=False,
                parsed_data=None,
                error=f"Validation failed: {e}",
            )

        years_str = ", ".join(str(y) for y in filing_years) if filing_years else "unknown"
        if self.logger:
            self.logger.info(
                f"Extracted {len(all_domestic)} domestic + {len(all_foreign)} foreign grants "
                f"across {len(filings_data)} filing(s) (years: {years_str}, "
                f"${total_domestic + total_foreign:,.0f} total)"
            )

        return ParseResult(
            success=True,
            parsed_data={self.schema_key: profile.model_dump()},
            error=None,
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

        # Extract object_id from raw_data for backwards compatibility
        import json
        object_id = None
        if fetch_result.raw_data and fetch_result.raw_data.startswith("<!-- FORM990_METADATA:"):
            try:
                metadata_line = fetch_result.raw_data.split("-->\n")[0]
                metadata_json = metadata_line.replace("<!-- FORM990_METADATA: ", "").strip()
                metadata = json.loads(metadata_json)
                object_id = metadata.get("object_id")
            except (json.JSONDecodeError, ValueError, IndexError):
                pass

        return True, {
            **parse_result.parsed_data,
            "raw_xml_object_id": object_id,
            "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
        }, None

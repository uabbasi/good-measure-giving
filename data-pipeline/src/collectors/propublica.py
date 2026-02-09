"""
ProPublica NonProfit Explorer collector.

Fetches IRS Form 990 data from ProPublica's API.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests

from ..utils.logger import PipelineLogger
from ..utils.rate_limiter import global_rate_limiter
from ..validators.propublica_validator import ProPublica990Profile
from .base import BaseCollector, FetchResult, ParseResult


class ProPublicaCollector(BaseCollector):
    """
    Collect IRS Form 990 data from ProPublica NonProfit Explorer API.

    API Docs: https://projects.propublica.org/nonprofits/api

    Implements BaseCollector for 3-phase pipeline:
    - fetch(): HTTP GET to ProPublica API, returns raw JSON
    - parse(): Parse JSON response into ProPublica990Profile schema
    """

    BASE_URL = "https://projects.propublica.org/nonprofits/api/v2"

    def __init__(
        self,
        logger: Optional[PipelineLogger] = None,
        rate_limit_delay: float = 2.0,
        timeout: int = 30,
    ):
        """
        Initialize ProPublica collector.

        Args:
            logger: Logger instance
            rate_limit_delay: Seconds between requests (default 2.0 - ProPublica is strict)
            timeout: Request timeout in seconds
        """
        self.logger = logger
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time = 0

    @property
    def source_name(self) -> str:
        return "propublica"

    @property
    def schema_key(self) -> str:
        return "propublica_990"

    def _rate_limit(self):
        """Enforce rate limiting (global, thread-safe)."""
        global_rate_limiter.wait("propublica", self.rate_limit_delay)

    def _log_field_extraction_report(self, profile: Dict[str, Any]):
        """Log detailed field extraction report."""
        if not self.logger:
            return

        critical_fields = {"name", "ein", "tax_year", "total_revenue", "total_expenses", "total_assets"}
        extracted = []
        missing_critical = []

        for key, value in profile.items():
            if value is not None and value != "" and value != []:
                display_value = str(value)
                if len(display_value) > 50:
                    display_value = display_value[:47] + "..."
                extracted.append(f"  ✓ {key}: {display_value}")
            elif key in critical_fields:
                missing_critical.append(f"  ✗ {key}: MISSING (CRITICAL)")

        total_fields = len(profile)
        extracted_count = len(extracted)
        percentage = (extracted_count / total_fields * 100) if total_fields > 0 else 0

        self.logger.debug("[PROPUBLICA] Field Extraction Report:")
        for line in extracted:
            self.logger.debug(line)

        if missing_critical:
            for line in missing_critical:
                self.logger.warning(line)

        self.logger.debug(f"Summary: {extracted_count}/{total_fields} fields extracted ({percentage:.1f}%)")

    def _extract_ruling_year(self, ruling_date: Optional[str]) -> Optional[int]:
        """Extract year from ProPublica ruling_date field.

        Args:
            ruling_date: String in format "YYYY-MM" or "YYYY" or None

        Returns:
            Year as integer, or None if invalid/missing
        """
        if not ruling_date:
            return None

        try:
            # ruling_date is typically "YYYY-MM" or "YYYY"
            year_str = ruling_date.split("-")[0] if "-" in ruling_date else ruling_date
            year = int(year_str)
            if 1800 <= year <= 2100:
                return year
        except (ValueError, IndexError):
            pass

        return None

    def _determine_form_990_exempt_status(
        self, filing_requirement_code: Optional[int], ntee_code: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """Determine Form 990 exempt status from ProPublica filing_requirement_code.

        Args:
            filing_requirement_code: From ProPublica API (0 = exempt, 1 = required)
            ntee_code: NTEE code for determining if religious org

        Returns:
            Tuple of (is_exempt, exempt_reason)
        """
        # filing_requirement_code == 0 means NOT required to file Form 990
        # This includes churches, religious orgs, and small orgs under $50K revenue
        is_exempt = filing_requirement_code == 0

        if not is_exempt:
            return False, None

        # Try to determine specific reason based on NTEE code
        # NTEE codes starting with "X" are religious organizations
        if ntee_code and ntee_code.startswith("X"):
            return True, "Religious organization"

        # Generic reason - could be church or small org
        return True, "Exempt from Form 990 filing"

    def fetch(self, ein: str, **kwargs) -> FetchResult:
        """
        Fetch raw JSON from ProPublica API.

        Args:
            ein: EIN (with or without hyphen)

        Returns:
            FetchResult with raw JSON string
        """
        # Normalize EIN - remove hyphen for API
        ein_clean = ein.replace("-", "")

        if len(ein_clean) != 9 or not ein_clean.isdigit():
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="json",
                error=f"Invalid EIN format: {ein}",
            )

        url = f"{self.BASE_URL}/organizations/{ein_clean}.json"

        if self.logger:
            self.logger.debug(f"Fetching ProPublica 990 data for EIN {ein}")

        self._rate_limit()

        try:
            response = requests.get(url, timeout=self.timeout)

            if response.status_code == 404:
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="json",
                    error=f"Organization not found for EIN {ein}",
                )

            # C-003: Handle rate limiting (429) explicitly
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                if self.logger:
                    self.logger.warning(f"ProPublica rate limited (429). Retry-After: {retry_after}s")
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="json",
                    error=f"Rate limited (429). Retry after {retry_after}s",
                )

            if response.status_code != 200:
                return FetchResult(
                    success=False,
                    raw_data=None,
                    content_type="json",
                    error=f"HTTP {response.status_code}",
                )

            # Return raw JSON string for storage in raw_html
            return FetchResult(
                success=True,
                raw_data=response.text,
                content_type="json",
                error=None,
            )

        except requests.Timeout:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="json",
                error=f"Request timeout after {self.timeout}s",
            )
        except requests.RequestException as e:
            return FetchResult(
                success=False,
                raw_data=None,
                content_type="json",
                error=f"Request failed: {str(e)}",
            )

    def parse(self, raw_data: str, ein: str, **kwargs) -> ParseResult:
        """
        Parse ProPublica JSON into validated schema.

        Args:
            raw_data: Raw JSON string from fetch()
            ein: EIN for validation

        Returns:
            ParseResult with {"propublica_990": {...}}
        """
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as e:
            return ParseResult(
                success=False,
                parsed_data=None,
                error=f"Invalid JSON: {e}",
            )

        # Validate API response structure
        if "organization" not in data:
            return ParseResult(
                success=False,
                parsed_data=None,
                error="Invalid API response structure",
            )

        org_data = data["organization"]
        filings = data.get("filings_with_data", [])

        # E-010: Validate that API-returned EIN matches requested EIN
        api_ein = org_data.get("ein")
        if api_ein:
            # Normalize both EINs for comparison (remove dashes)
            requested_clean = ein.replace("-", "")
            api_clean = str(api_ein).replace("-", "")
            if requested_clean != api_clean:
                return ParseResult(
                    success=False,
                    parsed_data=None,
                    error=f"VALIDATION_ERROR: EIN mismatch: requested {ein} but API returned {api_ein}",
                )

        # Handle new orgs with no filings yet - still extract org-level data
        if not filings:
            ein_clean = ein.replace("-", "")
            raw_subsection = org_data.get("subsection_code")
            subsection_code = str(raw_subsection) if raw_subsection is not None else None
            filing_requirement_code = org_data.get("filing_requirement_code")
            ntee_code = org_data.get("ntee_code")
            is_form_990_exempt, exempt_reason = self._determine_form_990_exempt_status(
                filing_requirement_code, ntee_code
            )
            profile_data = {
                "ein": f"{ein_clean[:2]}-{ein_clean[2:]}",
                "name": org_data.get("name", "Unknown"),
                "address": org_data.get("address"),
                "city": org_data.get("city"),
                "state": org_data.get("state"),
                "zip": org_data.get("zipcode"),
                "ntee_code": ntee_code,
                "subsection_code": subsection_code,
                "affiliation_code": str(org_data.get("affiliation_code"))
                if org_data.get("affiliation_code") is not None
                else None,
                "foundation_code": str(org_data.get("foundation_code"))
                if org_data.get("foundation_code") is not None
                else None,
                "irs_ruling_year": self._extract_ruling_year(org_data.get("ruling_date")),
                "filing_history": [],
                "no_filings": True,  # Flag to indicate this is a new org without 990s
                "form_990_exempt": is_form_990_exempt,
                "form_990_exempt_reason": exempt_reason,
            }
            return ParseResult(
                success=True,
                parsed_data={"propublica_990": profile_data},
                error=None,
            )

        most_recent = filings[0]  # Already sorted by tax_year desc

        # Extract up to 3 years of filing history for trend analysis
        filing_history = []
        for filing in filings[:3]:
            history_entry = {
                "tax_year": filing.get("tax_prd_yr"),
                "total_revenue": filing.get("totrevenue"),
                "total_expenses": filing.get("totfuncexpns"),
                "program_expenses": filing.get("progrmservexp"),  # Part IX Line 25A
                "admin_expenses": filing.get("mgmtandgeneral"),  # Part IX Line 25B (management & general)
                "fundraising_expenses": filing.get("fundfees"),  # Part IX Line 25C
                "total_assets": filing.get("totassetsend"),
                "net_assets": filing.get("totnetassetend"),
                "employees_count": filing.get("totemploy"),
                "form_type": filing.get("formtype"),
            }
            filing_history.append(history_entry)

        # Normalize EIN for profile
        ein_clean = ein.replace("-", "")

        # Extract subsection code and determine Form 990 exempt status
        raw_subsection = org_data.get("subsection_code")
        subsection_code = str(raw_subsection) if raw_subsection is not None else None
        filing_requirement_code = org_data.get("filing_requirement_code")
        ntee_code = org_data.get("ntee_code")
        is_form_990_exempt, exempt_reason = self._determine_form_990_exempt_status(
            filing_requirement_code, ntee_code
        )

        # Build structured profile
        profile_data = {
            "ein": f"{ein_clean[:2]}-{ein_clean[2:]}",
            "name": org_data.get("name", "Unknown"),
            "tax_year": most_recent.get("tax_prd_yr"),
            "total_revenue": most_recent.get("totrevenue"),
            "total_expenses": most_recent.get("totfuncexpns"),
            "program_expenses": most_recent.get("progrmservexp"),  # Part IX Line 25A
            "admin_expenses": most_recent.get("mgmtandgeneral"),  # Part IX Line 25B
            "fundraising_expenses": most_recent.get("fundfees"),  # Part IX Line 25C
            "total_assets": most_recent.get("totassetsend"),
            "total_liabilities": most_recent.get("totliabend"),
            "net_assets": most_recent.get("totnetassetend"),
            "total_contributions": most_recent.get("totcntrbgfts"),
            "program_service_revenue": most_recent.get("totprgmrevnue"),
            "investment_income": most_recent.get("invstmntinc"),
            "other_revenue": most_recent.get("othrevnue"),
            "employees_count": most_recent.get("totemploy"),
            "volunteers_count": most_recent.get("totvolunteers"),
            "compensation_current_officers": most_recent.get("compnsatncurrofcr"),
            "other_salaries_wages": most_recent.get("othrsalwages"),
            "payroll_tax": most_recent.get("payrolltx"),
            "address": org_data.get("address"),
            "city": org_data.get("city"),
            "state": org_data.get("state"),
            "zip": org_data.get("zipcode"),
            "ntee_code": ntee_code,
            "subsection_code": subsection_code,
            "affiliation_code": str(org_data.get("affiliation_code"))
            if org_data.get("affiliation_code") is not None
            else None,
            "filing_type": most_recent.get("formtype"),
            "foundation_code": str(org_data.get("foundation_code"))
            if org_data.get("foundation_code") is not None
            else None,
            "irs_ruling_year": self._extract_ruling_year(org_data.get("ruling_date")),
            "filing_history": filing_history,
            "no_filings": False,
            "form_990_exempt": is_form_990_exempt,
            "form_990_exempt_reason": exempt_reason,
        }

        if self.logger:
            extracted = {k: v for k, v in profile_data.items() if v is not None}
            self.logger.debug(f"Extracted {len(extracted)} fields from ProPublica API")

        # Validate with Pydantic
        try:
            profile = ProPublica990Profile(**profile_data)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Validation error: {e}")
            return ParseResult(
                success=False,
                parsed_data=None,
                error=f"Validation failed: {e}",
            )

        if self.logger:
            self._log_field_extraction_report(profile.model_dump())
            self.logger.debug(f"Successfully parsed ProPublica data for {ein}")

        return ParseResult(
            success=True,
            parsed_data={self.schema_key: profile.model_dump()},
            error=None,
        )

    def collect(self, ein: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Legacy method: fetch + parse in one call.

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
            "raw_content": fetch_result.raw_data,  # Store raw JSON string for re-parsing
            "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return True, result, None

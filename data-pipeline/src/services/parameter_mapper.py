"""
Parameter Mapper - Maps source-specific fields to unified schema.

This service implements field mapping logic to transform data from different
sources (ProPublica, Charity Navigator, Candid, Form 990 Grants, website) into the
unified ReconciledCharityProfile schema.
"""

import logging
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class FieldType(Enum):
    """Field data types for mapping validation."""

    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST = "list"
    DATE = "date"


class ParameterMapper:
    """Maps source-specific fields to unified reconciled schema."""

    # Source priority hierarchy by parameter type (from FR-002)
    # Extended for agentic pipeline (Phase 4)
    FIELD_PRIORITY = {
        # Financial data - IRS filings are authoritative
        "financial": ["propublica", "candid", "charity_navigator", "website"],
        # Mission/programs - charity's own website is authoritative
        "mission": ["website", "candid", "charity_navigator"],
        "programs": ["website", "candid", "charity_navigator"],
        # Contact info
        "contact": ["website", "candid", "charity_navigator", "propublica"],
        # Ratings - Charity Navigator is most recognized
        "ratings": ["charity_navigator", "bbb", "charity_watch", "guidestar", "others"],
        # Evidence - academic/rigorous sources first
        "evidence": ["givewell", "academic", "third_party", "self_reported", "anecdotal"],
        # Reputation - major news outlets first
        "reputation": ["major_news", "trade_press", "blogs", "social_media"],
        # Grantmaking data (Schedule I/F from Form 990)
        "grantmaking": ["form990_grants"],
    }

    # Field mappings: unified_field -> {source: source_field_path}
    FIELD_MAPPINGS = {
        # ProPublica (IRS 990)
        "propublica": {
            "total_revenue": "total_revenue",
            "total_expenses": "total_expenses",
            "program_expenses": "program_expense",
            "admin_expenses": "administrative_expense",
            "fundraising_expenses": "fundraising_expense",
            "total_assets": "total_assets",
            "total_liabilities": "total_liabilities",
            "net_assets": "net_assets",
            "fiscal_year_end": "tax_year",
            "ntee_code": "ntee_code",
            "name": "organization_name",
            "ein": "ein",
            # Additional fields
            "employees_count": "employees_count",
            "volunteers_count": "volunteers_count",
        },
        # Charity Navigator
        "charity_navigator": {
            "overall_score": "overall_score",
            "financial_score": "financial_score",
            "accountability_score": "accountability_score",
            "impact_score": "impact_score",
            "leadership_score": "leadership_score",
            "culture_score": "culture_score",
            "name": "name",
            "ein": "ein",
            "mission": "mission",
            "website": "website_url",
            "total_revenue": "total_revenue",
            "total_expenses": "total_expenses",
            "program_expenses": "program_expenses",
            "admin_expenses": "admin_expenses",
            "fundraising_expenses": "fundraising_expenses",
            "program_expense_ratio": "program_expense_ratio",
            "admin_expense_ratio": "admin_expense_ratio",
            "fundraising_expense_ratio": "fundraising_expense_ratio",
            # Additional fields
            "beacons": "beacons",
            "ceo_name": "ceo_name",
            "ceo_compensation": "ceo_compensation",
            "has_financial_audit": "has_financial_audit",
            "independent_board_percentage": "independent_board_percentage",
            "working_capital_ratio": "working_capital_ratio",
            "net_assets": "net_assets",
            "total_assets": "total_assets",
            "total_liabilities": "total_liabilities",
            "board_size": "board_size",
            "phone": "phone",
        },
        # Candid
        "candid": {
            "name": "organization_name",
            "ein": "ein",
            "mission": "mission",
            "programs": "programs",
            "populations_served": "populations_served",
            "geographic_coverage": "areas_served",
            "website": "website_url",
            # Financial fields (T030 - US1)
            "total_revenue": "revenue",
            "total_expenses": "expenses",
            "program_expense_ratio": "program_ratio",
            # V2 scorer fields
            "candid_seal": "candid_seal",
            "board_size": "board_size",
            "outcomes": "outcomes",
            "program_descriptions": "program_details",
            # Additional fields
            "ceo_name": "ceo_name",
            "tagline": "tagline",
            "vision": "vision",
            "phone": "phone",
            "ntee_code": "ntee_code",
            "founded_year": "ruling_year",
        },
        # Form 990 Grants (Schedule I/F from 990 XML)
        "form990_grants": {
            "name": "organization_name",
            "ein": "ein",
            "domestic_grants": "domestic_grants",
            "foreign_grants": "foreign_grants",
            "total_grants": "total_grants",
        },
        # Charity Website
        "website": {
            "name": "name",
            "mission": "mission_statement",
            "programs": "programs",
            "populations_served": "beneficiaries",
            "geographic_coverage": "geographic_coverage",
            "website": "url",
            # Additional fields
            "beneficiaries_served": "beneficiaries_served",
            "volunteer_page_url": "volunteer_page_url",
            "vision": "vision_statement",
            "phone": "contact_phone",
            "founded_year": "founded_year",
        },
    }

    def map_source_to_unified(self, source_name: str, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and map fields from a single source to unified schema.

        Args:
            source_name: Name of the data source (e.g., "ProPublica", "Charity Navigator")
            source_data: Raw data from the source

        Returns:
            Dictionary with unified field names and extracted values
        """
        if source_name not in self.FIELD_MAPPINGS:
            logger.warning(f"Unknown source: {source_name}")
            return {}

        mapping = self.FIELD_MAPPINGS[source_name]
        unified_data = {}

        for unified_field, source_field in mapping.items():
            # Handle nested field paths (e.g., "data.profile.mission")
            value = self._extract_nested_value(source_data, source_field)

            if value is not None:
                unified_data[unified_field] = value

        logger.debug(f"Mapped {len(unified_data)} fields from {source_name}")
        return unified_data

    def _extract_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Extract value from nested dict using dot notation path."""
        keys = field_path.split(".")
        value = data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def get_field_priority(self, field_name: str) -> List[str]:
        """
        Get source priority list for a specific field.

        Args:
            field_name: Name of the unified field

        Returns:
            List of source names in priority order (highest first)
        """
        # Determine field category (T031 - US1: Financial field reconciliation)
        if field_name in [
            "total_revenue",
            "total_expenses",
            "program_expenses",
            "admin_expenses",
            "fundraising_expenses",
            "program_expense_ratio",
            "admin_expense_ratio",
            "fundraising_expense_ratio",
            "fiscal_year_end",
            "total_assets",
            "total_liabilities",
            "net_assets",
        ]:
            return self.FIELD_PRIORITY["financial"]
        elif field_name in ["mission", "programs", "populations_served", "geographic_coverage"]:
            return self.FIELD_PRIORITY["mission"]
        elif field_name in ["website", "email", "phone"]:
            return self.FIELD_PRIORITY["contact"]
        elif field_name in [
            "overall_score",
            "financial_score",
            "accountability_score",
            "impact_score",
            "leadership_score",
            "culture_score",
        ]:
            return self.FIELD_PRIORITY["ratings"]
        else:
            # Default to mission priority for unknown fields
            return self.FIELD_PRIORITY["mission"]

    def get_field_type(self, field_name: str) -> FieldType:
        """Determine the data type for a given field."""
        if field_name in ["programs", "populations_served", "geographic_coverage", "zakaat_criteria_met"]:
            return FieldType.LIST
        elif field_name in [
            "total_revenue",
            "total_expenses",
            "program_expenses",
            "admin_expenses",
            "fundraising_expenses",
            "program_expense_ratio",
            "admin_expense_ratio",
            "fundraising_expense_ratio",
            "total_assets",
            "total_liabilities",
            "net_assets",
            "overall_score",
            "financial_score",
            "accountability_score",
            "effectiveness_score",
            "impact_score",
            "leadership_score",
            "culture_score",
        ]:
            return FieldType.NUMBER
        elif field_name in ["zakaat_eligible", "is_muslim_charity"]:
            return FieldType.BOOLEAN
        elif field_name in ["fiscal_year_end", "rating_timestamp", "last_updated"]:
            return FieldType.DATE
        else:
            return FieldType.TEXT

    def ntee_to_category(self, ntee_code: str) -> str:
        """
        Convert NTEE code to human-readable category.

        Args:
            ntee_code: NTEE code (e.g., "P20", "X20", "Z99")

        Returns:
            Human-readable category string
        """
        if not ntee_code or not isinstance(ntee_code, str):
            return "General"

        # Extract first letter (major category)
        major_code = ntee_code[0].upper()

        # NTEE major category mapping
        ntee_map = {
            "A": "Arts & Culture",
            "B": "Education",
            "C": "Environment",
            "D": "Animal Welfare",
            "E": "Health",
            "F": "Mental Health",
            "G": "Medical Research",
            "H": "Medical Research",
            "I": "Crime & Legal",
            "J": "Employment",
            "K": "Food & Agriculture",
            "L": "Housing",
            "M": "Public Safety & Relief",
            "N": "Recreation & Sports",
            "O": "Youth Development",
            "P": "Human Services",
            "Q": "International Affairs",
            "R": "Civil Rights",
            "S": "Community Development",
            "T": "Philanthropy",
            "U": "Science & Technology",
            "V": "Social Science",
            "W": "Public Benefit",
            "X": "Religion",
            "Y": "Membership Benefit",
            "Z": "General",
        }

        return ntee_map.get(major_code, "General")

    def extract_calendar_year(self, date_value: Any) -> int:
        """
        Convert fiscal year, calendar year, or timestamp to numeric calendar year.

        Per FR-003 clarification: Use fiscal year END date.
        Example: FY ending 2023-06-30 → calendar year 2023

        Args:
            date_value: Date in various formats (string, datetime, int)

        Returns:
            Calendar year as integer, or current year if parsing fails
        """
        from datetime import datetime

        if date_value is None:
            return datetime.now().year

        # If already an integer, assume it's a year
        if isinstance(date_value, int):
            return date_value

        # If string, try to parse
        if isinstance(date_value, str):
            # Try common formats
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    dt = datetime.strptime(date_value, fmt)
                    return dt.year
                except ValueError:
                    continue

            # Try to extract 4-digit year from string
            import re

            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", date_value)
            if year_match:
                return int(year_match.group(1))

        # If datetime object
        if hasattr(date_value, "year"):
            return date_value.year

        # Fallback to current year
        logger.warning(f"Could not parse year from: {date_value}, using current year")
        return datetime.now().year

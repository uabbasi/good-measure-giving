"""
Base collector interface for the 3-phase pipeline.

Phase 1 (fetch.py): Calls fetch() → stores raw data in raw_html
Phase 2 (extract.py): Calls parse() → stores structured data in parsed_json

All collectors should implement both methods to enable phase separation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FetchResult:
    """Result from fetch() - raw bytes/text from source."""

    success: bool
    raw_data: Optional[str]  # JSON string, HTML, or XML - stored in raw_html
    content_type: str  # "json", "html", "xml" - informational only
    error: Optional[str] = None


@dataclass
class ParseResult:
    """Result from parse() - structured data for parsed_json."""

    success: bool
    parsed_data: Optional[dict[str, Any]]  # Schema-wrapped: {"propublica_990": {...}}
    error: Optional[str] = None


class BaseCollector(ABC):
    """
    Base class for collectors with separated fetch/parse phases.

    Subclasses must implement:
    - fetch(ein, ...) -> FetchResult: HTTP requests only, returns raw response
    - parse(raw_data) -> ParseResult: Parse raw_data into validated schema

    The legacy collect() method calls both for backwards compatibility.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Canonical source name (e.g., 'propublica', 'charity_navigator')."""
        ...

    @property
    @abstractmethod
    def schema_key(self) -> str:
        """Key for parsed_json wrapper (e.g., 'propublica_990', 'cn_profile')."""
        ...

    @abstractmethod
    def fetch(self, ein: str, **kwargs) -> FetchResult:
        """
        Fetch raw data from source. No parsing.

        Args:
            ein: Charity EIN in XX-XXXXXXX format
            **kwargs: Source-specific arguments (e.g., website_url)

        Returns:
            FetchResult with raw_data as string (JSON/HTML/XML)
        """
        ...

    @abstractmethod
    def parse(self, raw_data: str, ein: str, **kwargs) -> ParseResult:
        """
        Parse raw data into validated schema.

        Args:
            raw_data: Raw string from fetch() - JSON, HTML, or XML
            ein: Charity EIN (needed for schema validation)
            **kwargs: Source-specific arguments

        Returns:
            ParseResult with parsed_data wrapped in schema key
        """
        ...

    def collect(
        self, ein: str, **kwargs
    ) -> tuple[bool, Optional[dict[str, Any]], Optional[str]]:
        """
        Legacy method: fetch + parse in one call.

        Returns:
            Tuple of (success, data_dict, error_message)
            - data_dict includes {schema_key: {...}, raw_html: "...", fetch_timestamp: "..."}
        """
        from datetime import datetime

        # Fetch
        fetch_result = self.fetch(ein, **kwargs)
        if not fetch_result.success:
            return False, None, fetch_result.error

        # Parse
        parse_result = self.parse(fetch_result.raw_data, ein, **kwargs)
        if not parse_result.success:
            return False, None, parse_result.error

        # Combine for backwards compatibility
        result = {
            **parse_result.parsed_data,
            "raw_content": fetch_result.raw_data,
            "fetch_timestamp": datetime.now().isoformat(),
        }

        return True, result, None

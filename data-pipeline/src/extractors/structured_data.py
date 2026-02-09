"""
Structured data extractor for JSON-LD, Open Graph, and microdata.

This module extracts machine-readable data from HTML to reduce LLM calls.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StructuredDataSource(BaseModel):
    """Extracted structured data from webpage."""

    source_type: Literal["json-ld", "opengraph", "microdata", "rdfa"]
    extracted_fields: dict[str, Any]  # Flexible dict for various schemas
    validation_status: Literal["valid", "invalid", "partial"]
    confidence_level: Literal["high", "medium", "low"]
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_type": "json-ld",
                "extracted_fields": {
                    "@type": "Organization",
                    "name": "Example Charity",
                    "email": "info@example-charity.org",
                    "telephone": "+1-555-000-0000",
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": "123 Main St",
                        "addressLocality": "Anytown",
                        "addressRegion": "CA",
                        "postalCode": "90210",
                    },
                },
                "validation_status": "valid",
                "confidence_level": "high",
            }
        }
    )


class StructuredDataExtractor:
    """
    Extractor for structured data using extruct library.

    Extracts data from:
    - JSON-LD (Schema.org)
    - Open Graph tags
    - Microdata
    - RDFa (optional)
    """

    def extract(self, html: str, base_url: str) -> dict[str, list[dict[str, Any]]]:
        """
        Extract all structured data formats from HTML.

        Args:
            html: HTML content
            base_url: Base URL for resolving relative URLs

        Returns:
            Dict with keys: json-ld, opengraph, microdata

        Raises:
            Exception: If extraction fails completely
        """
        import extruct

        try:
            data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld", "opengraph", "microdata"])

            # Normalize the output
            og_data = data.get("opengraph", {})
            return {
                "json-ld": data.get("json-ld", []),
                "opengraph": og_data if isinstance(og_data, dict) else {},  # OG is a single dict
                "microdata": data.get("microdata", []),
            }
        except Exception as e:
            # E-003: Log the error instead of silently swallowing
            import logging

            logging.getLogger(__name__).debug(f"extruct extraction failed: {e}")
            return {"json-ld": [], "opengraph": {}, "microdata": []}

    def extract_json_ld(self, html: str) -> list[dict[str, Any]]:
        """
        Parse JSON-LD structured data from HTML.

        Args:
            html: HTML content

        Returns:
            List of JSON-LD objects found
        """
        import json
        import re

        json_ld_objects = []

        # Find all JSON-LD script tags
        pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            try:
                # Parse JSON
                obj = json.loads(match.strip())
                json_ld_objects.append(obj)
            except json.JSONDecodeError:
                # Skip malformed JSON
                continue

        return json_ld_objects

    def extract_opengraph(self, html: str) -> dict[str, str]:
        """
        Parse Open Graph meta tags from HTML.

        Args:
            html: HTML content

        Returns:
            Dict of OG properties
        """
        import re

        og_data = {}

        # Find all Open Graph meta tags
        pattern = r'<meta[^>]*property=["\']og:([^"\']+)["\'][^>]*content=["\']([^"\']+)["\'][^>]*>'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for prop, content in matches:
            og_data[prop] = content

        # Also check for reversed order (content before property)
        pattern_rev = r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:([^"\']+)["\'][^>]*>'
        matches_rev = re.findall(pattern_rev, html, re.IGNORECASE)

        for content, prop in matches_rev:
            if prop not in og_data:  # Don't overwrite if already found
                og_data[prop] = content

        return og_data

    def extract_microdata(self, html: str, base_url: str) -> list[dict[str, Any]]:
        """
        Parse microdata from HTML.

        Args:
            html: HTML content
            base_url: Base URL for resolving relative URLs

        Returns:
            List of microdata items
        """
        import extruct

        try:
            data = extruct.extract(html, base_url=base_url, syntaxes=["microdata"])
            return data.get("microdata", [])
        except Exception:
            return []

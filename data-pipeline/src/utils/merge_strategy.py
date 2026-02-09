"""
Data merging utility with precedence rules.

This module implements the merge strategy from spec FR-015 and FR-016:
- Factual fields: structured data > regex > LLM
- Semantic fields: LLM > structured data
"""

from typing import Any


class MergeStrategy:
    """
    Strategy for merging extracted data with precedence rules.

    Implements two precedence orders:
    1. Factual fields (EIN, contact, social, donate_url):
       - Structured data (JSON-LD, OG, microdata) - highest priority
       - Deterministic extraction (regex) - medium priority
       - LLM extraction - lowest priority

    2. Semantic fields (mission, programs, impact, leadership):
       - LLM extraction - highest priority
       - Structured data - fallback
    """

    # Factual fields use: structured > regex > LLM
    FACTUAL_FIELDS = {
        "ein",
        "contact_email",
        "contact_phone",
        "address",
        "social_media",
        "donate_url",
        "volunteer_url",
        "logo_url",
        "name",
        "url",
        "founded_year",
        "tax_deductible",
    }

    # Semantic fields use: LLM > structured
    SEMANTIC_FIELDS = {
        "mission",
        "vision",
        "tagline",
        "values",
        "programs",
        "target_populations",
        "geographic_coverage",
        "impact_metrics",
        "beneficiaries",
        "leadership",
        "additional_info",
    }

    # Source priority for factual fields (higher number = higher priority)
    FACTUAL_SOURCE_PRIORITY = {
        "json-ld": 3,
        "opengraph": 3,
        "microdata": 3,
        "regex-ein": 2,
        "regex-contact": 2,
        "regex-social": 2,
        "regex-donate": 2,
        "llm-homepage": 1,
        "llm-about": 1,
        "llm-programs": 1,
        "llm-impact": 1,
        "llm-donate": 1,
        "llm-contact": 1,
    }

    # Source priority for semantic fields (higher number = higher priority)
    SEMANTIC_SOURCE_PRIORITY = {
        "llm-homepage": 3,
        "llm-about": 3,
        "llm-programs": 3,
        "llm-impact": 3,
        "llm-donate": 3,
        "llm-contact": 3,
        "json-ld": 2,
        "opengraph": 2,
        "microdata": 2,
        "regex-ein": 1,
        "regex-contact": 1,
        "regex-social": 1,
        "regex-donate": 1,
    }

    def merge_field(self, field_name: str, extraction_results: list[dict[str, Any]]) -> tuple[Any, str]:
        """
        Merge multiple extractions for a single field using precedence rules.

        Args:
            field_name: Name of the field to merge
            extraction_results: List of dicts with keys: field_value, extraction_source, confidence_score

        Returns:
            Tuple of (merged_value, winning_source)

        Example:
            >>> strategy = MergeStrategy()
            >>> results = [
            ...     {"field_value": "95-4453134", "extraction_source": "json-ld", "confidence_score": 1.0},
            ...     {"field_value": "954453134", "extraction_source": "regex-ein", "confidence_score": 0.9},
            ...     {"field_value": "95-4453134", "extraction_source": "llm-about", "confidence_score": 0.8}
            ... ]
            >>> strategy.merge_field("ein", results)
            ('95-4453134', 'json-ld')
        """
        if not extraction_results:
            return None, "none"

        # Determine field type and priority map
        if field_name in self.FACTUAL_FIELDS:
            priority_map = self.FACTUAL_SOURCE_PRIORITY
        elif field_name in self.SEMANTIC_FIELDS:
            priority_map = self.SEMANTIC_SOURCE_PRIORITY
        else:
            # Unknown field - use factual precedence by default
            priority_map = self.FACTUAL_SOURCE_PRIORITY

        # Sort by priority (descending) and confidence (descending)
        def sort_key(result: dict[str, Any]) -> tuple[int, float]:
            source = result.get("extraction_source", "unknown")
            priority = priority_map.get(source, 0)
            confidence = result.get("confidence_score", 0.0)
            return (priority, confidence)

        sorted_results = sorted(extraction_results, key=sort_key, reverse=True)

        # Return highest-priority result
        winner = sorted_results[0]
        return winner.get("field_value"), winner.get("extraction_source", "unknown")

    def merge_all_fields(self, extraction_results: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Merge all fields from extraction results into final values.

        Args:
            extraction_results: List of ExtractionResult dicts with keys:
                - field_name
                - field_value
                - extraction_source
                - confidence_score

        Returns:
            Dict with keys:
                - merged_data: Dict of {field_name: value}
                - data_sources: Dict of {field_name: source}

        Example:
            >>> strategy = MergeStrategy()
            >>> results = [
            ...     {"field_name": "ein", "field_value": "95-4453134", "extraction_source": "json-ld", "confidence_score": 1.0},
            ...     {"field_name": "mission", "field_value": "Help people", "extraction_source": "llm-about", "confidence_score": 0.9}
            ... ]
            >>> merged = strategy.merge_all_fields(results)
            >>> merged["merged_data"]["ein"]
            '95-4453134'
            >>> merged["data_sources"]["ein"]
            'json-ld'
        """
        # Group results by field name
        fields_map: dict[str, list[dict[str, Any]]] = {}
        for result in extraction_results:
            field_name = result.get("field_name")
            if field_name:
                if field_name not in fields_map:
                    fields_map[field_name] = []
                fields_map[field_name].append(result)

        # Merge each field
        merged_data = {}
        data_sources = {}

        for field_name, field_results in fields_map.items():
            value, source = self.merge_field(field_name, field_results)
            if value is not None:
                merged_data[field_name] = value
                data_sources[field_name] = source

        return {"merged_data": merged_data, "data_sources": data_sources}

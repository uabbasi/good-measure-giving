"""
Extractors module for smart web crawler.

This module contains components for extracting data from websites:
- structured_data: JSON-LD, Open Graph, and microdata extraction
- deterministic: Regex-based extraction for EIN, contact info, etc.
- page_classifier: URL scoring and page type classification
"""

__all__ = [
    "StructuredDataExtractor",
    "DeterministicExtractor",
    "PageClassifier",
    "PageScore",
    "PageClassification",
]

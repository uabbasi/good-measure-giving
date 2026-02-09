"""
Agentic discovery using Gemini Search Grounding.

This package contains the GeminiSearchClient which uses Google's
search grounding feature to discover and verify information.
"""

from .gemini_search import GeminiSearchClient, SearchGroundingResult

__all__ = [
    "GeminiSearchClient",
    "SearchGroundingResult",
]

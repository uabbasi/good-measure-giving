"""
Gemini Search Grounding client.

Wraps the Google GenAI SDK to provide search-grounded responses
with full metadata about sources used.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from google import genai
from google.genai import types

from ..models.agent_discovery import (
    GroundingChunk,
    GroundingMetadata,
    GroundingSupport,
)

logger = logging.getLogger(__name__)

# Default max output tokens to prevent truncation issues
# 2048 tokens is ~8KB which is plenty for structured JSON responses
DEFAULT_MAX_OUTPUT_TOKENS = 2048


def extract_json_from_response(text: str) -> Optional[str]:
    """
    Extract JSON from LLM response text, handling various formats.

    Handles:
    - Plain JSON
    - JSON wrapped in markdown code blocks
    - JSON with trailing content after closing brace
    - Truncated JSON (attempts repair)

    Args:
        text: Raw response text from LLM

    Returns:
        Extracted JSON string, or None if no valid JSON found
    """
    text = text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()

    # Find the JSON object boundaries
    # Look for the first { and last matching }
    start = text.find("{")
    if start == -1:
        return None

    # Count braces to find matching closing brace
    depth = 0
    in_string = False
    escape_next = False
    end = -1

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        # D-001: Removed redundant `not escape_next` check - by this point
        # escape_next is always False (handled above with continue)
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        # No matching closing brace - try to repair truncated JSON
        return _repair_truncated_json(text[start:])

    return text[start:end]


def _repair_truncated_json(json_str: str) -> Optional[str]:
    """
    Attempt to repair truncated JSON by closing open structures.

    This handles cases where the response was cut off mid-JSON.
    """
    # Count unclosed structures
    in_string = False
    escape_next = False
    open_braces = 0
    open_brackets = 0
    last_complete_pos = 0

    for i, char in enumerate(json_str):
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            open_braces += 1
        elif char == "}":
            open_braces -= 1
            if open_braces >= 0:
                last_complete_pos = i + 1
        elif char == "[":
            open_brackets += 1
        elif char == "]":
            open_brackets -= 1
            if open_brackets >= 0:
                last_complete_pos = i + 1
        elif char == "," and open_braces == 1 and open_brackets == 0:
            # Top-level comma - marks end of a complete field
            last_complete_pos = i + 1

    # Truncate to last complete position and close structures
    if last_complete_pos > 0:
        repaired = json_str[:last_complete_pos].rstrip().rstrip(",")
        # Add closing brackets/braces as needed
        repaired += "]" * open_brackets + "}" * open_braces
        # D-009: Validate repaired JSON is actually valid before returning
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            logger.warning(f"Repaired JSON still invalid: {repaired[:100]}...")
            return None

    return None


def calculate_grounding_confidence(result: "SearchGroundingResult") -> float:
    """
    Calculate confidence score from grounding metadata.

    Uses grounding support confidence scores if available,
    otherwise falls back to a default based on whether grounding exists.

    Args:
        result: SearchGroundingResult with grounding metadata

    Returns:
        Confidence score between 0.0 and 1.0
    """
    confidence = 0.0

    if result.grounding_metadata.grounding_supports:
        scores = []
        for support in result.grounding_metadata.grounding_supports:
            if support.confidence_scores:
                scores.extend(support.confidence_scores)
        if scores:
            confidence = sum(scores) / len(scores)
    elif result.has_grounding:
        # Has search results but no explicit confidence scores
        confidence = 0.7

    return confidence


@dataclass
class SearchGroundingResult:
    """Result from a search-grounded Gemini call."""

    text: str
    grounding_metadata: GroundingMetadata
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def has_grounding(self) -> bool:
        """Whether any grounding sources were found."""
        return len(self.grounding_metadata.grounding_chunks) > 0

    @property
    def source_count(self) -> int:
        """Number of sources used for grounding."""
        return len(self.grounding_metadata.grounding_chunks)


class GeminiSearchClient:
    """
    Client for Gemini with Search Grounding enabled.

    Uses the Google GenAI SDK directly (not LiteLLM) to access
    search grounding features.

    Usage:
        client = GeminiSearchClient()
        result = client.search("What is Islamic Relief USA's rating?")
        print(result.text)
        print(result.grounding_metadata.source_urls)
    """

    # Default model for search grounding - use same as main LLM client
    DEFAULT_MODEL = "gemini-3-flash-preview"

    # Cost per million tokens (Jan 2026 pricing)
    COSTS = {
        "gemini-3-flash-preview": {"input": 0.10, "output": 0.40},
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    }

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Gemini Search client.

        Args:
            model: Gemini model to use (default: gemini-2.5-flash)
            api_key: Google API key (defaults to GEMINI_API_KEY or GOOGLE_API_KEY env var)
        """
        self.model = model
        # Check both env vars - GOOGLE_API_KEY first (more likely to be valid),
        # then GEMINI_API_KEY. Skip placeholder values that start with "your_".
        self.api_key = api_key
        if not self.api_key:
            for env_var in ["GOOGLE_API_KEY", "GEMINI_API_KEY"]:
                key = os.environ.get(env_var)
                if key and not key.startswith("your_"):
                    self.api_key = key
                    break

        if not self.api_key:
            raise ValueError(
                "API key not found. Set GEMINI_API_KEY or GOOGLE_API_KEY in environment, "
                "or pass api_key parameter."
            )

        # Initialize the GenAI client
        self.client = genai.Client(api_key=self.api_key)
        logger.info(f"GeminiSearchClient initialized with model: {model}")

    def search(
        self,
        query: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
    ) -> SearchGroundingResult:
        """
        Perform a search-grounded query.

        Args:
            query: The question or search query
            system_prompt: Optional system instructions
            temperature: Sampling temperature (lower = more deterministic)
            max_output_tokens: Maximum tokens in response (prevents truncation issues)

        Returns:
            SearchGroundingResult with text and grounding metadata
        """
        # Build the content with optional system prompt
        contents = query
        if system_prompt:
            contents = f"{system_prompt}\n\n{query}"

        # Configure with Google Search tool
        # Use low temperature and top_k for deterministic extraction
        config = types.GenerateContentConfig(
            temperature=temperature,
            top_k=40,  # Limit token sampling for more determinism
            max_output_tokens=max_output_tokens,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )

            # Extract response text
            text = response.text if response.text else ""

            # Parse grounding metadata
            grounding_metadata = self._parse_grounding_metadata(response)

            # Calculate tokens and cost
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            cost = self._calculate_cost(input_tokens, output_tokens)

            logger.info(
                f"Search completed: {len(grounding_metadata.grounding_chunks)} sources, "
                f"{input_tokens}→{output_tokens} tokens, ${cost:.6f}"
            )

            return SearchGroundingResult(
                text=text,
                grounding_metadata=grounding_metadata,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

        except Exception as e:
            logger.error(f"Search grounding failed: {e}")
            raise

    def _parse_grounding_metadata(self, response: Any) -> GroundingMetadata:
        """Parse grounding metadata from Gemini response."""
        # Get grounding metadata from first candidate
        if not response.candidates or len(response.candidates) == 0:
            return GroundingMetadata()

        candidate = response.candidates[0]
        raw_metadata = getattr(candidate, "grounding_metadata", None)

        if not raw_metadata:
            return GroundingMetadata()

        # Parse web search queries
        web_search_queries = list(getattr(raw_metadata, "web_search_queries", []) or [])

        # Parse grounding chunks
        grounding_chunks = []
        raw_chunks = getattr(raw_metadata, "grounding_chunks", []) or []
        for chunk in raw_chunks:
            # Check if it's a web chunk
            web = getattr(chunk, "web", None)
            if web:
                grounding_chunks.append(
                    GroundingChunk(
                        uri=getattr(web, "uri", None),
                        title=getattr(web, "title", None),
                        domain=getattr(web, "domain", None),
                    )
                )

        # Parse grounding supports (claim-to-source links)
        grounding_supports = []
        raw_supports = getattr(raw_metadata, "grounding_supports", []) or []
        for support in raw_supports:
            segment = getattr(support, "segment", None)
            segment_text = None
            start_index = None
            end_index = None
            if segment:
                segment_text = getattr(segment, "text", None)
                start_index = getattr(segment, "start_index", None)
                end_index = getattr(segment, "end_index", None)

            confidence_scores = list(getattr(support, "confidence_scores", []) or [])
            chunk_indices = list(getattr(support, "grounding_chunk_indices", []) or [])

            grounding_supports.append(
                GroundingSupport(
                    segment_text=segment_text,
                    start_index=start_index,
                    end_index=end_index,
                    confidence_scores=confidence_scores,
                    grounding_chunk_indices=chunk_indices,
                )
            )

        # Parse retrieval queries
        retrieval_queries = list(getattr(raw_metadata, "retrieval_queries", []) or [])

        return GroundingMetadata(
            web_search_queries=web_search_queries,
            grounding_chunks=grounding_chunks,
            grounding_supports=grounding_supports,
            retrieval_queries=retrieval_queries,
        )

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        # D-002: Fallback to DEFAULT_MODEL costs, not hardcoded model
        costs = self.COSTS.get(self.model, self.COSTS.get(self.DEFAULT_MODEL, {"input": 0.10, "output": 0.40}))
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost


# Convenience function
def search_with_grounding(
    query: str,
    system_prompt: Optional[str] = None,
    model: str = GeminiSearchClient.DEFAULT_MODEL,
) -> SearchGroundingResult:
    """
    Convenience function for one-off search-grounded queries.

    Args:
        query: The search query
        system_prompt: Optional system instructions
        model: Gemini model to use

    Returns:
        SearchGroundingResult
    """
    client = GeminiSearchClient(model=model)
    return client.search(query, system_prompt=system_prompt)

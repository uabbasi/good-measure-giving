"""Prompt utilities for LLM interactions.

Shared utilities for sanitizing and preparing text for LLM prompts.
"""

import re
from typing import Any


def sanitize_for_prompt(text: Any, max_length: int = 5000) -> str:
    """Sanitize text to prevent prompt injection.

    Removes dangerous patterns that could break prompt boundaries or inject
    instructions. Also truncates excessively long content.

    Args:
        text: The text to sanitize (will be converted to string if not already)
        max_length: Maximum allowed length before truncation

    Returns:
        Sanitized string safe for prompt insertion
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # Remove potential prompt delimiters and instruction markers
    dangerous_patterns = [
        r"\n-{3,}\n",  # Markdown horizontal rules (----)
        r"\n#{1,6}\s",  # Markdown headers that could inject sections
        r"<\|.*?\|>",  # Special tokens like <|im_start|>
        r"\[INST\]|\[/INST\]",  # Llama instruction markers
        r"<<SYS>>|<</SYS>>",  # Llama system markers
        r"<\|system\|>|<\|user\|>|<\|assistant\|>",  # Chat markers
        r"Human:|Assistant:",  # Anthropic-style markers
    ]
    result = text
    for pattern in dangerous_patterns:
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)

    # Truncate excessively long fields
    if len(result) > max_length:
        result = result[:max_length] + "... [truncated]"

    return result.strip()

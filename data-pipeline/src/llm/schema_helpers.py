"""Schema helpers for LLM structured output.

Utilities for preparing JSON schemas for different LLM providers.
"""

from typing import Any


def fix_schema_for_anthropic(schema: dict) -> dict:
    """Add additionalProperties: false to all object types in schema.

    Anthropic's structured output requires explicit additionalProperties: false
    on all object types. Pydantic doesn't add this by default.

    Args:
        schema: JSON schema dict (typically from Pydantic model)

    Returns:
        Modified schema with additionalProperties: false on all objects
    """

    def fix_object(obj: Any) -> Any:
        if isinstance(obj, dict):
            if obj.get("type") == "object":
                obj["additionalProperties"] = False
            for key, value in obj.items():
                obj[key] = fix_object(value)
        elif isinstance(obj, list):
            return [fix_object(item) for item in obj]
        return obj

    return fix_object(schema.copy())

"""
Prompt loader with versioning and content hashing.

Prompts use a frontmatter format:
```
# PROMPT: prompt_name
# VERSION: 1.0.0
# LAST_UPDATED: 2025-11-27
# DESCRIPTION: Brief description
---
[actual prompt content]
```

The hash is computed from content BELOW the --- separator only.
This allows version bumps without changing the hash, and validates
that content changes are accompanied by version bumps.

Usage:
    from src.llm.prompt_loader import load_prompt, PromptInfo

    prompt = load_prompt("baseline_narrative")
    print(prompt.version)       # "2.0.0"
    print(prompt.content_hash)  # "a1b2c3d4e5f6..."
    print(prompt.content)       # The actual prompt text
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Environment variable for version check mode
# Values: "warn" (default), "strict" (error), "off" (silent)
VERSION_CHECK_MODE = os.environ.get("PROMPT_VERSION_CHECK", "warn")

# Cache of known good hashes for each version (populated at runtime)
# Format: {prompt_name: {version: content_hash}}
_version_hash_cache: Dict[str, Dict[str, str]] = {}


@dataclass
class PromptInfo:
    """Loaded prompt with metadata."""

    name: str
    version: str
    content: str
    content_hash: str
    last_updated: Optional[str] = None
    description: Optional[str] = None
    file_path: Optional[str] = None

    # Validation state
    hash_mismatch: bool = False  # True if content changed but version didn't

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "prompt_name": self.name,
            "prompt_version": self.version,
            "prompt_hash": self.content_hash,
            "hash_mismatch": self.hash_mismatch,
        }


def _compute_hash(content: str) -> str:
    """Compute SHA256 hash of content, truncated to 16 chars."""
    return hashlib.sha256(content.strip().encode()).hexdigest()[:16]


def _parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    """
    Parse frontmatter and extract content.

    Frontmatter format (at very top of file):
    ```
    # PROMPT: name
    # VERSION: 1.0.0
    # LAST_UPDATED: 2025-11-27
    # DESCRIPTION: Brief description
    # ---PROMPT_START---
    [actual prompt content]
    ```

    The separator `# ---PROMPT_START---` is used to avoid conflicts with
    markdown `---` used within prompts.

    Returns:
        (metadata_dict, content_string)
    """
    # Look for unique separator
    separator_pattern = r"^#\s*---PROMPT_START---\s*$"
    match = re.search(separator_pattern, text, re.MULTILINE)

    if not match:
        # No frontmatter, entire text is content
        return {}, text.strip()

    frontmatter = text[: match.start()]
    content = text[match.end() :]

    # Parse frontmatter lines
    metadata = {}
    for line in frontmatter.strip().split("\n"):
        # Match lines like "# KEY: value"
        line_match = re.match(r"^#\s*(\w+):\s*(.+)$", line.strip())
        if line_match:
            key = line_match.group(1).lower()
            value = line_match.group(2).strip()
            metadata[key] = value

    return metadata, content.strip()


def _get_prompts_dir() -> Path:
    """Get the prompts directory path."""
    return Path(__file__).parent / "prompts"


def load_prompt(
    name: str,
    prompts_dir: Optional[Path] = None,
    check_version: bool = True,
) -> PromptInfo:
    """
    Load a prompt file with version and hash tracking.

    Args:
        name: Prompt name (without .txt extension)
        prompts_dir: Optional custom prompts directory
        check_version: Whether to validate version/hash consistency

    Returns:
        PromptInfo with metadata and content

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        ValueError: If strict mode and hash mismatch detected
    """
    if prompts_dir is None:
        prompts_dir = _get_prompts_dir()

    file_path = prompts_dir / f"{name}.txt"

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    # Read and parse
    text = file_path.read_text()
    metadata, content = _parse_frontmatter(text)

    # Extract metadata with defaults
    version = metadata.get("version", "0.0.0")
    last_updated = metadata.get("last_updated")
    description = metadata.get("description")

    # Compute hash of content only (not frontmatter)
    content_hash = _compute_hash(content)

    # Check for hash mismatch (content changed but version didn't)
    hash_mismatch = False
    if check_version and VERSION_CHECK_MODE != "off":
        if name in _version_hash_cache:
            cached = _version_hash_cache[name]
            if version in cached and cached[version] != content_hash:
                hash_mismatch = True
                msg = (
                    f"Prompt '{name}' content changed but version still {version}. "
                    f"Expected hash {cached[version][:8]}..., got {content_hash[:8]}... "
                    f"Consider bumping the version."
                )
                if VERSION_CHECK_MODE == "strict":
                    raise ValueError(msg)
                elif VERSION_CHECK_MODE == "warn":
                    logger.warning(msg)

        # Cache this version/hash pair
        if name not in _version_hash_cache:
            _version_hash_cache[name] = {}
        _version_hash_cache[name][version] = content_hash

    return PromptInfo(
        name=name,
        version=version,
        content=content,
        content_hash=content_hash,
        last_updated=last_updated,
        description=description,
        file_path=str(file_path),
        hash_mismatch=hash_mismatch,
    )


def load_prompt_raw(name: str, prompts_dir: Optional[Path] = None) -> str:
    """
    Load just the prompt content (for backward compatibility).

    Args:
        name: Prompt name (without .txt extension)
        prompts_dir: Optional custom prompts directory

    Returns:
        Prompt content string (without frontmatter)
    """
    info = load_prompt(name, prompts_dir, check_version=False)
    return info.content


def get_prompt_version(name: str) -> str:
    """Get the version of a prompt file."""
    try:
        info = load_prompt(name, check_version=False)
        return info.version
    except FileNotFoundError:
        return "0.0.0"


def list_prompts(prompts_dir: Optional[Path] = None) -> list[PromptInfo]:
    """List all available prompts with their metadata."""
    if prompts_dir is None:
        prompts_dir = _get_prompts_dir()

    prompts = []
    for file_path in prompts_dir.glob("*.txt"):
        name = file_path.stem
        try:
            info = load_prompt(name, prompts_dir, check_version=False)
            prompts.append(info)
        except Exception as e:
            logger.warning(f"Failed to load prompt {name}: {e}")

    return prompts


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        name = sys.argv[1]
        try:
            info = load_prompt(name)
            print(f"Prompt: {info.name}")
            print(f"Version: {info.version}")
            print(f"Hash: {info.content_hash}")
            print(f"Last Updated: {info.last_updated or 'N/A'}")
            print(f"Description: {info.description or 'N/A'}")
            print(f"Content length: {len(info.content)} chars")
            print("---")
            print(info.content[:500] + "..." if len(info.content) > 500 else info.content)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print("Available prompts:")
        for info in list_prompts():
            print(f"  {info.name}: v{info.version} ({info.content_hash[:8]}...)")

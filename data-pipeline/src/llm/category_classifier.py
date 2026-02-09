"""Category classifier for charity scoring calibration.

Maps charities to categories and loads category-specific scoring prompts.
Categories are defined in config/charity_categories.yaml and prompt
calibrations are in prompts/categories/{CATEGORY}.txt.

Usage:
    from src.llm.category_classifier import get_charity_category, load_category_prompt

    category = get_charity_category("77-0646756")  # Returns "CIVIL_RIGHTS_LEGAL"
    prompt = load_category_prompt("CIVIL_RIGHTS_LEGAL")  # Returns category-specific scoring guide
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Cache for loaded category mappings
_category_cache: Optional[dict] = None


def _get_config_path() -> Path:
    """Get the path to the charity categories config file."""
    return Path(__file__).parent.parent.parent / "config" / "charity_categories.yaml"


def _get_categories_prompt_dir() -> Path:
    """Get the path to the category prompts directory."""
    return Path(__file__).parent / "prompts" / "categories"


def _load_category_config() -> dict:
    """Load and cache the category configuration."""
    global _category_cache

    if _category_cache is not None:
        return _category_cache

    config_path = _get_config_path()
    if not config_path.exists():
        logger.warning(f"Category config not found at {config_path}")
        return {}

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Build reverse lookup: EIN -> category
    ein_to_category = {}
    categories = config.get("categories", {})
    for category_name, category_data in categories.items():
        charities = category_data.get("charities", {})
        for ein, name in charities.items():
            ein_to_category[ein] = category_name

    _category_cache = {
        "categories": categories,
        "ein_to_category": ein_to_category,
    }

    logger.info(f"Loaded {len(ein_to_category)} charity category mappings across {len(categories)} categories")
    return _category_cache


def get_charity_category(ein: str) -> Optional[str]:
    """Get the category for a charity by EIN.

    Args:
        ein: The charity's EIN (e.g., "77-0646756")

    Returns:
        Category name (e.g., "CIVIL_RIGHTS_LEGAL") or None if not found
    """
    config = _load_category_config()
    return config.get("ein_to_category", {}).get(ein)


def get_category_info(category_name: str) -> Optional[dict]:
    """Get the full category info including benchmarks and description.

    Args:
        category_name: Category name (e.g., "CIVIL_RIGHTS_LEGAL")

    Returns:
        Category data dict or None if not found
    """
    config = _load_category_config()
    return config.get("categories", {}).get(category_name)


def load_category_prompt(category_name: str) -> Optional[str]:
    """Load the category-specific scoring calibration prompt.

    Args:
        category_name: Category name (e.g., "CIVIL_RIGHTS_LEGAL")

    Returns:
        Category prompt content or None if not found
    """
    prompt_dir = _get_categories_prompt_dir()
    prompt_path = prompt_dir / f"{category_name}.txt"

    if not prompt_path.exists():
        logger.warning(f"Category prompt not found for {category_name} at {prompt_path}")
        return None

    return prompt_path.read_text()


def get_category_prompt_for_charity(ein: str) -> Optional[str]:
    """Convenience function to get category prompt for a charity by EIN.

    Args:
        ein: The charity's EIN

    Returns:
        Category-specific prompt content or None if not found
    """
    category = get_charity_category(ein)
    if not category:
        logger.info(f"No category mapping found for EIN {ein}")
        return None

    return load_category_prompt(category)


def list_categories() -> list[str]:
    """List all available categories."""
    config = _load_category_config()
    return list(config.get("categories", {}).keys())


def clear_cache():
    """Clear the category cache (useful for testing)."""
    global _category_cache
    _category_cache = None


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        ein = sys.argv[1]
        category = get_charity_category(ein)
        if category:
            print(f"EIN {ein} -> Category: {category}")
            info = get_category_info(category)
            if info:
                print(f"Description: {info.get('description')}")
                print(f"Benchmarks: {', '.join(info.get('benchmarks', []))}")
            prompt = load_category_prompt(category)
            if prompt:
                print(f"\nCategory prompt ({len(prompt)} chars):")
                print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        else:
            print(f"No category found for EIN {ein}")
    else:
        print("Available categories:")
        for cat in list_categories():
            info = get_category_info(cat)
            count = len(info.get("charities", {})) if info else 0
            print(f"  {cat}: {count} charities")

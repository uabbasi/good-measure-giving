"""Rubric Registry — Per-archetype Impact weight profiles.

Maps charity categories to archetypes, and archetypes to Impact component
weight profiles.  All profiles sum to 50.

Usage:
    from src.scorers.rubric_registry import get_rubric_config, get_archetype_for_category

    archetype = get_archetype_for_category("CIVIL_RIGHTS_LEGAL")  # "SYSTEMIC_CHANGE"
    rubric = get_rubric_config(archetype)
    # rubric.weights["cost_per_beneficiary"] == 7
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Expected Impact component keys (must match v2_scorers component names)
IMPACT_COMPONENT_KEYS = [
    "cost_per_beneficiary",
    "directness",
    "financial_health",
    "program_ratio",
    "evidence_outcomes",
    "theory_of_change",
    "governance",
]

IMPACT_TOTAL = 50

# Base weights from rubric v4.0.0 — used as the denominator for proportional scaling
BASE_WEIGHTS = {
    "cost_per_beneficiary": 20,
    "directness": 7,
    "financial_health": 7,
    "program_ratio": 6,
    "evidence_outcomes": 5,
    "theory_of_change": 3,
    "governance": 2,
}


@dataclass
class RubricConfig:
    """Impact weight profile for a single archetype."""

    archetype: str
    description: str = ""
    weights: dict[str, int] = field(default_factory=dict)

    def scale_score(self, component_key: str, raw_score: float) -> int:
        """Scale a raw score (computed on v4.0.0 base) to this archetype's weight.

        Uses proportional scaling: scaled = raw * (new_possible / old_possible).
        """
        old_possible = BASE_WEIGHTS[component_key]
        new_possible = self.weights[component_key]
        if old_possible == 0:
            return 0
        return round(raw_score * new_possible / old_possible)


# Module-level cache
_registry_cache: Optional[dict] = None


def _get_config_path() -> Path:
    return Path(__file__).parent.parent.parent / "config" / "rubric_archetypes.yaml"


def _load_registry() -> dict:
    """Load and cache archetype config from YAML."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    config_path = _get_config_path()
    if not config_path.exists():
        logger.warning(f"Rubric archetypes config not found at {config_path}, using defaults")
        _registry_cache = _build_default_registry()
        return _registry_cache

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    archetypes: dict[str, RubricConfig] = {}
    for name, data in raw.get("archetypes", {}).items():
        weights = data.get("weights", {})
        _validate_weights(name, weights)
        archetypes[name] = RubricConfig(
            archetype=name,
            description=data.get("description", ""),
            weights=weights,
        )

    category_map: dict[str, str] = raw.get("category_archetype_map", {})
    default_archetype: str = raw.get("default_archetype", "DIRECT_SERVICE")

    _registry_cache = {
        "archetypes": archetypes,
        "category_map": category_map,
        "default_archetype": default_archetype,
    }
    logger.info(f"Loaded {len(archetypes)} rubric archetypes, {len(category_map)} category mappings")
    return _registry_cache


def _build_default_registry() -> dict:
    """Fallback: single DIRECT_SERVICE archetype using v4.0.0 base weights."""
    default = RubricConfig(
        archetype="DIRECT_SERVICE",
        description="Default fallback",
        weights=dict(BASE_WEIGHTS),
    )
    return {
        "archetypes": {"DIRECT_SERVICE": default},
        "category_map": {},
        "default_archetype": "DIRECT_SERVICE",
    }


def _validate_weights(archetype_name: str, weights: dict[str, int]) -> None:
    """Validate that weights contain the right keys and sum to 50."""
    missing = set(IMPACT_COMPONENT_KEYS) - set(weights.keys())
    if missing:
        raise ValueError(f"Archetype {archetype_name} missing weight keys: {missing}")
    extra = set(weights.keys()) - set(IMPACT_COMPONENT_KEYS)
    if extra:
        raise ValueError(f"Archetype {archetype_name} has unexpected weight keys: {extra}")
    total = sum(weights.values())
    if total != IMPACT_TOTAL:
        raise ValueError(f"Archetype {archetype_name} weights sum to {total}, expected {IMPACT_TOTAL}")


def get_archetype_for_category(category: Optional[str]) -> str:
    """Map a charity category to its archetype name.

    Falls back to the default archetype (DIRECT_SERVICE) for unknown categories.
    """
    registry = _load_registry()
    if category is None:
        return registry["default_archetype"]
    return registry["category_map"].get(category, registry["default_archetype"])


def get_rubric_config(archetype: str) -> RubricConfig:
    """Get the RubricConfig for a given archetype.

    Falls back to default archetype if not found.
    """
    registry = _load_registry()
    config = registry["archetypes"].get(archetype)
    if config is None:
        default = registry["default_archetype"]
        logger.warning(f"Unknown archetype '{archetype}', falling back to {default}")
        config = registry["archetypes"][default]
    return config


def get_rubric_for_category(category: Optional[str]) -> RubricConfig:
    """Convenience: category -> archetype -> RubricConfig in one call."""
    archetype = get_archetype_for_category(category)
    return get_rubric_config(archetype)


def list_archetypes() -> list[str]:
    """List all available archetype names."""
    registry = _load_registry()
    return list(registry["archetypes"].keys())


def clear_cache():
    """Clear the registry cache (useful for testing)."""
    global _registry_cache
    _registry_cache = None

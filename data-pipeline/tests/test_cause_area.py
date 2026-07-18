"""Tests for src/utils/cause_area.py (curation overlay contract #3)."""

from pathlib import Path

import yaml
from src.utils.cause_area import CATEGORY_TO_CAUSE_AREA, derive_cause_area

CONFIG_PATH = Path(__file__).parent.parent / "config" / "charity_categories.yaml"


def test_map_covers_exactly_the_yaml_categories():
    config = yaml.safe_load(CONFIG_PATH.read_text())
    assert set(CATEGORY_TO_CAUSE_AREA) == set(config["categories"])
    assert len(CATEGORY_TO_CAUSE_AREA) == 16


class TestDeriveCauseArea:
    def test_humanitarian_maps_straight_through(self):
        assert derive_cause_area("HUMANITARIAN", None) == "HUMANITARIAN"

    def test_humanitarian_refined_to_extreme_poverty(self):
        assert derive_cause_area("HUMANITARIAN", "EXTREME_POVERTY") == "EXTREME_POVERTY"

    def test_detected_cause_area_normalized(self):
        assert derive_cause_area("HUMANITARIAN", "  extreme_poverty ") == "EXTREME_POVERTY"

    def test_refinement_only_applies_to_humanitarian(self):
        # UNICEF USA's real DB shape: EDUCATION_INTERNATIONAL + detected EXTREME_POVERTY
        assert derive_cause_area("EDUCATION_INTERNATIONAL", "EXTREME_POVERTY") == "EDUCATION_GLOBAL"

    def test_medical_health_maps_to_global_health(self):
        assert derive_cause_area("MEDICAL_HEALTH", None) == "GLOBAL HEALTH"

    def test_detected_value_other_than_extreme_poverty_ignored(self):
        assert derive_cause_area("RELIGIOUS_CONGREGATION", "GLOBAL_HEALTH") == "RELIGIOUS_CULTURAL"

    def test_none_category_is_general(self):
        assert derive_cause_area(None, None) == "GENERAL"

    def test_empty_category_is_general(self):
        assert derive_cause_area("", None) == "GENERAL"

    def test_unknown_category_is_general(self):
        assert derive_cause_area("SPACE_EXPLORATION", None) == "GENERAL"

    def test_lowercase_category_normalized(self):
        assert derive_cause_area("humanitarian", None) == "HUMANITARIAN"

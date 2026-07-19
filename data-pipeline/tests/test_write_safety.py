"""Tests for the non-destructive-synthesize write-safety guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestStalenessConstant:
    def test_constant_is_two_years(self):
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS

        assert DATA_FULL_CONFIDENCE_MAX_AGE_YEARS == 2

    def test_recency_factor_uses_constant(self):
        # Age exactly at the boundary keeps full weight; one past it decays.
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        from src.scorers.v2_scorers import AmalScorerV2

        boundary = DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        assert AmalScorerV2._recency_factor(boundary) == 1.0
        assert AmalScorerV2._recency_factor(boundary + 1) < 1.0

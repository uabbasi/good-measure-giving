"""Shared fixtures for data-pipeline tests.

Note: Tests use DoltDB. For integration tests that need
real data, ensure DoltDB is running locally.
"""

import sys
from pathlib import Path

import pytest

# Add src to path so tests can import from src
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_charity_metrics():
    """Create sample CharityMetrics for testing."""
    from src.parsers.charity_metrics_aggregator import CharityMetrics

    return CharityMetrics(
        ein="12-3456789",
        name="Test Charity",
        mission="Test mission statement",
        programs=["Program 1", "Program 2"],
        total_revenue=1_000_000,
        total_expenses=900_000,
        program_expenses=750_000,
        program_expense_ratio=0.833,
        cn_overall_score=95.0,
        cn_financial_score=96.0,
        cn_accountability_score=94.0,
        candid_seal="Gold",
        is_muslim_focused=True,
        zakat_claim_detected=True,
    )


@pytest.fixture
def sample_raw_sources():
    """Create sample raw data sources for testing."""
    return {
        "charity_navigator": {
            "cn_profile": {
                "name": "Test Charity",
                "overall_score": 95.0,
                "financial_score": 96.0,
                "accountability_score": 94.0,
                "program_expense_ratio": 0.833,
                "total_revenue": 1_000_000,
                "total_expenses": 900_000,
                "program_expenses": 750_000,
            }
        },
        "propublica": {
            "propublica_990": {
                "total_revenue": 1_000_000,
                "total_expenses": 900_000,
            }
        },
        "candid": {
            "candid_profile": {
                "candid_seal": "Gold",
                "ntee_code": "P60",
            }
        },
        "website": {
            "website_profile": {
                "founded_year": 2000,
            }
        },
        "discovered": {
            "discovered_profile": {
                "zakat": {
                    "accepts_zakat": True,
                    "accepts_zakat_evidence": "Test zakat evidence",
                    "accepts_zakat_url": "https://example.org/zakat",
                }
            }
        },
    }

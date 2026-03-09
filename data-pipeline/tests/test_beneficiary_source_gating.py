from src.parsers.charity_metrics_aggregator import CharityMetrics
from src.scorers.v2_scorers import ImpactScorer
from src.validators.source_required_validator import SourceRequiredValidator


def _base_metrics(**overrides):
    payload = {
        "ein": "00-0000000",
        "name": "Test Charity",
        "program_expenses": 100_000,
        "total_expenses": 120_000,
        "program_expense_ratio": 0.86,
        "beneficiaries_served_annually": 1_000,
        "source_attribution": {},
    }
    payload.update(overrides)
    return CharityMetrics(**payload)


def test_cpb_uses_beneficiaries_with_cited_source():
    metrics = _base_metrics(
        source_attribution={
            "beneficiaries_served_annually": {
                "source_url": "https://example.org/impact",
                "source_name": "Charity Website",
            }
        }
    )
    scorer = ImpactScorer()

    cpb = scorer._calculate_cpb(metrics)  # noqa: SLF001 - intentional unit test of gating behavior

    assert cpb is not None
    assert round(cpb, 2) == 100.00


def test_cpb_downweights_plausible_uncited_beneficiaries():
    metrics = _base_metrics(
        source_attribution={
            "beneficiaries_served_annually": {
                "source_url": None,
                "source_name": "Charity Website",
            }
        }
    )
    scorer = ImpactScorer()

    cpb = scorer._calculate_cpb(metrics)  # noqa: SLF001 - intentional unit test of gating behavior
    _raw_cpb, points, evidence = scorer._score_cost_per_beneficiary(metrics, "HUMANITARIAN")  # noqa: SLF001

    assert cpb is not None
    assert 0 < points <= 5  # confidence-weighted + capped
    assert "uncorroborated beneficiary estimate" in evidence


def test_cpb_excludes_implausible_uncited_beneficiaries():
    metrics = _base_metrics(
        beneficiaries_served_annually=1_000_000,
        program_expenses=300_000,  # $0.30 per beneficiary (implausible threshold)
        source_attribution={
            "beneficiaries_served_annually": {
                "source_url": None,
                "source_name": "Charity Website",
            }
        },
    )
    scorer = ImpactScorer()

    cpb = scorer._calculate_cpb(metrics)  # noqa: SLF001 - intentional unit test of gating behavior
    _raw_cpb, points, evidence = scorer._score_cost_per_beneficiary(metrics, "HUMANITARIAN")  # noqa: SLF001

    assert cpb == 0.3
    assert points == 0
    assert "implausible" in evidence


def test_source_required_validator_rejects_non_numeric_impact_metrics():
    validator = SourceRequiredValidator()
    source_data = {
        "candid_profile": None,
        "website_profile": {
            "impact_metrics": {
                "metrics": {
                    "people_reached": "many",
                }
            }
        },
    }

    validated_value, is_valid = validator.validate("beneficiaries_served_annually", 10_000, source_data)

    assert validated_value is None
    assert is_valid is False


def test_source_required_validator_accepts_numeric_impact_metrics():
    validator = SourceRequiredValidator()
    source_data = {
        "candid_profile": None,
        "website_profile": {
            "impact_metrics": {
                "metrics": {
                    "people_reached_annually": "1,500,000",
                }
            }
        },
    }

    validated_value, is_valid = validator.validate("beneficiaries_served_annually", 1_500_000, source_data)

    assert validated_value == 1_500_000
    assert is_valid is True

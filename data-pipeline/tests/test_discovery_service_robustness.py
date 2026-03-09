from src.agents.gemini_search import GroundingMetadata, SearchGroundingResult
from src.services.awards_discovery_service import AwardsDiscoveryService
from src.services.evidence_discovery_service import EvidenceDiscoveryService
from src.services.outcome_discovery_service import OutcomeDiscoveryService
from src.services.toc_discovery_service import TheoryOfChangeDiscoveryService


def _grounding_result(text: str, source_count: int, cost_usd: float = 0.123) -> SearchGroundingResult:
    chunks = [
        {"uri": f"https://example.org/{i}", "title": f"Source {i}", "domain": "example.org"}
        for i in range(source_count)
    ]
    return SearchGroundingResult(
        text=text,
        grounding_metadata=GroundingMetadata(grounding_chunks=chunks, grounding_supports=[]),
        model="gemini-2.5-flash",
        cost_usd=cost_usd,
    )


def test_evidence_zero_sources_invalid_json_is_clean_negative():
    result = _grounding_result('{"third_party_evaluated": true]', source_count=0)
    parsed = EvidenceDiscoveryService()._parse_response(result, "Test Charity")
    assert parsed.third_party_evaluated is False
    assert parsed.error is None


def test_outcome_zero_sources_invalid_json_is_clean_negative():
    result = _grounding_result('{"has_outcomes": true]', source_count=0)
    parsed = OutcomeDiscoveryService()._parse_response(result, "Test Charity")
    assert parsed.has_reported_outcomes is False
    assert parsed.error is None


def test_toc_zero_sources_invalid_json_is_clean_negative():
    result = _grounding_result('{"has_theory_of_change": true]', source_count=0)
    parsed = TheoryOfChangeDiscoveryService()._parse_response(result, "Test Charity")
    assert parsed.has_theory_of_change is False
    assert parsed.error is None


def test_awards_zero_sources_invalid_json_is_clean_negative():
    result = _grounding_result('{"has_awards": true]', source_count=0)
    parsed = AwardsDiscoveryService()._parse_response(result, "Test Charity")
    assert parsed.has_awards is False
    assert parsed.error is None

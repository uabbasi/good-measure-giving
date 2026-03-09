from src.agents.gemini_search import GroundingMetadata, SearchGroundingResult
from src.services.zakat_verification_service import ZakatVerificationService


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


def test_parse_response_zero_sources_no_json_is_clean_negative():
    service = ZakatVerificationService()
    result = _grounding_result("", source_count=0)

    verification = service._parse_response(result, "Maristan", "https://maristan.org")

    assert verification.accepts_zakat is False
    assert verification.confidence == 0.0
    assert verification.source_count == 0
    assert verification.error is None


def test_parse_response_with_sources_and_no_json_is_error():
    service = ZakatVerificationService()
    result = _grounding_result("not json at all", source_count=2)

    verification = service._parse_response(result, "Chicago Community Bond Fund", "https://chicagobond.org")

    assert verification.accepts_zakat is False
    assert verification.error is not None
    assert "No JSON found in zakat response" in verification.error
    assert verification.source_count == 2

"""Tests for the synthesize-time beneficiary metric-semantics verifier.

The verifier makes ONE cheap LLM call to classify what a beneficiary count
actually represents. Only category == "annual_people_served" AND confident
yields verified=True (the state the export gate requires for publication).

No live LLM calls: every test injects a fake client (or forces a raise).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.beneficiary_semantics_verifier import (
    SEMANTIC_CATEGORIES,
    verify_beneficiary_semantics,
)


class _FakeResponse:
    def __init__(self, text: str, model: str = "gemini-2.5-flash-lite", cost_usd: float = 0.0004):
        self.text = text
        self.model = model
        self.cost_usd = cost_usd


class _FakeClient:
    """Records the last generate() kwargs and returns a canned response."""

    def __init__(self, text: str):
        self._text = text
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._text)


class _RaisingClient:
    def generate(self, **kwargs):
        raise RuntimeError("simulated LLM outage")


def _verify(text: str, client=None):
    client = client or _FakeClient(text)
    return (
        verify_beneficiary_semantics(
            charity_name="Test Charity",
            mission="Serves refugees with direct humanitarian aid.",
            value=11_413,
            program_expenses=46_600_000,
            source_path="website_profile.impact_metrics.metrics.people_served_annually",
            metric_context=["people_served_annually", "meals_distributed"],
            llm_client=client,
        ),
        client,
    )


class TestVerifiedState:
    def test_annual_people_served_confident_is_verified(self):
        result, _ = _verify('{"category": "annual_people_served", "confident": true, "reasoning": "headcount"}')
        assert result["category"] == "annual_people_served"
        assert result["confident"] is True
        assert result["verified"] is True
        assert result["model"] == "gemini-2.5-flash-lite"
        assert "timestamp" in result
        assert "error" not in result

    def test_annual_people_served_not_confident_is_unverified(self):
        result, _ = _verify('{"category": "annual_people_served", "confident": false, "reasoning": "unsure"}')
        assert result["verified"] is False

    def test_families_households_is_unverified(self):
        result, _ = _verify('{"category": "families_households", "confident": true, "reasoning": "families"}')
        assert result["category"] == "families_households"
        assert result["verified"] is False

    def test_monetary_value_is_unverified(self):
        result, _ = _verify('{"category": "monetary_value", "confident": true, "reasoning": "usd"}')
        assert result["verified"] is False

    def test_cumulative_total_is_unverified(self):
        result, _ = _verify('{"category": "cumulative_total", "confident": true, "reasoning": "since inception"}')
        assert result["verified"] is False

    def test_reach_or_impressions_is_unverified(self):
        result, _ = _verify('{"category": "reach_or_impressions", "confident": true, "reasoning": "reach"}')
        assert result["verified"] is False

    def test_unknown_category_from_model_is_unverified_not_crash(self):
        result, _ = _verify('{"category": "totally_made_up", "confident": true, "reasoning": "x"}')
        assert result["verified"] is False
        assert result["category"] == "totally_made_up"


class TestFailClosed:
    def test_llm_raise_returns_unverified_other_with_error(self):
        result, _ = _verify("", client=_RaisingClient())
        assert result["category"] == "other"
        assert result["confident"] is False
        assert result["verified"] is False
        assert "error" in result

    def test_unparseable_response_fails_closed(self):
        result, _ = _verify("this is not json at all")
        assert result["verified"] is False
        assert result["category"] == "other"
        assert "error" in result

    def test_markdown_fenced_json_is_parsed(self):
        text = '```json\n{"category": "annual_people_served", "confident": true, "reasoning": "ok"}\n```'
        result, _ = _verify(text)
        assert result["verified"] is True


class TestClientContract:
    def test_uses_json_mode_and_schema(self):
        _, client = _verify('{"category": "other", "confident": false, "reasoning": "x"}')
        assert len(client.calls) == 1
        call = client.calls[0]
        assert call.get("json_mode") is True
        assert call.get("json_schema") is not None

    def test_prompt_includes_core_signals(self):
        _, client = _verify('{"category": "other", "confident": false, "reasoning": "x"}')
        prompt = client.calls[0]["prompt"]
        assert "Test Charity" in prompt
        assert "people_served_annually" in prompt
        assert "46,600,000" in prompt or "46600000" in prompt

    def test_categories_constant_is_complete(self):
        assert "annual_people_served" in SEMANTIC_CATEGORIES
        assert len(SEMANTIC_CATEGORIES) == 8

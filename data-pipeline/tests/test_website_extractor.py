import pytest

from src.llm.llm_client import MODEL_GEMINI_31_PRO, MODEL_GEMINI_3_PRO, MODEL_GPT52
from src.llm.website_extractor import WebsiteExtractor


def test_default_verifier_prefers_gemini_with_openai_fallback():
    extractor = WebsiteExtractor()

    assert extractor.verifier_model == MODEL_GEMINI_31_PRO
    assert extractor.verifier_fallback_models == [MODEL_GEMINI_3_PRO, MODEL_GPT52]


def test_extract_with_verifier_uses_configured_fallback_chain(monkeypatch):
    captured = {}

    class FakeResponse:
        text = '{"mission": "Verified mission"}'
        cost_usd = 0.42

    class FakeLLMClient:
        def __init__(self, model=None, logger=None, task=None, **kwargs):
            captured["init_model"] = model
            captured["logger"] = logger
            captured["task"] = task
            self.fallback_models = []

        def generate(self, prompt, temperature, max_tokens, json_mode):
            captured["fallback_models"] = list(self.fallback_models)
            captured["generate_args"] = {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "json_mode": json_mode,
            }
            return FakeResponse()

    monkeypatch.setattr("src.llm.website_extractor.LLMClient", FakeLLMClient)

    extractor = WebsiteExtractor(
        verifier_model=MODEL_GEMINI_3_PRO,
        verifier_fallback_models=[MODEL_GPT52],
    )

    data, cost = extractor._extract_with_verifier("verify this")

    assert captured["init_model"] == MODEL_GEMINI_3_PRO
    assert captured["fallback_models"] == [MODEL_GPT52]
    assert captured["generate_args"]["json_mode"] is True
    assert data == {"mission": "Verified mission"}
    assert cost == pytest.approx(0.42)

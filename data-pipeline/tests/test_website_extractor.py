import re

import pytest
from src.llm.llm_client import MODEL_GEMINI_25_FLASH, MODEL_GEMINI_31_PRO, MODEL_GPT52
from src.llm.website_extractor import WebsiteExtractor


def test_default_verifier_prefers_gemini_with_openai_fallback():
    extractor = WebsiteExtractor()

    assert extractor.verifier_model == MODEL_GEMINI_31_PRO
    assert extractor.verifier_fallback_models == [MODEL_GEMINI_31_PRO, MODEL_GPT52]


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
        verifier_model=MODEL_GEMINI_25_FLASH,
        verifier_fallback_models=[MODEL_GPT52],
    )

    data, cost = extractor._extract_with_verifier("verify this")

    assert captured["init_model"] == MODEL_GEMINI_25_FLASH
    assert captured["fallback_models"] == [MODEL_GPT52]
    assert captured["generate_args"]["json_mode"] is True
    assert data == {"mission": "Verified mission"}
    assert cost == pytest.approx(0.42)


def _prompt_top_level_keys():
    extractor = WebsiteExtractor()
    prompt = extractor._build_prompt([], "https://example.org")
    schema_block = prompt.split("Required JSON schema:")[1].split("NOTES:")[0]
    keys = set(re.findall(r'^  "([a-z0-9_]+)"\s*:', schema_block, re.MULTILINE))
    return {k for k in keys if not k.startswith("_comment")}


def test_every_prompt_key_has_explicit_merge_class():
    """H6 drift guard: no prompt key may fall into the unverified default branch."""
    keys = _prompt_top_level_keys()
    assert keys, "failed to parse schema keys from prompt"
    classified = WebsiteExtractor.TRUSTED_FIELDS | WebsiteExtractor.HALLUCINATION_PRONE_FIELDS
    unclassified = keys - classified
    assert unclassified == set(), f"prompt keys missing a merge class: {sorted(unclassified)}"


def test_merge_classes_are_disjoint():
    overlap = WebsiteExtractor.TRUSTED_FIELDS & WebsiteExtractor.HALLUCINATION_PRONE_FIELDS
    assert overlap == set(), f"keys in both classes: {sorted(overlap)}"


def test_beneficiary_fields_require_verifier_confirmation():
    """The audit's headline cases: beneficiary counts + impact claims must be prone."""
    for key in ("beneficiaries", "beneficiaries_served", "impact_metrics", "accreditations", "policy_influence"):
        assert key in WebsiteExtractor.HALLUCINATION_PRONE_FIELDS, key


def test_flash_only_prone_claim_is_dropped():
    """End-to-end merge behavior for a newly-prone key."""
    extractor = WebsiteExtractor()
    merged = extractor._merge_ensemble(
        {"beneficiaries_served": 50000, "contact_email": "info@x.org"},
        {"contact_email": "info@x.org"},  # verifier silent on the count
    )
    assert merged["beneficiaries_served"] is None
    assert merged["contact_email"] == "info@x.org"

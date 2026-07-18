"""Guards for model configuration: no retired model IDs, healthy fallback chains.

Retired (Google decommissioned, live-verified dead 2026-07):
- gemini-2.0-flash
- gemini-3-pro-preview
"""

from src.judges.factual_judge import FactualJudge
from src.judges.schemas.config import JudgeConfig
from src.llm.llm_client import (
    MODEL_REGISTRY,
    TASK_MODELS,
    LLMClient,
    LLMTask,
)

RETIRED_MODEL_IDS = {"gemini-2.0-flash", "gemini-3-pro-preview"}


class TestNoRetiredModels:
    def test_registry_has_no_retired_ids(self):
        assert not RETIRED_MODEL_IDS & set(MODEL_REGISTRY.keys())

    def test_registry_litellm_names_have_no_retired_ids(self):
        litellm_names = {cfg["litellm_name"] for cfg in MODEL_REGISTRY.values()}
        for retired in RETIRED_MODEL_IDS:
            assert not any(name.endswith(retired) for name in litellm_names), retired

    def test_task_chains_have_no_retired_ids(self):
        for task, (primary, fallbacks) in TASK_MODELS.items():
            assert primary not in RETIRED_MODEL_IDS, task
            assert not RETIRED_MODEL_IDS & set(fallbacks), task


class TestChainIntegrity:
    def test_every_task_model_is_registered(self):
        for task, (primary, fallbacks) in TASK_MODELS.items():
            assert primary in MODEL_REGISTRY, task
            for m in fallbacks:
                assert m in MODEL_REGISTRY, (task, m)

    def test_every_task_has_a_fallback(self):
        for task, (_primary, fallbacks) in TASK_MODELS.items():
            assert len(fallbacks) >= 1, task

    def test_default_client_has_registered_fallbacks(self):
        client = LLMClient()
        assert client.fallback_models, "default client lost its fallback chain"
        for m in client.fallback_models:
            assert m in MODEL_REGISTRY


class TestJudgeModelConfig:
    def test_judge_default_matches_llm_judge_primary(self):
        primary, _fallbacks = TASK_MODELS[LLMTask.LLM_JUDGE]
        assert JudgeConfig().judge_model == primary == "gemini-2.5-flash-lite"

    def test_judge_default_client_has_fallbacks(self):
        judge = FactualJudge(JudgeConfig())
        client = judge.get_llm_client()
        assert client.model_name == "gemini-2.5-flash-lite"
        assert client.fallback_models, "judge client lost its fallback chain"

    def test_judge_custom_model_restores_task_fallbacks(self):
        judge = FactualJudge(JudgeConfig(judge_model="gemini-2.5-flash"))
        client = judge.get_llm_client()
        assert client.model_name == "gemini-2.5-flash"
        assert client.fallback_models, "custom judge model must keep fallbacks"
        assert "gemini-2.5-flash" not in client.fallback_models

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


class TestTheJudgeDoesNotFallBehindWhatItJudges:
    """The gate had drifted two generations behind the pipeline it gates.

    Narratives were written by gemini-3-flash and judged by gemini-2.5-flash-lite,
    which is how the gate came to read Charity Navigator's YEARS as months, anchor
    its date arithmetic to 2024, and file findings whose own message said "the
    claim is accurate" as blocking errors. Nothing flagged it, because nothing
    compared the two chains.

    Compared on MAJOR generation only. Google does not ship a lite build at
    every minor — there is no 3.6 flash-lite — so holding the judge to the
    narrative model's exact minor would forbid the cheap tier entirely. The
    defect this guards was 2.x judging 3.x, not 3.5 judging 3.6.
    """

    @staticmethod
    def _generation(model_id: str) -> int:
        digits = model_id.removeprefix("gemini-").split("-")[0]
        try:
            return int(float(digits))
        except ValueError:
            return 0

    def test_the_judge_is_no_older_than_the_narrative_generator(self):
        judge, _ = TASK_MODELS[LLMTask.LLM_JUDGE]
        writer, _ = TASK_MODELS[LLMTask.NARRATIVE_GENERATION]
        assert self._generation(judge) >= self._generation(writer), (
            f"judge {judge} is a generation behind the narrative model {writer}"
        )

    def test_every_gemini_in_use_is_current_generation(self):
        for task, (primary, fallbacks) in TASK_MODELS.items():
            for model in (primary, *fallbacks):
                if not model.startswith("gemini-"):
                    continue
                assert self._generation(model) >= 3, (task, model)


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
        assert JudgeConfig().judge_model == primary == "gemini-3.5-flash-lite"

    def test_judge_default_client_has_fallbacks(self):
        judge = FactualJudge(JudgeConfig())
        client = judge.get_llm_client()
        assert client.model_name == "gemini-3.5-flash-lite"
        assert client.fallback_models, "judge client lost its fallback chain"

    def test_judge_custom_model_restores_task_fallbacks(self):
        judge = FactualJudge(JudgeConfig(judge_model="gemini-2.5-flash"))
        client = judge.get_llm_client()
        assert client.model_name == "gemini-2.5-flash"
        assert client.fallback_models, "custom judge model must keep fallbacks"
        assert "gemini-2.5-flash" not in client.fallback_models

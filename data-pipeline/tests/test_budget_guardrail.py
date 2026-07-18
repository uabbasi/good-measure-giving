"""H9: default budget cap, discovery spend tracking, clean exhaustion."""

from types import SimpleNamespace

import pytest
from src.llm.budget_tracker import BudgetExceededError, add_cost, get_limit, get_spent, set_budget


@pytest.fixture(autouse=True)
def reset_budget():
    set_budget(None)
    yield
    set_budget(None)


class TestApplyBudgetCap:
    def test_zero_means_uncapped(self):
        import streaming_runner

        streaming_runner.apply_budget_cap(0)
        assert get_limit() is None

    def test_positive_sets_cap(self):
        import streaming_runner

        streaming_runner.apply_budget_cap(5.0)
        assert get_limit() == 5.0

    def test_negative_raises(self):
        import streaming_runner

        with pytest.raises(ValueError):
            streaming_runner.apply_budget_cap(-1.0)

    def test_default_argparse_value_is_ten(self):
        import streaming_runner

        assert streaming_runner.DEFAULT_BUDGET_USD == 10.0


class TestGeminiSearchBudget:
    def _client_with_fake_api(self, fake_generate):
        from src.agents.gemini_search import GeminiSearchClient

        client = GeminiSearchClient(api_key="test-key")
        client.client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate))
        return client

    def test_search_records_spend(self):
        fake_response = SimpleNamespace(
            text="answer",
            usage_metadata=SimpleNamespace(prompt_token_count=1_000_000, candidates_token_count=1000),
            candidates=[],
        )
        client = self._client_with_fake_api(lambda **kw: fake_response)
        set_budget(100.0)
        result = client.search("test query")
        assert result.cost_usd > 0
        assert get_spent() == pytest.approx(result.cost_usd)

    def test_search_blocks_when_exhausted(self):
        def explode(**kwargs):
            raise AssertionError("google.genai must not be called once the budget is exhausted")

        client = self._client_with_fake_api(explode)
        set_budget(0.001)
        add_cost(0.001)
        with pytest.raises(BudgetExceededError):
            client.search("test query")

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

    def test_default_model_cost_uses_registry_prices(self):
        """Tracked discovery spend must use the authoritative MODEL_REGISTRY prices."""
        from src.agents.gemini_search import GeminiSearchClient
        from src.llm.llm_client import MODEL_REGISTRY

        client = GeminiSearchClient(api_key="test-key")
        registry_entry = MODEL_REGISTRY[client.model]
        cost = client._calculate_cost(1_000_000, 1_000_000)
        assert cost == pytest.approx(registry_entry["cost_per_1m_input"] + registry_entry["cost_per_1m_output"])


# Discovery service wrappers: (module, class, search-calling method)
_DISCOVERY_SERVICES = [
    ("src.services.evidence_discovery_service", "EvidenceDiscoveryService", "discover"),
    ("src.services.zakat_verification_service", "ZakatVerificationService", "verify"),
    ("src.services.awards_discovery_service", "AwardsDiscoveryService", "discover"),
    ("src.services.toc_discovery_service", "TheoryOfChangeDiscoveryService", "discover"),
    ("src.services.outcome_discovery_service", "OutcomeDiscoveryService", "discover"),
]


class TestBudgetPropagatesThroughDiscovery:
    """BudgetExceededError must not degrade into an ordinary error result anywhere."""

    @pytest.mark.parametrize("module_name,class_name,method", _DISCOVERY_SERVICES)
    def test_service_reraises_budget_error(self, module_name, class_name, method):
        import importlib

        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        svc = cls.__new__(cls)  # skip __init__ (would build a real GeminiSearchClient)

        def raise_budget(**kwargs):
            raise BudgetExceededError("cap hit")

        svc.client = SimpleNamespace(search=raise_budget)
        svc.model = "test-model"
        with pytest.raises(BudgetExceededError):
            getattr(svc, method)("Test Charity", None)

    def test_run_discovery_phase_reraises_budget_error(self, monkeypatch):
        """The executor loop's catch-all must not swallow BudgetExceededError."""
        import streaming_runner

        class FakeService:
            def __init__(self, *args, **kwargs):
                pass

            def verify(self, *args, **kwargs):
                raise BudgetExceededError("cap hit")

            def discover(self, *args, **kwargs):
                raise BudgetExceededError("cap hit")

        for svc_name in [
            "ZakatVerificationService",
            "EvidenceDiscoveryService",
            "OutcomeDiscoveryService",
            "TheoryOfChangeDiscoveryService",
            "AwardsDiscoveryService",
        ]:
            monkeypatch.setattr(streaming_runner, svc_name, FakeService)

        fake_logger = SimpleNamespace(
            info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None
        )
        with pytest.raises(BudgetExceededError):
            streaming_runner.run_discovery_phase("12-3456789", "Test Charity", "https://example.org", None, fake_logger)


class TestProcessCharityBudgetPaths:
    _CHARITY = {"ein": "12-3456789", "name": "Test Charity", "website": "https://example.org"}
    _LOGGER = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None)

    def test_pre_charity_skip_when_exhausted(self, monkeypatch):
        import streaming_runner

        def forbid(*args, **kwargs):
            raise AssertionError("no work may start once the budget is exhausted")

        monkeypatch.setattr(streaming_runner, "_get_worker_resources", forbid)
        set_budget(0.001)
        add_cost(0.001)
        result = streaming_runner.process_charity_full(self._CHARITY, 1, 1, "test-model", self._LOGGER)
        assert result["budget_exhausted"] is True
        assert result["success"] is False

    def test_mid_charity_budget_error_sets_budget_exhausted(self, monkeypatch):
        import streaming_runner

        def raise_budget(*args, **kwargs):
            raise BudgetExceededError("cap hit mid-charity")

        monkeypatch.setattr(streaming_runner, "_get_worker_resources", raise_budget)
        set_budget(100.0)  # not exhausted up-front; error surfaces mid-run
        result = streaming_runner.process_charity_full(self._CHARITY, 1, 1, "test-model", self._LOGGER)
        assert result["budget_exhausted"] is True
        assert result["success"] is False
        assert "cap hit mid-charity" in result["error"]


class TestExhaustionMessage:
    def test_message_names_uncapped_escape_hatch(self):
        from src.llm.budget_tracker import check_budget

        set_budget(0.001)
        add_cost(0.001)
        with pytest.raises(BudgetExceededError, match=r"--budget 0"):
            check_budget()

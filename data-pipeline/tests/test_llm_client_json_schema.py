"""LLMClient must emit the litellm/OpenAI response_format convention for json_schema.

litellm 1.81.0's Gemini transformer extracts new_value["json_schema"]["schema"];
passing the raw schema dict as "json_schema" silently drops structured output.
"strict" is intentionally omitted: OpenAI strict mode requires
additionalProperties:false + all-props-required, which the judges' Pydantic
schemas (Optional fields) do not satisfy; Gemini ignores it.
"""

from unittest.mock import MagicMock

import src.llm.llm_client as llm_client_module
from src.llm.llm_client import LLMClient


def _fake_completion_response():
    response = MagicMock()
    message = MagicMock()
    message.content = "{}"
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"
    response.choices = [choice]
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    response.usage.prompt_tokens_details = None
    response.usage.cache_read_input_tokens = None
    response.usage.cache_creation_input_tokens = None
    return response


def _patch_llm(monkeypatch, captured):
    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_completion_response()

    monkeypatch.setattr(llm_client_module, "completion", fake_completion)
    monkeypatch.setattr(llm_client_module, "completion_cost", lambda completion_response: 0.0)
    monkeypatch.setattr(llm_client_module, "_budget_check", lambda: None)
    monkeypatch.setattr(llm_client_module, "_budget_add_cost", lambda cost: None)


def test_json_schema_wrapped_in_litellm_convention(monkeypatch):
    captured = {}
    _patch_llm(monkeypatch, captured)

    client = LLMClient(model="gemini-3-flash-preview")
    schema = {"title": "MyResult", "type": "object", "properties": {}}
    client.generate("hi", json_mode=True, json_schema=schema)

    rf = captured["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["schema"] == schema
    assert rf["json_schema"]["name"] == "MyResult"


def test_json_mode_without_schema_uses_json_object(monkeypatch):
    captured = {}
    _patch_llm(monkeypatch, captured)

    client = LLMClient(model="gemini-3-flash-preview")
    client.generate("hi", json_mode=True)

    assert captured["response_format"] == {"type": "json_object"}

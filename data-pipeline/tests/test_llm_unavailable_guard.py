"""An LLM we could not REACH must never be recorded as an LLM that ANSWERED.

On 2026-07-26 a DNS failure to Gemini (`litellm.APIConnectionError: [Errno 8]
nodename nor servname provided`) ran through synthesize for all 166 charities.
Both LLM-backed enrichers caught it with a bare `except Exception` and returned
a degraded value:

  * verify_beneficiary_semantics -> {"verified": False, "confident": False,
    "category": "other", "error": ...}  — an outage stamped as a verdict
  * detect_program_focus_tags    -> ([], 0.0)                — read downstream
    as "this charity has no program focus tags"

Because CharityDataRepository.upsert writes every field including None, those
degraded values overwrote good data: program_focus_tags went from 0 NULL to 119
NULL across 169 charities, and 35 charities flipped to
beneficiariesExcludedFromScoring.

A model that returns an unusable answer is still an answer, and staying
fail-closed there is correct. A model we never reached is not an answer at all
and must stop the request instead of writing a conclusion nobody drew.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.errors import LLMUnavailableError


class _Boom:
    """Stands in for a client whose transport fails."""

    def __init__(self, exc):
        self._exc = exc

    def generate(self, **kwargs):
        raise self._exc


class _BadAnswer:
    """Reached the model; the reply is unusable."""

    def generate(self, **kwargs):
        class R:
            text = "not json at all"
            model = "gemini-x"
            cost_usd = 0.0
        return R()


class TestBeneficiarySemanticsVerifier:
    def _call(self, client):
        from src.services.beneficiary_semantics_verifier import verify_beneficiary_semantics
        return verify_beneficiary_semantics(
            charity_name="Example", mission="m", value=1000,
            program_expenses=100, source_path="p", llm_client=client,
        )

    def test_unreachable_model_raises_instead_of_stamping_a_verdict(self):
        exc = ConnectionError("[Errno 8] nodename nor servname provided, or not known")
        with pytest.raises(LLMUnavailableError):
            self._call(_Boom(exc))

    def test_unusable_answer_still_fails_closed(self):
        """The model responded — staying fail-closed here is correct."""
        stamp = self._call(_BadAnswer())
        assert stamp["verified"] is False
        assert stamp["confident"] is False


class TestProgramFocusTags:
    def _call(self, client, monkeypatch):
        import synthesize
        monkeypatch.setattr(synthesize, "LLMClient", lambda **kw: client)
        return synthesize.detect_program_focus_tags(
            mission="feeding people", programs=["food"], name="Example",
        )

    def test_unreachable_model_raises_instead_of_returning_no_tags(self, monkeypatch):
        exc = ConnectionError("[Errno 8] nodename nor servname provided, or not known")
        with pytest.raises(LLMUnavailableError):
            self._call(_Boom(exc), monkeypatch)

    def test_unusable_answer_returns_no_tags_without_raising(self, monkeypatch):
        tags, cost = self._call(_BadAnswer(), monkeypatch)
        assert tags == []

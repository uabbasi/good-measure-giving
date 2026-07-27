"""Regression coverage for the explicit-NULL-vs-missing-key bug class in
`RichNarrativeGenerator`: several nullable `json` columns (`dolt_schema.sql`)
were read with `d.get(key, {})`, whose default only applies when `key` is
*missing* — not when the column holds an explicit SQL NULL. For an explicit
NULL, `.get(key, {})` returns `None`, and the very next `.get(...)` call on
that `None` raises `AttributeError`.

`score_details` (the reported crash) is covered in
test_rich_narrative_program_ratio.py. This file covers the two other
call sites that shared the same bug: `baseline_narrative` (used twice in
`generate()`) and `source_attribution` (used in `_inject_verified_metrics`).
"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

from src.services.rich_narrative_generator import RichNarrativeGenerator
from src.validators.consistency_validator import ValidationResult

EIN = "13-5660870"


def _generator(**overrides):
    """Build a RichNarrativeGenerator with every collaborator stubbed except
    the real `_inject_immutable_fields` / `_inject_verified_metrics` /
    `_canonicalize_citation_urls`, so the explicit-NULL handling in
    `generate()` itself is genuinely exercised."""
    gen = object.__new__(RichNarrativeGenerator)

    baseline = overrides.get(
        "baseline",
        {
            "amal_score": 68,
            "wallet_tag": "SADAQAH-ELIGIBLE",
            "baseline_narrative": None,  # explicit SQL NULL, not a missing key
        },
    )

    gen.eval_repo = Mock()
    gen.charity_data_repo = overrides.get("charity_data_repo", Mock(get=Mock(return_value={})))
    gen.raw_data_repo = Mock(get_by_source=Mock(return_value=None))
    gen.citation_service = Mock(build_registry=Mock(return_value=SimpleNamespace(sources=[])))
    gen.reconciliation_engine = Mock(reconcile=Mock(return_value=None))
    gen.llm_client = Mock(
        generate=Mock(return_value=SimpleNamespace(cost_usd=0.05, text=json.dumps({"summary": "Generated."})))
    )
    gen.validator = Mock(
        validate=Mock(return_value=ValidationResult(is_valid=True)),
        validate_cn_score_citations=Mock(),
    )
    gen.last_generation_cost = 0.0

    gen._load_baseline = Mock(return_value=baseline)
    gen._assemble_investment_memo_data = Mock(return_value={})
    gen._load_metrics = Mock(return_value=None)
    gen._build_prompt = Mock(return_value="prompt")
    gen._validate_external_evaluations = Mock(side_effect=lambda ein, rich_content, *a, **kw: rich_content)
    gen._store_results = Mock()

    return gen


class TestBaselineNarrativeExplicitNull:
    def test_generate_does_not_crash_when_baseline_narrative_is_explicitly_null(self):
        """generate() reads baseline_narrative twice (immutable-field
        injection, then post-sanitize re-injection). Both used
        `baseline.get("baseline_narrative", {})`, which returns None for an
        explicit NULL, and the real `_inject_immutable_fields` /
        dimension-backfill code immediately calls `.get(...)` on the result."""
        gen = _generator()

        result = gen.generate(EIN)

        assert result is not None
        assert result["summary"] == "Generated."


class TestSourceAttributionExplicitNull:
    def test_inject_verified_metrics_does_not_crash_when_source_attribution_is_explicitly_null(self):
        """source_attribution is a nullable json column; charity_data.get(
        "source_attribution", {}) returned None for an explicit NULL, and the
        get_source_value() closure immediately called .get(...) on it."""
        gen = object.__new__(RichNarrativeGenerator)
        gen.charity_data_repo = Mock(
            get=Mock(return_value={"source_attribution": None, "ein": EIN})
        )
        gen.raw_data_repo = Mock(get_by_source=Mock(return_value=None))

        result = gen._inject_verified_metrics(EIN, {"financial_deep_dive": {}})

        assert result is not None

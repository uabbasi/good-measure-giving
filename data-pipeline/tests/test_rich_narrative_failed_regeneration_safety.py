"""A failed rich-narrative regeneration must not destroy the previously-stored,
previously-validated narrative.

`RichNarrativeGenerator.generate()` used to call `eval_repo.clear_rich_narrative()`
whenever a freshly regenerated narrative failed consistency validation. That
NULLed the stored `rich_narrative`/`rich_strategic_narrative` fields even though
the existing content isn't stale -- it's the last content that DID pass
validation. Nothing downstream is protected by the deletion: the standing
error already blocks this generation attempt from being used, and (via
judge_phase's score-judge retry) the export gate stays closed either way.
Deleting only converts a recoverable state into permanent content loss.
"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

from src.services.rich_narrative_generator import RichNarrativeGenerator
from src.validators.consistency_validator import ValidationResult

EIN = "13-5660870"


def _generator(**overrides):
    """Build a RichNarrativeGenerator with every collaborator stubbed except
    the piece under test (the post-validation branch in `generate()`)."""
    gen = object.__new__(RichNarrativeGenerator)

    baseline = {
        "amal_score": 68,
        "wallet_tag": "SADAQAH-ELIGIBLE",
        "baseline_narrative": {"summary": "Baseline summary."},
        # No rich_narrative yet on the baseline object itself -- irrelevant
        # to this test, which exercises the post-generation validation branch.
    }

    gen.eval_repo = overrides.get("eval_repo", Mock())
    gen.charity_data_repo = Mock(get=Mock(return_value={}))
    gen.raw_data_repo = Mock()
    gen.citation_service = Mock(build_registry=Mock(return_value=SimpleNamespace(sources=[])))
    gen.reconciliation_engine = Mock(reconcile=Mock(return_value=None))
    gen.llm_client = Mock(
        generate=Mock(
            return_value=SimpleNamespace(cost_usd=0.05, text=json.dumps({"summary": "Regenerated summary."}))
        )
    )
    gen.validator = overrides.get(
        "validator",
        Mock(
            validate=Mock(
                return_value=ValidationResult(is_valid=False)  # populated by caller below
            ),
            validate_cn_score_citations=Mock(),
        ),
    )
    gen.last_generation_cost = 0.0

    gen._load_baseline = Mock(return_value=baseline)
    gen._assemble_investment_memo_data = Mock(return_value={})
    gen._load_metrics = Mock(return_value=None)
    gen._build_prompt = Mock(return_value="prompt")
    gen._inject_immutable_fields = Mock(side_effect=lambda rich_content, *a, **kw: rich_content)
    gen._canonicalize_citation_urls = Mock(side_effect=lambda rich_content, *a, **kw: rich_content)
    gen._validate_external_evaluations = Mock(side_effect=lambda ein, rich_content, *a, **kw: rich_content)
    gen._store_results = Mock()

    return gen


def _failed_validation_result() -> ValidationResult:
    result = ValidationResult(is_valid=True)
    result.add_error(
        field="program_expense_ratio",
        baseline_value=0.83,
        rich_value=0.48,
        message="Rich narrative contradicts baseline program ratio",
    )
    return result


class TestFailedRegenerationDoesNotDestroyExistingNarrative:
    def test_failed_consistency_validation_leaves_stored_narrative_intact(self):
        """This must fail before the fix: the old code called
        eval_repo.clear_rich_narrative(ein), NULLing the previously-validated
        rich_narrative even though this generation attempt (not the stored
        content) is what failed."""
        eval_repo = Mock()
        validator = Mock(validate=Mock(return_value=_failed_validation_result()), validate_cn_score_citations=Mock())
        gen = _generator(eval_repo=eval_repo, validator=validator)

        result = gen.generate(EIN)

        assert result is None
        eval_repo.clear_rich_narrative.assert_not_called()

    def test_failed_consistency_validation_returns_none_without_raising(self):
        eval_repo = Mock()
        validator = Mock(validate=Mock(return_value=_failed_validation_result()), validate_cn_score_citations=Mock())
        gen = _generator(eval_repo=eval_repo, validator=validator)

        assert gen.generate(EIN) is None

"""temperature=0 did not make the factual judge reproducible. Consensus does.

`_verify_claims_with_llm` already sets temperature=0.0 with the comment "a
publication gate must not change its mind on identical input", after measuring
[1, 1, 0] errors across three rolls at the client default of 0.1. Temperature 0 is
not actually bit-reproducible in a served model, and this run proved the gate still
flips: across two consecutive runs with a BYTE-IDENTICAL judge_content_hash,

    27-3175543 UMR      13aad00e94299cfc   0 errors -> 1 error
    77-0442850 Rahima   5f54d69843b4f4b9   1 error  -> 0 errors
    93-2136609 Clinic   e1912686657e7fca   0 errors -> 1 error

Same content, same code, different publication decision. The flipping errors were
interpretive ("the narrative *implies* revenue is primarily cash-based"), which is
exactly the kind of judgement that varies roll to roll.

`score_judge` already solved this class: CONSENSUS_ROLLS = 3, an ERROR stands only
on a majority of completed rolls, and it fails CLOSED when no roll completes --
"gating on a single roll produced spurious publication blocks". `factual_judge`
gated publication on a single roll. This mirrors the precedent.

The deterministic `_quick_checks` are deliberately NOT part of the vote: they don't
flip, so subjecting them to consensus would only weaken them.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.factual_judge import FactualJudge, LLMFactualResult
from src.judges.schemas.verdict import Severity, ValidationIssue


def _issue(severity=Severity.ERROR, field="revenue"):
    return ValidationIssue(severity=severity, field=field, message="mismatch")


def _roll(*issues):
    return LLMFactualResult(issues=list(issues), cost=0.001, claims_checked=3, claims_verified=3)


def _judge():
    j = object.__new__(FactualJudge)
    return j


OUTPUT = {"narrative": {"summary": "Some narrative text."}, "ein": "27-3175543"}
CONTEXT = {"metrics": {}}


def _validate_with_rolls(rolls):
    """Run validate() with _verify_claims_with_llm returning each roll in turn."""
    judge = _judge()
    seq = list(rolls)
    with patch.object(FactualJudge, "_quick_checks", return_value=[]), \
         patch.object(FactualJudge, "_verify_claims_with_llm", side_effect=seq):
        return judge.validate(OUTPUT, CONTEXT)


def _errors(verdict):
    return [i for i in verdict.issues if i.severity == Severity.ERROR]


class TestMajorityRules:
    def test_a_single_dissenting_roll_does_not_block_publication(self):
        """The observed flake: 1 of 3 rolls invents an interpretive error."""
        verdict = _validate_with_rolls([_roll(_issue()), _roll(), _roll()])
        assert _errors(verdict) == [], "a minority error must not gate publication"
        assert verdict.passed is True

    def test_a_majority_of_rolls_finding_errors_still_blocks(self):
        """The gate must not get weaker: a real error found by 2+ rolls stands."""
        verdict = _validate_with_rolls([_roll(_issue()), _roll(_issue()), _roll()])
        assert len(_errors(verdict)) >= 1
        assert verdict.passed is False

    def test_unanimous_errors_block(self):
        verdict = _validate_with_rolls([_roll(_issue()), _roll(_issue()), _roll(_issue())])
        assert verdict.passed is False

    def test_unanimous_clean_passes(self):
        verdict = _validate_with_rolls([_roll(), _roll(), _roll()])
        assert verdict.passed is True
        assert _errors(verdict) == []


class TestNonGatingAndFailClosed:
    def test_warnings_are_not_subject_to_the_vote(self):
        """Warnings never gate, so a single roll reporting them is enough to keep
        them for the editorial queue."""
        verdict = _validate_with_rolls([
            _roll(_issue(Severity.WARNING, "citation")), _roll(), _roll()
        ])
        assert verdict.passed is True
        assert any(i.severity == Severity.WARNING for i in verdict.issues)

    def test_no_completed_roll_fails_closed(self):
        """A judge that verified nothing must not report 0 errors and open the
        gate on an unchecked narrative -- score_judge does the same."""
        verdict = _validate_with_rolls([None, None, None])
        assert verdict.passed is False, "zero completed rolls must fail CLOSED"
        assert len(_errors(verdict)) >= 1


class TestDeterministicChecksAreNotDiluted:
    def test_quick_check_errors_survive_even_with_all_rolls_clean(self):
        """_quick_checks is arithmetic, not prose -- it doesn't flip, so it must
        not need a majority to count."""
        judge = _judge()
        with patch.object(FactualJudge, "_quick_checks", return_value=[_issue(field="arith")]), \
             patch.object(FactualJudge, "_verify_claims_with_llm",
                          side_effect=[_roll(), _roll(), _roll()]):
            verdict = judge.validate(OUTPUT, CONTEXT)
        assert verdict.passed is False
        assert any(i.field == "arith" for i in _errors(verdict))

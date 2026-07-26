"""H4: baseline prompt unification — drift guard between template and call site."""

import re
from string import Formatter
from types import SimpleNamespace

import pytest
from baseline import (
    _baseline_prompt_kwargs,
    _repair_removal_artifacts,
    build_baseline_prompt,
    sanitize_narrative_metrics,
)
from src.llm.prompt_loader import load_prompt
from src.utils.phase_fingerprint import PHASE_CODE_FILES


def _fake_scores(wallet_tag="ZAKAT-ELIGIBLE"):
    return SimpleNamespace(
        wallet_tag=wallet_tag,
        amal_score=81,
        impact=SimpleNamespace(score=37, directness_level="HIGH", cost_per_beneficiary=907),
        alignment=SimpleNamespace(score=44, muslim_donor_fit_level="STRONG", cause_urgency_label="HIGH"),
        data_confidence=SimpleNamespace(overall=0.8, badge="HIGH"),
    )


def test_baseline_prompt_file_is_v2():
    info = load_prompt("baseline_narrative", check_version=False)
    assert info.version == "2.3.0"
    assert "{charity_name}" in info.content
    assert "{zakat_constraint_text}" in info.content
    # v1.1.0 style rules survived the merge
    assert "8th grade reading level" in info.content
    assert "Do NOT reveal internal assessment scores" in info.content


def test_template_placeholders_match_format_kwargs(sample_charity_metrics):
    """THE drift guard: template placeholders == kwargs at the call site."""
    info = load_prompt("baseline_narrative", check_version=False)
    placeholders = {name for _, name, _, _ in Formatter().parse(info.content) if name}
    kwargs = _baseline_prompt_kwargs(sample_charity_metrics, _fake_scores(), 3, "[1] Charity Navigator")
    assert placeholders == set(kwargs.keys())


def test_build_baseline_prompt_renders_cleanly(sample_charity_metrics):
    prompt, info = build_baseline_prompt(sample_charity_metrics, _fake_scores(), 3, "[1] Charity Navigator")
    assert info.version == "2.3.0"
    assert "Test Charity" in prompt
    assert "{charity_name}" not in prompt          # all placeholders resolved
    assert '"headline"' in prompt                   # JSON braces rendered as literals
    assert "EXACTLY 3 sources" in prompt


def test_sadaqah_constraint_text(sample_charity_metrics):
    prompt, _ = build_baseline_prompt(sample_charity_metrics, _fake_scores("SADAQAH-ELIGIBLE"), 1, "[1] CN")
    assert "DO NOT mention zakat eligibility" in prompt


def test_prompt_file_in_baseline_fingerprint():
    assert "src/llm/prompts/baseline_narrative.txt" in PHASE_CODE_FILES["baseline"]


class TestDataVintageNote:
    def test_fresh_filing_attributes_year(self):
        from src.llm.prompt_loader import data_vintage_note

        note = data_vintage_note(2024, today_year=2026)
        assert "fiscal year 2024" in note
        assert "RED FLAG" not in note

    def test_stale_filing_requires_disclosure(self):
        from src.llm.prompt_loader import data_vintage_note

        note = data_vintage_note(2022, today_year=2026)
        assert "RED FLAG" in note
        assert "4 years old" in note
        assert "FY2022" in note
        assert "caution" in note

    def test_unknown_year_forbids_attribution(self):
        from src.llm.prompt_loader import data_vintage_note

        note = data_vintage_note(None)
        assert "unknown" in note

    def test_boundary_two_years_is_fresh(self):
        from src.llm.prompt_loader import data_vintage_note

        assert "RED FLAG" not in data_vintage_note(2024, today_year=2026)
        assert "RED FLAG" in data_vintage_note(2023, today_year=2026)

    def test_non_int_fiscal_year_does_not_raise(self):
        """A str fiscal_year (e.g. from a JSON round-trip) must not reach the
        None >= int comparison inside filing_age_years' TypeError path."""
        from src.llm.prompt_loader import data_vintage_note

        note = data_vintage_note("2023")  # str, not int
        assert isinstance(note, str) and note
        assert "unknown" in note
        assert "2023" not in note  # must not cite a year it can't trust

        assert isinstance(data_vintage_note(None), str)
        assert isinstance(data_vintage_note(0), str)
        assert isinstance(data_vintage_note(2024, today_year=2026), str)


class TestCnScoreSanitizationIsIdempotent:
    """baseline.py's CN correction rule matched `\\d+/100` — no decimal, no left
    anchor — while its replacement is the raw unrounded cn_overall_score (an
    average of CN's beacon sub-scores, e.g. 98.66666666666667). The unanchored
    `\\d+` matched only the digits after the decimal point, so re.sub re-inserted
    the full value and left the integer prefix: 98. + 98.66666666666667/100.
    Non-idempotent, and sanitize_narrative_metrics runs twice on the retry path."""

    def _sanitize(self, text, cn_score):
        metrics = SimpleNamespace(
            cn_overall_score=cn_score,
            cn_accountability_score=None,
            cn_financial_score=None,
            fundraising_expenses=1000,
            total_revenue=100000,
            program_expense_ratio=None,
            working_capital_ratio=None,
        )
        return sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]

    def test_the_rounded_value_is_left_alone(self):
        """Idempotency: sanitizing already-correct text must be a no-op."""
        text = "The charity holds an overall score of 98.7/100 from Charity Navigator."
        assert self._sanitize(text, 98.66666666666667) == text

    def test_an_unrounded_value_is_replaced_not_doubled(self):
        """The bug: \\d+/100 matched only '66666666666667', leaving the '98.' prefix."""
        out = self._sanitize(
            "Scored 98.66666666666667/100 from Charity Navigator.", 98.66666666666667
        )
        assert "98.7/100 from Charity Navigator" in out
        assert not re.search(r"\d+\.\d+\.\d+/100", out)

    def test_sanitizing_twice_is_a_no_op(self):
        text = "Rated 87.5/100 from Charity Navigator."
        once = self._sanitize(text, 87.5)
        assert self._sanitize(once, 87.5) == once

    def test_a_wrong_value_is_replaced_not_concatenated(self):
        out = self._sanitize("Rated 42/100 from Charity Navigator.", 87.5)
        assert "87.5/100 from Charity Navigator" in out
        assert "42" not in out


class TestFundraisingClaimIsStrippedWhenDataIsMissing:
    """The model hallucinates $0.00 despite an N/A prompt; the deterministic
    strip is the safety net, and its adjacency requirement made it miss every
    real phrasing. Fixtures below are verbatim from published charities."""

    REAL_HALLUCINATIONS = [
        "Exceptional fundraising efficiency of $0.00 spent per $1 raised [1].",
        "Operates with high fundraising efficiency, spending $0.00 to raise every $1 in FY2025.",
        "The charity has a 91.1% program expense ratio, and a $0.00 fundraising efficiency rate.",
    ]

    def _sanitize_with_null_fundraising(self, text):
        # program_expense_ratio is real (0.911) here, not null: the two tests
        # below assert the "91.1% program expense ratio" clause *survives* as
        # a legitimate neighbor to the stripped fundraising claim. Under a
        # null ratio that clause is itself an unsupported fabrication (task
        # G7) — the fixture disagreed with what these tests' own docstrings
        # already claimed about it.
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=0.911,
                                  working_capital_ratio=None)
        return sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]

    def test_every_real_hallucination_is_stripped(self):
        for text in self.REAL_HALLUCINATIONS:
            out = self._sanitize_with_null_fundraising(text)
            assert "$0.00" not in out, f"not stripped: {text!r}"

    def test_unrelated_sentences_survive(self):
        text = "The charity has a 91.1% program expense ratio. It serves 4,000 families."
        out = self._sanitize_with_null_fundraising(text)
        assert "91.1% program expense ratio" in out
        assert "4,000 families" in out

    def test_decimal_before_the_claim_does_not_truncate_prose(self):
        """G3 defect: `[^.]*` treats the decimal point in "91.1" as a sentence
        boundary, so the strip starts mid-number. Must not end with a bare,
        unclosed number — and the legitimate program-ratio clause (joined to
        the fabricated one by a comma) must survive intact."""
        text = "The charity has a 91.1% program expense ratio, and a $0.00 fundraising efficiency rate."
        out = self._sanitize_with_null_fundraising(text)
        assert "91.1% program expense ratio" in out, f"legit clause was mangled: {out!r}"
        assert "$0.00" not in out
        assert "fundraising efficiency" not in out
        assert not re.search(r"\d+\.\s*$", out), f"truncated mid-number: {out!r}"

    def test_strengths_array_entries_are_stripped_too(self):
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        out = sanitize_narrative_metrics(
            {"strengths": ["Exceptional fundraising efficiency of $0.00 spent per $1 raised [1]."]},
            metrics, None)
        assert "$0.00" not in str(out["strengths"])

    def test_a_correct_real_efficiency_claim_survives_unchanged(self):
        """When fundraising_expenses is known and the claim already matches it,
        the correction-path rule should leave the text as-is (not the removal
        path — that only fires when the metric is null/undetermined)."""
        metrics = SimpleNamespace(fundraising_expenses=30000, total_revenue=600000,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        text = "Spends $0.05 per $1 raised on fundraising."
        out = sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]
        assert out == text

    def test_no_raised_suffix_fundraising_costs_phrasing_is_stripped(self):
        """Rule kept beyond the original two ("fundraising costs/expenses of $X
        per dollar", no "raised" suffix) had no direct test coverage — an
        untested rule is exactly what a future edit deletes by accident."""
        out = self._sanitize_with_null_fundraising(
            "The nonprofit reports fundraising expenses of $0.42 per dollar in overhead."
        )
        assert "$0.42" not in out
        assert "fundraising expenses" not in out


class TestTinyRealFundraisingRatioIsNotRenderedAsZero:
    """G4: 10 charities have real, non-null, non-zero fundraising_expenses whose
    true ratio rounds to $0.00 under :.2f — e.g. $241,666 / $79.6M = $0.003 per
    $1. The data is correct; :.2f made a real cost read as zero."""

    def test_a_tiny_but_real_fundraising_ratio_is_not_rendered_as_zero(self):
        """$241,666 / $79.6M = $0.003 per $1 — real, and not zero."""
        from baseline import _format_fundraising_efficiency

        assert _format_fundraising_efficiency(241666, 79_600_000) == "<$0.01 per $1 raised"
        assert _format_fundraising_efficiency(0, 100_000) == "$0.00 per $1 raised"
        assert _format_fundraising_efficiency(None, 100_000) == "N/A"
        assert _format_fundraising_efficiency(10_000, 100_000) == "$0.10 per $1 raised"
        assert _format_fundraising_efficiency(10_000, 0) == "N/A"
        assert _format_fundraising_efficiency(10_000, None) == "N/A"

    def test_prompt_kwargs_use_the_shared_formatter(self, sample_charity_metrics):
        """The prompt-construction call site (_baseline_prompt_kwargs) must not
        reimplement the raw :.2f formatting that caused the bug."""
        sample_charity_metrics.fundraising_expenses = 241666
        sample_charity_metrics.total_revenue = 79_600_000
        kwargs = _baseline_prompt_kwargs(sample_charity_metrics, _fake_scores(), 3, "[1] Charity Navigator")
        assert kwargs["fundraising_efficiency"] == "<$0.01 per $1 raised"

    def test_tiny_ratio_string_survives_the_sanitizer(self):
        """The new "<$0.01 per $1 raised" text must not get stripped by the
        null-fundraising removal rules in sanitize_narrative_metrics, and must
        not be clobbered back to "$0.00" by the sanitizer's own correction path
        (a second, independent reimplementation of this same ratio)."""
        metrics = SimpleNamespace(fundraising_expenses=241666, total_revenue=79_600_000,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        text = "The charity spends <$0.01 per $1 raised on fundraising."
        out = sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]
        assert "<$0.01 per $1 raised" in out
        assert "$0.00" not in out

    def test_sanitizer_correction_path_also_avoids_stamping_zero(self):
        """If the LLM writes a plausible-but-wrong dollar figure, the
        sanitizer's own correction (not just the prompt kwargs) must replace it
        with the tiny-but-real rendering, not silently round it to $0.00."""
        metrics = SimpleNamespace(fundraising_expenses=241666, total_revenue=79_600_000,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        text = "The charity spends $0.05 per $1 raised on fundraising."
        out = sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]
        assert "$0.00" not in out
        assert "<$0.01 per $1 raised" in out

    def test_sanitizing_the_tiny_ratio_twice_is_a_no_op(self):
        """sanitize_narrative_metrics runs twice on the citation-repair retry
        path (see TestCnScoreSanitizationIsIdempotent). The correction regex
        for pattern 1 isn't anchored past a leading "<", so re-running it on
        already-correct "<$0.01 per $1 raised" text must not duplicate the
        "<" into "<<$0.01"."""
        metrics = SimpleNamespace(fundraising_expenses=241666, total_revenue=79_600_000,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        text = "The charity spends $0.05 per $1 raised on fundraising."
        once = sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]
        twice = sanitize_narrative_metrics({"rationale": once}, metrics, None)["rationale"]
        assert twice == once
        assert "<<" not in twice


def _sanitize(text, metrics, wallet_tag="ZAKAT-ELIGIBLE"):
    scores = SimpleNamespace(wallet_tag=wallet_tag, amal_score=None)
    return sanitize_narrative_metrics({"rationale": text}, metrics, scores)["rationale"]


def _metrics(**overrides):
    """All metrics default to a real, present value; a test nulls out
    whichever one its removal rule is meant to fire on."""
    base = dict(
        working_capital_ratio=5.0,
        program_expense_ratio=0.75,
        cn_overall_score=88.0,
        cn_accountability_score=90,
        cn_financial_score=85,
        fundraising_expenses=10_000,
        total_revenue=100_000,
        founded_year=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _five_passes(text, metrics):
    """Sanitize the same text five times in a row, feeding each pass's
    output into the next. Two passes can't distinguish a fixed point from
    a slow-settling bug (a defect that adds one artifact per pass would
    still differ between pass 1 and pass 2); five passes, asserted
    byte-identical from pass one, is what actually demonstrates one."""
    passes = [text]
    for _ in range(5):
        passes.append(_sanitize(passes[-1], metrics))
    return passes[1:]


class TestClauseScopedRemovalPreservesSupportedClaims:
    """Task G6: a removal rule used to scan to the *sentence* boundary on
    both sides ("everything up to the next period"), so removing one
    fabricated claim deleted any true, supported claim sharing its sentence.
    These are the four cases the controller reproduced by hand — the floor,
    not the ceiling, per the task brief."""

    def _null_program_and_working_capital(self, **overrides):
        return _metrics(program_expense_ratio=None, working_capital_ratio=None, **overrides)

    def test_null_ratio_then_tiny_real_fundraising_survives(self):
        text = "The charity has a program expense ratio of 91.1%, and spends <$0.01 per $1 raised on overhead."
        metrics = self._null_program_and_working_capital(fundraising_expenses=241666, total_revenue=79_600_000)
        out = _sanitize(text, metrics)
        assert out == "Spends <$0.01 per $1 raised on overhead."

    def test_null_ratio_then_real_fundraising_survives(self):
        text = "The charity has a program expense ratio of 91.1%, and spends $0.10 per $1 raised on overhead."
        metrics = self._null_program_and_working_capital(fundraising_expenses=10_000, total_revenue=100_000)
        out = _sanitize(text, metrics)
        assert out == "Spends $0.10 per $1 raised on overhead."

    def test_real_fundraising_then_null_ratio_survives(self):
        text = "The charity spends $0.10 per $1 raised, and has a program expense ratio of 91.1%."
        metrics = self._null_program_and_working_capital(fundraising_expenses=10_000, total_revenue=100_000)
        out = _sanitize(text, metrics)
        assert out == "The charity spends $0.10 per $1 raised."

    def test_null_working_capital_then_real_fundraising_survives(self):
        text = "It holds 4.2 months of working capital, and spends $0.10 per $1 raised."
        metrics = self._null_program_and_working_capital(fundraising_expenses=10_000, total_revenue=100_000)
        out = _sanitize(text, metrics)
        assert out == "Spends $0.10 per $1 raised."

    def test_all_four_are_idempotent(self):
        cases = [
            ("The charity has a program expense ratio of 91.1%, and spends <$0.01 per $1 raised on overhead.",
             self._null_program_and_working_capital(fundraising_expenses=241666, total_revenue=79_600_000)),
            ("The charity has a program expense ratio of 91.1%, and spends $0.10 per $1 raised on overhead.",
             self._null_program_and_working_capital(fundraising_expenses=10_000, total_revenue=100_000)),
            ("The charity spends $0.10 per $1 raised, and has a program expense ratio of 91.1%.",
             self._null_program_and_working_capital(fundraising_expenses=10_000, total_revenue=100_000)),
            ("It holds 4.2 months of working capital, and spends $0.10 per $1 raised.",
             self._null_program_and_working_capital(fundraising_expenses=10_000, total_revenue=100_000)),
        ]
        for text, metrics in cases:
            once = _sanitize(text, metrics)
            twice = _sanitize(once, metrics)
            assert twice == once, f"not idempotent: {once!r} -> {twice!r}"


class TestClauseScopedRemovalStillRemovesFabricatedTails:
    """The other half of the tension the brief calls out: clause-scoping
    must not let a fabricated claim's own dangling tail survive just because
    it sits after a comma. "a perfect score from Charity Navigator, its
    highest rating" is one fabricated claim, not two — the appositive after
    the comma is not an independent, potentially-true clause, so it must go
    with the rest of it."""

    def test_fabricated_score_and_its_appositive_are_both_removed(self):
        text = "The charity earned a perfect score from Charity Navigator, its highest rating."
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == ""

    def test_true_clause_then_fabricated_score_with_appositive_survives(self):
        """A true claim in front of the fabricated one must survive in
        full, and the fabricated claim's appositive tail must not leak
        through as a dangling fragment."""
        text = (
            "The charity spends $0.10 per $1 raised, and earned a perfect score "
            "from Charity Navigator, its highest rating."
        )
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == "The charity spends $0.10 per $1 raised."
        assert "highest rating" not in out

    def test_appositive_case_is_idempotent(self):
        text = "The charity earned a perfect score from Charity Navigator, its highest rating."
        metrics = _metrics(cn_overall_score=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == ""


# Matrix: each removal-rule family x {unsupported alone, unsupported first +
# supported second, supported first + unsupported second, both unsupported}.
# The "supported" companion claim is fundraising for every family except
# fundraising itself, which pairs with working capital instead. Exact
# strings, not substring checks — a `not in` assertion would pass against an
# empty string and hide exactly the bug this task fixes.
_FAMILY_MATRIX = [
    # (family, text, metrics_overrides, expected_output)
    (
        "working_capital", "It holds 4.2 months of working capital.",
        dict(working_capital_ratio=None), "",
    ),
    (
        "working_capital",
        "It holds 4.2 months of working capital, and spends $0.10 per $1 raised.",
        dict(working_capital_ratio=None), "Spends $0.10 per $1 raised.",
    ),
    (
        "working_capital",
        "The charity spends $0.10 per $1 raised, and holds 4.2 months of working capital.",
        dict(working_capital_ratio=None), "The charity spends $0.10 per $1 raised.",
    ),
    (
        "working_capital",
        "It holds 4.2 months of working capital, and spends $0.00 per $1 raised.",
        dict(working_capital_ratio=None, fundraising_expenses=None), "",
    ),
    (
        "program_ratio", "The charity has a program expense ratio of 91.1%.",
        dict(program_expense_ratio=None), "",
    ),
    (
        "program_ratio",
        "The charity has a program expense ratio of 91.1%, and spends $0.10 per $1 raised.",
        dict(program_expense_ratio=None), "Spends $0.10 per $1 raised.",
    ),
    (
        "program_ratio",
        "The charity spends $0.10 per $1 raised, and has a program expense ratio of 91.1%.",
        dict(program_expense_ratio=None), "The charity spends $0.10 per $1 raised.",
    ),
    (
        "program_ratio",
        "The charity has a program expense ratio of 91.1%, and spends $0.00 per $1 raised.",
        dict(program_expense_ratio=None, fundraising_expenses=None), "",
    ),
    (
        "charity_navigator", "The charity scored 87/100 from Charity Navigator.",
        dict(cn_overall_score=None), "",
    ),
    (
        "charity_navigator",
        "The charity scored 87/100 from Charity Navigator, and spends $0.10 per $1 raised.",
        dict(cn_overall_score=None), "Spends $0.10 per $1 raised.",
    ),
    (
        "charity_navigator",
        "The charity spends $0.10 per $1 raised, and scored 87/100 from Charity Navigator.",
        dict(cn_overall_score=None), "The charity spends $0.10 per $1 raised.",
    ),
    (
        "charity_navigator",
        "The charity scored 87/100 from Charity Navigator, and spends $0.00 per $1 raised.",
        dict(cn_overall_score=None, fundraising_expenses=None), "",
    ),
    (
        "accountability_score", "The charity has an accountability score of 87.",
        dict(cn_accountability_score=None), "",
    ),
    (
        "accountability_score",
        "The charity has an accountability score of 87, and spends $0.10 per $1 raised.",
        dict(cn_accountability_score=None), "Spends $0.10 per $1 raised.",
    ),
    (
        "accountability_score",
        "The charity spends $0.10 per $1 raised, and has an accountability score of 87.",
        dict(cn_accountability_score=None), "The charity spends $0.10 per $1 raised.",
    ),
    (
        "accountability_score",
        "The charity has an accountability score of 87, and spends $0.00 per $1 raised.",
        dict(cn_accountability_score=None, fundraising_expenses=None), "",
    ),
    (
        "fundraising", "The charity spends $0.00 per $1 raised.",
        dict(fundraising_expenses=None), "",
    ),
    (
        "fundraising",
        "The charity spends $0.00 per $1 raised, and holds 5.0 months of working capital.",
        dict(fundraising_expenses=None), "Holds 5.0 months of working capital.",
    ),
    (
        "fundraising",
        "The charity holds 5.0 months of working capital, and spends $0.00 per $1 raised.",
        dict(fundraising_expenses=None), "The charity holds 5.0 months of working capital.",
    ),
    (
        "fundraising",
        "The charity spends $0.00 per $1 raised, and holds 4.2 months of working capital.",
        dict(fundraising_expenses=None, working_capital_ratio=None), "",
    ),
    (
        "zakat", "The charity is zakat-eligible.",
        dict(), "",
    ),
    (
        "zakat",
        "The charity is zakat-eligible, and spends $0.10 per $1 raised.",
        dict(), "Spends $0.10 per $1 raised.",
    ),
    (
        "zakat",
        "The charity spends $0.10 per $1 raised, and is zakat-eligible.",
        dict(), "The charity spends $0.10 per $1 raised.",
    ),
    (
        "zakat",
        "The charity is zakat-eligible, and spends $0.00 per $1 raised.",
        dict(fundraising_expenses=None), "",
    ),
]


class TestRemovalRuleFamilyClauseMatrix:
    """Requirement 5: every removal-rule family x every clause-sharing
    arrangement. "zakat" always runs with wallet_tag=SADAQAH-ELIGIBLE (the
    only wallet tag that triggers its removal rule); every other family runs
    with the default ZAKAT-ELIGIBLE so the zakat rule never fires and
    contaminates a result meant to isolate one family at a time."""

    @pytest.mark.parametrize(
        "family,text,overrides,expected",
        _FAMILY_MATRIX,
        ids=[f"{family}-{i}" for i, (family, *_rest) in enumerate(_FAMILY_MATRIX)],
    )
    def test_matrix_case(self, family, text, overrides, expected):
        metrics = _metrics(**overrides)
        wallet_tag = "SADAQAH-ELIGIBLE" if family == "zakat" else "ZAKAT-ELIGIBLE"
        out = _sanitize(text, metrics, wallet_tag=wallet_tag)
        assert out == expected

    @pytest.mark.parametrize(
        "family,text,overrides,expected",
        _FAMILY_MATRIX,
        ids=[f"{family}-{i}" for i, (family, *_rest) in enumerate(_FAMILY_MATRIX)],
    )
    def test_matrix_case_is_idempotent(self, family, text, overrides, expected):
        metrics = _metrics(**overrides)
        wallet_tag = "SADAQAH-ELIGIBLE" if family == "zakat" else "ZAKAT-ELIGIBLE"
        once = _sanitize(text, metrics, wallet_tag=wallet_tag)
        twice = _sanitize(once, metrics, wallet_tag=wallet_tag)
        assert twice == once


class TestCorrectionRulesPreserveSentenceInitialCase:
    """G6 review Critical 1: `_match_case` (added in aa83a32) was applied to
    only one correction rule (working capital's "holds X of working capital"
    pattern), but every correction rule whose replacement is a fixed-case
    literal beginning with a word is exposed to the same hazard: a removal
    rule elsewhere in this function can leave that match sentence-initial
    and capitalized, and a hardcoded lowercase replacement silently
    re-lowercases it. Six more rules had this gap (all now wrapped in
    `_preserve_case`): program-ratio patterns 2 and 3, the CN "scored X out
    of 100 on Charity Navigator" pattern, the fundraising "fundraising costs
    of $X per dollar" pattern, and both founded-year patterns. These tests
    exercise each directly — no removal needed, just feeding the match at
    the very start of a sentence — which is the simplest possible
    reproduction of the hazard `_match_case` guards against.

    A later addition, the program-ratio "spends X% on programs" correction
    rule (pattern 5), was wrapped in `_preserve_case` from the start for the
    same reason and is exercised here too."""

    def test_working_capital_holds_pattern(self):
        text = "Holds 3.0 months of working capital. It serves many families."
        metrics = _metrics()
        out = _sanitize(text, metrics)
        assert out == "Holds 5.0 months of working capital. It serves many families."

    def test_program_ratio_pattern2(self):
        text = "Program ratio of 50% was reported. It serves many families."
        metrics = _metrics()
        out = _sanitize(text, metrics)
        assert out == "Program expense ratio of 75.0% was reported. It serves many families."

    def test_program_ratio_pattern3_directs(self):
        text = "Directs 50% to programs. It serves many families."
        metrics = _metrics()
        out = _sanitize(text, metrics)
        assert out == "Directs 75.0% to programs. It serves many families."

    def test_cn_scored_pattern(self):
        text = "Scored 80 out of 100 on Charity Navigator. It serves many families."
        metrics = _metrics()
        out = _sanitize(text, metrics)
        assert out == "Scored 88.0/100 on Charity Navigator. It serves many families."

    def test_fundraising_costs_pattern(self):
        text = "Fundraising costs of $0.05 per dollar were reported. It serves many families."
        metrics = _metrics()
        out = _sanitize(text, metrics)
        assert out == "Fundraising costs of $0.10 per dollar were reported. It serves many families."

    def test_founded_in_pattern(self):
        text = "Founded in 1980. It serves many families."
        metrics = _metrics(founded_year=1985)
        out = _sanitize(text, metrics)
        assert out == "Founded in 1985. It serves many families."

    def test_operating_since_pattern(self):
        text = "Operating since 1980. It serves many families."
        metrics = _metrics(founded_year=1985)
        out = _sanitize(text, metrics)
        assert out == "Operating since 1985. It serves many families."

    def test_spends_on_programs_pattern(self):
        """Follow-up fix: the new "spends X% on programs" correction rule
        (pattern 5) needed the same _preserve_case wrapping as its siblings
        — a preceding clause's removal can leave it sentence-initial."""
        text = "Spends 45.0% on programs. It serves many families."
        metrics = _metrics()
        out = _sanitize(text, metrics)
        assert out == "Spends 75.0% on programs. It serves many families."

    @pytest.mark.parametrize(
        "text,overrides",
        [
            ("Holds 3.0 months of working capital.", dict()),
            ("Program ratio of 50% was reported.", dict()),
            ("Directs 50% to programs.", dict()),
            ("Scored 80 out of 100 on Charity Navigator.", dict()),
            ("Fundraising costs of $0.05 per dollar were reported.", dict()),
            ("Founded in 1980.", dict(founded_year=1985)),
            ("Operating since 1980.", dict(founded_year=1985)),
            ("Spends 45.0% on programs.", dict()),
        ],
    )
    def test_sentence_initial_correction_is_idempotent(self, text, overrides):
        metrics = _metrics(**overrides)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once


class TestCnConnectorSurvivesASecondPass:
    """G6 review Critical 1 (the idempotency-breaking half): the CN "X/100
    ... Charity Navigator" correction rule used to hardcode "from Charity
    Navigator" in its replacement regardless of which connector ("on", "by",
    "from") the match actually used. That's fine on the first pass — the
    "scored X out of 100 on Charity Navigator" rule produces "on", and this
    rule never got a chance to fire on the original "80 out of 100" text.
    But sanitize_narrative_metrics runs twice on the citation-repair retry
    path, and on the second pass the already-correct "X/100 ... Charity
    Navigator" text now matches this rule for the first time — which used
    to silently swap "on" to "from". Fixed by capturing and echoing back
    whatever connector was actually present."""

    def test_on_connector_survives_a_second_pass(self):
        metrics = _metrics(working_capital_ratio=None, cn_overall_score=88.0)
        text = "It holds 4.2 months of working capital, and scored 80 out of 100 on Charity Navigator."
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert once == "Scored 88.0/100 on Charity Navigator."
        assert twice == once

    def test_by_connector_is_not_forced_to_from(self):
        metrics = _metrics(cn_overall_score=88.0)
        text = "Rated 87/100 by Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "Rated 88.0/100 by Charity Navigator."

    def test_bare_no_connector_still_defaults_to_from(self):
        """When the original prose has no connector at all, "from" remains
        the sensible default — nothing regresses for the common case."""
        metrics = _metrics(cn_overall_score=88.0)
        text = "Rated 87/100 Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "Rated 88.0/100 from Charity Navigator."


# Critical 1 matrix: each (removal family, correction family) pair where the
# removal rule runs *earlier* in sanitize_narrative_metrics's internal rules
# list than the correction rule — the only pairs where a removal's repair
# pass can expose a match to a later correction rule sentence-initially and
# capitalized, which is exactly the composition the review found broken.
# Pairs where the correction rule runs earlier than the removal rule aren't
# reachable via this mechanism (the correction already ran against the
# original, unmodified text by the time the removal fires), so they're
# excluded — not because they're untested, but because they're a different,
# unrelated question already covered by
# TestCorrectionRulesPreserveSentenceInitialCase above.
_CROSS_FAMILY_IDEMPOTENCY = [
    ("working_capital", "program_ratio",
     "Holds 4.2 months of working capital, and directs 50% to programs.",
     dict(working_capital_ratio=None), "Directs 75.0% to programs."),
    ("working_capital", "cn_score",
     "Holds 4.2 months of working capital, and scored 80 out of 100 on Charity Navigator.",
     dict(working_capital_ratio=None), "Scored 88.0/100 on Charity Navigator."),
    ("working_capital", "fundraising",
     "Holds 4.2 months of working capital, and spends $0.05 per $1 raised.",
     dict(working_capital_ratio=None), "Spends $0.10 per $1 raised."),
    ("working_capital", "founded_year",
     "Holds 4.2 months of working capital, and founded in 1980.",
     dict(working_capital_ratio=None), "Founded in 1985."),
    ("program_ratio", "cn_score",
     "Has a program expense ratio of 91.1%, and scored 80 out of 100 on Charity Navigator.",
     dict(program_expense_ratio=None), "Scored 88.0/100 on Charity Navigator."),
    ("program_ratio", "fundraising",
     "Has a program expense ratio of 91.1%, and spends $0.05 per $1 raised.",
     dict(program_expense_ratio=None), "Spends $0.10 per $1 raised."),
    ("program_ratio", "founded_year",
     "Has a program expense ratio of 91.1%, and founded in 1980.",
     dict(program_expense_ratio=None), "Founded in 1985."),
    ("cn_score", "fundraising",
     "Scored 87/100 from Charity Navigator, and spends $0.05 per $1 raised.",
     dict(cn_overall_score=None), "Spends $0.10 per $1 raised."),
    ("cn_score", "founded_year",
     "Scored 87/100 from Charity Navigator, and founded in 1980.",
     dict(cn_overall_score=None), "Founded in 1985."),
    ("cn_accountability", "fundraising",
     "Has an accountability score of 87, and spends $0.05 per $1 raised.",
     dict(cn_accountability_score=None), "Spends $0.10 per $1 raised."),
    ("cn_accountability", "founded_year",
     "Has an accountability score of 87, and founded in 1980.",
     dict(cn_accountability_score=None), "Founded in 1985."),
    ("cn_financial", "fundraising",
     "Has a financial score of 82, and spends $0.05 per $1 raised.",
     dict(cn_financial_score=None), "Spends $0.10 per $1 raised."),
    ("cn_financial", "founded_year",
     "Has a financial score of 82, and founded in 1980.",
     dict(cn_financial_score=None), "Founded in 1985."),
    ("fundraising", "founded_year",
     "Spends $0.00 per $1 raised, and founded in 1980.",
     dict(fundraising_expenses=None), "Founded in 1985."),
    ("zakat", "founded_year",
     "Is zakat-eligible, and founded in 1980.",
     dict(), "Founded in 1985."),
]


class TestCrossFamilyRemovalCorrectionIdempotency:
    """Requirement: 'for each removal family crossed with each correction
    family, run two passes and assert byte-identical output.' Every case
    here has a null metric whose removal rule fires first and exposes a
    *different*, present metric's correction rule to sentence-initial,
    capitalized text — the exact composition Critical 1 was found in."""

    @pytest.mark.parametrize(
        "removal_family,correction_family,text,overrides,expected",
        _CROSS_FAMILY_IDEMPOTENCY,
        ids=[f"{r}-x-{c}" for r, c, *_rest in _CROSS_FAMILY_IDEMPOTENCY],
    )
    def test_pair_produces_expected_output(self, removal_family, correction_family, text, overrides, expected):
        metrics = _metrics(founded_year=1985, **overrides)
        wallet_tag = "SADAQAH-ELIGIBLE" if removal_family == "zakat" else "ZAKAT-ELIGIBLE"
        out = _sanitize(text, metrics, wallet_tag=wallet_tag)
        assert out == expected

    @pytest.mark.parametrize(
        "removal_family,correction_family,text,overrides,expected",
        _CROSS_FAMILY_IDEMPOTENCY,
        ids=[f"{r}-x-{c}" for r, c, *_rest in _CROSS_FAMILY_IDEMPOTENCY],
    )
    def test_pair_is_idempotent(self, removal_family, correction_family, text, overrides, expected):
        metrics = _metrics(founded_year=1985, **overrides)
        wallet_tag = "SADAQAH-ELIGIBLE" if removal_family == "zakat" else "ZAKAT-ELIGIBLE"
        once = _sanitize(text, metrics, wallet_tag=wallet_tag)
        twice = _sanitize(once, metrics, wallet_tag=wallet_tag)
        assert twice == once


# Critical 2 matrix: the same false-clause-first arrangement as
# _FAMILY_MATRIX, but joined by a *bare* comma instead of ", and" — the
# review found this wiped the true clause to '' for every family because
# `_clause_trail` treated any bare comma as staying inside the same
# fabricated claim. The true companion clause is always verb-led (elided
# subject, matching the corpus style used throughout this file), which is
# exactly the signal `_clause_trail` now uses to tell an independent clause
# from a fabricated claim's own appositive tail.
_BARE_COMMA_FALSE_FIRST = [
    ("working_capital",
     "It holds 4.2 months of working capital, spends $0.10 per $1 raised on overhead.",
     dict(working_capital_ratio=None), "Spends $0.10 per $1 raised on overhead."),
    ("program_ratio",
     "The charity has a program expense ratio of 91.1%, spends $0.10 per $1 raised on overhead.",
     dict(program_expense_ratio=None), "Spends $0.10 per $1 raised on overhead."),
    ("cn_score",
     "It scored 87/100 from Charity Navigator, holds 4.2 months of working capital.",
     dict(cn_overall_score=None), "Holds 5.0 months of working capital."),
    ("cn_accountability",
     "The charity has an accountability score of 87, spends $0.10 per $1 raised.",
     dict(cn_accountability_score=None), "Spends $0.10 per $1 raised."),
    ("cn_financial",
     "The charity has a financial score of 82, spends $0.10 per $1 raised.",
     dict(cn_financial_score=None), "Spends $0.10 per $1 raised."),
    ("fundraising",
     "The charity spends $0.00 per $1 raised, holds 4.2 months of working capital.",
     dict(fundraising_expenses=None), "Holds 5.0 months of working capital."),
    ("zakat",
     "The charity is zakat-eligible, spends $0.10 per $1 raised.",
     dict(), "Spends $0.10 per $1 raised."),
]


class TestClauseTrailBareCommaBoundary:
    """G6 review Critical 2: with the false (unsupported) clause first and a
    *bare* comma joining it to a true clause, the whole sentence wiped to
    ''. Resolved by having `_clause_trail` stop at a bare comma when what
    follows it leads with a finite verb (an independent clause) and keep
    consuming when it doesn't (a noun-phrase appositive, still part of the
    same fabricated claim)."""

    @pytest.mark.parametrize(
        "family,text,overrides,expected",
        _BARE_COMMA_FALSE_FIRST,
        ids=[f"{family}" for family, *_rest in _BARE_COMMA_FALSE_FIRST],
    )
    def test_true_clause_survives_bare_comma_false_first(self, family, text, overrides, expected):
        metrics = _metrics(**overrides)
        wallet_tag = "SADAQAH-ELIGIBLE" if family == "zakat" else "ZAKAT-ELIGIBLE"
        out = _sanitize(text, metrics, wallet_tag=wallet_tag)
        assert out == expected

    @pytest.mark.parametrize(
        "family,text,overrides,expected",
        _BARE_COMMA_FALSE_FIRST,
        ids=[f"{family}" for family, *_rest in _BARE_COMMA_FALSE_FIRST],
    )
    def test_bare_comma_false_first_is_idempotent(self, family, text, overrides, expected):
        metrics = _metrics(**overrides)
        wallet_tag = "SADAQAH-ELIGIBLE" if family == "zakat" else "ZAKAT-ELIGIBLE"
        once = _sanitize(text, metrics, wallet_tag=wallet_tag)
        twice = _sanitize(once, metrics, wallet_tag=wallet_tag)
        assert twice == once

    def test_true_clause_first_bare_comma_still_works(self):
        """Regression: this ordering already worked before Critical 2's fix
        (via `_clause_lead`'s existing bare-comma handling on the leading
        edge) and must keep working."""
        metrics = _metrics(working_capital_ratio=None)
        text = "The charity spends $0.10 per $1 raised, holds 4.2 months of working capital."
        out = _sanitize(text, metrics)
        assert out == "The charity spends $0.10 per $1 raised."

    def test_appositive_tail_still_fully_removed_with_bare_comma(self):
        """The other half of the tension: a fabricated claim's own
        appositive tail (a noun phrase, not an independent clause) must
        still be swallowed whole, not preserved as a dangling fragment."""
        metrics = _metrics(cn_overall_score=None)
        text = "The charity earned a perfect score from Charity Navigator, its highest rating."
        out = _sanitize(text, metrics)
        assert out == ""

    def test_second_appositive_phrasing_still_fully_removed(self):
        """A determiner+adjective+noun appositive ("a strong reserve
        position"), not just a possessive-pronoun one — the brief's own
        example of the noun-phrase side of the boundary."""
        metrics = _metrics(working_capital_ratio=None)
        text = "The charity holds 4.2 months of working capital, a strong reserve position."
        out = _sanitize(text, metrics)
        assert out == ""


# Re-review of `_clause_trail`: the finite-verb-lead heuristic ("spends",
# "holds", "scored", "is", ...) enumerated the open class — any verb not on
# the list reproduced the original bug. These are the exact verbs the
# reviewer found missing, each paired with a true clause that must survive
# a bare-comma join to the false clause in front of it.
_OPEN_VERB_CLASS_GAP = [
    ("reports",
     "It holds 4.2 months of working capital, reports $2M in revenue this year.",
     "Reports $2M in revenue this year."),
    ("serves",
     "It holds 4.2 months of working capital, serves over 10,000 families each year.",
     "Serves over 10,000 families each year."),
    ("operates",
     "It holds 4.2 months of working capital, operates 12 clinics nationwide.",
     "Operates 12 clinics nationwide."),
    ("distributed",
     "It holds 4.2 months of working capital, distributed 3M meals last year.",
     "Distributed 3M meals last year."),
]

# The comparative-tail trap the brief warned about: a genuine comparison of
# the SAME fabricated number carries its own digits too ("82"), so a naive
# "does the tail have a number" boundary test would wrongly treat it as an
# independent clause and leave a fabricated fragment ("Up from 82 last
# year.") behind instead of removing the whole claim.
_COMPARATIVE_TAIL_TRAP = [
    ("up_from", "The charity scored 87/100 from Charity Navigator, up from 82 last year."),
    ("compared_to", "The charity scored 87/100 from Charity Navigator, compared to last year."),
]

# Appositive phrasings beyond the possessive-pronoun one already covered —
# these open with a determiner or quantifier, the closed class
# `_trail_same_claim_lead` is built on, not a verb.
_CLOSED_CLASS_APPOSITIVES = [
    ("the_best_in_its_class",
     "The charity holds 4.2 months of working capital, the best in its class."),
    ("one_of_the_highest",
     "The charity scored 87/100 from Charity Navigator, one of the highest in its cohort."),
]

# Follow-up gap (found after 048c6b4 shipped): an appositive tail with no
# determiner at all ("best in its class", "higher than most peers") wasn't on
# `_trail_same_claim_lead`, so it defaulted to a clause boundary and stranded
# a comparison whose basis (the just-deleted fabricated number) no longer
# exists. Bare comparative/superlative leads close that gap.
_BARE_COMPARATIVE_APPOSITIVES = [
    ("best", "It scored 87/100 from Charity Navigator, best in its class."),
    ("worst", "It scored 87/100 from Charity Navigator, worst in its cohort."),
    ("higher", "It scored 87/100 from Charity Navigator, higher than most peers."),
    ("lower", "It scored 87/100 from Charity Navigator, lower than its closest competitor."),
    ("better", "It scored 87/100 from Charity Navigator, better than its regional peers."),
    ("stronger", "It scored 87/100 from Charity Navigator, stronger than most peers its size."),
    ("weaker", "It scored 87/100 from Charity Navigator, weaker than average for its sector."),
    ("highest", "It scored 87/100 from Charity Navigator, highest among comparable nonprofits."),
    ("lowest", "It scored 87/100 from Charity Navigator, lowest among comparable nonprofits."),
    ("strongest", "It scored 87/100 from Charity Navigator, strongest in its peer group."),
    ("among", "It scored 87/100 from Charity Navigator, among the best in its sector."),
    ("second_only_to", "It scored 87/100 from Charity Navigator, second only to one other nonprofit."),
]

# `lower` and `better` can each lead either a bare-comparative appositive
# (above) or a genuine independent clause with a verb of the same spelling
# ("lower their overhead", "better their outcomes"). Widening the
# continuation list to catch the appositive reading also catches this verb
# reading, over-consuming it. Per the standing tie-break (a surviving
# fabrication-adjacent fragment is worse than an over-removed true clause)
# this is accepted, not fixed — documented here rather than silently left
# untested.
_AMBIGUOUS_CONTINUATION_LEAD_COLLISION = [
    ("lower_as_verb",
     "It holds 4.2 months of working capital, lower their overhead each year."),
    ("better_as_verb",
     "It holds 4.2 months of working capital, better their outcomes every quarter."),
]


class TestClauseTrailReplacesVerbListWithClosedContinuationLead:
    """Re-review finding: `_clause_trail`'s bare-comma boundary must not be
    decided by an open verb class. Resolved by inverting which side is
    enumerated — a closed set of continuation markers (determiner/
    possessive/quantifier appositive leads, plus comparative-tail
    prepositions) decides when the comma is swallowed; everything else,
    including any verb, is a boundary and stops there."""

    @pytest.mark.parametrize("name,text,expected", _OPEN_VERB_CLASS_GAP, ids=[n for n, *_ in _OPEN_VERB_CLASS_GAP])
    def test_true_clause_survives_previously_unlisted_verb(self, name, text, expected):
        metrics = _metrics(working_capital_ratio=None)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize("name,text,expected", _OPEN_VERB_CLASS_GAP, ids=[n for n, *_ in _OPEN_VERB_CLASS_GAP])
    def test_previously_unlisted_verb_case_is_idempotent(self, name, text, expected):
        metrics = _metrics(working_capital_ratio=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once

    def test_founded_verb_missing_from_old_list_no_longer_wipes_the_correction(self):
        """The sharpest instance from the review: 'founded' was on neither
        the old verb list nor any list at all, so the ratio-removal rule
        swallowed 'founded in 1980' along with the false ratio clause
        before the founded-year correction rule ever got to run on it."""
        metrics = _metrics(program_expense_ratio=None, founded_year=1985)
        text = "The charity has a program expense ratio of 91.1%, founded in 1980."
        out = _sanitize(text, metrics)
        assert out == "Founded in 1985."

    def test_founded_verb_case_is_idempotent(self):
        metrics = _metrics(program_expense_ratio=None, founded_year=1985)
        text = "The charity has a program expense ratio of 91.1%, founded in 1980."
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once

    @pytest.mark.parametrize("name,text", _COMPARATIVE_TAIL_TRAP, ids=[n for n, _ in _COMPARATIVE_TAIL_TRAP])
    def test_comparative_tail_of_the_same_false_claim_is_not_left_as_a_fragment(self, name, text):
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == ""

    @pytest.mark.parametrize("name,text", _COMPARATIVE_TAIL_TRAP, ids=[n for n, _ in _COMPARATIVE_TAIL_TRAP])
    def test_comparative_tail_trap_case_is_idempotent(self, name, text):
        metrics = _metrics(cn_overall_score=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once

    @pytest.mark.parametrize("name,text", _CLOSED_CLASS_APPOSITIVES, ids=[n for n, _ in _CLOSED_CLASS_APPOSITIVES])
    def test_closed_class_appositive_still_fully_removed(self, name, text):
        metrics = _metrics(working_capital_ratio=None, cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == ""

    @pytest.mark.parametrize("name,text", _CLOSED_CLASS_APPOSITIVES, ids=[n for n, _ in _CLOSED_CLASS_APPOSITIVES])
    def test_closed_class_appositive_case_is_idempotent(self, name, text):
        metrics = _metrics(working_capital_ratio=None, cn_overall_score=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once


class TestClauseTrailBareComparativeAppositiveLead:
    """Closes the determiner-less appositive gap left by 048c6b4: an
    appositive tail with no leading determiner/possessive/quantifier
    ("best in its class", "higher than most peers") defaulted to a clause
    boundary and stranded a comparison whose basis was just deleted as
    unsupported. `_trail_same_claim_lead` gains a closed set of bare
    comparative/superlative continuation leads to catch these too."""

    @pytest.mark.parametrize(
        "name,text", _BARE_COMPARATIVE_APPOSITIVES, ids=[n for n, _ in _BARE_COMPARATIVE_APPOSITIVES]
    )
    def test_bare_comparative_appositive_fully_removed(self, name, text):
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == ""

    @pytest.mark.parametrize(
        "name,text", _BARE_COMPARATIVE_APPOSITIVES, ids=[n for n, _ in _BARE_COMPARATIVE_APPOSITIVES]
    )
    def test_bare_comparative_appositive_is_idempotent(self, name, text):
        metrics = _metrics(cn_overall_score=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once

    def test_open_verb_class_floor_cases_still_survive(self):
        """048c6b4's four open-class-verb regressions (the reason the
        continuation list was inverted at all) must not be reopened by
        widening it further here."""
        metrics = _metrics(working_capital_ratio=None)
        cases = [
            ("It holds 4.2 months of working capital, disbursed $4M in grants.",
             "Disbursed $4M in grants."),
            ("It holds 4.2 months of working capital, trains 200 midwives annually.",
             "Trains 200 midwives annually."),
            ("It holds 4.2 months of working capital, vaccinated 1.2M children.",
             "Vaccinated 1.2M children."),
            ("It holds 4.2 months of working capital, employs 45 staff.",
             "Employs 45 staff."),
        ]
        for text, expected in cases:
            assert _sanitize(text, metrics) == expected

    @pytest.mark.parametrize(
        "name,text",
        _AMBIGUOUS_CONTINUATION_LEAD_COLLISION,
        ids=[n for n, _ in _AMBIGUOUS_CONTINUATION_LEAD_COLLISION],
    )
    def test_verb_collision_words_resolve_by_consuming(self, name, text):
        """`lower`/`better` can lead either a bare-comparative appositive or
        a genuine verb clause of the same spelling. The ambiguity resolves
        toward consuming (over-removal), per the standing tie-break — an
        accepted trade-off, not a bug."""
        metrics = _metrics(working_capital_ratio=None)
        out = _sanitize(text, metrics)
        assert out == ""

    @pytest.mark.parametrize(
        "name,text",
        _AMBIGUOUS_CONTINUATION_LEAD_COLLISION,
        ids=[n for n, _ in _AMBIGUOUS_CONTINUATION_LEAD_COLLISION],
    )
    def test_verb_collision_case_is_idempotent(self, name, text):
        metrics = _metrics(working_capital_ratio=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once


_NUMBER_BEFORE_PROGRAM_RATIO_FABRICATIONS = [
    ("has_a_number_before", "The charity has a 91.1% program expense ratio.", ""),
    ("with_a_leading_number_before",
     "With a 91.1% program expense ratio, it is efficient.", "It is efficient."),
    ("spends_on_programs", "The charity spends 91.1% on programs.", ""),
    ("citation_marker", "The charity has a 91.1% program expense ratio [2].", ""),
]


class TestNumberBeforeProgramRatioRemoval:
    """Task G7: the null-program-ratio removal rules only matched
    number-after phrasing ("ratio of 91.1%") and the directs/allocates-to-
    programs shape, so a fabricated ratio with the number BEFORE the metric
    name ("has a 91.1% program expense ratio", "spends 91.1% on programs")
    survived unchanged — a donor-facing fabrication. The correction rule for
    the same metric already recognizes number-before phrasing when stamping
    a correct value over a wrong one; only removal was missing it. Reuses
    _clause_lead/_clause_trail, no new scoping idiom."""

    @pytest.mark.parametrize(
        "name,text,expected", _NUMBER_BEFORE_PROGRAM_RATIO_FABRICATIONS,
        ids=[n for n, *_ in _NUMBER_BEFORE_PROGRAM_RATIO_FABRICATIONS])
    def test_number_before_fabrication_is_removed(self, name, text, expected):
        metrics = _metrics(program_expense_ratio=None)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,expected", _NUMBER_BEFORE_PROGRAM_RATIO_FABRICATIONS,
        ids=[n for n, *_ in _NUMBER_BEFORE_PROGRAM_RATIO_FABRICATIONS])
    def test_number_before_fabrication_is_idempotent(self, name, text, expected):
        metrics = _metrics(program_expense_ratio=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once

    def test_number_before_real_ratio_is_corrected_not_deleted(self):
        """When program_expense_ratio IS real, the removal rules must not
        fire — the existing number-before correction rule already stamps
        the right value over a wrong one; this must keep working, not get
        swallowed by the new removal rule."""
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity has a 45.0% program expense ratio."
        out = _sanitize(text, metrics)
        assert out == "The charity has a 91.1% program expense ratio."

    def test_spends_on_programs_with_real_ratio_is_corrected_not_left_wrong(self):
        """Follow-up fix: 'spends X% on programs' now has a correction-side
        rule of its own — a wrong number publishing verbatim next to it was
        the exact defect this closes, not a phrasing to leave alone. (This
        test previously asserted the opposite, `out == text`, with a
        docstring calling the gap "pre-existing, separately-scoped" — i.e.
        documenting the bug, not protecting a feature. The removal-side gate
        this test used to half-protect is still covered independently by
        `test_number_before_fabrication_is_removed[spends_on_programs]`
        above, which asserts this same phrasing is fully removed when
        `program_expense_ratio` is null.)"""
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity spends 45.0% on programs."
        out = _sanitize(text, metrics)
        assert out == "The charity spends 91.1% on programs."

    def test_spends_on_programs_already_correct_survives_unchanged(self):
        """The other correction polarity: when the number already matches
        the stored ratio, the rule must be a no-op, not re-stamp (and
        potentially reformat) text that was already right."""
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity spends 91.1% on programs."
        out = _sanitize(text, metrics)
        assert out == text

    def test_spends_on_programs_correction_is_idempotent(self):
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity spends 45.0% on programs."
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == "The charity spends 91.1% on programs."

    def test_for_connector_is_deliberately_normalized_to_on(self):
        """Pattern 5's replacement hardcodes "on" regardless of whether the
        match used "on" or "for" — deliberate, mirroring pattern 3's own
        precedent (which hardcodes "to" even when the match said "toward").
        Unlike the CN rule's connector bug (fixed earlier: a *different*,
        later-running rule silently rewrote an already-correct "on" from a
        sibling rule's output back to "from" on a second pass), no sibling
        rule in this family ever produces "for programs" text, so there's
        no cross-rule idempotency hazard here — just a single rule
        normalizing its own connector, stable across passes either way."""
        metrics = _metrics(program_expense_ratio=0.911)
        out = _sanitize("The charity spends 45.0% for programs.", metrics)
        assert out == "The charity spends 91.1% on programs."
        once = _sanitize("The charity spends 45.0% for programs.", metrics)
        twice = _sanitize(once, metrics)
        assert twice == once


# Each case: fabricated clause first, joined to a true clause by a bare
# " and " with no comma. The fabricated clause's own metric is nulled out;
# the true clause after "and" must survive in full, exact digits and all —
# in particular the thousands-separator comma in "4,000" must not be
# mistaken for a clause boundary the way it was before this fix.
_BARE_AND_CLAUSE_BOUNDARY_CASES = [
    (
        "program_ratio_then_serves_thousands_separator",
        "The charity has a program expense ratio of 91.1% and serves 4,000 families.",
        dict(program_expense_ratio=None),
        "Serves 4,000 families.",
    ),
    (
        "charity_navigator_then_runs_clinics",
        "It scored 87/100 from Charity Navigator and runs 12 clinics.",
        dict(cn_overall_score=None),
        "Runs 12 clinics.",
    ),
    (
        "working_capital_then_employs_staff",
        "It holds 4.2 months of working capital and employs 45 staff.",
        dict(working_capital_ratio=None),
        "Employs 45 staff.",
    ),
]


class TestClauseTrailBareAndBoundary:
    """Fixes a defect found while probing task G7: `_clause_trail` treated
    ", and" (comma + and) as a clause boundary but not a bare " and " with no
    comma, so the trailing scan ran straight through it into the next
    clause and stopped only at whatever comma or period turned up first in
    THAT clause — including a thousands-separator comma ("4,000") or a
    decimal point, truncating mid-number instead of stopping at the real
    clause boundary. Unlike the bare-comma case (genuinely ambiguous between
    an appositive and an independent clause), "and" is an unambiguous
    coordinating conjunction, so it is always a boundary — no
    continuation-lead exception needed, and the existing ", and" handling is
    untouched."""

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _BARE_AND_CLAUSE_BOUNDARY_CASES,
        ids=[n for n, *_ in _BARE_AND_CLAUSE_BOUNDARY_CASES])
    def test_bare_and_is_a_clause_boundary(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _BARE_AND_CLAUSE_BOUNDARY_CASES,
        ids=[n for n, *_ in _BARE_AND_CLAUSE_BOUNDARY_CASES])
    def test_bare_and_case_is_idempotent(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == expected

    def test_and_inside_the_removed_claims_own_cooccurrence_gap_is_unaffected(self):
        """The intra-claim "and" trap, first form: an "and" that sits
        *inside* the fabricated claim's own `_decimal_safe` co-occurrence gap
        (a separate regex fragment from `_clause_trail`, unrelated to this
        fix) must still be swallowed along with the rest of the claim — only
        an "and" *after* the claim's core match is a boundary."""
        metrics = _metrics(cn_overall_score=None)
        text = "Charity Navigator rated it 82 and awarded 87/100 and serves 500 clients."
        out = _sanitize(text, metrics)
        assert out == "Serves 500 clients."

    def test_and_inside_the_surviving_true_clause_is_left_alone(self):
        """The intra-claim "and" trap, second form: once the boundary has
        correctly stopped at the first " and " after the fabricated core, a
        second, later "and" belonging to the surviving true clause's own
        phrasing (a metric's own compound name, e.g. "accountability and
        finance") must not be re-split or truncated."""
        metrics = _metrics(program_expense_ratio=None)
        text = "The charity has a program expense ratio of 91.1% and strong accountability and finance oversight."
        out = _sanitize(text, metrics)
        assert out == "Strong accountability and finance oversight."

    def test_multiple_and_joined_true_clauses_after_removal_all_survive(self):
        metrics = _metrics(working_capital_ratio=None)
        text = "It holds 8.3 months of working capital and rising reserves and growing donor support."
        out = _sanitize(text, metrics)
        assert out == "Rising reserves and growing donor support."

    def test_and_trap_cases_are_idempotent(self):
        metrics_and_cases = [
            (_metrics(cn_overall_score=None),
             "Charity Navigator rated it 82 and awarded 87/100 and serves 500 clients."),
            (_metrics(program_expense_ratio=None),
             "The charity has a program expense ratio of 91.1% and strong accountability and finance oversight."),
            (_metrics(working_capital_ratio=None),
             "It holds 8.3 months of working capital and rising reserves and growing donor support."),
        ]
        for metrics, text in metrics_and_cases:
            once = _sanitize(text, metrics)
            twice = _sanitize(once, metrics)
            assert twice == once


# Same defect class as TestClauseTrailBareAndBoundary, mirrored onto the
# LEADING edge: a true clause can sit BEFORE an "and"-joined fabricated one
# too, and `_clause_lead` had no bare-"and" boundary either — so the leading
# scan ran straight through " and " into the fabricated clause's own
# lead-in text, stopping only at whatever comma or period turned up there.
# Found while hand-probing the trailing-edge fix (confirmed pre-existing
# and byte-identical against unmodified df62b72); the team-lead widened the
# brief to include this side too rather than filing it separately.
_BARE_AND_LEADING_CLAUSE_BOUNDARY_CASES = [
    (
        "serves_thousands_then_program_ratio",
        "It serves 4,000 families and has a program expense ratio of 91.1%.",
        dict(program_expense_ratio=None),
        "It serves 4,000 families.",
    ),
    (
        "runs_clinics_then_charity_navigator",
        "It runs 12 clinics and scored 87/100 from Charity Navigator.",
        dict(cn_overall_score=None),
        "It runs 12 clinics.",
    ),
    (
        "employs_staff_then_working_capital",
        "It employs 45 staff and holds 4.2 months of working capital.",
        dict(working_capital_ratio=None),
        "It employs 45 staff.",
    ),
    (
        "distributed_meals_multi_comma_then_working_capital",
        "It distributed 1,250,000 meals and holds 4.2 months of working capital.",
        dict(working_capital_ratio=None),
        "It distributed 1,250,000 meals.",
    ),
]


class TestClauseLeadBareAndBoundary:
    """The leading-edge mirror of `TestClauseTrailBareAndBoundary`: a bare
    " and " (no comma) is now a boundary on `_clause_lead` too, so a true
    clause sitting BEFORE an "and"-joined fabricated one survives instead of
    being truncated mid-number — e.g. "It serves 4,000 families and has a
    program expense ratio of 91.1%." used to become "It serves 4." "and" is
    an unambiguous coordinating conjunction on this side too; no
    continuation-lead exception needed."""

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _BARE_AND_LEADING_CLAUSE_BOUNDARY_CASES,
        ids=[n for n, *_ in _BARE_AND_LEADING_CLAUSE_BOUNDARY_CASES])
    def test_bare_and_is_a_leading_clause_boundary(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _BARE_AND_LEADING_CLAUSE_BOUNDARY_CASES,
        ids=[n for n, *_ in _BARE_AND_LEADING_CLAUSE_BOUNDARY_CASES])
    def test_bare_and_leading_case_is_idempotent(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == expected

    def test_and_inside_the_surviving_leading_clause_is_left_alone(self):
        """The intra-claim "and" trap, leading-side form: a true clause's
        own compound phrasing ("accountability and finance") sitting BEFORE
        the real "and" that joins it to a fabricated clause must not be
        mistaken for that boundary — the search must advance past it to the
        real connector, which sits immediately before the fabricated core.

        The numeral is deliberately the fixture's own stored
        cn_accountability_score (90, formatted "90/100" — see
        TestCnSubScoreCorrections for why this fixture's plain `int` default
        rounds to a bare "90" rather than "90.0"), not an arbitrary
        placeholder: task G8 added a correction rule for this exact
        "accountability and finance score of X" phrasing, so a wrong
        number here would now get corrected — coupling this test to that
        rule's behavior instead of the `_clause_lead` boundary placement it
        exists to check. Pinning the already-correct value keeps this test
        about boundary placement only; correction is exercised separately
        in TestCnSubScoreCorrections."""
        metrics = _metrics(program_expense_ratio=None)
        text = "It has a strong accountability and finance score of 90/100 and a program expense ratio of 91.1%."
        out = _sanitize(text, metrics)
        assert out == "It has a strong accountability and finance score of 90/100."

    def test_second_intra_claim_and_trap_months_and_rising(self):
        metrics = _metrics(cn_overall_score=None)
        text = "The charity has 8.3 months and rising in reserves and scored 87/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "The charity has 8.3 months and rising in reserves."

    def test_leading_and_trap_cases_are_idempotent(self):
        metrics_and_cases = [
            (_metrics(program_expense_ratio=None),
             "It has a strong accountability and finance score of 87 and a program expense ratio of 91.1%."),
            (_metrics(cn_overall_score=None),
             "The charity has 8.3 months and rising in reserves and scored 87/100 from Charity Navigator."),
        ]
        for metrics, text in metrics_and_cases:
            once = _sanitize(text, metrics)
            twice = _sanitize(once, metrics)
            assert twice == once

    def test_intra_claim_and_survives_untouched_with_no_removal_pending(self):
        """The team-lead's own exact wording, standalone: with nothing null
        (no removal rule firing at all), a metric's own "and"-joined
        phrasing must be a pure no-op — not just survive alongside an
        unrelated removal, but never be touched in the first place.

        The accountability numeral is deliberately the fixture's own
        stored cn_accountability_score (90, formatted "90/100" — the
        fixture's plain `int` default), not an arbitrary placeholder: task
        G8 added a correction rule for "accountability and finance score of
        X", so a wrong number here would now get corrected, coupling this
        test to that rule instead of the no-op-when-nothing's-null
        behavior it exists to check. Pinning the already-correct value
        keeps this test about the no-op only; correction is exercised
        separately in TestCnSubScoreCorrections."""
        metrics = _metrics()
        for text in [
            "It has an accountability and finance score of 90/100.",
            "It holds 8.3 months and rising in reserves.",
        ]:
            out = _sanitize(text, metrics)
            assert out == text

    def test_intra_claim_and_no_removal_case_is_idempotent(self):
        metrics = _metrics()
        for text in [
            "It has an accountability and finance score of 90/100.",
            "It holds 8.3 months and rising in reserves.",
        ]:
            once = _sanitize(text, metrics)
            twice = _sanitize(once, metrics)
            assert twice == once


class TestCnSubScoreCorrections:
    """Task G8: cn_accountability_score and cn_financial_score previously had
    only removal rules (strip the claim when null) — a wrong-but-real number
    was published verbatim, the same "corrected number, not just a stripped
    claim" gap `cn_overall_score` already had a fix for. Covers, for each
    metric: a wrong number gets corrected, an already-correct number is left
    alone, a null value still strips the claim in full (existing behavior,
    proven unbroken), and 2-pass idempotency for every case. Also covers the
    number-before phrasing ("X/100 accountability score") and the combined
    "Accountability & Finance score" phrasing Charity Navigator itself uses
    for this beacon — the collector deliberately duplicates one shared value
    into both cn_accountability_score and cn_financial_score (see
    src/collectors/charity_navigator.py:790,978, "# Same score"), so
    correcting the combined phrasing from cn_accountability_score alone is
    safe: there is no second, independent value it could disagree with."""

    # --- accountability, number-after ("accountability score of X") ---

    def test_accountability_wrong_number_is_corrected(self):
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has an accountability score of 70."
        out = _sanitize(text, metrics)
        assert out == "It has an accountability score of 91.0/100."

    def test_accountability_already_correct_survives_unchanged(self):
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has an accountability score of 91.0/100."
        out = _sanitize(text, metrics)
        assert out == text

    def test_accountability_null_still_strips_claim(self):
        metrics = _metrics(cn_accountability_score=None)
        text = "It has an accountability score of 70."
        out = _sanitize(text, metrics)
        assert out == ""

    def test_accountability_correction_is_idempotent(self):
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has an accountability score of 70."
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == "It has an accountability score of 91.0/100."

    # --- financial, number-after ("financial score of X" / "financial
    # health score of X") ---

    def test_financial_wrong_number_is_corrected(self):
        metrics = _metrics(cn_financial_score=91.0)
        text = "It has a financial score of 60."
        out = _sanitize(text, metrics)
        assert out == "It has a financial score of 91.0/100."

    def test_financial_health_wrong_number_is_corrected(self):
        """The "health" variant — the exact phrasing named in the brief.
        Echoes "financial health score" back verbatim (only the number is
        fixed), matching the same echo-the-noun-phrase approach used for
        accountability/governance above."""
        metrics = _metrics(cn_financial_score=91.0)
        text = "It has a financial health score of 60."
        out = _sanitize(text, metrics)
        assert out == "It has a financial health score of 91.0/100."

    def test_financial_already_correct_survives_unchanged(self):
        metrics = _metrics(cn_financial_score=91.0)
        text = "It has a financial score of 91.0/100."
        out = _sanitize(text, metrics)
        assert out == text

    def test_financial_null_still_strips_claim(self):
        metrics = _metrics(cn_financial_score=None)
        text = "It has a financial score of 60."
        out = _sanitize(text, metrics)
        assert out == ""

    def test_financial_correction_is_idempotent(self):
        metrics = _metrics(cn_financial_score=91.0)
        text = "It has a financial score of 60."
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == "It has a financial score of 91.0/100."

    def test_financial_number_before_is_not_recognized_yet(self):
        """Documented gap, not a defect: unlike accountability, financial's
        number-before shape ("X/100 financial score") has zero live
        occurrences (checked website/data/charities/, 0/166) and isn't named
        in the G8 brief's required-phrasing list, so no rule was added for
        it. Pins the current (unhandled) behavior so a future change doesn't
        silently start altering it without a deliberate decision."""
        metrics = _metrics(cn_financial_score=91.0)
        text = "It earned a 91/100 financial score."
        out = _sanitize(text, metrics)
        assert out == text

    # --- accountability, number-before ("X/100 accountability score/rating")
    # — a shape with NO removal counterpart before this task, since the old
    # removal rule only matched the number-after "accountability score of X"
    # shape. Closing the correction side without also closing removal would
    # have left a null accountability score with this phrasing completely
    # unhandled — neither corrected nor stripped. ---

    def test_accountability_number_before_wrong_is_corrected(self):
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has a 70/100 accountability score."
        out = _sanitize(text, metrics)
        assert out == "It has a 91.0/100 accountability score."

    def test_accountability_number_before_rating_variant(self):
        """"rating" (not just "score") and "governance" (not just
        "accountability") both occur in real published prose for this
        shape — see charity-95-4453134.json ("97/100 accountability
        rating"). The noun and score/rating word are echoed back verbatim,
        not canonicalized to "accountability score" — see
        test_governance_article_is_not_broken_by_canonicalization for why
        that matters (a hardcoded "accountability" would silently produce
        a grammar error for a preceding article chosen for "governance")."""
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It earned a perfect 97/100 governance rating."
        out = _sanitize(text, metrics)
        assert out == "It earned a perfect 91.0/100 governance rating."

    def test_governance_article_is_not_broken_by_canonicalization(self):
        """Hand-probed failure mode: a version of this rule that hardcoded
        "accountability" in its replacement turned "a governance score of
        60" into "a accountability score of ..." — grammatically wrong,
        since "accountability" starts with a vowel sound and needs "an".
        Echoing the original noun phrase back (see baseline.py's
        `_acc_name` comment) leaves the article, which was already correct
        for the original word, untouched."""
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has a governance score of 60."
        out = _sanitize(text, metrics)
        assert out == "It has a governance score of 91.0/100."

    def test_accountability_score_percent_suffix_is_consumed_not_stranded(self):
        """Hand-probed failure mode: the optional trailing suffix group
        didn't include "%", so "accountability score of 87%" left the "%"
        outside the match — the correction (which already ends in "/100")
        then produced the garbled "91.0/100%". Fixed by adding "%" to the
        optional suffix alternation."""
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has an accountability score of 87%."
        out = _sanitize(text, metrics)
        assert out == "It has an accountability score of 91.0/100."

    def test_financial_score_percent_suffix_is_consumed_not_stranded(self):
        metrics = _metrics(cn_financial_score=91.0)
        text = "It has a financial score of 60%."
        out = _sanitize(text, metrics)
        assert out == "It has a financial score of 91.0/100."

    def test_accountability_number_before_already_correct_survives_unchanged(self):
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has a 91.0/100 accountability score."
        out = _sanitize(text, metrics)
        assert out == text

    def test_accountability_number_before_null_still_strips_claim(self):
        metrics = _metrics(cn_accountability_score=None)
        text = "It has a 70/100 accountability score."
        out = _sanitize(text, metrics)
        assert out == ""

    def test_accountability_number_before_is_idempotent(self):
        metrics = _metrics(cn_accountability_score=91.0)
        text = "It has a 70/100 accountability score."
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == "It has a 91.0/100 accountability score."

    # --- combined "Accountability & Finance score" phrasing (CN's own name
    # for this beacon; see class docstring for why cn_accountability_score
    # alone is a safe anchor for it) ---

    def test_combined_ampersand_wrong_is_corrected(self):
        """Echoes "Accountability & Finance" back verbatim rather than
        canonicalizing to plain "accountability" — same echo-the-noun-
        phrase reasoning as the governance/article case above; there is no
        grammar hazard here, but preserving the source's own phrasing is
        the more conservative fix, and it's what the shared `_acc_name`
        capture group produces either way."""
        metrics = _metrics(cn_accountability_score=91.0, cn_financial_score=91.0)
        text = "It has an Accountability & Finance score of 70."
        out = _sanitize(text, metrics)
        assert out == "It has an Accountability & Finance score of 91.0/100."

    def test_combined_and_wrong_is_corrected(self):
        metrics = _metrics(cn_accountability_score=91.0, cn_financial_score=91.0)
        text = "It has an accountability and finance score of 70."
        out = _sanitize(text, metrics)
        assert out == "It has an accountability and finance score of 91.0/100."

    def test_combined_number_before_wrong_is_corrected(self):
        metrics = _metrics(cn_accountability_score=91.0, cn_financial_score=91.0)
        text = "It holds a perfect 70/100 Accountability & Finance score."
        out = _sanitize(text, metrics)
        assert out == "It holds a perfect 91.0/100 Accountability & Finance score."

    def test_combined_null_still_strips_claim(self):
        metrics = _metrics(cn_accountability_score=None, cn_financial_score=None)
        text = "It has an accountability and finance score of 70."
        out = _sanitize(text, metrics)
        assert out == ""

    def test_combined_is_idempotent(self):
        metrics = _metrics(cn_accountability_score=91.0, cn_financial_score=91.0)
        for text in [
            "It has an Accountability & Finance score of 70.",
            "It holds a perfect 70/100 Accountability & Finance score.",
        ]:
            once = _sanitize(text, metrics)
            twice = _sanitize(once, metrics)
            assert twice == once

    # --- sentence-initial capitalization hazard (Critical 1's class): a
    # preceding removal from a DIFFERENT metric family exposes the new
    # accountability/financial correction rules sentence-initially. ---

    def test_working_capital_removal_exposes_accountability_correction(self):
        metrics = _metrics(working_capital_ratio=None, cn_accountability_score=91.0)
        text = "It holds 4.2 months of working capital, and has an accountability score of 70."
        out = _sanitize(text, metrics)
        assert out == "Has an accountability score of 91.0/100."

    def test_program_ratio_removal_exposes_financial_correction(self):
        metrics = _metrics(program_expense_ratio=None, cn_financial_score=91.0)
        text = "Has a program expense ratio of 91.1%, and has a financial score of 60."
        out = _sanitize(text, metrics)
        assert out == "Has a financial score of 91.0/100."

    def test_cn_score_removal_exposes_accountability_correction(self):
        metrics = _metrics(cn_overall_score=None, cn_accountability_score=91.0)
        text = "Scored 87/100 from Charity Navigator, and has an accountability score of 70."
        out = _sanitize(text, metrics)
        assert out == "Has an accountability score of 91.0/100."

    def test_accountability_removal_exposes_financial_correction(self):
        metrics = _metrics(cn_accountability_score=None, cn_financial_score=91.0)
        text = "Has an accountability score of 70, and has a financial score of 60."
        out = _sanitize(text, metrics)
        assert out == "Has a financial score of 91.0/100."

    def test_cross_family_exposure_is_idempotent(self):
        cases = [
            ("It holds 4.2 months of working capital, and has an accountability score of 70.",
             _metrics(working_capital_ratio=None, cn_accountability_score=91.0)),
            ("Has a program expense ratio of 91.1%, and has a financial score of 60.",
             _metrics(program_expense_ratio=None, cn_financial_score=91.0)),
            ("Scored 87/100 from Charity Navigator, and has an accountability score of 70.",
             _metrics(cn_overall_score=None, cn_accountability_score=91.0)),
            ("Has an accountability score of 70, and has a financial score of 60.",
             _metrics(cn_accountability_score=None, cn_financial_score=91.0)),
        ]
        for text, metrics in cases:
            once = _sanitize(text, metrics)
            twice = _sanitize(once, metrics)
            assert twice == once

    def test_brief_worked_example(self):
        """The exact repro from the G8 brief: cn_accountability_score=91.0,
        input states 70 — must now be corrected, not published verbatim."""
        metrics = _metrics(working_capital_ratio=None, cn_accountability_score=91.0)
        text = "It holds 4.2 months of working capital, and accountability score of 70."
        out = _sanitize(text, metrics)
        assert out == "Accountability score of 91.0/100."

    def test_charity_36_3673599_malformed_string_is_left_as_is(self):
        """charity-36-3673599.json (read-only — never modified by this
        test) carries a known, pre-existing mangled-CN-score artifact
        awaiting regeneration, not repair-in-place: "Strong external
        accountability rating of 96.96.0/100 from Charity Navigator" (a
        double-decimal corruption, phrased as "accountability rating" —
        not "score" — while the number is actually the CN *overall* score,
        not the accountability sub-score; stored accountability is 86.0,
        stored overall is 96). Neither new rule touches it: both require
        the literal word "score" (not "rating") immediately adjacent to
        "accountability"/"governance" for the number-after and
        number-before shapes alike, and the corrupted leading "96." isn't
        part of any recognized numeric shape either. Documented so it's
        clear regeneration — not this sanitizer — is what will fix that
        page; this task neither fixes nor worsens it."""
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "Strong external accountability rating of 96.96.0/100 from Charity Navigator"
        out = _sanitize(text, metrics)
        assert out == text


class TestNegativeWorkingCapitalDoesNotAccumulateDashes:
    """Live, unbounded bug found while auditing G8 (not caused by it, and not
    fixed by any prior task in this series — `_wc_num_unit` predates all of
    them): working_capital_ratio is net_assets / monthly_expenses with no
    floor at zero, so a negative value is a real, legitimate figure (unlike
    every other metric this function corrects, all non-negative by
    construction — see the report's survey of cn_overall_score/
    cn_accountability_score/cn_financial_score (Pydantic `ge=0`),
    program_expense_ratio (Pydantic `ge=0`), and amal_score (`max(0, ...)`
    clamped in the scorer) — none of which needed this fix).

    The old `_wc_num_unit` (`\\d+\\.?\\d*\\s*(?:months?|years?)`) never matched
    a leading "-", so the match started at the digit, and `correct_wc`
    (which does carry the sign when negative) got inserted right after
    whatever dash was already sitting there instead of replacing it. Two
    live published narratives (EIN 56-2392452 and 92-3079413, both citation
    fields) already show "---2.7"/"---6.1" — three dashes deep, from
    repeated sanitize passes (this runs twice for real on the citation-repair
    retry path). Left as-is per instruction; not this task's job to repair
    already-published text, only to stop the accumulation going forward."""

    def test_correction_is_stable_across_five_passes(self):
        """Two passes wouldn't have caught this (the bug adds one dash per
        pass, so pass 2 already differs from pass 1) — five passes is what
        actually demonstrates a fixed point rather than a slow leak."""
        metrics = _metrics(working_capital_ratio=-2.7)
        text = "The charity holds -2.7 months of working capital."
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize(passes[-1], metrics))
        assert passes[1] == "The charity holds -2.7 months of working capital."
        assert passes[1] == passes[2] == passes[3] == passes[4] == passes[5]

    def test_wrong_negative_number_is_corrected_and_then_stable(self):
        metrics = _metrics(working_capital_ratio=-6.1)
        text = "The charity holds -2.7 months of working capital."
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize(passes[-1], metrics))
        assert passes[1] == "The charity holds -6.1 months of working capital."
        assert passes[1] == passes[2] == passes[3] == passes[4] == passes[5]

    def test_already_mangled_multi_dash_text_does_not_grow_further(self):
        """Does NOT repair the pre-existing artifact (still 3 dashes after
        sanitizing) — only confirms it stops getting worse. Matches the
        real shape published in EIN 56-2392452/92-3079413."""
        metrics = _metrics(working_capital_ratio=-2.7)
        text = "The charity holds ---2.7 months of working capital."
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize(passes[-1], metrics))
        assert all(p == "The charity holds ---2.7 months of working capital." for p in passes)

    def test_null_metric_still_fully_removes_a_negative_claim(self):
        """Removal path, negative-value polarity: the claim must still be
        stripped in full when the metric is null, exactly as it is for a
        positive value — the sign is not special-cased for removal."""
        metrics = _metrics(working_capital_ratio=None)
        text = "It holds -2.7 months of working capital."
        out = _sanitize(text, metrics)
        assert out == ""
        twice = _sanitize(out, metrics)
        assert twice == out

    def test_null_metric_removes_negative_claim_but_preserves_companion_clause(self):
        metrics = _metrics(working_capital_ratio=None)
        text = "It holds -2.7 months of working capital, and spends $0.10 per $1 raised."
        out = _sanitize(text, metrics)
        assert out == "Spends $0.10 per $1 raised."
        twice = _sanitize(out, metrics)
        assert twice == out

    def test_reproduces_the_two_live_published_cases(self):
        """The exact shapes published in EIN 56-2392452 and 92-3079413,
        confirming the fix applies to the real citation-claim phrasing, not
        just a simplified test sentence. Not asserting anything about the
        already-published 3-dash text itself (not this task's job to
        repair it) — only that a *fresh* sanitize of the correct, un-mangled
        figure is stable."""
        metrics = _metrics(working_capital_ratio=-2.7)
        text = (
            "In FY2024, the charity had a 90.3% program ratio, $4,309,990 in revenue, "
            "-2.7 months of working capital, and $0.02 fundraising efficiency."
        )
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize(passes[-1], metrics))
        assert passes[1] == passes[2] == passes[3] == passes[4] == passes[5]
        assert "-2.7 months" in passes[1]
        assert "--2.7" not in passes[1]


class TestStrayCommaAfterPeriodIsRepunctuatedNotDropped:
    """Task G10: `_clause_lead`'s leftmost-match search starts a removal's
    leading edge as early as the previous sentence's own terminal period
    (see its docstring), swallowing the boundary space along with the
    fabricated clause. When the surviving fragment on the far side is
    joined by a bare comma with no recognized continuation lead (see
    `_trail_same_claim_lead`), that fragment ends up touching the previous
    period with literally zero whitespace between them: a genuine `.,`
    reads as "...administrative costs., as reported in its latest
    filings." — visibly malformed prose, even though no number is wrong.

    Nine real published narratives had this shape (all traced to the
    `program_expense_ratio`/`fundraising_efficiency`/`working_capital`
    removal rules leaving a trailing appositive- or coordinate-fragment
    behind). The first hypothesis for fixing it — drop the whole
    comma-led fragment, on the theory that it always belonged to the
    removed claim — is correct for 7 of the 9, but was checked against
    all nine before being built on, and breaks for 2: `56-2639095`'s
    fragment is a real, distinct 99.7-months-of-reserves figure, and
    `88-0405956`'s is a real, distinct 17%-revenue-decline figure —
    neither restated anywhere else in those narratives, so dropping either
    would silently delete a true fact. There's no mechanical way to tell
    "gloss fragment, safe to drop" (leads with a participle/subordinator:
    "meaning", "as", "which", "suggesting" — can't stand alone) apart from
    "independent/coordinate clause carrying its own fact" (leads with its
    own subject-and-verb, or a coordinating "and"/"but") without
    reproducing the exact open-class verb/appositive-lead enumeration
    problem `_clause_trail` already gave up on. So the fix never drops the
    fragment at all: it inserts the one missing space so the fragment
    starts a fresh, capitalized sentence instead of running on from a
    comma. The trade is an occasional awkward-but-truthful fragment
    sentence ("Meaning it does not spend donor funds...") in exchange for
    a guarantee that no fact is ever silently lost — the same
    over-preservation-beats-over-removal tie-break already documented
    elsewhere in this function.

    A tenth, previously-uncounted case turned up empirically while
    checking `baseline_narrative` as well as `rich_narrative` — EIN
    23-7065716 has the same artifact in `baseline_narrative` too (its own
    prior task, G8, only checked `rich_narrative` for this category).
    Covered here as the seventh distinct shape.
    """

    def test_meaning_gloss_becomes_its_own_sentence(self):
        """Shape 1 of 7 — EINs 11-3013369, 46-3973114, 83-2222109: a
        participial gloss ("meaning ...") that only restates the just-
        removed fundraising claim, with nothing of its own to lose."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "It provides critical services in Pakistan. "
            "The organization is notable for its fundraising efficiency of $0.00 per $1 raised, "
            "meaning it does not spend donor funds on professional fundraising fees. "
            "However, donors should note that the foundation holds significant reserves."
        )
        expected = (
            "It provides critical services in Pakistan. "
            "Meaning it does not spend donor funds on professional fundraising fees. "
            "However, donors should note that the foundation holds significant reserves."
        )
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_as_attribution_becomes_its_own_sentence(self):
        """Shape 2 of 7 — EINs 20-3069841, 54-1674126 (the team-lead's own
        worked example: "...costs., as reported..." -> "...costs.
        Furthermore..." was the hypothesis that started this task; this is
        the case where dropping and re-punctuating agree)."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "It achieved a lean financial model, ensuring that public donations are not diverted to administrative costs. "
            "This is supported by fundraising efficiency of $0.00 per $1 raised, as reported in its latest filings. "
            "Furthermore, the organization demonstrates strong outcomes."
        )
        expected = (
            "It achieved a lean financial model, ensuring that public donations are not diverted to administrative costs. "
            "As reported in its latest filings. "
            "Furthermore, the organization demonstrates strong outcomes."
        )
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_which_relative_clause_becomes_its_own_sentence(self):
        """Shape 3 of 7 — EIN 23-7065716 (rich_narrative)."""
        metrics = _metrics(working_capital_ratio=None)
        text = (
            "Operations appear efficient, but the lack of outcome tracking makes it difficult to verify actual results. "
            "The organization currently has 1.2 months of working capital, which is considered lean."
        )
        expected = (
            "Operations appear efficient, but the lack of outcome tracking makes it difficult to verify actual results. "
            "Which is considered lean."
        )
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_suggesting_inference_becomes_its_own_sentence(self):
        """Shape 4 of 7 — EIN 26-3531888."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "It has achieved a strong growth rate over three years. "
            "The organization is also noted for its fundraising efficiency of $0.00 per $1 raised, "
            "suggesting that it relies on low-cost donor acquisition methods. "
            "Furthermore, the charity holds significant total assets."
        )
        expected = (
            "It has achieved a strong growth rate over three years. "
            "Suggesting that it relies on low-cost donor acquisition methods. "
            "Furthermore, the charity holds significant total assets."
        )
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_it_holds_independent_clause_preserves_the_real_fact(self):
        """Shape 5 of 7 — EIN 56-2639095. This is one of the two cases that
        broke the team-lead's original "drop the fragment" hypothesis: what
        follows the artifact isn't debris from the removed fundraising
        claim, it's a real, distinct working-capital figure. Dropping it
        would have deleted a true fact; it must survive, as its own
        sentence."""
        metrics = _metrics(fundraising_expenses=None, working_capital_ratio=99.7)
        text = (
            "The organization reported a revenue decline between 2022 and 2023, with total revenue falling to $461,841. "
            "While the foundation maintains high fundraising efficiency, spending $0.00 to raise every $1, "
            "it also holds 99.7 months of operating reserves. "
            "For a zakat-collecting entity, this level of capital retention is unusual."
        )
        expected = (
            "The organization reported a revenue decline between 2022 and 2023, with total revenue falling to $461,841. "
            "It also holds 99.7 months of operating reserves. "
            "For a zakat-collecting entity, this level of capital retention is unusual."
        )
        assert _sanitize(text, metrics) == expected
        assert "99.7 months" in expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_and_coordinate_clause_preserves_the_real_fact(self):
        """Shape 6 of 7 — EIN 88-0405956. The other case that broke "drop
        the fragment": the 17%-revenue-decline figure is a real, distinct
        fact joined via "and" as the second half of a "balance between X
        and Y" construction, not commentary on the removed claim."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "The organization reported a program expense ratio in FY2024, which is below the industry standard. "
            "This neutral performance reflects a balance between high fundraising efficiency, "
            "where the charity spends $0.00 to raise every $1, and a recent 17% decline in revenue "
            "from the previous fiscal year. Despite these shifts, the charity remains financially stable."
        )
        expected = (
            "The organization reported a program expense ratio in FY2024, which is below the industry standard. "
            "A recent 17% decline in revenue from the previous fiscal year. "
            "Despite these shifts, the charity remains financially stable."
        )
        assert _sanitize(text, metrics) == expected
        assert "17% decline" in expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_but_independent_clause_becomes_a_full_sentence(self):
        """Shape 7 of 7 — EIN 23-7065716's `baseline_narrative` field, found
        empirically while checking both fields rather than just
        `rich_narrative` (not one of the team-lead's original nine — this
        one wasn't counted until this task's own empirical check covered
        both). "but the high amount of..." has its own subject and verb,
        so it comes out as a complete, grammatical sentence rather than a
        fragment — unlike the participial/subordinate-clause shapes above."""
        metrics = _metrics(working_capital_ratio=None)
        text = (
            "However, there is no clear evidence or third-party data showing the long-term effectiveness of these services. "
            "The organization holds 1.2 months of working capital available, "
            "but the high amount of total reserves may conflict with the need to distribute zakat funds quickly."
        )
        expected = (
            "However, there is no clear evidence or third-party data showing the long-term effectiveness of these services. "
            "But the high amount of total reserves may conflict with the need to distribute zakat funds quickly."
        )
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_repair_does_not_fire_without_a_stray_period_comma(self):
        """Ordinary prose containing a period and a later, unrelated comma
        must be left completely untouched — the repair only targets a
        comma directly touching a period, not "any period somewhere before
        any comma somewhere later." A `not in` assertion would pass even
        against a mangled string, so this asserts the exact, full output."""
        text = "The charity operates efficiently. Its revenue, however, remained flat this year."
        assert _repair_removal_artifacts(text) == text

    def test_repair_is_a_no_op_on_text_with_no_removal_artifact_at_all(self):
        text = "The organization serves refugees in Jordan and Lebanon."
        assert _repair_removal_artifacts(text) == text


class TestAbbreviationBeforeCommaIsNotMistakenForARemovalArtifact:
    """A bare `.,` isn't unique to the removal artifact above — "U.S.,",
    "e.g.,", "Inc.,", "Jr.,", and "et al.," are all ordinary, correctly
    punctuated English with the exact same zero-whitespace period-then-
    comma shape. Unlike the open-ended appositive-lead-in class
    `_clause_trail` gave up on enumerating, sentence-ending abbreviations
    are a small, closed, standard set (the same kind of static list
    sentence-boundary detectors have always used), so `_ABBREVIATIONS_
    BEFORE_COMMA` is a bounded, defensible exception list, not a repeat of
    that problem. `(e.g.,` and `U.S.,` are both real, live occurrences in
    the corpus today (`charity-26-3531888.json` and `charity-23-2202414
    .json`, among others) — this isn't a hypothetical hazard."""

    def test_inc_before_comma_is_untouched(self):
        text = "XYZ Foundation, Inc., is a 501(c)(3) charity."
        assert _repair_removal_artifacts(text) == text

    def test_jr_before_comma_is_untouched(self):
        text = "Founded by John Smith Jr., the organization serves refugees."
        assert _repair_removal_artifacts(text) == text

    def test_e_g_before_comma_is_untouched(self):
        """The real, live shape from charity-26-3531888.json."""
        text = "It requires a high percentage of donations (e.g., >80%) to go directly to programs."
        assert _repair_removal_artifacts(text) == text

    def test_u_s_before_comma_is_untouched(self):
        """The real, live shape from charity-23-2202414.json."""
        text = "A potential concern for donors is that spending remains in the U.S., even though the mission is global."
        assert _repair_removal_artifacts(text) == text

    def test_et_al_before_comma_is_untouched(self):
        text = "The report cites prior studies (et al., 2024) on donor behavior."
        assert _repair_removal_artifacts(text) == text

    def test_abbreviation_survives_even_when_a_real_removal_fires_elsewhere(self):
        """The guard has to hold in the actual invocation path, not just in
        isolation: `_repair_removal_artifacts` only runs at all when some
        OTHER removal fired somewhere in the same text field, and then it
        scans the whole field — so an unrelated "Inc.," sitting elsewhere
        in that same string must survive a real removal happening nearby."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "XYZ Foundation, Inc., is a 501(c)(3) charity. "
            "The organization is notable for its fundraising efficiency of $0.00 per $1 raised, "
            "meaning it does not spend donor funds on professional fundraising fees. "
            "It operates primarily in the U.S., serving refugees nationwide."
        )
        out = _sanitize(text, metrics)
        assert out == (
            "XYZ Foundation, Inc., is a 501(c)(3) charity. "
            "Meaning it does not spend donor funds on professional fundraising fees. "
            "It operates primarily in the U.S., serving refugees nationwide."
        )


class TestCnRatingPhrasingIsNotMisattributedToOverallScore:
    """Task G11, Finding 1: the generic cn_overall_score rule ("X/100 ...
    Charity Navigator") only ever competed with the accountability/financial
    rules over the literal word "score" — those rules required "score" and
    ignored "rating", so "accountability rating of X/100 from Charity
    Navigator" fell through to the generic rule and got the *overall* score
    stamped into a slot labelled accountability. Fixed two ways: the
    accountability/financial correction rules now recognize "rating" too
    (not just "score"), and the generic rule now refuses to claim a span
    whose number is named by a sub-score noun (`_sub_score_lead_re` in
    baseline.py) rather than relying on rule ordering to sort it out — the
    brief was explicit that ordering is fragile and this function has
    already shipped two bugs from rules matching each other's output."""

    def test_accountability_rating_wrong_is_corrected_not_overall(self):
        """The brief's own isolated repro, first line: "rating" phrasing
        used to get the overall score (96) instead of accountability's own
        value (86)."""
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "Strong external accountability rating of 50/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "Strong external accountability rating of 86.0/100 from Charity Navigator."

    def test_financial_health_rating_wrong_is_corrected_not_overall(self):
        """The brief's second isolated repro line: "financial health rating"
        used to get the overall score (96) instead of financial's own value
        (88)."""
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "The charity has a financial health rating of 40/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "The charity has a financial health rating of 88.0/100 from Charity Navigator."

    def test_accountability_score_phrasing_still_correct(self):
        """The brief's third isolated repro line, pinned as a no-regression
        check: "score" phrasing already worked before this task (the
        accountability rule's own re-correction happened to overwrite
        whatever the generic rule stamped in first) — the gap was
        specifically "rating", not "score"."""
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "Strong external accountability score of 50/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "Strong external accountability score of 86.0/100 from Charity Navigator."

    def test_accountability_rating_already_correct_survives_unchanged(self):
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "Strong external accountability rating of 86.0/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_financial_rating_already_correct_survives_unchanged(self):
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "The charity has a financial health rating of 88.0/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_accountability_rating_null_still_strips_claim(self):
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=None, cn_financial_score=88.0)
        text = "Strong external accountability rating of 50/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == ""

    def test_financial_rating_null_still_strips_claim(self):
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=None)
        text = "The charity has a financial health rating of 40/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == ""

    def test_governance_rating_wrong_is_corrected(self):
        """"governance" (an _acc_name alternative) with "rating" phrasing —
        both axes of the noun/word matrix at once."""
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "It earned a governance rating of 50/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "It earned a governance rating of 86.0/100 from Charity Navigator."

    def test_plain_overall_rating_with_no_subscore_noun_is_unaffected(self):
        """Regression: the guard must not over-fire on ordinary overall-score
        prose that names no sub-score at all — that's exactly the shape the
        generic rule exists to correct."""
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "The charity earned a rating of 50/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "The charity earned a rating of 96.0/100 from Charity Navigator."

    def test_linking_verb_is_also_guarded_not_just_of(self):
        """Hand-probed beyond the brief's own two repro lines: "X rating IS
        N" (a linking verb, not the preposition "of") is a different
        phrasing shape than either sub-score correction rule parses — that
        part is unchanged, pre-existing, and out of this task's scope, so
        the financial number here stays uncorrected either way. But before
        the guard also recognized "is"/"was", the generic overall rule
        still claimed this span and replaced the financial number with the
        *overall* score (96.0) — the exact mislabeling Finding 1 is about,
        just one preposition removed from the brief's own examples. The
        fix must leave the number exactly as the model wrote it (still
        wrong, but not actively mislabeled as a different metric)."""
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        text = "The accountability rating is 50/100 and the financial rating is 40/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text",
        [
            "Strong external accountability rating of 50/100 from Charity Navigator.",
            "The charity has a financial health rating of 40/100 from Charity Navigator.",
            "Strong external accountability score of 50/100 from Charity Navigator.",
            "It earned a governance rating of 50/100 from Charity Navigator.",
            "The charity earned a rating of 50/100 from Charity Navigator.",
        ],
    )
    def test_rating_phrasing_correction_is_five_pass_stable(self, text):
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestBareRatingPhrasingWithoutSlashOrCitationIsStillCorrected:
    """Task G11, Finding 2: "rating of N" with no "/100" suffix and/or no
    "Charity Navigator" mention nearby must still be corrected when the noun
    names a metric this function holds a real value for — the optional
    trailing-suffix group already tolerated a missing "/100" for "score"
    phrasing (see G8), and extending "score" to "score|rating" inherits that
    tolerance for free, so both gaps close with the same one-word change,
    no separate handling needed. Judgment call, stated plainly: a BARE
    "rating of N" with no "/100" and no unit at all is still only corrected
    when it's immediately anchored to one of the closed noun alternatives
    (accountability/governance/financial(-health)) this function already
    recognizes — an unanchored "rating" (no noun at all, e.g. "a rating of
    50") is NOT touched, since without a noun there's no way to know which
    metric (or the overall score) it's even claiming, and guessing wrong
    would fabricate an attribution that was never there. That shape is
    intentionally left alone, not silently handled."""

    def test_accountability_rating_no_slash_no_citation_is_corrected(self):
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "The charity earned an accountability rating of 50 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "The charity earned an accountability rating of 86.0/100 from Charity Navigator."

    def test_accountability_rating_no_charity_navigator_mention_is_corrected(self):
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "The charity earned an accountability rating of 50/100."
        out = _sanitize(text, metrics)
        assert out == "The charity earned an accountability rating of 86.0/100."

    def test_accountability_rating_bare_number_no_slash_no_navigator_is_corrected(self):
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "The charity earned an accountability rating of 50."
        out = _sanitize(text, metrics)
        assert out == "The charity earned an accountability rating of 86.0/100."

    def test_financial_rating_no_slash_is_corrected(self):
        metrics = _metrics(cn_financial_score=88.0)
        text = "The charity has a financial rating of 40."
        out = _sanitize(text, metrics)
        assert out == "The charity has a financial rating of 88.0/100."

    def test_unanchored_bare_rating_with_no_noun_is_deliberately_left_alone(self):
        """No accountability/financial/overall noun at all — nothing here
        says which metric this number is even claiming, so nothing
        corrects it. Documented gap, not a defect."""
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "The charity earned a rating of 50 last year."
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text",
        [
            "The charity earned an accountability rating of 50 from Charity Navigator.",
            "The charity earned an accountability rating of 50/100.",
            "The charity earned an accountability rating of 50.",
            "The charity has a financial rating of 40.",
        ],
    )
    def test_bare_rating_correction_is_five_pass_stable(self, text):
        metrics = _metrics(cn_accountability_score=86.0, cn_financial_score=88.0, cn_overall_score=96.0)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestMalformedMultiDecimalNumberIsNeverSplicedWithANewValue:
    """Task G11, Finding 3: a malformed multi-decimal numeral (two or more
    embedded decimal points in one run, e.g. "96.96.0" — a corrupted
    leftover from an earlier regeneration, not something any current rule
    produces from clean input) has no single clean number any correction
    rule can take without either starting late (skipping a stray leading
    "<digit>." and inventing a phantom value that existed in neither the
    source data nor the corrupted input) or starting on time but stopping
    short at the first embedded dot (splicing a correction onto a numeral
    that silently continues right after it).

    Decision: LEAVE IT COMPLETELY UNTOUCHED, for every rule in this section
    (cn_overall_score, cn_accountability_score, cn_financial_score) —
    reasoned as follows. Removing the whole claim was rejected: the standing
    rule elsewhere in this function (see `_clause_trail`'s own comments) is
    that over-preserving a claim is safer than over-removing one, and nothing
    about a malformed *number* changes that; the claim itself (that Charity
    Navigator rates this charity) is still true, only its printed number is
    corrupted. Correcting the whole token by rewriting the entire malformed
    run was also rejected: that requires guessing which of the multiple
    embedded numbers (if any) the LLM meant, and a wrong guess would silently
    replace one fabricated number with a different fabricated one dressed up
    as a fix — worse than doing nothing, since it would look authoritative.
    Leaving it alone is honest about what this sanitizer can't safely infer,
    matches the existing stance on `charity-36-3673599.json`'s pinned test,
    and — verified below — is what the three real, currently-published
    malformed narratives already need: regeneration, not in-place repair."""

    def test_overall_score_malformed_number_is_left_untouched(self):
        """The brief's own isolated repro: a phantom "91.2" spliced in where
        neither the raw input nor the source data ever had it."""
        metrics = _metrics(cn_overall_score=91.2)
        text = "It earned a 96.96.0/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_accountability_rating_malformed_number_is_left_untouched(self):
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "Strong external accountability rating of 96.96.0/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_accountability_score_malformed_number_is_left_untouched(self):
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "Strong external accountability score of 96.96.0/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_financial_score_malformed_number_is_left_untouched(self):
        metrics = _metrics(cn_financial_score=88.0, cn_overall_score=96.0)
        text = "The charity has a financial health score of 96.96.0/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_number_before_accountability_malformed_number_is_left_untouched(self):
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        text = "It holds a 96.96.0/100 accountability rating."
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,overrides",
        [
            ("It earned a 96.96.0/100 from Charity Navigator.", dict(cn_overall_score=91.2)),
            ("Strong external accountability rating of 96.96.0/100 from Charity Navigator.",
             dict(cn_accountability_score=86.0, cn_overall_score=96.0)),
            ("The charity has a financial health score of 96.96.0/100 from Charity Navigator.",
             dict(cn_financial_score=88.0, cn_overall_score=96.0)),
        ],
    )
    def test_malformed_number_is_five_pass_stable(self, text, overrides):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    # --- the three real, currently-published malformed narratives (read
    # from website/data/charities/ while writing this task; the exact
    # strings and scores are pinned here, not re-read from disk, since this
    # file must stay independent of that data — see the report for how they
    # were reconstructed) ---

    @pytest.mark.parametrize(
        "ein,overrides,text",
        [
            ("95-4453134",
             dict(cn_accountability_score=100, cn_overall_score=97, cn_financial_score=100),
             "High transparency and accountability rating of 97.97.0/100 from Charity Navigator"),
            ("47-2864379",
             dict(cn_accountability_score=92, cn_overall_score=97.5, cn_financial_score=92),
             "Strong external accountability rating of 97.97.5/100 from Charity Navigator"),
            ("36-3673599",
             dict(cn_accountability_score=85.99555863262657, cn_overall_score=96, cn_financial_score=85.99555863262657),
             "Strong external accountability rating of 96.96.0/100 from Charity Navigator"),
        ],
    )
    def test_live_malformed_narratives_are_left_untouched_pending_regeneration(self, ein, overrides, text):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == text, f"{ein}: malformed narrative should be left untouched, not repaired in place"

    def test_95_4453134_once_regenerated_to_clean_text_uses_true_accountability(self):
        """This EIN's malformed string can't be repaired in place (see
        above) — but this proves the underlying Finding 1 bug it also
        carries (the "rating" wording being stamped with the *overall*
        score, 97, instead of the real accountability value, 100) is fixed
        for what regeneration will produce: a clean, single-decimal number
        (the malformed run collapsed to its true single-decimal overall
        value, which is presumably what the live LLM output looked like
        before whatever earlier bug mangled it)."""
        metrics = _metrics(cn_accountability_score=100, cn_overall_score=97, cn_financial_score=100)
        text = "High transparency and accountability rating of 97/100 from Charity Navigator"
        out = _sanitize(text, metrics)
        assert out == "High transparency and accountability rating of 100/100 from Charity Navigator"

    def test_47_2864379_once_regenerated_to_clean_text_uses_true_accountability(self):
        metrics = _metrics(cn_accountability_score=92, cn_overall_score=97.5, cn_financial_score=92)
        text = "Strong external accountability rating of 97.5/100 from Charity Navigator"
        out = _sanitize(text, metrics)
        assert out == "Strong external accountability rating of 92/100 from Charity Navigator"

    def test_36_3673599_once_regenerated_to_clean_text_uses_true_accountability(self):
        metrics = _metrics(
            cn_accountability_score=85.99555863262657, cn_overall_score=96, cn_financial_score=85.99555863262657
        )
        text = "Strong external accountability rating of 96/100 from Charity Navigator"
        out = _sanitize(text, metrics)
        assert out == "Strong external accountability rating of 86.0/100 from Charity Navigator"


class TestProgramExpenseNounIsEchoedNotHardcodedToProgramsPlural:
    """Task G11: the directs/allocates/etc. correction rule's `programs?`
    alternative matched just the word "program" inside the unrelated phrase
    "program expense" (no word boundary was needed before the next word),
    then hardcoded the replacement to plural "programs" — so "directs 50%
    to program expense." became "directs 91.1% to programs expense.": right
    number, doubled/garbled noun. Fixed by capturing whatever the noun group
    actually matched and echoing it back, so an unmatched tail like
    " expense" reattaches to whatever was actually there instead of a
    hardcoded plural."""

    def test_program_expense_noun_is_not_doubled(self):
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity directs 50% to program expense."
        out = _sanitize(text, metrics)
        assert out == "The charity directs 91.1% to program expense."

    def test_plain_programs_still_works(self):
        """No-regression check: the ordinary, already-correct "programs"
        (plural, standalone) shape must keep working exactly as before."""
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity directs 50% to programs."
        out = _sanitize(text, metrics)
        assert out == "The charity directs 91.1% to programs."

    def test_programmatic_activities_noun_is_echoed(self):
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity allocates 50% toward programmatic activities."
        out = _sanitize(text, metrics)
        assert out == "The charity directs 91.1% to programmatic activities."

    @pytest.mark.parametrize(
        "text",
        [
            "The charity directs 50% to program expense.",
            "The charity directs 50% to programs.",
            "The charity allocates 50% toward programmatic activities.",
        ],
    )
    def test_program_expense_noun_echo_is_five_pass_stable(self, text):
        metrics = _metrics(program_expense_ratio=0.911)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestWorkingCapitalVerbIsEchoedNotHardcodedToHolds:
    """Task G11: the holds/maintains/has correction rule hardcoded its
    replacement to "holds" regardless of which verb actually matched — a
    real idempotency violation (not just a canonicalization choice), because
    it interacted with Pattern 3's "X years' worth of Y" shape across two
    passes: "The charity has 5 years' worth of operating expenses saved."
    doesn't match this verb-first pattern on pass 1 (the apostrophe blocks
    the noun from sitting immediately after the number, so Pattern 3 catches
    it instead, leaving the leading "has" alone) but DOES match on pass 2
    once Pattern 3 has already normalized the tail to "... of working
    capital" — and the old hardcoded "holds" replacement then silently
    rewrote "has" to "holds" on that second pass, so pass 1's output
    differed from pass 2's even though the number never changed. Fixed by
    capturing and echoing the verb actually matched."""

    def test_has_verb_is_preserved_not_rewritten_to_holds(self):
        metrics = _metrics(working_capital_ratio=8.3)
        text = "The charity has 5 years' worth of operating expenses saved."
        passes = _five_passes(text, metrics)
        assert passes[0] == "The charity has 8.3 months of working capital saved."
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_maintains_verb_is_preserved(self):
        metrics = _metrics(working_capital_ratio=8.3)
        text = "The charity maintains 3.0 months of reserves."
        out = _sanitize(text, metrics)
        assert out == "The charity maintains 8.3 months of working capital."

    def test_holds_verb_still_works(self):
        """No-regression check: the already-covered "holds" shape (the only
        verb the old hardcoded replacement ever matched byte-for-byte) keeps
        working exactly as before."""
        metrics = _metrics(working_capital_ratio=8.3)
        text = "The charity holds 3.0 months of reserves."
        out = _sanitize(text, metrics)
        assert out == "The charity holds 8.3 months of working capital."

    def test_sentence_initial_has_is_still_capitalized(self):
        """`_match_case` still applies: a preceding clause's removal can
        leave this rule sentence-initial, and the echoed verb must still
        pick up the capital, not just fall back to whatever case it was
        originally written in."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = "It scored 87/100 from Charity Navigator, and has 3.0 months of reserves."
        out = _sanitize(text, metrics)
        assert out == "Has 8.3 months of working capital."


# Task G12: four defects found by an adversarial probe of
# `sanitize_narrative_metrics`, all in the same clause-scoped-removal
# machinery task G6-G11 built up (`_clause_lead`/`_clause_trail`/
# `_decimal_safe`/`_repair_removal_artifacts`). Three destroy true, cited
# financial facts; the fourth is a latent capitalization gap.
class TestThousandsSeparatorCommaIsNotAClauseBoundary:
    """Defects 1 & 2: a thousands comma ("$141,261", "4,000 families") was
    treated as a clause boundary by `_clause_lead`/`_clause_trail` — the same
    defect shape `_decimal_safe` was written for originally (a digit-
    sandwiched decimal point mistaken for a *sentence* boundary), just never
    mirrored onto the comma exclusion that guards *clause* boundaries.
    `(?<=\\d),(?=\\d)` closes it, the same lookaround idiom already used for
    the decimal point."""

    def test_true_number_survives_a_semicolon_clause_boundary(self):
        """Defect 2's exact repro: the true beneficiary count used to be
        destroyed down to "The charity has 4." because `_clause_lead`'s
        leading scan was blocked at the thousands comma and found a later
        valid start right at that comma, swallowing everything after it —
        including the "000" and the whole fabricated CN-score clause."""
        metrics = _metrics(cn_overall_score=None)
        text = "The charity has 4,000 beneficiaries; it also scored 87/100 on Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "The charity has 4,000 beneficiaries."

    def test_true_number_with_thousands_comma_leads_the_whole_string(self):
        """The thousands comma sits at the very start of the string this
        time (not mid-sentence) — a different position for the same trap."""
        metrics = _metrics(cn_overall_score=None)
        text = "4,000 families were served; it also scored 87/100 on Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "4,000 families were served."

    def test_thousands_comma_inside_the_fabricated_claim_is_fully_removed(self):
        """The comma sandwiched between digits sits *inside* the fabricated
        claim's own number this time. It must not confuse the removal into
        stopping early (leaving a fragment) or matching too little."""
        metrics = _metrics(fundraising_expenses=None)
        text = "The charity reports a $1,234.00 per $1 raised inefficiency, which is a red flag."
        out = _sanitize(text, metrics)
        assert out == "Which is a red flag."

    def test_several_thousands_commas_in_one_sentence_all_survive(self):
        """Two independent true facts, each with their own thousands-comma
        number, sit on either side of one fabricated claim joined by "and"
        and a trailing comma. Both numbers must survive exactly; only the
        fabricated fundraising claim goes."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = (
            "Total revenue was $141,261 and it served 4,000 people, "
            "but fundraising efficiency was $0.00 per $1 raised."
        )
        out = _sanitize(text, metrics)
        assert out == "Total revenue was $141,261 and it served 4,000 people."

    def test_combined_thousands_comma_and_decimal_point_survives_intact(self):
        """$1,250,000.50 — two thousands commas AND a decimal point in one
        number, all digit-sandwiched. Every one of the three punctuation
        marks must be recognized as "not a boundary" for the true clause to
        survive byte-exact."""
        metrics = _metrics(cn_overall_score=None)
        text = (
            "The organization manages $1,250,000.50 in total assets; "
            "it also scored 87/100 on Charity Navigator."
        )
        out = _sanitize(text, metrics)
        assert out == "The organization manages $1,250,000.50 in total assets."

    @pytest.mark.parametrize(
        "text,overrides",
        [
            (
                "The charity has 4,000 beneficiaries; it also scored 87/100 on Charity Navigator.",
                dict(cn_overall_score=None),
            ),
            (
                "4,000 families were served; it also scored 87/100 on Charity Navigator.",
                dict(cn_overall_score=None),
            ),
            (
                "The charity reports a $1,234.00 per $1 raised inefficiency, which is a red flag.",
                dict(fundraising_expenses=None),
            ),
            (
                "Total revenue was $141,261 and it served 4,000 people, "
                "but fundraising efficiency was $0.00 per $1 raised.",
                dict(total_revenue=141_261, fundraising_expenses=None),
            ),
            (
                "The organization manages $1,250,000.50 in total assets; "
                "it also scored 87/100 on Charity Navigator.",
                dict(cn_overall_score=None),
            ),
        ],
    )
    def test_thousands_comma_cases_are_five_pass_stable(self, text, overrides):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestFundraisingDollarFigureDoesNotBindToAnUnrelatedTrueNumber:
    """Defect 1's actual mechanism, distinct from the boundary-scan fix
    above: the null-fundraising removal's own core (`\\$\\d+\\.?\\d*`) can match
    a truncated PREFIX of an unrelated true dollar figure elsewhere in the
    sentence (its `\\d+` simply stops at that number's own thousands comma —
    e.g. grabbing "$141" out of "$141,261"), and the permissive
    "co-occurrence within one sentence" gap between the number and the
    phrase then bridges straight across " and " to reach "fundraising
    efficiency" — bringing the true revenue clause along with it.

    Fixed with a fundraising-specific gap (`_fr_gap`) that additionally
    excludes a bare " and ", *not* by tightening the shared `_decimal_safe`
    — an existing, deliberately-pinned test
    (`TestClauseTrailBareAndBoundary.
    test_and_inside_the_removed_claims_own_cooccurrence_gap_is_unaffected`)
    relies on `_decimal_safe` tolerating "and" inside a claim's own
    phrasing for the CN/accountability/financial rules, none of which
    anchor on a truncatable `$` number and so were never exposed to this
    defect in the first place."""

    def test_leading_true_dollar_figure_with_thousands_comma_survives(self):
        """The brief's own repro, verbatim."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = (
            "Total revenue was $141,261 and fundraising efficiency was "
            "$0.00 per $1 raised, but filings are delayed."
        )
        out = _sanitize(text, metrics)
        assert out == "Total revenue was $141,261, but filings are delayed."

    def test_trailing_dollar_anchor_does_not_reach_across_and_for_an_unrelated_number(self):
        """Mirrors the leading-side defect onto the *other* null-fundraising
        rule (fixed phrase first, bare `$` number second, `_fr_gap` again):
        pre-fix, this rule's own `\\$\\d+(?:\\.\\d+)?` reached forward across
        an "and" to bind to an unrelated true revenue figure, truncating it
        at its own thousands comma ("...total revenue reached $141,261 this
        year." -> "261 this year." — verified against unmodified HEAD).
        There is no actual number attached to "fundraising efficiency" here
        (the LLM only named the concept), so once the "and" correctly blocks
        the reach, nothing is left to remove and the whole sentence must
        survive untouched."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "Fundraising efficiency was mentioned and total revenue reached $141,261 this year."
        out = _sanitize(text, metrics)
        assert out == text

    def test_and_inside_one_cn_claims_own_phrasing_is_still_unaffected(self):
        """No-regression check: `_fr_gap`'s "and"-exclusion is scoped to the
        two fundraising rules only. The shared `_decimal_safe` used by the
        CN/accountability/financial rules must still tolerate a bare "and"
        *inside* one fabricated claim's own phrasing, exactly as
        task G7 pinned it."""
        metrics = _metrics(cn_overall_score=None)
        text = "Charity Navigator rated it 82 and awarded 87/100 and serves 500 clients."
        out = _sanitize(text, metrics)
        assert out == "Serves 500 clients."

    @pytest.mark.parametrize(
        "text",
        [
            "Total revenue was $141,261 and fundraising efficiency was "
            "$0.00 per $1 raised, but filings are delayed.",
            "Fundraising efficiency was mentioned and total revenue reached "
            "$141,261 this year.",
        ],
    )
    def test_dollar_figure_truncation_cases_are_five_pass_stable(self, text):
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


# Defect 3: semicolon, colon, question mark, and exclamation mark were
# admitted freely by `_clause_lead`/`_clause_trail`'s character classes, so a
# removal ran straight through a genuine independent-clause separator (or,
# for `?`/`!`, straight across what is really the end of the PRECEDING true
# sentence). All four are unambiguous — they separate independent clauses by
# definition — so, unlike the bare comma, they get no appositive-continuation
# exception: always a boundary, both directions.
_FOUR_UNAMBIGUOUS_JOINER_CASES = [
    (
        "semicolon_fabricated_leads",
        "It scored 87/100 on Charity Navigator; it also holds 8.3 months of working capital.",
        "It also holds 8.3 months of working capital.",
    ),
    (
        "semicolon_true_leads",
        "It holds 8.3 months of working capital; it also scored 87/100 on Charity Navigator.",
        "It holds 8.3 months of working capital.",
    ),
    (
        "colon_fabricated_leads",
        "It scored 87/100 on Charity Navigator: it also holds 8.3 months of working capital.",
        "It also holds 8.3 months of working capital.",
    ),
    (
        "colon_true_leads",
        "It holds 8.3 months of working capital: it also scored 87/100 on Charity Navigator.",
        "It holds 8.3 months of working capital.",
    ),
    (
        "question_mark_fabricated_leads",
        "Did it score 87/100 on Charity Navigator? It also holds 8.3 months of working capital.",
        "It also holds 8.3 months of working capital.",
    ),
    (
        "question_mark_true_leads",
        "Is the working capital position strong? It also scored 87/100 on Charity Navigator.",
        "Is the working capital position strong?",
    ),
    (
        "exclamation_mark_fabricated_leads",
        "It scored 87/100 on Charity Navigator! It also holds 8.3 months of working capital.",
        "It also holds 8.3 months of working capital.",
    ),
    (
        "exclamation_mark_true_leads",
        "The working capital position is excellent! It also scored 87/100 on Charity Navigator.",
        "The working capital position is excellent!",
    ),
]


class TestFourUnambiguousJoinersAreNowClauseBoundaries:
    """Defect 3 (four of the five joiners — em dash is its own class below,
    since it isn't unambiguous). Both polarities per joiner, per the brief:
    a true clause on the far side of the joiner survives in full, and a
    fabricated claim genuinely spanning the joiner is removed in full with
    no surviving fragment that still asserts the metric."""

    @pytest.mark.parametrize(
        "name,text,expected", _FOUR_UNAMBIGUOUS_JOINER_CASES,
        ids=[n for n, *_ in _FOUR_UNAMBIGUOUS_JOINER_CASES])
    def test_joiner_boundary_both_polarities(self, name, text, expected):
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,expected", _FOUR_UNAMBIGUOUS_JOINER_CASES,
        ids=[n for n, *_ in _FOUR_UNAMBIGUOUS_JOINER_CASES])
    def test_joiner_boundary_cases_are_five_pass_stable(self, name, text, expected):
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected


class TestEmDashGetsTheSameAppositiveVsClauseTreatmentAsABareComma:
    """Defect 3's fifth joiner, and the doubtful one (the brief's own
    framing): an em dash introduces an appositive of the SAME claim about as
    often as it introduces a genuine independent clause
    ("scored 87/100 — its best result yet" vs. "scored 87/100 — it also
    holds 8.3 months of working capital"). Tested both readings before
    choosing:

    - Making it an unconditional boundary strands a fabrication-referencing
      appositive behind ("A great achievement!" — still about a score that
      no longer exists — a surviving fabrication-adjacent fragment, the
      worse failure mode per the standing tie-break).
    - Making it an unconditional continuation instead risks swallowing a
      genuine independent clause that just happens to be dash-joined
      instead of semicolon-joined.

    Resolved by giving the em dash the exact same context-sensitive
    treatment already built for the bare comma — reusing
    `_trail_same_claim_lead` rather than inventing a second mechanism, since
    the same question (does what follows read as an appositive of the same
    claim, or as its own clause?) is what actually distinguishes the two
    cases for a dash exactly as it does for a comma."""

    def test_appositive_of_the_fabricated_claim_is_removed_in_full(self):
        """The brief's own em-dash repro: the appositive ("a great
        achievement") is commentary ABOUT the fabricated score, not an
        independent fact, so over-removing it is correct — nothing survives
        that still references the fabricated score."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = (
            "It scored 87/100 on Charity Navigator — a great achievement! "
            "It also holds 8.3 months of working capital."
        )
        out = _sanitize(text, metrics)
        assert out == "It also holds 8.3 months of working capital."

    def test_genuine_independent_clause_after_the_dash_survives(self):
        """No appositive lead here ("it also holds...") — `_trail_same_claim_lead`
        doesn't recognize it, so the dash is a hard boundary and the true
        clause after it survives, cleanly repunctuated."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = "It scored 87/100 on Charity Navigator — it also holds 8.3 months of working capital."
        out = _sanitize(text, metrics)
        assert out == "It also holds 8.3 months of working capital."

    def test_true_clause_survives_when_the_dash_leads_into_the_fabricated_one(self):
        """The mirrored, leading-edge polarity: a true clause sits BEFORE an
        em-dash-joined fabricated one. Also confirms the leading space
        conventional before an em dash ("capital — it") is consumed cleanly,
        with no stray space left in front of the surviving clause's own
        terminal period."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = "It holds 8.3 months of working capital — it also scored 87/100 on Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "It holds 8.3 months of working capital."

    def test_true_clause_with_its_own_appositive_before_the_dash_survives_whole(self):
        """The true clause's own comma-led appositive (", and rising") must
        not be mistaken for a boundary either — only the em dash further
        along is."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = (
            "It holds 8.3 months of working capital, and rising — "
            "it also scored 87/100 on Charity Navigator."
        )
        out = _sanitize(text, metrics)
        assert out == "It holds 8.3 months of working capital, and rising."

    @pytest.mark.parametrize(
        "text,expected",
        [
            (
                "It scored 87/100 on Charity Navigator — a great achievement! "
                "It also holds 8.3 months of working capital.",
                "It also holds 8.3 months of working capital.",
            ),
            (
                "It scored 87/100 on Charity Navigator — it also holds 8.3 months of working capital.",
                "It also holds 8.3 months of working capital.",
            ),
            (
                "It holds 8.3 months of working capital — it also scored 87/100 on Charity Navigator.",
                "It holds 8.3 months of working capital.",
            ),
            (
                "It holds 8.3 months of working capital, and rising — "
                "it also scored 87/100 on Charity Navigator.",
                "It holds 8.3 months of working capital, and rising.",
            ),
        ],
    )
    def test_em_dash_cases_are_five_pass_stable(self, text, expected):
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected


class TestCapitalizationRepairSeesThroughCitationMarkup:
    """Defect 4 (latent): `_repair_removal_artifacts`'s capitalization regex
    expected a letter immediately at the sentence boundary and found `<`
    instead whenever a removal left a surviving clause's own `<cite
    id="...">` wrapper sentence-initial, silently leaving the visible word
    lowercase. Zero live instances when found (needs one unlucky clause
    ordering), but `<cite>` markup appears in all 166 published files."""

    def test_cite_tag_immediately_after_a_removed_clause_is_still_capitalized(self):
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = (
            'The charity <cite id="1">scored 87/100 on Charity Navigator</cite> '
            'and <cite id="2">holds 8.3 months of working capital</cite>.'
        )
        out = _sanitize(text, metrics)
        assert out == '<cite id="2">Holds 8.3 months of working capital</cite>.'

    def test_cite_tag_capitalization_is_five_pass_stable(self):
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = (
            'The charity <cite id="1">scored 87/100 on Charity Navigator</cite> '
            'and <cite id="2">holds 8.3 months of working capital</cite>.'
        )
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]
        assert passes[0] == '<cite id="2">Holds 8.3 months of working capital</cite>.'

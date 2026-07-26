"""H4: baseline prompt unification — drift guard between template and call site."""

import re
from string import Formatter
from types import SimpleNamespace

import pytest
from baseline import _baseline_prompt_kwargs, build_baseline_prompt, sanitize_narrative_metrics
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
    reproduction of the hazard `_match_case` guards against."""

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

    def test_spends_on_programs_with_real_ratio_survives_unremoved(self):
        """'spends X% on programs' has no correction-side rule of its own (a
        pre-existing, separately-scoped gap); the new removal rule must stay
        gated strictly behind the null branch and leave this text alone."""
        metrics = _metrics(program_expense_ratio=0.911)
        text = "The charity spends 45.0% on programs."
        out = _sanitize(text, metrics)
        assert out == text

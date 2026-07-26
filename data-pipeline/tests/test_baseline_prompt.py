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
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
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

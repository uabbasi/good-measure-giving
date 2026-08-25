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
        impact=SimpleNamespace(score=37, cost_per_beneficiary=907),
        alignment=SimpleNamespace(score=44, muslim_donor_fit_level="STRONG", cause_urgency_label="HIGH"),
        data_confidence=SimpleNamespace(overall=0.8, badge="HIGH"),
    )


def test_baseline_prompt_file_is_v2():
    info = load_prompt("baseline_narrative", check_version=False)
    assert info.version == "2.7.0"
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
    assert info.version == "2.7.0"
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
            total_contributions=100000,
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
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759, total_contributions=604759,
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
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759, total_contributions=604759,
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
        metrics = SimpleNamespace(fundraising_expenses=30000, total_revenue=600000, total_contributions=600000,
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
        sample_charity_metrics.total_contributions = 79_600_000
        kwargs = _baseline_prompt_kwargs(sample_charity_metrics, _fake_scores(), 3, "[1] Charity Navigator")
        assert kwargs["fundraising_efficiency"] == "<$0.01 per $1 raised"

    def test_tiny_ratio_string_survives_the_sanitizer(self):
        """The new "<$0.01 per $1 raised" text must not get stripped by the
        null-fundraising removal rules in sanitize_narrative_metrics, and must
        not be clobbered back to "$0.00" by the sanitizer's own correction path
        (a second, independent reimplementation of this same ratio)."""
        metrics = SimpleNamespace(fundraising_expenses=241666, total_revenue=79_600_000, total_contributions=79_600_000,
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
        metrics = SimpleNamespace(fundraising_expenses=241666, total_revenue=79_600_000, total_contributions=79_600_000,
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
        metrics = SimpleNamespace(fundraising_expenses=241666, total_revenue=79_600_000, total_contributions=79_600_000,
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
        total_contributions=100000,
        total_revenue=100_000,
        founded_year=None,
    )
    base.update(overrides)
    # Same as above: these fixtures use revenue as 'the denominator'.
    if "total_revenue" in overrides and "total_contributions" not in overrides:
        base["total_contributions"] = overrides["total_revenue"]
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
    """Task G15 reversed the determiner-consumption behavior these tests
    originally pinned: "a perfect score from Charity Navigator, its highest
    rating" is one fabricated claim with an appositive tail, but consuming
    determiner-led text after a bare comma to erase that tail also erased
    ordinary true independent clauses whose subjects begin with "the"/"its"/
    "an" — the determiner test can't tell the two apart, because it
    identifies a noun phrase, not an appositive. What must never regress is
    that the fabricated NUMBER itself is gone — that's still true here. What
    used to also be true, and no longer is by deliberate choice, is that the
    appositive tail vanished with it; it now strands as its own fragment
    instead."""

    def test_fabricated_score_is_removed_appositive_tail_now_strands(self):
        text = "The charity earned a perfect score from Charity Navigator, its highest rating."
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == "Its highest rating."
        assert "Charity Navigator" not in out
        assert "87" not in out

    def test_true_clause_survives_fabricated_score_removed_appositive_tail_strands(self):
        """A true claim in front of the fabricated one must survive in
        full, and the fabricated claim itself (the score, "Charity
        Navigator") must be gone. Task G15: the appositive tail after it no
        longer goes with it — it strands, joined to the true clause by the
        comma that was already there."""
        text = (
            "The charity spends $0.10 per $1 raised, and earned a perfect score "
            "from Charity Navigator, its highest rating."
        )
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == "The charity spends $0.10 per $1 raised, its highest rating."
        assert "Charity Navigator" not in out
        assert "perfect score" not in out

    def test_appositive_case_is_idempotent(self):
        text = "The charity earned a perfect score from Charity Navigator, its highest rating."
        metrics = _metrics(cn_overall_score=None)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once == "Its highest rating."


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

    def test_appositive_tail_now_strands_after_the_fabricated_score_is_removed(self):
        """Task G15 reversed this: the appositive tail ("its highest
        rating") opens with a determiner, exactly like the subject of an
        ordinary true clause does, so treating a determiner as "same claim,
        keep consuming" also erased true clauses that happened to be
        phrased that way. The fabricated score itself must still be gone;
        the appositive tail is no longer swallowed with it."""
        metrics = _metrics(cn_overall_score=None)
        text = "The charity earned a perfect score from Charity Navigator, its highest rating."
        out = _sanitize(text, metrics)
        assert out == "Its highest rating."
        assert "Charity Navigator" not in out

    def test_second_appositive_phrasing_now_strands(self):
        """Same reversal, a determiner+adjective+noun appositive ("a strong
        reserve position") rather than a possessive pronoun. The fabricated
        working-capital figure is gone; the appositive strands instead of
        being consumed."""
        metrics = _metrics(working_capital_ratio=None)
        text = "The charity holds 4.2 months of working capital, a strong reserve position."
        out = _sanitize(text, metrics)
        assert out == "A strong reserve position."
        assert "4.2" not in out


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
# these open with a determiner or quantifier. Task G15 dropped the
# determiner/quantifier branch from `_clause_trail`'s continuation set (it
# was indistinguishable from an ordinary true-clause subject), so these two
# no longer get swallowed with the fabricated claim in front of them — they
# strand as their own fragment instead. What must still hold is that the
# fabricated number/claim itself is gone (`absent`, checked in the text
# that survives).
_CLOSED_CLASS_APPOSITIVES = [
    ("the_best_in_its_class",
     "The charity holds 4.2 months of working capital, the best in its class.",
     "The best in its class.", "4.2"),
    ("one_of_the_highest",
     "The charity scored 87/100 from Charity Navigator, one of the highest in its cohort.",
     "One of the highest in its cohort.", "Charity Navigator"),
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

    @pytest.mark.parametrize(
        "name,text,expected,absent", _CLOSED_CLASS_APPOSITIVES,
        ids=[n for n, *_ in _CLOSED_CLASS_APPOSITIVES])
    def test_closed_class_appositive_now_strands_fabricated_claim_still_gone(
        self, name, text, expected, absent
    ):
        """Task G15 reversal: these are determiner/quantifier leads, so they
        no longer get swallowed with the fabricated claim in front of them.
        The fabricated claim itself must still be gone."""
        metrics = _metrics(working_capital_ratio=None, cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == expected
        assert absent not in out

    @pytest.mark.parametrize(
        "name,text,expected,absent", _CLOSED_CLASS_APPOSITIVES,
        ids=[n for n, *_ in _CLOSED_CLASS_APPOSITIVES])
    def test_closed_class_appositive_case_is_idempotent(self, name, text, expected, absent):
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
        ],
    )
    def test_live_malformed_narratives_are_left_untouched_pending_regeneration(self, ein, overrides, text):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == text, f"{ein}: malformed narrative should be left untouched, not repaired in place"

    def test_36_3673599_malformed_text_is_removed_because_its_subscore_is_unpublishable(self):
        """REVERSAL of this class's "left untouched" expectation for this one
        EIN (Task G20). The other two EINs above keep it.

        36-3673599's accountability value is 85.99555863262657 — a weighted
        mean this pipeline computes over CN's sub-areas, not a number Charity
        Navigator publishes (their beacon is read with an integer-only regex).
        G20 treats such a value as absent, so the null branch strips the claim
        rather than restating it "from Charity Navigator".

        This class's actual invariant — a malformed multi-decimal number is
        never SPLICED with a new value — still holds: removing is not
        splicing. And removing beats the previous outcome, which shipped the
        malformed "96.96.0/100" to donors verbatim.
        """
        metrics = _metrics(
            cn_accountability_score=85.99555863262657, cn_overall_score=96, cn_financial_score=85.99555863262657
        )
        text = "Strong external accountability rating of 96.96.0/100 from Charity Navigator"
        assert _sanitize(text, metrics) == ""

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

    def test_36_3673599_once_regenerated_drops_the_claim_rather_than_citing_a_computed_score(self):
        """REVERSAL of the G8-era expectation for this EIN (Task G20).

        This previously asserted the claim was rewritten to "86.0/100 from
        Charity Navigator" — publishing OUR weighted mean over CN's sub-areas
        under CN's name, a figure they never stated. The two sibling tests
        above keep their corrections because their values (100, 92) are real
        published beacons.

        Removal, not correction, is the fail-safe outcome the function's
        governing tradeoff already prefers: better to drop an attributable
        claim we cannot back than to assert a sourced-looking number we
        invented the label for.
        """
        metrics = _metrics(
            cn_accountability_score=85.99555863262657, cn_overall_score=96, cn_financial_score=85.99555863262657
        )
        text = "Strong external accountability rating of 96/100 from Charity Navigator"
        assert _sanitize(text, metrics) == ""


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


class TestFundraisingBareCommaBindsToNearestDollarFigure:
    """Gap 1 left open by the task above: excluding "and" from `_fr_gap`
    stops the reach when the two clauses are "and"-joined, but a BARE COMMA
    joining them exposes the identical mechanism. `\\$\\d+\\.?\\d*` matches a
    truncated prefix of any dollar figure in the sentence (stopping at that
    number's own thousands comma), and because `_fr_gap*` is greedy, the
    regex engine tries the longest possible gap first and only backtracks
    from the end of the string — so, left unguarded, it binds to whichever
    `$` figure is FARTHEST away that still lets the whole pattern match, not
    the nearest one. Fixed by excluding the literal `$` from `_fr_gap`'s
    character class, so the gap can never be consumed past any dollar sign:
    the core can only ever bind to the nearest one."""

    def test_leading_null_fundraising_no_longer_reaches_across_a_comma_to_a_true_figure(self):
        """The exact destructive case: no "and" at all, just a bare comma.
        Pre-fix this reached across the adjacent "$0.00" to bind to
        "$141,261" instead, truncating it to "$141" and destroying the
        entire true revenue clause."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "Fundraising efficiency was $0.00, total revenue reached $141,261 this year."
        out = _sanitize(text, metrics)
        assert out == "Total revenue reached $141,261 this year."

    def test_leading_null_fundraising_with_per_dollar_phrasing_still_binds_correctly(self):
        """Same shape, but the fundraising claim carries its own anchoring
        phrase ("per $1 raised") ahead of the comma — confirms the fix
        doesn't depend on that phrasing being absent."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = (
            "Fundraising efficiency was $0.00 per $1 raised, total revenue "
            "reached $141,261 this year."
        )
        out = _sanitize(text, metrics)
        assert out == "Total revenue reached $141,261 this year."

    def test_every_real_hallucination_still_strips_with_the_dollar_exclusion(self):
        """Re-verifies the fix against all three of `REAL_HALLUCINATIONS`
        (see `TestFundraisingClaimIsStrippedWhenDataIsMissing`): none of
        them require the gap to cross a second `$` sign to find the
        hallucinated one, so excluding `$` from `_fr_gap` must not stop any
        of them from being stripped."""
        real_hallucinations = [
            "Exceptional fundraising efficiency of $0.00 spent per $1 raised [1].",
            "Operates with high fundraising efficiency, spending $0.00 to raise every $1 in FY2025.",
            "The charity has a 91.1% program expense ratio, and a $0.00 fundraising efficiency rate.",
        ]
        metrics = _metrics(fundraising_expenses=None, total_revenue=604_759,
                            cn_overall_score=None, cn_accountability_score=None,
                            cn_financial_score=None, program_expense_ratio=0.911,
                            working_capital_ratio=None)
        for text in real_hallucinations:
            out = _sanitize(text, metrics)
            assert "$0.00" not in out, f"not stripped: {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "Fundraising efficiency was $0.00, total revenue reached $141,261 this year.",
            "Fundraising efficiency was $0.00 per $1 raised, total revenue reached "
            "$141,261 this year.",
        ],
    )
    def test_bare_comma_cases_are_five_pass_stable(self, text):
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestDollarFirstRuleDoesNotAnchorOnATrueFigureAcrossABareComma:
    """Gap 1, round 2: excluding `$` from `_fr_gap` stops the rule from
    reaching PAST an adjacent `$0.00` to a farther true figure, but it
    doesn't stop the *dollar-first* rule's own core (`\\$\\d+\\.?\\d*` followed
    by the literal "fundraising efficiency") from anchoring directly on a
    true dollar figure in the first place — no second `$` needs crossing,
    since the rule's suffix is satisfied by the bare words "fundraising
    efficiency" with no number of its own required. A bare comma (no "and")
    joining a true dollar clause to any mention of "fundraising efficiency"
    destroyed the true clause even when nothing resembling a hallucinated
    value was present at all.

    Fixed by giving the dollar-first rule its own gap
    (`_fr_gap_dollar_first`) that additionally treats a bare (non-thousands)
    comma as a boundary — mirroring `_clause_lead`/`_clause_trail`'s own
    digit-sandwich exception. The *phrase*-first rule keeps the original
    `_fr_gap`, unchanged: its anchor is the unambiguous literal "fundraising
    efficiency", which a true dollar figure can never masquerade as, and the
    real, pinned hallucination ("high fundraising efficiency, spending
    $0.00...") needs its own gap to cross exactly that kind of bare comma.

    An UNCONDITIONAL bare-comma boundary on the dollar-first gap was tried
    first and rejected: hand-probing found it reopens a false negative for a
    genuine, natural two-sided fabrication — "The charity spent $0.00, an
    indication of poor fundraising efficiency." (the SAME $0.00 figure,
    commented on across the comma) went unstripped. So `_fr_gap_dollar_first`
    instead reuses `_trail_same_claim_lead` (the exact same appositive-vs-
    independent-clause question `_clause_trail` already answers): a bare
    comma is a boundary UNLESS what follows opens with a determiner/
    possessive/comparative lead-in, in which case it's still the same claim.
    This closes the determiner-led hallucination shape while still blocking
    both true-fact cases above. It does NOT close a gerund-led continuation
    of the same claim ("$0.00, reflecting strong fundraising efficiency") —
    see `test_gerund_led_appositive_of_the_same_figure_is_a_known_residual_gap`
    below — for the same reason `_trail_same_claim_lead` was never given a
    verb list: the set of participles that can lead a same-claim appositive
    is exactly as unbounded as the set of verbs that can lead an independent
    clause. Reported as a known gap rather than forced further."""

    @pytest.mark.parametrize(
        "text",
        [
            "Total revenue was $141,261, fundraising efficiency was mentioned.",
            "Total revenue was $141,261, though fundraising efficiency could not "
            "be determined.",
        ],
    )
    def test_true_dollar_figure_survives_a_bare_comma_into_a_bare_mention(self, text):
        """No hallucinated value anywhere in these sentences at all — the
        bare mention of "fundraising efficiency" alone must not detonate
        the null-fundraising rule against an unrelated true dollar figure."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        out = _sanitize(text, metrics)
        assert out == text

    def test_and_joined_variant_still_survives_no_regression(self):
        """The "and"-joined sibling of the bare-comma case above, already
        fixed by the "and" exclusion — re-asserted here since it shares this
        test class's fixture and framing."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "Total revenue was $141,261, and fundraising efficiency data is unavailable."
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text",
        [
            "The charity spent $0.00, an indication of poor fundraising efficiency.",
            "The organization reported $0.00 in costs, a sign of excellent "
            "fundraising efficiency.",
        ],
    )
    def test_determiner_led_appositive_of_the_same_figure_still_strips(self, text):
        """A bare comma joining $0.00 to a determiner-led appositive
        ("an indication of...", "a sign of...") is a genuine, natural
        two-sided fabrication about the SAME figure — an unconditional
        bare-comma boundary would have left this unstripped (verified
        against a monkeypatched unconditional-boundary version before
        choosing the `_trail_same_claim_lead` reuse instead). Must still be
        fully removed, same as the pinned `REAL_HALLUCINATIONS` cases."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        out = _sanitize(text, metrics)
        assert "$0.00" not in out

    def test_gerund_led_appositive_of_the_same_figure_is_a_known_residual_gap(self):
        """Documents, rather than hides, the one shape `_trail_same_claim_lead`
        reuse does not close: a gerund-led continuation of the same claim
        ("reflecting...") is indistinguishable in shape from an independent
        clause, for the same reason `_trail_same_claim_lead` was never given
        a verb/participle list. This assertion pins the CURRENT (imperfect)
        behavior so a future change to this shape is a deliberate decision,
        not a silent regression."""
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "It spent just $0.00, reflecting strong fundraising efficiency."
        out = _sanitize(text, metrics)
        assert out == text  # known gap: the $0.00 hallucination is NOT stripped here

    def test_every_real_hallucination_still_strips_with_the_bare_comma_exclusion(self):
        """Re-verifies all three `REAL_HALLUCINATIONS` once more: the
        phrase-first rule's gap is untouched by this fix, and the third
        entry (dollar-first, "a $0.00 fundraising efficiency rate") has no
        comma at all between the dollar figure and the phrase, so neither
        is affected by the new boundary."""
        real_hallucinations = [
            "Exceptional fundraising efficiency of $0.00 spent per $1 raised [1].",
            "Operates with high fundraising efficiency, spending $0.00 to raise every $1 in FY2025.",
            "The charity has a 91.1% program expense ratio, and a $0.00 fundraising efficiency rate.",
        ]
        metrics = _metrics(fundraising_expenses=None, total_revenue=604_759,
                            cn_overall_score=None, cn_accountability_score=None,
                            cn_financial_score=None, program_expense_ratio=0.911,
                            working_capital_ratio=None)
        for text in real_hallucinations:
            out = _sanitize(text, metrics)
            assert "$0.00" not in out, f"not stripped: {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "Total revenue was $141,261, fundraising efficiency was mentioned.",
            "Total revenue was $141,261, though fundraising efficiency could not "
            "be determined.",
            "Total revenue was $141,261, and fundraising efficiency data is unavailable.",
        ],
    )
    def test_bare_comma_survival_cases_are_five_pass_stable(self, text):
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    @pytest.mark.parametrize(
        "text",
        [
            "The charity spent $0.00, an indication of poor fundraising efficiency.",
            "The organization reported $0.00 in costs, a sign of excellent "
            "fundraising efficiency.",
            "It spent just $0.00, reflecting strong fundraising efficiency.",
        ],
    )
    def test_determiner_and_gerund_appositive_cases_are_five_pass_stable(self, text):
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
    holds 8.3 months of working capital"). Originally resolved by giving the
    em dash the exact same context-sensitive treatment already built for the
    bare comma — reusing `_trail_same_claim_lead`'s determiner/possessive
    branch, so a determiner-led appositive ("a great achievement") was
    swallowed with the fabricated score in front of it.

    Task G15 reversed that branch for `_clause_trail` (it identifies a noun
    phrase, not an appositive — the same shape opens the subject of an
    ordinary true clause, e.g. "a great achievement" vs. "a great fundraiser
    joined the board"). So the determiner-led em-dash appositive below now
    strands instead of being consumed, exactly like the bare-comma case.
    What must never regress either way: the fabricated score itself is
    gone."""

    def test_appositive_of_the_fabricated_claim_now_strands_score_still_gone(self):
        """The brief's own em-dash repro: the appositive ("a great
        achievement") is a determiner-led noun phrase, the same shape Task
        G15 stopped consuming after `_clause_trail`. It now strands as its
        own sentence; the fabricated score ("87/100 on Charity Navigator")
        must still be gone."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = (
            "It scored 87/100 on Charity Navigator — a great achievement! "
            "It also holds 8.3 months of working capital."
        )
        out = _sanitize(text, metrics)
        assert out == "A great achievement! It also holds 8.3 months of working capital."
        assert "Charity Navigator" not in out
        assert "87" not in out

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
                "A great achievement! It also holds 8.3 months of working capital.",
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


# Gap 2 left open by the task above: `;` and `:` originally reused
# `_trail_same_claim_lead`'s determiner/possessive branch, exactly like the
# em dash and the bare comma, so a determiner/possessive/quantifier-led
# appositive of the fabricated claim in front of it was consumed and removed
# with it. Task G15 dropped that branch from `_clause_trail`'s continuation
# set for the same reason it did everywhere else: a determiner identifies a
# noun phrase, not an appositive, and the same shape opens the subject of a
# true clause. So each of these four now strands as its own fragment instead
# of being consumed. What must never regress: the fabricated score itself
# ("87/100 on Charity Navigator") is gone either way.
_SEMICOLON_COLON_APPOSITIVE_CASES = [
    (
        "semicolon_determiner_appositive",
        "It scored 87/100 on Charity Navigator; a truly remarkable result.",
        "A truly remarkable result.",
    ),
    (
        "colon_determiner_appositive",
        "It scored 87/100 on Charity Navigator: the best in its class.",
        "The best in its class.",
    ),
    (
        "semicolon_possessive_appositive",
        "It scored 87/100 on Charity Navigator; its highest rating.",
        "Its highest rating.",
    ),
    (
        "colon_one_of_appositive",
        "It scored 87/100 on Charity Navigator: one of the highest.",
        "One of the highest.",
    ),
]


class TestSemicolonAndColonGetTheSameAppositiveVsClauseTreatmentAsEmDash:
    """Gap 2: `;` and `:` reuse `_clause_trail_same_claim_lead`, exactly
    like the em dash and the bare comma. Task G15 reversed the determiner/
    possessive/quantifier branch of that continuation set (see the module
    comment above `_SEMICOLON_COLON_APPOSITIVE_CASES`), so a
    determiner-led appositive of the fabricated claim now strands instead of
    being consumed with it — the fabricated score itself must still be
    gone. A genuine independent clause on the far side is untouched by this
    change either way and still survives (already pinned by
    `TestFourUnambiguousJoinersAreNowClauseBoundaries`'s
    `semicolon_true_leads` / `colon_true_leads` / `semicolon_fabricated_leads`
    / `colon_fabricated_leads` cases, re-asserted here as a no-regression
    check)."""

    @pytest.mark.parametrize(
        "name,text,expected", _SEMICOLON_COLON_APPOSITIVE_CASES,
        ids=[n for n, *_ in _SEMICOLON_COLON_APPOSITIVE_CASES])
    def test_appositive_of_the_fabricated_claim_now_strands_score_still_gone(
        self, name, text, expected
    ):
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == expected
        assert "Charity Navigator" not in out
        assert "87" not in out

    @pytest.mark.parametrize(
        "name,text,expected", _SEMICOLON_COLON_APPOSITIVE_CASES,
        ids=[n for n, *_ in _SEMICOLON_COLON_APPOSITIVE_CASES])
    def test_appositive_cases_are_five_pass_stable(self, name, text, expected):
        metrics = _metrics(cn_overall_score=None)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            (
                "It scored 87/100 on Charity Navigator; it also holds 8.3 months of working capital.",
                "It also holds 8.3 months of working capital.",
            ),
            (
                "It holds 8.3 months of working capital; it also scored 87/100 on Charity Navigator.",
                "It holds 8.3 months of working capital.",
            ),
            (
                "It scored 87/100 on Charity Navigator: it also holds 8.3 months of working capital.",
                "It also holds 8.3 months of working capital.",
            ),
            (
                "It holds 8.3 months of working capital: it also scored 87/100 on Charity Navigator.",
                "It holds 8.3 months of working capital.",
            ),
        ],
    )
    def test_independent_clause_still_survives_no_regression(self, text, expected):
        """Re-asserts the gap-3 (task G12) semicolon/colon independent-clause
        cases still pass unchanged now that `;`/`:` have a continuation
        exception — "it" never appears in `_trail_same_claim_lead`, so this
        polarity never reaches the new alternative at all."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        out = _sanitize(text, metrics)
        assert out == expected


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


class TestFoundedYearRemovalWhenNull:
    """Task G13: founded_year had only the correction half of the pair every
    other metric family in this function carries — a null founded_year (no
    filings, a brand-new organization) let a fabricated founding-year claim
    survive verbatim. The removal rules mirror the two correction patterns
    above, clause-scoped like every other null branch, plus a third phrasing
    ("a 1985 organization") that has no correction counterpart."""

    def test_founded_in_alone_is_removed(self):
        text = "It was founded in 1985."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == ""

    def test_established_in_alone_is_removed(self):
        text = "The nonprofit was established in 1990. It serves many families."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == "It serves many families."

    def test_since_phrasing_alone_is_removed(self):
        text = "It has been operating since 1985. It serves many families."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == "It serves many families."

    def test_was_founded_in_phrasing_alone_is_removed(self):
        text = "The charity was founded in 1985. It serves many families."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == "It serves many families."

    def test_a_year_organization_phrasing_alone_is_removed(self):
        text = "This is a 1985 organization. It serves the local community."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == "It serves the local community."

    @pytest.mark.parametrize(
        "text",
        [
            "The organization hosted a 2020 charity gala that raised $50,000 for local families.",
            "It ran a 1999 nonprofit fundraiser to support education.",
            "It partnered with a 2015 charity initiative focused on clean water.",
        ],
    )
    def test_a_year_organization_phrasing_does_not_swallow_a_compound_noun_phrase(self, text):
        """Hand-probe found this: without a trailing boundary requirement,
        "organization"/"nonprofit"/"charity" are common enough nouns to head
        a compound noun phrase that has nothing to do with founding — the
        removal used to swallow the entire sentence in each case (a real
        over-removal, confirmed against the pre-fix version of this rule),
        destroying an unrelated true fact. Must survive untouched."""
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,overrides,expected",
        [
            ("It was founded in 1985.", dict(founded_year=None), ""),
            (
                "It was founded in 1985, and spends $0.10 per $1 raised.",
                dict(founded_year=None),
                "Spends $0.10 per $1 raised.",
            ),
            (
                "The charity spends $0.10 per $1 raised, and was founded in 1985.",
                dict(founded_year=None),
                "The charity spends $0.10 per $1 raised.",
            ),
            (
                "It was founded in 1985, and spends $0.00 per $1 raised.",
                dict(founded_year=None, fundraising_expenses=None),
                "",
            ),
        ],
        ids=["alone", "unsupported_first", "supported_first", "both_unsupported"],
    )
    def test_family_matrix(self, text, overrides, expected):
        """The same alone / unsupported-first / supported-first / both-null
        shape TestRemovalRuleFamilyClauseMatrix already runs for every other
        family, applied to founded_year now that it has a removal half."""
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "text,overrides",
        [
            ("It was founded in 1985.", dict(founded_year=None)),
            ("It was founded in 1985, and spends $0.10 per $1 raised.", dict(founded_year=None)),
            (
                "The charity spends $0.10 per $1 raised, and was founded in 1985.",
                dict(founded_year=None),
            ),
            (
                "It was founded in 1985, and spends $0.00 per $1 raised.",
                dict(founded_year=None, fundraising_expenses=None),
            ),
            ("This is a 1985 organization. It serves the local community.", dict(founded_year=None)),
        ],
    )
    def test_family_matrix_is_idempotent(self, text, overrides):
        metrics = _metrics(**overrides)
        once = _sanitize(text, metrics)
        twice = _sanitize(once, metrics)
        assert twice == once


class TestFoundedYearRemovalDoesNotTouchUnrelatedYears:
    """The main hazard the brief calls out: a four-digit year is
    indistinguishable from any other number, and these narratives are full
    of dates that have nothing to do with founding. None of these anchor
    words ("founded"/"established"/.../"in", "operating"/.../"since", or
    "a YYYY organization") appear adjacent to the year in any of these, so
    the removal rules must never fire on them."""

    def test_beneficiary_count_year_survives(self):
        text = "In 2024 it served 4,000 families across the region."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == text

    def test_fiscal_year_filing_reference_survives(self):
        text = "Its FY2023 filings show a strong balance sheet."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == text

    def test_revenue_growth_years_survive(self):
        text = "Revenue grew through 2022 and 2023."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == text

    def test_unrelated_year_survives_alongside_a_real_removal(self):
        text = "It was founded in 1985. In 2024 it served 4,000 families."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == "In 2024 it served 4,000 families."

    def test_unrelated_years_are_five_pass_stable(self):
        text = "In 2024 it served 4,000 families. Its FY2023 filings show a strong balance sheet."
        metrics = _metrics(founded_year=None)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text


def _sanitize_scores(text, metrics, amal_score, wallet_tag="ZAKAT-ELIGIBLE"):
    scores = SimpleNamespace(wallet_tag=wallet_tag, amal_score=amal_score)
    return sanitize_narrative_metrics({"rationale": text}, metrics, scores)["rationale"]


class TestAmalScoreRemovalWhenNull:
    """Task G13: scores.amal_score had the same only-correction asymmetry as
    founded_year. Null amal_score is the realistic path per the brief — an
    evaluation that failed to score, not a missing scores object entirely —
    but the existing guard (`scores and hasattr(...) and ... is not None`)
    already covers all three falsy shapes uniformly, so the same else branch
    fires whether scores is None, lacks the attribute, or has it as None."""

    def test_number_before_amal_alone_is_removed(self):
        text = "The charity earned a 70/100 AMAL score."
        metrics = _metrics()
        out = _sanitize_scores(text, metrics, amal_score=None)
        assert out == ""

    def test_amal_score_of_x_alone_is_removed(self):
        text = "AMAL score of 70 was calculated. It serves many families."
        metrics = _metrics()
        out = _sanitize_scores(text, metrics, amal_score=None)
        assert out == "It serves many families."

    def test_scored_on_amal_index_alone_is_removed(self):
        text = "This nonprofit scored 70 on the AMAL index. It serves many families."
        metrics = _metrics()
        out = _sanitize_scores(text, metrics, amal_score=None)
        assert out == "It serves many families."

    def test_missing_scores_object_entirely_also_strips(self):
        """scores=None (no evaluation at all) must hit the same else branch
        as an explicit amal_score=None — hasattr/None guard covers both."""
        text = "The charity earned a 70/100 AMAL score."
        metrics = _metrics()
        out = sanitize_narrative_metrics({"rationale": text}, metrics, None)["rationale"]
        assert out == ""

    def test_real_amal_score_number_before_is_still_corrected(self):
        text = "The charity earned a 70/100 AMAL score."
        metrics = _metrics()
        out = _sanitize_scores(text, metrics, amal_score=91)
        assert out == "The charity earned a 91/100 AMAL score."

    def test_real_amal_score_of_x_is_still_corrected(self):
        text = "AMAL score of 70 was calculated for this charity."
        metrics = _metrics()
        out = _sanitize_scores(text, metrics, amal_score=91)
        assert out == "AMAL score of 91/100 was calculated for this charity."

    def test_amal_removal_exposes_founded_year_correction_sentence_initially(self):
        """AMAL's rules run earlier in the internal rules list than
        founded_year's — the same Critical-1-shaped composition prior tasks
        in this series found broken elsewhere: an earlier removal can leave
        a later correction's target sentence-initial and capitalized."""
        text = "The charity earned a 70/100 AMAL score, and founded in 1980."
        metrics = _metrics(founded_year=1985)
        out = _sanitize_scores(text, metrics, amal_score=None)
        assert out == "Founded in 1985."

    def test_amal_removal_founded_year_correction_composition_is_idempotent(self):
        text = "The charity earned a 70/100 AMAL score, and founded in 1980."
        metrics = _metrics(founded_year=1985)
        once = _sanitize_scores(text, metrics, amal_score=None)
        twice = _sanitize_scores(once, metrics, amal_score=None)
        assert twice == once

    @pytest.mark.parametrize(
        "text",
        [
            "The charity earned a 70/100 AMAL score.",
            "AMAL score of 70 was calculated. It serves many families.",
            "This nonprofit scored 70 on the AMAL index. It serves many families.",
        ],
    )
    def test_removal_is_five_pass_stable(self, text):
        metrics = _metrics()
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize_scores(passes[-1], metrics, amal_score=None))
        assert passes[1] == passes[2] == passes[3] == passes[4] == passes[5]


# Task G14: every correction/removal rule below anchors its number to one
# specific word directly in front of it ("of", "in", "since", "a",
# "directs", "spends", "scored") with nothing tolerated in between. A hedge
# phrase ("roughly", "nearly", "only", "approximately", "an impressive", "a
# mere") sitting between that word and the number defeated the anchor
# entirely across six of the eight metric families this function handles
# (working capital and fundraising are immune — they anchor on a noun/`$`
# rather than a single word, so this task doesn't touch either). Three
# distinct failure modes, all from the same root cause:
#   1. The worst: a sub-score claim (accountability/financial) gets the
#      *overall* score's value stamped into it, because `_sub_score_lead_re`
#      itself used the same defeated anchor and so failed to recognize the
#      claim as a sub-score at all — this is what let the generic overall
#      rule claim and mislabel it.
#   2. A null metric survives as a clean-looking fabrication (the removal
#      rule's anchor is defeated, so it never matches, so nothing is
#      stripped).
#   3. A real-but-wrong number survives uncorrected (the correction rule's
#      anchor is defeated the same way).
#
# Fixed with `_hedge_gap` in baseline.py: a bounded run of up to
# `_hedge_max_words` bare words, blocked from ever consuming a digit or a
# word from this function's own closed set of metric nouns (so a
# permissive gap can never reach PAST its own metric's number to one
# belonging to a different metric — the same technique a prior task used
# to stop the fundraising gap from reaching a farther "$").
def _sanitize_amal(text, metrics, amal_score, wallet_tag="ZAKAT-ELIGIBLE"):
    return _sanitize_scores(text, metrics, amal_score, wallet_tag)


class TestHedgeWordGapCnOverallScore:
    """`_hedge_gap` closes the gap for the CN overall score family: the
    "Charity Navigator score/rating of X" correction pattern and the
    "scored X ... Charity Navigator" removal pattern both anchored the
    number directly to the preceding word, with no hedge tolerated."""

    def test_null_hedged_claim_is_removed(self):
        text = "It scored a truly remarkable 87 out of 100 from Charity Navigator. It serves many families."
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics)
        assert out == "It serves many families."

    def test_wrong_hedged_number_is_corrected(self):
        """Note: the trailing "." is consumed by the match here (`\\d+\\.?\\d*`
        reads it as a would-be decimal point with nothing after it) and
        does not survive in the output — confirmed pre-existing,
        independent of the hedge fix: unhedged "Charity Navigator score of
        60." on unmodified `771f51d` produces the same missing period.
        Out of scope for this task; pinned as-is, not fixed here."""
        text = "Charity Navigator score of roughly 60."
        metrics = _metrics(cn_overall_score=94.0)
        out = _sanitize(text, metrics)
        assert out == "Charity Navigator score of 94.0/100"

    def test_right_unhedged_number_survives_unchanged(self):
        text = "Charity Navigator score of 94.0/100."
        metrics = _metrics(cn_overall_score=94.0)
        out = _sanitize(text, metrics)
        assert out == text

    def test_right_hedged_number_has_its_hedge_dropped_not_left_wrong(self):
        """Documented side effect, not a defect: the correction rule
        replaces the whole matched span with a fixed template (it always
        has — every other rule in this function does the same for its own
        connectors/verbs), so a hedge word sitting in front of an
        already-correct number gets consumed and dropped rather than
        preserved. The number is right either way; nothing is fabricated
        or misattributed by dropping it."""
        text = "Charity Navigator score of roughly 94.0/100."
        metrics = _metrics(cn_overall_score=94.0)
        out = _sanitize(text, metrics)
        assert out == "Charity Navigator score of 94.0/100."

    def test_malformed_multi_decimal_number_stays_untouched_even_with_a_hedge(self):
        """Task G11's malformed-number guard must still hold: a hedge word
        must not open a back door around `_number_not_malformed`."""
        text = "Strong external accountability rating of roughly 96.96.0/100 from Charity Navigator."
        metrics = _metrics(cn_accountability_score=86.0, cn_overall_score=96.0)
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("It scored a truly remarkable 87 out of 100 from Charity Navigator. It serves many families.",
             _metrics(cn_overall_score=None)),
            ("Charity Navigator score of roughly 60.", _metrics(cn_overall_score=94.0)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestHedgeWordGapCnAccountabilityScore:
    """The worst bug this task found: the generic overall-score rule
    guarded itself against claiming a sub-score-labelled span via
    `_sub_score_lead_re` — but that guard used the same defeated anchor, so
    a hedge word ("of roughly 40/100") let the guard fail silently and the
    overall score got stamped into text explicitly labelled
    accountability's, not just left uncorrected."""

    def test_null_hedged_claim_is_removed(self):
        text = "It has an accountability score of roughly 40/100 from Charity Navigator."
        metrics = _metrics(cn_accountability_score=None, cn_overall_score=94.0)
        out = _sanitize(text, metrics)
        assert out == ""

    def test_wrong_hedged_number_is_corrected_to_its_own_value_not_overall(self):
        """The exact worst-bug repro: cn_overall_score=94.0 must NOT leak
        into accountability's slot; the number must become 60.0, not 94.0."""
        text = "The charity has an accountability score of roughly 40/100 from Charity Navigator."
        metrics = _metrics(cn_overall_score=94.0, cn_accountability_score=60.0)
        out = _sanitize(text, metrics)
        assert out == "The charity has an accountability score of 60.0/100 from Charity Navigator."

    def test_right_unhedged_number_survives_unchanged(self):
        text = "It has an accountability score of 60.0/100."
        metrics = _metrics(cn_accountability_score=60.0)
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("It has an accountability score of roughly 40/100 from Charity Navigator.",
             _metrics(cn_accountability_score=None, cn_overall_score=94.0)),
            ("The charity has an accountability score of roughly 40/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_accountability_score=60.0)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestHedgeWordGapCnFinancialScore:
    """Same worst-bug shape as accountability, for the financial sub-score:
    "financial score of nearly 40/100 from Charity Navigator" used to get
    the *overall* score (94.0) stamped in, not financial's own value."""

    def test_null_hedged_claim_is_removed(self):
        text = "It has a financial score of nearly 40/100 from Charity Navigator."
        metrics = _metrics(cn_financial_score=None, cn_overall_score=94.0)
        out = _sanitize(text, metrics)
        assert out == ""

    def test_wrong_hedged_number_is_corrected_to_its_own_value_not_overall(self):
        text = "The charity has a financial score of nearly 40/100 from Charity Navigator."
        metrics = _metrics(cn_overall_score=94.0, cn_financial_score=55.0)
        out = _sanitize(text, metrics)
        assert out == "The charity has a financial score of 55.0/100 from Charity Navigator."

    def test_right_unhedged_number_survives_unchanged(self):
        text = "It has a financial score of 55.0/100."
        metrics = _metrics(cn_financial_score=55.0)
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("It has a financial score of nearly 40/100 from Charity Navigator.",
             _metrics(cn_financial_score=None, cn_overall_score=94.0)),
            ("The charity has a financial score of nearly 40/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_financial_score=55.0)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestHedgeWordGapProgramExpenseRatio:
    """Two anchor shapes for this metric, both defeated by a hedge: "ratio
    of X%" (anchored on "of") and "directs X% to programs" (anchored on the
    verb) — both the correction and null-removal sides of each."""

    def test_null_hedged_claim_directs_verb_is_removed_appositive_now_strands(self):
        """The brief's own repro line (task G14). Task G15 reversed
        `_clause_trail`'s determiner branch, so the trailing appositive ("a
        strong showing") — a determiner-led noun phrase, same shape as an
        ordinary clause subject — no longer goes with the fabricated hedged
        percentage; it strands as its own fragment. The fabricated
        percentage itself must still be gone."""
        text = "The organization directs an impressive 91% to programs, a strong showing."
        metrics = _metrics(program_expense_ratio=None)
        out = _sanitize(text, metrics)
        assert out == "A strong showing."
        assert "91" not in out

    def test_null_hedged_claim_ratio_of_is_removed(self):
        text = "It has a program expense ratio of only 91% this year."
        metrics = _metrics(program_expense_ratio=None)
        out = _sanitize(text, metrics)
        assert out == ""

    def test_wrong_hedged_ratio_of_is_corrected(self):
        text = "It has a program expense ratio of only 50%."
        metrics = _metrics(program_expense_ratio=0.914)
        out = _sanitize(text, metrics)
        assert out == "It has a program expense ratio of 91.4%."

    def test_wrong_hedged_directs_verb_is_corrected(self):
        text = "The organization directs an impressive 50% to programs."
        metrics = _metrics(program_expense_ratio=0.914)
        out = _sanitize(text, metrics)
        assert out == "The organization directs 91.4% to programs."

    def test_right_unhedged_survives_unchanged(self):
        text = "The organization directs 91.4% to programs."
        metrics = _metrics(program_expense_ratio=0.914)
        out = _sanitize(text, metrics)
        assert out == text

    def test_right_hedged_spends_number_has_its_hedge_dropped_not_left_wrong(self):
        """Pinned from the live corpus (charity-56-2500794.json): "spends an
        efficient 88.7% on programs" (already the correct value) loses its
        hedge "an efficient" the same documented way CN overall's own
        already-correct hedge gets dropped — the number is right either
        way, nothing is fabricated or misattributed."""
        text = "It spends an efficient 88.7% on programs."
        metrics = _metrics(program_expense_ratio=0.887)
        out = _sanitize(text, metrics)
        assert out == "It spends 88.7% on programs."

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("The organization directs an impressive 91% to programs, a strong showing.",
             _metrics(program_expense_ratio=None)),
            ("It has a program expense ratio of only 91% this year.",
             _metrics(program_expense_ratio=None)),
            ("It has a program expense ratio of only 50%.", _metrics(program_expense_ratio=0.914)),
            ("The organization directs an impressive 50% to programs.",
             _metrics(program_expense_ratio=0.914)),
            ("It spends an efficient 88.7% on programs.", _metrics(program_expense_ratio=0.887)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestHedgeWordGapAmalScore:
    """"AMAL score of roughly 72/100" — anchored on "of", same defeated
    anchor as the CN sub-scores."""

    def test_null_hedged_claim_is_removed(self):
        text = "The AMAL score of roughly 72/100 reflects strong impact."
        metrics = _metrics()
        out = _sanitize_amal(text, metrics, amal_score=None)
        assert out == ""

    def test_wrong_hedged_number_is_corrected(self):
        text = "The AMAL score of roughly 72/100 reflects strong impact."
        metrics = _metrics()
        out = _sanitize_amal(text, metrics, amal_score=88)
        assert out == "The AMAL score of 88/100 reflects strong impact."

    def test_right_unhedged_number_survives_unchanged(self):
        text = "AMAL score of 88/100 reflects strong impact."
        metrics = _metrics()
        out = _sanitize_amal(text, metrics, amal_score=88)
        assert out == text

    @pytest.mark.parametrize(
        "amal_score,text",
        [
            (None, "The AMAL score of roughly 72/100 reflects strong impact."),
            (88, "The AMAL score of roughly 72/100 reflects strong impact."),
        ],
    )
    def test_five_pass_stable(self, amal_score, text):
        metrics = _metrics()
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize_amal(passes[-1], metrics, amal_score=amal_score))
        assert passes[1] == passes[2] == passes[3] == passes[4] == passes[5]


class TestHedgeWordGapFoundedYear:
    """Two anchors, both defeated by a hedge: "founded in X" and "operating
    since X". The brief's own repro line is the "in" shape; "since" gets
    the identical fix for the same reason."""

    def test_null_hedged_claim_is_removed(self):
        """The brief's own repro line."""
        text = "The organization was founded in approximately 1975 and has grown since."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == "Has grown since."

    def test_wrong_hedged_in_is_corrected(self):
        text = "The organization was founded in approximately 1975 and has grown since."
        metrics = _metrics(founded_year=1990)
        out = _sanitize(text, metrics)
        assert out == "The organization was founded in 1990 and has grown since."

    def test_wrong_hedged_since_is_corrected(self):
        text = "It has been operating since approximately 1975."
        metrics = _metrics(founded_year=1990)
        out = _sanitize(text, metrics)
        assert out == "It has been operating since 1990."

    def test_right_unhedged_survives_unchanged(self):
        text = "The organization was founded in 1990."
        metrics = _metrics(founded_year=1990)
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("The organization was founded in approximately 1975 and has grown since.",
             _metrics(founded_year=None)),
            ("The organization was founded in approximately 1975 and has grown since.",
             _metrics(founded_year=1990)),
            ("It has been operating since approximately 1975.", _metrics(founded_year=1990)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestHedgeWordGapCrossMetricTrap:
    """A permissive gap risks reaching PAST its own metric's number to one
    belonging to a DIFFERENT metric. Blocked by forbidding `_hedge_gap` from
    consuming a digit (so the match always binds to the nearest number) or
    a word from this function's own closed set of metric nouns (so it can't
    cross into a different metric's named phrase even when that phrase has
    no digit of its own standing in the way). Both orders tested; both are
    synthetic probes built to isolate the noun-boundary defense specifically
    — see the task report for a direct regex-level proof that these exact
    strings WOULD misattribute without the metric-noun exclusion."""

    def test_accountability_does_not_reach_past_program_expense_ratio(self):
        """No digit sits between "of" and "50%" other than through the
        words "program expense" — without the metric-noun exclusion,
        accountability's own hedge_gap could walk right through them and
        stamp its own value (60.0) onto program expense's "50%". Must stay
        completely untouched: neither rule can safely resolve this
        (accountability's own anchor never finds a number of its own to
        correct, and program's rule doesn't recognize this exact phrasing
        either), which is the correct, safe outcome — an under-match, not
        a misattribution."""
        text = "It has an accountability score of program expense 50%."
        metrics = _metrics(cn_accountability_score=60.0, program_expense_ratio=0.914)
        out = _sanitize(text, metrics)
        assert out == text

    def test_program_expense_ratio_does_not_reach_past_accountability_score(self):
        """Reversed order: program-expense-ratio's own "ratio of X%" gap
        must not walk through "accountability score" to reach a number
        that isn't its own. What actually happens: program's rule never
        matches (blocked at "accountability"), and accountability's own
        rule legitimately claims "accountability score 60%" as its own
        claim and corrects it to its own real value — not program's
        91.4%. Confirms no cross-metric value ever leaks either way."""
        text = "It has a program expense ratio of accountability score 60%."
        metrics = _metrics(cn_accountability_score=60.0, program_expense_ratio=0.914)
        out = _sanitize(text, metrics)
        assert out == "It has a program expense ratio of accountability score of 60.0/100."
        assert "91.4" not in out

    def test_natural_no_hedge_sentence_still_binds_nearest_not_farthest(self):
        """No-regression control: without any hedge at all, both numbers
        in one sentence must resolve independently to their own metric's
        value — the pre-existing, already-correct behavior this task must
        not disturb."""
        text = "It has an accountability score of 40/100 and a program expense ratio of 50%."
        metrics = _metrics(cn_accountability_score=60.0, program_expense_ratio=0.5)
        out = _sanitize(text, metrics)
        assert out == "It has an accountability score of 60.0/100 and a program expense ratio of 50.0%."

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("It has an accountability score of program expense 50%.",
             _metrics(cn_accountability_score=60.0, program_expense_ratio=0.914)),
            ("It has a program expense ratio of accountability score 60%.",
             _metrics(cn_accountability_score=60.0, program_expense_ratio=0.914)),
            ("It has an accountability score of 40/100 and a program expense ratio of 50%.",
             _metrics(cn_accountability_score=60.0, program_expense_ratio=0.5)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestHedgeWordGapBoundedByCountNotVocabulary:
    """`_hedge_gap` is bounded by count (`_hedge_max_words = 3`), not by
    enumerating hedge vocabulary — the open-class trap this function has
    been burned by three times already (a verb list, an appositive-lead
    list, a participle list). 3 was chosen to cover every hedge in the
    reported defect ("roughly"/"nearly"/"only"/"approximately" are 1 word;
    "an impressive"/"a mere"/"just over"/"a strong" are 2) with one word of
    headroom. A hedge phrase longer than 3 words still defeats the anchor —
    an honest, bounded residual gap, not silently unhandled: the anchor
    simply fails to match at all, so the rule neither corrects the wrong
    number nor (critically) misattributes a different metric's value to
    it — the failure mode stays "safe", just incomplete."""

    def test_exactly_three_hedge_words_is_still_corrected(self):
        text = "It has an accountability score of a truly remarkable 40/100."
        metrics = _metrics(cn_accountability_score=60.0)
        out = _sanitize(text, metrics)
        assert out == "It has an accountability score of 60.0/100."

    def test_four_hedge_words_is_a_known_residual_gap(self):
        """One word past the bound, no "Charity Navigator" mention in this
        specific text: the correction rule's anchor fails to match at all,
        so the wrong number (40/100) survives exactly as written. Note:
        this text alone does not exercise the sharper defect
        `TestSubScoreGuardStaysPermissiveBeyondTheCorrectionBound` covers —
        see that class for what actually happens once "Charity Navigator"
        is in the sentence and the generic overall rule has something to
        claim."""
        text = "It has an accountability score of a truly quite remarkable 40/100."
        metrics = _metrics(cn_accountability_score=60.0)
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("It has an accountability score of a truly remarkable 40/100.",
             _metrics(cn_accountability_score=60.0)),
            ("It has an accountability score of a truly quite remarkable 40/100.",
             _metrics(cn_accountability_score=60.0)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestSubScoreGuardStaysPermissiveBeyondTheCorrectionBound:
    """A guard must never be narrower than the rule it guards. `_sub_score_
    lead_re` exists specifically to stop the generic CN-overall correction
    rule from claiming a span whose noun names a sub-score — but it
    originally reused `_hedge_gap`'s own 3-word bound to do its own
    backward lookup. Past that bound, the SUB-SCORE rule's own correction
    correctly declines to fire (an honest, mild residual gap: the wrong
    number stays uncorrected) — but the GUARD *also* declined, at exactly
    the same threshold, so the generic overall rule proceeded unguarded
    and stamped the *overall* score into a span explicitly labelled a
    sub-score's — the exact severe misattribution this whole task exists
    to prevent, just relocated to 4+ words instead of eliminated.

    Fixed by giving the guard's own backward lookup an unbounded gap
    (`_guard_gap`, no `{0,N}` cap) while the correction rules keep the
    conservative, bounded `_hedge_gap` — a deliberate asymmetry: the
    correction only ever touches text it fully recognizes (bounded,
    conservative), while the guard's only job is refusing to let a
    DIFFERENT rule act on a span it doesn't own (permissive is safe here,
    since a guard firing too often just means "the overall rule declines
    to fix a legitimate overall-score claim" — over-cautious, not
    corrupting). Now the correct behavior at 4+ words is: the wrong
    number survives completely untouched — neither corrected (still
    bounded) nor misattributed (guard no longer expires)."""

    @pytest.mark.parametrize(
        "hedge",
        ["just a little over", "a bit more than roughly", "just a little bit more than roughly"],
        ids=["4_words", "5_words", "6_plus_words"],
    )
    def test_accountability_wrong_number_is_never_misattributed_to_overall(self, hedge):
        text = f"It has an accountability score of {hedge} 40/100 from Charity Navigator."
        metrics = _metrics(cn_overall_score=94.0, cn_accountability_score=60.0)
        out = _sanitize(text, metrics)
        assert "94.0" not in out
        assert out == text

    @pytest.mark.parametrize(
        "hedge",
        ["just a little under", "a bit less than roughly", "just a little bit less than roughly"],
        ids=["4_words", "5_words", "6_plus_words"],
    )
    def test_financial_wrong_number_is_never_misattributed_to_overall(self, hedge):
        text = f"It has a financial score of {hedge} 40/100 from Charity Navigator."
        metrics = _metrics(cn_overall_score=94.0, cn_financial_score=55.0)
        out = _sanitize(text, metrics)
        assert "94.0" not in out
        assert out == text

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("It has an accountability score of just a little over 40/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_accountability_score=60.0)),
            ("It has an accountability score of a bit more than roughly 40/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_accountability_score=60.0)),
            ("It has a financial score of just a little under 40/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_financial_score=55.0)),
            ("It has a financial score of a bit less than roughly 40/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_financial_score=55.0)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text


class TestHedgeWordGapDoesNotReopenTheLinkingVerbGuard:
    """Task G11 deliberately left "the financial rating IS 40/100" (a
    linking verb, not "of") uncorrected — the guard only stops it from
    being mislabeled as the overall score, it was never meant to correct
    it, since neither sub-score rule parses "is X" as a phrasing shape at
    all (see `test_linking_verb_is_also_guarded_not_just_of`, pinned
    before this task). `_hedge_gap` must not silently reopen that: "is"/
    "was" are excluded from what counts as a hedge word specifically so
    this stays exactly as G11 left it."""

    def test_linking_verb_phrasing_is_still_completely_unchanged(self):
        text = "The accountability rating is 50/100 and the financial rating is 40/100 from Charity Navigator."
        metrics = _metrics(cn_overall_score=96.0, cn_accountability_score=86.0, cn_financial_score=88.0)
        out = _sanitize(text, metrics)
        assert out == text


class TestHedgeGapDoesNotCrossAnAbsentConnectorIntoAnUnrelatedNumber:
    """Two real regressions the empirical corpus check caught that no
    synthetic test above did — both from `website/data/charities/`, both
    fixed by requiring the literal connector word ("of"/"a") to actually be
    present before `_hedge_gap` is allowed to activate at all
    (`(?:of\\s+{_hedge_gap})?`, not `(?:of\\s+)?{_hedge_gap}`): when the
    connector is absent, the whole group is skipped and the number must sit
    immediately adjacent to the anchor, exactly as before this task —
    closing the exposure without enumerating the open-ended set of
    "different referent" words ("median", "peer", "falls below", ...) that
    a word-list approach would have needed instead.

    1. charity-13-1760110.json (and 5 other files): "Charity Navigator
       score and an 85.7% program expense ratio" — two unrelated clauses
       joined by bare "and", no "of" anywhere — used to have the CN
       correction rule's gap walk straight through "and an" and stamp the
       *CN* value into the *program-ratio* clause's number.
    2. charity-06-0726487.json (and 5 other files): "peer program ratio
       median of 90.0%" — a PEER benchmark statistic, not the charity's
       own value — used to have the program-ratio correction rule's gap
       walk through "median" (which sits BEFORE "of", not after it) and
       overwrite the peer figure with the charity's own ratio.

    Both are pinned here as permanent regressions, not just caught once by
    the read-only corpus check — a future edit to `_hedge_gap` or its call
    sites must keep failing loudly if either reopens."""

    def test_and_joined_clauses_with_no_of_stay_untouched(self):
        """Simplified from charity-13-1760110.json. The malformed CN
        number stays untouched (task G11's guard) AND the unrelated
        program-ratio clause must not be corrupted by CN's own value."""
        text = "UNICEF USA has a 97.97.0/100 from Charity Navigator score and an 85.7% program expense ratio."
        metrics = _metrics(cn_overall_score=97.0, program_expense_ratio=0.857)
        out = _sanitize(text, metrics)
        assert out == text

    def test_peer_median_statistic_is_not_overwritten_with_own_value(self):
        """Simplified from charity-06-0726487.json. "median" sits between
        "ratio" and "of" — the connector "of" is never immediately after
        "ratio", so the correction rule must not activate at all."""
        text = "Its program expense ratio sits below the peer program ratio median of 90.0% for similar groups."
        metrics = _metrics(program_expense_ratio=0.849)
        out = _sanitize(text, metrics)
        assert out == text

    def test_comparison_verb_phrasing_with_no_of_at_all_stays_untouched(self):
        """Simplified from charity-91-1914868.json: "falls below" is a
        comparison verb, not a hedge on the metric's OWN number, and there
        is no "of" anywhere in this shape at all."""
        text = "Program ratio falls below the 81.4% peer median when adjusted for non-cash items."
        metrics = _metrics(program_expense_ratio=0.775)
        out = _sanitize(text, metrics)
        assert out == text

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("UNICEF USA has a 97.97.0/100 from Charity Navigator score and an 85.7% program expense ratio.",
             _metrics(cn_overall_score=97.0, program_expense_ratio=0.857)),
            ("Its program expense ratio sits below the peer program ratio median of 90.0% for similar groups.",
             _metrics(program_expense_ratio=0.849)),
            ("Program ratio falls below the 81.4% peer median when adjusted for non-cash items.",
             _metrics(program_expense_ratio=0.775)),
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text


# Task G15, defect 1: `_trail_same_claim_lead`'s determiner/possessive/
# quantifier branch ("a", "an", "the", "its", "their", "his", "her", "one
# of") does not identify an appositive of a removed claim — it identifies a
# noun phrase, and the subject of a true independent clause is a noun phrase
# too. This is a deliberate REVERSAL of the controller's earlier decision to
# consume determiner-led text after a bare comma, not a refinement of it: a
# bare comma is now the default clause boundary for `_clause_trail`, and the
# determiner branch is dropped from the continuation set it consults
# (`_clause_trail_same_claim_lead`). The non-determiner continuation markers
# (comparative-tail prepositions, bare comparatives/superlatives) are kept
# unchanged, since none of those can open the subject of an independent
# clause the way a determiner can.
_G15_TRUE_CLAUSE_SURVIVES_CASES = [
    (
        "founded_the_charity_serves",
        "Founded in 1990, the charity serves 5,000 families each year.",
        dict(founded_year=None),
        "The charity serves 5,000 families each year.",
    ),
    (
        "founded_the_organization_has_trained",
        "Founded in 1990, the organization has trained over 200 volunteers.",
        dict(founded_year=None),
        "The organization has trained over 200 volunteers.",
    ),
    (
        "founded_an_independent_audit",
        "Founded in 1990, an independent audit confirmed its clean record.",
        dict(founded_year=None),
        "An independent audit confirmed its clean record.",
    ),
    (
        "founded_its_mission",
        "Founded in 1990, its mission is to provide clean water to villages.",
        dict(founded_year=None),
        "Its mission is to provide clean water to villages.",
    ),
    (
        "working_capital_the_organization_also_serves",
        "The charity holds 5.2 months of working capital, the organization "
        "also serves 5,000 families annually.",
        dict(working_capital_ratio=None),
        "The organization also serves 5,000 families annually.",
    ),
    (
        "cn_score_the_board_consists_of",
        "Scored 87/100 on Charity Navigator, the board consists of nine "
        "independent members.",
        dict(cn_overall_score=None),
        "The board consists of nine independent members.",
    ),
]

# Control confirming the mechanism rather than coincidence: "this" is not on
# `_clause_trail_same_claim_lead` either (it never was), so this case already
# passed before task G15 and must keep passing unchanged.
_G15_CONTROL_CASE = (
    "founded_this_organization",
    "Founded in 1990, this organization has won three national awards.",
    dict(founded_year=None),
    "This organization has won three national awards.",
)

# The other half of the reversal: a determiner-led appositive of a claim that
# WAS just removed is no longer consumed with it — it strands as a dangling
# fragment instead. Accepted per the brief's own standing instruction: a
# visible, fabrication-adjacent fragment is preferable to silently erasing a
# true clause, and stranded fragments are already a documented, accepted
# artifact class (`_repair_removal_artifacts`). These pin the NEW behavior
# deliberately, as a record of the trade, not as a claim it's an improvement
# in isolation.
_G15_APPOSITIVE_NOW_STRANDS_CASES = [
    (
        "its_highest_rating",
        "The charity earned a perfect score from Charity Navigator, its highest rating.",
        dict(cn_overall_score=None),
        "Its highest rating.",
    ),
    (
        "a_strong_reserve_position",
        "The charity holds 4.2 months of working capital, a strong reserve position.",
        dict(working_capital_ratio=None),
        "A strong reserve position.",
    ),
    (
        "the_best_in_its_class",
        "The charity holds 4.2 months of working capital, the best in its class.",
        dict(working_capital_ratio=None),
        "The best in its class.",
    ),
    (
        "one_of_the_highest_in_its_cohort",
        "The charity scored 87/100 from Charity Navigator, one of the highest in its cohort.",
        dict(cn_overall_score=None),
        "One of the highest in its cohort.",
    ),
]


class TestClauseTrailDeterminerLeadIsReversed:
    """Task G15, defect 1. See the module-level comments above this class
    for the reasoning; this class pins the observable behavior."""

    def test_the_reversal_itself_a_determiner_led_true_clause_survives(self):
        """The single case that most directly proves the reversal: if a
        future change restores the determiner/possessive/quantifier branch
        to `_clause_trail`'s continuation set, this is the case that must
        fail. Kept as its own, unmistakably-named test rather than only a
        parametrized row, so it can't be silently dropped alongside the rest
        of `_G15_TRUE_CLAUSE_SURVIVES_CASES`."""
        text = "Founded in 1990, the charity serves 5,000 families each year."
        metrics = _metrics(founded_year=None)
        out = _sanitize(text, metrics)
        assert out == "The charity serves 5,000 families each year."

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _G15_TRUE_CLAUSE_SURVIVES_CASES,
        ids=[n for n, *_ in _G15_TRUE_CLAUSE_SURVIVES_CASES])
    def test_true_independent_clause_now_survives(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _G15_TRUE_CLAUSE_SURVIVES_CASES,
        ids=[n for n, *_ in _G15_TRUE_CLAUSE_SURVIVES_CASES])
    def test_true_independent_clause_case_is_five_pass_stable(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected

    def test_control_case_this_was_never_on_the_list(self):
        _, text, overrides, expected = _G15_CONTROL_CASE
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _G15_APPOSITIVE_NOW_STRANDS_CASES,
        ids=[n for n, *_ in _G15_APPOSITIVE_NOW_STRANDS_CASES])
    def test_determiner_led_appositive_now_strands_instead_of_being_consumed(
        self, name, text, overrides, expected
    ):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _G15_APPOSITIVE_NOW_STRANDS_CASES,
        ids=[n for n, *_ in _G15_APPOSITIVE_NOW_STRANDS_CASES])
    def test_stranded_appositive_case_is_five_pass_stable(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected


class TestFrGapDollarFirstUnaffectedByTheDeterminerReversal:
    """The coupling the brief calls out: `_fr_gap_dollar_first` reuses
    `_trail_same_claim_lead` (unchanged, NOT `_clause_trail_same_claim_lead`)
    for its own bare-comma test, so this rule keeps its separate, already-
    documented reason to tolerate a determiner-led continuation: a bare
    comma joining a null $0.00 to "an indication of poor fundraising
    efficiency" is a genuine two-sided fabrication about the SAME figure, not
    a candidate true-clause subject."""

    def test_determiner_led_dollar_appositive_still_strips(self):
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "The charity spent $0.00, an indication of poor fundraising efficiency."
        out = _sanitize(text, metrics)
        assert "$0.00" not in out

    def test_true_dollar_figure_with_hedge_still_survives(self):
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "Total revenue was $141,261, though fundraising efficiency could not be determined."
        out = _sanitize(text, metrics)
        assert out == text

    def test_determiner_led_dollar_appositive_is_five_pass_stable(self):
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "The charity spent $0.00, an indication of poor fundraising efficiency."
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_true_dollar_figure_with_hedge_is_five_pass_stable(self):
        metrics = _metrics(total_revenue=141_261, fundraising_expenses=None)
        text = "Total revenue was $141,261, though fundraising efficiency could not be determined."
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text


# Task G15, defect 2: a structural "Label: value" quote lost both the colon
# AND the value, stranding a bare label asserting nothing ("Fundraising
# Efficiency"). Fixed with `_label_colon_lead`: at a true sentence start, a
# digit-free run of text ending in a colon is swallowed as part of the same
# removal, so the whole "Label: value" unit goes, matching the existing,
# already-correct behavior of the short form with no trailing phrase.
_G15_LABEL_COLON_CASES = [
    (
        "fundraising_efficiency_label",
        "Fundraising Efficiency: $0.00 per $1 raised",
        dict(fundraising_expenses=None),
        "",
    ),
    (
        "overall_score_and_rating_label",
        "Overall Score & Rating: 92/100 from Charity Navigator",
        dict(cn_overall_score=None),
        "",
    ),
    (
        "working_capital_label",
        "Working Capital: 5.2 months of reserves",
        dict(working_capital_ratio=None),
        "",
    ),
]


class TestLabelColonValueGoesFullyEmpty:
    """Task G15, defect 2."""

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _G15_LABEL_COLON_CASES,
        ids=[n for n, *_ in _G15_LABEL_COLON_CASES])
    def test_label_colon_value_removed_as_one_unit(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _G15_LABEL_COLON_CASES,
        ids=[n for n, *_ in _G15_LABEL_COLON_CASES])
    def test_label_colon_value_case_is_five_pass_stable(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected

    def test_short_form_with_no_trailing_phrase_unaffected(self):
        """No-regression check: the short form ("Label: $0.00" with nothing
        after) already went fully empty before this task, via the
        phrase-first rule whose own core literally anchors on "fundraising
        efficiency" — confirms defect 2's fix didn't change this path."""
        metrics = _metrics(fundraising_expenses=None)
        text = "Fundraising Efficiency: $0.00"
        out = _sanitize(text, metrics)
        assert out == ""

    def test_colon_true_leads_still_protects_a_genuine_clause_with_its_own_digit(self):
        """No-regression check for the existing `colon_true_leads` case
        (`TestFourUnambiguousJoinersAreNowClauseBoundaries`): the text
        before the colon has its own digit (8.3), so `_label_colon_lead`
        cannot match there, and the pre-existing colon-as-connector
        protection for a genuine true clause is exactly what still
        applies."""
        metrics = _metrics(cn_overall_score=None, working_capital_ratio=8.3)
        text = "It holds 8.3 months of working capital: it also scored 87/100 on Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "It holds 8.3 months of working capital."


class TestOverallGuardFailsSafeOnAnyUnrecognizedName:
    """Task G16: `_sub_score_lead_re` (the guard that stops the generic
    cn_overall_score rule from claiming a span whose number is actually
    named by a *different* metric) worked by ENUMERATING the sub-score
    vocabulary it must refuse — names ("accountability", "financial",
    "governance") and nouns ("score", "rating"). Escaped three times by
    three different routes (a new noun word, a hedge defeating the anchor,
    the guard's own hedge bound expiring before the rule it guards) — and,
    live in the corpus, by a fourth beacon name ("Leadership") the guard's
    vocabulary never enumerated at all (charity-26-0906163.json's
    rich_narrative, "a Leadership score of 20/100 from Charity Navigator",
    inert on disk only because a citation tag breaks the match; the same
    claim shape appears elsewhere without one).

    Fixed by INVERTING the guard: instead of a closed list of names to
    REFUSE (open-ended, always escapable — any new beacon name or noun is
    a fresh bypass), it is now a closed list of names the overall rule may
    CLAIM (`_overall_name` — "overall" and "Charity Navigator" itself,
    the metric's own two ways of referring to itself). Everything else —
    any other named metric, known or not, however it's phrased — declines
    by default via `_named_metric_claim_lead_re`, whose only job is
    detecting *that* a number is named by *something* (via an open, un-
    enumerated noun match once a connector word is present, so "grade"/
    "index"/"mark"/"quotient"/anything else works with no vocabulary to
    keep pace with) — not identifying *what*. The failure mode inverts
    correctly: an unrecognized name now leaves the text alone rather than
    stamping a different metric's value into it."""

    # --- the exact leak lines from the report, name-noun matrix ---

    @pytest.mark.parametrize(
        "noun", ["score", "rating", "grade", "index", "mark"],
        ids=["score", "rating", "grade", "index", "mark"],
    )
    def test_accountability_with_any_noun_is_never_misattributed_to_overall(self, noun):
        metrics = _metrics(cn_overall_score=75.0, cn_accountability_score=90.0, cn_financial_score=40.0)
        text = f"an accountability {noun} of 55/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert "75.0" not in out
        if noun in ("score", "rating"):
            # These two are still corrected, by accountability's own rule,
            # to accountability's real value — not left alone, and
            # certainly not misattributed to overall.
            assert out == f"an accountability {noun} of 90.0/100 from Charity Navigator."
        else:
            # No rule anywhere in this function knows what an
            # "accountability grade/index/mark" is, so it's an honest
            # residual gap (left completely alone) — not a misattribution.
            assert out == text

    @pytest.mark.parametrize(
        "name", ["financial", "finance", "fiscal"],
        ids=["financial", "finance", "fiscal"],
    )
    def test_financial_name_variant_with_score_is_never_misattributed_to_overall(self, name):
        metrics = _metrics(cn_overall_score=75.0, cn_accountability_score=90.0, cn_financial_score=40.0)
        text = f"a {name} score of 55/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert "75.0" not in out
        if name == "financial":
            assert out == "a financial score of 40.0/100 from Charity Navigator."
        else:
            # "finance"/"fiscal" aren't `_fin_name` (only "financial" is),
            # so financial's own rule can't correct them either — left
            # alone, not misattributed.
            assert out == text

    def test_fiscal_health_score_is_never_misattributed_to_overall(self):
        metrics = _metrics(cn_overall_score=75.0, cn_accountability_score=90.0, cn_financial_score=40.0)
        text = "a fiscal health score of 55/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert "75.0" not in out
        assert out == text

    # --- the live corpus leak: a beacon name never enumerated at all ---

    def test_leadership_beacon_score_is_never_misattributed_to_overall(self):
        """Reproduces charity-26-0906163.json's rich_narrative claim shape
        (citation tag stripped, matching the un-tagged form that appears
        elsewhere in the corpus): a real Charity Navigator Encompass
        beacon this function has no correction rule for at all. Must be
        left completely alone, not stamped with the overall score."""
        metrics = _metrics(cn_overall_score=64.0, cn_accountability_score=90.0, cn_financial_score=40.0)
        text = ("The organization received a Leadership score of 20/100 from Charity "
                "Navigator, indicating a need for better board oversight.")
        out = _sanitize(text, metrics)
        assert out == text

    def test_adaptability_beacon_score_is_never_misattributed_to_overall(self):
        """Charity Navigator's fourth Encompass beacon is named
        "Leadership & Adaptability" in some published prose and just
        "Adaptability" in others."""
        metrics = _metrics(cn_overall_score=64.0)
        text = "It earned an Adaptability score of 20/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    # --- invented names/nouns nowhere in this codebase's vocabulary ---

    def test_invented_fictional_beacon_name_is_never_misattributed(self):
        """A beacon name that doesn't exist, invented for this test — proves
        the guard's safety doesn't depend on recognizing any particular
        name, only on recognizing that a name is present at all."""
        metrics = _metrics(cn_overall_score=64.0)
        text = "It received a Zephyr Integrity score of 30/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_invented_unusual_noun_is_never_misattributed(self):
        """"quotient" is not "score"/"rating"/any noun this function has
        ever enumerated anywhere."""
        metrics = _metrics(cn_overall_score=64.0, cn_accountability_score=90.0)
        text = "It has an accountability quotient of 30/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    def test_invented_unusual_name_form_is_never_misattributed(self):
        """A hyphenated, invented compound name form."""
        metrics = _metrics(cn_overall_score=64.0)
        text = "It earned a Donor-Trust rating of 45/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    # --- genuine overall-score claims must still be corrected ---

    @pytest.mark.parametrize(
        "text",
        [
            "an overall score of 55/100 from Charity Navigator.",
            "an overall rating of 55/100 from Charity Navigator.",
            "a Charity Navigator score of 55/100.",
            "Charity Navigator score of 55/100.",
            "the Charity Navigator's overall score of 55/100 from Charity Navigator.",
        ],
        ids=["overall_score", "overall_rating", "a_cn_score", "bare_cn_score", "cn_possessive_overall"],
    )
    def test_explicitly_labelled_overall_claims_are_still_corrected(self, text):
        metrics = _metrics(cn_overall_score=94.0, cn_accountability_score=60.0, cn_financial_score=55.0)
        out = _sanitize(text, metrics)
        assert "94.0" in out
        assert "60.0" not in out and "55.0" not in out

    @pytest.mark.parametrize(
        "text",
        [
            "It maintains a 94.0/100 from Charity Navigator.",
            "The charity has earned a 94.0/100 score from Charity Navigator [1].",
            "Donors can trust this charity due to its 94.0/100 from Charity Navigator.",
            "The organization holds a perfect 94.0/100 from Charity Navigator.",
        ],
        ids=["maintains_a", "earned_a", "due_to_its", "perfect"],
    )
    def test_genuinely_unlabelled_claims_still_get_corrected(self, text):
        """No named-metric noun sits between the determiner/verb and the
        number at all — this is the shape 94/166 real published files use
        (a bare number, no "score of"/"rating of" construction), and it
        must remain correctable exactly as before the inversion."""
        metrics = _metrics(cn_overall_score=71.0, cn_accountability_score=60.0, cn_financial_score=55.0)
        out = _sanitize(text, metrics)
        assert "71.0" in out

    def test_wrong_overall_number_with_no_label_at_all_is_still_corrected(self):
        metrics = _metrics(cn_overall_score=71.0)
        text = "It scored 55/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert "71.0" in out

    # --- accountability/financial/governance still correct to their OWN values ---

    def test_accountability_score_still_corrects_to_its_own_value(self):
        metrics = _metrics(cn_overall_score=94.0, cn_accountability_score=60.0, cn_financial_score=55.0)
        text = "an accountability score of 10/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "an accountability score of 60.0/100 from Charity Navigator."

    def test_financial_score_still_corrects_to_its_own_value(self):
        metrics = _metrics(cn_overall_score=94.0, cn_accountability_score=60.0, cn_financial_score=55.0)
        text = "a financial score of 10/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "a financial score of 55.0/100 from Charity Navigator."

    def test_governance_score_still_corrects_to_its_own_value(self):
        metrics = _metrics(cn_overall_score=94.0, cn_accountability_score=60.0, cn_financial_score=55.0)
        text = "a governance score of 10/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == "a governance score of 60.0/100 from Charity Navigator."

    def test_linking_verb_sub_score_claim_still_guarded_not_misattributed(self):
        """G11's pinned decision, re-verified under the new guard: "is X"
        phrasing is a shape no sub-score rule parses, so it stays
        uncorrected — but it must never be misattributed to overall
        either, and the new guard's mandatory-connector branch
        (score|rating with optional of/is/was) still catches this."""
        metrics = _metrics(cn_overall_score=94.0, cn_financial_score=55.0)
        text = "the financial rating is 40/100 from Charity Navigator."
        out = _sanitize(text, metrics)
        assert out == text

    # --- five-pass idempotency across everything above ---

    @pytest.mark.parametrize(
        "text,metrics",
        [
            ("an accountability grade of 55/100 from Charity Navigator.",
             _metrics(cn_overall_score=75.0, cn_accountability_score=90.0)),
            ("a fiscal health score of 55/100 from Charity Navigator.",
             _metrics(cn_overall_score=75.0, cn_financial_score=40.0)),
            ("The organization received a Leadership score of 20/100 from Charity "
             "Navigator, indicating a need for better board oversight.",
             _metrics(cn_overall_score=64.0)),
            ("It received a Zephyr Integrity score of 30/100 from Charity Navigator.",
             _metrics(cn_overall_score=64.0)),
            ("an overall score of 55/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_accountability_score=60.0)),
            ("It maintains a 94.0/100 from Charity Navigator.",
             _metrics(cn_overall_score=71.0)),
            ("an accountability score of 10/100 from Charity Navigator.",
             _metrics(cn_overall_score=94.0, cn_accountability_score=60.0)),
        ],
        ids=[
            "accountability_grade", "fiscal_health_score", "leadership", "invented_beacon",
            "overall_score", "unlabelled_bare", "accountability_score",
        ],
    )
    def test_five_pass_stable(self, text, metrics):
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestWorkingCapitalRangeHyphenIsNotFabricatedIntoANumber:
    """Task G17, defect 1. G9 gave `_wc_num_unit` a leading `-?` so a
    genuinely negative working-capital ratio replaces cleanly instead of
    accumulating dashes. That same `-?` also matches a hyphen used as an
    ordinary number-RANGE separator ("the standard 6-41.7 months") — since
    regex matching is leftmost-start-wins, the digit before the hyphen
    fails to match alone (no unit immediately follows it), so the next
    start position tried is the hyphen itself, where `-?` consumes it as a
    sign and glues the preceding digit onto the replacement: "6-41.7" ->
    "641.7" on the first pass, a number that exists in neither the source
    data nor the source text, then a second, still-wrong number on the
    next pass — not idempotent. `(?<!\\d)` fixes it: a hyphen directly
    preceded by a digit is a range separator, never a sign, so matching
    can no longer start there at all."""

    def test_range_already_correct_is_left_completely_untouched(self):
        """LIVE shape: charity-32-0077563, rich_narrative.case_against.
        risk_factors[0]. The second number already equals the metric, so a
        correct fix is invisible here — but the old bug still fabricated
        "641.7" on pass one even when the eventual value was right."""
        metrics = _metrics(working_capital_ratio=41.7)
        text = "This is significantly higher than the standard 6-41.7 months of working capital."
        assert _sanitize(text, metrics) == text
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    def test_range_second_number_is_corrected_without_touching_the_first(self):
        metrics = _metrics(working_capital_ratio=12.0)
        text = "A range of 3-12 months of working capital is typical."
        expected = "A range of 3-12.0 months of working capital is typical."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_range_second_number_is_corrected_with_reserves_noun(self):
        metrics = _metrics(working_capital_ratio=10.0)
        text = "The 2019-2024 period saw 5-10 months of reserves."
        expected = "The 2019-2024 period saw 5-10.0 months of working capital."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_control_case_stays_unmatched(self):
        """The team-lead's own control case: "operating reserves" isn't a
        recognized noun phrase (only "operating expenses/costs" or bare
        "reserves" are), so this rule never fires here at all — confirms
        the fix introduces no new false positive on an ordinary hyphenated
        year/count range."""
        metrics = _metrics(working_capital_ratio=9.0)
        text = "Peers hold 6-9 years of operating reserves."
        assert _sanitize(text, metrics) == text
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    def test_negative_ratio_with_no_range_still_corrects_normally(self):
        """G9's own case, re-pinned here as a regression guard against this
        specific fix: a genuine negative sign (always preceded by
        whitespace or a verb, never a digit) must still be consumed by the
        match exactly as G9 left it."""
        metrics = _metrics(working_capital_ratio=-2.7)
        text = "The charity holds -2.7 months of working capital."
        assert _sanitize(text, metrics) == text
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text


class TestRepairIsScopedToTheRemovalSite:
    """Task G17, defect 2 (root cause). `_repair_removal_artifacts`'s
    cleanup used to run unconditionally over the WHOLE narrative field
    whenever a removal fired anywhere in it — gated on "did a removal
    happen at all," not on where it happened. An ordinary sentence
    boundary sitting anywhere else in the same field ("Inc. is...", "the
    U.S. and abroad...") got misread as this removal's own leftover
    debris: a real "and" silently deleted, a real word wrongly
    capitalized. Now scoped to a window around the actual removal joint
    (see `_joint_windows`); text outside every window must survive byte-
    identical."""

    def test_abbreviation_far_from_the_removal_survives_untouched(self):
        """LIVE shape: charity-83-1794093. "Inc." is nowhere near where the
        fundraising claim was removed (the end of the field), so it must
        not be touched at all."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "Hikma Health Inc. is an early-stage nonprofit. "
            "It has a fundraising efficiency of $0.00 per $1 raised."
        )
        expected = "Hikma Health Inc. is an early-stage nonprofit."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_second_abbreviation_case_far_from_the_removal_survives(self):
        """LIVE shape: charity-88-2454707."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "HEAL Palestine Inc. is a relief org. "
            "It has a fundraising efficiency of $0.00 per $1 raised."
        )
        expected = "HEAL Palestine Inc. is a relief org."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_and_conjunction_far_from_the_removal_is_not_deleted(self):
        """Worse than the capitalization case: the old bug didn't just
        miscapitalize "abroad", it deleted the word "and" entirely, turning
        one true sentence into a different, ungrammatical one."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "It works in the U.S. and abroad. "
            "It has a fundraising efficiency of $0.00 per $1 raised."
        )
        expected = "It works in the U.S. and abroad."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_sentence_initial_and_far_from_the_removal_is_not_deleted(self):
        """The other case the team-lead called out: the same unscoped
        mechanism silently drops a legitimate sentence-initial "And "
        anywhere else in the field, not just after an abbreviation."""
        metrics = _metrics(fundraising_expenses=None)
        text = (
            "Some fact holds true. And another true fact follows here. "
            "It has a fundraising efficiency of $0.00 per $1 raised."
        )
        expected = "Some fact holds true. And another true fact follows here."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_repair_still_cleans_up_its_own_actual_joint(self):
        """Scoping must not turn into "never repair anything" — the
        orphaned double period this removal itself creates, right where it
        actually happened, must still be collapsed to one."""
        metrics = _metrics(fundraising_expenses=None)
        text = "It serves refugees. It has a fundraising efficiency of $0.00 per $1 raised."
        expected = "It serves refugees."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestAbbreviationExceptionEvenWithinTheRemovalWindow:
    """Task G17, defect 2, requirement 2. Scoping alone isn't enough when
    the abbreviation sits directly AT the removal joint — e.g. `_clause_
    lead`'s own leftmost-match search stops right at "Corp."'s period,
    so the window legitimately includes it. Reuses `_ABBREVIATIONS_
    BEFORE_COMMA`, the same closed vocabulary `_abbreviation_before_
    stray_comma` already guards `.,` with, rather than a second list."""

    def test_inc_directly_before_the_joint_is_not_a_boundary(self):
        metrics = _metrics(fundraising_expenses=None)
        text = "It partners with Example Inc. and abroad, spending $0.00 per $1 raised to help refugees."
        expected = "It partners with Example Inc. and abroad."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_corp_directly_before_the_joint_is_not_a_boundary(self):
        metrics = _metrics(fundraising_expenses=None)
        text = "It works with Example Corp. and abroad, spending $0.00 per $1 raised to help refugees."
        expected = "It works with Example Corp. and abroad."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_us_directly_before_the_joint_is_not_a_boundary(self):
        metrics = _metrics(fundraising_expenses=None)
        text = "It works in the U.S. and abroad, spending $0.00 per $1 raised to reach them."
        expected = "It works in the U.S. and abroad."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_corp_was_directly_before_the_joint_is_not_capitalized_wrong(self):
        """`_clause_lead`'s greedy leftmost search reaches this far back
        when nothing blocks it, stopping the removal's own leading edge
        right at "Corp."'s period rather than after "founded"."""
        metrics = _metrics(fundraising_expenses=None)
        text = "It works with Example Corp. was founded to help refugees, spending $0.00 per $1 raised to reach them."
        expected = "It works with Example Corp. was founded to help refugees."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_jr_served_directly_before_the_joint_is_not_capitalized_wrong(self):
        metrics = _metrics(fundraising_expenses=None)
        text = "It was led by John Smith Jr. served as chair, spending $0.00 per $1 raised on outreach."
        expected = "It was led by John Smith Jr. served as chair."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]

    def test_et_al_found_directly_before_the_joint_is_not_capitalized_wrong(self):
        metrics = _metrics(fundraising_expenses=None)
        text = "According to Smith et al. found major gains, spending $0.00 per $1 raised on outreach."
        expected = "According to Smith et al. found major gains."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestScopedRepairHandlesMultipleRemovalsInOneField:
    """Two separate removal rules firing on the same field, one after the
    other (each gets its own `_repair_removal_artifacts` call per `_apply_
    rules`'s loop) — confirms scoping composes correctly across rules
    rather than only being tested one-removal-at-a-time."""

    def test_two_independent_removals_each_scoped_to_their_own_joint(self):
        metrics = _metrics(fundraising_expenses=None, founded_year=None)
        text = (
            "It works with Example Corp. and abroad, spending $0.00 per $1 raised. "
            "It was founded in 1985. "
            "It serves refugees."
        )
        expected = "It works with Example Corp. and abroad. It serves refugees."
        assert _sanitize(text, metrics) == expected
        passes = _five_passes(text, metrics)
        assert passes[0] == expected
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4]


class TestScopedRepairHandlesSeveralMatchesFromOneRuleInOnePass:
    """Task G17, hand-probing finding beyond the two assigned defects: one
    removal rule's single `re.sub` call can itself remove several separate
    matches from the same field ("Zakat-eligible... fuqara, masakin" for a
    SADAQAH-ELIGIBLE charity strips all three zakat-keyword phrases in one
    pass), leaving several joints close together with nothing but
    punctuation debris between them. Windowing each joint independently
    left that debris — "..." with the words gone from both sides — outside
    every window, so it survived unrepaired (LIVE: charity-75-2352043's
    citation quote produced ".." instead of fully empty). `_joint_windows`
    now merges two windows whenever the gap between them has no letter or
    digit at all, since such a gap can only be removal debris, never
    genuine surviving prose."""

    def test_three_keyword_matches_leave_no_punctuation_debris(self):
        """LIVE shape: charity-75-2352043, rich_narrative.all_citations[2].
        quote. Every word is a separate zakat-keyword match; only the
        ellipsis and a comma separate them, and none of it is real prose."""
        metrics = _metrics()
        text = "Zakat-eligible... fuqara, masakin"
        out = _sanitize(text, metrics, wallet_tag="SADAQAH-ELIGIBLE")
        assert out == ""
        twice = _sanitize(out, metrics, wallet_tag="SADAQAH-ELIGIBLE")
        assert twice == out

    def test_keyword_matches_with_real_prose_between_them_keep_that_prose(self):
        """Control: when there IS real prose between two matches of the
        same rule, it must survive — the merge only ever fires on a
        punctuation-only gap, never on a gap containing actual words."""
        metrics = _metrics()
        text = "It is zakat-eligible. It also serves the poor and needy of Chicago. It is asnaf-recognized."
        out = _sanitize(text, metrics, wallet_tag="SADAQAH-ELIGIBLE")
        assert out == "It also serves the poor and needy of Chicago."
        twice = _sanitize(out, metrics, wallet_tag="SADAQAH-ELIGIBLE")
        assert twice == out


class TestWindowExtendsThroughAWholeRunOfTerminalMarks:
    """Task G17, hand-probing finding beyond the two assigned defects: a
    window's edge search stopped at the FIRST terminal mark found, but
    that mark can itself be the start of a multi-mark run (an ellipsis, or
    a doubled mark from elsewhere) — leaving the REST of the run just
    outside the window as unrepaired debris. LIVE: charity-20-4097808's
    citation quote "The FYI is Zakat eligible... Zakat Categories:
    fisabilillah" removed "Zakat eligible" (the whole leading clause),
    leaving "..." as the joint's own orphaned trailer; taking only the
    ellipsis's first dot left ".. Zakat Categories: fisabilillah" instead
    of the correct "Zakat Categories: fisabilillah". `_run_start`/`_run_end`
    now extend through the whole run before fixing the window boundary."""

    def test_removal_leaves_a_full_ellipsis_orphan_which_is_fully_cleaned(self):
        metrics = _metrics()
        text = "The FYI is Zakat eligible... Zakat Categories: fisabilillah"
        out = _sanitize(text, metrics, wallet_tag="SADAQAH-ELIGIBLE")
        assert out == "Zakat Categories: fisabilillah"
        twice = _sanitize(out, metrics, wallet_tag="SADAQAH-ELIGIBLE")
        assert twice == out


class TestRepairRemainsUnscopedWhenCalledWithoutJoints:
    """`_repair_removal_artifacts(text)` with no second argument is the
    direct, whole-string mode existing callers (and the tests above this
    class in the file) already rely on — must be completely unchanged by
    the G17 scoping work."""

    def test_no_joints_still_repairs_the_whole_string_as_before(self):
        text = ", and it also serves the community."
        assert _repair_removal_artifacts(text) == "It also serves the community."

    def test_no_joints_is_still_idempotent(self):
        text = ", and it also serves the community."
        once = _repair_removal_artifacts(text)
        twice = _repair_removal_artifacts(once)
        assert once == twice


# Task G18: a null-metric removal rule anchors on two ends (e.g. "scored N out
# of 100" ... "Charity Navigator") with a permissive gap between them, so
# genuine same-claim co-occurrence within one sentence still matches ("scored
# 87/100 last year from Charity Navigator"). That same gap tolerated commas
# (and, for two rules, bound its own bare `/100` core) unconditionally — so it
# would just as happily bridge over a comma-joined, UNRELATED, real claim
# sitting in between, deleting it, or bind straight to a different metric's
# own number. Both mechanisms are fixed the same way `_fr_gap` was fixed in
# task G12: forbid the gap from reaching a DIFFERENT metric's own claim,
# reusing this function's existing per-metric name/noun atoms rather than a
# new vocabulary list.
_CN_BRIDGING_REPRO_CASES = [
    (
        "accountability_between_score_and_navigator",
        "It scored 87 out of 100, with an accountability rating of 91.0/100, from Charity Navigator.",
        dict(cn_overall_score=None, cn_accountability_score=91.0),
        "It scored 87 out of 100, with an accountability rating of 91.0/100, from Charity Navigator.",
    ),
    (
        "financial_between_score_and_navigator",
        "It scored 87 out of 100, with a financial score of 55.0/100, from Charity Navigator.",
        dict(cn_overall_score=None, cn_financial_score=55.0),
        "It scored 87 out of 100, with a financial score of 55.0/100, from Charity Navigator.",
    ),
    (
        "accountability_before_navigator_name_first",
        "Charity Navigator notes its 91.0/100 accountability score, and scored 87 out of 100 overall.",
        dict(cn_overall_score=None, cn_accountability_score=91.0),
        "Charity Navigator notes its 91.0/100 accountability score, and scored 87 out of 100 overall.",
    ),
    (
        "working_capital_between_score_and_navigator",
        "It scored 87 out of 100, holding 8.3 months of working capital, from Charity Navigator.",
        dict(cn_overall_score=None, working_capital_ratio=8.3),
        "It scored 87 out of 100, holding 8.3 months of working capital, from Charity Navigator.",
    ),
    (
        "program_expense_between_score_and_navigator",
        "It scored 87 out of 100, directing 91.4% to programs, from Charity Navigator.",
        dict(cn_overall_score=None, program_expense_ratio=0.914),
        "It scored 87 out of 100, directing 91.4% to programs, from Charity Navigator.",
    ),
]

_CN_BRIDGING_CONTROL_CASES = [
    (
        "bare_score_last_year_still_removed",
        "It scored 87/100 last year from Charity Navigator.",
        dict(cn_overall_score=None),
        "",
    ),
    (
        "bare_score_out_of_100_with_year_still_removed",
        "It scored 87 out of 100 in 2024 from Charity Navigator.",
        dict(cn_overall_score=None),
        "",
    ),
]

_CN_BRIDGING_INVENTED_CASES = [
    (
        "governance_name_variant",
        "It scored 87 out of 100, with a governance rating of 60.0/100, from Charity Navigator.",
        dict(cn_overall_score=None, cn_accountability_score=60.0),
        "It scored 87 out of 100, with a governance rating of 60.0/100, from Charity Navigator.",
    ),
    (
        "perfect_score_rule_with_embedded_working_capital",
        "It earned a perfect score, holding 8.3 months of working capital, from Charity Navigator.",
        dict(cn_overall_score=None, working_capital_ratio=8.3),
        "It earned a perfect score, holding 8.3 months of working capital, from Charity Navigator.",
    ),
    (
        "star_rating_rule_with_embedded_program_expense",
        "It has a 5-star rating, directing 91.4% to programs, from Charity Navigator.",
        dict(cn_overall_score=None, program_expense_ratio=0.914),
        "It has a 5-star rating, directing 91.4% to programs, from Charity Navigator.",
    ),
]


class TestNullCnRemovalDoesNotBridgeOverAnotherMetricClaim:
    """The five repros from the task brief: a null cn_overall_score removal
    rule's gap bridged over an unrelated, TRUE claim about a different
    metric sitting between its two anchors, deleting it (or, for the
    name/number-adjacent shapes, binding its own bare `/100` core straight
    to that different metric's number). Fixed by declining to remove at
    all when doing so would require crossing another metric's own claim —
    an accepted, safer trade: the null CN mention survives unstripped in
    this narrower combined shape rather than risk deleting real content."""

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _CN_BRIDGING_REPRO_CASES, ids=[c[0] for c in _CN_BRIDGING_REPRO_CASES]
    )
    def test_true_claim_survives_uncorrupted(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _CN_BRIDGING_REPRO_CASES, ids=[c[0] for c in _CN_BRIDGING_REPRO_CASES]
    )
    def test_true_claim_survival_is_five_pass_stable(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected


class TestNullCnRemovalControlsStillFullyStrip:
    """The two controls the permissive gap exists FOR: genuine same-claim
    co-occurrence within one sentence, with nothing else in between, must
    still be removed in full — this task's fix must not turn into a new
    under-removal regression for the ordinary case."""

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _CN_BRIDGING_CONTROL_CASES, ids=[c[0] for c in _CN_BRIDGING_CONTROL_CASES]
    )
    def test_bare_claim_still_fully_removed(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _CN_BRIDGING_CONTROL_CASES, ids=[c[0] for c in _CN_BRIDGING_CONTROL_CASES]
    )
    def test_bare_claim_removal_is_five_pass_stable(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected


class TestNullCnRemovalInventedCoOccurrenceShapes:
    """Three more co-occurrence shapes beyond the brief's own five repros,
    each exercising a DIFFERENT one of the null-CN rules: the governance
    name variant of the accountability rule, the "perfect score" rule with
    an embedded working-capital claim, and the star-rating rule with an
    embedded program-expense claim. All three must preserve the true
    claim exactly as written."""

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _CN_BRIDGING_INVENTED_CASES, ids=[c[0] for c in _CN_BRIDGING_INVENTED_CASES]
    )
    def test_true_claim_survives_uncorrupted(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        out = _sanitize(text, metrics)
        assert out == expected

    @pytest.mark.parametrize(
        "name,text,overrides,expected", _CN_BRIDGING_INVENTED_CASES, ids=[c[0] for c in _CN_BRIDGING_INVENTED_CASES]
    )
    def test_true_claim_survival_is_five_pass_stable(self, name, text, overrides, expected):
        metrics = _metrics(**overrides)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected


class TestFundraisingGapsDoNotBridgeOverAnotherMetricClaim:
    """Task G18 audit: the two null-fundraising removal rules (`_fr_gap`,
    `_fr_gap_dollar_first`) have the identical permissive-middle-gap shape
    the brief describes for the CN rules, and were independently confirmed
    vulnerable to the same defect — an embedded true metric claim between
    "fundraising efficiency" and its `$` figure was deleted along with the
    fabrication. `_fr_gap_dollar_first`'s existing bare-comma-boundary-by-
    default design (task G12 round 2) already blocked the comma-joined
    shape, but not a SEMICOLON-joined one (`;` was never added to this
    gap's excluded-boundary set the way task G12 added it to
    `_clause_lead`/`_clause_trail`) — closed as a side effect of the same
    `_other_metric_claim` exclusion, since it fires on the claim's own
    wording, not on which punctuation joins it."""

    def test_phrase_first_rule_preserves_embedded_working_capital(self):
        text = "Fundraising efficiency was mentioned, with an accountability rating of 91.0/100, spending $0.00 to raise every $1."
        metrics = _metrics(fundraising_expenses=None, total_revenue=141_261, cn_accountability_score=91.0)
        out = _sanitize(text, metrics)
        assert out == text

    def test_phrase_first_rule_preservation_is_five_pass_stable(self):
        text = "Fundraising efficiency was mentioned, with an accountability rating of 91.0/100, spending $0.00 to raise every $1."
        metrics = _metrics(fundraising_expenses=None, total_revenue=141_261, cn_accountability_score=91.0)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    def test_dollar_first_rule_preserves_semicolon_joined_working_capital(self):
        text = "The charity spent $0.00; holding 8.3 months of working capital; per $1 raised."
        metrics = _metrics(fundraising_expenses=None, total_revenue=141_261, working_capital_ratio=8.3)
        out = _sanitize(text, metrics)
        assert out == text

    def test_dollar_first_rule_semicolon_preservation_is_five_pass_stable(self):
        text = "The charity spent $0.00; holding 8.3 months of working capital; per $1 raised."
        metrics = _metrics(fundraising_expenses=None, total_revenue=141_261, working_capital_ratio=8.3)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    def test_phrase_first_control_with_no_embedded_claim_still_fully_removed(self):
        """The permissive gap exists so genuine same-claim co-occurrence
        keeps matching — control, no embedded claim to protect."""
        text = "Exceptional fundraising efficiency of $0.00 spent per $1 raised last year."
        metrics = _metrics(fundraising_expenses=None, total_revenue=141_261)
        out = _sanitize(text, metrics)
        assert out == ""

    def test_dollar_first_control_with_no_embedded_claim_still_fully_removed(self):
        text = "The charity spent $0.00 last year per $1 raised."
        metrics = _metrics(fundraising_expenses=None, total_revenue=141_261)
        out = _sanitize(text, metrics)
        assert out == ""


class TestCnBridgingGuardToleratesAHedgeBeforeTheOtherMetricNumber:
    """Hand-probing found a real gap in the backward guard's first version:
    a hedge word between "accountability rating of" and the number
    ("...rating of ROUGHLY 91.0/100...") defeated the anchor the same way
    every other anchor in this function has already had to be hardened
    against (task G14) — the guard's `$`-anchored backward search never
    reached the string end, so it silently declined to protect a real
    accountability value and the CN rule deleted it. Fixed by reusing
    `_hedge_gap` (already bounded, already excludes metric nouns and
    digits) in the guard's own connector, the same fix G14 applied
    everywhere else."""

    def test_hedged_accountability_number_survives(self):
        text = "It scored 87 out of 100, with an accountability rating of roughly 91.0/100, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None, cn_accountability_score=91.0)
        out = _sanitize(text, metrics)
        assert out == "It scored 87 out of 100, with an accountability rating of 91.0/100, from Charity Navigator."

    def test_hedged_accountability_number_survival_is_five_pass_stable(self):
        text = "It scored 87 out of 100, with an accountability rating of roughly 91.0/100, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None, cn_accountability_score=91.0)
        expected = "It scored 87 out of 100, with an accountability rating of 91.0/100, from Charity Navigator."
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == expected


class TestOtherMetricClaimCoversEveryFamilyTheFunctionKnows:
    """Team-lead follow-up review: `_other_metric_claim` was originally
    built from only four families (accountability/financial/working-
    capital/program-expense) even though the CN rules' gap can bridge over
    ANY of this function's other metrics. Audited against every family —
    fundraising, AMAL, founded year, and zakat-eligibility language — and
    confirmed three of the four were ALSO vulnerable (fundraising, AMAL,
    founded year); only zakat needed no fix (it already worked once the
    other three were closed, since `_metric_noun_boundary` — now reused
    wholesale for `_other_metric_noun` — already carried "zakat" as one of
    its existing entries)."""

    def test_fundraising_dollar_phrasing_survives_between_score_and_navigator(self):
        """The exact case from the follow-up review: a bare "$X per $1
        raised" phrasing (no literal word "fundraising" or "efficiency" in
        it at all) used to destroy the true fundraising figure."""
        text = "It scored 87 out of 100, spends $0.05 per $1 raised, and is from Charity Navigator."
        metrics = _metrics(cn_overall_score=None, fundraising_expenses=30_000, total_revenue=600_000)
        out = _sanitize(text, metrics)
        assert out == text

    def test_fundraising_dollar_phrasing_survival_is_five_pass_stable(self):
        text = "It scored 87 out of 100, spends $0.05 per $1 raised, and is from Charity Navigator."
        metrics = _metrics(cn_overall_score=None, fundraising_expenses=30_000, total_revenue=600_000)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    def test_amal_score_survives_between_score_and_navigator(self):
        """AMAL uses the identical "/100" format the null-CN rule's own
        bare-number core anchors on — the same "wrong anchor" hazard as
        accountability/financial, not just a bridging one."""
        text = "It scored 87 out of 100, with an AMAL score of 75/100, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize_amal(text, metrics, amal_score=75)
        assert out == text

    def test_amal_score_survival_is_five_pass_stable(self):
        text = "It scored 87 out of 100, with an AMAL score of 75/100, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None)
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize_amal(passes[-1], metrics, amal_score=75))
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    def test_founded_year_survives_between_score_and_navigator(self):
        text = "It scored 87 out of 100, founded in 1985, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None, founded_year=1985)
        out = _sanitize(text, metrics)
        assert out == text

    def test_founded_year_survival_is_five_pass_stable(self):
        text = "It scored 87 out of 100, founded in 1985, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None, founded_year=1985)
        passes = _five_passes(text, metrics)
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text

    def test_true_zakat_eligible_claim_survives_between_score_and_navigator(self):
        """For a ZAKAT-ELIGIBLE charity (not SADAQAH-ELIGIBLE), a
        zakat-eligible mention is a TRUE claim, not fabricated language to
        strip — a positive case showing the reused `_metric_noun_boundary`
        vocabulary (which already carried "zakat") protects it too."""
        text = "It scored 87 out of 100, is zakat-eligible under its own criteria, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None)
        out = _sanitize(text, metrics, wallet_tag="ZAKAT-ELIGIBLE")
        assert out == text

    def test_true_zakat_eligible_claim_survival_is_five_pass_stable(self):
        text = "It scored 87 out of 100, is zakat-eligible under its own criteria, from Charity Navigator."
        metrics = _metrics(cn_overall_score=None)
        passes = [text]
        for _ in range(5):
            passes.append(_sanitize(passes[-1], metrics, wallet_tag="ZAKAT-ELIGIBLE"))
        assert passes[0] == passes[1] == passes[2] == passes[3] == passes[4] == text


class TestCnSubScoreProvenanceGuard:
    """Task G20: a CN sub-score this pipeline COMPUTED must never be quoted as
    one Charity Navigator PUBLISHED.

    CN publishes a single "Accountability & Finance" beacon. The collector has
    two paths to it: `_extract_nextjs_data_legacy` reads CN's published number
    directly, while `_extract_nextjs_data_new` has no such field and recomputes
    a weighted mean over CN's sub-areas. Stamping the recomputation into prose
    ending "from Charity Navigator" publishes a figure CN never stated. 57 of
    166 live charities carry such a value.

    An explicit `cn_score_provenance` decides it when present. When absent (all
    data crawled before the field existed) the guard falls back to a mechanical
    property rather than a label — CN's published beacon is captured by an
    INTEGER-only regex, so a non-integer value cannot have come from it. That
    fallback only ever withholds a correction it can prove is unpublishable;
    integers are genuinely ambiguous and stay permissive.
    """

    TEXT = "It has an accountability score of 70."
    FIN_TEXT = "It has a financial score of 70."

    def test_explicit_published_provenance_corrects_even_a_non_integer(self):
        """The label beats the heuristic: a real beacon that happens to be
        non-integer must still be usable."""
        metrics = _metrics(cn_accountability_score=85.5, cn_score_provenance="published_beacon")
        assert _sanitize(self.TEXT, metrics) == "It has an accountability score of 85.5/100."

    def test_explicit_computed_provenance_removes_even_an_integer(self):
        """The label beats the heuristic in the other direction too: a
        recomputation landing exactly on an integer is still unpublishable."""
        metrics = _metrics(cn_accountability_score=86, cn_score_provenance="computed_from_subareas")
        assert _sanitize(self.TEXT, metrics) == ""

    def test_absent_provenance_with_integer_still_corrects(self):
        """Permissive fallback — an integer could be a real beacon, so the
        pre-G20 correction behavior is preserved."""
        metrics = _metrics(cn_accountability_score=91.0)
        assert _sanitize(self.TEXT, metrics) == "It has an accountability score of 91.0/100."

    def test_absent_provenance_with_non_integer_removes(self):
        """A non-integer cannot have come from the integer-only beacon regex."""
        metrics = _metrics(cn_accountability_score=85.99555863262657)
        assert _sanitize(self.TEXT, metrics) == ""

    def test_financial_score_is_guarded_the_same_way(self):
        metrics = _metrics(cn_financial_score=85.99555863262657, cn_accountability_score=None)
        assert _sanitize(self.FIN_TEXT, metrics) == ""

    def test_financial_score_integer_still_corrects(self):
        metrics = _metrics(cn_financial_score=85)
        assert _sanitize(self.FIN_TEXT, metrics) == "It has a financial score of 85/100."

    def test_guard_does_not_touch_the_overall_score(self):
        """cn_overall_score has its own single published value and is out of
        scope — a non-integer overall must still be corrected, not removed."""
        metrics = _metrics(cn_overall_score=97.5, cn_accountability_score=None, cn_financial_score=None)
        text = "It scored 88/100 on Charity Navigator."
        assert _sanitize(text, metrics) == "It scored 97.5/100 on Charity Navigator."

    def test_removal_path_is_idempotent_across_five_passes(self):
        metrics = _metrics(cn_accountability_score=85.99555863262657)
        _five_passes(self.TEXT, metrics)

    def test_correction_path_is_idempotent_across_five_passes(self):
        metrics = _metrics(cn_accountability_score=85.5, cn_score_provenance="published_beacon")
        _five_passes(self.TEXT, metrics)


def test_the_mandatory_values_block_carries_no_inline_instructions():
    """EIN 47-5165837 published our own prompt text.

    Its impact explanation contained, verbatim: "(use this exact percentage
    everywhere, and describe it using this exact label — do not restate it as
    the plain 'program expense ratio' if the label says cash-adjusted)". The
    instruction sat in parentheses immediately after the value on the same
    line, so the model copied it along with the value it was attached to. The
    score judge caught it, correctly — that text was one gate away from a
    donor-facing page.

    Instructions now live above the list; every line in it is data.
    """
    body = load_prompt("baseline_narrative", check_version=False).content
    block = body.split("## MANDATORY VALUES", 1)[1].split("If a value is", 1)[0]
    values = [ln for ln in block.splitlines() if ln.strip().startswith("- ")]

    assert values, "the mandatory values list disappeared"
    for line in values:
        assert "(" not in line, f"instruction left inside a value line: {line}"
        assert "use this exact" not in line.lower(), line

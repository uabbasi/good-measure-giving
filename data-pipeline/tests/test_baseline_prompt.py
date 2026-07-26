"""H4: baseline prompt unification — drift guard between template and call site."""

import re
from string import Formatter
from types import SimpleNamespace

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

    def test_strengths_array_entries_are_stripped_too(self):
        metrics = SimpleNamespace(fundraising_expenses=None, total_revenue=604759,
                                  cn_overall_score=None, cn_accountability_score=None,
                                  cn_financial_score=None, program_expense_ratio=None,
                                  working_capital_ratio=None)
        out = sanitize_narrative_metrics(
            {"strengths": ["Exceptional fundraising efficiency of $0.00 spent per $1 raised [1]."]},
            metrics, None)
        assert "$0.00" not in str(out["strengths"])

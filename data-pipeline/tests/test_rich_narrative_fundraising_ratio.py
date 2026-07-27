"""G5: the third call site that divides fundraising_expenses / total_revenue
and rendered it with :.2f. G4 fixed the other two (baseline.py's prompt-kwargs
builder and its narrative sanitizer); this is the rich-narrative prompt's
"MANDATORY VALUES" block, which independently computed the same ratio inline.

For 10 real charities the true ratio is tiny but nonzero (e.g. $241,666 /
$79.6M = $0.003 per $1), and :.2f rounds that to "$0.00" -- combined with the
surrounding "you MUST use the EXACT values below" instruction, that tells the
LLM to state, verbatim, that the charity spends nothing to raise a dollar.
"""

from types import SimpleNamespace

from src.services.rich_narrative_generator import RichNarrativeGenerator


def _generator():
    return object.__new__(RichNarrativeGenerator)


def _financials(total_revenue=149_888_609, fundraising_expenses=None, program_expense_ratio=0.83):
    return SimpleNamespace(
        total_revenue=total_revenue,
        program_expense_ratio=program_expense_ratio,
        fundraising_expenses=fundraising_expenses,
    )


class _FakeBundle:
    """charity_bundle stand-in: only `financials` is real, everything else
    the formatter probes (ratings, trends, etc.) reads back as falsy."""

    def __init__(self, financials):
        self.financials = financials

    def __getattr__(self, name):
        return None


def _charity_bundle(financials):
    return _FakeBundle(financials)


_BASELINE = {"amal_score": 68}


class TestRichNarrativeFundraisingRatioIsNotRenderedAsZero:
    def test_tiny_but_real_ratio_renders_as_less_than_a_cent(self):
        """$241,666 / $79.6M = $0.003 per $1 -- real, and not zero."""
        gen = _generator()
        bundle = _charity_bundle(_financials(total_revenue=79_600_000, fundraising_expenses=241_666))

        text = gen._format_charity_data(_BASELINE, bundle, None)

        assert "Fundraising Efficiency: <$0.01 per $1 raised (use this exact value)" in text
        assert "$0.00" not in text

    def test_genuine_zero_still_renders_as_zero(self):
        gen = _generator()
        bundle = _charity_bundle(_financials(total_revenue=100_000, fundraising_expenses=0))

        text = gen._format_charity_data(_BASELINE, bundle, None)

        assert "Fundraising Efficiency: $0.00 per $1 raised (use this exact value)" in text

    def test_normal_ratio_is_unchanged(self):
        gen = _generator()
        bundle = _charity_bundle(_financials(total_revenue=100_000, fundraising_expenses=10_000))

        text = gen._format_charity_data(_BASELINE, bundle, None)

        assert "Fundraising Efficiency: $0.10 per $1 raised (use this exact value)" in text

    def test_no_revenue_omits_the_line_entirely(self):
        gen = _generator()
        bundle = _charity_bundle(_financials(total_revenue=0, fundraising_expenses=10_000))

        text = gen._format_charity_data(_BASELINE, bundle, None)

        assert "Fundraising Efficiency" not in text

    def test_no_fundraising_expenses_omits_the_line_entirely(self):
        gen = _generator()
        bundle = _charity_bundle(_financials(total_revenue=100_000, fundraising_expenses=None))

        text = gen._format_charity_data(_BASELINE, bundle, None)

        assert "Fundraising Efficiency" not in text

    def test_reuses_the_shared_helper_not_a_third_implementation(self):
        """Pins the call site to baseline._fundraising_ratio_str so a future
        change to the shared helper (or its rendering vocabulary) can't
        silently diverge here again."""
        import baseline

        calls = []
        original = baseline._fundraising_ratio_str

        def spy(*args):
            calls.append(args)
            return original(*args)

        baseline._fundraising_ratio_str = spy
        try:
            gen = _generator()
            bundle = _charity_bundle(_financials(total_revenue=79_600_000, fundraising_expenses=241_666))
            gen._format_charity_data(_BASELINE, bundle, None)
        finally:
            baseline._fundraising_ratio_str = original

        assert calls == [(241_666, 79_600_000)]

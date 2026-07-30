"""A different fiscal year's figure is not a contradiction.

The factual judge blocked two charities in this run for choosing the most recent
fiscal year, and in both cases its own message contained the corroborating evidence:

  Amoud Foundation (75-2882187): "The narrative states $11,142,566 in total revenue
  for FY2024, but the Form 990 (2023) shows $9,535,194 for FY2023 AND CHARITY
  NAVIGATOR SHOWS $11,142,566 FOR FY2024."

  Rahima Foundation (77-0442850): "narrative states $4,100,385 but the Form 990
  (2023) reports $4,006,022" -- where CN (FY2024) and form990_grants (tax_year 2024)
  both independently report $4,100,385.

ProPublica's latest filing routinely lags Charity Navigator by a year, so the same
charity legitimately has different revenue in FY2023 and FY2024. The judge compared
across years and called the difference a contradiction.

This is NOT the flake that CONSENSUS_ROLLS fixes: consensus filters a lone
dissenting roll, but every roll makes this same reasoning error, so a majority
agrees on a wrong answer. The prompt had no fiscal-year guidance at all -- unlike
the wallet-tag case, where the codebase concluded "the answer is not more prompt
text" precisely because the prompt already named the correct pair.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PROMPT = Path(__file__).parent.parent / "src" / "judges" / "prompts" / "factual_judge.txt"


class TestTheFiscalYearRuleIsStated:
    def _text(self):
        return PROMPT.read_text()

    def test_the_prompt_tells_the_judge_to_compare_like_for_like_on_fiscal_year(self):
        text = self._text().lower()
        assert "fiscal year" in text, "the judge needs explicit fiscal-year guidance"
        assert "like-for-like" in text or "same year" in text

    def test_the_rule_lives_in_the_do_not_report_as_errors_section(self):
        """Guidance the model must act on belongs with the other suppressions,
        not buried in the tolerance list."""
        text = self._text()
        section = text.split("## CRITICAL: Do NOT Report as Errors", 1)
        assert len(section) == 2, "the suppression section must still exist"
        after = section[1].split("##", 1)[0]
        assert "fiscal year" in after.lower(), (
            "the fiscal-year rule must sit inside the Do-NOT-report section"
        )

    def test_the_observed_amoud_numbers_are_named_as_the_worked_example(self):
        """A concrete example is what makes this stick; keep the real one."""
        text = self._text()
        assert "11,142,566" in text and "9,535,194" in text

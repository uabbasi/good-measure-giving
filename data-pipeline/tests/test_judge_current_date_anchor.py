"""A judge doing age arithmetic needs to be told what "now" is.

format_prompt substituted charity_name, ein, narrative, scores, citations and
context — nothing that dates the run. So any claim of the form "this data is N
years old" was checked against whatever year the model assumed, and MAS Boston
(20-1799252) was blocked for it:

    "The narrative states the organization's financial data is 8 years old,
     but the latest available financial data is from FY2018, making it 6 years
     old as of 2024."

FY2018 is 8 years before 2026. The narrative was right and the judge was
anchored to 2024. Worse than wrong, it is *unstable*: the same narrative judged
by a different model, or the same model later, gets a different verdict on text
that never changed — the opposite of the determinism these gates exist to give.

The anchor is passed in rather than described, because a prompt cannot know the
date it will run on.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.base_judge import BaseJudge


class TestTheAnchorIsAvailableToEveryJudge:
    def test_current_date_is_substituted(self):
        template = "Today is {current_date}. Verify: {narrative}"
        out = BaseJudge.apply_prompt_substitutions(
            template, {"narrative": {"text": "eight years old"}}, {}
        )
        assert date.today().isoformat() in out
        assert "{current_date}" not in out

    def test_current_year_is_substituted(self):
        out = BaseJudge.apply_prompt_substitutions("year={current_year}", {}, {})
        assert out == f"year={date.today().year}"

    def test_the_existing_substitutions_still_work(self):
        out = BaseJudge.apply_prompt_substitutions(
            "{charity_name} / {ein}", {"name": "MAS Boston Society", "ein": "20-1799252"}, {}
        )
        assert out == "MAS Boston Society / 20-1799252"

    def test_a_template_that_never_mentions_the_date_is_unchanged(self):
        out = BaseJudge.apply_prompt_substitutions("{charity_name} only", {"name": "X"}, {})
        assert out == "X only"


class TestTheFactualPromptActuallyUsesIt:
    PROMPT = Path(__file__).parent.parent / "src" / "judges" / "prompts" / "factual_judge.txt"

    def test_the_prompt_carries_the_placeholder(self):
        """An anchor nothing references is an anchor that does not hold."""
        assert "{current_date}" in self.PROMPT.read_text()

    def test_it_tells_the_judge_to_date_its_arithmetic_from_that(self):
        text = self.PROMPT.read_text().lower()
        assert "years old" in text or "age" in text

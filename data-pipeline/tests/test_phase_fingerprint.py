"""Fingerprint coverage: the file lists in PHASE_CODE_FILES must track where
prompt-bearing logic actually lives, or code changes silently produce a
fleet-wide cache hit instead of a re-run.
"""

from pathlib import Path

from src.utils.phase_fingerprint import PHASE_CODE_FILES


def test_baseline_fingerprint_covers_prompt_and_constant_modules():
    baseline = set(PHASE_CODE_FILES["baseline"])
    assert "src/llm/prompt_loader.py" in baseline, "baseline prompt calls data_vintage_note()"
    assert "src/constants.py" in baseline, "drives _recency_factor in v2_scorers"
    assert "src/utils/fiscal_year.py" in baseline, "shared fiscal-year age arithmetic"


def test_rich_fingerprint_covers_what_the_rich_prompt_injects():
    rich = set(PHASE_CODE_FILES["rich"])
    assert "src/llm/prompt_loader.py" in rich, "rich prompt calls data_vintage_note()"
    assert "src/scorers/v2_scorers.py" in rich, "rich prompt calls score_band_label()"


def test_every_listed_fingerprint_file_exists():
    """A typo'd path silently contributes nothing to the hash."""
    root = Path(__file__).parent.parent
    missing = [f for files in PHASE_CODE_FILES.values() for f in files if not (root / f).exists()]
    assert missing == []

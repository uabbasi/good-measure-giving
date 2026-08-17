"""Fingerprint coverage: the file lists in PHASE_CODE_FILES must track where
prompt-bearing logic actually lives, or code changes silently produce a
fleet-wide cache hit instead of a re-run.
"""

import ast
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


def test_extract_fingerprint_covers_every_validator_its_collectors_import():
    """A new validator module is easy to add and easy to forget listing here.

    ad4c252 added src/validators/form990_governance_validator.py and imported
    it from form990_grants.py without listing it; the omission was masked
    because the collector itself changed in the same commit, so a later
    governance-only edit would have hit a fleet-wide stale cache.
    """
    root = Path(__file__).parent.parent
    listed = set(PHASE_CODE_FILES["extract"])
    imported: set[str] = set()

    for rel in PHASE_CODE_FILES["extract"]:
        if not rel.startswith("src/collectors/"):
            continue
        tree = ast.parse((root / rel).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "validators" in node.module:
                module = node.module.split("validators.")[-1]
                imported.add(f"src/validators/{module}.py")

    assert imported - listed == set()


def test_every_listed_fingerprint_file_exists():
    """A typo'd path silently contributes nothing to the hash."""
    root = Path(__file__).parent.parent
    missing = [f for files in PHASE_CODE_FILES.values() for f in files if not (root / f).exists()]
    assert missing == []

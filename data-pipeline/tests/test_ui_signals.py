"""Tests for qualitative ui_signals_v1 derivation and calibration reporting."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from export import (  # noqa: E402
    _build_calibration_report,
    _compute_config_hash,
    _derive_ui_signals_v1,
    _load_ui_signals_config,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.mark.parametrize(
    "fixture_name",
    [
        "ui_signals_standard.json",
        "ui_signals_new_org.json",
        "ui_signals_research_policy.json",
    ],
)
def test_ui_signals_snapshot_tracks(fixture_name: str):
    cfg = _load_ui_signals_config()
    config_hash = _compute_config_hash(cfg)
    fixture = _load_fixture(fixture_name)

    derived = _derive_ui_signals_v1(
        charity=fixture["charity"],
        charity_data=fixture["charity_data"],
        evaluation=fixture["evaluation"],
        cfg=cfg,
        config_hash=config_hash,
    )

    assert derived is not None
    assert derived["schema_version"] == cfg["schema_version"]
    assert derived["config_version"] == cfg["config_version"]
    assert derived["config_hash"] == config_hash

    expected = fixture["expected"]
    assert derived["assessment_label"] == expected["assessment_label"]
    assert derived["archetype_label"] == expected["archetype_label"]
    assert derived["evidence_stage"] == expected["evidence_stage"]
    assert derived["recommendation_cue"] == expected["recommendation_cue"]
    assert derived["signal_states"] == expected["signal_states"]


def test_calibration_report_warning_and_hard_fail_thresholds():
    cfg = _load_ui_signals_config()
    config_hash = _compute_config_hash(cfg)

    # 12 summaries total: 3 missing ui_signals_v1 (25% fallback) => hard fail
    summaries = [
        {"ein": f"00-{i:07d}", "amalScore": 60, "evaluationTrack": "STANDARD"} for i in range(3)
    ]
    valid_ui = {
        "schema_version": cfg["schema_version"],
        "config_version": cfg["config_version"],
        "config_hash": config_hash,
        "assessment_label": "Promising",
        "evidence_stage": "Established",
        "recommendation_cue": "Good Match",
        "signal_states": {
            "evidence": "Strong",
            "financial_health": "Moderate",
            "donor_fit": "Moderate",
            "risk": "Moderate",
        },
        "used_fallback": False,
    }
    for i in range(3, 12):
        summaries.append(
            {
                "ein": f"00-{i:07d}",
                "amalScore": 60,
                "evaluationTrack": "STANDARD",
                "ui_signals_v1": valid_ui,
            }
        )

    report = _build_calibration_report(
        summaries=summaries,
        cfg=cfg,
        config_hash=config_hash,
        source_commit="abc123",
    )

    assert report["fallback"]["rate_pct"] == 25.0
    assert report["guardrail_status"]["hard_fail"] is True
    assert any("Fallback rate" in reason for reason in report["guardrail_status"]["reasons"])
    assert any("High fallback rate" in warning for warning in report["warnings"])

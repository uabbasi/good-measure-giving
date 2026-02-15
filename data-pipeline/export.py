"""
Phase 6: Export - Export charity data to website JSON files.

Exports two types of files:
1. charities.json - Summary list for browse/search
2. charities/charity-{ein}.json - Individual detail files

Usage:
    uv run python export.py --ein 95-4453134
    uv run python export.py --charities pilot_charities.txt
    uv run python export.py  # All charities with evaluations
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from src.db import (
    CharityDataRepository,
    CharityRepository,
    EvaluationRepository,
    RawDataRepository,
)
from src.db.dolt_client import dolt
from src.judges.base_judge import JudgeConfig
from src.judges.export_quality_judge import ExportQualityJudge
from src.judges.schemas.verdict import Severity

# Output directory
WEBSITE_DATA_DIR = Path(__file__).parent.parent / "website" / "data"
WEBSITE_PUBLIC_DATA_DIR = Path(__file__).parent.parent / "website" / "public" / "data"
PILOT_CHARITIES_FILE = Path(__file__).parent / "pilot_charities.txt"
UI_SIGNALS_CONFIG_FILE = Path(__file__).parent / "config" / "ui_signals.yaml"

# Beacons to exclude (not really awards)
# - "Profile Managed" = just means nonprofit manages their CN profile
# - "Encompass Award" = was incorrectly extracted; "Encompass" is just CN's rating system name
EXCLUDED_BEACONS = {"Profile Managed", "Encompass Award"}

# Valid tier values
VALID_TIERS = {"baseline", "rich", "hidden"}
_RISK_SIGNAL_ORDER = ("Strong", "Moderate", "Limited")


def _load_ui_signals_config() -> dict[str, Any]:
    """Load canonical qualitative UI signal policy from YAML."""
    if not UI_SIGNALS_CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing UI signals config: {UI_SIGNALS_CONFIG_FILE}")
    with open(UI_SIGNALS_CONFIG_FILE) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("ui_signals.yaml must contain a top-level mapping")
    return cfg


def _compute_config_hash(cfg: dict[str, Any]) -> str:
    """Compute deterministic config hash for auditability."""
    canonical = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _mirror_export_to_public_data(output_dir: Path) -> None:
    """Mirror website/data exports to website/public/data for the frontend runtime."""
    if output_dir.resolve() != WEBSITE_DATA_DIR.resolve():
        return
    WEBSITE_PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(output_dir, WEBSITE_PUBLIC_DATA_DIR, dirs_exist_ok=True)


def _safe_upper(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned.upper() if cleaned else None
    return None


def _normalize_confidence_badge(raw_badge: Any) -> str:
    badge = _safe_upper(raw_badge)
    if badge in {"HIGH", "MEDIUM", "LOW"}:
        return badge
    if badge in {"MODERATE", "MID"}:
        return "MEDIUM"
    if badge in {"INSUFFICIENT_DATA", "NONE", "UNKNOWN", None}:
        return "LOW"
    return "LOW"


def _extract_score_details(evaluation: dict | None) -> dict[str, Any]:
    if not evaluation:
        return {}
    score_details = evaluation.get("score_details")
    return score_details if isinstance(score_details, dict) else {}


def _extract_component(
    score_details: dict[str, Any], dimension: str, candidates: tuple[str, ...]
) -> dict[str, Any] | None:
    details = score_details.get(dimension)
    if not isinstance(details, dict):
        return None
    components = details.get("components")
    if not isinstance(components, list):
        return None
    candidate_lc = {c.lower() for c in candidates}
    for component in components:
        if not isinstance(component, dict):
            continue
        name = component.get("name")
        if isinstance(name, str) and name.strip().lower() in candidate_lc:
            return component
    return None


def _component_ratio(component: dict[str, Any] | None) -> float | None:
    if not isinstance(component, dict):
        return None
    scored = component.get("scored")
    possible = component.get("possible")
    try:
        scored_f = float(scored)
        possible_f = float(possible)
    except (TypeError, ValueError):
        return None
    if possible_f <= 0:
        return None
    return max(0.0, min(1.0, scored_f / possible_f))


def _extract_third_party_evaluated(charity_data: dict | None, score_details: dict[str, Any]) -> bool:
    if isinstance(charity_data, dict) and charity_data.get("third_party_evaluated") is True:
        return True
    evidence = score_details.get("evidence")
    if isinstance(evidence, dict) and evidence.get("third_party_evaluated") is True:
        return True
    impact_ev = _extract_component(score_details, "impact", ("Evidence & Outcomes",))
    if isinstance(impact_ev, dict):
        ev = impact_ev.get("evidence")
        if isinstance(ev, str) and "VERIFIED" in ev.upper():
            return True
    return False


def _extract_alignment_score(evaluation: dict | None, score_details: dict[str, Any]) -> float:
    alignment = score_details.get("alignment")
    if isinstance(alignment, dict):
        score = alignment.get("score")
        if isinstance(score, (int, float)):
            return float(score)
    confidence_scores = evaluation.get("confidence_scores") if isinstance(evaluation, dict) else None
    if isinstance(confidence_scores, dict):
        score = confidence_scores.get("alignment")
        if isinstance(score, (int, float)):
            return float(score)
    return 0.0


def _extract_donor_fit_level(score_details: dict[str, Any]) -> str:
    alignment = score_details.get("alignment")
    if isinstance(alignment, dict):
        level = _safe_upper(alignment.get("muslim_donor_fit_level"))
        if level in {"HIGH", "MODERATE", "LOW"}:
            return level
        if level in {"MEDIUM", "MID"}:
            return "MODERATE"
    return "LOW"


def _extract_risk_deduction(score_details: dict[str, Any]) -> float:
    if isinstance(score_details.get("risk_deduction"), (int, float)):
        return float(score_details["risk_deduction"])
    risks = score_details.get("risks")
    if isinstance(risks, dict) and isinstance(risks.get("total_deduction"), (int, float)):
        return float(risks["total_deduction"])
    return 0.0


def _extract_governance_ratio(score_details: dict[str, Any]) -> float | None:
    governance = _extract_component(score_details, "impact", ("Governance",))
    ratio = _component_ratio(governance)
    if ratio is not None:
        return ratio
    credibility = _extract_component(score_details, "credibility", ("Governance",))
    return _component_ratio(credibility)


def _derive_archetype_label(archetype_code: str | None, cfg: dict[str, Any]) -> str:
    default = "General Profile"
    if not archetype_code:
        return default
    mapping = cfg.get("archetype_labels")
    if isinstance(mapping, dict):
        label = mapping.get(archetype_code)
        if isinstance(label, str) and label.strip():
            return label
    return archetype_code.replace("_", " ").title()


def _derive_evidence_signal_state(score_details: dict[str, Any], cfg: dict[str, Any]) -> str:
    signal_cfg = (cfg.get("signals") or {}).get("evidence", {})
    strong_ratio = float(signal_cfg.get("strong_ratio", 0.70))
    moderate_ratio_min = float(signal_cfg.get("moderate_ratio_min", 0.40))
    strong_grades = {str(g).upper() for g in signal_cfg.get("strong_grades", ["A", "B"])}
    moderate_grades = {str(g).upper() for g in signal_cfg.get("moderate_grades", ["C"])}

    legacy_ev = score_details.get("evidence")
    if isinstance(legacy_ev, dict):
        grade = _safe_upper(legacy_ev.get("evidence_grade"))
        if grade in strong_grades:
            return "Strong"
        if grade in moderate_grades:
            return "Moderate"
        if grade:
            return "Limited"

    evidence_component = _extract_component(score_details, "impact", ("Evidence & Outcomes",))
    ratio = _component_ratio(evidence_component)
    if ratio is None:
        return "Limited"
    if ratio >= strong_ratio:
        return "Strong"
    if ratio >= moderate_ratio_min:
        return "Moderate"
    return "Limited"


def _derive_financial_signal_state(score_details: dict[str, Any], cfg: dict[str, Any]) -> str:
    signal_cfg = (cfg.get("signals") or {}).get("financial_health", {})
    strong_min = float(signal_cfg.get("strong_min", 0.70))
    moderate_min = float(signal_cfg.get("moderate_min", 0.40))

    financial = _component_ratio(_extract_component(score_details, "impact", ("Financial Health",)))
    program = _component_ratio(_extract_component(score_details, "impact", ("Program Ratio",)))

    if financial is None or program is None:
        return "Limited"
    if financial >= strong_min and program >= strong_min:
        return "Strong"
    if financial < moderate_min or program < moderate_min:
        return "Limited"
    return "Moderate"


def _derive_donor_fit_signal_state(evaluation: dict | None, score_details: dict[str, Any], cfg: dict[str, Any]) -> str:
    signal_cfg = (cfg.get("signals") or {}).get("donor_fit", {})
    strong_alignment_min = float(signal_cfg.get("strong_alignment_min", 35))
    moderate_alignment_min = float(signal_cfg.get("moderate_alignment_min", 25))

    donor_fit = _extract_donor_fit_level(score_details)
    alignment = _extract_alignment_score(evaluation, score_details)

    if donor_fit == "HIGH" and alignment >= strong_alignment_min:
        return "Strong"
    if donor_fit == "MODERATE" or alignment >= moderate_alignment_min:
        return "Moderate"
    return "Limited"


def _derive_risk_signal_state(score_details: dict[str, Any], cfg: dict[str, Any]) -> str:
    risk_cfg = (cfg.get("signals") or {}).get("risk", {})
    governance_strong_min = float(risk_cfg.get("governance_strong_min", 0.60))
    governance_moderate_min = float(risk_cfg.get("governance_moderate_min", 0.40))
    deduction_moderate_min = float(risk_cfg.get("deduction_moderate_min", -3))
    deduction_moderate_max = float(risk_cfg.get("deduction_moderate_max", -1))
    deduction_limited_max = float(risk_cfg.get("deduction_limited_max", -4))

    deduction = _extract_risk_deduction(score_details)
    governance_ratio = _extract_governance_ratio(score_details)

    if deduction == 0 and governance_ratio is not None and governance_ratio >= governance_strong_min:
        return "Strong"
    if deduction <= deduction_limited_max or (governance_ratio is not None and governance_ratio < governance_moderate_min):
        return "Limited"
    if deduction_moderate_min <= deduction <= deduction_moderate_max or (
        governance_ratio is not None and governance_moderate_min <= governance_ratio < governance_strong_min
    ):
        return "Moderate"
    return "Moderate"


def _risk_level_from_signal(risk_signal: str) -> str:
    if risk_signal == "Strong":
        return "LOW"
    if risk_signal == "Moderate":
        return "MODERATE"
    return "HIGH"


def _derive_evidence_stage(
    confidence_badge: str,
    founded_year: int | None,
    third_party_evaluated: bool,
    evaluation_track: str | None,
    evidence_signal: str,
) -> str:
    current_year = datetime.now(UTC).year
    years_operating = current_year - founded_year if isinstance(founded_year, int) and founded_year > 0 else None

    if confidence_badge == "HIGH" and bool(years_operating and years_operating >= 10) and third_party_evaluated:
        return "Verified"
    if confidence_badge == "HIGH" or (confidence_badge == "MEDIUM" and evidence_signal == "Strong"):
        return "Established"
    if confidence_badge == "MEDIUM":
        return "Building"
    if confidence_badge == "LOW" or _safe_upper(evaluation_track) == "NEW_ORG":
        return "Early"
    return "Early"


def _derive_recommendation_cue(score: float, confidence_badge: str, risk_level: str, cfg: dict[str, Any]) -> str:
    cue_cfg = cfg.get("recommendation_cue", {})
    limited_max = float((cue_cfg.get("limited_match") or {}).get("score_max_exclusive", 30))
    strong_min = float((cue_cfg.get("strong_match") or {}).get("score_min", 75))
    good_min = float((cue_cfg.get("good_match") or {}).get("score_min", 60))

    # Precedence: Limited -> Strong -> Good -> Mixed Signals
    if score < limited_max or (confidence_badge == "LOW" and risk_level == "HIGH"):
        return "Limited Match"
    if score >= strong_min and confidence_badge == "HIGH" and risk_level == "LOW":
        return "Strong Match"
    if score >= good_min and confidence_badge in {"HIGH", "MEDIUM"} and risk_level in {"LOW", "MODERATE"}:
        return "Good Match"
    return "Mixed Signals"


def _derive_assessment_label(cue: str, stage: str) -> str:
    if cue == "Limited Match" and stage in {"Verified", "Established"}:
        return "Well Documented Low Score"
    if cue == "Strong Match" and stage in {"Verified", "Established"}:
        return "High Conviction"
    if cue == "Good Match" and stage in {"Verified", "Established", "Building"}:
        return "Promising"
    if cue == "Mixed Signals":
        return "Context Dependent"
    return "Limited Basis"


def _build_recommendation_rationale(cue: str, signals: dict[str, str], stage: str) -> str:
    if cue == "Strong Match":
        return "Strong donor fit, low risk profile, and credible supporting evidence for outcomes."
    if cue == "Good Match":
        return "Good donor alignment with manageable risk. Evidence quality is solid but still evolving in places."
    if cue == "Limited Match":
        if stage in {"Verified", "Established"}:
            return "Evidence quality is well documented, but results are weak on the current rubric dimensions."
        return "Limited match due to weaker results and/or higher uncertainty; review methodology details before deciding."
    return "Context dependent profile. Consider cause fit, risk profile, and evidence maturity before deciding."


def _derive_ui_signals_v1(
    charity: dict[str, Any], charity_data: dict | None, evaluation: dict | None, cfg: dict[str, Any], config_hash: str
) -> dict[str, Any] | None:
    """Derive donor-facing qualitative signals from existing scored fields."""
    if not evaluation:
        return None

    score_details = _extract_score_details(evaluation)
    score = float(evaluation.get("amal_score") or 0)
    confidence_badge = _normalize_confidence_badge(
        (score_details.get("data_confidence") or {}).get("badge")
        or evaluation.get("confidence_tier")
    )

    archetype_code = _safe_upper(_extract_archetype(charity_data) or _extract_rubric_archetype(evaluation))
    archetype_label = _derive_archetype_label(archetype_code, cfg)

    signal_states = {
        "evidence": _derive_evidence_signal_state(score_details, cfg),
        "financial_health": _derive_financial_signal_state(score_details, cfg),
        "donor_fit": _derive_donor_fit_signal_state(evaluation, score_details, cfg),
        "risk": _derive_risk_signal_state(score_details, cfg),
    }
    risk_level = _risk_level_from_signal(signal_states["risk"])

    founded_year = charity_data.get("founded_year") if isinstance(charity_data, dict) else None
    evaluation_track = charity_data.get("evaluation_track") if isinstance(charity_data, dict) else None
    third_party_evaluated = _extract_third_party_evaluated(charity_data, score_details)
    evidence_stage = _derive_evidence_stage(
        confidence_badge=confidence_badge,
        founded_year=founded_year if isinstance(founded_year, int) else None,
        third_party_evaluated=third_party_evaluated,
        evaluation_track=evaluation_track if isinstance(evaluation_track, str) else None,
        evidence_signal=signal_states["evidence"],
    )

    recommendation_cue = _derive_recommendation_cue(score, confidence_badge, risk_level, cfg)
    assessment_label = _derive_assessment_label(recommendation_cue, evidence_stage)
    recommendation_rationale = _build_recommendation_rationale(recommendation_cue, signal_states, evidence_stage)

    fallback_reasons: list[str] = []
    if not score_details:
        fallback_reasons.append("missing_score_details")
    if not archetype_code:
        fallback_reasons.append("missing_archetype")
    if _extract_governance_ratio(score_details) is None:
        fallback_reasons.append("missing_governance_component")

    return {
        "schema_version": str(cfg.get("schema_version", "1.0.0")),
        "config_version": str(cfg.get("config_version", "unknown")),
        "config_hash": config_hash,
        "assessment_label": assessment_label,
        "archetype_code": archetype_code,
        "archetype_label": archetype_label,
        "evidence_stage": evidence_stage,
        "signal_states": signal_states,
        "recommendation_cue": recommendation_cue,
        "recommendation_rationale": recommendation_rationale,
        "used_fallback": len(fallback_reasons) > 0,
        "fallback_reasons": fallback_reasons or None,
    }


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _build_calibration_report(
    summaries: list[dict[str, Any]], cfg: dict[str, Any], config_hash: str, source_commit: str | None
) -> dict[str, Any]:
    """Build deterministic calibration report from exported summaries."""
    total = len(summaries)
    cue_dist: dict[str, int] = {}
    stage_dist: dict[str, int] = {}
    label_dist: dict[str, int] = {}
    signal_dist: dict[str, dict[str, int]] = {
        "evidence": {},
        "financial_health": {},
        "donor_fit": {},
        "risk": {},
    }
    by_track: dict[str, dict[str, int]] = {}
    missing_signals = {k: 0 for k in signal_dist}
    fallback_count = 0
    near_threshold_count = 0
    near_threshold_bounds = (30.0, 60.0, 75.0)

    for summary in summaries:
        ui = summary.get("ui_signals_v1")
        if not isinstance(ui, dict):
            fallback_count += 1
            continue

        if ui.get("used_fallback") is True:
            fallback_count += 1

        cue = ui.get("recommendation_cue")
        stage = ui.get("evidence_stage")
        label = ui.get("assessment_label")

        if isinstance(cue, str):
            cue_dist[cue] = cue_dist.get(cue, 0) + 1
        if isinstance(stage, str):
            stage_dist[stage] = stage_dist.get(stage, 0) + 1
        if isinstance(label, str):
            label_dist[label] = label_dist.get(label, 0) + 1

        states = ui.get("signal_states")
        if isinstance(states, dict):
            for key in signal_dist:
                value = states.get(key)
                if isinstance(value, str):
                    signal_dist[key][value] = signal_dist[key].get(value, 0) + 1
                else:
                    missing_signals[key] += 1
        else:
            for key in signal_dist:
                missing_signals[key] += 1

        track = summary.get("evaluationTrack") if isinstance(summary.get("evaluationTrack"), str) else "UNKNOWN"
        if track not in by_track:
            by_track[track] = {"count": 0}
        by_track[track]["count"] += 1
        if isinstance(cue, str):
            key = f"cue::{cue}"
            by_track[track][key] = by_track[track].get(key, 0) + 1
        if isinstance(stage, str):
            key = f"stage::{stage}"
            by_track[track][key] = by_track[track].get(key, 0) + 1

        score = summary.get("amalScore")
        if isinstance(score, (int, float)) and any(abs(float(score) - b) <= 2 for b in near_threshold_bounds):
            near_threshold_count += 1

    fallback_rate = _safe_pct(fallback_count, total)
    near_threshold_rate = _safe_pct(near_threshold_count, total)

    calibration_cfg = (cfg.get("calibration") or {}).get("warning_thresholds", {})
    fallback_warn = float(calibration_cfg.get("fallback_rate_warn_pct", 5))
    cue_skew_warn = float(calibration_cfg.get("cue_skew_warn_pct", 60))
    missing_warn = float(calibration_cfg.get("missing_signal_warn_pct", 3))
    near_threshold_warn = float(calibration_cfg.get("near_threshold_warn_pct", 20))
    stage_concentration_warn = float(calibration_cfg.get("stage_concentration_warn_pct", 50))
    hard_fail_cfg = calibration_cfg.get("hard_fail", {})
    fallback_hard_fail = float(hard_fail_cfg.get("fallback_rate_pct", 20))
    missing_hard_fail = float(hard_fail_cfg.get("missing_signal_pct", 10))

    warnings: list[str] = []
    if fallback_rate > fallback_warn:
        warnings.append(f"High fallback rate — {fallback_count} charities using client-side derivation")

    for cue, count in cue_dist.items():
        pct = _safe_pct(count, total)
        if pct > cue_skew_warn:
            warnings.append(f"Cue skew — '{cue}' assigned to {pct}% of charities")

    for signal_name, missing in missing_signals.items():
        pct = _safe_pct(missing, total)
        if pct > missing_warn:
            warnings.append(f"Missing signal — '{signal_name}' absent for {missing} charities")

    if near_threshold_rate > near_threshold_warn:
        warnings.append(f"Boundary clustering — {near_threshold_rate}% near cue thresholds")

    for stage, count in stage_dist.items():
        pct = _safe_pct(count, total)
        if pct > stage_concentration_warn:
            warnings.append(f"Stage concentration — '{stage}' covers {pct}% of charities")

    hard_fail_reasons: list[str] = []
    if fallback_rate > fallback_hard_fail:
        hard_fail_reasons.append(
            f"Fallback rate {fallback_rate}% exceeds hard limit {fallback_hard_fail}%"
        )
    for signal_name, missing in missing_signals.items():
        pct = _safe_pct(missing, total)
        if pct > missing_hard_fail:
            hard_fail_reasons.append(
                f"Missing signal {signal_name} rate {pct}% exceeds hard limit {missing_hard_fail}%"
            )

    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "dolt_commit": source_commit,
            "schema_version": str(cfg.get("schema_version", "1.0.0")),
            "config_version": str(cfg.get("config_version", "unknown")),
            "config_hash": config_hash,
            "total_charities": total,
        },
        "distributions": {
            "assessment_label": label_dist,
            "evidence_stage": stage_dist,
            "recommendation_cue": cue_dist,
            "signal_states": signal_dist,
        },
        "by_evaluation_track": by_track,
        "fallback": {
            "count": fallback_count,
            "rate_pct": fallback_rate,
        },
        "missing_signals": {
            key: {
                "count": value,
                "rate_pct": _safe_pct(value, total),
            }
            for key, value in missing_signals.items()
        },
        "near_threshold": {
            "count": near_threshold_count,
            "rate_pct": near_threshold_rate,
            "boundaries": list(near_threshold_bounds),
        },
        "warnings": warnings,
        "guardrail_status": {
            "hard_fail": len(hard_fail_reasons) > 0,
            "reasons": hard_fail_reasons,
        },
    }


def run_export_quality_check(summary: dict[str, Any]) -> tuple[bool, list[dict]]:
    """Run deterministic export quality checks against summary payload."""
    try:
        judge = ExportQualityJudge(JudgeConfig(sample_rate=1.0))
        verdict = judge.validate(summary, {})
        issues = [
            {
                "judge": verdict.judge_name,
                "severity": issue.severity.value,
                "field": issue.field,
                "message": issue.message,
            }
            for issue in verdict.issues
        ]
        has_errors = any(issue.severity == Severity.ERROR for issue in verdict.issues)
        return not has_errors, issues
    except Exception as e:
        return True, [
            {
                "judge": "export_quality",
                "severity": "warning",
                "field": "judge_execution",
                "message": f"Quality judge failed: {str(e)[:100]}",
            }
        ]


def _determine_tier(evaluation: dict | None) -> str:
    """Determine charity tier based on narrative availability.

    E-002: Extracted to avoid duplicate logic in summary/detail builders.

    Returns:
        'rich' if rich_narrative exists
        'baseline' if only baseline_narrative exists
        'hidden' if no narrative yet
    """
    if not evaluation:
        return "hidden"
    if evaluation.get("rich_narrative"):
        return "rich"
    if evaluation.get("baseline_narrative"):
        return "baseline"
    return "hidden"


def _build_awards(
    ein: str, cn_profile: dict, candid_profile: dict, bbb_profile: dict, cn_is_rated: bool
) -> dict | None:
    """Build awards/recognition data from CN, Candid, and BBB.

    Only includes CN beacons when cn_is_rated is True to filter out
    unreliable data from unrated charity profiles.
    """
    cn_beacons = []
    cn_url = None

    # Only trust CN beacons if the charity is actually rated
    # (unrated profiles may have stale/incorrect beacon data)
    if cn_is_rated:
        # Filter CN beacons to actual awards (exclude "Profile Managed")
        cn_beacons = [b for b in cn_profile.get("beacons", []) if b not in EXCLUDED_BEACONS]

        # Add star rating as recognition if available (only 4-star)
        star_rating = cn_profile.get("star_rating")
        if star_rating and star_rating >= 4:
            cn_beacons.append(f"{star_rating}-Star Rating")

        # Construct CN URL from EIN (remove hyphen)
        cn_url = f"https://www.charitynavigator.org/ein/{ein.replace('-', '')}"

    # Candid seal - show all seal levels (Bronze/Silver/Gold/Platinum)
    candid_seal_raw = candid_profile.get("candid_seal")
    candid_seal = candid_seal_raw.title() if candid_seal_raw else None
    candid_url = candid_profile.get("candid_url") if candid_seal else None

    # BBB Wise Giving Alliance status
    bbb_meets_standards = bbb_profile.get("meets_standards") if bbb_profile else None
    bbb_review_url = bbb_profile.get("review_url") if bbb_profile else None

    # Only return if we have something to show
    # Always include bbbReviewUrl when available (for transparency, even if not accredited)
    if cn_beacons or candid_seal or bbb_meets_standards or bbb_review_url:
        return {
            "cnBeacons": cn_beacons if cn_beacons else None,
            "cnUrl": cn_url,  # Link to Charity Navigator profile
            "candidSeal": candid_seal,
            "candidUrl": candid_url,  # Link to Candid profile
            "bbbStatus": "Meets Standards" if bbb_meets_standards else None,
            "bbbReviewUrl": bbb_review_url,  # Always show when available
        }
    return None


def _extract_donate_url(raw_sources: dict[str, dict]) -> str | None:
    """Extract a well-formed donation URL from raw website data."""
    website_data = raw_sources.get("website", {}) or {}
    if not isinstance(website_data, dict):
        return None
    website_profile = website_data.get("website_profile", website_data)
    if not isinstance(website_profile, dict):
        return None
    url = website_profile.get("donate_url") or website_profile.get("donation_page_url")
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return url
    except Exception:
        pass
    return None


def _build_evidence_quality(charity_data: dict | None) -> dict | None:
    """Bundle evidence quality fields into a single sub-object."""
    if not charity_data:
        return None
    fields = {
        "hasOutcomeMethodology": charity_data.get("has_outcome_methodology"),
        "hasMultiYearMetrics": charity_data.get("has_multi_year_metrics"),
        "thirdPartyEvaluated": charity_data.get("third_party_evaluated"),
        "evaluationSources": charity_data.get("evaluation_sources"),
        "receivesFoundationGrants": charity_data.get("receives_foundation_grants"),
    }
    # Only return if at least one field has a non-None value
    if any(v is not None for v in fields.values()):
        return fields
    return None


def _normalize_public_url(url: Any) -> str | None:
    """Return a safe public URL, excluding grounding redirect links."""
    if not isinstance(url, str):
        return None
    candidate = url.strip()
    if not candidate:
        return None
    if _is_grounding_redirect(candidate):
        return None
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return candidate


def _select_canonical_zakat_url(
    charity_data: dict | None, evaluation: dict | None, fallback_website: str | None
) -> str | None:
    """Choose the best canonical URL for zakat evidence/source display.

    Priority:
    1) Baseline narrative citations explicitly tied to zakat/donate claims
    2) Source attribution for claims_zakat_eligible
    3) Charity website fallback
    """
    # 1) Baseline narrative citations
    if isinstance(evaluation, dict):
        baseline = evaluation.get("baseline_narrative")
        citations = baseline.get("all_citations") if isinstance(baseline, dict) else None
        if isinstance(citations, list):
            zakat_candidate = None
            donate_candidate = None
            generic_candidate = None
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                url = _normalize_public_url(citation.get("source_url"))
                if not url:
                    continue
                claim = str(citation.get("claim") or "").lower()
                source_name = str(citation.get("source_name") or "").lower()
                if "zakat" in claim or "zakat" in source_name:
                    zakat_candidate = url
                    break
                if ("/donate" in url.lower() or " donate" in source_name) and not donate_candidate:
                    donate_candidate = url
                if not generic_candidate:
                    generic_candidate = url
            if zakat_candidate:
                return zakat_candidate
            if donate_candidate:
                return donate_candidate
            if generic_candidate:
                return generic_candidate

    # 2) Source attribution for claims_zakat_eligible
    if isinstance(charity_data, dict):
        source_attribution = charity_data.get("source_attribution")
        if isinstance(source_attribution, dict):
            zakat_meta = source_attribution.get("claims_zakat_eligible")
            if isinstance(zakat_meta, dict):
                url = _normalize_public_url(zakat_meta.get("source_url"))
                if url:
                    return url

    # 3) Charity website fallback
    return _normalize_public_url(fallback_website)


def _rewrite_evidence_source(evidence: str, canonical_url: str | None) -> str:
    """Rewrite evidence source annotation to use canonical URL only."""
    # Drop any trailing source clause from upstream evidence text.
    cleaned = re.sub(r"\s*\(Source:\s*https?://[^)]+\)\s*$", "", evidence, flags=re.IGNORECASE).strip()
    if canonical_url:
        return f"{cleaned} (Source: {canonical_url})"
    return cleaned


def _extract_zakat_claim_evidence(
    charity_data: dict | None, evaluation: dict | None = None, fallback_website: str | None = None
) -> list[str] | None:
    """Extract zakat claim evidence with canonical URLs and no grounding redirects."""
    if not charity_data:
        return None
    evidence = charity_data.get("zakat_claim_evidence")
    if not evidence:
        return None
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        return None
    canonical_url = _select_canonical_zakat_url(charity_data, evaluation, fallback_website)

    filtered = []
    for item in evidence:
        if not isinstance(item, str):
            continue
        if item.startswith("CORROBORATION FAILED:"):
            continue
        rewritten = _rewrite_evidence_source(item, canonical_url)
        if rewritten:
            filtered.append(rewritten)

    return filtered if filtered else None


def _extract_archetype(charity_data: dict | None) -> str | None:
    """Extract human-readable archetype from strategic classification."""
    if not charity_data:
        return None
    classification = charity_data.get("strategic_classification")
    if not classification or not isinstance(classification, dict):
        return None
    return classification.get("archetype")


def _extract_rubric_archetype(evaluation: dict | None) -> str | None:
    """Extract rubric archetype from score_details.impact.rubric_archetype."""
    if not evaluation:
        return None
    score_details = evaluation.get("score_details")
    if not score_details or not isinstance(score_details, dict):
        return None
    impact = score_details.get("impact")
    if not impact or not isinstance(impact, dict):
        return None
    return impact.get("rubric_archetype")


def _normalize_score_details_zakat_sources(
    score_details: dict[str, Any] | None, canonical_url: str | None
) -> dict[str, Any] | None:
    """Normalize score_details.zakat.claim_evidence to canonical URL."""
    if not isinstance(score_details, dict):
        return score_details

    normalized = dict(score_details)
    zakat = normalized.get("zakat")
    if not isinstance(zakat, dict):
        return normalized

    zakat_normalized = dict(zakat)
    claim_evidence = zakat_normalized.get("claim_evidence")
    if isinstance(claim_evidence, str) and claim_evidence.strip():
        zakat_normalized["claim_evidence"] = _rewrite_evidence_source(claim_evidence, canonical_url)

    normalized["zakat"] = zakat_normalized
    return normalized


def _is_truncated_text(value: str | None) -> bool:
    """Detect text that is likely UI-truncated."""
    return isinstance(value, str) and value.rstrip().endswith("...")


def _choose_best_mission(*candidates: Any) -> str | None:
    """Choose the best available mission, preferring non-truncated longer text."""
    cleaned: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, str):
            text = candidate.strip()
            if text:
                cleaned.append(text)

    if not cleaned:
        return None

    non_truncated = [text for text in cleaned if not _is_truncated_text(text)]
    pool = non_truncated or cleaned
    return max(pool, key=len)


def _clean_program_list(programs: Any) -> list[str]:
    """Normalize program lists and remove placeholders."""
    if not isinstance(programs, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in programs:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        if re.match(r"^Program \d+$", text, flags=re.IGNORECASE):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _is_grounding_redirect(url: Any) -> bool:
    """Return True for Google grounding redirect URLs."""
    return (
        isinstance(url, str)
        and "vertexaisearch.cloud.google.com" in url
        and "grounding-api-redirect" in url
    )


def _normalize_source_attribution_urls(source_attribution: Any, fallback_website: str | None) -> Any:
    """Replace non-canonical grounding redirect URLs with charity website URLs."""
    if not isinstance(source_attribution, dict):
        return source_attribution

    normalized: dict[str, Any] = {}
    for field, meta in source_attribution.items():
        if not isinstance(meta, dict):
            normalized[field] = meta
            continue
        updated = dict(meta)
        if _is_grounding_redirect(updated.get("source_url")):
            updated["source_url"] = fallback_website
        normalized[field] = updated
    return normalized


def _extract_pillar_scores(evaluation: dict | None) -> dict[str, int | float] | None:
    """Extract pillar scores from score_details for visualization.

    Default 2-dimension framework: impact/50, alignment/50, plus dataConfidence (0.0-1.0).
    Legacy records may also include credibility/50.
    """
    if not evaluation:
        return None
    score_details = evaluation.get("score_details")
    if not score_details or not isinstance(score_details, dict):
        return None

    impact = score_details.get("impact", {}).get("score")
    alignment = score_details.get("alignment", {}).get("score")
    data_confidence = score_details.get("data_confidence", {}).get("overall")

    if impact is None or alignment is None:
        return None

    result: dict[str, int | float] = {
        "impact": impact,
        "alignment": alignment,
    }
    credibility = score_details.get("credibility", {}).get("score")
    if credibility is None:
        confidence_scores = evaluation.get("confidence_scores")
        if isinstance(confidence_scores, dict):
            credibility = confidence_scores.get("credibility")
    if isinstance(credibility, (int, float)):
        result["credibility"] = float(credibility)
    if data_confidence is not None:
        result["dataConfidence"] = data_confidence
    return result


def _extract_score_summary(evaluation: dict | None) -> str | None:
    """Extract the score_summary sentence from score_details."""
    if not evaluation:
        return None
    score_details = evaluation.get("score_details")
    if not score_details or not isinstance(score_details, dict):
        return None
    return score_details.get("score_summary")


def build_charity_summary(
    charity: dict,
    charity_data: dict | None,
    evaluation: dict | None,
    raw_sources: dict[str, dict] | None = None,
    hide_from_curated: bool = False,
    ui_signals_v1: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build summary record for charities.json."""

    # E-002: Use shared tier determination logic
    tier = _determine_tier(evaluation)

    # Extract causeArea from rich_narrative (if available)
    cause_area = None
    headline = None
    if evaluation:
        rich_narrative = evaluation.get("rich_narrative")
        baseline_narrative = evaluation.get("baseline_narrative")
        if rich_narrative and isinstance(rich_narrative, dict):
            donor_fit = rich_narrative.get("donor_fit_matrix")
            if donor_fit and isinstance(donor_fit, dict):
                cause_area = donor_fit.get("cause_area")
            headline = rich_narrative.get("headline")
        if not headline and baseline_narrative and isinstance(baseline_narrative, dict):
            headline = baseline_narrative.get("headline")

    website_profile = {}
    candid_profile = {}
    cn_profile = {}
    if raw_sources and isinstance(raw_sources.get("website"), dict):
        website_raw = raw_sources.get("website", {})
        website_profile = website_raw.get("website_profile", website_raw)
        if not isinstance(website_profile, dict):
            website_profile = {}
    if raw_sources and isinstance(raw_sources.get("candid"), dict):
        candid_raw = raw_sources.get("candid", {})
        candid_profile = candid_raw.get("candid_profile", candid_raw)
        if not isinstance(candid_profile, dict):
            candid_profile = {}
    if raw_sources and isinstance(raw_sources.get("charity_navigator"), dict):
        cn_raw = raw_sources.get("charity_navigator", {})
        cn_profile = cn_raw.get("cn_profile", cn_raw)
        if not isinstance(cn_profile, dict):
            cn_profile = {}

    best_mission = _choose_best_mission(
        charity.get("mission"),
        website_profile.get("mission"),
        website_profile.get("mission_statement"),
        candid_profile.get("mission"),
        cn_profile.get("mission"),
    )

    return {
        "id": charity["ein"],
        "ein": charity["ein"],
        "name": charity.get("name") or charity["ein"],
        "tier": tier,
        "mission": best_mission,
        "headline": headline,  # Fallback description from baseline/rich narrative
        "category": charity.get("category"),
        "website": charity.get("website"),
        "overallScore": charity_data.get("charity_navigator_score") if charity_data else None,
        "financialScore": None,  # Not in current schema
        "accountabilityScore": None,
        "programExpenseRatio": charity_data.get("program_expense_ratio") if charity_data else None,
        "totalRevenue": charity_data.get("total_revenue") if charity_data else None,
        "isMuslimCharity": charity_data.get("muslim_charity_fit") == "high" if charity_data else False,
        # E-003: Use None instead of datetime.now() - don't fake update timestamps
        "lastUpdated": evaluation.get("updated_at") if evaluation else None,
        "status": evaluation.get("state") if evaluation else None,
        "impactTier": evaluation.get("impact_tier") if evaluation else None,
        "confidenceTier": evaluation.get("confidence_tier") if evaluation else None,
        "zakatClassification": evaluation.get("zakat_classification") if evaluation else None,
        "amalScore": evaluation.get("amal_score") if evaluation else None,
        "walletTag": evaluation.get("wallet_tag") if evaluation else None,
        # Pillar scores for methodology visualization (impact/50, alignment/50, dataConfidence 0-1)
        "pillarScores": _extract_pillar_scores(evaluation) if evaluation else None,
        "causeArea": cause_area,  # For cause-based filtering on browse page
        # Category fields for donor discovery (MECE primary category + metadata)
        "primaryCategory": charity_data.get("primary_category") if charity_data else None,
        "categoryMetadata": {
            "importance": charity_data.get("category_importance"),
            "neglectedness": charity_data.get("category_neglectedness"),
        }
        if charity_data and charity_data.get("primary_category")
        else None,
        "causeTags": charity_data.get("cause_tags") if charity_data else None,
        "programFocusTags": charity_data.get("program_focus_tags") if charity_data else None,
        "hideFromCurated": hide_from_curated if hide_from_curated else None,
        # Evaluation track (NEW_ORG, RESEARCH_POLICY, STANDARD)
        "evaluationTrack": charity_data.get("evaluation_track") if charity_data else None,
        "foundedYear": charity_data.get("founded_year") if charity_data else None,
        # Score summary sentence (deterministic, template-based)
        "scoreSummary": _extract_score_summary(evaluation) if evaluation else None,
        # Rubric archetype used for Impact weighting (v5.0.0+)
        "rubricArchetype": _extract_rubric_archetype(evaluation),
        # Asnaf categories for future filtering
        "asnafServed": (charity_data.get("zakat_metadata") or {}).get("asnaf_categories_served")
        if charity_data
        else None,
        "ui_signals_v1": ui_signals_v1,
    }


def build_charity_detail(
    charity: dict,
    charity_data: dict | None,
    evaluation: dict | None,
    raw_sources: dict[str, dict],
    hide_from_curated: bool = False,
    ui_signals_v1: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build detailed record for individual charity JSON."""

    # E-002: Use shared tier determination logic
    # Note: detail view treats "hidden" as "baseline" (always has some content)
    tier = _determine_tier(evaluation)
    if tier == "hidden":
        tier = "baseline"

    # Extract data from raw sources
    cn_data = raw_sources.get("charity_navigator", {})
    cn_profile = cn_data.get("cn_profile", cn_data)

    candid_data = raw_sources.get("candid", {})
    candid_profile = candid_data.get("candid_profile", candid_data)

    pp_data = raw_sources.get("propublica", {})
    pp_profile = pp_data.get("propublica_990", pp_data)

    website_data = raw_sources.get("website", {})
    website_profile = website_data.get("website_profile", website_data) if isinstance(website_data, dict) else {}
    if not isinstance(website_profile, dict):
        website_profile = {}

    bbb_data = raw_sources.get("bbb", {})
    bbb_profile = bbb_data.get("bbb_profile", bbb_data)

    # Check if CN has scores to show
    # Show scores if: (1) fully rated with 2+ beacons, OR (2) has valid overall_score from any beacon
    # Previous logic only showed scores for 2+ beacons, hiding valid 1-beacon ratings like Muslim Advocates (81/100)
    cn_is_rated = cn_profile.get("cn_is_rated", False)
    cn_has_scores = cn_profile.get("overall_score") is not None

    website_programs = _clean_program_list(website_profile.get("programs"))
    candid_programs = _clean_program_list(candid_profile.get("programs"))
    programs = website_programs if len(website_programs) >= len(candid_programs) else candid_programs

    best_mission = _choose_best_mission(
        charity.get("mission"),
        website_profile.get("mission"),
        website_profile.get("mission_statement"),
        candid_profile.get("mission"),
        cn_profile.get("mission"),
    )

    # NOTE: populationsServed removed - was 65% unreliable from naive keyword matching
    # See Task #3 audit: candid scraper matches "men", "communities" etc. anywhere in page text

    # Build geographic coverage
    geographic = []
    if candid_profile.get("areas_served"):
        geographic = candid_profile["areas_served"]

    detail = {
        "id": charity["ein"],
        "ein": charity["ein"],
        "name": charity.get("name") or charity["ein"],
        "tier": tier,
        "mission": best_mission,
        "programs": programs,
        # "populationsServed" removed - data quality too low (65% unreliable)
        "geographicCoverage": geographic,
        "category": charity.get("category"),
        "website": charity.get("website") or cn_profile.get("website_url"),
        # Location fields from charities table (populated during synthesis)
        "location": {
            "address": charity.get("address"),
            "city": charity.get("city"),
            "state": charity.get("state"),
            "zip": charity.get("zip"),
        }
        if any([charity.get("city"), charity.get("state"), charity.get("zip")])
        else None,
        "isMuslimCharity": charity_data.get("muslim_charity_fit") == "high" if charity_data else False,
        "zakatEligible": None,
        "status": evaluation.get("state") if evaluation else None,
        "scores": {
            # Show CN scores if they have any valid score (1+ beacons)
            # Encompasses both fully-rated (2+ beacons) and partially-rated (1 beacon) charities
            "overall": cn_profile.get("overall_score") if cn_has_scores else None,
            "financial": cn_profile.get("financial_score") if cn_has_scores else None,
            "accountability": cn_profile.get("accountability_score") if cn_has_scores else None,
            "transparency": charity_data.get("transparency_score") if charity_data else None,
        },
        # Awards and recognition (CN beacons, Candid seal, star ratings)
        "awards": _build_awards(charity["ein"], cn_profile, candid_profile, bbb_profile, cn_is_rated),
        "financials": {
            "totalRevenue": charity_data.get("total_revenue") if charity_data else None,
            "totalExpenses": (charity_data.get("total_expenses") if charity_data else None)
            or cn_profile.get("total_expenses"),
            "programExpenses": charity_data.get("program_expenses") if charity_data else None,
            "adminExpenses": charity_data.get("admin_expenses") if charity_data else None,
            "fundraisingExpenses": charity_data.get("fundraising_expenses") if charity_data else None,
            "programExpenseRatio": charity_data.get("program_expense_ratio") if charity_data else None,
            # Balance sheet data (previously missing - audit fix)
            "totalAssets": charity_data.get("total_assets") if charity_data else None,
            "totalLiabilities": charity_data.get("total_liabilities") if charity_data else None,
            "netAssets": charity_data.get("net_assets") if charity_data else None,
            # Working capital months (balance sheet derived, previously only in rich narrative)
            "workingCapitalMonths": charity_data.get("working_capital_months") if charity_data else None,
        },
        # Baseline governance data - only for charities WITHOUT rich narratives
        # Rich charities get governance from rich.organizational_capacity (with citations)
        "baselineGovernance": {
            "boardSize": charity_data.get("board_size") if charity_data else None,
            "independentBoardMembers": charity_data.get("independent_board_members") if charity_data else None,
            "ceoCompensation": charity_data.get("ceo_compensation") if charity_data else None,
        }
        if (
            charity_data
            and not (evaluation and evaluation.get("rich_narrative"))  # Only for baseline
            and any(
                [
                    charity_data.get("board_size"),
                    charity_data.get("independent_board_members"),
                    charity_data.get("ceo_compensation"),
                ]
            )
        )
        else None,
        # Targeting data (previously missing - audit fix)
        "targeting": {
            "populationsServed": charity_data.get("populations_served") if charity_data else None,
            "geographicCoverage": charity_data.get("geographic_coverage") if charity_data else None,
        }
        if charity_data and any([charity_data.get("populations_served"), charity_data.get("geographic_coverage")])
        else None,
        # Trust signals (previously missing scorer-critical fields - data flow audit fix)
        "trustSignals": {
            "hasAnnualReport": charity_data.get("has_annual_report"),
            "hasAuditedFinancials": charity_data.get("has_audited_financials"),
            "candidSeal": charity_data.get("candid_seal"),
            "isConflictZone": charity_data.get("is_conflict_zone"),
            "nonprofitSizeTier": charity_data.get("nonprofit_size_tier"),
            "employeesCount": charity_data.get("employees_count"),
            "volunteersCount": charity_data.get("volunteers_count"),
        }
        if charity_data
        and any(
            [
                charity_data.get("has_annual_report"),
                charity_data.get("has_audited_financials"),
                charity_data.get("employees_count"),
            ]
        )
        else None,
        # Website evidence signals (previously missing - audit fix)
        "websiteEvidenceSignals": charity_data.get("website_evidence_signals") if charity_data else None,
        # E-003: Use None instead of datetime.now() - don't fake update timestamps
        "lastUpdated": evaluation.get("updated_at") if evaluation else None,
        # Source attribution - maps field name to {source_name, source_url, value, timestamp}
        "sourceAttribution": (
            _normalize_source_attribution_urls(charity_data.get("source_attribution"), charity.get("website"))
            if charity_data
            else None
        ),
        # Category fields for donor discovery (MECE primary category + metadata)
        "primaryCategory": charity_data.get("primary_category") if charity_data else None,
        "categoryMetadata": {
            "importance": charity_data.get("category_importance"),
            "neglectedness": charity_data.get("category_neglectedness"),
        }
        if charity_data and charity_data.get("primary_category")
        else None,
        "causeTags": charity_data.get("cause_tags") if charity_data else None,
        "programFocusTags": charity_data.get("program_focus_tags") if charity_data else None,
        "hideFromCurated": hide_from_curated if hide_from_curated else None,
        # Theory of change (from website/PDFs)
        "theoryOfChange": charity_data.get("theory_of_change") if charity_data else None,
        # Grants data (from Form 990 Schedule I/F)
        "grantsData": charity_data.get("grants_made") if charity_data else None,
        # Evaluation track (NEW_ORG, RESEARCH_POLICY, STANDARD)
        "evaluationTrack": charity_data.get("evaluation_track") if charity_data else None,
        "foundedYear": charity_data.get("founded_year") if charity_data else None,
        # Form 990 filing status - prefer charity_data (persisted), fallback to pp_profile
        "form990Exempt": charity_data.get("form_990_exempt") if charity_data else pp_profile.get("form_990_exempt"),
        "form990ExemptReason": (
            charity_data.get("form_990_exempt_reason") if charity_data else pp_profile.get("form_990_exempt_reason")
        ),
        "noFilings": pp_profile.get("no_filings"),
        # P0: Donation URL from raw website extraction
        "donationUrl": _extract_donate_url(raw_sources),
        # P0: Working capital months (balance sheet derived)
        # P0: Beneficiaries served annually (self-reported)
        "beneficiariesServedAnnually": charity_data.get("beneficiaries_served_annually") if charity_data else None,
        # P1: Evidence quality signals for scoring transparency
        "evidenceQuality": _build_evidence_quality(charity_data),
        # P1: Zakat claim evidence (filtered)
        "zakatClaimEvidence": _extract_zakat_claim_evidence(
            charity_data,
            evaluation=evaluation,
            fallback_website=charity.get("website"),
        ),
        # P2: Strategic archetype (e.g., RESILIENCE, LEVERAGE)
        "archetype": _extract_archetype(charity_data),
        "ui_signals_v1": ui_signals_v1,
    }

    canonical_zakat_url = _select_canonical_zakat_url(
        charity_data,
        evaluation,
        charity.get("website"),
    )

    # Add AMAL evaluation if available
    if evaluation:
        detail["amalEvaluation"] = {
            "charity_ein": charity["ein"],
            "charity_name": charity.get("name"),
            "amal_score": evaluation.get("amal_score"),
            "wallet_tag": evaluation.get("wallet_tag"),
            "evaluation_date": evaluation.get("evaluated_at"),
            "rubric_version": evaluation.get("rubric_version"),
            "confidence_scores": evaluation.get("confidence_scores"),
            "score_details": _normalize_score_details_zakat_sources(
                evaluation.get("score_details"), canonical_zakat_url
            ),  # Full scorer output
            "baseline_narrative": evaluation.get("baseline_narrative"),
        }
        # Include rich_narrative whenever it exists in the database
        if evaluation.get("rich_narrative"):
            detail["amalEvaluation"]["rich_narrative"] = evaluation.get("rich_narrative")

        # Strategic/Zakat lens evaluations removed from export (pipeline still calculates them)
        # Frontend shows AMAL-only scoring framework

    return detail


def export_charity(
    ein: str,
    charity_repo: CharityRepository,
    raw_repo: RawDataRepository,
    data_repo: CharityDataRepository,
    eval_repo: EvaluationRepository,
    output_dir: Path,
    ui_signals_config: dict[str, Any],
    config_hash: str,
    hide_from_curated: bool = False,
    pilot_name: str | None = None,
) -> dict[str, Any]:
    """Export a single charity to JSON files."""
    result = {"ein": ein, "success": False}

    # Get charity
    charity = charity_repo.get(ein)
    if not charity:
        result["error"] = "Charity not found"
        return result

    # Fix missing name: if name is absent or equals the EIN, use pilot_charities.txt name
    current_name = charity.get("name")
    if (not current_name or current_name == ein or current_name == ein.replace("-", "")) and pilot_name:
        charity["name"] = pilot_name

    # Get synthesized data
    charity_data = data_repo.get(ein)

    # Get evaluation
    evaluation = eval_repo.get(ein)

    # Build deterministic qualitative UI signals from scored fields
    ui_signals_v1 = _derive_ui_signals_v1(charity, charity_data, evaluation, ui_signals_config, config_hash)

    # Get raw sources for detail view
    raw_data = raw_repo.get_for_charity(ein)
    raw_sources: dict[str, dict] = {}
    for rd in raw_data:
        if rd.get("success") and rd.get("parsed_json"):
            raw_sources[rd["source"]] = rd["parsed_json"]

    # Build summary
    summary = build_charity_summary(
        charity,
        charity_data,
        evaluation,
        raw_sources,
        hide_from_curated,
        ui_signals_v1=ui_signals_v1,
    )

    # Build detail
    detail = build_charity_detail(
        charity,
        charity_data,
        evaluation,
        raw_sources,
        hide_from_curated,
        ui_signals_v1=ui_signals_v1,
    )

    # Write individual charity file
    charities_dir = output_dir / "charities"
    charities_dir.mkdir(parents=True, exist_ok=True)

    charity_file = charities_dir / f"charity-{ein}.json"
    with open(charity_file, "w") as f:
        json.dump(detail, f, indent=2, default=str)

    result["summary"] = summary
    result["detail_file"] = str(charity_file)
    result["tier"] = summary["tier"]
    result["success"] = True
    return result


@dataclass
class PilotCharityFlags:
    """Flags parsed from pilot_charities.txt for a charity."""

    hide_from_curated: bool = False
    name: str | None = None  # Name from pilot_charities.txt for fallback


# =============================================================================
# PROMPT EXPORT
# =============================================================================

# The baseline prompt template (from baseline.py lines 324-412)
# This is extracted here to avoid importing the full baseline module
BASELINE_PROMPT_TEMPLATE = """Generate a baseline narrative for this charity with Wikipedia-style inline citations.

## Charity Information
- Name: {charity_name}
- EIN: {ein}
- Mission: {mission}
- Programs: {programs}

## Financial Data
- Total Revenue: {revenue}
- Program Expense Ratio: {ratio}
- Charity Navigator Score: {cn_score}
- Working Capital: {working_capital}
- Fundraising Efficiency: {fundraising_efficiency}

## MANDATORY VALUES (USE EXACTLY AS PROVIDED - DO NOT CALCULATE OR INVENT)
When mentioning these metrics in the narrative, you MUST use the EXACT values below.
Do NOT round differently, do NOT calculate your own values, do NOT invent numbers.

- Program Expense Ratio: {ratio} (use this exact percentage everywhere)
- Total Revenue: {revenue} (use this exact amount everywhere)
- Working Capital: {working_capital} (use this exact value everywhere)
- Fundraising Efficiency: {fundraising_efficiency} (use this exact value everywhere)

If a value is "N/A", do NOT mention that metric in the narrative at all.

## ZAKAT ELIGIBILITY CONSTRAINT (CRITICAL)
Wallet Tag: {wallet_tag}
{zakat_constraint_text}

## REVENUE GROWTH CONSTRAINT (CRITICAL)
Do NOT mention 3-year revenue CAGR, compound annual growth rate, or multi-year revenue growth percentages.
This data is not provided in the baseline context. Only mention single-year revenue if available.

## Pre-computed Scores (for context only - explain in plain English)
- GMG Score: {amal_score}/100
- Wallet Tag: {wallet_tag}
- Impact: {impact_score}/50 (Directness: {impact_directness}, Cost per beneficiary: {impact_cpb})
- Alignment: {alignment_score}/50 (Donor fit: {alignment_fit}, Cause urgency: {alignment_urgency})
- Data Confidence: {data_confidence} ({data_confidence_badge})

## SCORE/RATIONALE CONSISTENCY (CRITICAL)
Your dimension_explanations MUST be consistent with the scores above:
- If a score is LOW (0-15): Explain what's MISSING or CONCERNING (e.g., "Limited data available", "No third-party verification")
- If a score is MEDIUM (16-33): Balanced explanation of strengths and gaps
- If a score is HIGH (34+): Can highlight strengths

DO NOT invent positive data to justify low scores:
- If Impact is low, do NOT claim the organization "demonstrates effectiveness"
- If Alignment is low, do NOT claim strong Muslim donor fit
- Only mention ratings/scores that are explicitly provided in the source data above

## Available Sources for Citations (EXACTLY {num_sources} sources)
{sources_list}

## Citation Rules (CRITICAL - follow exactly)
1. You have EXACTLY {num_sources} sources available, numbered [1] through [{num_sources}]
2. ONLY use citation numbers that exist in the list above - do NOT use [N] where N > {num_sources}
3. For EVERY [N] citation you use in text, you MUST include a matching entry in all_citations
4. Format: [N] where N is the source number (e.g., [1], [2])
5. Example: "The charity maintains strong financial accountability [1]."

## Output Format
Return ONLY a valid JSON object (no markdown code blocks):

{
  "headline": "One compelling sentence about the charity",
  "summary": "2-3 sentences with citations like [1] and [2]",
  "strengths": ["strength 1", "strength 2"],
  "areas_for_improvement": ["area 1"],
  "amal_score_rationale": "1-2 sentences explaining the overall score",
  "dimension_explanations": {
    "impact": "Plain English with citations about program effectiveness, financial health, and evidence quality",
    "alignment": "Plain English with citations about donor fit, cause urgency, and track record"
  },
  "all_citations": [
    {
      "id": "[1]",
      "source_name": "Source name from list above",
      "source_url": "URL from source list (or null if not available)",
      "claim": "The specific claim this citation supports"
    }
  ]
}

Generate the narrative JSON:"""


def export_prompts(output_dir: Path) -> dict[str, Any]:
    """Export all LLM prompts to website/data/prompts/ for transparency.

    Reads prompts from multiple sources and writes structured JSON files
    with metadata and annotations for the public transparency page.
    """
    base_path = Path(__file__).parent
    prompts_dir = output_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # Load annotations
    annotations_path = base_path / "config" / "prompt_annotations.yaml"
    with open(annotations_path) as f:
        annotations = yaml.safe_load(f)

    # Load page prompts
    page_prompts_path = base_path / "config" / "page_prompts.yaml"
    with open(page_prompts_path) as f:
        page_prompts = yaml.safe_load(f)

    prompts_index = []
    exported_count = 0

    # Helper to read a prompt file
    def read_prompt_file(relative_path: str) -> str | None:
        full_path = base_path / relative_path
        if full_path.exists():
            return full_path.read_text()
        return None

    # Export judge prompts
    judge_prompts = {
        "score_judge": "src/judges/prompts/score_judge.txt",
        "citation_judge": "src/judges/prompts/citation_judge.txt",
        "factual_judge": "src/judges/prompts/factual_judge.txt",
        "zakat_judge": "src/judges/prompts/zakat_judge.txt",
    }

    for prompt_id, file_path in judge_prompts.items():
        content = read_prompt_file(file_path)
        if content and prompt_id in annotations:
            meta = annotations[prompt_id]
            prompt_data = {
                "id": prompt_id,
                "name": meta["name"],
                "category": meta["category"],
                "description": meta["description"],
                "status": meta["status"],
                "source_file": meta["source_file"],
                "content": content,
                "annotations": meta.get("annotations", []),
            }
            # Write individual prompt file
            with open(prompts_dir / f"{prompt_id}.json", "w") as f:
                json.dump(prompt_data, f, indent=2)

            # Add to index (without content)
            prompts_index.append(
                {
                    "id": prompt_id,
                    "name": meta["name"],
                    "category": meta["category"],
                    "description": meta["description"],
                    "status": meta["status"],
                }
            )
            exported_count += 1

    # Export page extraction prompts
    page_prompt_ids = [
        "homepage_prompt",
        "about_prompt",
        "programs_prompt",
        "impact_prompt",
        "donate_prompt",
        "contact_prompt",
        "zakat_prompt",
    ]

    for prompt_id in page_prompt_ids:
        if prompt_id in page_prompts and prompt_id in annotations:
            content = page_prompts[prompt_id]
            meta = annotations[prompt_id]
            prompt_data = {
                "id": prompt_id,
                "name": meta["name"],
                "category": meta["category"],
                "description": meta["description"],
                "status": meta["status"],
                "source_file": meta["source_file"],
                "content": content,
                "annotations": meta.get("annotations", []),
            }
            with open(prompts_dir / f"{prompt_id}.json", "w") as f:
                json.dump(prompt_data, f, indent=2)

            prompts_index.append(
                {
                    "id": prompt_id,
                    "name": meta["name"],
                    "category": meta["category"],
                    "description": meta["description"],
                    "status": meta["status"],
                }
            )
            exported_count += 1

    # Export baseline narrative prompt (inline template)
    if "baseline_narrative" in annotations:
        meta = annotations["baseline_narrative"]
        prompt_data = {
            "id": "baseline_narrative",
            "name": meta["name"],
            "category": meta["category"],
            "description": meta["description"],
            "status": meta["status"],
            "source_file": meta["source_file"],
            "content": BASELINE_PROMPT_TEMPLATE,
            "annotations": meta.get("annotations", []),
        }
        with open(prompts_dir / "baseline_narrative.json", "w") as f:
            json.dump(prompt_data, f, indent=2)

        prompts_index.append(
            {
                "id": "baseline_narrative",
                "name": meta["name"],
                "category": meta["category"],
                "description": meta["description"],
                "status": meta["status"],
            }
        )
        exported_count += 1

    # Export rich narrative v2 prompt
    rich_content = read_prompt_file("src/llm/prompts/rich_narrative_v2.txt")
    if rich_content and "rich_narrative_v2" in annotations:
        meta = annotations["rich_narrative_v2"]
        prompt_data = {
            "id": "rich_narrative_v2",
            "name": meta["name"],
            "category": meta["category"],
            "description": meta["description"],
            "status": meta["status"],
            "source_file": meta["source_file"],
            "content": rich_content,
            "annotations": meta.get("annotations", []),
        }
        with open(prompts_dir / "rich_narrative_v2.json", "w") as f:
            json.dump(prompt_data, f, indent=2)

        prompts_index.append(
            {
                "id": "rich_narrative_v2",
                "name": meta["name"],
                "category": meta["category"],
                "description": meta["description"],
                "status": meta["status"],
            }
        )
        exported_count += 1

    # Export charity navigator financials prompt
    cn_content = read_prompt_file("src/llm/prompts/charity_navigator_financials.txt")
    if cn_content and "charity_navigator_financials" in annotations:
        meta = annotations["charity_navigator_financials"]
        prompt_data = {
            "id": "charity_navigator_financials",
            "name": meta["name"],
            "category": meta["category"],
            "description": meta["description"],
            "status": meta["status"],
            "source_file": meta["source_file"],
            "content": cn_content,
            "annotations": meta.get("annotations", []),
        }
        with open(prompts_dir / "charity_navigator_financials.json", "w") as f:
            json.dump(prompt_data, f, indent=2)

        prompts_index.append(
            {
                "id": "charity_navigator_financials",
                "name": meta["name"],
                "category": meta["category"],
                "description": meta["description"],
                "status": meta["status"],
            }
        )
        exported_count += 1

    # Export category calibration prompts (planned status)
    category_files = sorted((base_path / "src/llm/prompts/categories").glob("*.txt"))
    for cat_file in category_files:
        category_name = cat_file.stem.lower()
        prompt_id = f"category_{category_name}"

        # Check if we have annotations for this prompt
        if prompt_id in annotations:
            meta = annotations[prompt_id]
            content = cat_file.read_text()

            prompt_data = {
                "id": prompt_id,
                "name": meta["name"],
                "category": meta["category"],
                "description": meta["description"],
                "status": meta["status"],
                "source_file": meta["source_file"],
                "content": content,
                "annotations": meta.get("annotations", []),
            }
            with open(prompts_dir / f"{prompt_id}.json", "w") as f:
                json.dump(prompt_data, f, indent=2)

            prompts_index.append(
                {
                    "id": prompt_id,
                    "name": meta["name"],
                    "category": meta["category"],
                    "description": meta["description"],
                    "status": meta["status"],
                }
            )
            exported_count += 1

    # Write index file
    index_data = {
        "prompts": prompts_index,
        "categories": [
            {
                "id": "quality_validation",
                "name": "Quality Validation",
                "description": "Prompts that verify accuracy and consistency of generated content",
            },
            {
                "id": "data_extraction",
                "name": "Data Extraction",
                "description": "Prompts that extract structured data from charity websites",
            },
            {
                "id": "narrative_generation",
                "name": "Narrative Generation",
                "description": "Prompts that generate human-readable evaluations",
            },
            {
                "id": "category_calibration",
                "name": "Category Calibration",
                "description": "Cause-specific prompts that adjust scoring benchmarks (planned)",
            },
        ],
        "total_count": len(prompts_index),
        "active_count": sum(1 for p in prompts_index if p["status"] == "active"),
        "planned_count": sum(1 for p in prompts_index if p["status"] == "planned"),
    }

    with open(prompts_dir / "index.json", "w") as f:
        json.dump(index_data, f, indent=2)

    return {
        "exported": exported_count,
        "output_dir": str(prompts_dir),
    }


def load_pilot_charities(file_path: str) -> dict[str, PilotCharityFlags]:
    """Load charities from pilot_charities.txt format (Name | EIN | URL | flags | Comments).

    Flags can include HIDE:TRUE to exclude from curated lists.
    Returns dict mapping EIN -> PilotCharityFlags.
    """
    from src.utils.charity_loader import load_charity_entries

    charities = {}
    for entry in load_charity_entries(file_path):
        flags_upper = entry.flags_text.upper()
        hide_from_curated = "HIDE" in flags_upper and "TRUE" in flags_upper
        charities[entry.ein] = PilotCharityFlags(hide_from_curated=hide_from_curated, name=entry.name)
    return charities


def main():
    parser = argparse.ArgumentParser(description="Export charity data to website JSON")
    parser.add_argument("--ein", type=str, help="Single charity EIN to export")
    parser.add_argument("--charities", type=str, help="Path to charities file")
    parser.add_argument("--output", type=str, help="Output directory (default: ../website/data)")
    args = parser.parse_args()

    # Output directory
    output_dir = Path(args.output) if args.output else WEBSITE_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load pilot flags (from provided file or default)
    # pilot_flags maps EIN -> PilotCharityFlags (hide_from_curated)
    pilot_flags: dict[str, PilotCharityFlags] = {}
    if args.charities:
        pilot_flags = load_pilot_charities(args.charities)
    elif PILOT_CHARITIES_FILE.exists():
        pilot_flags = load_pilot_charities(str(PILOT_CHARITIES_FILE))

    # Determine which charities to export
    if args.ein:
        eins = [args.ein]
    elif args.charities:
        eins = list(pilot_flags.keys())
    else:
        # Default: export all charities with evaluations
        charity_repo = CharityRepository()
        all_charities = charity_repo.get_all()
        eins = [c["ein"] for c in all_charities]

    if not eins:
        print("No charities to export")
        return

    # Initialize repositories
    charity_repo = CharityRepository()
    raw_repo = RawDataRepository()
    data_repo = CharityDataRepository()
    eval_repo = EvaluationRepository()
    ui_signals_config = _load_ui_signals_config()
    config_hash = _compute_config_hash(ui_signals_config)

    print(f"\n{'=' * 60}")
    print(f"EXPORT: {len(eins)} CHARITIES")
    print(f"  Output: {output_dir}")
    print(f"  UI config: v{ui_signals_config.get('config_version', 'unknown')} ({config_hash[:20]}...)")
    print(f"{'=' * 60}\n")

    # Export each charity
    summaries = []
    success_count = 0
    tier_counts = {"baseline": 0, "rich": 0, "hidden": 0}
    failed_charities: list[tuple[str, str]] = []

    for i, ein in enumerate(eins, 1):
        flags = pilot_flags.get(ein, PilotCharityFlags())
        result = export_charity(
            ein,
            charity_repo,
            raw_repo,
            data_repo,
            eval_repo,
            output_dir,
            ui_signals_config=ui_signals_config,
            config_hash=config_hash,
            hide_from_curated=flags.hide_from_curated,
            pilot_name=flags.name,
        )

        if result["success"]:
            summary = result["summary"]
            quality_passed, quality_issues = run_export_quality_check(summary)
            if not quality_passed:
                failed_charities.append((ein, "Export quality check failed"))
                print(f"[{i}/{len(eins)}] ✗ {ein}: Export quality check failed")
                for issue in quality_issues:
                    if issue.get("severity") == "error":
                        print(f"    {issue['field']}: {issue['message'][:120]}")
                continue

            summaries.append(summary)
            success_count += 1
            tier = result["tier"]
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            print(f"[{i}/{len(eins)}] ✓ {ein} ({tier})")
        else:
            error = result.get("error", "Unknown")
            failed_charities.append((ein, error))
            print(f"[{i}/{len(eins)}] ✗ {ein}: {error}")

    # Capture source commit for provenance
    log_entries = dolt.log(1)
    source_commit = log_entries[0].hash if log_entries else None

    # Write charities.json summary file
    charities_file = output_dir / "charities.json"
    with open(charities_file, "w") as f:
        json.dump(
            {"source_commit": source_commit, "charities": summaries},
            f,
            indent=2,
            default=str,
        )

    # Write calibration report
    calibration_report = _build_calibration_report(
        summaries=summaries,
        cfg=ui_signals_config,
        config_hash=config_hash,
        source_commit=source_commit,
    )
    calibration_file = output_dir / "calibration-report.json"
    with open(calibration_file, "w") as f:
        json.dump(calibration_report, f, indent=2, default=str)

    # Export prompts for transparency page
    print("\n  Exporting prompts...")
    prompts_result = export_prompts(output_dir)
    print(f"    Exported {prompts_result['exported']} prompts to {prompts_result['output_dir']}")
    _mirror_export_to_public_data(output_dir)
    if output_dir.resolve() == WEBSITE_DATA_DIR.resolve():
        print(f"  Synced website runtime data to {WEBSITE_PUBLIC_DATA_DIR}")
    if calibration_report.get("warnings"):
        print(f"  Calibration warnings: {len(calibration_report['warnings'])}")
        for warning in calibration_report["warnings"]:
            print(f"    - {warning}")

    # Summary
    print(f"\n{'=' * 60}")
    print("EXPORT COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Charities: {success_count}/{len(eins)}")
    print(f"  Tiers: baseline={tier_counts['baseline']}, rich={tier_counts['rich']}, hidden={tier_counts['hidden']}")
    print(f"  Prompts: {prompts_result['exported']} exported")
    if failed_charities:
        print(f"  Failed: {len(failed_charities)}/{len(eins)}")
        for ein, error in failed_charities:
            print(f"    {ein}: {error}")
    print("\n  Output files:")
    print(f"    {charities_file}")
    print(f"    {calibration_file}")
    print(f"    {output_dir}/charities/charity-*.json")
    print(f"    {output_dir}/prompts/*.json")

    if calibration_report.get("guardrail_status", {}).get("hard_fail"):
        print("\n  HARD FAIL: calibration guardrails breached")
        for reason in calibration_report.get("guardrail_status", {}).get("reasons", []):
            print(f"    - {reason}")
        sys.exit(1)

    if failed_charities:
        sys.exit(1)


if __name__ == "__main__":
    main()

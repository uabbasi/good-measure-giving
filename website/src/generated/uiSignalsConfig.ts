/**
 * Auto-generated from data-pipeline/config/ui_signals.yaml
 * Do not edit manually.
 */

export const uiSignalsConfig = {
  "schema_version": "1.0.0",
  "config_version": "2026-02-15",
  "archetype_labels": {
    "DIRECT_SERVICE": "Frontline Relief",
    "SYSTEMIC_CHANGE": "Systems Builder",
    "EDUCATION": "Education & Training",
    "COMMUNITY": "Community Hub",
    "MULTIPLIER": "Grantmaker",
    "LEVERAGE": "Strategic Advocacy",
    "RESILIENCE": "Community Resilience",
    "SOVEREIGNTY": "Sovereignty Builder",
    "ASSET_CREATION": "Asset Creator"
  },
  "signals": {
    "evidence": {
      "strong_ratio": 0.7,
      "moderate_ratio_min": 0.4,
      "strong_grades": [
        "A",
        "B"
      ],
      "moderate_grades": [
        "C"
      ]
    },
    "financial_health": {
      "strong_min": 0.7,
      "moderate_min": 0.4
    },
    "donor_fit": {
      "strong_alignment_min": 35,
      "moderate_alignment_min": 25
    },
    "risk": {
      "governance_strong_min": 0.6,
      "governance_moderate_min": 0.4,
      "deduction_moderate_min": -3,
      "deduction_moderate_max": -1,
      "deduction_limited_max": -4
    }
  },
  "recommendation_cue": {
    "limited_match": {
      "score_max_exclusive": 40
    },
    "strong_match": {
      "score_min": 75
    },
    "good_match": {
      "score_min": 55
    }
  },
  "calibration": {
    "warning_thresholds": {
      "fallback_rate_warn_pct": 5,
      "cue_skew_warn_pct": 60,
      "missing_signal_warn_pct": 3,
      "near_threshold_warn_pct": 20,
      "stage_concentration_warn_pct": 50,
      "hard_fail": {
        "fallback_rate_pct": 20,
        "missing_signal_pct": 10
      }
    }
  }
} as const;
export const UI_SIGNALS_CONFIG_VERSION = "2026-02-15";
export const UI_SIGNALS_CONFIG_HASH = "sha256:91b9a405221d9c69a5d8b837355c40a88161b048ab5b06ddf9e309bfead956b6";

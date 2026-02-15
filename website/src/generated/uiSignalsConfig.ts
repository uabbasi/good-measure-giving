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
  "archetype_descriptions": {
    "DIRECT_SERVICE": "Delivers direct aid and services to people in need.",
    "SYSTEMIC_CHANGE": "Targets root causes through policy, legal, or systems reform.",
    "EDUCATION": "Builds long-term capacity through education and training.",
    "COMMUNITY": "Strengthens local institutions and community support systems.",
    "MULTIPLIER": "Amplifies impact by funding and coordinating other organizations.",
    "LEVERAGE": "Uses strategic advocacy to drive outsized social outcomes.",
    "RESILIENCE": "Builds long-term resilience for communities facing recurring pressures.",
    "SOVEREIGNTY": "Builds Muslim civic power and representation so communities shape policy and public life.",
    "ASSET_CREATION": "Creates durable assets and institutions that compound impact over time."
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
export const UI_SIGNALS_CONFIG_HASH = "sha256:72039be2a4983ac8d58fe0e5660161ad2d33b63cd85ef041c372f5156192690f";

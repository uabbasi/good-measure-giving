/**
 * Top-scoring charity for landing page sample audit
 * Auto-generated at build time - always shows the current highest-rated charity
 *
 * NOTE: This is intentionally in a separate file from charities.ts to ensure
 * the large CHARITIES array (4+ MB) is not pulled into the main bundle.
 */
import type { CharityProfile, AmalDimensionScore, ScoreDetails } from '../../types';

// Extended type for landing page with pillar scores as objects
interface FeaturedCharityData extends CharityProfile {
  amalEvaluation?: CharityProfile['amalEvaluation'] & {
    trust?: AmalDimensionScore;
    evidence?: AmalDimensionScore;
    effectiveness?: AmalDimensionScore;
    fit?: AmalDimensionScore;
    score_details?: ScoreDetails;
  };
}

export const TOP_CHARITY_FOR_LANDING: FeaturedCharityData | null = {
  "name": "Sadagaat",
  "ein": "47-2864379",
  "headline": "SADAGAAT-USA empowers vulnerable communities through high-impact humanitarian programs in education, health, and water infrastructure.",
  "amalEvaluation": {
    "amal_score": 89,
    "confidence_scores": {
      "impact": 46,
      "alignment": 43,
      "dataConfidence": 0
    },
    "trust": {
      "score": 0
    },
    "evidence": {
      "score": 0
    },
    "effectiveness": {
      "score": 0
    },
    "fit": {
      "score": 0
    },
    "score_details": {
      "alignment": {
        "cause_urgency_label": "HUMANITARIAN",
        "components": [
          {
            "evidence": "Explicit zakat program (+4); Muslim-focused organization (+2); Asnaf: fuqara (+5); Operates in Muslim-majority regions (+3); Strong humanitarian service (+4)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Muslim Donor Fit",
            "possible": 19,
            "scored": 18,
            "status": "full"
          },
          {
            "evidence": "Cause area: Humanitarian (13/13)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cause Urgency",
            "possible": 13,
            "scored": 13,
            "status": "full"
          },
          {
            "evidence": "Serves underserved populations (+3)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Underserved Space",
            "possible": 7,
            "scored": 3,
            "status": "partial"
          },
          {
            "evidence": "Founded 2015 (11 years — 4/6)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Track Record",
            "possible": 6,
            "scored": 4,
            "status": "full"
          },
          {
            "evidence": "Revenue: $1.3M (5/5 funding gap)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Funding Gap",
            "possible": 5,
            "scored": 5,
            "status": "full"
          }
        ],
        "muslim_donor_fit_level": "HIGH",
        "rationale": "Alignment 43/50: HIGH Muslim donor fit, humanitarian cause area",
        "score": 43
      },
      "data_confidence": {
        "badge": "HIGH",
        "data_quality_label": "HIGH",
        "data_quality_value": 1,
        "overall": 1,
        "transparency_label": "PLATINUM",
        "transparency_value": 1,
        "verification_tier": "HIGH",
        "verification_value": 1
      },
      "impact": {
        "components": [
          {
            "evidence": "$0.15/beneficiary (exceptional for HUMANITARIAN)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cost Per Beneficiary",
            "possible": 20,
            "scored": 20,
            "status": "full"
          },
          {
            "evidence": "Delivery model: Direct Provision",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Directness",
            "possible": 7,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Working capital: 3.6 months (HEALTHY)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Financial Health",
            "possible": 7,
            "scored": 5,
            "status": "full"
          },
          {
            "evidence": "Program expense ratio: 98%",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Program Ratio",
            "possible": 6,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Evidence & outcomes: TRACKED",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Evidence & Outcomes",
            "possible": 5,
            "scored": 4,
            "status": "full"
          },
          {
            "evidence": "Theory of change: CLEAR",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Theory of Change",
            "possible": 3,
            "scored": 3,
            "status": "full"
          },
          {
            "evidence": "Board governance: STRONG (8 members)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Governance",
            "possible": 2,
            "scored": 2,
            "status": "full"
          }
        ],
        "cost_per_beneficiary": 0.14748857142857144,
        "directness_level": "DIRECT_PROVISION",
        "impact_design_categories": [],
        "rationale": "$0.15/beneficiary; Delivery: direct provision; Impact 46/50",
        "score": 46
      },
      "judge_issues": [
        {
          "field": "discovered.evaluations.confidence",
          "judge": "discover_quality",
          "message": "Low confidence (0.00) for evaluations discovery (threshold: 0.75)",
          "severity": "info"
        },
        {
          "field": "discovered.theory_of_change.confidence",
          "judge": "discover_quality",
          "message": "Low confidence (0.00) for theory_of_change discovery (threshold: 0.75)",
          "severity": "info"
        },
        {
          "field": "discovered.awards.confidence",
          "judge": "discover_quality",
          "message": "Low confidence (0.00) for awards discovery (threshold: 0.75)",
          "severity": "info"
        },
        {
          "field": "hallucination_denylist.populations_served",
          "judge": "synthesize_quality",
          "message": "Hallucination-prone field 'populations_served' lacks cross-source corroboration",
          "severity": "warning"
        }
      ],
      "risk_deduction": 0,
      "risks": {
        "overall_risk_level": "LOW",
        "risk_summary": "No significant risks identified.",
        "risks": [],
        "total_deduction": 0
      },
      "score_summary": "SADAGAAT-USA earns 89/100 due to exceptional impact and exceptional alignment, with zakat compliance.",
      "zakat": {
        "asnaf_category": "fuqara",
        "bonus_points": 0,
        "charity_claims_zakat": true,
        "claim_evidence": "Dedicated zakat page found at https://sadagaat-usa.org/giving/zakat (Source: https://sadagaat-usa.org/giving/zakat)",
        "notes": null
      }
    }
  },
  "impactHighlight": "SADAGAAT-USA empowers vulnerable communities through high-impact humanitarian programs in education, health, and water infrastructure."
};

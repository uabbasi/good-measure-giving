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
  "name": "Obat Helpers",
  "ein": "47-0946122",
  "headline": "OBAT Helpers Inc. empowers marginalized communities through integrated education, healthcare, and poverty alleviation initiatives.",
  "amalEvaluation": {
    "amal_score": 88,
    "confidence_scores": {
      "impact": 42,
      "alignment": 46,
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
        "cause_urgency_label": "EDUCATION_GLOBAL",
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
            "evidence": "Cause area: Education Global (10/13)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cause Urgency",
            "possible": 13,
            "scored": 10,
            "status": "full"
          },
          {
            "evidence": "Niche cause: UNKNOWN (+4); Serves underserved populations (+3)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Underserved Space",
            "possible": 7,
            "scored": 7,
            "status": "full"
          },
          {
            "evidence": "Founded 2004 (22 years — 6/6)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Track Record",
            "possible": 6,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Revenue: $2.2M (5/5 funding gap)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Funding Gap",
            "possible": 5,
            "scored": 5,
            "status": "full"
          }
        ],
        "muslim_donor_fit_level": "HIGH",
        "rationale": "Alignment 46/50: HIGH Muslim donor fit, education global cause area",
        "score": 46
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
            "evidence": "$100.01/beneficiary (general benchmark)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cost Per Beneficiary",
            "possible": 13,
            "scored": 7,
            "status": "full"
          },
          {
            "evidence": "Delivery model: Direct Provision",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Directness",
            "possible": 5,
            "scored": 4,
            "status": "full"
          },
          {
            "evidence": "Working capital: 5.7 months (RESILIENT)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Financial Health",
            "possible": 7,
            "scored": 7,
            "status": "full"
          },
          {
            "evidence": "Program expense ratio: 82%",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Program Ratio",
            "possible": 5,
            "scored": 4,
            "status": "full"
          },
          {
            "evidence": "Evidence & outcomes: VERIFIED",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Evidence & Outcomes",
            "possible": 5,
            "scored": 5,
            "status": "full"
          },
          {
            "evidence": "Theory of change: STRONG",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Theory of Change",
            "possible": 5,
            "scored": 5,
            "status": "full"
          },
          {
            "evidence": "Board governance: STRONG (22 members)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Governance",
            "possible": 10,
            "scored": 10,
            "status": "full"
          }
        ],
        "cost_per_beneficiary": 100.01115384615385,
        "directness_level": "DIRECT_PROVISION",
        "impact_design_categories": [],
        "rationale": "$100.01/beneficiary; Delivery: direct provision; Impact 42/50",
        "rubric_archetype": "DIRECT_SERVICE",
        "score": 42
      },
      "risk_deduction": 0,
      "risks": {
        "overall_risk_level": "LOW",
        "risk_summary": "No significant risks identified.",
        "risks": [],
        "total_deduction": 0
      },
      "score_summary": "OBAT HELPERS INC shows exceptional alignment and strong impact, with zakat compliance.",
      "zakat": {
        "asnaf_category": "fuqara",
        "bonus_points": 0,
        "charity_claims_zakat": true,
        "claim_evidence": "Dedicated zakat page found at https://obathelpers.org/donate (Source: https://obathelpers.org/donate)",
        "notes": null
      }
    }
  },
  "impactHighlight": "OBAT Helpers Inc. empowers marginalized communities through integrated education, healthcare, and poverty alleviation initiatives."
};

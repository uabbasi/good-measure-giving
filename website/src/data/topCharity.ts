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
  "name": "The Citizens Foundation USA",
  "ein": "41-2046295",
  "headline": "The Citizens Foundation USA empowers underprivileged children in Pakistan through high-quality education and sustainable school infrastructure.",
  "amalEvaluation": {
    "amal_score": 86,
    "confidence_scores": {
      "impact": 48,
      "alignment": 38,
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
            "evidence": "Explicit zakat program (+4); Muslim-focused organization (+2); Asnaf: fuqara (+5); Operates in Muslim-majority regions (+3); Humanitarian service (+2)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Muslim Donor Fit",
            "possible": 19,
            "scored": 16,
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
            "evidence": "Serves underserved populations (+3)",
            "improvement_suggestion": "Expand services to underserved populations or geographies with limited nonprofit coverage.",
            "improvement_value": 3,
            "name": "Underserved Space",
            "possible": 7,
            "scored": 3,
            "status": "partial"
          },
          {
            "evidence": "Founded 1995 (31 years — 6/6)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Track Record",
            "possible": 6,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Revenue: $18.3M (3/5 funding gap)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Funding Gap",
            "possible": 5,
            "scored": 3,
            "status": "full"
          }
        ],
        "muslim_donor_fit_level": "HIGH",
        "rationale": "Alignment 38/50: HIGH Muslim donor fit, education global cause area",
        "score": 38
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
            "evidence": "$55.37/beneficiary (exceptional for EDUCATION_GLOBAL)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cost Per Beneficiary",
            "possible": 10,
            "scored": 10,
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
            "evidence": "Working capital: 4.7 months (RESILIENT)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Financial Health",
            "possible": 7,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Program expense ratio: 89%",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Program Ratio",
            "possible": 5,
            "scored": 5,
            "status": "full"
          },
          {
            "evidence": "Evidence & outcomes: VERIFIED",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Evidence & Outcomes",
            "possible": 6,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Theory of change: STRONG",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Theory of Change",
            "possible": 7,
            "scored": 7,
            "status": "full"
          },
          {
            "evidence": "Board governance: STRONG (15 members)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Governance",
            "possible": 10,
            "scored": 10,
            "status": "full"
          }
        ],
        "cost_per_beneficiary": 55.370275,
        "directness_level": "DIRECT_PROVISION",
        "impact_design_categories": [],
        "rationale": "$55.37/beneficiary; Delivery: direct provision; Impact 48/50",
        "rubric_archetype": "EDUCATION",
        "score": 48
      },
      "judge_issues": [
        {
          "field": "discovered.evaluations.confidence",
          "judge": "discover_quality",
          "message": "Low confidence (0.00) for evaluations discovery (threshold: 0.75)",
          "severity": "info"
        },
        {
          "field": "hallucination_denylist.populations_served",
          "judge": "synthesize_quality",
          "message": "Hallucination-prone field 'populations_served' lacks cross-source corroboration",
          "severity": "warning"
        },
        {
          "field": "hallucination_denylist.third_party_evaluated",
          "judge": "synthesize_quality",
          "message": "Hallucination-prone field 'third_party_evaluated' lacks cross-source corroboration",
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
      "score_summary": "The Citizens Foundation USA shows exceptional impact and strong alignment, with zakat compliance.",
      "zakat": {
        "asnaf_category": "fuqara",
        "bonus_points": 0,
        "charity_claims_zakat": true,
        "claim_evidence": "Dedicated zakat page found at https://www.tcfusa.org/zakat (Source: https://www.tcfusa.org/zakat)",
        "notes": null
      }
    }
  },
  "impactHighlight": "The Citizens Foundation USA empowers underprivileged children in Pakistan through high-quality education and sustainable school infrastructure."
};

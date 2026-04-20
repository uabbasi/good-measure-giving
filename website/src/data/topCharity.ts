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
  "name": "International Aid Charity",
  "ein": "46-3973114",
  "headline": "International Aid Charity provides essential humanitarian relief and social support to marginalized communities through highly efficient financial management.",
  "amalEvaluation": {
    "amal_score": 91,
    "confidence_scores": {
      "impact": 48,
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
            "evidence": "Explicit zakat program (+4); Muslim-focused organization (+2); Asnaf: masakin (+5); Operates in Muslim-majority regions (+3); Strong humanitarian service (+4)",
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
            "improvement_suggestion": "Expand services to underserved populations or geographies with limited nonprofit coverage.",
            "improvement_value": 3,
            "name": "Underserved Space",
            "possible": 7,
            "scored": 3,
            "status": "partial"
          },
          {
            "evidence": "Founded 2014 (12 years — 4/6)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Track Record",
            "possible": 6,
            "scored": 4,
            "status": "full"
          },
          {
            "evidence": "Revenue: $851,150 (5/5 funding gap)",
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
        "overall": 0.95,
        "transparency_label": "GOLD",
        "transparency_value": 0.86,
        "verification_tier": "HIGH",
        "verification_value": 1
      },
      "impact": {
        "components": [
          {
            "evidence": "$49.53/beneficiary (exceptional for HUMANITARIAN)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cost Per Beneficiary",
            "possible": 13,
            "scored": 12,
            "status": "full"
          },
          {
            "evidence": "Delivery model: Direct Service",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Directness",
            "possible": 5,
            "scored": 5,
            "status": "full"
          },
          {
            "evidence": "Working capital: 4.4 months (RESILIENT)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Financial Health",
            "possible": 7,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Program expense ratio: 88%",
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
            "evidence": "Board governance: ADEQUATE (6 members)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Governance",
            "possible": 10,
            "scored": 10,
            "status": "full"
          }
        ],
        "cost_per_beneficiary": 49.5267,
        "directness_level": "DIRECT_SERVICE",
        "impact_design_categories": [],
        "rationale": "$49.53/beneficiary; Delivery: direct service; Impact 48/50",
        "rubric_archetype": "DIRECT_SERVICE",
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
          "field": "discovered.awards.confidence",
          "judge": "discover_quality",
          "message": "Low confidence (0.00) for awards discovery (threshold: 0.75)",
          "severity": "info"
        },
        {
          "field": "hallucination_denylist.populations_served",
          "judge": "synthesize_quality",
          "message": "Hallucination-prone field 'populations_served' lacks cross-source corroboration",
          "severity": "info"
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
      "score_summary": "International Aid Charity shows exceptional impact and exceptional alignment, with zakat compliance.",
      "zakat": {
        "asnaf_category": "amil",
        "bonus_points": 0,
        "charity_claims_zakat": true,
        "claim_evidence": "Dedicated zakat page found at https://iacharity.org/zakat (Source: https://iacharity.org/zakat)",
        "notes": null
      }
    }
  },
  "impactHighlight": "International Aid Charity provides essential humanitarian relief and social support to marginalized communities through highly efficient financial management."
};

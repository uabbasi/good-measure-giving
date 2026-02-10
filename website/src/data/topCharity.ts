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
  "name": "SIUT",
  "ein": "76-0656947",
  "headline": "SIUT North America Inc provides critical financial support for life-saving dialysis and kidney transplant services through the SIUT Charitable Trust.",
  "amalEvaluation": {
    "amal_score": 87,
    "confidence_scores": {
      "impact": 47,
      "alignment": 40,
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
        "cause_urgency_label": "GLOBAL_HEALTH",
        "components": [
          {
            "evidence": "Accepts zakat (+2); Muslim-focused organization (+2); Asnaf: fuqara (+5); Operates in Muslim-majority regions (+3); Strong humanitarian service (+4)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Muslim Donor Fit",
            "possible": 19,
            "scored": 16,
            "status": "full"
          },
          {
            "evidence": "Cause area: Global Health (13/13)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cause Urgency",
            "possible": 13,
            "scored": 13,
            "status": "full"
          },
          {
            "evidence": "Well-covered space with mainstream reach",
            "improvement_suggestion": "Expand services to underserved populations or regions with limited nonprofit coverage",
            "improvement_value": 3,
            "name": "Underserved Space",
            "possible": 7,
            "scored": 0,
            "status": "partial"
          },
          {
            "evidence": "Founded 2000 (26 years — 6/6)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Track Record",
            "possible": 6,
            "scored": 6,
            "status": "full"
          },
          {
            "evidence": "Revenue: $5.9M (5/5 funding gap)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Funding Gap",
            "possible": 5,
            "scored": 5,
            "status": "full"
          }
        ],
        "muslim_donor_fit_level": "HIGH",
        "rationale": "Alignment 40/50: HIGH Muslim donor fit, global health cause area",
        "score": 40
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
            "evidence": "$1.14/beneficiary (exceptional for GLOBAL_HEALTH)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Cost Per Beneficiary",
            "possible": 13,
            "scored": 13,
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
            "evidence": "Working capital: 4.0 months (HEALTHY)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Financial Health",
            "possible": 7,
            "scored": 5,
            "status": "full"
          },
          {
            "evidence": "Program expense ratio: 84%",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Program Ratio",
            "possible": 5,
            "scored": 5,
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
            "possible": 5,
            "scored": 5,
            "status": "full"
          },
          {
            "evidence": "Board governance: STRONG (7 members)",
            "improvement_suggestion": null,
            "improvement_value": 0,
            "name": "Governance",
            "possible": 10,
            "scored": 10,
            "status": "full"
          }
        ],
        "cost_per_beneficiary": 1.1426035555555556,
        "directness_level": "DIRECT_SERVICE",
        "impact_design_categories": [],
        "rationale": "$1.14/beneficiary; Delivery: direct service; Impact 47/50",
        "rubric_archetype": "DIRECT_SERVICE",
        "score": 47
      },
      "judge_issues": [
        {
          "field": "discovered.zakat.confidence",
          "judge": "discover_quality",
          "message": "Low confidence (0.50) for zakat discovery (threshold: 0.75)",
          "severity": "info"
        },
        {
          "field": "discovered.outcomes.confidence",
          "judge": "discover_quality",
          "message": "Low confidence (0.00) for outcomes discovery (threshold: 0.75)",
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
      "score_summary": "SIUT North America Inc earns 87/100 due to exceptional impact and strong alignment, with zakat compliance.",
      "zakat": {
        "asnaf_category": "fuqara",
        "bonus_points": 0,
        "charity_claims_zakat": true,
        "claim_evidence": "Your Zakat and Sadaqah has the power to save lives. Donate to SIUTNA and help us provide free healthcare with dignity. ; Commit your Sadaqah, Zakat, and donations to SIUT North America to help build the SIUT Children's Hospital. (Source: https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0R99H1C_4mSUQnFzV_cb0EmiiZZW5nY3rohwirR4tKAj14xR0B6nibRhPIJy5nApS_CPzR3NVSTggtK8_uJV8uhLUhA-oTbQxzCwsIuZ5zfufSVEwRgeImAq7ADZ4y2w=)",
        "notes": null
      }
    }
  },
  "impactHighlight": "SIUT North America Inc provides critical financial support for life-saving dialysis and kidney transplant services through the SIUT Charitable Trust."
};

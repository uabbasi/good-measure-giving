import { describe, expect, it } from 'vitest';
import type { CharityProfile } from '../../types';
import {
  deriveUISignalsFromCharity,
  getAssessmentLabel,
  getEvidenceStage,
  getEvidenceStageRank,
  getRecommendationCue,
  getSignalStates,
} from './scoreUtils';

function makeCharity(partial: Partial<CharityProfile>): CharityProfile {
  return {
    id: '1',
    ein: '11-1111111',
    name: 'Test Charity',
    category: 'General',
    rawData: {
      name: 'Test Charity',
      description: '',
      mission: '',
      program_expense_ratio: 0,
      admin_fundraising_ratio: 0,
      beneficiaries_annual: 0,
      geographic_reach: [],
      board_members_count: 0,
      independent_board_members: 0,
      audit_performed: false,
      zakat_policy: '',
      transparency_level: '',
      red_flags: [],
      outcomes_evidence: '',
    },
    ...partial,
  };
}

describe('qualitative ui signal derivation', () => {
  it('derives strong-match profile from fallback fields', () => {
    const charity = makeCharity({
      foundedYear: 2005,
      evaluationTrack: 'STANDARD',
      evidenceQuality: { thirdPartyEvaluated: true },
      archetype: 'DIRECT_SERVICE',
      amalEvaluation: {
        charity_ein: '11-1111111',
        charity_name: 'Test Charity',
        amal_score: 78,
        wallet_tag: 'ZAKAT-ELIGIBLE',
        evaluation_date: '2026-01-01',
        score_details: {
          impact: {
            score: 40,
            rationale: '',
            cost_per_beneficiary: null,
            directness_level: 'DIRECT_SERVICE',
            impact_design_categories: [],
            components: [
              { name: 'Evidence & Outcomes', scored: 8, possible: 9, evidence: '', status: 'full', improvement_value: 0 },
              { name: 'Financial Health', scored: 6, possible: 7, evidence: '', status: 'full', improvement_value: 0 },
              { name: 'Program Ratio', scored: 6, possible: 7, evidence: '', status: 'full', improvement_value: 0 },
              { name: 'Governance', scored: 8, possible: 10, evidence: '', status: 'full', improvement_value: 0 },
            ],
          },
          alignment: {
            score: 38,
            rationale: '',
            muslim_donor_fit_level: 'HIGH',
            cause_urgency_label: 'HUMANITARIAN',
            components: [],
          },
          data_confidence: { overall: 1, badge: 'HIGH' },
          risks: { risks: [], overall_risk_level: 'LOW', risk_summary: '', total_deduction: 0 },
          risk_deduction: 0,
        },
      },
    });

    const derived = deriveUISignalsFromCharity(charity);
    expect(derived.recommendation_cue).toBe('Strong Match');
    expect(derived.evidence_stage).toBe('Verified');
    expect(derived.assessment_label).toBe('High Conviction');
    expect(derived.signal_states.evidence).toBe('Strong');
    expect(derived.signal_states.risk).toBe('Strong');
  });

  it('exposes convenience getters', () => {
    const charity = makeCharity({
      ui_signals_v1: {
        schema_version: '1.0.0',
        config_version: '2026-02-14',
        config_hash: 'sha256:test',
        assessment_label: 'Promising',
        archetype_code: 'SYSTEMIC_CHANGE',
        archetype_label: 'Systems Builder',
        evidence_stage: 'Established',
        signal_states: {
          evidence: 'Strong',
          financial_health: 'Moderate',
          donor_fit: 'Moderate',
          risk: 'Moderate',
        },
        recommendation_cue: 'Good Match',
        recommendation_rationale: 'Good profile',
      },
    });

    expect(getRecommendationCue(charity)).toBe('Good Match');
    expect(getEvidenceStage(charity)).toBe('Established');
    expect(getAssessmentLabel(charity)).toBe('Promising');
    expect(getSignalStates(charity).financial_health).toBe('Moderate');
    expect(getEvidenceStageRank('Verified')).toBeGreaterThan(getEvidenceStageRank('Building'));
  });
});

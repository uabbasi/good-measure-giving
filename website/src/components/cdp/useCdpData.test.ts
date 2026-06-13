import { describe, it, expect } from 'vitest';
import { buildCdpData } from './useCdpData';
import type { CharityProfile } from '../../../types';

const base = {
  name: 'Test Org',
  category: 'relief',
  amalEvaluation: {
    charity_ein: '12-3456789', charity_name: 'Test Org', amal_score: 82,
    wallet_tag: 'ZAKAT-ELIGIBLE', evaluation_date: '2026-01-01',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
  rawData: {},
} as unknown as CharityProfile;

describe('buildCdpData', () => {
  it('exposes amal score, impact/alignment, and risk deduction', () => {
    const d = buildCdpData(base, true);
    expect(d.amalScore).toBe(82);
    expect(d.impact).toBe(44);
    expect(d.alignment).toBe(41);
    expect(d.riskDeduction).toBe(3);
  });

  it('falls back to baseline narrative when canViewRich is false', () => {
    const d = buildCdpData(base, false);
    expect(d.headline).toBe('h');
  });

  it('keeps rich ungated but uses baseline headline when canViewRich is false', () => {
    const withRich = {
      ...base,
      amalEvaluation: {
        ...base.amalEvaluation,
        rich_narrative: { headline: 'rich-h', all_citations: [] },
      },
    } as unknown as CharityProfile;
    const d = buildCdpData(withRich, false);
    // rich stays exposed (point-of-use gating mirrors TabbedView)...
    expect(d.rich).toBeDefined();
    // ...but headline resolves to the baseline value because canViewRich is false.
    expect(d.headline).toBe('h');
  });

  it('uses rich narrative when canViewRich is true and rich_narrative is present', () => {
    const withRich = {
      ...base,
      amalEvaluation: {
        ...base.amalEvaluation,
        rich_narrative: { headline: 'rich-h', all_citations: [] },
      },
    } as unknown as CharityProfile;
    const d = buildCdpData(withRich, true);
    expect(d.rich).toBeDefined();
    expect(d.hasRich).toBe(true);
    expect(d.headline).toBe('rich-h');
  });
});

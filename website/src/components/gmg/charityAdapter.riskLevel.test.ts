/**
 * Risk level: "no red flags found" vs "nothing was checkable".
 *
 * Every pipeline risk check is null-gated, so a charity with no Form 990
 * fires none of them and arrives with an empty register and a 0 deduction.
 * That used to be printed as "LOW" — in green, in the hero strip and Quick
 * Facts, indistinguishable from an audited charity's LOW. Six of the 169
 * published charities are in that state, all `noFilings`; the Islamic
 * Society of Greater Houston is the one a reader caught.
 *
 * The scorer now emits UNKNOWN for it. These tests also cover the records
 * exported before that change, which still say LOW on an empty register —
 * the adapter recognises the shape so the fix doesn't wait on a pipeline run.
 */

import { describe, expect, it } from 'vitest';
import { adaptCharity, deriveRiskLevel, isRiskUnrated } from './charityAdapter';

const risks = (over: Record<string, unknown> = {}) => ({
  risks: [], overall_risk_level: 'LOW', risk_summary: '', total_deduction: 0, ...over,
});

const NO_FINANCIALS = {
  totalRevenue: null, totalExpenses: null, programExpenseRatio: null,
  workingCapitalMonths: null, totalAssets: null,
};

describe('deriveRiskLevel', () => {
  it('does not report LOW for a charity with nothing to check', () => {
    const c = { financials: NO_FINANCIALS, baselineGovernance: null, noFilings: true };

    expect(deriveRiskLevel(c, { risks: risks() })).toBe('UNRATED');
  });

  it('passes UNKNOWN from the scorer straight through', () => {
    const c = { financials: { totalRevenue: 5_000_000 } };

    expect(deriveRiskLevel(c, { risks: risks({ overall_risk_level: 'UNKNOWN' }) })).toBe('UNRATED');
  });

  it('keeps LOW when the checks actually ran', () => {
    const c = { financials: { totalRevenue: 5_000_000, programExpenseRatio: 0.88 } };

    expect(deriveRiskLevel(c, { risks: risks() })).toBe('LOW');
  });

  it('keeps a scored level even with no financials, since something fired', () => {
    const c = { financials: NO_FINANCIALS };
    const scored = risks({ overall_risk_level: 'HIGH', risks: [{ description: 'x' }], total_deduction: -8 });

    expect(deriveRiskLevel(c, { risks: scored })).toBe('HIGH');
  });

  it('treats a missing risk block as unrated, not as low risk', () => {
    expect(deriveRiskLevel({ financials: NO_FINANCIALS }, {})).toBe('UNRATED');
  });

  it('rates a charity whose only input is governance data', () => {
    const c = { financials: NO_FINANCIALS, baselineGovernance: { boardSize: 9 } };

    expect(deriveRiskLevel(c, { risks: risks() })).toBe('LOW');
  });
});

describe('adaptCharity', () => {
  it('carries the unrated state onto the page model', () => {
    const c = {
      ein: '23-7065716',
      name: 'Islamic Society of Greater Houston',
      financials: NO_FINANCIALS,
      noFilings: true,
      amalEvaluation: { amal_score: 58, score_details: { risks: risks() } },
    };

    const adapted = adaptCharity(c);

    expect(adapted.riskLevel).toBe('UNRATED');
    expect(isRiskUnrated(adapted.riskLevel)).toBe(true);
  });
});

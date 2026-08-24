import { describe, it, expect } from 'vitest';
import { summaryToProfile } from './useCharities';
import { adaptRow } from '../components/gmg/charityAdapter';

// summaryToProfile is the browse-index projection: charities.json -> CharityProfile.
// Every /browse row goes through it before adaptRow, so a value it manufactures
// here is indistinguishable downstream from one the pipeline actually reported.
// These tests run the real chain, which the GmgBrowse fixtures deliberately skip.

const summary = {
  id: 'test-org',
  ein: '00-0000000',
  name: 'Test Org',
  tier: 'baseline' as const,
  mission: null,
  category: null,
  website: '',
  amalScore: 50,
  walletTag: '',
  confidenceTier: '',
  impactTier: '',
  zakatClassification: null,
  isMuslimCharity: false,
  programExpenseRatio: null as number | null,
  totalRevenue: null as number | null,
  lastUpdated: '2026-01-01',
};

describe('summaryToProfile: an unreported ratio stays unreported', () => {
  it('does not manufacture a 0 for a null programExpenseRatio', () => {
    const p = summaryToProfile({ ...summary });
    expect(p.financials?.programExpenseRatio).toBeNull();
    expect(p.rawData?.program_expense_ratio).toBeNull();
  });

  it('renders as a blank programPct, not 0%, through the real adaptRow chain', () => {
    const row = adaptRow(summaryToProfile({ ...summary }));
    // adaptRow falls back financials.programExpenseRatio ?? rawData.program_expense_ratio,
    // so BOTH sides have to stay null or the fallback resurrects the zero.
    expect(row.programPct).toBeNull();
  });

  it('still preserves a genuine 0 distinctly from a missing value', () => {
    const zero = summaryToProfile({ ...summary, programExpenseRatio: 0 });
    expect(zero.financials?.programExpenseRatio).toBe(0);
    expect(adaptRow(zero).programPct).toBe(0);
  });

  it('passes a real ratio through as a percentage', () => {
    const row = adaptRow(summaryToProfile({ ...summary, programExpenseRatio: 0.83 }));
    expect(row.programPct).toBe(83);
  });
});

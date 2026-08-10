// GmgBrowse — Program % column sort, null handling (Phase 3 final-review
// Finding 5).
//
// The comparator uses `a.programPct ?? -1` so an unreported ratio sorts
// strictly below a genuine 0%, not the same as it. `?? 0` would stay green
// on every other test in the suite while quietly mixing "not reported" into
// the worst-performing bucket — the same "missing is not zero" conflation as
// Finding 2 and Task 1's `|| 0` fix.

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));

const base = {
  category: 'Humanitarian Relief',
  primaryCategory: 'HUMANITARIAN',
  totalRevenue: 5_000_000,
  isMuslimCharity: false,
  amalEvaluation: {
    wallet_tag: 'SADAQAH-ONLY',
    amal_score: 60,
    confidence_scores: { impact: 40, alignment: 40, dataConfidence: 0.8 },
  },
  ui_signals_v1: {
    signal_states: { financial_health: 'moderate', risk: 'moderate', donor_fit: 'moderate' },
    evidence_stage: 'Verified',
  },
};

// Name order deliberately makes the tie-break (alphabetical, always
// ascending regardless of sort direction — see GmgBrowse.tsx) disagree with
// the correct desc-by-programPct order, so a mutant that ties "no ratio
// filed" with "filed a real 0%" is distinguishable from the correct
// behaviour rather than accidentally producing the same row order.
const mockCharities = [
  { ...base, ein: '10-0000001', name: 'Fifty', financials: { programExpenseRatio: 0.5 } },
  { ...base, ein: '10-0000002', name: 'Zulu', financials: { programExpenseRatio: 0 } },
  { ...base, ein: '10-0000003', name: 'Alpha' }, // no `financials` at all -> programPct null
];

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: mockCharities, summaries: mockCharities, loading: false, error: null }),
}));

const renderBrowse = () => render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);

describe('GmgBrowse Program % column sort', () => {
  it('sorts a charity with no filed ratio below one that filed a genuine 0%, not tied with it', async () => {
    const user = userEvent.setup();
    renderBrowse();

    await user.click(screen.getByRole('columnheader', { name: /Program %/ }));

    const order = screen.getAllByText(/^(Fifty|Zulu|Alpha)$/).map((el) => el.textContent);
    expect(order).toEqual(['Fifty', 'Zulu', 'Alpha']);
  });
});

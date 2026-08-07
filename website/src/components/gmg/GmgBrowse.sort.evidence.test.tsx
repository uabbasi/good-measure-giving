// GmgBrowse — Evidence column sort (Phase 3 final-review Finding 4).
//
// EVIDENCE_RANK and the Evidence column are both new in this branch, and
// nothing exercised clicking its header: the comparator could be entirely
// broken and the suite would stay green.

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

// amal_score is deliberately in the OPPOSITE order from evidence rank, so the
// default 'overall'-desc sort and an Evidence-desc sort produce genuinely
// different row orders — a test that happened to match the default order
// wouldn't prove the comparator does anything.
const mockCharities = [
  { name: 'Whiskey', ein: '10-0000001', score: 80, evidence: 'Established' },
  { name: 'Xray', ein: '10-0000002', score: 70, evidence: 'Early' },
  { name: 'Yankee', ein: '10-0000003', score: 60, evidence: 'Verified' },
  { name: 'Zeta', ein: '10-0000004', score: 50, evidence: 'Building' },
].map(({ name, ein, score, evidence }) => ({
  ein,
  name,
  category: 'Humanitarian Relief',
  primaryCategory: 'HUMANITARIAN',
  totalRevenue: 5_000_000,
  isMuslimCharity: false,
  amalEvaluation: {
    wallet_tag: 'SADAQAH-ONLY',
    amal_score: score,
    confidence_scores: { impact: 40, alignment: 40, dataConfidence: 0.8 },
  },
  ui_signals_v1: {
    signal_states: { financial_health: 'moderate', risk: 'moderate', donor_fit: 'moderate' },
    evidence_stage: evidence,
  },
  financials: { programExpenseRatio: 0.5 },
}));

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: mockCharities, summaries: mockCharities, loading: false, error: null }),
}));

const renderBrowse = () => render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);

describe('GmgBrowse Evidence column sort', () => {
  it('sorts by evidence rank (Verified > Established > Building > Early) when the header is clicked', async () => {
    const user = userEvent.setup();
    renderBrowse();

    await user.click(screen.getByRole('columnheader', { name: /Evidence/ }));

    const order = screen.getAllByText(/^(Whiskey|Xray|Yankee|Zeta)$/).map((el) => el.textContent);
    expect(order).toEqual(['Yankee', 'Whiskey', 'Zeta', 'Xray']);
  });
});

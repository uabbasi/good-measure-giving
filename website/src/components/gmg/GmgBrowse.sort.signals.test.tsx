// GmgBrowse: a charity with no finance/governance/donor-fit signal shows "—" and
// must sort last whichever way the column runs. Encoding "missing" as the lowest
// rank put it before "Weak" in ascending order, presenting absence as the worst.

import '@testing-library/jest-dom';
import { render, screen, within } from '@testing-library/react';
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
};
const signals = (financial_health?: string) => ({
  signal_states: { financial_health, risk: 'moderate', donor_fit: 'moderate' },
  evidence_stage: 'Verified',
});

// Names are chosen so the alphabetical tie-break cannot stand in for the rating order.
const mockCharities = [
  { ...base, ein: '10-0000001', name: 'Alpha', ui_signals_v1: signals('limited') }, // Weak
  { ...base, ein: '10-0000002', name: 'Bravo', ui_signals_v1: signals(undefined) }, // missing
  { ...base, ein: '10-0000003', name: 'Charlie', ui_signals_v1: signals('strong') }, // Strong
];

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: mockCharities, summaries: mockCharities, loading: false, error: null }),
}));

const order = () => screen.getAllByText(/^(Alpha|Bravo|Charlie)$/).map((el) => el.textContent);

describe('GmgBrowse signal column sort', () => {
  it('keeps a missing signal last in descending and ascending order', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);
    const header = () => within(screen.getByRole('columnheader', { name: /Finances/ })).getByRole('button');

    await user.click(header()); // first click on a new column: descending, best first
    expect(order()).toEqual(['Charlie', 'Alpha', 'Bravo']);

    await user.click(header()); // ascending: worst first, still missing last
    expect(order()).toEqual(['Alpha', 'Charlie', 'Bravo']);
  });
});

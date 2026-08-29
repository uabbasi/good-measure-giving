// GmgBrowse — mobile card rendering (Phase 3 final-review Finding 2).
//
// Task 4's last commit exists specifically to stop a null program ratio
// rendering as "0%" — stating as fact that a real charity spent nothing on
// programs. That fix was pinned only for the desktop table cell
// (GmgBrowse.seo.test.tsx); the mobile stacked-card cell renders the exact
// same `row.programPct` with its own separate JSX and was left unguarded.

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => true }));

// A charity with no filed program-expense ratio. Deliberately omits
// `financials` entirely (not `financials: { programExpenseRatio: null }`) so
// adaptRow's real fallback chain — financials.programExpenseRatio ??
// rawData.program_expense_ratio — is what produces the null, the same way a
// real under-filed charity would (mirrors GmgBrowse.seo.test.tsx's fixture).
const NULL_PROGRAM_PCT_CHARITY = {
  ein: '99-9999999',
  name: 'Unreported Program Charity',
  category: 'Humanitarian Relief',
  primaryCategory: 'HUMANITARIAN',
  totalRevenue: 5_000_000,
  isMuslimCharity: false,
  amalEvaluation: {
    wallet_tag: 'SADAQAH-ONLY',
    amal_score: 60,
    confidence_scores: { impact: 30, alignment: 30, dataConfidence: 0.5 },
  },
  ui_signals_v1: {
    signal_states: { financial_health: 'moderate', risk: 'moderate', donor_fit: 'moderate' },
    evidence_stage: 'Early',
  },
};

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({
    charities: [NULL_PROGRAM_PCT_CHARITY],
    summaries: [NULL_PROGRAM_PCT_CHARITY],
    loading: false,
    error: null,
  }),
}));

const renderBrowse = () => render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);

describe('GmgBrowse mobile Program % card', () => {
  it('renders the em dash for a charity with no reported program ratio, never "0%"', () => {
    const { container } = renderBrowse();
    // Selected by attribute rather than by walking up from the name, which
    // silently pointed at the wrong node the moment the card's structure
    // changed.
    const card = container.querySelector('[data-charity-card="99-9999999"]') as HTMLElement;
    expect(card).not.toBeNull();
    const programPctGroup = screen.getByText('Program %', { selector: 'span' });
    expect(card.contains(programPctGroup)).toBe(true);
    expect(programPctGroup.parentElement).toHaveTextContent('—');
    expect(programPctGroup.parentElement).not.toHaveTextContent('0%');
  });
});

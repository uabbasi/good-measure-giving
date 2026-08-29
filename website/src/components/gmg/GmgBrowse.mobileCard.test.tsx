// GmgBrowse — mobile card hierarchy and layout.
//
// The phone card had grown a shape nobody chose: "Compare", a secondary
// action, was the first thing in every card, above the charity's own name;
// and the six signals sat in a flex-wrap row that broke 4 + 2 at a 393px
// Pixel width, so every card ended in a short orphan line and a ragged gap.
//
// Both are layout properties, so both can regress silently — nothing throws
// when a card reads in the wrong order or wraps badly. These pin the two
// decisions that fixed it.

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => true }));

const CHARITY = {
  ein: '12-3456789',
  name: 'Test Relief Fund',
  category: 'Humanitarian Relief',
  primaryCategory: 'HUMANITARIAN',
  totalRevenue: 7_300_000,
  isMuslimCharity: true,
  financials: { programExpenseRatio: 0.84 },
  amalEvaluation: {
    wallet_tag: 'ZAKAT-ELIGIBLE',
    amal_score: 72,
    confidence_scores: { impact: 36, alignment: 36, dataConfidence: 0.8 },
  },
  ui_signals_v1: {
    signal_states: { financial_health: 'strong', risk: 'moderate', donor_fit: 'strong' },
    evidence_stage: 'Verified',
  },
};

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({
    charities: [CHARITY],
    summaries: [CHARITY],
    loading: false,
    error: null,
  }),
}));

const renderBrowse = () => render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);

const card = (container: HTMLElement) =>
  container.querySelector('[data-charity-card="12-3456789"]') as HTMLElement;

describe('GmgBrowse mobile card', () => {
  it('leads with the charity name, not the Compare control', () => {
    const { container } = renderBrowse();
    const text = card(container).textContent ?? '';

    expect(text.indexOf('Test Relief Fund')).toBeGreaterThanOrEqual(0);
    expect(text.indexOf('Test Relief Fund')).toBeLessThan(text.indexOf('Compare'));
  });

  it('lays the three supporting signals out in a fixed three-column grid', () => {
    // A flex-wrap row is what produced the ragged 4 + 2 break. An explicit
    // three-column grid renders identically on every card at every width.
    const { container } = renderBrowse();
    const financesLabel = screen.getByText('Finances', { selector: 'span' });
    const grid = financesLabel.parentElement!.parentElement as HTMLElement;

    expect(grid.style.display).toBe('grid');
    expect(grid.style.gridTemplateColumns).toBe('repeat(3, 1fr)');
    expect(grid.children).toHaveLength(3);
  });

  it('keeps GMG out of that grid, on its own line as the headline verdict', () => {
    const { container } = renderBrowse();
    const financesLabel = screen.getByText('Finances', { selector: 'span' });
    const grid = financesLabel.parentElement!.parentElement as HTMLElement;
    const gmgLabel = screen.getByText('GMG', { selector: 'span' });

    expect(card(container).contains(gmgLabel)).toBe(true);
    expect(grid.contains(gmgLabel)).toBe(false);
  });

  it('drops the EIN from the card, keeping cause and size', () => {
    // A donor scanning 169 charities does not pick one by tax id, and it cost
    // a third of the meta line.
    const text = card(renderBrowse().container).textContent ?? '';

    expect(text).toContain('Humanitarian Relief');
    expect(text).not.toContain('12-3456789');
  });

  it('still exposes Compare as a real checkbox', () => {
    renderBrowse();
    const box = screen.getByRole('checkbox', { name: 'Select Test Relief Fund to compare' });

    expect(box).toHaveAttribute('aria-checked', 'false');
  });
});

// GmgBrowse — the mobile scan list.
//
// The phone list is dense on purpose: 169 charities, so the scan is the whole
// job. Getting there meant taking the labels off every card and putting them
// in one header row, and taking the rating words ("Strong", "Moderate") off
// the Harvey balls, which already encode the level.
//
// Both moves are the kind that regress silently — nothing throws when a
// heading stops sitting above its column, or when a rating that used to be
// announced becomes a bare graphic. These pin what makes the density safe.

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

/** The card's signal row — the grid holding the four balls. */
const signalRow = (container: HTMLElement) =>
  card(container).querySelector('[data-program-pct]')!.parentElement as HTMLElement;

/**
 * Text a sighted reader actually sees.
 *
 * textContent includes the visually-hidden spans that carry each ball's
 * rating for assistive tech, so asserting on it directly would claim the
 * words are on the page when the whole point is that they are not.
 */
const visibleText = (el: HTMLElement): string => {
  const clone = el.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('[data-sr-only]').forEach((s) => s.remove());
  return clone.textContent ?? '';
};

describe('GmgBrowse mobile scan list', () => {
  it('leads with the charity name, not the compare control', () => {
    renderBrowse();
    const name = screen.getByText('Test Relief Fund');
    const box = screen.getByRole('checkbox', { name: 'Select Test Relief Fund to compare' });

    // eslint-disable-next-line no-bitwise
    const boxComesAfterName = name.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING;
    expect(boxComesAfterName).toBeTruthy();
  });

  it('lays every card on the same column track as the header', () => {
    // This is the whole basis for labelling the columns once. If the two
    // tracks drift, the headings sit above the wrong balls and say something
    // untrue — silently, because both still render.
    const { container } = renderBrowse();
    const header = screen.getByText('GMG', { selector: 'span' }).parentElement as HTMLElement;

    expect(header.style.display).toBe('grid');
    expect(header.style.gridTemplateColumns).not.toBe('');
    expect(signalRow(container).style.gridTemplateColumns).toBe(header.style.gridTemplateColumns);
  });

  it('names each column exactly once, in the header rather than per card', () => {
    const { container } = renderBrowse();
    // Scoped to the list header: "Evidence" also labels a filter in the facet
    // bar, and "Risk" appears in the facets too.
    const header = screen.getByText('GMG', { selector: 'span' }).parentElement as HTMLElement;
    const headings = Array.from(header.children).map((c) => c.textContent);

    expect(headings).toEqual(['GMG', 'Fin', 'Risk', 'Fit', 'Prog', 'Evidence', 'Compare']);
    // ...and no card repeats them.
    const seen = visibleText(card(container));
    for (const heading of ['Fin', 'Risk', 'Fit', 'Prog', 'Compare']) {
      expect(seen).not.toContain(heading);
    }
  });

  it('drops the rating words from the page but keeps them for screen readers', () => {
    // "Strong / Strong / Moderate / Strong" read four times on every card.
    // The ball encodes the level; assistive tech still needs the words.
    const { container } = renderBrowse();

    expect(visibleText(signalRow(container))).not.toContain('Strong');
    expect(visibleText(signalRow(container))).not.toContain('Moderate');
    // Still announced, from the hidden spans the helper above strips.
    expect(card(container).textContent).toContain('Finances: Strong');
    expect(card(container).textContent).toContain('Risk: Moderate');
    expect(card(container).textContent).toContain('Donor fit: Strong');
  });

  it('drops the EIN from the card, keeping cause and size', () => {
    const text = card(renderBrowse().container).textContent ?? '';

    expect(text).toContain('Humanitarian Relief');
    expect(text).not.toContain('12-3456789');
  });

  it('still exposes compare as a real checkbox', () => {
    renderBrowse();
    const box = screen.getByRole('checkbox', { name: 'Select Test Relief Fund to compare' });

    expect(box).toHaveAttribute('aria-checked', 'false');
  });
});

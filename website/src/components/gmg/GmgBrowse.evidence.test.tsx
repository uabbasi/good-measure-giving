/**
 * The Evidence column on the desktop table.
 *
 * Reported as: the terms don't make sense in the charity list. Three things
 * were wrong at once, and only the third is about wording.
 *
 *  - It rendered as <Tag tone="muted">, the same chip the wallet category
 *    uses two columns to its left. The row's one ranked signal was dressed
 *    as a category.
 *  - With no visible scale behind them, "Verified" and "Established" read as
 *    a status on the charity rather than a step on a scale about its
 *    evidence — and "Established" is separately the name of a >$10M revenue
 *    band on /methodology.
 *  - The only explanation was a title tooltip on the column header, which is
 *    invisible until you hover the one word you already didn't understand.
 *
 * The column stays on desktop with its rank drawn and a legend above the
 * table; the phone card drops it (see GmgBrowse.mobileCard.test.tsx).
 */

import '@testing-library/jest-dom';
import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';
import { EVIDENCE_VALUES, EVIDENCE_RANK, EVIDENCE_STAGE_EXPLAINERS } from './facetState';
import { gmgPalette } from './tokens';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));

const charity = (ein: string, name: string, stage: string) => ({
  ein,
  name,
  category: 'Humanitarian Relief',
  primaryCategory: 'HUMANITARIAN',
  totalRevenue: 5_000_000,
  financials: { programExpenseRatio: 0.9 },
  amalEvaluation: {
    wallet_tag: 'ZAKAT-ELIGIBLE',
    amal_score: 70,
    confidence_scores: { impact: 35, alignment: 35, dataConfidence: 0.8 },
  },
  ui_signals_v1: {
    signal_states: { financial_health: 'strong', risk: 'moderate', donor_fit: 'strong' },
    evidence_stage: stage,
  },
});

const ROWS = [
  charity('11-1111111', 'Top Evidence Fund', 'Verified'),
  charity('22-2222222', 'Middle Evidence Fund', 'Established'),
  charity('33-3333333', 'Thin Evidence Fund', 'Early'),
];

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: ROWS, summaries: ROWS, loading: false, error: null }),
}));

const renderBrowse = () => render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);

/** The rendered evidence cell for one charity's table row. */
const cellFor = (container: HTMLElement, ein: string): HTMLElement => {
  const row = (container.querySelector(`input[aria-label*="${ein}"]`)
    ?? screen.getByText(ein.replace(/^/, 'EIN '))).closest('tr') as HTMLElement;
  return row.querySelector('[data-evidence]') as HTMLElement;
};

const legend = (container: HTMLElement) =>
  container.querySelector('[data-evidence-legend]') as HTMLElement;

const bars = (cell: HTMLElement): HTMLElement[] =>
  Array.from(cell.querySelectorAll('span[style*="border-radius"]'));

/** jsdom reads inline hex back as `rgb(r, g, b)`. */
const asRgb = (hex: string): string => {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgb(${r}, ${g}, ${b})`;
};

/** How many of the four bars are filled, read off the rendered colours. */
const filledBars = (cell: HTMLElement): number => {
  const accent = asRgb(gmgPalette(false).accent);
  return bars(cell).filter((b) => b.style.background === accent).length;
};

describe('Evidence column on desktop', () => {
  it('draws the rank rather than only naming it', () => {
    const { container } = renderBrowse();
    const top = cellFor(container, '11-1111111');
    const thin = cellFor(container, '33-3333333');

    // Four bars per cell, filled to the stage's rank.
    expect(bars(top).length).toBe(4);
    expect(filledBars(top)).toBe(EVIDENCE_RANK.Verified);
    expect(filledBars(thin)).toBe(EVIDENCE_RANK.Early);
  });

  it('still names the stage, so the bars are not the only carrier', () => {
    const { container } = renderBrowse();
    expect(cellFor(container, '22-2222222').textContent).toContain('Established');
  });

  it('announces the rank to a screen reader, which cannot see the bars', () => {
    const { container } = renderBrowse();
    expect(cellFor(container, '22-2222222').textContent).toContain('3 of 4');
  });

  it('explains the scale on the page instead of in a hover-only tooltip', () => {
    const { container } = renderBrowse();
    const l = legend(container);

    expect(l).not.toBeNull();
    for (const stage of EVIDENCE_VALUES) {
      expect(l.textContent).toContain(stage);
      expect(l.textContent).toContain(EVIDENCE_STAGE_EXPLAINERS[stage]);
    }
  });

  it('says the scale is about the claims, not about the charity', () => {
    // The reason the words misread: a bare "Verified" beside a charity name
    // is taken as GMG certifying the charity.
    const text = legend(renderBrowse().container).textContent ?? '';

    expect(text).toMatch(/claims about its results/i);
    expect(text).toMatch(/not the charity itself/i);
    expect(text).toMatch(/certification/i);
  });

  it('puts the legend above the table, not after 169 rows of it', () => {
    // A key you meet after scrolling the whole table is a key you needed at
    // the top of it.
    const { container } = renderBrowse();
    const table = container.querySelector('table') as HTMLElement;

    // eslint-disable-next-line no-bitwise
    const legendComesFirst = legend(container).compareDocumentPosition(table)
      & Node.DOCUMENT_POSITION_FOLLOWING;
    expect(legendComesFirst).toBeTruthy();
  });

  it('lists the legend best-first, matching the column sort', () => {
    const { container } = renderBrowse();
    const order = Array.from(legend(container).querySelectorAll('[data-evidence]'))
      .map((el) => el.getAttribute('data-evidence'));

    expect(order).toEqual([...EVIDENCE_VALUES]);
  });

  it('no longer dresses a ranked signal as a category chip', () => {
    // The wallet tag is a real category and keeps the Tag treatment; evidence
    // must not share it, or the row says "category" about a scale.
    const { container } = renderBrowse();
    const cell = cellFor(container, '11-1111111');
    const wallet = within(container).getAllByText(/Accepts Zakat/i)[0];

    expect(cell.tagName).toBe('SPAN');
    expect(cell.style.borderRadius).toBe('');
    expect(getComputedStyle(wallet).borderRadius).not.toBe(getComputedStyle(cell).borderRadius);
  });
});

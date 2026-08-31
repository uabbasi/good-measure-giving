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
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';
import { gmgPalette } from './tokens';

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

let dark = false;

const renderBrowse = () => render(<MemoryRouter><GmgBrowse isDark={dark} /></MemoryRouter>);

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


/** jsdom reads an inline hex back as `rgb(r, g, b)`. */
const asRgb = (hex: string): string => {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgb(${r}, ${g}, ${b})`;
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
    // Scoped to the list header: "Risk" also labels a filter in the facet bar.
    const header = screen.getByText('GMG', { selector: 'span' }).parentElement as HTMLElement;
    const headings = Array.from(header.children).map((c) => c.textContent);

    expect(headings).toEqual(['GMG', 'Fin', 'Risk', 'Fit', 'Prog', 'Compare']);
    // ...and no card repeats them.
    const seen = visibleText(card(container));
    for (const heading of ['Fin', 'Risk', 'Fit', 'Prog', 'Compare']) {
      expect(seen).not.toContain(heading);
    }
  });

  it('leaves evidence off the phone card entirely', () => {
    // It was the row's only ranked signal rendered as a word, in the same Tag
    // the wallet category uses — so the design called it a category, and
    // "Verified" read as a stamp on the charity rather than a step on a scale
    // about its evidence. It keeps its column on desktop, where the rank is
    // drawn and a legend sits under the table.
    const { container } = renderBrowse();
    const seen = visibleText(card(container));

    for (const stage of ['Verified', 'Established', 'Building', 'Early']) {
      expect(seen).not.toContain(stage);
    }
    expect(card(container).querySelector('[data-evidence]')).toBeNull();
  });

  it('keeps the header and the card on one column track after the removal', () => {
    // The track is shared, so dropping a column from one side and not the
    // other slides every ball out from under its heading — silently.
    const { container } = renderBrowse();
    const header = screen.getByText('GMG', { selector: 'span' }).parentElement as HTMLElement;

    expect(signalRow(container).style.gridTemplateColumns).toBe(header.style.gridTemplateColumns);
    expect(header.style.gridTemplateColumns).not.toContain('44px');
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

describe('GmgBrowse mobile card — what looks tappable', () => {
  // The card navigates on tap, but said so nowhere: no chevron, no hover
  // state a phone can show, and a name styled exactly like a heading. The one
  // control that looked touchable was the compare checkbox, which is the one
  // control that does not open the charity.

  it('ends the identity row with a disclosure chevron', () => {
    const { container } = renderBrowse();
    const chevron = card(container).querySelector('[data-card-chevron]');

    expect(chevron).not.toBeNull();
    expect(chevron?.textContent).toBe('›');
  });

  it('hides the chevron from screen readers — the name already carries the link', () => {
    const { container } = renderBrowse();
    expect(card(container).querySelector('[data-card-chevron]')).toHaveAttribute('aria-hidden', 'true');
  });

  it('puts the chevron after the name, at the end of the row', () => {
    const { container } = renderBrowse();
    const name = screen.getByText('Test Relief Fund');
    const chevron = card(container).querySelector('[data-card-chevron]') as HTMLElement;

    // eslint-disable-next-line no-bitwise
    expect(name.compareDocumentPosition(chevron) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('actually changes the card when a finger goes down on it', () => {
    // The regression this exists for: the press was a `:active` rule in a
    // stylesheet, and the card sets `background` INLINE. An inline
    // declaration beats any author rule that is not `!important`, so the rule
    // lost the cascade in both themes and the press never rendered once — and
    // because the same block killed the native Android tap flash, taps ended
    // up with less feedback than before the feature existed. Asserting the
    // CSS text was there is what let that ship; assert the element changes.
    const { container } = renderBrowse();
    const el = card(container);
    const resting = el.style.background;

    fireEvent.pointerDown(el);

    expect(el.style.background).not.toBe(resting);
    expect(el.style.background).toBe(asRgb(gmgPalette(false).press));
  });

  it('marks the edge too, not just the fill', () => {
    // Against the resting card the accent edge is 7.6:1 light and 9.9:1 dark,
    // where any fill shift tops out near 2:1. On a dim screen the edge is the
    // half of the cue that survives.
    const { container } = renderBrowse();
    const el = card(container);

    fireEvent.pointerDown(el);
    expect(el.style.borderColor).toBe(asRgb(gmgPalette(false).pressEdge));
  });

  it('snaps the press in rather than fading it in', () => {
    // A tap can be 50ms. Easing in over 120ms means a quick one only ever
    // reaches part of the colour before reversing.
    const { container } = renderBrowse();
    const el = card(container);

    fireEvent.pointerDown(el);
    expect(el.style.transition).toBe('none');
  });

  it('releases the press, and releases it on a scroll too', () => {
    const { container } = renderBrowse();
    const el = card(container);
    const resting = el.style.background;

    fireEvent.pointerDown(el);
    fireEvent.pointerUp(el);
    expect(el.style.background).toBe(resting);
    // pointercancel is what fires when a touch becomes a scroll; without it
    // every card dragged past would stay lit.
    fireEvent.pointerDown(el);
    fireEvent.pointerCancel(el);
    expect(el.style.background).toBe(resting);
    expect(el.style.borderColor).toBe(asRgb(gmgPalette(false).rule2));
  });

  it('presses in the palette of whichever theme is showing', () => {
    for (const isDark of [false, true]) {
      dark = isDark;
      const { container } = renderBrowse();
      const el = card(container);

      fireEvent.pointerDown(el);
      expect(el.style.background).toBe(asRgb(gmgPalette(isDark).press));
      expect(el.style.borderColor).toBe(asRgb(gmgPalette(isDark).pressEdge));
      cleanup();
    }
    dark = false;
  });
});

// GmgBrowse — facet URL sync and the crawl-budget guard (Task 4).
//
// /browse's static HTML is the indexable, canonical page. A facet selection
// is the same page with a query string; ?type= previously leaked crawl
// budget this way (see paths.ts history), so a filtered view must tell a
// JS-rendering crawler not to index it — while a plain search query must
// not, since that would make ordinary searching un-indexable. Also pins
// that URL sync never creates a history entry (replaceState only) and that
// every facet control stays a real <button>, never a link.

import '@testing-library/jest-dom';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { GmgBrowse } from './GmgBrowse';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));

// A handful of synthetic rows, varied enough to exercise the Wallet and
// Scope facets without depending on the real 166-charity corpus.
const mockCharities = Array.from({ length: 6 }, (_, i) => ({
  ein: `1${i}-000000${i}`,
  name: `Charity ${i}`,
  category: 'Humanitarian Relief',
  primaryCategory: 'HUMANITARIAN',
  totalRevenue: 1_000_000 * (i + 1),
  isMuslimCharity: i % 2 === 0,
  amalEvaluation: {
    wallet_tag: i % 2 === 0 ? 'ZAKAT-ELIGIBLE' : 'SADAQAH-ONLY',
    amal_score: 70 + i,
    confidence_scores: { impact: 40, alignment: 40, dataConfidence: 0.8 },
  },
  ui_signals_v1: {
    signal_states: { financial_health: 'strong', risk: 'moderate', donor_fit: 'strong' },
    evidence_stage: 'Verified',
  },
  financials: { programExpenseRatio: 0.8 },
}));

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: mockCharities, summaries: mockCharities, loading: false, error: null }),
}));

// The desktop table also has a "Wallet" column header, so every lookup is
// scoped to the facet bar (found via the search input) before narrowing to
// a specific <Kicker>-labelled group, same idea as BrowseFacets.test.tsx.
const facetsSection = (): HTMLElement =>
  screen.getByPlaceholderText('Search charities, EINs, causes…').closest('section') as HTMLElement;
const groupFor = (label: string): HTMLElement =>
  within(facetsSection()).getByText(label).parentElement as HTMLElement;

const robotsTag = (): HTMLElement | null => document.querySelector('meta[name="robots"][data-gmg-facets]');

const renderBrowse = () => render(<MemoryRouter><GmgBrowse isDark={false} /></MemoryRouter>);

beforeEach(() => {
  // Every test starts from a clean, query-free URL regardless of what a
  // prior test's URL-sync effect left behind.
  window.history.replaceState({}, '', '/browse');
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('GmgBrowse SEO guard', () => {
  it('adds no robots meta on the default view', () => {
    renderBrowse();
    expect(robotsTag()).toBeNull();
  });

  it('adds noindex,follow once a facet is selected', async () => {
    const user = userEvent.setup();
    renderBrowse();
    await user.click(within(groupFor('Wallet')).getByRole('button', { name: /Zakat/ }));
    const tag = robotsTag();
    expect(tag).not.toBeNull();
    expect(tag).toHaveAttribute('content', 'noindex,follow');
  });

  it('removes it again when facets are cleared', async () => {
    const user = userEvent.setup();
    renderBrowse();
    await user.click(within(groupFor('Wallet')).getByRole('button', { name: /Zakat/ }));
    expect(robotsTag()).not.toBeNull();
    await user.click(within(groupFor('Wallet')).getByRole('button', { name: /All/ }));
    expect(robotsTag()).toBeNull();
  });

  it('does NOT add it for a search query alone', async () => {
    const user = userEvent.setup();
    renderBrowse();
    await user.type(screen.getByPlaceholderText('Search charities, EINs, causes…'), 'Charity 1');
    expect(robotsTag()).toBeNull();
  });

  it('writes facet state to the URL with replaceState, never pushState', async () => {
    const replaceSpy = vi.spyOn(window.history, 'replaceState');
    const pushSpy = vi.spyOn(window.history, 'pushState');
    const user = userEvent.setup();
    renderBrowse();
    await user.click(within(groupFor('Wallet')).getByRole('button', { name: /Zakat/ }));

    expect(pushSpy).not.toHaveBeenCalled();
    expect(replaceSpy).toHaveBeenCalled();
    const lastUrl = replaceSpy.mock.calls[replaceSpy.mock.calls.length - 1][2] as string;
    expect(lastUrl).toContain('wallet=zakat');
  });

  it('restores facet state from an existing query string on mount', () => {
    window.history.pushState({}, '', '/browse?wallet=zakat');
    renderBrowse();
    expect(within(groupFor('Wallet')).getByRole('button', { name: /Zakat/ })).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders no anchor elements for facet controls', async () => {
    const user = userEvent.setup();
    renderBrowse();
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    expect(facetsSection().querySelectorAll('a')).toHaveLength(0);
  });
});

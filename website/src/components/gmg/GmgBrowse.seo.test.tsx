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
import { render, screen, within, waitFor } from '@testing-library/react';
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

// A charity with no filed program-expense ratio. Deliberately omits
// `financials` entirely (not `financials: { programExpenseRatio: null }`) so
// adaptRow's real fallback chain — financials.programExpenseRatio ??
// rawData.program_expense_ratio — is what produces the null, the same way a
// real under-filed charity would.
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

const allMockCharities = [...mockCharities, NULL_PROGRAM_PCT_CHARITY];

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: allMockCharities, summaries: allMockCharities, loading: false, error: null }),
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

    // The URL write is debounced (Task 3) — wait for it to fire rather than
    // asserting immediately.
    await waitFor(() => expect(replaceSpy).toHaveBeenCalled());
    expect(pushSpy).not.toHaveBeenCalled();
    const lastUrl = replaceSpy.mock.calls[replaceSpy.mock.calls.length - 1][2] as string;
    expect(lastUrl).toContain('wallet=zakat');
  });

  // `query` lives in the same state the URL-sync effect depends on, so
  // typing a search term one keystroke at a time used to fire one
  // history.replaceState per keystroke — browsers rate-limit the history
  // API, and Safari has historically thrown SecurityError past that limit.
  // The debounce should collapse a burst of keystrokes into a single write.
  it('debounces a burst of keystrokes into one URL write, with the final URL correct', async () => {
    const replaceSpy = vi.spyOn(window.history, 'replaceState');
    const user = userEvent.setup();
    renderBrowse();

    const query = 'islamic relief';
    await user.type(screen.getByPlaceholderText('Search charities, EINs, causes…'), query);

    // The 300ms debounce hasn't elapsed yet — none of the 14 keystrokes
    // should have written to the URL synchronously.
    expect(replaceSpy).not.toHaveBeenCalled();

    await waitFor(() => expect(replaceSpy).toHaveBeenCalled());
    expect(replaceSpy.mock.calls.length).toBeLessThan(query.length);
    const lastUrl = replaceSpy.mock.calls[replaceSpy.mock.calls.length - 1][2] as string;
    expect(lastUrl).toContain('q=islamic+relief');
  });

  it('restores facet state from an existing query string on mount', () => {
    window.history.pushState({}, '', '/browse?wallet=zakat');
    renderBrowse();
    expect(within(groupFor('Wallet')).getByRole('button', { name: /Zakat/ })).toHaveAttribute('aria-pressed', 'true');
  });

  // The URL sync effect must MERGE facet params into the query string, not
  // replace it wholesale — otherwise anything this page doesn't own
  // (utm_source, gclid, a hand-typed ?type=) is wiped on mount and again on
  // every later state change.
  it('preserves a non-facet query param on mount and after a facet click', async () => {
    window.history.pushState({}, '', '/browse?utm_source=newsletter');
    const user = userEvent.setup();
    renderBrowse();

    expect(window.location.search).toContain('utm_source=newsletter');

    await user.click(within(groupFor('Wallet')).getByRole('button', { name: /Zakat/ }));

    // The URL write is debounced (Task 3) — wait for it to fire rather than
    // asserting immediately.
    await waitFor(() => expect(window.location.search).toContain('wallet=zakat'));
    expect(window.location.search).toContain('utm_source=newsletter');
  });

  it('renders no anchor elements for facet controls', async () => {
    const user = userEvent.setup();
    renderBrowse();
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    expect(facetsSection().querySelectorAll('a')).toHaveLength(0);
  });
});

// This project has already shipped a null-coerced-to-zero bug on this exact
// page (a null revenue rendered as "$0" via `|| 0` in summaryToProfile,
// fixed in Task 1 of this plan). A null program ratio rendering as "0%"
// would be the same failure mode, and worse: it states as fact that a real
// charity spent nothing on programs.
describe('GmgBrowse Program % column', () => {
  it('renders the em dash for a charity with no reported program ratio, never "0%"', () => {
    renderBrowse();
    const nameCell = screen.getByText('Unreported Program Charity');
    const row = nameCell.closest('tr') as HTMLElement;
    // Column order per COLS (GmgBrowse.tsx): checkbox, name, cause, wallet,
    // overall, finances, risk, donorFit, programPct, evidence, size, chevron.
    const programPctCell = row.querySelectorAll('td')[8];
    expect(programPctCell).toHaveTextContent('—');
    expect(programPctCell).not.toHaveTextContent('0%');
  });
});

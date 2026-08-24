import '@testing-library/jest-dom';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import React, { useReducer } from 'react';
import { BrowseFacets } from './BrowseFacets';
import { adaptRow } from './charityAdapter';
import { buildCharitiesIndex } from '../../hooks/useCharities';
import { INITIAL_FACET_STATE, facetReducer, FacetState } from './facetState';
import { gmgPalette } from './tokens';

const index = JSON.parse(readFileSync(join(__dirname, '../../../data/charities.json'), 'utf-8'));
const rows = buildCharitiesIndex(index).charities.map(adaptRow);
const p = gmgPalette(false);

// Facet pills render as `${label} ${count}`. Deriving the counts keeps this
// file about the pill UI -- which values show, which are pressed, which are
// hidden at zero -- instead of about how many charities carry a tag this
// month. Corpus composition is snapshotted in corpusComposition.test.ts.
const TOTAL = rows.length;
const zakatCount = rows.filter((r) => r.walletIsZakat).length;
const usaCount = rows.filter((r) => r.regionTags.includes('usa')).length;
const fuqaraCount = rows.filter((r) => r.asnafTags.includes('fuqara')).length;
const zakatPill = `Zakat ${zakatCount}`;
const usaPill = `United States ${usaCount}`;
const fuqaraPill = `Fuqara (the poor) ${fuqaraCount}`;
const sadaqahPill = `Sadaqah ${TOTAL - zakatCount}`;
const muslimLedPill = `Muslim-led ${rows.filter((r) => r.isMuslimLed).length}`;
const humanitarianPill = `Humanitarian Relief ${rows.filter((r) => r.causeKey === 'HUMANITARIAN').length}`;

// A thin harness that owns real reducer state, the same wiring GmgBrowse
// uses, so a click really goes click -> dispatch -> re-render.
const Harness: React.FC<{ initial?: FacetState; isMobile?: boolean }> = ({
  initial = INITIAL_FACET_STATE,
  isMobile = false,
}) => {
  const [state, dispatch] = useReducer(facetReducer, initial);
  return (
    <BrowseFacets
      state={state}
      dispatch={dispatch}
      rows={rows}
      p={p}
      padX={16}
      isMobile={isMobile}
      total={rows.length}
      resultCount={rows.length}
    />
  );
};

// Facet groups share the string "All" across Wallet and Scope, so scope
// every lookup to its own <Kicker>-labelled group rather than querying the
// whole screen. The Kicker itself is a <span>, so its parent is the group's
// wrapping <span> that also holds the pill buttons.
const groupFor = (label: string): HTMLElement => screen.getByText(label).parentElement as HTMLElement;

describe('BrowseFacets', () => {
  it('renders every facet control as a button, never a link', async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    expect(container.querySelectorAll('a')).toHaveLength(0);
    expect(container.querySelectorAll('button').length).toBeGreaterThan(10);
  });

  it('shows counts beside each value', () => {
    render(<Harness />);
    expect(within(groupFor('Wallet')).getByRole('button', { name: zakatPill })).toBeInTheDocument();
    expect(within(groupFor('Wallet')).getByRole('button', { name: sadaqahPill })).toBeInTheDocument();
    expect(within(groupFor('Scope')).getByRole('button', { name: muslimLedPill })).toBeInTheDocument();
  });

  it('hides the Cause and Region rows until More filters is clicked', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.queryByRole('button', { name: humanitarianPill })).toBeNull();
    expect(screen.queryByRole('button', { name: usaPill })).toBeNull();

    await user.click(screen.getByRole('button', { name: /More filters/ }));

    expect(screen.getByRole('button', { name: humanitarianPill })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: usaPill })).toBeInTheDocument();
  });

  it('opens the expander already-open when a facet inside it is selected', () => {
    const initial: FacetState = { ...INITIAL_FACET_STATE, cause: ['HUMANITARIAN'] };
    render(<Harness initial={initial} />);
    // No click on "More filters" — it must already be open.
    expect(screen.getByRole('button', { name: humanitarianPill })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /More filters \(1\)/ })).toBeInTheDocument();
  });

  it('omits zero-count values that are not selected', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    // Only 4 of the 8 Qur'anic asnaf appear anywhere in the corpus.
    expect(within(groupFor('Zakat asnaf')).getByRole('button', { name: fuqaraPill })).toBeInTheDocument();
    expect(within(groupFor('Zakat asnaf')).queryByRole('button', { name: /Amilin/ })).toBeNull();
    expect(within(groupFor('Zakat asnaf')).queryByRole('button', { name: /Riqab/ })).toBeNull();
  });

  it('keeps a selected value visible even when its count drops to zero', () => {
    // No Muslim-led charity in the corpus is categorized ENVIRONMENT_CLIMATE,
    // so selecting it alongside the Muslim-led scope zeroes its own count.
    const initial: FacetState = { ...INITIAL_FACET_STATE, scope: 'muslim', cause: ['ENVIRONMENT_CLIMATE'] };
    render(<Harness initial={initial} />);
    const pill = screen.getByRole('button', { name: 'Environment & Climate 0' });
    expect(pill).toBeInTheDocument();
    expect(pill).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows Clear all only once something is filtered', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull();

    await user.click(within(groupFor('Wallet')).getByRole('button', { name: zakatPill }));

    expect(screen.getByRole('button', { name: 'Clear all' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Clear all' }));

    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull();
  });

  it('shows Clear all for a search query alone, with no facet selected', async () => {
    // isFacetActive deliberately ignores `query` (see facetState.ts), so a
    // visitor who has only typed a search still needs a way to reset —
    // showClearAll must check the query independently of isFacetActive.
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull();

    await user.type(screen.getByLabelText('Search charities'), 'islamic');

    expect(screen.getByRole('button', { name: 'Clear all' })).toBeInTheDocument();
  });

  it('dispatches a toggle with the right facet and value on click', async () => {
    const user = userEvent.setup();
    const dispatch = vi.fn();
    render(
      <BrowseFacets
        state={INITIAL_FACET_STATE}
        dispatch={dispatch}
        rows={rows}
        p={p}
        padX={16}
        isMobile={false}
        total={rows.length}
        resultCount={rows.length}
      />,
    );
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    await user.click(screen.getByRole('button', { name: humanitarianPill }));
    expect(dispatch).toHaveBeenCalledWith({ type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
  });

  it('marks selected pills with aria-pressed', () => {
    const initial: FacetState = { ...INITIAL_FACET_STATE, wallet: 'zakat' };
    render(<Harness initial={initial} />);
    const wallet = groupFor('Wallet');
    expect(within(wallet).getByRole('button', { name: zakatPill })).toHaveAttribute('aria-pressed', 'true');
    expect(within(wallet).getByRole('button', { name: `Wallet: All ${TOTAL}` })).toHaveAttribute('aria-pressed', 'false');
  });

  it('keeps the expander closed by default on mobile even when an inner facet is already active, but still shows the count', () => {
    const initial: FacetState = { ...INITIAL_FACET_STATE, region: ['usa'] };
    render(<Harness initial={initial} isMobile />);
    expect(screen.getByRole('button', { name: /More filters \(1\)/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /United States/ })).toBeNull();
  });

  // Under scope=muslim, Nigeria (region) and Environment & Climate (cause)
  // both drop to 0 matching charities in the real corpus — verified directly
  // against data/charities.json, not asserted from a mocked fixture. Neither
  // is selected, so the zero-count rule should hide both, the same way it
  // already hides zero-count asnaf. Only the asnaf case had a test before.
  it('omits zero-count region and cause values under a narrowed scope, not just asnaf', async () => {
    const user = userEvent.setup();
    const initial: FacetState = { ...INITIAL_FACET_STATE, scope: 'muslim' };
    render(<Harness initial={initial} />);
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    expect(within(groupFor('Where it works')).queryByRole('button', { name: /Nigeria/ })).toBeNull();
    expect(within(groupFor('Cause')).queryByRole('button', { name: /Environment & Climate/ })).toBeNull();
  });

  // Wallet's and Scope's "All" pill both read the same "All {total}" by default, and a
  // screen-reader user tabbing the strip has no way to tell them apart. Every
  // button in the (fully expanded) strip must have a distinct accessible
  // name. None of these buttons use aria-labelledby, a title attribute, or
  // nested images, so aria-label (when set) or else the normalized text
  // content is the accessible name — the same precedence the real Accessible
  // Name computation uses for a plain <button>.
  const accessibleName = (el: HTMLElement): string =>
    (el.getAttribute('aria-label') ?? el.textContent ?? '').replace(/\s+/g, ' ').trim();

  it('gives no two buttons in the strip the same accessible name', async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    const names = Array.from(container.querySelectorAll('button')).map(accessibleName);
    expect(new Set(names).size).toBe(names.length);
  });
});

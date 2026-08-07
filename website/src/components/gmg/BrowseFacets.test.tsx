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
    expect(within(groupFor('Wallet')).getByRole('button', { name: 'Zakat 90' })).toBeInTheDocument();
    expect(within(groupFor('Wallet')).getByRole('button', { name: 'Sadaqah 76' })).toBeInTheDocument();
    expect(within(groupFor('Scope')).getByRole('button', { name: 'Muslim-led 123' })).toBeInTheDocument();
  });

  it('hides the Cause and Region rows until More filters is clicked', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.queryByRole('button', { name: 'Humanitarian Relief 35' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'United States 52' })).toBeNull();

    await user.click(screen.getByRole('button', { name: /More filters/ }));

    expect(screen.getByRole('button', { name: 'Humanitarian Relief 35' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'United States 52' })).toBeInTheDocument();
  });

  it('opens the expander already-open when a facet inside it is selected', () => {
    const initial: FacetState = { ...INITIAL_FACET_STATE, cause: ['HUMANITARIAN'] };
    render(<Harness initial={initial} />);
    // No click on "More filters" — it must already be open.
    expect(screen.getByRole('button', { name: 'Humanitarian Relief 35' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /More filters \(1\)/ })).toBeInTheDocument();
  });

  it('omits zero-count values that are not selected', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: /More filters/ }));
    // Only 4 of the 8 Qur'anic asnaf appear anywhere in the corpus.
    expect(within(groupFor('Zakat asnaf')).getByRole('button', { name: 'Fuqara (the poor) 89' })).toBeInTheDocument();
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

    await user.click(within(groupFor('Wallet')).getByRole('button', { name: 'Zakat 90' }));

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
    await user.click(screen.getByRole('button', { name: 'Humanitarian Relief 35' }));
    expect(dispatch).toHaveBeenCalledWith({ type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
  });

  it('marks selected pills with aria-pressed', () => {
    const initial: FacetState = { ...INITIAL_FACET_STATE, wallet: 'zakat' };
    render(<Harness initial={initial} />);
    const wallet = groupFor('Wallet');
    expect(within(wallet).getByRole('button', { name: 'Zakat 90' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(wallet).getByRole('button', { name: 'All 166' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('keeps the expander closed by default on mobile even when an inner facet is already active, but still shows the count', () => {
    const initial: FacetState = { ...INITIAL_FACET_STATE, region: ['usa'] };
    render(<Harness initial={initial} isMobile />);
    expect(screen.getByRole('button', { name: /More filters \(1\)/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /United States/ })).toBeNull();
  });
});

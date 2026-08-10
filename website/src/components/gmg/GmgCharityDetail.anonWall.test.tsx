/**
 * GmgCharityDetail — the baseline/rich tier boundary
 *
 * A signed-out visitor (and every SSR pass, which has no FirebaseProvider
 * and so is always signed-out — see useCommunityMember) sees the whole
 * BASELINE tier: identity, the quality bands, the hard financials, the
 * ui_signals_v1 tags, all six donor-question sections, the SectionRail and
 * the methodology block — plus the AnonWall prompt after it.
 *
 * Exactly two things are member-only, and this file pins both:
 *   1. Raw score numerals (`37 / 50`, `{scored}/{possible}`). The
 *      qualitative band beside each one is public, matching /browse, which
 *      publishes bands to anonymous visitors but never numbers.
 *   2. Rich-tier content, gated inside each section's own GatedBlock —
 *      covered by the per-section tests, not repeated here.
 */

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { MemoryRouter } from 'react-router-dom';
import { GmgCharityDetail } from './GmgCharityDetail';

const mockMember = vi.fn(() => false);
vi.mock('../../auth/useAuth', () => ({ useCommunityMember: () => mockMember() }));
vi.mock('../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));

// A couple of same-category peers so the (always-public) similar-charities
// block has something to render in both states — this file isn't testing
// that block itself (see GmgCharityDetail.similar.test.tsx), only that its
// presence doesn't depend on member state.
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({
    summaries: [
      // GmgCharityDetail's similar-selector reads `charity.primaryCategory`
      // (raw top-level field, "HUMANITARIAN") for the current charity, not
      // the display label c.category ("Humanitarian Relief") — match on that.
      { ein: '13-5660870', name: 'International Rescue Committee', category: 'HUMANITARIAN', primaryCategory: 'HUMANITARIAN', walletTag: 'ZAKAT-ELIGIBLE', amalScore: 78 },
      { ein: '11-1111111', name: 'Peer Alpha', category: 'HUMANITARIAN', primaryCategory: 'HUMANITARIAN', walletTag: 'ZAKAT-ELIGIBLE', amalScore: 70 },
      { ein: '22-2222222', name: 'Peer Beta', category: 'HUMANITARIAN', primaryCategory: 'HUMANITARIAN', walletTag: 'ZAKAT-ELIGIBLE', amalScore: 65 },
    ],
    loading: false,
    charities: [],
  }),
}));

const dir = path.resolve(__dirname, '../../../data/charities');
const ircRaw = JSON.parse(fs.readFileSync(path.join(dir, 'charity-13-5660870.json'), 'utf8'));

const renderDetail = () =>
  render(
    <MemoryRouter>
      <GmgCharityDetail charity={ircRaw} isDark={false} />
    </MemoryRouter>,
  );

const SECTION_IDS = ['what-they-do', 'money', 'trust', 'run-well', 'right-for-you', 'compares'];

describe('GmgCharityDetail — signed out', () => {
  it('shows identity: name, EIN, category, and zakat status (wallet + asnaf)', () => {
    mockMember.mockReturnValue(false);
    const { container } = renderDetail();
    expect(container.querySelector('h1')?.textContent).toBe('International Rescue Committee');
    expect(container.textContent).toContain('EIN 13-5660870');
    expect(container.textContent).toContain('Humanitarian Relief');
    expect(container.textContent).toContain('Accepts Zakat');
    expect(container.textContent).toContain('Fuqara');
  });

  it('mounts every section wrapper and the SectionRail', () => {
    mockMember.mockReturnValue(false);
    const { container, getByLabelText } = renderDetail();
    for (const id of SECTION_IDS) {
      expect(container.querySelector(`[data-section="${id}"]`)).not.toBeNull();
    }
    expect(getByLabelText('Page sections')).toBeInTheDocument();
  });

  it('hides the raw score numerals but keeps the bands beside them', () => {
    mockMember.mockReturnValue(false);
    const { container } = renderDetail();
    expect(container.textContent).not.toContain('37 / 50');
    expect(container.textContent).not.toContain('41 / 50');
    // The DimensionDetail criteria numerals go too. Anchored to the criterion
    // name because a bare /\d+\/\d+/ also matches legitimate baseline prose
    // ("97.0/100 from Charity Navigator", "Cause area: Humanitarian (13/13)").
    expect(container.textContent).not.toMatch(/Cost Per Beneficiary\s*\d+\/\d+/);
    // ...while the qualitative bands those numerals annotate remain.
    expect(container.textContent).toContain('Cost Per Beneficiary');
    expect(container.textContent).toContain('Program Ratio');
  });

  it('shows the financial figures and the ui_signals tags', () => {
    mockMember.mockReturnValue(false);
    const { container } = renderDetail();
    expect(container.textContent).toContain('$4,088');
    expect(container.textContent).toContain('88%');
    expect(container.textContent).toContain('2.4 mo');
    expect(container.textContent).toContain('High Conviction');
    expect(container.textContent).toContain('Frontline Relief');
    expect(container.textContent).toContain('Verified');
  });

  it('shows every section heading and the methodology block', () => {
    mockMember.mockReturnValue(false);
    const { container } = renderDetail();
    expect(container.textContent).toContain('What they do, and is it real?');
    expect(container.textContent).toContain('Where your money goes');
    expect(container.textContent).toContain('Can you trust these numbers?');
    expect(container.textContent).toContain('Is it run well?');
    expect(container.textContent).toContain('Is it right for you?');
    expect(container.textContent).toContain('How it compares');
    expect(container.textContent).toContain('Methodology details');
  });

  it('shows the prompt and the similar-charities block', () => {
    mockMember.mockReturnValue(false);
    const { container, getByText } = renderDetail();
    // Matched on the wall's own headline rather than /is free/, which now
    // also matches each GatedBlock's inline "Sign in to see this — it's free."
    expect(getByText(/The in-depth analysis of .* is free/i)).toBeInTheDocument();
    expect(container.querySelector('[aria-labelledby="gmg-similar-heading"]')).not.toBeNull();
  });
});

describe('GmgCharityDetail — signed in', () => {
  it('renders all six sections and the rail', () => {
    mockMember.mockReturnValue(true);
    const { container, getByLabelText } = renderDetail();
    for (const id of SECTION_IDS) {
      expect(container.querySelector(`[data-section="${id}"]`)).not.toBeNull();
    }
    expect(getByLabelText('Page sections')).toBeInTheDocument();
  });

  it('adds the raw score numerals on top of the baseline tier', () => {
    mockMember.mockReturnValue(true);
    const { container } = renderDetail();
    expect(container.textContent).toContain('37 / 50');
    expect(container.textContent).toContain('41 / 50');
    // The counterpart of the signed-out assertion above — proves that check
    // is load-bearing rather than matching a pattern that never renders.
    expect(container.textContent).toMatch(/Cost Per Beneficiary\s*\d+\/\d+/);
    expect(container.textContent).toContain('$4,088');
    expect(container.textContent).toContain('88%');
    expect(container.textContent).toContain('2.4 mo');
    expect(container.textContent).toContain('High Conviction');
    expect(container.textContent).toContain('Frontline Relief');
    expect(container.textContent).toContain('Verified');
  });

  it('renders the methodology block and no wall', () => {
    mockMember.mockReturnValue(true);
    const { container, queryByText } = renderDetail();
    expect(container.textContent).toContain('Methodology details');
    expect(queryByText(/is free/i)).toBeNull();
  });
});

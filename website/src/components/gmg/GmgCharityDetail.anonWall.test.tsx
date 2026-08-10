/**
 * GmgCharityDetail — the anonymous wall
 *
 * A signed-out visitor (and every SSR pass, which has no FirebaseProvider
 * and so is always signed-out — see useCommunityMember) must see only the
 * charity's identity, one wall panel, and the similar-charities block. All
 * six donor-question sections, the stat strip, the rating cards, the
 * conviction/quality tags, the SectionRail, and the methodology block are
 * for members only. A signed-in member must see exactly what this page
 * has always rendered.
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

  it('mounts no section wrappers and no SectionRail', () => {
    mockMember.mockReturnValue(false);
    const { container, queryByLabelText } = renderDetail();
    expect(container.querySelectorAll('[data-section]')).toHaveLength(0);
    expect(queryByLabelText('Page sections')).toBeNull();
  });

  it('hides the scores, financial figures, and conviction tags', () => {
    mockMember.mockReturnValue(false);
    const { container } = renderDetail();
    expect(container.textContent).not.toContain('37 / 50');
    expect(container.textContent).not.toContain('41 / 50');
    expect(container.textContent).not.toContain('$4,088');
    expect(container.textContent).not.toContain('88%');
    expect(container.textContent).not.toContain('2.4 mo');
    expect(container.textContent).not.toContain('Strong Match');
    expect(container.textContent).not.toContain('High Conviction');
    expect(container.textContent).not.toContain('Frontline Relief');
    expect(container.textContent).not.toContain('Verified');
  });

  it('hides every section heading and the methodology block', () => {
    mockMember.mockReturnValue(false);
    const { container } = renderDetail();
    expect(container.textContent).not.toContain('What they do, and is it real?');
    expect(container.textContent).not.toContain('Where your money goes');
    expect(container.textContent).not.toContain('Can you trust these numbers?');
    expect(container.textContent).not.toContain('Is it run well?');
    expect(container.textContent).not.toContain('Is it right for you?');
    expect(container.textContent).not.toContain('How it compares');
    expect(container.textContent).not.toContain('Methodology details');
  });

  it('shows the wall and the similar-charities block', () => {
    mockMember.mockReturnValue(false);
    const { container, getByText } = renderDetail();
    expect(getByText(/is free/i)).toBeInTheDocument();
    expect(getByText('Sign in')).toBeInTheDocument();
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

  it('renders the scores, financial figures, and conviction tags', () => {
    mockMember.mockReturnValue(true);
    const { container } = renderDetail();
    expect(container.textContent).toContain('37 / 50');
    expect(container.textContent).toContain('41 / 50');
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

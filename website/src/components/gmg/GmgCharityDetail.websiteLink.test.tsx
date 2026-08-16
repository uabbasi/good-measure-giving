// The hero previously rendered exactly one outbound link, labeled "Donate",
// which silently WAS the org's plain homepage whenever no dedicated donation
// page existed (donateUrl = donationUrl || website). Found in manual QA:
// there was no way to just browse an organization's own site before
// deciding to donate. Now a distinct "Visit website" link renders whenever
// the two URLs actually differ, and takes over the PRIMARY (filled) button
// styling when there's no dedicated donateUrl at all — see 1368108, which
// also separated the two fields (donateUrl no longer falls back to
// website) and superseded this file's original, plainer "Website ↗" design.

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { MemoryRouter } from 'react-router-dom';
import { GmgCharityDetail } from './GmgCharityDetail';

vi.mock('../../auth/useAuth', () => ({ useCommunityMember: () => false }));
vi.mock('../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: [], loading: false, charities: [] }),
}));

const dir = path.resolve(__dirname, '../../../data/charities');
const load = (ein: string) => JSON.parse(fs.readFileSync(path.join(dir, `charity-${ein}.json`), 'utf8'));

const renderDetail = (raw: unknown) =>
  render(
    <MemoryRouter>
      <GmgCharityDetail charity={raw} isDark={false} />
    </MemoryRouter>,
  );

describe('GmgCharityDetail — Website link', () => {
  it('renders a distinct "Visit website" link alongside Donate when the two URLs differ', () => {
    const raw = load('13-5660870'); // IRC: website https://rescue.org, donationUrl https://www.rescue.org/
    expect(raw.website).not.toBe(raw.donationUrl);
    const { getByText } = renderDetail(raw);
    const donateLink = getByText('Donate ↗').closest('a');
    const websiteLink = getByText('Visit website ↗').closest('a');
    expect(donateLink).not.toBeNull();
    expect(websiteLink).not.toBeNull();
    expect(websiteLink!.getAttribute('href')).toBe(raw.website);
    expect(donateLink!.getAttribute('href')).not.toBe(websiteLink!.getAttribute('href'));
  });

  it('omits the website link rather than repeating the same URL under two labels', () => {
    const raw = load('13-5660870');
    raw.donationUrl = raw.website; // force the no-dedicated-donation-page case
    const { getByText, queryByText } = renderDetail(raw);
    expect(getByText('Donate ↗')).toBeInTheDocument();
    expect(queryByText('Visit website ↗')).toBeNull();
  });

  it('promotes "Visit website" to the primary button when there is no dedicated donateUrl', () => {
    const raw = load('13-5660870');
    raw.donationUrl = null; // no dedicated donation page at all, only a homepage
    const { getByText, queryByText } = renderDetail(raw);
    expect(queryByText('Donate ↗')).toBeNull();
    const websiteLink = getByText('Visit website ↗').closest('a') as HTMLAnchorElement;
    expect(websiteLink.getAttribute('href')).toBe(raw.website);
    // Filled/primary styling — the same treatment Donate gets when it exists.
    expect(websiteLink.style.fontWeight).toBe('500');
  });
});

// The hero previously rendered exactly one outbound link, labeled "Donate",
// which silently WAS the org's plain homepage whenever no dedicated donation
// page existed (donateUrl = donationUrl || website). Found in manual QA:
// there was no way to just browse an organization's own site before
// deciding to donate. Now a distinct "Website" link renders whenever the
// two URLs actually differ — 151 of 166 charities gain one; the other 15
// only have one URL at all, so there's nothing distinct to show.

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
  it('renders a distinct Website link alongside Donate when the two URLs differ', () => {
    const raw = load('13-5660870'); // IRC: website https://rescue.org, donationUrl https://www.rescue.org/
    expect(raw.website).not.toBe(raw.donationUrl);
    const { getByText } = renderDetail(raw);
    const donateLink = getByText('Donate ↗').closest('a');
    const websiteLink = getByText('Website ↗').closest('a');
    expect(donateLink).not.toBeNull();
    expect(websiteLink).not.toBeNull();
    expect(websiteLink!.getAttribute('href')).toBe(raw.website);
    expect(donateLink!.getAttribute('href')).not.toBe(websiteLink!.getAttribute('href'));
  });

  it('omits the Website link rather than repeating the same URL under two labels', () => {
    const raw = load('13-5660870');
    raw.donationUrl = raw.website; // force the no-dedicated-donation-page case
    const { getByText, queryByText } = renderDetail(raw);
    expect(getByText('Donate ↗')).toBeInTheDocument();
    expect(queryByText('Website ↗')).toBeNull();
  });
});

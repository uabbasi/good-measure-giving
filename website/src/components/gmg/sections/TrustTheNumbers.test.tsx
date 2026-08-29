import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { TrustTheNumbers } from './TrustTheNumbers';
import { gmgPalette } from '../tokens';
import { adaptCharity } from '../charityAdapter';

const mockMember = vi.fn(() => false);
vi.mock('../../../auth/useAuth', () => ({ useCommunityMember: () => mockMember() }));
vi.mock('../../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const p = gmgPalette(false);
const dir = path.resolve(__dirname, '../../../../data/charities');
const load = (file: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')));

/**
 * Pick a charity out of the real corpus by the shape the test needs.
 *
 * Pinned EINs annotated with the shape they had when written ("3 concerns,
 * 1 trust-anchored", "standardsMet is 0") fail on their own precondition once
 * regeneration moves the charity, having tested nothing. Searching for the
 * shape keeps the case real; throwing when it is gone says so rather than
 * passing vacuously.
 */
const corpus = fs
  .readdirSync(dir)
  .filter((f) => f.endsWith('.json'))
  .map((f) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'))));

type Charity = (typeof corpus)[number];

const pick = (shape: string, predicate: (c: Charity) => boolean): Charity => {
  const found = corpus.find(predicate);
  if (!found) throw new Error(`No charity in the corpus is ${shape} — the case is gone.`);
  return found;
};

// Has a BBB reviewUrl, standardsMet === 0 (present, must still render since
// the guard is presence-based not truthy-based), and all three award URLs.
// concerns.all has 2 entries but byAnchor.trust is empty (both anchor
// elsewhere) — the common case: nothing in the trust-concerns block, but the
// pointer line still points at the 2 caveats shown elsewhere on the page.
const richTrust = () => load('charity-01-0548371.json');
// A BBB standards-met count of exactly 0 — a real value, not an absence.
const zeroStandardsMet = () =>
  pick('reporting exactly 0 BBB standards met', (c) => c.bbb.standardsMet === 0);
// One of only 7 charities fleet-wide with a byAnchor.trust concern
// ("Organization has negative net assets") — 1 of its 3 total concerns.
const withTrustConcern = () =>
  pick(
    'carrying exactly one trust-anchored concern plus concerns anchored elsewhere',
    (c) => c.concerns.byAnchor.trust.length === 1 && c.concerns.all.length > 1,
  );
// bbb.summary present but reviewUrl is null.
const noBbbReviewUrl = () => load('charity-11-3013369.json');
// Two provenance entries with a null sourceUrl, out of 14 total.
const provenanceGaps = () => load('charity-04-2535767.json');
// dataAgeYears = 6 -> dated-data badge should appear.
const datedData = () => load('charity-20-0310701.json');
// dataAgeYears = null, zero concerns, no awards, no BBB reviewUrl.
const bare = () => load('charity-20-8085421.json');
// bbb.standardsMet is null (not present at all, distinct from 0).
// No charity in the corpus reports a null standards-met count any more, so
// this one is constructed from a real charity with just that field cleared.
// The behaviour under test — null must not render "standards met", while 0
// must — is worth keeping whether or not the corpus currently exhibits it.
const noStandardsMet = () => {
  const base = zeroStandardsMet();
  return { ...base, bbb: { ...base.bbb, standardsMet: null } };
};

describe('TrustTheNumbers', () => {
  it('gates only the BBB assessment; data vintage, concerns, provenance, and badge links stay public', () => {
    mockMember.mockReturnValue(false);
    const c = richTrust();
    const { container } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain("Sign in to see this — it's free.");
    // The BBB assessment prose must not leak while signed out.
    expect(container.textContent).not.toContain(c.bbb.summary);
    // But everything else on this page stays public, including the raw
    // verification-badge links (a different thing from the BBB assessment).
    expect(container.textContent).toContain(String(c.citations.ordered.length));
    const hrefs = Array.from(container.querySelectorAll('a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toContain(c.awards.bbbUrl);
  });

  it('shows the dated-data badge only once data age crosses the threshold', () => {
    const dated = datedData();
    expect(dated.dataAgeYears).toBe(6);
    const { container: datedContainer } = render(<TrustTheNumbers c={dated} p={p} isMobile={false} padX={16} />);
    expect(datedContainer.textContent).toContain('Dated data');
    expect(datedContainer.textContent).toContain('6 years since last filed 990');

    const recent = bare();
    expect(recent.dataAgeYears).toBeNull();
    const { container: recentContainer } = render(<TrustTheNumbers c={recent} p={p} isMobile={false} padX={16} />);
    expect(recentContainer.textContent).not.toContain('Dated data');
  });

  it('renders only byAnchor.trust concerns here, not the full concerns.all list, and points to the rest', () => {
    const c = withTrustConcern();
    expect(c.concerns.byAnchor.trust).toHaveLength(1);
    // More than the trust one, so the "don't duplicate the others" check below
    // has something to prove. The literal 3 moved with regeneration.
    expect(c.concerns.all.length).toBeGreaterThan(1);
    const { container } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    // The trust-anchored concern renders.
    expect(container.textContent).toContain(c.concerns.byAnchor.trust[0].headline);
    // The other 2 concerns (anchored elsewhere: domestic_burn -> money,
    // risk_deduction -> risks) must NOT be duplicated here.
    for (const concern of c.concerns.all) {
      if (concern.anchor === 'trust') continue;
      expect(container.textContent).not.toContain(concern.headline);
    }
    // A pointer line names the count of caveats shown elsewhere.
    expect(container.textContent).toContain(
      `${c.concerns.all.length - c.concerns.byAnchor.trust.length} further caveats appear beside`,
    );
  });

  it('shows no trust concerns for the common case (7 of 343 concerns fleet-wide are trust-anchored), but still points to the caveats shown elsewhere', () => {
    const c = richTrust();
    expect(c.concerns.byAnchor.trust).toHaveLength(0);
    expect(c.concerns.all.length).toBe(2);
    const { container } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    // Neither of this charity's 2 concerns is trust-anchored, so neither
    // headline should appear (nothing to duplicate, nothing to leak).
    for (const concern of c.concerns.all) {
      expect(container.textContent).not.toContain(concern.headline);
    }
    expect(container.textContent).toContain(
      `${c.concerns.all.length - c.concerns.byAnchor.trust.length} further caveats appear beside`,
    );
  });

  it('collapses the trust-concerns block to nothing — no heading, no pointer line — when there are no concerns at all', () => {
    const c = bare();
    expect(c.concerns.all).toHaveLength(0);
    expect(c.concerns.byAnchor.trust).toHaveLength(0);
    const { container } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain('further caveat');
  });

  it('never drops a provenance row for lacking a sourceUrl — it renders label-only', () => {
    const c = provenanceGaps();
    const noUrlRows = c.provenance.filter((row) => row.sourceUrl == null);
    expect(noUrlRows.length).toBeGreaterThan(0);
    const { container } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    for (const row of c.provenance) {
      expect(container.textContent).toContain(row.sourceName);
    }
    // No-URL rows must not produce an outbound link for their source name.
    for (const row of noUrlRows) {
      const link = Array.from(container.querySelectorAll('a')).find((a) => a.textContent?.includes(row.sourceName));
      expect(link).toBeUndefined();
    }
  });

  it('renders the provenance table as a header + grid rows on desktop, and as stacked cards on mobile', () => {
    const c = provenanceGaps();
    const { container: desktop } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    expect(desktop.textContent).toContain('Fiscal year');
    expect(desktop.innerHTML).toContain('1.1fr 1.3fr 0.5fr');

    const { container: mobile } = render(<TrustTheNumbers c={c} p={p} isMobile={true} padX={16} />);
    // The column-header row is desktop-only.
    expect(mobile.textContent).not.toContain('Fiscal year');
    expect(mobile.innerHTML).not.toContain('1.1fr 1.3fr 0.5fr');
    // But the same rows still render with their content intact.
    for (const row of c.provenance) {
      expect(mobile.textContent).toContain(row.sourceName);
    }
  });

  it('renders BBB statuses to a signed-in member, and standardsMet only when present (0 counts as present, null does not)', () => {
    mockMember.mockReturnValue(true);
    const zero = zeroStandardsMet();
    expect(zero.bbb.standardsMet).toBe(0);
    const { container: zeroContainer } = render(<TrustTheNumbers c={zero} p={p} isMobile={false} padX={16} />);
    expect(zeroContainer.textContent).toContain('0 standards met');

    const nullCase = noStandardsMet();
    expect(nullCase.bbb.standardsMet).toBeNull();
    const { container: nullContainer } = render(<TrustTheNumbers c={nullCase} p={p} isMobile={false} padX={16} />);
    expect(nullContainer.textContent).not.toContain('standards met');
  });

  it('links the BBB review only when reviewUrl is present, once signed in', () => {
    mockMember.mockReturnValue(true);
    const withUrl = richTrust();
    expect(withUrl.bbb.reviewUrl).toBeTruthy();
    const { getByText, unmount } = render(<TrustTheNumbers c={withUrl} p={p} isMobile={false} padX={16} />);
    expect(getByText('Read the BBB review ↗').closest('a')).toHaveAttribute('href', withUrl.bbb.reviewUrl as string);
    unmount();

    const withoutUrl = noBbbReviewUrl();
    expect(withoutUrl.bbb.reviewUrl).toBeNull();
    expect(withoutUrl.bbb.summary).toBeTruthy();
    const { queryByText } = render(<TrustTheNumbers c={withoutUrl} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Read the BBB review ↗')).toBeNull();
  });

  it('gates the BBB review link behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const withUrl = richTrust();
    const { queryByText } = render(<TrustTheNumbers c={withUrl} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Read the BBB review ↗')).toBeNull();
  });

  it('renders a verification badge link for every award URL present, and none when absent', () => {
    const c = richTrust();
    expect(c.awards.cnUrl).toBeTruthy();
    expect(c.awards.candidUrl).toBeTruthy();
    expect(c.awards.bbbUrl).toBeTruthy();
    const { container, unmount } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    const hrefs = Array.from(container.querySelectorAll('a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toContain(c.awards.cnUrl);
    expect(hrefs).toContain(c.awards.candidUrl);
    expect(hrefs).toContain(c.awards.bbbUrl);
    unmount();

    const none = bare();
    expect(none.awards.cnUrl).toBeNull();
    expect(none.awards.candidUrl).toBeNull();
    expect(none.awards.bbbUrl).toBeNull();
    const { queryByText } = render(<TrustTheNumbers c={none} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Verification badges')).toBeNull();
  });

  it('renders the sourced-claims count from citations.ordered', () => {
    const c = richTrust();
    expect(c.citations.ordered.length).toBeGreaterThan(0);
    const { container } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(`${c.citations.ordered.length}`);
    expect(container.textContent).toContain('sourced claims');
  });

  it('always mounts the section wrapper even for a minimal charity', () => {
    const minimal = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    const { container } = render(<TrustTheNumbers c={minimal} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('[data-section="trust"]')).not.toBeNull();
  });

  it('renders every real charity in the corpus without throwing, in both layouts', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let rendered = 0;
    for (const f of files) {
      const c = load(f);
      const { unmount } = render(<TrustTheNumbers c={c} p={p} isMobile={false} padX={16} />);
      unmount();
      const { unmount: unmountMobile } = render(<TrustTheNumbers c={c} p={p} isMobile={true} padX={16} />);
      unmountMobile();
      rendered += 1;
    }
    expect(rendered).toBe(files.length);
  }, 30000); // renders 166 charities x 2 layouts; generous margin under worker contention
});

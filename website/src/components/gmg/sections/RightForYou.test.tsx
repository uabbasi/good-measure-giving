import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { RightForYou } from './RightForYou';
import { gmgPalette } from '../tokens';
import { adaptCharity } from '../charityAdapter';

const mockMember = vi.fn(() => false);
vi.mock('../../../auth/useAuth', () => ({ useCommunityMember: () => mockMember() }));
vi.mock('../../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const p = gmgPalette(false);
const dir = path.resolve(__dirname, '../../../../data/charities');
const load = (file: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')));

// claimsZakat, asnaf category present, meaningful zakatAsnafServed (fuqara +
// masakin + ...), notIdealFor present, caseAgainstFactors + mitigation
// present, idealFor/considerations/bestForSummary present.
const richZakat = () => load('charity-04-3810161.json');
// case_against.summary carries a <cite> marker in this fixture (charity-04-3810161's
// does not) — used only for the citation-rendering assertion.
const citedCaseAgainst = () => load('charity-01-0548371.json');
// claimsZakat FALSE (Sadaqah), zakatAsnafServed is an empty list (legitimate
// non-applicability, not a gap), notIdealFor empty, but idealFor/considerations/
// caseAgainstFactors present.
const noAsnafNotZakat = () => load('charity-04-2535767.json');
// zakat-collecting charity with a zakat_hoarding concern (byAnchor.zakat).
const withZakatConcern = () => load('charity-20-0310701.json');

describe('RightForYou', () => {
  it('renders zakat verification: Pass tag, quoted evidence, and asnaf category', () => {
    const c = richZakat();
    expect(c.claimsZakat).toBe(true);
    expect(c.asnaf).toBeTruthy();
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Pass');
    expect(container.textContent).toContain(c.zakatEvidence);
    expect(container.textContent).toContain(c.asnaf as string);
  });

  it('shows Sadaqah (not Pass) for a charity that does not claim zakat', () => {
    const c = noAsnafNotZakat();
    expect(c.claimsZakat).toBe(false);
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Sadaqah');
    expect(container.textContent).not.toContain('Pass');
  });

  it('renders the donor-fit matrix including asnaf served when the list is meaningful', () => {
    const c = richZakat();
    const dfm = c.donorFitMatrix;
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(dfm.causeArea);
    expect(container.textContent).toContain(dfm.givingStyle);
    expect(container.textContent).toContain(dfm.evidenceRigor);
    expect(container.textContent).toContain(dfm.geographicFocus);
    expect(container.textContent).toContain(dfm.zakatStatus);
    expect(container.textContent).toContain('Asnaf served');
  });

  it('omits the asnaf-served fact when the export list is empty (non-applicability, not a gap)', () => {
    const c = noAsnafNotZakat();
    expect(c.donorFitMatrix.zakatAsnafServed).toEqual([]);
    const { queryByText } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Asnaf served')).toBeNull();
  });

  it('renders bestForSummary, idealFor, and considerations', () => {
    const c = richZakat();
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(c.bestForSummary);
    for (const t of c.idealFor) expect(container.textContent).toContain(t);
    for (const t of c.considerations) expect(container.textContent).toContain(t);
  });

  it('renders notIdealFor when non-empty, and nothing when empty', () => {
    const rich = richZakat();
    expect(rich.notIdealFor.length).toBeGreaterThan(0);
    const { container } = render(<RightForYou c={rich} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Not ideal for');
    expect(container.textContent).toContain(rich.notIdealFor[0]);

    const plain = noAsnafNotZakat();
    expect(plain.notIdealFor).toHaveLength(0);
    const { queryByText } = render(<RightForYou c={plain} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Not ideal for')).toBeNull();
  });

  it('renders the case-against summary publicly with inline citations and a source list', () => {
    const c = citedCaseAgainst();
    expect(c.cited.caseAgainstSummary.length).toBeGreaterThan(0);
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('The case against');
    expect(container.textContent).toContain('Sources');
    expect(container.querySelector('sup')).not.toBeNull();
  });

  it('gates caseAgainstFactors and caseAgainstMitigation behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = richZakat();
    expect(c.caseAgainstFactors.length).toBeGreaterThan(0);
    expect(c.caseAgainstMitigation).toBeTruthy();
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    // Signed out: the gated risk-factor prose must not leak.
    for (const f of c.caseAgainstFactors) {
      expect(container.textContent).not.toContain(f);
    }
    expect(container.textContent).not.toContain(c.caseAgainstMitigation);
    expect(container.textContent).toContain("Sign in to see this — it's free.");
  });

  it('shows caseAgainstFactors and caseAgainstMitigation to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = richZakat();
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    for (const f of c.caseAgainstFactors) {
      expect(container.textContent).toContain(f);
    }
    expect(container.textContent).toContain(c.caseAgainstMitigation);
  });

  it('renders zakat-anchored concerns', () => {
    mockMember.mockReturnValue(false);
    const c = withZakatConcern();
    expect(c.concerns.byAnchor.zakat.length).toBeGreaterThan(0);
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    for (const concern of c.concerns.byAnchor.zakat) {
      expect(container.textContent).toContain(concern.headline);
    }
  });

  it('lays out the donor-fit facts as a single column on mobile and a multi-column grid on desktop', () => {
    const c = richZakat();
    const { container: mobile } = render(<RightForYou c={c} p={p} isMobile={true} padX={16} />);
    expect(mobile.innerHTML).toContain('grid-template-columns: 1fr;');
    expect(mobile.innerHTML).not.toContain('repeat(auto-fit');

    const { container: desktop } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(desktop.innerHTML).toContain('repeat(auto-fit');
  });

  it('always mounts the section wrapper even for a minimal charity', () => {
    const minimal = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    const { container } = render(<RightForYou c={minimal} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('[data-section="right-for-you"]')).not.toBeNull();
  });

  it('renders every real charity in the corpus without throwing, in both layouts', () => {
    mockMember.mockReturnValue(false);
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let rendered = 0;
    for (const f of files) {
      const c = load(f);
      const { unmount } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
      unmount();
      const { unmount: unmountMobile } = render(<RightForYou c={c} p={p} isMobile={true} padX={16} />);
      unmountMobile();
      rendered += 1;
    }
    expect(rendered).toBe(files.length);
  });
});

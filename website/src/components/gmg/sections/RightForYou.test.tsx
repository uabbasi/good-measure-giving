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

/**
 * Pick a charity out of the real corpus by the shape the test needs, instead
 * of pinning an EIN annotated with the shape it had when the test was written.
 * Regeneration moves a charity out of that shape and the test then fails on
 * its own precondition without testing anything.
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

// Nothing in notIdealFor: the block must not render at all.
const emptyNotIdealFor = () =>
  pick('listing nothing under "not ideal for"', (c) => c.notIdealFor.length === 0);

// claimsZakat, asnaf category present, meaningful zakatAsnafServed (fuqara +
// masakin + ...), notIdealFor present, caseAgainstFactors + mitigation
// present, idealFor/considerations/bestForSummary present.
const richZakat = () => load('charity-04-3810161.json');
// case_against.summary carries a <cite> marker in this fixture (charity-04-3810161's
// does not) — used only for the citation-rendering assertion.
const citedCaseAgainst = () =>
  pick(
    'making a cited case against itself',
    (c) => c.cited.caseAgainstSummary.some((s) => s.kind === 'cited'),
  );
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

  it('gates the donor-fit matrix, including asnaf served, behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = richZakat();
    const dfm = c.donorFitMatrix;
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(dfm.causeArea);
    expect(container.textContent).not.toContain(dfm.givingStyle);
    expect(container.textContent).not.toContain(dfm.evidenceRigor);
    expect(container.textContent).not.toContain('Asnaf served');
    expect(container.textContent).toContain("Sign in to see this — it's free.");
  });

  it('shows the donor-fit matrix including asnaf served to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
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
    mockMember.mockReturnValue(true);
    const c = noAsnafNotZakat();
    expect(c.donorFitMatrix.zakatAsnafServed).toEqual([]);
    const { queryByText } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Asnaf served')).toBeNull();
  });

  it('gates bestForSummary, idealFor, and considerations behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = richZakat();
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(c.bestForSummary);
    for (const t of c.idealFor) expect(container.textContent).not.toContain(t);
    for (const t of c.considerations) expect(container.textContent).not.toContain(t);
  });

  it('shows bestForSummary, idealFor, and considerations to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = richZakat();
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(c.bestForSummary);
    for (const t of c.idealFor) expect(container.textContent).toContain(t);
    for (const t of c.considerations) expect(container.textContent).toContain(t);
  });

  it('gates notIdealFor when non-empty, and renders nothing when empty', () => {
    mockMember.mockReturnValue(false);
    const rich = richZakat();
    expect(rich.notIdealFor.length).toBeGreaterThan(0);
    const { container } = render(<RightForYou c={rich} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(rich.notIdealFor[0]);

    const plain = emptyNotIdealFor();
    expect(plain.notIdealFor).toHaveLength(0);
    const { queryByText } = render(<RightForYou c={plain} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Not ideal for')).toBeNull();
  });

  it('shows notIdealFor to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const rich = richZakat();
    const { container } = render(<RightForYou c={rich} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Not ideal for');
    expect(container.textContent).toContain(rich.notIdealFor[0]);
  });

  it('gates the case-against summary, including its inline citations, behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = citedCaseAgainst();
    expect(c.cited.caseAgainstSummary.length).toBeGreaterThan(0);
    const { container } = render(<RightForYou c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain('Sources');
    expect(container.querySelector('sup')).toBeNull();
    expect(container.textContent).toContain("Sign in to see this — it's free.");
  });

  it('shows the case-against summary with inline citations and a source list to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = citedCaseAgainst();
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
    mockMember.mockReturnValue(true);
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
  }, 30000); // renders 166 charities x 2 layouts; generous margin under worker contention
});

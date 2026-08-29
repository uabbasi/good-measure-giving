import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { RunWell } from './RunWell';
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
 * These fixtures were pinned EINs annotated with the shape they had when the
 * test was written ("boardSize 0", "ceoCompensation null"). Regeneration moves
 * a charity out of that shape and the test then fails on its own precondition
 * without having tested anything. Searching for the shape keeps the case real;
 * throwing when it has vanished says so rather than passing vacuously.
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

// ceoCompensation present ($539,137), boardSize null, 2 risks (both medium),
// a governance-anchored concern.
const withGovernanceConcern = () => load('charity-13-1837442.json');
// Full capacity data incl. non-zero boardSize/independentBoardPct/employees,
// but zero risks.
const fullCapacityNoRisks = () => load('charity-04-2535767.json');
// hasConflictPolicy/hasFinancialAudit both FALSE, boardSize/independentBoardPct
// /employeesCount/volunteersCount all 0 — every one of these is a legitimate,
// meaningful value that must still render (not be treated as absent). Also
// has risks of every severity and a risks-anchored concern.
const allZerosAndFalse = () =>
  pick(
    'reporting false conflict/audit policies and a zero board, staff and volunteer count',
    (c) =>
      c.capacity.hasConflictPolicy === false &&
      c.capacity.hasFinancialAudit === false &&
      c.capacity.boardSize === 0 &&
      c.capacity.independentBoardPct === 0 &&
      c.capacity.employeesCount === 0 &&
      c.capacity.volunteersCount === 0 &&
      // The concerns test below shares this fixture and needs something to
      // render, so require it here rather than let that test go vacuous.
      c.concerns.byAnchor.governance.length + c.concerns.byAnchor.risks.length > 0,
  );
// ceoCompensation AND ceoCompensationPctRevenue both null, but boardSize,
// ceoName, and geographicReach are present — the capacity gate must still
// appear for those, just without any compensation figures inside it.
const noCeoComp = () =>
  pick(
    'missing both CEO compensation figures while still reporting a board size',
    (c) =>
      c.capacity.ceoCompensation == null &&
      c.capacity.ceoCompensationPctRevenue == null &&
      c.capacity.boardSize != null,
  );

describe('RunWell', () => {
  it('gates the entire organizational-capacity block, including CEO name, board, and governance facts', () => {
    mockMember.mockReturnValue(false);
    const c = fullCapacityNoRisks();
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(String(c.capacity.boardSize));
    expect(container.textContent).not.toContain(String(c.capacity.employeesCount));
    if (c.capacity.geographicReach) expect(container.textContent).not.toContain(c.capacity.geographicReach);
    expect(container.textContent).toContain("Sign in to see this — it's free.");
  });

  it('shows capacity facts to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = fullCapacityNoRisks();
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(String(c.capacity.boardSize));
    expect(container.textContent).toContain(`${Math.round((c.capacity.independentBoardPct as number) * 100)}%`);
    expect(container.textContent).toContain(String(c.capacity.employeesCount));
    expect(container.textContent).toContain(c.capacity.geographicReach);
  });

  it('renders false/zero governance facts explicitly instead of treating them as absent, once signed in', () => {
    mockMember.mockReturnValue(true);
    const c = allZerosAndFalse();
    expect(c.capacity.hasConflictPolicy).toBe(false);
    expect(c.capacity.hasFinancialAudit).toBe(false);
    expect(c.capacity.boardSize).toBe(0);
    expect(c.capacity.independentBoardPct).toBe(0);
    expect(c.capacity.employeesCount).toBe(0);
    expect(c.capacity.volunteersCount).toBe(0);

    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    const factValue = (label: string): string | null | undefined =>
      Array.from(container.querySelectorAll('span')).find((el) => el.textContent === label)?.nextElementSibling
        ?.textContent;
    // Both booleans render an explicit "No" value next to their label, not a
    // gap in the layout where a truthy-only guard would have skipped them.
    expect(factValue('Conflict-of-interest policy')).toBe('No');
    expect(factValue('Independent financial audit')).toBe('No');
    expect(factValue('Independent board')).toBe('0%');
  });

  it('gates CEO compensation together with the rest of organizational capacity, behind one gate', () => {
    mockMember.mockReturnValue(false);
    const c = withGovernanceConcern();
    expect(c.capacity.ceoCompensation).not.toBeNull();
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    // Signed out: the gated *figures* must not leak. (A risk-narrative
    // sentence elsewhere on this charity's page separately mentions the same
    // dollar amount in prose — that's pre-existing narrative content, not
    // this section's gated data, so it's excluded by scoping to <strong>,
    // the tag this section uses to render the actual gated values.)
    const strongValues = Array.from(container.querySelectorAll('strong')).map((el) => el.textContent);
    expect(strongValues).not.toContain('$539,137');
    expect(strongValues).not.toContain('2.25%');
    expect(container.textContent).toContain("Sign in to see this — it's free.");
    // The CEO's name is part of the same gated capacity block — must not leak either.
    expect(container.textContent).not.toContain(c.capacity.ceoName as string);
  });

  it('shows the CEO compensation figures and CEO name to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = withGovernanceConcern();
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('$539,137');
    expect(container.textContent).toContain('2.25%');
    expect(container.textContent).toContain(c.capacity.ceoName as string);
  });

  it('renders no gate at all when a charity has no organizational-capacity data whatsoever', () => {
    mockMember.mockReturnValue(false);
    const bare = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    expect(bare.capacity.ceoCompensation).toBeNull();
    expect(bare.capacity.boardSize).toBeNull();
    const { queryByText } = render(<RunWell c={bare} p={p} isMobile={false} padX={16} />);
    // No teaser implying hidden capacity data that doesn't exist.
    expect(queryByText('Sign in')).toBeNull();
  });

  it('still gates the capacity block when CEO compensation is absent but other capacity facts exist', () => {
    mockMember.mockReturnValue(false);
    const c = noCeoComp();
    expect(c.capacity.ceoCompensation).toBeNull();
    expect(c.capacity.ceoCompensationPctRevenue).toBeNull();
    expect(c.capacity.boardSize).not.toBeNull();
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain("Sign in to see this — it's free.");
    expect(container.textContent).not.toContain(String(c.capacity.boardSize));

    mockMember.mockReturnValue(true);
    const { container: signedIn } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    expect(signedIn.textContent).toContain(String(c.capacity.boardSize));
    expect(signedIn.textContent).not.toContain('Compensation');
  });

  it('renders risks with category, description, and severity, and never a mitigation field', () => {
    mockMember.mockReturnValue(false);
    const c = withGovernanceConcern();
    expect(c.risks.length).toBeGreaterThan(0);
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    for (const risk of c.risks) {
      expect(container.textContent).toContain(risk.category);
      expect(container.textContent).toContain(risk.description);
    }
    expect(container.textContent).not.toContain('mitigation');
    expect(container.textContent).not.toContain('Mitigation');
  });

  it('renders no risks block for a charity with zero risks', () => {
    const c = fullCapacityNoRisks();
    expect(c.risks).toHaveLength(0);
    const { queryByText } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Risks on file')).toBeNull();
  });

  it('renders governance and risks concerns', () => {
    const c = allZerosAndFalse();
    const expected = [...c.concerns.byAnchor.governance, ...c.concerns.byAnchor.risks];
    expect(expected.length).toBeGreaterThan(0);
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    for (const concern of expected) {
      expect(container.textContent).toContain(concern.headline);
    }
  });

  // allZerosAndFalse (above) has no governance-anchored concern at all — its
  // "governance and risks" coverage was accidentally exercising byAnchor.risks
  // only, so removing the byAnchor.governance spread from the ConcernList call
  // left all 11 prior tests in this file green. withGovernanceConcern is the
  // one fixture with a real governance concern (ceo_comp_excessive); this
  // pins it directly.
  //
  // Asserting on `concern.headline` would ALSO stay green with the spread
  // removed: fleet-wide, every ceo_comp_excessive concern's headline is a
  // verbatim duplicate of a `risks[].description` string, which "Risks on
  // file" above renders unconditionally regardless of ConcernList. `detail`
  // ("For orgs with revenue $5-50M...") is unique to the ConcernList
  // rendering, so it's the one load-bearing thing to check here.
  it('renders a governance-anchored concern for a charity that actually has one', () => {
    mockMember.mockReturnValue(false);
    const c = withGovernanceConcern();
    const governanceConcerns = c.concerns.byAnchor.governance;
    expect(governanceConcerns.length).toBeGreaterThan(0);
    const { container } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    for (const concern of governanceConcerns) {
      expect(concern.detail).toBeTruthy();
      expect(container.textContent).toContain(concern.detail);
    }
  });

  it('lays out capacity facts as a single column on mobile and a multi-column grid on desktop', () => {
    mockMember.mockReturnValue(true);
    const c = fullCapacityNoRisks();
    const { container: mobile } = render(<RunWell c={c} p={p} isMobile={true} padX={16} />);
    expect(mobile.innerHTML).toContain('grid-template-columns: 1fr;');
    expect(mobile.innerHTML).not.toContain('repeat(auto-fit');

    const { container: desktop } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
    expect(desktop.innerHTML).toContain('repeat(auto-fit');
    expect(desktop.innerHTML).not.toContain('grid-template-columns: 1fr;');
  });

  it('always mounts the section wrapper even for a minimal charity', () => {
    const minimal = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    const { container } = render(<RunWell c={minimal} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('[data-section="run-well"]')).not.toBeNull();
  });

  it('renders every real charity in the corpus without throwing, in both layouts', () => {
    mockMember.mockReturnValue(false);
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let rendered = 0;
    for (const f of files) {
      const c = load(f);
      const { unmount } = render(<RunWell c={c} p={p} isMobile={false} padX={16} />);
      unmount();
      const { unmount: unmountMobile } = render(<RunWell c={c} p={p} isMobile={true} padX={16} />);
      unmountMobile();
      rendered += 1;
    }
    expect(rendered).toBe(files.length);
  }, 30000); // renders 166 charities x 2 layouts; generous margin under worker contention
});

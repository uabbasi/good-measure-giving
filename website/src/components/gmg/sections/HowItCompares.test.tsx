import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { HowItCompares } from './HowItCompares';
import { gmgPalette } from '../tokens';
import { adaptCharity } from '../charityAdapter';

const mockMember = vi.fn(() => false);
vi.mock('../../../auth/useAuth', () => ({ useCommunityMember: () => mockMember() }));
vi.mock('../../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const p = gmgPalette(false);
const dir = path.resolve(__dirname, '../../../../data/charities');
const load = (file: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')));

// peers.programRatioMedian present (0.892 -> 89%), industryProgramRatio 0.75
// -> 75%, programRatioPct 94% — a clean three-bar comparison. Also has
// peerCount, cnOverallScore, transparencyScore, revenueGrowth3yr, non-empty
// similarOrganizations, and a populated strengthsDeepDive.
const withMedian = () => load('charity-04-3810161.json');
/**
 * Pick a charity out of the real corpus by the shape the test needs.
 *
 * These fixtures used to be pinned EINs annotated with the shape they had at
 * the time ("peerCount is 0", "programRatioMedian is null"). Regeneration moves
 * a charity out of that shape and the test then fails on its own precondition,
 * having tested nothing. Searching for the shape keeps the case real, and
 * throwing when it has vanished says so plainly instead of passing vacuously.
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

// A two-bar comparison: no peer median to draw, but an industry ratio to
// compare against.
const noMedian = () =>
  pick(
    'missing a peer median while having an industry ratio',
    (c) => c.peers.programRatioMedian == null && c.peers.industryProgramRatio != null,
  );

// A legitimate zero, which must render rather than be treated as absent.
const zeroPeerCount = () =>
  pick(
    'reporting a peer count of exactly 0 alongside a CN score',
    (c) => c.peers.peerCount === 0 && c.peers.cnOverallScore != null,
  );

/**
 * A distinctive multi-word run from a cited block's own prose.
 *
 * 'fundraising costs capped' was pinned here as a phrase that appeared in the
 * deep-dive at the time. It is LLM-written and every regeneration rewrites it,
 * so the literal broke while proving nothing about gating. A run taken from
 * the middle of the actual text is just as distinctive -- long enough not to
 * collide with the page's public copy -- and always current.
 */
const distinctivePhrase = (segments: { text: string }[]): string => {
  // Sampled from within ONE segment. CitedText renders each citation as a
  // superscript mid-sentence, so a run spanning a citation boundary is never
  // contiguous in the DOM and could never be found by toContain.
  const longest = segments
    .map((s) => s.text.replace(/\s+/g, ' ').trim())
    .sort((a, b) => b.length - a.length)[0];
  const words = (longest ?? '').split(' ').filter(Boolean);
  if (words.length < 6) throw new Error('deep-dive prose too short to sample a phrase from');
  const mid = Math.floor(words.length / 2);
  return words.slice(mid - 3, mid + 3).join(' ');
};

describe('HowItCompares', () => {
  it('gates the entire peer-comparison block, including the peer group and cited differentiator', () => {
    mockMember.mockReturnValue(false);
    const c = withMedian();
    expect(c.peers.peerGroup).toBeTruthy();
    expect(c.cited.peerDifferentiator.length).toBeGreaterThan(0);
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(c.peers.peerGroup);
    expect(container.textContent).not.toContain('Sources');
    expect(container.querySelector('sup')).toBeNull();
    expect(container.textContent).toContain("Sign in to see this — it's free.");
  });

  it('shows the peer group and the cited differentiator with its source list to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = withMedian();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(c.peers.peerGroup);
    expect(container.textContent).toContain('Sources');
    expect(container.querySelector('sup')).not.toBeNull();
  });

  it('gates the three-bar program-ratio comparison behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = withMedian();
    expect(c.programRatioPct).toBe(94);
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain('Peer median');
    expect(container.textContent).not.toContain('Program ratio vs. peers');
  });

  it('shows a three-bar program-ratio comparison when a peer median exists, to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = withMedian();
    expect(c.programRatioPct).toBe(94);
    expect(c.peers.programRatioMedian).toBeCloseTo(0.892);
    expect(c.peers.industryProgramRatio).toBe(0.75);
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('94%');
    expect(container.textContent).toContain('89%');
    expect(container.textContent).toContain('75%');
    expect(container.textContent).toContain('Peer median');
    expect(container.textContent).toContain('Industry');
  });

  it('shows a two-bar comparison (no peer median) without a Peer median row, to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = noMedian();
    expect(c.peers.programRatioMedian).toBeNull();
    expect(c.peers.industryProgramRatio).not.toBeNull();
    const { container, queryByText } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(queryByText('Peer median')).toBeNull();
    expect(container.textContent).toContain('This charity');
    expect(container.textContent).toContain('Industry');
  });

  it('gates cnOverallScore, transparencyScore, peerCount (including a legitimate 0), and revenueGrowth3yr', () => {
    mockMember.mockReturnValue(false);
    const c = zeroPeerCount();
    expect(c.peers.peerCount).toBe(0);
    expect(c.peers.cnOverallScore).not.toBeNull();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    // Signed out: none of the gated benchmark figures may leak.
    const strongValues = Array.from(container.querySelectorAll('strong')).map((el) => el.textContent);
    expect(strongValues).not.toContain(String(c.peers.cnOverallScore));
    expect(strongValues).not.toContain(String(c.peers.transparencyScore));
    expect(strongValues).not.toContain('0');
    expect(container.textContent).toContain("Sign in to see this — it's free.");
  });

  it('shows the gated benchmark figures to a signed-in community member, including a legitimate zero', () => {
    mockMember.mockReturnValue(true);
    const c = zeroPeerCount();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(String(c.peers.cnOverallScore));
    expect(container.textContent).toContain(String(c.peers.transparencyScore));
    expect(container.textContent).toContain('Peers compared');
    // peerCount === 0 must render as an explicit "0", not be treated as absent.
    const strongValues = Array.from(container.querySelectorAll('strong')).map((el) => el.textContent);
    expect(strongValues).toContain('0');
    expect(container.textContent).toContain(`${c.outlook.revenueGrowth3yr}%`);
  });

  it('gates similarOrganizations behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = withMedian();
    expect(c.peers.similarOrganizations.length).toBeGreaterThan(0);
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    for (const org of c.peers.similarOrganizations) {
      expect(container.textContent).not.toContain(org.name);
    }
  });

  it('shows similarOrganizations as unlinked context to a signed-in community member, not as anchors', () => {
    mockMember.mockReturnValue(true);
    const c = withMedian();
    expect(c.peers.similarOrganizations.length).toBeGreaterThan(0);
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Also worth knowing about');
    expect(container.textContent).toContain('not linked');
    for (const org of c.peers.similarOrganizations) {
      expect(container.textContent).toContain(org.name);
      const link = Array.from(container.querySelectorAll('a')).find((a) => a.textContent?.includes(org.name));
      expect(link).toBeUndefined();
    }
  });

  it('gates long-term outlook facts and strategic priorities behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = withMedian();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(c.outlook.roomForFundingExplanation);
    for (const sp of c.outlook.strategicPriorities) {
      expect(container.textContent).not.toContain(sp);
    }
  });

  it('shows long-term outlook facts and strategic priorities to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = withMedian();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(c.outlook.maturityStage);
    expect(container.textContent).toContain(c.outlook.roomForFunding);
    expect(container.textContent).toContain(c.outlook.roomForFundingExplanation);
    for (const sp of c.outlook.strategicPriorities) {
      expect(container.textContent).toContain(sp);
    }
  });

  it('gates strengthsDeepDive behind the community gate', () => {
    mockMember.mockReturnValue(false);
    const c = withMedian();
    expect(c.cited.strengthsDeepDive.length).toBeGreaterThan(0);
    // A distinctive multi-word phrase from the deep-dive prose, not a lone
    // connector word — those coincidentally appear in unrelated public copy
    // elsewhere on the page and would make this assertion pass vacuously.
    const phrase = distinctivePhrase(c.cited.strengthsDeepDive[0]);
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(phrase);
    expect(container.textContent).toContain('Strengths in depth');
  });

  it('shows strengthsDeepDive to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = withMedian();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    // Every deep-dive block must render, not just the first — the second
    // assertion here used to be the literal '1.1 million individuals', which
    // was simply a phrase that happened to be in the prose at the time.
    for (const block of c.cited.strengthsDeepDive) {
      expect(container.textContent).toContain(distinctivePhrase(block));
    }
  });

  it('lays out the outlook facts as a single column on mobile and a multi-column grid on desktop', () => {
    mockMember.mockReturnValue(true);
    const c = withMedian();
    const { container: mobile } = render(<HowItCompares c={c} p={p} isMobile={true} padX={16} />);
    expect(mobile.innerHTML).toContain('grid-template-columns: 1fr;');

    const { container: desktop } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(desktop.innerHTML).toContain('repeat(auto-fit');
    expect(desktop.innerHTML).not.toContain('grid-template-columns: 1fr;');
  });

  it('always mounts the section wrapper even for a minimal charity', () => {
    const minimal = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    const { container } = render(<HowItCompares c={minimal} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('[data-section="compares"]')).not.toBeNull();
  });

  it('renders every real charity in the corpus without throwing, in both layouts', () => {
    mockMember.mockReturnValue(false);
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let rendered = 0;
    for (const f of files) {
      const c = load(f);
      const { unmount } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
      unmount();
      const { unmount: unmountMobile } = render(<HowItCompares c={c} p={p} isMobile={true} padX={16} />);
      unmountMobile();
      rendered += 1;
    }
    expect(rendered).toBe(files.length);
  }, 30000); // renders 166 charities x 2 layouts; generous margin under worker contention
});

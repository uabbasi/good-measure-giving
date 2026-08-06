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
// peers.programRatioMedian is null (30/166 fleet-wide) but industryProgramRatio
// is present — a two-bar comparison. peerCount is 0 (a legitimate value, not
// absence). Reused from RunWell's governance fixture.
const noMedian = () => load('charity-13-1837442.json');

describe('HowItCompares', () => {
  it('renders the peer group and the cited differentiator with its source list', () => {
    const c = withMedian();
    expect(c.peers.peerGroup).toBeTruthy();
    expect(c.cited.peerDifferentiator.length).toBeGreaterThan(0);
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(c.peers.peerGroup);
    expect(container.textContent).toContain('Sources');
    expect(container.querySelector('sup')).not.toBeNull();
  });

  it('renders a three-bar program-ratio comparison when a peer median exists', () => {
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

  it('renders a two-bar comparison (no peer median) without a Peer median row', () => {
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
    const c = noMedian();
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
    const c = noMedian();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(String(c.peers.cnOverallScore));
    expect(container.textContent).toContain(String(c.peers.transparencyScore));
    expect(container.textContent).toContain('Peers compared');
    // peerCount === 0 must render as an explicit "0", not be treated as absent.
    const strongValues = Array.from(container.querySelectorAll('strong')).map((el) => el.textContent);
    expect(strongValues).toContain('0');
    expect(container.textContent).toContain(`${c.outlook.revenueGrowth3yr}%`);
  });

  it('renders similarOrganizations as unlinked context, not as anchors', () => {
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

  it('renders long-term outlook facts and strategic priorities publicly', () => {
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
    expect(c.cited.strengthsDeepDive[0].map((s) => s.text).join('')).toContain('fundraising costs capped');
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain('fundraising costs capped');
    expect(container.textContent).not.toContain('1.1 million individuals');
    expect(container.textContent).toContain('Strengths in depth');
  });

  it('shows strengthsDeepDive to a signed-in community member', () => {
    mockMember.mockReturnValue(true);
    const c = withMedian();
    const { container } = render(<HowItCompares c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('fundraising costs capped');
    expect(container.textContent).toContain('1.1 million individuals');
  });

  it('lays out the outlook facts as a single column on mobile and a multi-column grid on desktop', () => {
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

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { WhatTheyDo } from './WhatTheyDo';
import { gmgPalette } from '../tokens';
import { adaptCharity } from '../charityAdapter';

const mockMember = vi.fn(() => false);
vi.mock('../../../auth/useAuth', () => ({ useCommunityMember: () => mockMember() }));
vi.mock('../../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));
vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

// jsdom doesn't implement matchMedia. WhatTheyDo now calls the real
// useIsMobile() internally (for the intermediate About/Quick-facts
// breakpoint) rather than only receiving it as a prop, so it needs a stub —
// same convention as the hooks tests that stub LandingThemeProvider's
// matchMedia call.
window.matchMedia = ((query: string) => ({
  matches: false,
  media: query,
  addEventListener: () => {},
  removeEventListener: () => {},
})) as unknown as typeof window.matchMedia;

const p = gmgPalette(false);
const dir = path.resolve(__dirname, '../../../../data/charities');
const load = (file: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')));

// charity-01-0548371.json: no grants, but has an evidence grade, root-level
// theoryOfChange, externalEvaluations, and both whatTheyDo concerns — a rich
// fixture for this section specifically.
const richNoGrants = () => load('charity-01-0548371.json');

describe('WhatTheyDo Quick facts on a phone', () => {
  // Label left / value right is fine while the value fits its line. Programs
  // and Populations are comma-joined lists that run three or four lines at
  // 393px, and right-aligned wrapped text goes ragged down its left edge —
  // the side you read from. Long values drop under their label instead.
  const factRow = (container: HTMLElement, label: string): HTMLElement => {
    const cell = Array.from(container.querySelectorAll('span')).find(
      (s) => s.textContent === label,
    );
    if (!cell) throw new Error(`no Quick facts row labelled "${label}"`);
    return cell.parentElement as HTMLElement;
  };

  // The IRC has a programs list well past one line, and a two-word wallet.
  const longAndShort = () => load('charity-13-5660870.json');

  it('stacks a value too long for its line', () => {
    const { container } = render(<WhatTheyDo c={longAndShort()} p={p} isMobile padX={16} />);
    const row = factRow(container, 'Programs');

    expect(row.style.flexDirection).toBe('column');
    expect((row.lastElementChild as HTMLElement).style.textAlign).toBe('left');
  });

  it('leaves a short value in the compact two-column row', () => {
    const { container } = render(<WhatTheyDo c={longAndShort()} p={p} isMobile padX={16} />);
    const row = factRow(container, 'Wallet');

    expect(row.style.flexDirection).toBe('row');
    expect((row.lastElementChild as HTMLElement).style.textAlign).toBe('right');
  });

  it('leaves desktop alone — the card is wide enough there', () => {
    const { container } = render(<WhatTheyDo c={longAndShort()} p={p} isMobile={false} padX={24} />);
    const row = factRow(container, 'Programs');

    expect(row.style.flexDirection).toBe('row');
    expect((row.lastElementChild as HTMLElement).style.textAlign).toBe('right');
  });
});

describe('WhatTheyDo', () => {
  it('renders the About lede and Quick facts card ahead of the cited summary', () => {
    const c = richNoGrants();
    const { container, getByText } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);

    expect(getByText('About')).toBeInTheDocument();
    expect(getByText(c.headline)).toBeInTheDocument();
    expect(getByText('Quick facts')).toBeInTheDocument();
    // A representative sample of quick-facts rows this fixture has values for.
    expect(getByText(c.category)).toBeInTheDocument();
    expect(getByText(c.riskLevel)).toBeInTheDocument();

    // Composition, not just presence: the headline must appear before the
    // cited summary text in document order — a regression that keeps both
    // fields but drops the About block (e.g. moves the headline back into
    // page header meta only) would still pass a bare "is present" check.
    const html = container.innerHTML;
    const headlineIdx = html.indexOf(c.headline);
    const summaryIdx = html.indexOf('Sources');
    expect(headlineIdx).toBeGreaterThan(-1);
    expect(headlineIdx).toBeLessThan(summaryIdx);
  });

  it('renders the narrative summary exactly once, not once plain and once cited', () => {
    // c.summary and c.cited.summary are parsed from the SAME source field
    // (narrative.summary) — rendering both is the same paragraph twice. The
    // plain, uncited version's fingerprint is a <p> whose entire text is
    // the raw summary string; the cited version breaks that string up with
    // inline citation markers, so it never produces this exact match.
    const c = richNoGrants();
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    const plainDuplicates = Array.from(container.querySelectorAll('p')).filter(
      (el) => el.textContent === c.summary,
    );
    expect(plainDuplicates).toHaveLength(0);
    // The cited version must still be the one thing that renders it.
    expect(container.textContent).toContain('Sources');
  });

  it('collapses the About/Quick-facts grid to one column before the 768px mobile breakpoint', () => {
    // useIsMobile is a single binary breakpoint at 768px, so the 1.6fr/1fr
    // split otherwise stayed two columns at any width above that — cramped
    // well before actual mobile. Simulate a mid-size viewport (matches the
    // intermediate 1100px query but not an actual mobile one) and confirm
    // the grid has already collapsed.
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query === '(max-width: 1100px)',
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;

    const c = richNoGrants();
    const { getByText } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    let grid: HTMLElement | null = getByText('Quick facts');
    while (grid && grid.style.display !== 'grid') grid = grid.parentElement;
    expect(grid?.style.gridTemplateColumns).toBe('1fr');

    window.matchMedia = original;
  });

  it('keeps the About/Quick-facts grid at two columns above the intermediate breakpoint', () => {
    const c = richNoGrants();
    // Module-level stub (top of file) always reports matches: false.
    const { getByText } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    let grid: HTMLElement | null = getByText('Quick facts');
    while (grid && grid.style.display !== 'grid') grid = grid.parentElement;
    expect(grid?.style.gridTemplateColumns).toBe('minmax(0, 1.6fr) minmax(0, 1fr)');
  });

  it('caps the evidence prose cluster to a readable measure', () => {
    // The complaint was ~180 characters per line at 1440px — a container
    // running full width with no measure cap. Every block in this prose
    // cluster (cited summary, evidence grade, theory of change, external
    // evaluations) must sit inside a capped-width ancestor.
    mockMember.mockReturnValue(true);
    const c = richNoGrants();
    const { getByText } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    let capped: HTMLElement | null = getByText(c.evidence.gradeExplanation);
    while (capped && capped.style.maxWidth !== '75ch') capped = capped.parentElement;
    expect(capped).not.toBeNull();
  });

  it('renders the cited summary and its source list', () => {
    const c = richNoGrants();
    expect(c.cited.summary.length).toBeGreaterThan(0);
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain('Sources');
  });

  it('gates the whole impact-evidence block: grade, theory-of-change status/summary, external evaluations', () => {
    mockMember.mockReturnValue(false);
    const c = richNoGrants();
    expect(c.evidence.grade).toBeTruthy();
    expect(c.evidence.theoryOfChange).toBeTruthy();
    expect(c.evidence.theoryOfChangeSummary).toBeTruthy();
    expect(c.evidence.externalEvaluations.length).toBeGreaterThan(0);
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).not.toContain(`Evidence grade ${c.evidence.grade}`);
    expect(container.textContent).not.toContain(c.evidence.theoryOfChange);
    expect(container.textContent).not.toContain(c.evidence.theoryOfChangeSummary);
    for (const e of c.evidence.externalEvaluations) expect(container.textContent).not.toContain(e);
    expect(container.textContent).toContain("Sign in to see this — it's free.");
    // The root-level, non-narrative theoryOfChange stays public even though
    // the evaluator's own impact-evidence assessment above is gated.
    expect(container.textContent).toContain(c.theoryOfChange as string);
  });

  it('renders the evaluator theory of change and the charity-reported one as separate blocks, not merged, to a signed-in member', () => {
    mockMember.mockReturnValue(true);
    const c = richNoGrants();
    expect(c.evidence.theoryOfChange).toBeTruthy();
    expect(c.theoryOfChange).toBeTruthy();
    // Load-bearing: if the two were merged into one field, this would fail —
    // both distinct passages must appear in the rendered output.
    const { getByText } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    expect(getByText(c.evidence.theoryOfChange)).toBeInTheDocument();
    expect(getByText(c.theoryOfChange as string)).toBeInTheDocument();
    expect(c.evidence.theoryOfChange).not.toBe(c.theoryOfChange);
  });

  it('renders the evidence grade and its explanation to a signed-in member', () => {
    mockMember.mockReturnValue(true);
    const c = richNoGrants();
    expect(c.evidence.grade).toBeTruthy();
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    expect(container.textContent).toContain(`Evidence grade ${c.evidence.grade}`);
    if (c.evidence.gradeExplanation) expect(container.textContent).toContain(c.evidence.gradeExplanation);
  });

  it('renders the theory-of-change summary prose, not the bare status enum, as the explanation, to a signed-in member', () => {
    mockMember.mockReturnValue(true);
    const c = richNoGrants();
    expect(c.evidence.theoryOfChangeSummary).toBeTruthy();
    expect(c.evidence.theoryOfChangeSummary).not.toBe(c.evidence.theoryOfChange);
    const { getByText, container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);

    // The real prose renders as the explanation.
    expect(getByText(c.evidence.theoryOfChangeSummary)).toBeInTheDocument();

    // The status enum still renders (as a badge, a legitimate signal), but a
    // regression that renders it as a standalone paragraph — presenting
    // "DOCUMENTED" as if it were a sentence of narrative — must fail here.
    const paragraphs = Array.from(container.querySelectorAll('p'));
    expect(paragraphs.some((el) => el.textContent === c.evidence.theoryOfChange)).toBe(false);
  });

  it('renders external evaluations as a list to a signed-in member', () => {
    mockMember.mockReturnValue(true);
    const c = richNoGrants();
    expect(c.evidence.externalEvaluations.length).toBeGreaterThan(0);
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    for (const e of c.evidence.externalEvaluations) expect(container.textContent).toContain(e);
  });

  it('renders programs, populations, and geography as tag rows', () => {
    const c = richNoGrants();
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    for (const item of [...c.programs, ...c.populations, ...c.geography]) {
      expect(container.textContent).toContain(item);
    }
  });

  it('renders whatTheyDo concerns', () => {
    const c = richNoGrants();
    expect(c.concerns.byAnchor.whatTheyDo.length).toBeGreaterThan(0);
    const { container } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
    for (const concern of c.concerns.byAnchor.whatTheyDo) {
      expect(container.textContent).toContain(concern.headline);
    }
  });

  it('always mounts the section wrapper even when a charity has none of the optional content', () => {
    const bare = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    const { container } = render(<WhatTheyDo c={bare} p={p} isMobile={false} padX={16} />);
    expect(container.querySelector('[data-section="what-they-do"]')).not.toBeNull();
  });

  it('renders every real charity in the corpus without throwing', () => {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let rendered = 0;
    for (const f of files) {
      const c = load(f);
      const { unmount } = render(<WhatTheyDo c={c} p={p} isMobile={false} padX={16} />);
      rendered += 1;
      unmount();
    }
    expect(rendered).toBe(files.length);
  }, 30000); // renders 166 charities; generous margin under worker contention
});

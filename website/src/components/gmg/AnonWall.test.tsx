import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { AnonWall, computeAnalysisAreas, computeWallItems } from './AnonWall';
import { gmgPalette } from './tokens';
import { adaptCharity } from './charityAdapter';

vi.mock('../../auth/SignInButton', () => ({ SignInButton: () => <button>Sign in</button> }));

const p = gmgPalette(false);
const dir = path.resolve(__dirname, '../../../data/charities');
const load = (ein: string) => adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, `charity-${ein}.json`), 'utf8')));

// International Rescue Committee — 1 concern, 6 citations/6 sources, 703 grants.
const irc = () => load('13-5660870');
// Doctors Without Borders — 2 concerns, 5 citations/5 sources, 11 grants.
// Different counts on every line from IRC, on the same shared page shape,
// so a hardcoded copy of IRC's numbers can never pass both.
const dwb = () => load('13-3433452');
// MCC East Bay — zero concerns, but real citations and analysis areas, so
// the "no concerns" case isn't just a blank charity with nothing to show.
const zeroConcerns = () => load('20-8085421');

describe('computeWallItems — real counts, not hardcoded copy', () => {
  // Every count below was pinned as a literal ('1 identified concern',
  // '6 cited claims from 6 sources', '703 grants'). Regeneration moves all of
  // them, and a re-pinned literal only defers the same failure. Deriving the
  // expected line from the charity's own data is also the stronger proof:
  // hardcoded copy cannot match two different charities' arithmetic.
  const concernLine = (c: ReturnType<typeof irc>) =>
    `${c.concerns.all.length} identified ${c.concerns.all.length === 1 ? 'concern' : 'concerns'}`;

  const citationLine = (c: ReturnType<typeof irc>) => {
    const n = c.citations.ordered.length;
    const sources = new Set(c.citations.ordered.map((ci) => ci.sourceName).filter(Boolean)).size;
    return `${n} cited ${n === 1 ? 'claim' : 'claims'} from ${sources} ${sources === 1 ? 'source' : 'sources'}`;
  };

  it('reports concern and citation counts taken from each charity, not fixed copy', () => {
    const a = irc();
    const b = dwb();

    expect(computeWallItems(a)).toContain(concernLine(a));
    expect(computeWallItems(b)).toContain(concernLine(b));
    expect(computeWallItems(a)).toContain(citationLine(a));
    expect(computeWallItems(b)).toContain(citationLine(b));
  });

  it('produces different lines for two different charities', () => {
    // The mutation guard: a function returning fixed strings would give these
    // two identical output, whatever the fixtures say.
    expect(computeWallItems(irc())).not.toEqual(computeWallItems(dwb()));
  });

  it('never advertises concerns for a charity that has none', () => {
    const c = zeroConcerns();
    expect(c.concerns.all.length).toBe(0);
    const items = computeWallItems(c);
    expect(items.some((i) => /concern/i.test(i))).toBe(false);
    // The charity isn't otherwise empty — it still has real lines to show.
    expect(items.length).toBeGreaterThan(0);
    expect(items).toContain(citationLine(c));
  });

  it('omits the financial-history and grant lines for a charity with neither', () => {
    const c = zeroConcerns();
    expect(c.financialSeries.length).toBe(0);
    expect(c.grantFlows).toBeNull();
    const items = computeWallItems(c);
    expect(items.some((i) => /year.*financial history/i.test(i))).toBe(false);
    expect(items.some((i) => /grant/i.test(i))).toBe(false);
  });

  it('lists only analysis areas this charity actually has content for', () => {
    const bare = adaptCharity({ ein: '00-0000000', name: 'Bare Org' });
    expect(computeAnalysisAreas(bare)).toEqual([]);
    expect(computeWallItems(bare)).toEqual([]);
  });
});

describe('AnonWall', () => {
  it('renders the charity name, a call to action, and the sign-in control', () => {
    const c = irc();
    const { getByText, container } = render(<AnonWall c={c} p={p} padX={16} />);
    expect(container.textContent).toContain(c.name);
    expect(getByText(/is free/i)).toBeInTheDocument();
    expect(getByText('Sign in')).toBeInTheDocument();
  });

  it('renders each computed item as a list entry', () => {
    const c = irc();
    const { container } = render(<AnonWall c={c} p={p} padX={16} />);
    for (const item of computeWallItems(c)) {
      expect(container.textContent).toContain(item);
    }
  });
});

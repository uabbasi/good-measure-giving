// @vitest-environment node
//
// GmgBrowse SSR (Task 4). scripts/prerender.ts wraps each route in try/catch
// and silently degrades a throwing route to a meta-only shell — a crash here
// would blank /browse in production with a green build and passing CI (this
// project has shipped exactly that failure mode once already). Render
// through the same server path entry-server.tsx uses, seeded the way
// scripts/prerender.ts seeds /browse (the charities index only), and assert
// real content comes out the other end.
//
// useEffect does not run during renderToString, so the URL-sync and robots
// effects never fire here — but the useReducer initializer DOES run
// synchronously during render, and its `typeof window === 'undefined'`
// guard is what stops that from throwing. (Proven load-bearing manually
// during development: removing the guard turned the tests below red with
// `ReferenceError: window is not defined`; see task-4-report.md.)

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { render } from '../../../entry-server';
import { buildCharitiesIndex } from '../../hooks/useCharities';
import { adaptRow } from './charityAdapter';

const DATA_PATH = path.resolve(__dirname, '../../../data/charities.json');
const rawIndex = JSON.parse(fs.readFileSync(DATA_PATH, 'utf8'));
const charitiesIndexResult = buildCharitiesIndex(rawIndex);

// Mirrors scripts/prerender.ts's seedFor() for the '/' | '/browse' | '/changelog'
// routes: seed only the charities index (the "masthead" seed), exactly as
// production prerendering does — no charity-detail seed belongs here.
const renderBrowse = (): Promise<string> =>
  render('/browse', [{ queryKey: ['charities'], data: charitiesIndexResult }]);

describe('GmgBrowse SSR (entry-server, real charity data)', () => {
  it('renders an h1, the "Every charity" copy, and at least 100 charity names', async () => {
    const html = await renderBrowse();

    expect(html).toMatch(/<h1[ >]/);
    expect(html).toContain('Every charity');

    // Real content, not a meta-only shell: most of the corpus's names show up
    // as literal text in the rendered table.
    const names: string[] = rawIndex.charities.map((c: { name: string }) => c.name);
    const found = names.filter((name) => html.includes(name));
    expect(found.length).toBeGreaterThanOrEqual(100);
  }, 20000);

  // Two prior facts (applyFacets(allRows, INITIAL_FACET_STATE) returns the
  // full corpus,
  // and the sort switch is byte-identical to pre-Phase-3) don't prove the
  // wiring BETWEEN them survived Task 3's reducer swap. Read the markup the
  // component actually produced — row count and row order — rather than a
  // count computed alongside it.
  it('renders the default view as every indexed charity, sorted by overall GMG score descending', async () => {
    const html = await renderBrowse();

    // Each desktop row's name cell is the only <a href="/charity/<ein>/"> on
    // the page (no similar-charities block on /browse), so scanning the
    // rendered HTML in document order gives the actual on-page row sequence
    // — not a count or order computed separately from the markup.
    const rowEins = [...html.matchAll(/href="\/charity\/([\d-]+)\/"/g)].map((m) => m[1]);
    // Every charity in the index must reach the page; deriving the expected
    // count keeps this about the SSR wiring rather than the corpus size.
    expect(rowEins.length).toBe(rawIndex.charities.length);

    const nameByEin = new Map<string, string>(
      rawIndex.charities.map((c: { ein: string; name: string }) => [c.ein, c.name]),
    );

    // Derived from the corpus at test time (never hardcode a charity name):
    // the same allRows = charities.map(adaptRow) the component computes,
    // sorted by the same rule GmgBrowse's default 'overall'/'desc' sort uses
    // (amalScore descending, stable A–Z tiebreak) — without calling the
    // component's own sort function, so this still exercises the wiring.
    const expectedOrder = [...charitiesIndexResult.charities]
      .map(adaptRow)
      .filter((r) => r.ein)
      .sort((a, b) => {
        let v = b.amalScore - a.amalScore;
        if (v === 0) v = a.name.localeCompare(b.name);
        return v;
      });

    expect(nameByEin.get(rowEins[0])).toBe(expectedOrder[0].name);
    expect(nameByEin.get(rowEins[rowEins.length - 1])).toBe(expectedOrder[expectedOrder.length - 1].name);
  }, 20000);
});

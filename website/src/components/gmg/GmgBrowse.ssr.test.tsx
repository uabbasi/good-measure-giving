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
// guard is what stops that from throwing. The guard is proven load-bearing
// in the second test below.

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { render } from '../../../entry-server';
import { buildCharitiesIndex } from '../../hooks/useCharities';

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
});

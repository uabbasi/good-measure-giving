import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity } from './charityAdapter';

const dir = path.resolve(__dirname, '../../../data/charities');
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
const load = (f: string) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));

describe('adaptCharity.cited', () => {
  it('parses the summary into segments carrying real citations', () => {
    const withCites = files.map(load).find(
      (d) => typeof d?.amalEvaluation?.rich_narrative?.summary === 'string'
        && d.amalEvaluation.rich_narrative.summary.includes('<cite'),
    );
    expect(withCites).toBeDefined();
    const c = adaptCharity(withCites);
    expect(c.cited.summary.length).toBeGreaterThan(1);
    const citedSegs = c.cited.summary.filter((s) => s.kind === 'cited');
    expect(citedSegs.length).toBeGreaterThan(0);
    for (const seg of citedSegs) {
      if (seg.kind !== 'cited') continue;
      expect(seg.citation.n).toBeGreaterThan(0);
      expect(seg.citation.sourceName).not.toBe('');
    }
  });

  it('never leaks cite markup into any segment text', () => {
    for (const f of files) {
      const c = adaptCharity(load(f));
      const all = [
        ...c.cited.summary,
        ...c.cited.caseAgainstSummary,
        ...c.cited.peerDifferentiator,
        ...c.cited.dimensionExplanations.impact,
        ...c.cited.dimensionExplanations.alignment,
        ...c.cited.dimensionExplanations.credibility,
        ...c.cited.strengths.flatMap((s) => s.detail),
        ...c.cited.growthAreas.flatMap((g) => g.detail),
        ...c.cited.strengthsDeepDive.flat(),
      ];
      for (const seg of all) {
        expect(seg.text).not.toContain('<cite');
        expect(seg.text).not.toContain('</cite>');
        expect(seg.text).not.toMatch(/<[a-z][^>]*>/i);
      }
    }
  });

  it('keeps the plain-text fields plain, for meta tags and the compare page', () => {
    const c = adaptCharity(load(files[0]));
    expect(typeof c.summary).toBe('string');
    expect(c.summary).not.toContain('<cite');
  });

  it('renders segment text that reconstructs the plain summary', () => {
    // The cited segments and the stripped string must say the same thing —
    // otherwise the page shows different prose to different code paths.
    for (const f of files.slice(0, 40)) {
      const c = adaptCharity(load(f));
      if (c.cited.summary.length === 0) continue;
      const joined = c.cited.summary.map((s) => s.text).join('').replace(/\s+/g, ' ').trim();
      expect(joined).toBe(c.summary.replace(/\s+/g, ' ').trim());
    }
  });

  it('yields empty arrays rather than throwing when narrative is absent', () => {
    const c = adaptCharity({ ein: '00-0000000', name: 'Empty' });
    expect(c.cited.summary).toEqual([]);
    expect(c.cited.strengths).toEqual([]);
    expect(c.cited.growthAreas).toEqual([]);
    expect(c.cited.strengthsDeepDive).toEqual([]);
    expect(c.cited.dimensionExplanations.impact).toEqual([]);
  });

  it('keeps growthAreas label and cited detail paired, so they cannot drift', () => {
    // cited.growthAreas.point must be the same label plain growthAreas shows —
    // otherwise a consumer could reasonably assume the two arrays describe the
    // same items in the same order and be wrong.
    // An EMPTY cited list is allowed and means "no citations for these".
    // growthAreas falls back to the baseline narrative while cited.growthAreas
    // reads only the rich one, so a charity with baseline-only growth areas
    // (Muslim Association of Puget Sound today) legitimately has one and not
    // the other. Nothing can mis-pair in that case; the drift this guards
    // against is a NON-empty cited list disagreeing with the plain one.
    let paired = 0;
    for (const f of files) {
      const c = adaptCharity(load(f));
      if (c.cited.growthAreas.length === 0) continue;
      paired += 1;
      c.cited.growthAreas.forEach((g, i) => {
        expect(g.point).not.toBe('');
        expect(g.point).toBe(c.growthAreas[i]);
      });
    }
    // ...and the check must not pass by finding nothing to check.
    expect(paired).toBeGreaterThan(files.length / 2);
  });

  it('covers the corpus — most charities carry cited segments in the summary', () => {
    const withCited = files
      .map((f) => adaptCharity(load(f)))
      .filter((c) => c.cited.summary.some((s) => s.kind === 'cited'));
    expect(withCited.length).toBeGreaterThanOrEqual(150);
  });
});

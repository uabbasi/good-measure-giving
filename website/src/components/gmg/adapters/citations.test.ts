import { describe, it, expect } from 'vitest';
import { normalizeCitationId, buildCitationIndex, parseCitedText } from './citations';

const RAW = [
  { id: '[1]', claim: 'overall score of 97.0/100', quote: 'Overall Score 97',
    source_name: 'Charity Navigator - Ratings', source_type: 'rating',
    source_url: 'https://www.charitynavigator.org/ein/135660870', access_date: '2026-01-09', confidence: 0.95 },
  { id: '[2]', claim: 'revenue', quote: '', source_name: 'IRS Form 990',
    source_type: 'form990', source_url: 'https://projects.propublica.org/x', access_date: '2026-01-09', confidence: 0.9 },
];

describe('normalizeCitationId', () => {
  it('strips the brackets all_citations uses so bare inline ids match', () => {
    expect(normalizeCitationId('[1]')).toBe('1');
    expect(normalizeCitationId('1')).toBe('1');
    expect(normalizeCitationId(' [12] ')).toBe('12');
    expect(normalizeCitationId(null)).toBe('');
  });
});

describe('buildCitationIndex', () => {
  it('keys citations by normalized id and numbers them from 1', () => {
    const idx = buildCitationIndex(RAW);
    expect(idx.ordered).toHaveLength(2);
    expect(idx.ordered[0].n).toBe(1);
    expect(idx.ordered[0].sourceName).toBe('Charity Navigator - Ratings');
    expect(idx.byId.get('1')?.n).toBe(1);
    expect(idx.byId.get('2')?.sourceUrl).toBe('https://projects.propublica.org/x');
  });

  it('returns an empty index for missing or malformed input', () => {
    expect(buildCitationIndex(undefined).ordered).toEqual([]);
    expect(buildCitationIndex(null).ordered).toEqual([]);
    expect(buildCitationIndex('nope' as unknown).ordered).toEqual([]);
  });
});

describe('parseCitedText', () => {
  it('splits cited spans out of narrative prose', () => {
    const idx = buildCitationIndex(RAW);
    const segs = parseCitedText('Founded in <cite id="1">1933</cite>, the org grew.', idx);
    expect(segs).toEqual([
      { kind: 'text', text: 'Founded in ' },
      { kind: 'cited', text: '1933', citation: expect.objectContaining({ n: 1 }) },
      { kind: 'text', text: ', the org grew.' },
    ]);
  });

  it('degrades an unresolvable citation id to plain text rather than dropping the words', () => {
    const idx = buildCitationIndex(RAW);
    const segs = parseCitedText('Serves <cite id="99">many people</cite>.', idx);
    expect(segs).toEqual([
      { kind: 'text', text: 'Serves ' },
      { kind: 'text', text: 'many people' },
      { kind: 'text', text: '.' },
    ]);
  });

  it('strips non-citation markup and collapses whitespace', () => {
    const idx = buildCitationIndex(RAW);
    expect(parseCitedText('a <b>bold</b>   claim', idx)).toEqual([
      { kind: 'text', text: 'a bold claim' },
    ]);
  });

  it('returns nothing for empty input', () => {
    expect(parseCitedText('', buildCitationIndex(RAW))).toEqual([]);
    expect(parseCitedText(null, buildCitationIndex(RAW))).toEqual([]);
  });
});

import fs from 'node:fs';
import path from 'node:path';

describe('citations against the real export corpus', () => {
  const dir = path.resolve(__dirname, '../../../../data/charities');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));

  it('writes one detail file per published charity', () => {
    // Pinning a literal count here meant every roster change failed this test
    // for a reason that had nothing to do with citations. The invariant that
    // actually matters is that the two exports agree.
    const index = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, '../../../../data/charities.json'), 'utf8'),
    );
    const published = Array.isArray(index) ? index : (index.charities ?? []);

    expect(files).toHaveLength(published.length);
  });

  it('resolves essentially every inline citation reference in the corpus', () => {
    let refs = 0;
    let unresolved = 0;
    for (const f of files) {
      const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
      const rn = d?.amalEvaluation?.rich_narrative ?? {};
      const idx = buildCitationIndex(rn.all_citations, d);
      for (const key of ['summary', 'headline', 'amal_score_rationale']) {
        for (const seg of parseCitedText(rn[key], idx)) {
          if (seg.kind === 'cited') refs += 1;
        }
        const raw = typeof rn[key] === 'string' ? rn[key] : '';
        const total = (raw.match(/<cite\s+id="/gi) || []).length;
        unresolved += total;
      }
    }
    // Every <cite> in the corpus is counted in `unresolved`; resolved ones are
    // also counted in `refs`. "Essentially every" is the claim, so assert a
    // rate rather than the exact dangling count -- which was 1, and which any
    // regeneration can move without anything being wrong.
    const dangling = unresolved - refs;

    expect(dangling).toBeGreaterThanOrEqual(0);
    expect(dangling / Math.max(refs, 1)).toBeLessThan(0.01);
    // Citations are the substance of a rich narrative; a corpus averaging
    // under three would mean generation had quietly stopped emitting them.
    expect(refs).toBeGreaterThan(files.length * 3);
  });

  it('leaves no <cite markup in any rendered segment', () => {
    for (const f of files) {
      const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
      const rn = d?.amalEvaluation?.rich_narrative ?? {};
      const idx = buildCitationIndex(rn.all_citations, d);
      for (const seg of parseCitedText(rn.summary, idx)) {
        expect(seg.text).not.toContain('<cite');
        expect(seg.text).not.toContain('</cite>');
      }
    }
  });
});

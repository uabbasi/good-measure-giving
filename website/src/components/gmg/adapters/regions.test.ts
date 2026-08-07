import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  REGION_TAGS, ASNAF_TAGS, KNOWN_NON_GEOGRAPHIC_TAGS, regionsFromCauseTags, regionLabel,
} from './regions';

describe('regionsFromCauseTags', () => {
  it('maps known geography tags to display labels', () => {
    expect(regionsFromCauseTags(['faith-based', 'palestine', 'medical'])).toEqual(['Palestine']);
  });

  it('ignores tags that are not geography', () => {
    expect(regionsFromCauseTags(['grantmaking', 'fuqara', 'youth'])).toEqual([]);
  });

  it('maps a long-tail geography tag added after the initial top-30 cut', () => {
    expect(regionsFromCauseTags(['somalia'])).toEqual(['Somalia']);
  });

  it('does not treat the scope marker "international" as a region', () => {
    expect(regionsFromCauseTags(['international', 'grantmaking'])).toEqual([]);
  });

  it('preserves the order given in REGION_TAGS so output is stable', () => {
    const keys = Object.keys(REGION_TAGS);
    const out = regionsFromCauseTags([keys[2], keys[0]]);
    expect(out).toEqual([REGION_TAGS[keys[0]], REGION_TAGS[keys[2]]]);
  });

  it('tolerates missing or malformed input', () => {
    expect(regionsFromCauseTags(undefined)).toEqual([]);
    expect(regionsFromCauseTags(null)).toEqual([]);
    expect(regionsFromCauseTags('usa' as unknown)).toEqual([]);
    expect(regionsFromCauseTags([null, 5] as unknown[])).toEqual([]);
  });
});

describe('regionLabel', () => {
  it('names a single region', () => {
    expect(regionLabel(['Palestine'])).toBe('Palestine');
  });

  it('summarizes several without hiding the count', () => {
    expect(regionLabel(['Palestine', 'Syria', 'Yemen'])).toBe('Palestine +2');
  });

  it('renders nothing when no geography was extracted, rather than claiming Multi', () => {
    expect(regionLabel([])).toBe('');
  });

  it('stops naming an arbitrary leading region once the list gets long', () => {
    // REGION_TAGS order is corpus frequency, not this charity's emphasis —
    // "Palestine +12" for a 40-country operation implies Palestine is the
    // charity's lead region, which is not a fact this data supports.
    const many = ['Palestine', 'Syria', 'Yemen', 'Pakistan'];
    expect(regionLabel(many)).toBe('Multi-region (4)');
  });
});

describe('regions against the real index', () => {
  it('derives a region for a substantial share of the index', () => {
    const file = path.resolve(__dirname, '../../../../data/charities.json');
    const index = JSON.parse(fs.readFileSync(file, 'utf8'));
    const rows = index.charities as Array<Record<string, unknown>>;
    expect(rows).toHaveLength(166);
    const withRegion = rows.filter((c) => regionsFromCauseTags(c.causeTags).length > 0);
    expect(withRegion.length).toBeGreaterThanOrEqual(95);
  });
});

// REGION_TAGS and ASNAF_TAGS are hardcoded, curated subsets of the ~62
// distinct causeTags the corpus carries (causeTags holds 62 values; a
// set-equality check against either vocabulary would be wrong on purpose —
// `international` is deliberately excluded as a scope marker, not a place,
// and 4 of the 8 asnaf are fixed by fiqh with zero current matches). What
// *is* a real risk is one-directional: the pipeline starts emitting a new
// place tag (e.g. 'gaza') and the facet silently omits it, making those
// charities unfilterable by geography with nothing going red. These tests
// guard against exactly that, without asserting the vocabularies are closed.
describe('geography vocabulary drift guard', () => {
  // Below this, a single idiosyncratic tag ('clothing', 'homeless', a typo)
  // isn't worth forcing a classification decision over.
  const MIN_COUNT = 3;

  const tagCounts = (rows: Array<{ causeTags?: unknown }>): Map<string, number> => {
    const counts = new Map<string, number>();
    for (const row of rows) {
      const tags = Array.isArray(row.causeTags) ? row.causeTags : [];
      for (const raw of tags) {
        if (typeof raw !== 'string') continue;
        const tag = raw.toLowerCase();
        counts.set(tag, (counts.get(tag) ?? 0) + 1);
      }
    }
    return counts;
  };

  const unclassifiedTags = (counts: Map<string, number>, minCount: number): string[] => {
    const known = new Set<string>([
      ...Object.keys(REGION_TAGS),
      ...Object.keys(ASNAF_TAGS),
      ...KNOWN_NON_GEOGRAPHIC_TAGS,
    ]);
    return [...counts.entries()]
      .filter(([tag, n]) => n >= minCount && !known.has(tag))
      .map(([tag, n]) => `${tag} (${n})`);
  };

  const realRows = (): Array<Record<string, unknown>> => {
    const file = path.resolve(__dirname, '../../../../data/charities.json');
    const index = JSON.parse(fs.readFileSync(file, 'utf8'));
    return index.charities as Array<Record<string, unknown>>;
  };

  it(`classifies every causeTag on ${MIN_COUNT}+ charities as a region, an asnaf, or a known non-geographic tag`, () => {
    const unclassified = unclassifiedTags(tagCounts(realRows()), MIN_COUNT);
    expect(
      unclassified,
      unclassified.length > 0
        ? `Unclassified causeTag(s) — likely a new geography the pipeline started emitting: ${unclassified.join(', ')}. ` +
          'Classify each: add it to REGION_TAGS if it is a place, ASNAF_TAGS if it is a zakat category, ' +
          'or KNOWN_NON_GEOGRAPHIC_TAGS in regions.ts otherwise.'
        : undefined,
    ).toEqual([]);
  });

  it('every REGION_TAGS key still matches at least one charity in the corpus', () => {
    const counts = tagCounts(realRows());
    const stale = Object.keys(REGION_TAGS).filter((key) => !counts.get(key));
    expect(
      stale,
      stale.length > 0
        ? `REGION_TAGS key(s) with zero matches, possibly renamed or removed upstream: ${stale.join(', ')}`
        : undefined,
    ).toEqual([]);
  });

  it('flags a new high-frequency tag instead of silently dropping it (proves the guard bites)', () => {
    const counts = tagCounts([
      { causeTags: ['gaza', 'usa'] },
      { causeTags: ['gaza'] },
      { causeTags: ['gaza'] },
    ]);
    expect(unclassifiedTags(counts, MIN_COUNT)).toEqual(['gaza (3)']);
  });

  it('does not force classification of a one-off idiosyncratic tag below the threshold', () => {
    const counts = tagCounts([{ causeTags: ['a-typo-nobody-repeats'] }]);
    expect(unclassifiedTags(counts, MIN_COUNT)).toEqual([]);
  });
});

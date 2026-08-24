import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { adaptRow } from './charityAdapter';
import { buildCharitiesIndex } from '../../hooks/useCharities';
import {
  INITIAL_FACET_STATE, facetReducer, applyFacets, facetCounts,
  isFacetActive, facetStateToSearch, facetStateFromSearch, CAUSE_KEYS, EVIDENCE_VALUES,
} from './facetState';

const index = JSON.parse(readFileSync(join(__dirname, '../../../data/charities.json'), 'utf-8'));
const rows = buildCharitiesIndex(index).charities.map(adaptRow);

/**
 * Counts derived from the corpus, never hardcoded. These tests are about the
 * reducer -- whether toggling a facet filters correctly -- not about how many
 * charities happen to be humanitarian this month. Pinning literals here meant
 * every pipeline regeneration turned the reducer red for unrelated reasons.
 * Corpus composition is asserted once, as a snapshot, in
 * corpusComposition.test.ts.
 */
const TOTAL = rows.length;
const byCause = (k: string) => rows.filter((r) => r.causeKey === k).length;
const bySize = (b: string) => rows.filter((r) => r.sizeBand === b).length;
const byRegion = (k: string) => rows.filter((r) => r.regionTags.includes(k)).length;
const regionUnion = (...keys: string[]) =>
  rows.filter((r) => keys.some((k) => r.regionTags.includes(k))).length;
const asnafUnion = (...keys: string[]) =>
  rows.filter((r) => keys.some((k) => r.asnafTags.includes(k))).length;

describe('facetReducer', () => {
  it('starts with nothing selected and everything showing', () => {
    expect(applyFacets(rows, INITIAL_FACET_STATE)).toHaveLength(TOTAL);
    expect(isFacetActive(INITIAL_FACET_STATE)).toBe(false);
  });

  it('toggles a value on and back off', () => {
    const on = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    expect(on.cause).toEqual(['HUMANITARIAN']);
    expect(applyFacets(rows, on)).toHaveLength(byCause('HUMANITARIAN'));
    const off = facetReducer(on, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    expect(off.cause).toEqual([]);
    expect(applyFacets(rows, off)).toHaveLength(TOTAL);
  });

  it('ORs within a facet', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    s = facetReducer(s, { type: 'toggle', facet: 'cause', value: 'MEDICAL_HEALTH' });
    expect(applyFacets(rows, s)).toHaveLength(byCause('HUMANITARIAN') + byCause('MEDICAL_HEALTH'));
  });

  it('ANDs across facets', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    s = facetReducer(s, { type: 'scope', value: 'muslim' });
    const out = applyFacets(rows, s);
    expect(out.every((r) => r.causeKey === 'HUMANITARIAN' && r.isMuslimLed)).toBe(true);
    expect(out.length).toBeLessThan(byCause('HUMANITARIAN'));
    expect(out.length).toBeGreaterThan(0);
  });

  it('excludes revenue-less charities only when size is active', () => {
    expect(applyFacets(rows, INITIAL_FACET_STATE)).toHaveLength(TOTAL);
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'size', value: 'gte100m' });
    expect(applyFacets(rows, s)).toHaveLength(bySize('gte100m'));
    expect(applyFacets(rows, s).every((r) => r.sizeBand === 'gte100m')).toBe(true);
  });

  it('matches only the charities carrying the selected region tag', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'region', value: 'usa' });
    expect(applyFacets(rows, s)).toHaveLength(byRegion('usa'));
  });

  // region and asnaf are multi-valued row fields (a charity can carry several
  // region/asnaf tags), so they route through `intersects` rather than the
  // `matchesOneOf` helper the 'ORs within a facet' test above exercises for
  // cause. Nothing previously pinned that a multi-value selection on either
  // one is still an OR, not an AND.
  it('ORs within the region facet rather than intersecting', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'region', value: 'usa' });
    s = facetReducer(s, { type: 'toggle', facet: 'region', value: 'palestine' });
    // The OR is the point: the union must exceed either tag alone, which an
    // AND could never do.
    expect(applyFacets(rows, s)).toHaveLength(regionUnion('usa', 'palestine'));
    expect(regionUnion('usa', 'palestine')).toBeGreaterThan(
      Math.max(byRegion('usa'), byRegion('palestine')),
    );
  });

  it('ORs within the asnaf facet rather than intersecting', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'asnaf', value: 'fuqara' });
    s = facetReducer(s, { type: 'toggle', facet: 'asnaf', value: 'muallaf' });
    expect(applyFacets(rows, s)).toHaveLength(asnafUnion('fuqara', 'muallaf'));
    expect(asnafUnion('fuqara', 'muallaf')).toBeGreaterThan(
      rows.filter((r) => r.asnafTags.includes('fuqara')).length,
    );
  });

  it('treats a search query as not-a-facet', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'query', value: 'islamic' });
    expect(isFacetActive(s)).toBe(false);
    expect(applyFacets(rows, s).length).toBeLessThan(TOTAL);
  });

  it('clearAll returns to the initial state but keeps nothing stale', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    s = facetReducer(s, { type: 'query', value: 'relief' });
    s = facetReducer(s, { type: 'wallet', value: 'zakat' });
    expect(facetReducer(s, { type: 'clearAll' })).toEqual(INITIAL_FACET_STATE);
  });

  it('never mutates the state it is given', () => {
    const before = JSON.stringify(INITIAL_FACET_STATE);
    facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    expect(JSON.stringify(INITIAL_FACET_STATE)).toBe(before);
  });

  it('CAUSE_KEYS matches the distinct causeKey values across the corpus exactly', () => {
    const distinct = new Set(rows.map((r) => r.causeKey).filter(Boolean));
    expect(new Set(CAUSE_KEYS)).toEqual(distinct);
  });

  it('EVIDENCE_VALUES matches the distinct verification values across the corpus exactly', () => {
    const distinct = new Set(rows.map((r) => r.verification).filter(Boolean));
    expect(new Set(EVIDENCE_VALUES)).toEqual(distinct);
    const total = EVIDENCE_VALUES.reduce(
      (sum, v) => sum + rows.filter((r) => r.verification === v).length,
      0,
    );
    expect(total).toBe(TOTAL);
  });
});

describe('facetCounts', () => {
  it('counts each value over the unfiltered set when nothing is selected', () => {
    const c = facetCounts(rows, INITIAL_FACET_STATE, 'cause');
    expect(c.HUMANITARIAN).toBe(byCause('HUMANITARIAN'));
    expect(c.MEDIA_JOURNALISM).toBe(byCause('MEDIA_JOURNALISM'));
  });

  it('ignores the facet\'s own selection so counts stay stable while narrowing', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    const c = facetCounts(rows, s, 'cause');
    expect(c.MEDICAL_HEALTH).toBe(byCause('MEDICAL_HEALTH'));   // not 0 — the user can still add it
    expect(c.HUMANITARIAN).toBe(byCause('HUMANITARIAN'));
  });

  it('does narrow a facet by the OTHER facets\' selections', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'scope', value: 'muslim' });
    const c = facetCounts(rows, s, 'cause');
    expect(c.HUMANITARIAN).toBeLessThan(byCause('HUMANITARIAN'));
  });
});

describe('URL round trip', () => {
  it('round-trips a populated state', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    s = facetReducer(s, { type: 'toggle', facet: 'region', value: 'palestine' });
    s = facetReducer(s, { type: 'toggle', facet: 'size', value: 'gte100m' });
    s = facetReducer(s, { type: 'wallet', value: 'zakat' });
    s = facetReducer(s, { type: 'scope', value: 'muslim' });
    s = facetReducer(s, { type: 'query', value: 'relief fund' });
    expect(facetStateFromSearch(facetStateToSearch(s))).toEqual(s);
  });

  it('emits nothing for the initial state', () => {
    expect(facetStateToSearch(INITIAL_FACET_STATE)).toBe('');
  });

  it('ignores unknown values and unknown params rather than throwing', () => {
    const s = facetStateFromSearch('?cause=NOT_A_CAUSE&bogus=1&size=lt1m');
    expect(s.cause).toEqual([]);
    expect(s.size).toEqual(['lt1m']);
  });

  it('does not resurrect the retired ?type= parameter as facet state', () => {
    expect(facetStateFromSearch('?type=serif')).toEqual(INITIAL_FACET_STATE);
  });
});

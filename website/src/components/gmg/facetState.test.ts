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

describe('facetReducer', () => {
  it('starts with nothing selected and everything showing', () => {
    expect(applyFacets(rows, INITIAL_FACET_STATE)).toHaveLength(166);
    expect(isFacetActive(INITIAL_FACET_STATE)).toBe(false);
  });

  it('toggles a value on and back off', () => {
    const on = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    expect(on.cause).toEqual(['HUMANITARIAN']);
    expect(applyFacets(rows, on)).toHaveLength(35);
    const off = facetReducer(on, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    expect(off.cause).toEqual([]);
    expect(applyFacets(rows, off)).toHaveLength(166);
  });

  it('ORs within a facet', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    s = facetReducer(s, { type: 'toggle', facet: 'cause', value: 'MEDICAL_HEALTH' });
    expect(applyFacets(rows, s)).toHaveLength(35 + 14);
  });

  it('ANDs across facets', () => {
    let s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    s = facetReducer(s, { type: 'scope', value: 'muslim' });
    const out = applyFacets(rows, s);
    expect(out.every((r) => r.causeKey === 'HUMANITARIAN' && r.isMuslimLed)).toBe(true);
    expect(out.length).toBeLessThan(35);
    expect(out.length).toBeGreaterThan(0);
  });

  it('excludes the 7 revenue-less charities only when size is active', () => {
    expect(applyFacets(rows, INITIAL_FACET_STATE)).toHaveLength(166);
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'size', value: 'gte100m' });
    expect(applyFacets(rows, s)).toHaveLength(24);
    expect(applyFacets(rows, s).every((r) => r.sizeBand === 'gte100m')).toBe(true);
  });

  it('matches no region for the 69 charities with no region tag', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'region', value: 'usa' });
    expect(applyFacets(rows, s)).toHaveLength(52);
  });

  it('treats a search query as not-a-facet', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'query', value: 'islamic' });
    expect(isFacetActive(s)).toBe(false);
    expect(applyFacets(rows, s).length).toBeLessThan(166);
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
    expect(total).toBe(166);
  });
});

describe('facetCounts', () => {
  it('counts each value over the unfiltered set when nothing is selected', () => {
    const c = facetCounts(rows, INITIAL_FACET_STATE, 'cause');
    expect(c.HUMANITARIAN).toBe(35);
    expect(c.MEDIA_JOURNALISM).toBe(2);
  });

  it('ignores the facet\'s own selection so counts stay stable while narrowing', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'toggle', facet: 'cause', value: 'HUMANITARIAN' });
    const c = facetCounts(rows, s, 'cause');
    expect(c.MEDICAL_HEALTH).toBe(14);   // not 0 — the user can still add it
    expect(c.HUMANITARIAN).toBe(35);
  });

  it('does narrow a facet by the OTHER facets\' selections', () => {
    const s = facetReducer(INITIAL_FACET_STATE, { type: 'scope', value: 'muslim' });
    const c = facetCounts(rows, s, 'cause');
    expect(c.HUMANITARIAN).toBeLessThan(35);
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

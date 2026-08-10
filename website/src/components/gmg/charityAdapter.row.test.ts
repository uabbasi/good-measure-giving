import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { adaptRow } from './charityAdapter';
import { buildCharitiesIndex } from '../../hooks/useCharities';

const index = JSON.parse(
  readFileSync(join(__dirname, '../../../data/charities.json'), 'utf-8'),
);
const rows = buildCharitiesIndex(index).charities.map(adaptRow);

describe('adaptRow facet fields', () => {
  it('covers all 166 charities', () => {
    expect(rows).toHaveLength(166);
  });

  it('marks exactly 123 charities Muslim-led', () => {
    expect(rows.filter((r) => r.isMuslimLed)).toHaveLength(123);
  });

  it('assigns the four size bands with 7 unbanded', () => {
    const count = (b: string) => rows.filter((r) => r.sizeBand === b).length;
    expect(count('lt1m')).toBe(26);
    expect(count('1to10m')).toBe(74);
    expect(count('10to100m')).toBe(35);
    expect(count('gte100m')).toBe(24);
    expect(rows.filter((r) => r.sizeBand === null)).toHaveLength(7);
  });

  it('reads region keys from causeTags, leaving 69 with none', () => {
    expect(rows.filter((r) => r.regionTags.length === 0)).toHaveLength(69);
    expect(rows.filter((r) => r.regionTags.includes('usa'))).toHaveLength(52);
    expect(rows.filter((r) => r.regionTags.includes('palestine'))).toHaveLength(33);
  });

  it('reads the four asnaf that actually appear, leaving 65 with none', () => {
    expect(rows.filter((r) => r.asnafTags.includes('fuqara'))).toHaveLength(89);
    expect(rows.filter((r) => r.asnafTags.includes('masakin'))).toHaveLength(88);
    expect(rows.filter((r) => r.asnafTags.includes('fisabilillah'))).toHaveLength(50);
    expect(rows.filter((r) => r.asnafTags.includes('muallaf'))).toHaveLength(20);
    expect(rows.filter((r) => r.asnafTags.length === 0)).toHaveLength(65);
  });

  it('gives every row a causeKey drawn from the 16-value enum', () => {
    const keys = new Set(rows.map((r) => r.causeKey));
    expect(keys.size).toBe(16);
    expect(keys.has('HUMANITARIAN')).toBe(true);
    expect(rows.every((r) => r.causeKey.length > 0)).toBe(true);
  });

  it('keeps the existing display fields unchanged', () => {
    // cause is the human label, causeKey is the enum — they must not be swapped
    const humanitarian = rows.filter((r) => r.causeKey === 'HUMANITARIAN');
    expect(humanitarian).toHaveLength(35);
    expect(humanitarian.every((r) => r.cause === 'Humanitarian Relief')).toBe(true);
  });
});

// The corpus-driven tests above happen to contain zero charities at exactly
// $1M/$10M/$100M, so mutating a `<` to `<=` at any of the three toSizeBand
// boundaries doesn't turn them red — that gap holds regardless of which
// values happen to exist in data/charities.json today. These assertions pin
// each boundary directly, independent of corpus coincidence, via a minimal
// row rather than the exported band function.
const rowWithRevenue = (totalRevenue: number | null) => adaptRow({ ein: '00-0000000', totalRevenue });

describe('adaptRow sizeBand boundaries (pure values, not corpus-dependent)', () => {
  it('bands just under, at, and just over the $1M boundary', () => {
    expect(rowWithRevenue(999_999).sizeBand).toBe('lt1m');
    expect(rowWithRevenue(1_000_000).sizeBand).toBe('1to10m');
    expect(rowWithRevenue(1_000_001).sizeBand).toBe('1to10m');
  });

  it('bands just under, at, and just over the $10M boundary', () => {
    expect(rowWithRevenue(9_999_999).sizeBand).toBe('1to10m');
    expect(rowWithRevenue(10_000_000).sizeBand).toBe('10to100m');
    expect(rowWithRevenue(10_000_001).sizeBand).toBe('10to100m');
  });

  it('bands just under, at, and just over the $100M boundary', () => {
    expect(rowWithRevenue(99_999_999).sizeBand).toBe('10to100m');
    expect(rowWithRevenue(100_000_000).sizeBand).toBe('gte100m');
    expect(rowWithRevenue(100_000_001).sizeBand).toBe('gte100m');
  });

  it('leaves null revenue unbanded, distinct from a genuine filed zero', () => {
    expect(rowWithRevenue(null).sizeBand).toBeNull();
    expect(rowWithRevenue(0).sizeBand).toBe('lt1m');
  });
});

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

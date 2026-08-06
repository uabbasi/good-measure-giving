import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { REGION_TAGS, regionsFromCauseTags, regionLabel } from './regions';

describe('regionsFromCauseTags', () => {
  it('maps known geography tags to display labels', () => {
    expect(regionsFromCauseTags(['faith-based', 'palestine', 'medical'])).toEqual(['Palestine']);
  });

  it('ignores tags that are not geography', () => {
    expect(regionsFromCauseTags(['grantmaking', 'fuqara', 'youth'])).toEqual([]);
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

  it('falls back to Multi only when nothing is known', () => {
    expect(regionLabel([])).toBe('Multi');
  });
});

describe('regions against the real index', () => {
  it('derives a region for a substantial share of the index', () => {
    const file = path.resolve(__dirname, '../../../../data/charities.json');
    const index = JSON.parse(fs.readFileSync(file, 'utf8'));
    const rows = index.charities as Array<Record<string, unknown>>;
    expect(rows).toHaveLength(166);
    const withRegion = rows.filter((c) => regionsFromCauseTags(c.causeTags).length > 0);
    expect(withRegion.length).toBeGreaterThanOrEqual(80);
  });
});

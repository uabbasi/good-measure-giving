// Runs every exported charity through the adapter and asserts that fields
// actually arrive. A wrong field path fails here instead of silently
// rendering an empty row, which is how targeting.* went unnoticed.
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity, adaptRow } from './charityAdapter';

const dir = path.resolve(__dirname, '../../../data/charities');
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
const all = files.map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));

const indexFile = path.resolve(__dirname, '../../../data/charities.json');
const index = JSON.parse(fs.readFileSync(indexFile, 'utf8')).charities as Record<string, unknown>[];

describe('adaptCharity over the real corpus', () => {
  it('covers all 166 exported charities', () => {
    expect(all).toHaveLength(166);
  });

  it('reads populations from targeting, not the absent top-level key', () => {
    const withPopulations = all.map(adaptCharity).filter((c) => c.populations.length > 0);
    expect(withPopulations.length).toBeGreaterThanOrEqual(150);
  });

  it('reads geography from targeting', () => {
    const withGeography = all.map(adaptCharity).filter((c) => c.geography.length > 0);
    expect(withGeography.length).toBeGreaterThanOrEqual(100);
  });

  it('does not fall back to the literal "Multi" for most charities', () => {
    const multi = all.map(adaptCharity).filter((c) => c.region === 'Multi');
    expect(multi.length).toBeLessThanOrEqual(60);
  });

  it('carries award URLs through so the page can link them', () => {
    // Loose inequality: pre-fix, the field is absent (undefined), not null.
    // `!== null` would count `undefined` as "present" and pass trivially
    // whether or not the URLs are actually threaded through.
    const adapted = all.map(adaptCharity);
    expect(adapted.filter((c) => c.awards.cnUrl != null).length).toBeGreaterThanOrEqual(50);
    expect(adapted.filter((c) => c.awards.bbbUrl != null).length).toBeGreaterThanOrEqual(20);
  });

  it('never throws and always yields a name and ein', () => {
    for (const c of all.map(adaptCharity)) {
      expect(c.name).not.toBe('');
      expect(c.ein).not.toBe('');
    }
  });
});

describe('adaptRow over the real index', () => {
  it('derives a region for a substantial share of rows', () => {
    const rows = index.map(adaptRow);
    expect(rows).toHaveLength(166);
    expect(rows.filter((r) => r.region !== 'Multi').length).toBeGreaterThanOrEqual(80);
  });
});

describe('adaptCharity exposes the newly wired data', () => {
  it('carries a citation index for every charity', () => {
    const adapted = all.map(adaptCharity);
    expect(adapted.every((c) => c.citations.ordered.length > 0)).toBe(true);
  });

  it('carries anchored concerns totalling the corpus count', () => {
    const total = all.map(adaptCharity).reduce((n, c) => n + c.concerns.all.length, 0);
    expect(total).toBe(343);
  });

  it('carries grant flows for exactly the grantmaking charities', () => {
    expect(all.map(adaptCharity).filter((c) => c.grantFlows !== null)).toHaveLength(81);
  });

  it('carries a financial series for most charities', () => {
    const withSeries = all.map(adaptCharity).filter((c) => c.financialSeries.length > 0);
    expect(withSeries.length).toBeGreaterThanOrEqual(155);
  });
});

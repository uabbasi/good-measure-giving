// Runs every exported charity through the adapter and asserts that fields
// actually arrive. A wrong field path fails here instead of silently
// rendering an empty row, which is how targeting.* went unnoticed.
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity, adaptRow } from './charityAdapter';
import { regionsFromCauseTags } from './adapters/regions';

const dir = path.resolve(__dirname, '../../../data/charities');
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
const all = files.map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));

const indexFile = path.resolve(__dirname, '../../../data/charities.json');
const index = JSON.parse(fs.readFileSync(indexFile, 'utf8')).charities as Record<string, unknown>[];

describe('adaptCharity over the real corpus', () => {
  it('exports a non-empty, self-consistent corpus (no dupes, filename matches content)', () => {
    expect(files.length).toBeGreaterThan(0);
    const einsFromFilenames = files.map((f) => f.replace(/^charity-/, '').replace(/\.json$/, ''));
    const einsFromContent = all.map((c) => c.ein);
    expect(einsFromContent).toEqual(einsFromFilenames);
    expect(new Set(einsFromContent).size).toBe(einsFromContent.length);
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

  it('agrees with the index row region whenever a region cause-tag is present', () => {
    const byEin = new Map(index.map((row) => [row.ein as string, row]));
    let checked = 0;
    for (const c of all) {
      const indexRow = byEin.get(c.ein);
      if (!indexRow || regionsFromCauseTags((indexRow as any).causeTags).length === 0) continue;
      checked += 1;
      expect(adaptCharity(c).region).toBe(adaptRow(indexRow).region);
    }
    // Sanity: this must actually exercise real charities, not vacuously pass.
    expect(checked).toBeGreaterThan(0);
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
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.filter((r) => r.region !== 'Multi').length).toBeGreaterThanOrEqual(80);
  });
});

describe('adaptCharity exposes the newly wired data', () => {
  it('carries a citation index for every charity that has raw citations', () => {
    for (const c of all) {
      const rawCitations = c?.amalEvaluation?.rich_narrative?.all_citations;
      if (!Array.isArray(rawCitations) || rawCitations.length === 0) continue;
      expect(adaptCharity(c).citations.ordered.length).toBeGreaterThan(0);
    }
  });

  it('carries anchored concerns totalling the corpus count', () => {
    const total = all.map(adaptCharity).reduce((n, c) => n + c.concerns.all.length, 0);
    const raw = all.reduce(
      (n, c) => n + (Array.isArray(c?.keyConcerns) ? c.keyConcerns.length : 0),
      0,
    );
    expect(total).toBe(raw);
  });

  it('carries grant flows iff the raw record has non-empty grantsData', () => {
    for (const c of all) {
      const hasRawGrants = Array.isArray(c?.grantsData) && c.grantsData.length > 0;
      expect(adaptCharity(c).grantFlows !== null).toBe(hasRawGrants);
    }
  });

  it('carries a financial series for most charities', () => {
    const withSeries = all.map(adaptCharity).filter((c) => c.financialSeries.length > 0);
    expect(withSeries.length).toBeGreaterThanOrEqual(155);
  });

  it('carries GIK/burn-rate signals matching the measured corpus population', () => {
    const adapted = all.map(adaptCharity);
    expect(adapted.filter((c) => c.noncashRatio !== null).length).toBe(62);
    expect(adapted.filter((c) => c.cashAdjustedProgramRatio !== null).length).toBe(20);
    expect(adapted.filter((c) => c.domesticBurnRate !== null).length).toBe(32);
    const atLeastOne = adapted.filter(
      (c) => c.noncashRatio !== null || c.cashAdjustedProgramRatio !== null || c.domesticBurnRate !== null,
    );
    expect(atLeastOne.length).toBe(71);
  });
});

import { describe, it, expect } from 'vitest';
import { computeVersionStripStats, type VersionStripCharity } from './versionStripData';

const c = (over: Partial<VersionStripCharity>): VersionStripCharity => ({
  amalScore: 80,
  walletTag: 'SADAQAH-ELIGIBLE',
  hideFromCurated: false,
  lastUpdated: '2026-01-01 00:00:00',
  ...over,
});

describe('computeVersionStripStats', () => {
  it('counts rated charities (scored and not hidden)', () => {
    const stats = computeVersionStripStats([
      c({ amalScore: 90 }),
      c({ amalScore: 70 }),
      c({ amalScore: null }), // unrated — excluded
      c({ amalScore: 60, hideFromCurated: true }), // hidden — excluded
    ]);
    expect(stats.ratedCount).toBe(2);
  });

  it('counts zakat-eligible by wallet tag', () => {
    const stats = computeVersionStripStats([
      c({ walletTag: 'ZAKAT-ELIGIBLE' }),
      c({ walletTag: 'ZAKAT-ELIGIBLE' }),
      c({ walletTag: 'SADAQAH-ELIGIBLE' }),
    ]);
    expect(stats.zakatCount).toBe(2);
  });

  it('derives the updated date and edition from the max lastUpdated', () => {
    const stats = computeVersionStripStats([
      c({ lastUpdated: '2026-06-27 19:16:58' }),
      c({ lastUpdated: '2026-05-01 12:00:00' }),
      c({ lastUpdated: '2026-06-10 08:30:00' }),
    ]);
    expect(stats.updated).toBe('2026-06-27');
    expect(stats.edition).toBe('June 2026');
    // Hijri year resolves via Intl (Umm al-Qura) where ICU is available.
    expect(stats.hijriYear === null || stats.hijriYear >= 1447).toBe(true);
  });

  it('returns zero counts and null dates for empty / missing input', () => {
    expect(computeVersionStripStats([])).toEqual({
      ratedCount: 0,
      zakatCount: 0,
      updated: null,
      edition: null,
      hijriYear: null,
    });
    expect(computeVersionStripStats(null)).toEqual({
      ratedCount: 0,
      zakatCount: 0,
      updated: null,
      edition: null,
      hijriYear: null,
    });
  });

  it('matches the live data shape (124 charities / 95 zakat / June 2026)', () => {
    // Mirrors the production index at build time: a couple hidden + unrated rows
    // plus a single newest timestamp.
    const list: VersionStripCharity[] = [];
    for (let i = 0; i < 124; i++) list.push(c({ amalScore: 75, lastUpdated: '2026-06-01 00:00:00' }));
    for (let i = 0; i < 95; i++) list[i].walletTag = 'ZAKAT-ELIGIBLE';
    list.push(c({ amalScore: null, lastUpdated: '2026-06-27 19:16:58' })); // newest but unrated
    const stats = computeVersionStripStats(list);
    expect(stats.ratedCount).toBe(124);
    expect(stats.zakatCount).toBe(95);
    expect(stats.updated).toBe('2026-06-27');
    expect(stats.edition).toBe('June 2026');
  });
});

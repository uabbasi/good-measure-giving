import { describe, it, expect } from 'vitest';
import { adaptRow } from './charityAdapter';

/**
 * Corpus composition -- how many charities are Muslim-led, which size bands
 * they fall in, which region and asnaf tags appear -- is asserted once in
 * corpusComposition.test.ts as a snapshot. Pinning those counts here too meant
 * every pipeline regeneration turned this file red for reasons that had
 * nothing to do with adaptRow.
 *
 * What remains is the part that is genuinely about adaptRow: the size-band
 * boundaries. The corpus happens to contain zero charities at exactly
 * $1M/$10M/$100M, so mutating a `<` to `<=` at any of the three toSizeBand
 * boundaries would not turn a corpus-driven test red -- a gap that holds
 * regardless of which values live in data/charities.json today. These pin each
 * boundary directly, via a minimal row rather than the exported band function.
 */
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

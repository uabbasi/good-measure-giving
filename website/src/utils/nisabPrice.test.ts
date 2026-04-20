import { describe, it, expect } from 'vitest';
import { computeNisabFromGoldPricePerOunce, isPlausibleNisab } from './nisabPrice';

describe('computeNisabFromGoldPricePerOunce', () => {
  it('computes 85g nisab from gold price per troy ounce', () => {
    // $2,800/oz gold → 85g = 85/31.1 oz ≈ 2.73 oz × $2,800 ≈ $7,653
    const nisab = computeNisabFromGoldPricePerOunce(2800);
    expect(nisab).toBeGreaterThanOrEqual(7600);
    expect(nisab).toBeLessThanOrEqual(7700);
  });

  it('scales linearly with price', () => {
    const low = computeNisabFromGoldPricePerOunce(2000);
    const high = computeNisabFromGoldPricePerOunce(4000);
    expect(high).toBeCloseTo(low * 2, -1);
  });
});

describe('isPlausibleNisab', () => {
  it('accepts values in the $3k-$20k sanity range', () => {
    expect(isPlausibleNisab(6_970)).toBe(true);
    expect(isPlausibleNisab(8_500)).toBe(true);
    expect(isPlausibleNisab(12_000)).toBe(true);
  });

  it('rejects implausibly low or high values', () => {
    expect(isPlausibleNisab(500)).toBe(false);
    expect(isPlausibleNisab(100_000)).toBe(false);
    expect(isPlausibleNisab(0)).toBe(false);
    expect(isPlausibleNisab(-1)).toBe(false);
  });

  it('rejects non-finite values', () => {
    expect(isPlausibleNisab(NaN)).toBe(false);
    expect(isPlausibleNisab(Infinity)).toBe(false);
  });
});

import { describe, it, expect } from 'vitest';
import { computeNisabFromGoldPricePerOunce, isPlausibleNisab } from './nisabPrice';
import {
  computeSilverPricePerGramFromOunce,
  isPlausibleSilverPrice,
} from './nisabPrice';

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

describe('computeSilverPricePerGramFromOunce', () => {
  it('converts a per-troy-ounce price to per-gram', () => {
    // $31.10/oz silver → $1.00/g (31.10/31.1034768 ≈ 1.0)
    expect(computeSilverPricePerGramFromOunce(31.1034768)).toBeCloseTo(1.0, 4);
  });

  it('scales linearly with price', () => {
    const low = computeSilverPricePerGramFromOunce(30);
    const high = computeSilverPricePerGramFromOunce(60);
    expect(high).toBeCloseTo(low * 2, 6);
  });
});

describe('isPlausibleSilverPrice', () => {
  it('accepts values in the $0.3-$5.0/g sanity range', () => {
    expect(isPlausibleSilverPrice(0.9)).toBe(true);
    expect(isPlausibleSilverPrice(1.7)).toBe(true);
    expect(isPlausibleSilverPrice(3.0)).toBe(true);
  });

  it('rejects implausibly low or high values', () => {
    expect(isPlausibleSilverPrice(0.05)).toBe(false);
    expect(isPlausibleSilverPrice(50)).toBe(false);
    expect(isPlausibleSilverPrice(0)).toBe(false);
  });

  it('rejects non-finite values', () => {
    expect(isPlausibleSilverPrice(NaN)).toBe(false);
    expect(isPlausibleSilverPrice(Infinity)).toBe(false);
  });
});

import { describe, expect, it } from 'vitest';
import { calculateZakat, NISAB_USD, ZAKAT_RATE } from './zakatCalculator';

describe('calculateZakat', () => {
  it('calculates 2.5% on cash above nisab', () => {
    const result = calculateZakat({ cash: 50_000 });
    expect(result.zakatAmount).toBe(Math.round(50_000 * ZAKAT_RATE));
    expect(result.isAboveNisab).toBe(true);
    expect(result.netZakatable).toBe(50_000);
  });

  it('returns zero when below nisab', () => {
    const result = calculateZakat({ cash: 1_000 });
    expect(result.zakatAmount).toBe(0);
    expect(result.isAboveNisab).toBe(false);
    expect(result.netZakatable).toBe(1_000);
  });

  it('returns zero for exactly zero assets', () => {
    const result = calculateZakat({});
    expect(result.zakatAmount).toBe(0);
    expect(result.totalAssets).toBe(0);
    expect(result.netZakatable).toBe(0);
    expect(result.isAboveNisab).toBe(false);
  });

  it('sums all asset categories', () => {
    const result = calculateZakat({
      cash: 10_000,
      gold: 5_000,
      silver: 1_000,
      stocks: 20_000,
      businessInventory: 3_000,
      receivables: 2_000,
      rentalIncome: 4_000,
      other: 500,
    });
    expect(result.totalAssets).toBe(45_500);
    expect(result.zakatAmount).toBe(Math.round(45_500 * ZAKAT_RATE));
  });

  it('deducts all liability categories', () => {
    const result = calculateZakat(
      { cash: 100_000 },
      { debts: 10_000, loans: 5_000, creditCards: 2_000, other: 1_000 },
    );
    expect(result.totalLiabilities).toBe(18_000);
    expect(result.netZakatable).toBe(82_000);
    expect(result.zakatAmount).toBe(Math.round(82_000 * ZAKAT_RATE));
  });

  it('clamps net zakatable to zero when liabilities exceed assets', () => {
    const result = calculateZakat({ cash: 5_000 }, { debts: 50_000 });
    expect(result.netZakatable).toBe(0);
    expect(result.zakatAmount).toBe(0);
    expect(result.isAboveNisab).toBe(false);
  });

  it('handles nisab boundary exactly at threshold', () => {
    const result = calculateZakat({ cash: NISAB_USD });
    expect(result.isAboveNisab).toBe(true);
    expect(result.zakatAmount).toBe(Math.round(NISAB_USD * ZAKAT_RATE));
  });

  it('handles nisab boundary one dollar below', () => {
    const result = calculateZakat({ cash: NISAB_USD - 1 });
    expect(result.isAboveNisab).toBe(false);
    expect(result.zakatAmount).toBe(0);
  });

  it('rounds zakat amount to nearest dollar', () => {
    // 10_001 * 0.025 = 250.025 → should round to 250
    const result = calculateZakat({ cash: 10_001 });
    expect(result.zakatAmount).toBe(250);
  });

  it('treats missing liabilities as zero', () => {
    const withoutLiabilities = calculateZakat({ cash: 50_000 });
    const withEmptyLiabilities = calculateZakat({ cash: 50_000 }, {});
    expect(withoutLiabilities.zakatAmount).toBe(withEmptyLiabilities.zakatAmount);
  });
});

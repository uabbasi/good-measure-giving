// src/utils/zakatChart.test.ts
import { describe, it, expect } from 'vitest';
import { buildChartRows, GOLD_WEIGHTS, SILVER_WEIGHTS } from './zakatChart';

describe('buildChartRows', () => {
  it('computes value = grams × pricePerGram and zakat = value × 2.5%', () => {
    const rows = buildChartRows(100, [{ label: '10 g', grams: 10 }]);
    expect(rows).toHaveLength(1);
    expect(rows[0].value).toBeCloseTo(1000, 6);
    expect(rows[0].zakat).toBeCloseTo(25, 6);
    expect(rows[0].isNisab).toBe(false);
  });

  it('passes through the isNisab flag', () => {
    const rows = buildChartRows(100, [{ label: '85 g (nisab)', grams: 85, isNisab: true }]);
    expect(rows[0].isNisab).toBe(true);
  });

  it('scales linearly with price', () => {
    const low = buildChartRows(50, GOLD_WEIGHTS);
    const high = buildChartRows(100, GOLD_WEIGHTS);
    expect(high[0].value).toBeCloseTo(low[0].value * 2, 6);
    expect(high[0].zakat).toBeCloseTo(low[0].zakat * 2, 6);
  });
});

describe('weight tables', () => {
  it('gold table marks exactly the 85g row as nisab', () => {
    const nisabRows = GOLD_WEIGHTS.filter((w) => w.isNisab);
    expect(nisabRows).toHaveLength(1);
    expect(nisabRows[0].grams).toBe(85);
  });

  it('silver table marks exactly the 595g row as nisab', () => {
    const nisabRows = SILVER_WEIGHTS.filter((w) => w.isNisab);
    expect(nisabRows).toHaveLength(1);
    expect(nisabRows[0].grams).toBe(595);
  });
});

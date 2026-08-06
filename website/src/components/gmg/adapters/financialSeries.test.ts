import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { buildFinancialSeries } from './financialSeries';

describe('buildFinancialSeries', () => {
  it('treats a zero as not-reported, not as a real value', () => {
    const s = buildFinancialSeries([
      { year: 2024, revenue: 1529582620, expenses: 0, net_assets: 0 },
    ]);
    expect(s).toEqual([
      { year: 2024, revenue: 1529582620, expenses: null, netAssets: null },
    ]);
  });

  it('sorts ascending by year', () => {
    const s = buildFinancialSeries([
      { year: 2024, revenue: 3, expenses: 3, net_assets: 3 },
      { year: 2022, revenue: 1, expenses: 1, net_assets: 1 },
      { year: 2023, revenue: 2, expenses: 2, net_assets: 2 },
    ]);
    expect(s.map((r) => r.year)).toEqual([2022, 2023, 2024]);
  });

  it('drops a row with no usable figure at all', () => {
    expect(buildFinancialSeries([{ year: 2024, revenue: 0, expenses: 0, net_assets: 0 }])).toEqual([]);
  });

  it('drops a row with no year', () => {
    expect(buildFinancialSeries([{ revenue: 10, expenses: 5, net_assets: 5 }])).toEqual([]);
  });

  it('returns an empty series for missing or malformed input', () => {
    expect(buildFinancialSeries(undefined)).toEqual([]);
    expect(buildFinancialSeries(null)).toEqual([]);
    expect(buildFinancialSeries('nope' as unknown)).toEqual([]);
    expect(buildFinancialSeries([null, 7] as unknown[])).toEqual([]);
  });
});

describe('buildFinancialSeries against the real corpus', () => {
  const dir = path.resolve(__dirname, '../../../../data/charities');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));

  it('never emits a zero as a rendered figure', () => {
    let charitiesWithSeries = 0;
    for (const f of files) {
      const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
      const raw = d?.amalEvaluation?.rich_narrative?.financial_deep_dive?.yearly_financials;
      const s = buildFinancialSeries(raw);
      if (s.length > 0) charitiesWithSeries += 1;
      for (const r of s) {
        expect(r.revenue).not.toBe(0);
        expect(r.expenses).not.toBe(0);
        expect(r.netAssets).not.toBe(0);
      }
    }
    expect(charitiesWithSeries).toBeGreaterThanOrEqual(155);
  });
});

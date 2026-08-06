// src/components/gmg/adapters/grantFlows.test.ts
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { aggregateGrants } from './grantFlows';

const row = (over: Record<string, unknown> = {}) => ({
  amount: 100, is_foreign: false, purpose: 'General support',
  recipient_ein: '11-1111111', recipient_name: 'Alpha Relief',
  region: 'United States', tax_year: 2023, ...over,
});

describe('aggregateGrants', () => {
  it('returns null when there are no grants', () => {
    expect(aggregateGrants(undefined)).toBeNull();
    expect(aggregateGrants([])).toBeNull();
    expect(aggregateGrants('nope' as unknown)).toBeNull();
  });

  it('uses only the most recent tax year so recurring recipients are not double counted', () => {
    const r = aggregateGrants([
      row({ tax_year: 2022, amount: 500 }),
      row({ tax_year: 2023, amount: 100 }),
    ]);
    expect(r?.taxYear).toBe(2023);
    expect(r?.grantCount).toBe(1);
    expect(r?.totalAmount).toBe(100);
  });

  it('splits domestic from foreign', () => {
    const r = aggregateGrants([
      row({ amount: 300, is_foreign: false }),
      row({ amount: 200, is_foreign: true, recipient_name: 'Beta Aid', recipient_ein: null }),
    ]);
    expect(r?.domestic).toEqual({ amount: 300, count: 1 });
    expect(r?.foreign).toEqual({ amount: 200, count: 1 });
    expect(r?.totalAmount).toBe(500);
  });

  it('merges repeat recipients within the year and ranks them by amount', () => {
    const r = aggregateGrants([
      row({ recipient_name: 'Alpha Relief', recipient_ein: '11-1111111', amount: 100 }),
      row({ recipient_name: 'Alpha Relief', recipient_ein: '11-1111111', amount: 250 }),
      row({ recipient_name: 'Gamma Fund', recipient_ein: '22-2222222', amount: 900 }),
    ]);
    expect(r?.topRecipients.map((x) => [x.name, x.amount])).toEqual([
      ['Gamma Fund', 900],
      ['Alpha Relief', 350],
    ]);
  });

  it('caps the recipient list at ten', () => {
    const rows = Array.from({ length: 25 }, (_, i) =>
      row({ recipient_name: `Org ${i}`, recipient_ein: `9${i}-0000000`, amount: i + 1 }));
    expect(aggregateGrants(rows)?.topRecipients).toHaveLength(10);
  });

  it('totals by region, largest first', () => {
    const r = aggregateGrants([
      row({ region: 'Africa', amount: 10, recipient_ein: '33-3333333' }),
      row({ region: 'Africa', amount: 40, recipient_ein: '44-4444444' }),
      row({ region: 'Asia', amount: 70, recipient_ein: '55-5555555' }),
    ]);
    expect(r?.byRegion).toEqual([
      { region: 'Asia', amount: 70, count: 1 },
      { region: 'Africa', amount: 50, count: 2 },
    ]);
  });

  it('ignores rows with no usable amount', () => {
    const r = aggregateGrants([row({ amount: 100 }), row({ amount: null, recipient_ein: '66-6666666' })]);
    expect(r?.grantCount).toBe(1);
    expect(r?.totalAmount).toBe(100);
  });

  it('excludes anonymous rows from topRecipients but still counts them in totals', () => {
    const r = aggregateGrants([
      row({ recipient_name: 'Alpha Relief', recipient_ein: '11-1111111', amount: 100 }),
      row({ recipient_name: null, recipient_ein: null, amount: 900 }),
    ]);
    expect(r?.topRecipients.map((x) => x.name)).toEqual(['Alpha Relief']);
    expect(r?.grantCount).toBe(2);
    expect(r?.totalAmount).toBe(1000);
    expect(r?.unattributed).toEqual({ amount: 900, count: 1 });
  });

  it('never merges anonymous rows into a single fabricated recipient', () => {
    const r = aggregateGrants([
      row({ recipient_name: null, recipient_ein: null, amount: 500 }),
      row({ recipient_name: null, recipient_ein: null, amount: 700 }),
      row({ recipient_name: null, recipient_ein: null, amount: 300 }),
    ]);
    expect(r?.topRecipients).toEqual([]);
    expect(r?.unattributed).toEqual({ amount: 1500, count: 3 });
  });

  it('an all-anonymous charity yields an empty topRecipients and a non-zero unattributed', () => {
    const r = aggregateGrants([
      row({ recipient_name: null, recipient_ein: null, amount: 88000000 }),
    ]);
    expect(r?.topRecipients).toEqual([]);
    expect(r?.unattributed).toEqual({ amount: 88000000, count: 1 });
  });
});

describe('aggregateGrants against the real corpus', () => {
  const dir = path.resolve(__dirname, '../../../../data/charities');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));

  // Independently reproduces "usable amount in the most recent tax year"
  // from the raw JSON, so the reconciliation check below doesn't just
  // restate aggregateGrants's own internal bookkeeping back at itself.
  const identifiableTotalForMostRecentYear = (rows: Array<Record<string, unknown>>): number => {
    const years = rows
      .map((r) => r.tax_year)
      .filter((y): y is number => typeof y === 'number');
    const taxYear = years.length > 0 ? Math.max(...years) : null;
    const inYear = rows.filter((r) => (taxYear === null ? true : r.tax_year === taxYear));
    return inYear
      .filter((r) => typeof r.amount === 'number' && (r.recipient_name || r.recipient_ein))
      .reduce((sum, r) => sum + (r.amount as number), 0);
  };

  it('aggregates the 81 grantmaking charities without throwing or going negative', () => {
    let withGrants = 0;
    let fullyAnonymous = 0;
    for (const f of files) {
      const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
      const r = aggregateGrants(d.grantsData);
      if (r === null) continue;
      withGrants += 1;
      expect(r.totalAmount).toBeGreaterThanOrEqual(0);
      expect(r.topRecipients.length).toBeLessThanOrEqual(10);
      expect(r.domestic.amount + r.foreign.amount).toBe(r.totalAmount);
      if (r.topRecipients.length === 0) fullyAnonymous += 1;

      const identifiableTotal = identifiableTotalForMostRecentYear(d.grantsData);
      expect(r.unattributed.amount + identifiableTotal).toBe(r.totalAmount);
    }
    expect(withGrants).toBe(81);
    expect(fullyAnonymous).toBe(26);
  });
});

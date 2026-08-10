// src/components/gmg/adapters/typeContract.test.ts
// Guards the declared TypeScript contract against the shipped JSON. These
// assertions are about real data, not about types — but they fail for the
// same reason a wrong type does, and they run in CI.
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import type { KeyConcernType, KeyConcernSeverity } from '../../../../types';

// Compile-time guard. The runtime assertions in this file describe the shipped
// JSON; they cannot catch someone narrowing these unions back down while the
// data stays put. These types fail `tsc` if that happens.
type Assert<T extends true> = T;
type _SeverityCoversCorpus = Assert<
  'high' | 'medium' | 'low' extends KeyConcernSeverity ? true : false
>;
type _TypeCoversCorpus = Assert<
  | 'gik_inflation' | 'domestic_burn' | 'zakat_hoarding' | 'risk_deduction' | 'data_quality'
  | 'ceo_comp_excessive' | 'geographic_mismatch' | 'high_fundraising_ratio'
  | 'implausible_cpb' | 'revenue_expense_mismatch' extends KeyConcernType ? true : false
>;

const dir = path.resolve(__dirname, '../../../../data/charities');
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
const load = (f: string) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));

describe('the exported JSON matches what types.ts promises', () => {
  it('uses ten concern types, not the five the union declared', () => {
    const seen = new Set<string>();
    for (const f of files) for (const c of load(f).keyConcerns ?? []) seen.add(c.type);
    expect([...seen].sort()).toEqual([
      'ceo_comp_excessive', 'data_quality', 'domestic_burn', 'geographic_mismatch',
      'gik_inflation', 'high_fundraising_ratio', 'implausible_cpb',
      'revenue_expense_mismatch', 'risk_deduction', 'zakat_hoarding',
    ]);
  });

  it('uses only the three severities the union now declares', () => {
    const seen = new Set<string>();
    for (const f of files) for (const c of load(f).keyConcerns ?? []) seen.add(c.severity);
    expect([...seen].sort()).toEqual(['high', 'low', 'medium']);
  });

  it('puts non-numeric values in data_points, so the record cannot be number-only', () => {
    const kinds = new Set<string>();
    for (const f of files)
      for (const c of load(f).keyConcerns ?? [])
        for (const v of Object.values(c.data_points ?? {})) kinds.add(typeof v);
    expect(kinds.has('string')).toBe(true);
    expect([...kinds].every((k) => ['string', 'number', 'boolean'].includes(k))).toBe(true);
  });

  it('never ships rawData, so it cannot be a required field', () => {
    expect(files.filter((f) => 'rawData' in load(f))).toEqual([]);
  });

  it('names grant fields recipient_name / recipient_ein, not name / recipient', () => {
    const withGrants = files.map(load).find((d) => (d.grantsData ?? []).length > 0);
    expect(withGrants).toBeDefined();
    const keys = Object.keys(withGrants.grantsData[0]).sort();
    expect(keys).toEqual(
      ['amount', 'is_foreign', 'purpose', 'recipient_ein', 'recipient_name', 'region', 'tax_year'],
    );
  });
});

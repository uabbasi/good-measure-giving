import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { anchorConcerns } from './concerns';

describe('anchorConcerns', () => {
  it('anchors by data_points.field when present', () => {
    const r = anchorConcerns([
      { type: 'data_quality', severity: 'low', headline: 'Reserves mix two years',
        detail: 'd', data_points: { field: 'working_capital_months', fiscal_year: 2023 } },
    ]);
    expect(r.byAnchor.reserves).toHaveLength(1);
    expect(r.byAnchor.reserves[0].headline).toBe('Reserves mix two years');
    expect(r.byAnchor.trust).toHaveLength(0);
  });

  it('falls back to the concern type when no field anchor exists', () => {
    const r = anchorConcerns([
      { type: 'ceo_comp_excessive', severity: 'high', headline: 'CEO pay', detail: 'd', data_points: {} },
      { type: 'zakat_hoarding', severity: 'medium', headline: 'Hoarding', detail: 'd' },
      { type: 'risk_deduction', severity: 'medium', headline: 'Risk', detail: 'd' },
    ]);
    expect(r.byAnchor.governance).toHaveLength(1);
    expect(r.byAnchor.zakat).toHaveLength(1);
    expect(r.byAnchor.risks).toHaveLength(1);
  });

  it('routes an unrecognized type to trust rather than dropping it', () => {
    const r = anchorConcerns([{ type: 'brand_new_check', severity: 'low', headline: 'x', detail: 'd' }]);
    expect(r.byAnchor.trust).toHaveLength(1);
    expect(r.all).toHaveLength(1);
  });

  it('accepts low severity, which is the majority value in the corpus', () => {
    const r = anchorConcerns([{ type: 'data_quality', severity: 'low', headline: 'x', detail: 'd' }]);
    expect(r.all[0].severity).toBe('low');
  });

  it('sorts high before medium before low within an anchor', () => {
    const r = anchorConcerns([
      { type: 'gik_inflation', severity: 'low', headline: 'L', detail: '' },
      { type: 'gik_inflation', severity: 'high', headline: 'H', detail: '' },
      { type: 'gik_inflation', severity: 'medium', headline: 'M', detail: '' },
    ]);
    expect(r.byAnchor.money.map((c) => c.headline)).toEqual(['H', 'M', 'L']);
  });

  it('reports the highest severity present', () => {
    expect(anchorConcerns([{ type: 'x', severity: 'low', headline: 'a', detail: '' }]).highest).toBe('low');
    expect(anchorConcerns([
      { type: 'x', severity: 'low', headline: 'a', detail: '' },
      { type: 'y', severity: 'high', headline: 'b', detail: '' },
    ]).highest).toBe('high');
    expect(anchorConcerns([]).highest).toBeNull();
  });

  it('tolerates missing and malformed input', () => {
    expect(anchorConcerns(undefined).all).toEqual([]);
    expect(anchorConcerns(null).all).toEqual([]);
    expect(anchorConcerns([null, 'nope', 42] as unknown[]).all).toEqual([]);
  });
});

describe('anchorConcerns against the real corpus', () => {
  const dir = path.resolve(__dirname, '../../../../data/charities');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));

  it('anchors every concern in the fleet, dropping none', () => {
    let raw = 0;
    let anchored = 0;
    for (const f of files) {
      const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
      const list = Array.isArray(d.keyConcerns) ? d.keyConcerns : [];
      raw += list.length;
      const r = anchorConcerns(list);
      anchored += r.all.length;
      expect(Object.values(r.byAnchor).reduce((n, v) => n + v.length, 0)).toBe(r.all.length);
    }
    expect(raw).toBe(343);
    expect(anchored).toBe(343);
  });
});

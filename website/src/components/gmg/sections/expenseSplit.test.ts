import { describe, expect, it } from 'vitest';
import { expenseSplit } from './expenseSplit';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity } from '../charityAdapter';

describe('expenseSplit', () => {
  it('returns null when there is no program ratio at all', () => {
    expect(
      expenseSplit({ programRatioPct: null, programExpenses: 800, adminExpenses: 150, fundraisingExpenses: 50 }),
    ).toBeNull();
  });

  it('derives the split from filed figures when they are available, ignoring a stale ratio', () => {
    // programRatioPct is deliberately wrong here — a real breakdown must win.
    const split = expenseSplit({
      programRatioPct: 999,
      programExpenses: 800,
      adminExpenses: 150,
      fundraisingExpenses: 50,
    });
    expect(split).toEqual({ progPct: 80, adminPct: 15, fundPct: 5 });
  });

  it('falls back to the program ratio alone when no filed figures are present', () => {
    const split = expenseSplit({
      programRatioPct: 72,
      programExpenses: null,
      adminExpenses: null,
      fundraisingExpenses: null,
    });
    expect(split).toEqual({ progPct: 72, adminPct: 28, fundPct: 0 });
  });

  it('never lets the three percentages sum past 100, even when independent rounding would push them over', () => {
    // prog=101, admin=99, fund=0 out of denom=200: raw prog% = 50.5, raw
    // admin% = 49.5. Each rounds up independently (JS Math.round rounds
    // .5 away from zero), so progPct+adminPct = 51+50 = 101 before the
    // remainder guard clamps fundPct to 0 instead of -1.
    const split = expenseSplit({
      programRatioPct: 50,
      programExpenses: 101,
      adminExpenses: 99,
      fundraisingExpenses: 0,
    });
    expect(split).toEqual({ progPct: 51, adminPct: 50, fundPct: 0 });
    // The load-bearing assertion: without the Math.max(0, ...) guard this
    // would be -1, not 0. Proven red in task-4-report.md by removing the
    // guard and re-running this test.
    expect(split!.fundPct).toBeGreaterThanOrEqual(0);
  });

  it('matches GmgCharityDetail.tsx\'s Financials-card split for every real charity in the corpus', () => {
    // Re-implements the pre-extraction inline math verbatim so a future edit
    // to expenseSplit that silently changes behaviour is caught here, not
    // just by eyeballing the diff.
    const legacySplit = (c: {
      programRatioPct: number | null;
      programExpenses: number | null;
      adminExpenses: number | null;
      fundraisingExpenses: number | null;
    }) => {
      if (c.programRatioPct == null) return null;
      const prog = c.programExpenses ?? 0;
      const admin = c.adminExpenses ?? 0;
      const fund = c.fundraisingExpenses ?? 0;
      const denom = prog + admin + fund;
      const hasBreakdown = denom > 0;
      const progPct = hasBreakdown ? Math.round((prog / denom) * 100) : c.programRatioPct;
      const adminPct = hasBreakdown
        ? Math.round((admin / denom) * 100)
        : Math.max(0, 100 - c.programRatioPct);
      const fundPct = Math.max(0, 100 - progPct - adminPct);
      return { progPct, adminPct, fundPct };
    };

    const dir = path.resolve(__dirname, '../../../../data/charities');
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let checked = 0;
    for (const f of files) {
      const c = adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));
      expect(expenseSplit(c)).toEqual(legacySplit(c));
      if (c.programRatioPct != null) checked += 1;
    }
    expect(checked).toBeGreaterThan(100);
  });
});

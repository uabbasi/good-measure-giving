import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity } from './charityAdapter';

/**
 * A charity with no Form 990 on file must report unknown revenue, not $0.
 *
 * totalRevenue used to read `fin?.totalRevenue ?? rn?.financial_deep_dive?.annual_revenue`.
 * financial_deep_dive is LLM-written, and for charities with nothing filed it
 * says `annual_revenue: 0` — meaning "none recorded", not "raised nothing". The
 * fallback promoted that to the charity's revenue, so three live pages rendered
 * a flat "Revenue $0" in the detail header and a "Total revenue $0" row.
 *
 * Driven off the corpus rather than a pinned EIN, so it keeps testing the real
 * case as the roster changes instead of going vacuous when one charity is
 * backfilled.
 */
const dir = path.resolve(__dirname, '../../../data/charities');
const corpus = fs
  .readdirSync(dir)
  .filter((f) => f.endsWith('.json'))
  .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));

const unfiled = corpus.filter((c) => (c.financials ?? {}).totalRevenue == null);

describe('totalRevenue never comes from the narrative', () => {
  it('has charities with no filed revenue to test against', () => {
    expect(unfiled.length).toBeGreaterThan(0);
  });

  it('reports null, never 0, when nothing is filed', () => {
    for (const raw of unfiled) {
      expect(adaptCharity(raw).totalRevenue).toBeNull();
    }
  });

  it('still carries a filed figure through', () => {
    const filed = corpus.filter((c) => typeof (c.financials ?? {}).totalRevenue === 'number');
    expect(filed.length).toBeGreaterThan(0);

    for (const raw of filed.slice(0, 25)) {
      expect(adaptCharity(raw).totalRevenue).toBe(raw.financials.totalRevenue);
    }
  });
});

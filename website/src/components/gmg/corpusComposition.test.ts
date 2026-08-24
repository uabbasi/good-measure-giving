import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { adaptRow } from './charityAdapter';
import { buildCharitiesIndex } from '../../hooks/useCharities';

/**
 * The single owner of "what the published corpus currently looks like".
 *
 * Every other test in this directory asserts BEHAVIOUR and derives whatever
 * counts it needs from the data. This one file asserts the counts themselves,
 * as one snapshot, so a pipeline regeneration produces one reviewable diff
 * instead of red across sixteen files.
 *
 * When a regen legitimately shifts the corpus:
 *   npx vitest -u src/components/gmg/corpusComposition.test.ts
 * then READ the diff. Distribution shifts are the point of the snapshot --
 * "no-region tags 69 -> 45" is exactly the kind of movement that should get a
 * human glance before it ships.
 *
 * The roster line is the one to look hardest at. `total` moving down means
 * charities left the index, which is a pipeline failure until proven
 * otherwise: export.py's drop guard (find_undeclared_drops) should have
 * aborted the run before it could reach here.
 *
 * Known-open: `total` is 162 and should be 165-166. The 2026-08-16 v6.0.0
 * regen lost four to the judge gate before that guard existed -- two judge
 * false positives, one real misclassification, one hallucinated narrative.
 * Tracked in bd good-measure-giving-jy7 and good-measure-giving-akb.
 */

const index = JSON.parse(
  readFileSync(join(__dirname, '../../../data/charities.json'), 'utf-8'),
);
const rows = buildCharitiesIndex(index).charities.map(adaptRow);

const tally = (values: string[]): Record<string, number> => {
  const counts: Record<string, number> = {};
  for (const v of values) counts[v] = (counts[v] ?? 0) + 1;
  // Sorted so the snapshot diff stays stable when counts shift rank.
  return Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)));
};

describe('published corpus composition', () => {
  it('matches the reviewed snapshot', () => {
    expect({
      total: rows.length,
      muslimLed: rows.filter((r) => r.isMuslimLed).length,
      sizeBand: tally(rows.map((r) => r.sizeBand ?? 'unbanded')),
      causeKey: tally(rows.map((r) => r.causeKey)),
      regionTags: tally(rows.flatMap((r) => (r.regionTags.length ? r.regionTags : ['none']))),
      asnafTags: tally(rows.flatMap((r) => (r.asnafTags.length ? r.asnafTags : ['none']))),
    }).toMatchSnapshot();
  });

  /**
   * Invariants, not counts. These hold at any corpus size and must NOT be
   * folded into the snapshot above -- `vitest -u` would silently accept a
   * regression in any of them.
   */
  it('gives every charity a non-empty cause key', () => {
    expect(rows.every((r) => r.causeKey.length > 0)).toBe(true);
  });

  it('never lets a charity appear twice', () => {
    expect(new Set(rows.map((r) => r.ein)).size).toBe(rows.length);
  });

  it('keeps the human cause label distinct from the enum key', () => {
    // Guards the swap: `cause` is the display string, `causeKey` the enum.
    const humanitarian = rows.filter((r) => r.causeKey === 'HUMANITARIAN');
    expect(humanitarian.length).toBeGreaterThan(0);
    expect(humanitarian.every((r) => r.cause === 'Humanitarian Relief')).toBe(true);
  });

  it('publishes a non-empty corpus', () => {
    expect(rows.length).toBeGreaterThan(0);
  });
});

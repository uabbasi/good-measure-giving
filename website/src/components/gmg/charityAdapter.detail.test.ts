// Eight rich-narrative structures the adapter never read. Population is
// uneven across the corpus, so most assertions here are floors measured
// against the real export rather than exact counts — see charityAdapter.ts
// for the field-by-field guard comments.
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity } from './charityAdapter';

const dir = path.resolve(__dirname, '../../../data/charities');
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
const load = (f: string) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
const all = () => files.map((f) => adaptCharity(load(f)));
// The corpus size, never a literal. These assertions mean "every charity",
// and the count moves whenever a charity is published or withheld -- it went
// 166 -> 168 detail files when four blocked charities were re-judged and
// published. Composition itself is snapshotted in corpusComposition.test.ts.
const EVERY = files.length;

describe('adaptCharity detail structures', () => {
  it('exposes an evidence grade for every charity', () => {
    expect(all().filter((c) => c.evidence.grade !== null).length).toBe(EVERY);
  });

  it('exposes organizational capacity with independent per-field guards', () => {
    const a = all();
    expect(a.filter((c) => c.capacity.ceoCompensation !== null).length).toBeGreaterThanOrEqual(120);
    expect(a.filter((c) => c.capacity.boardSize !== null).length).toBeGreaterThanOrEqual(120);
    // Sparser fields must be null, never 0 or undefined, when absent.
    for (const c of a) {
      for (const v of [c.capacity.ceoCompensation, c.capacity.boardSize, c.capacity.employeesCount]) {
        expect(v === null || typeof v === 'number').toBe(true);
      }
    }
  });

  it('exposes peer comparison for every charity and peer medians where present', () => {
    const a = all();
    expect(a.filter((c) => c.peers.differentiator !== '').length).toBe(EVERY);
    expect(a.filter((c) => c.peers.programRatioMedian !== null).length).toBeGreaterThanOrEqual(130);
  });

  it('exposes BBB statuses always and a review link only when one exists', () => {
    const a = all();
    expect(a.filter((c) => c.bbb.summary !== '').length).toBe(EVERY);
    const linked = a.filter((c) => c.bbb.reviewUrl !== null);
    expect(linked.length).toBeGreaterThanOrEqual(40);
    expect(linked.length).toBeLessThan(EVERY);
  });

  it('splits case-against into a public summary and gated reasoning', () => {
    const a = all();
    expect(a.filter((c) => c.caseAgainst !== '').length).toBe(EVERY);
    expect(a.filter((c) => c.caseAgainstFactors.length > 0).length).toBeGreaterThanOrEqual(150);
  });

  it('exposes risks without inventing mitigation text, which the export never has', () => {
    const a = all();
    const withRisks = a.filter((c) => c.risks.length > 0);
    expect(withRisks.length).toBeGreaterThanOrEqual(110);
    for (const c of a) {
      for (const r of c.risks) {
        expect(r.description).not.toBe('');
        expect(r.severity).not.toBe('');
        expect('mitigation' in r).toBe(false);
      }
    }
  });

  it('exposes provenance entries and marks which can be linked', () => {
    const a = all();
    const total = a.reduce((n, c) => n + c.provenance.length, 0);
    expect(total).toBeGreaterThan(1500);
    const unlinkable = a.flatMap((c) => c.provenance).filter((p) => p.sourceUrl === null);
    // 96 entries across 21 files carry no source_url at all — they must survive
    // as label-only provenance rather than being dropped.
    expect(unlinkable.length).toBeGreaterThanOrEqual(90);
  });

  it('keeps root theoryOfChange separate from the impact-evidence one', () => {
    const a = all();
    const withRoot = a.filter((c) => c.theoryOfChange !== null);
    expect(withRoot.length).toBeGreaterThanOrEqual(110);
    // evidence.theoryOfChange is populated for every charity — if root were
    // ever aliased to it, this count would jump to match. A gap here is what proves the two
    // fields have genuinely different population, not just different names.
    expect(withRoot.length).toBeLessThan(EVERY);
    expect(a.filter((c) => c.evidence.theoryOfChange !== '').length).toBe(EVERY);
    // Population differing isn't enough on its own — assert the two fields
    // actually carry different text for at least one charity where both exist.
    const bothPresent = withRoot.filter((c) => c.evidence.theoryOfChange !== '');
    expect(bothPresent.some((c) => c.theoryOfChange !== c.evidence.theoryOfChange)).toBe(true);
  });

  // `ideal_donor_profile.not_ideal_for` is exported as a single prose string
  // (confirmed corpus-wide, never an array). A naive strList()
  // mapping silently discards it every time, which the "tolerates a charity
  // with no evaluation" test below would NOT catch, since it only checks the
  // empty case. This asserts the populated case actually populates.
  it('exposes not-ideal-for guidance where the export provides it', () => {
    const a = all();
    const withGuidance = a.filter((c) => c.notIdealFor.length > 0);
    expect(withGuidance.length).toBeGreaterThanOrEqual(120);
    for (const c of a) {
      expect(Array.isArray(c.notIdealFor)).toBe(true);
    }
  });

  it('tolerates a charity with no evaluation at all', () => {
    const c = adaptCharity({ ein: '00-0000000', name: 'Empty' });
    expect(c.evidence.grade).toBeNull();
    expect(c.capacity.ceoCompensation).toBeNull();
    expect(c.risks).toEqual([]);
    expect(c.provenance).toEqual([]);
    expect(c.notIdealFor).toEqual([]);
    expect(c.donorFitMatrix.zakatAsnafServed).toEqual([]);
    expect(c.noncashRatio).toBeNull();
    expect(c.cashAdjustedProgramRatio).toBeNull();
    expect(c.domesticBurnRate).toBeNull();
  });
});

describe('GIK/burn-rate signals (noncashRatio, cashAdjustedProgramRatio, domesticBurnRate)', () => {
  it('guards each field independently — a charity can have one signal without the others', () => {
    const c = adaptCharity(load('charity-04-2535767.json'));
    expect(c.noncashRatio).not.toBeNull();
    expect(c.cashAdjustedProgramRatio).toBeNull();
    expect(c.domesticBurnRate).toBeNull();
  });

  it('keeps a real 0 value rather than treating it as absent', () => {
    const c = adaptCharity(load('charity-13-1760110.json'));
    expect(c.noncashRatio).toBeCloseTo(0.159, 3);
    expect(c.cashAdjustedProgramRatio).toBeCloseTo(0.783, 3);
    expect(c.domesticBurnRate).toBe(0);
  });
});

describe('donorFitMatrix.zakatAsnafServed is a string list, never a scalar', () => {
  it('carries the export list entries through when non-empty', () => {
    // This field is LLM-written, so its surface form moves between regens: it
    // used to read 'fuqara (poor)' and now reads 'fuqara'. Pinning the exact
    // strings tested the generator's phrasing, not the adapter. What the
    // adapter owes callers is a list of non-empty strings, each naming a real
    // asnaf category in whatever spelling the narrative used.
    const asnafRoot = /^(fuqara|masakin|amil|muallaf|riqab|gharim|fisabilillah|ibn[_-]?sabil)/i;
    const served = adaptCharity(load('charity-04-3810161.json')).donorFitMatrix.zakatAsnafServed;

    expect(Array.isArray(served)).toBe(true);
    expect(served.length).toBeGreaterThan(0);
    for (const entry of served) {
      expect(typeof entry).toBe('string');
      expect(entry.trim()).not.toBe('');
      expect(entry).toMatch(asnafRoot);
    }
  });

  it('yields [] for a charity where the asnaf category legitimately does not apply', () => {
    const c = adaptCharity(load('charity-04-2535767.json'));
    expect(c.donorFitMatrix.zakatAsnafServed).toEqual([]);
  });

  it('cleans and drops non-string entries rather than passing the raw list through', () => {
    const c = adaptCharity({
      ein: '00-0000001',
      name: 'Malformed',
      amalEvaluation: {
        rich_narrative: {
          donor_fit_matrix: { zakat_asnaf_served: ['fuqara (poor)', 42, null, '  masakin (needy)  '] },
        },
      },
    });
    expect(c.donorFitMatrix.zakatAsnafServed).toEqual(['fuqara (poor)', 'masakin (needy)']);
  });
});

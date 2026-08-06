import { describe, expect, it } from 'vitest';
import { dataVintage } from './dataVintage';
import fs from 'node:fs';
import path from 'node:path';
import { adaptCharity } from '../charityAdapter';

describe('dataVintage', () => {
  it('is not dated when data_age_years is null', () => {
    expect(dataVintage({ dataAgeYears: null })).toEqual({ fyAge: null, fyDated: false });
  });

  it('is not dated below the 3-year threshold', () => {
    expect(dataVintage({ dataAgeYears: 2 })).toEqual({ fyAge: 2, fyDated: false });
  });

  it('is dated at exactly 3 years and beyond', () => {
    expect(dataVintage({ dataAgeYears: 3 })).toEqual({ fyAge: 3, fyDated: true });
    expect(dataVintage({ dataAgeYears: 5 })).toEqual({ fyAge: 5, fyDated: true });
  });

  it('matches GmgCharityDetail.tsx\'s pre-extraction inline computation for every real charity in the corpus', () => {
    // Re-implements the pre-extraction inline math verbatim so a future edit
    // to dataVintage that silently changes behaviour is caught here, not
    // just by eyeballing the diff.
    const legacyVintage = (c: { dataAgeYears: number | null }) => {
      const fyAge = c.dataAgeYears;
      const fyDated = fyAge != null && fyAge >= 3;
      return { fyAge, fyDated };
    };

    const dir = path.resolve(__dirname, '../../../../data/charities');
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));
    let checked = 0;
    for (const f of files) {
      const c = adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));
      expect(dataVintage(c)).toEqual(legacyVintage(c));
      checked += 1;
    }
    expect(checked).toBeGreaterThan(100);
  });
});

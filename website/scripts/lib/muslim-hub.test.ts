import { describe, it, expect } from 'vitest';
import { filterMuslimCharities, byAmalScoreDesc } from './muslim-hub';
import { type HubCharity } from './cause-seo';

const make = (over: Partial<HubCharity> & Pick<HubCharity, 'ein' | 'name'>): HubCharity => ({
  primaryCategory: null,
  amalScore: null,
  walletTag: null,
  isMuslimCharity: true,
  hideFromCurated: false,
  ...over,
});

describe('filterMuslimCharities', () => {
  const pool: HubCharity[] = [
    make({ ein: '1', name: 'Alpha', amalScore: 80, isMuslimCharity: true }),
    make({ ein: '2', name: 'Bravo', amalScore: 90, isMuslimCharity: true }),
    make({ ein: '3', name: 'Charlie', amalScore: 75, isMuslimCharity: false }),
    make({ ein: '4', name: 'Delta', amalScore: null, isMuslimCharity: true }),
    make({ ein: '5', name: 'Echo', amalScore: 95, isMuslimCharity: true, hideFromCurated: true }),
    make({ ein: '6', name: 'Foxtrot', amalScore: 70, isMuslimCharity: false }),
  ];

  it('keeps only isMuslimCharity && !hideFromCurated', () => {
    const result = filterMuslimCharities(pool);
    const eins = result.map((c) => c.ein);
    expect(eins).not.toContain('3'); // not muslim
    expect(eins).not.toContain('6'); // not muslim
    expect(eins).not.toContain('5'); // hidden
    expect(new Set(eins)).toEqual(new Set(['1', '2', '4']));
  });

  it('sorts by amalScore desc, nulls last', () => {
    const result = filterMuslimCharities(pool);
    expect(result.map((c) => c.ein)).toEqual(['2', '1', '4']);
  });

  it('treats missing isMuslimCharity as excluded', () => {
    const p: HubCharity[] = [
      { ein: 'x', name: 'X', primaryCategory: null, amalScore: 50, walletTag: null },
    ];
    expect(filterMuslimCharities(p)).toEqual([]);
  });
});

describe('byAmalScoreDesc', () => {
  it('orders higher score first', () => {
    const a = make({ ein: '1', name: 'A', amalScore: 60 });
    const b = make({ ein: '2', name: 'B', amalScore: 90 });
    expect(byAmalScoreDesc(a, b)).toBeGreaterThan(0);
    expect(byAmalScoreDesc(b, a)).toBeLessThan(0);
  });

  it('puts null scores last', () => {
    const scored = make({ ein: '1', name: 'A', amalScore: 10 });
    const nullScore = make({ ein: '2', name: 'B', amalScore: null });
    expect(byAmalScoreDesc(scored, nullScore)).toBeLessThan(0);
    expect(byAmalScoreDesc(nullScore, scored)).toBeGreaterThan(0);
  });

  it('breaks score ties by name ascending', () => {
    const zed = make({ ein: '1', name: 'Zed', amalScore: 80 });
    const amy = make({ ein: '2', name: 'Amy', amalScore: 80 });
    expect(byAmalScoreDesc(zed, amy)).toBeGreaterThan(0);
    expect(byAmalScoreDesc(amy, zed)).toBeLessThan(0);
  });

  it('breaks ties between two null scores by name ascending', () => {
    const zed = make({ ein: '1', name: 'Zed', amalScore: null });
    const amy = make({ ein: '2', name: 'Amy', amalScore: null });
    expect(byAmalScoreDesc(zed, amy)).toBeGreaterThan(0);
  });
});

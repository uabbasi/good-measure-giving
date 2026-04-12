import { describe, expect, it } from 'vitest';
import { getTopPicks } from './topPicks';
import type { CharitySummary } from '../hooks/useCharities';

function charity(overrides: Partial<CharitySummary> & { ein: string }): CharitySummary {
  return {
    id: overrides.ein,
    name: overrides.ein,
    tier: 'rich',
    mission: null,
    category: null,
    website: '',
    walletTag: 'ZAKAT-ELIGIBLE',
    confidenceTier: 'HIGH',
    impactTier: 'HIGH',
    zakatClassification: null,
    isMuslimCharity: true,
    programExpenseRatio: null,
    totalRevenue: null,
    lastUpdated: '',
    amalScore: 85,
    primaryCategory: 'HUMANITARIAN',
    ...overrides,
  };
}

describe('getTopPicks', () => {
  it('groups charities by primaryCategory', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 90 }),
      charity({ ein: '2', primaryCategory: 'EDUCATION_INTERNATIONAL', amalScore: 88 }),
      charity({ ein: '3', primaryCategory: 'HUMANITARIAN', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities);
    expect(groups).toHaveLength(2);
    expect(groups[0].category).toBe('HUMANITARIAN');
    expect(groups[0].picks).toHaveLength(2);
    expect(groups[1].category).toBe('EDUCATION_INTERNATIONAL');
    expect(groups[1].picks).toHaveLength(1);
  });

  it('sorts categories by top score descending', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'BASIC_NEEDS', amalScore: 80 }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 95 }),
    ];
    const groups = getTopPicks(charities);
    expect(groups[0].category).toBe('HUMANITARIAN');
    expect(groups[1].category).toBe('BASIC_NEEDS');
  });

  it('sorts picks within category by score descending', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 80 }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 95 }),
      charity({ ein: '3', primaryCategory: 'HUMANITARIAN', amalScore: 88 }),
    ];
    const groups = getTopPicks(charities, { perCategory: 3 });
    expect(groups[0].picks.map(c => c.amalScore)).toEqual([95, 88, 80]);
  });

  it('respects perCategory limit', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 95 }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 90 }),
      charity({ ein: '3', primaryCategory: 'HUMANITARIAN', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities, { perCategory: 1 });
    expect(groups[0].picks).toHaveLength(1);
    expect(groups[0].picks[0].amalScore).toBe(95);
  });

  it('respects maxCategories limit', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 95 }),
      charity({ ein: '2', primaryCategory: 'EDUCATION_INTERNATIONAL', amalScore: 90 }),
      charity({ ein: '3', primaryCategory: 'BASIC_NEEDS', amalScore: 85 }),
      charity({ ein: '4', primaryCategory: 'MEDICAL_HEALTH', amalScore: 80 }),
      charity({ ein: '5', primaryCategory: 'CIVIL_RIGHTS_LEGAL', amalScore: 75 }),
    ];
    const groups = getTopPicks(charities, { maxCategories: 3 });
    expect(groups).toHaveLength(3);
  });

  it('filters by minScore', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 60 }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 80 }),
    ];
    const groups = getTopPicks(charities, { minScore: 70 });
    expect(groups[0].picks).toHaveLength(1);
    expect(groups[0].picks[0].amalScore).toBe(80);
  });

  it('excludes charities with no amalScore', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: null }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities);
    expect(groups[0].picks).toHaveLength(1);
  });

  it('excludes INSUFFICIENT-DATA charities', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', walletTag: 'INSUFFICIENT-DATA', amalScore: 90 }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities);
    expect(groups[0].picks).toHaveLength(1);
  });

  it('excludes hideFromCurated charities', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', hideFromCurated: true, amalScore: 90 }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities);
    expect(groups[0].picks).toHaveLength(1);
  });

  it('excludes specified EINs', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 95 }),
      charity({ ein: '2', primaryCategory: 'HUMANITARIAN', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities, { excludeEins: new Set(['1']) });
    expect(groups[0].picks).toHaveLength(1);
    expect(groups[0].picks[0].ein).toBe('2');
  });

  it('returns empty array when no charities qualify', () => {
    const groups = getTopPicks([]);
    expect(groups).toEqual([]);
  });

  it('provides human-readable labels', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'CIVIL_RIGHTS_LEGAL', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities);
    expect(groups[0].label).toBe('Civil Rights & Legal');
  });

  it('falls back to title-cased category name for unknown categories', () => {
    const charities = [
      charity({ ein: '1', primaryCategory: 'NEW_CATEGORY', amalScore: 85 }),
    ];
    const groups = getTopPicks(charities);
    expect(groups[0].label).toBe('New Category');
  });
});

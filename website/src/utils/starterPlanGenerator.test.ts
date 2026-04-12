import { describe, expect, it } from 'vitest';
import { generateStarterPlan, DEFAULT_CATEGORIES, type StarterCategory } from './starterPlanGenerator';
import type { CharitySummary } from '../hooks/useCharities';

function charity(overrides: Partial<CharitySummary> & { ein: string }): CharitySummary {
  return {
    id: overrides.ein,
    name: overrides.name ?? overrides.ein,
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

const charities = [
  charity({ ein: '1', name: 'Global Org A', primaryCategory: 'HUMANITARIAN', amalScore: 95 }),
  charity({ ein: '2', name: 'Global Org B', primaryCategory: 'HUMANITARIAN', amalScore: 90 }),
  charity({ ein: '3', name: 'Domestic Org', primaryCategory: 'CIVIL_RIGHTS_LEGAL', amalScore: 88 }),
  charity({ ein: '4', name: 'Edu Org', primaryCategory: 'EDUCATION_INTERNATIONAL', amalScore: 85 }),
  charity({ ein: '5', name: 'Community Org', primaryCategory: 'RELIGIOUS_OUTREACH', amalScore: 80 }),
  charity({ ein: '6', name: 'Extra Global', primaryCategory: 'BASIC_NEEDS', amalScore: 92 }),
];

describe('generateStarterPlan', () => {
  it('allocates across default categories', () => {
    const groups = generateStarterPlan(10000, charities);
    expect(groups).toHaveLength(4);
    expect(groups[0].category.id).toBe('global');
    expect(groups[1].category.id).toBe('domestic');
    expect(groups[2].category.id).toBe('education');
    expect(groups[3].category.id).toBe('community');
  });

  it('amounts sum exactly to target', () => {
    const groups = generateStarterPlan(10000, charities);
    const total = groups.reduce((s, g) => s + g.subtotal, 0);
    expect(total).toBe(10000);
  });

  it('amounts sum to target even with odd numbers', () => {
    const groups = generateStarterPlan(7777, charities);
    const total = groups.reduce((s, g) =>
      s + g.allocations.reduce((s2, a) => s2 + a.amount, 0), 0);
    expect(total).toBe(7777);
  });

  it('respects category percentages approximately', () => {
    const groups = generateStarterPlan(10000, charities);
    // Global is 40% = ~4000
    expect(groups[0].subtotal).toBeGreaterThanOrEqual(3900);
    expect(groups[0].subtotal).toBeLessThanOrEqual(4100);
  });

  it('allocates proportionally by score within category', () => {
    const groups = generateStarterPlan(10000, charities);
    // Global has two: score 95 and 92 (HUMANITARIAN + BASIC_NEEDS)
    const globalAllocs = groups[0].allocations;
    expect(globalAllocs).toHaveLength(2);
    // Higher score gets more
    expect(globalAllocs[0].amount).toBeGreaterThanOrEqual(globalAllocs[1].amount);
  });

  it('returns empty groups for unmatched categories', () => {
    const onlyGlobal = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 90 }),
    ];
    const groups = generateStarterPlan(10000, onlyGlobal);
    const emptyGroups = groups.filter(g => g.allocations.length === 0);
    expect(emptyGroups.length).toBeGreaterThan(0);
  });

  it('returns empty array when target is zero', () => {
    expect(generateStarterPlan(0, charities)).toEqual([]);
  });

  it('returns empty array when target is negative', () => {
    expect(generateStarterPlan(-100, charities)).toEqual([]);
  });

  it('filters by minScore', () => {
    const lowScoreCharities = [
      charity({ ein: '1', primaryCategory: 'HUMANITARIAN', amalScore: 60 }),
    ];
    const groups = generateStarterPlan(10000, lowScoreCharities);
    expect(groups[0].allocations).toHaveLength(0);
  });

  it('excludes specified EINs', () => {
    const groups = generateStarterPlan(10000, charities, DEFAULT_CATEGORIES, {
      excludeEins: new Set(['1']),
    });
    const allEins = groups.flatMap(g => g.allocations.map(a => a.ein));
    expect(allEins).not.toContain('1');
  });

  it('respects perCategory limit', () => {
    const groups = generateStarterPlan(10000, charities, DEFAULT_CATEGORIES, {
      perCategory: 1,
    });
    for (const group of groups) {
      expect(group.allocations.length).toBeLessThanOrEqual(1);
    }
  });

  it('works with custom categories', () => {
    const custom: StarterCategory[] = [
      { id: 'all', name: 'Everything', percentage: 100, color: '#000', matchCategories: ['HUMANITARIAN'] },
    ];
    const groups = generateStarterPlan(5000, charities, custom);
    expect(groups).toHaveLength(1);
    expect(groups[0].subtotal).toBe(5000);
  });

  it('all amounts are positive whole numbers', () => {
    const groups = generateStarterPlan(10000, charities);
    for (const group of groups) {
      for (const alloc of group.allocations) {
        expect(alloc.amount).toBeGreaterThan(0);
        expect(Number.isInteger(alloc.amount)).toBe(true);
      }
    }
  });
});

import type { CharitySummary } from '../hooks/useCharities';

export interface StarterCategory {
  id: string;
  name: string;
  percentage: number;
  color: string;
  /** primaryCategory values that match this bucket */
  matchCategories: string[];
}

export interface StarterAllocation {
  ein: string;
  name: string;
  amount: number;
}

export interface StarterGroup {
  category: StarterCategory;
  allocations: StarterAllocation[];
  subtotal: number;
}

export const DEFAULT_CATEGORIES: StarterCategory[] = [
  {
    id: 'global',
    name: 'Global Relief',
    percentage: 40,
    color: '#5ba88a',
    matchCategories: ['HUMANITARIAN', 'BASIC_NEEDS'],
  },
  {
    id: 'domestic',
    name: 'Domestic Impact',
    percentage: 20,
    color: '#5b8fb8',
    matchCategories: ['CIVIL_RIGHTS_LEGAL', 'SOCIAL_SERVICES', 'MEDICAL_HEALTH', 'WOMENS_SERVICES'],
  },
  {
    id: 'education',
    name: 'Education',
    percentage: 20,
    color: '#8b7cb8',
    matchCategories: ['EDUCATION_INTERNATIONAL', 'EDUCATION_K12_RELIGIOUS', 'EDUCATION_HIGHER_RELIGIOUS', 'RESEARCH_POLICY'],
  },
  {
    id: 'community',
    name: 'Community & Faith',
    percentage: 20,
    color: '#7a9e6e',
    matchCategories: ['RELIGIOUS_CONGREGATION', 'RELIGIOUS_OUTREACH', 'PHILANTHROPY_GRANTMAKING', 'ADVOCACY_CIVIC'],
  },
];

interface GenerateOptions {
  /** Max charities per category (default 2) */
  perCategory?: number;
  /** Minimum amalScore to include (default 70) */
  minScore?: number;
  /** EINs already in the user's plan to exclude */
  excludeEins?: Set<string>;
}

/**
 * Generate a starter giving plan by allocating a target amount
 * across cause-area categories proportional to charity scores.
 *
 * Amounts are rounded to whole dollars. Rounding remainder is
 * distributed to the largest category to ensure exact sum.
 */
export function generateStarterPlan(
  target: number,
  charities: CharitySummary[],
  categories: StarterCategory[] = DEFAULT_CATEGORIES,
  options: GenerateOptions = {},
): StarterGroup[] {
  const { perCategory = 2, minScore = 70, excludeEins } = options;

  if (target <= 0) return [];

  // Filter to scored, visible charities
  const eligible = charities.filter(c =>
    c.amalScore != null &&
    c.amalScore >= minScore &&
    c.walletTag !== 'INSUFFICIENT-DATA' &&
    !c.hideFromCurated &&
    c.primaryCategory &&
    (!excludeEins || !excludeEins.has(c.ein))
  );

  // Build index by primaryCategory
  const byCategory = new Map<string, CharitySummary[]>();
  for (const c of eligible) {
    const list = byCategory.get(c.primaryCategory!) ?? [];
    list.push(c);
    byCategory.set(c.primaryCategory!, list);
  }

  // Allocate each category
  const groups: StarterGroup[] = [];
  let allocatedTotal = 0;

  for (const cat of categories) {
    const catBudget = Math.round(target * cat.percentage / 100);
    const matched: CharitySummary[] = [];

    for (const pc of cat.matchCategories) {
      const list = byCategory.get(pc);
      if (list) matched.push(...list);
    }

    // Sort by score desc, take top N
    matched.sort((a, b) => (b.amalScore ?? 0) - (a.amalScore ?? 0));
    const picks = matched.slice(0, perCategory);

    if (picks.length === 0) {
      groups.push({ category: cat, allocations: [], subtotal: 0 });
      continue;
    }

    // Allocate proportionally by score within category
    const totalScore = picks.reduce((s, c) => s + (c.amalScore ?? 0), 0);
    const allocations: StarterAllocation[] = [];
    let catAllocated = 0;

    for (let i = 0; i < picks.length; i++) {
      const c = picks[i];
      const share = totalScore > 0 ? (c.amalScore ?? 0) / totalScore : 1 / picks.length;
      const isLast = i === picks.length - 1;
      // Last charity gets remainder to avoid rounding drift
      const amount = isLast ? catBudget - catAllocated : Math.round(catBudget * share);

      allocations.push({ ein: c.ein, name: c.name, amount });
      catAllocated += amount;
    }

    groups.push({ category: cat, allocations, subtotal: catAllocated });
    allocatedTotal += catAllocated;
  }

  // Fix any rounding gap between allocated total and target
  // Add/subtract from the largest non-empty group
  const gap = target - allocatedTotal;
  if (gap !== 0) {
    const largest = groups
      .filter(g => g.allocations.length > 0)
      .sort((a, b) => b.subtotal - a.subtotal)[0];
    if (largest) {
      const lastAlloc = largest.allocations[largest.allocations.length - 1];
      lastAlloc.amount += gap;
      largest.subtotal += gap;
    }
  }

  return groups;
}

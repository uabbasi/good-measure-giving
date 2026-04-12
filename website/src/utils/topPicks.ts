import type { CharitySummary } from '../hooks/useCharities';

/** Human-readable labels for primaryCategory values. */
const CATEGORY_LABELS: Record<string, string> = {
  HUMANITARIAN: 'Humanitarian',
  CIVIL_RIGHTS_LEGAL: 'Civil Rights & Legal',
  MEDICAL_HEALTH: 'Health & Medicine',
  EDUCATION_INTERNATIONAL: 'Education (International)',
  EDUCATION_K12_RELIGIOUS: 'Education (K-12)',
  EDUCATION_HIGHER_RELIGIOUS: 'Higher Education',
  ENVIRONMENT_CLIMATE: 'Environment & Climate',
  PHILANTHROPY_GRANTMAKING: 'Grantmaking',
  RELIGIOUS_CONGREGATION: 'Religious Community',
  RELIGIOUS_OUTREACH: 'Religious Outreach',
  BASIC_NEEDS: 'Basic Needs',
  SOCIAL_SERVICES: 'Social Services',
  RESEARCH_POLICY: 'Research & Policy',
  WOMENS_SERVICES: "Women's Services",
  ADVOCACY_CIVIC: 'Advocacy & Civic',
  MEDIA_JOURNALISM: 'Media & Journalism',
};

export interface TopPickGroup {
  category: string;
  label: string;
  picks: CharitySummary[];
}

export interface TopPicksOptions {
  /** Max charities per category (default 2) */
  perCategory?: number;
  /** Max categories to show (default 4) */
  maxCategories?: number;
  /** Minimum amalScore to include (default 70) */
  minScore?: number;
  /** EINs to exclude (e.g., already bookmarked) */
  excludeEins?: Set<string>;
}

/**
 * Select top-scoring charities grouped by cause area.
 * Returns categories ordered by their best charity's score.
 */
export function getTopPicks(
  charities: CharitySummary[],
  options: TopPicksOptions = {},
): TopPickGroup[] {
  const {
    perCategory = 2,
    maxCategories = 4,
    minScore = 70,
    excludeEins,
  } = options;

  // Filter to evaluated, scored, visible charities
  const eligible = charities.filter(c =>
    c.amalScore != null &&
    c.amalScore >= minScore &&
    c.walletTag !== 'INSUFFICIENT-DATA' &&
    !c.hideFromCurated &&
    c.primaryCategory &&
    (!excludeEins || !excludeEins.has(c.ein))
  );

  // Group by primaryCategory
  const byCategory = new Map<string, CharitySummary[]>();
  for (const c of eligible) {
    const cat = c.primaryCategory!;
    const list = byCategory.get(cat) ?? [];
    list.push(c);
    byCategory.set(cat, list);
  }

  // Sort within each category by score desc, take top N
  const groups: TopPickGroup[] = [];
  for (const [category, list] of byCategory) {
    list.sort((a, b) => (b.amalScore ?? 0) - (a.amalScore ?? 0));
    groups.push({
      category,
      label: CATEGORY_LABELS[category] ?? category.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()),
      picks: list.slice(0, perCategory),
    });
  }

  // Sort categories by their top charity's score desc
  groups.sort((a, b) => (b.picks[0]?.amalScore ?? 0) - (a.picks[0]?.amalScore ?? 0));

  return groups.slice(0, maxCategories);
}

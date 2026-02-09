/**
 * Cause category utilities for the Browse page.
 *
 * Normalizes the messy cause_area values from evaluations into
 * user-friendly categories for filtering.
 *
 * Raw cause_area values (from rich_narrative.donor_fit_matrix.cause_area):
 * - HUMANITARIAN (42 charities)
 * - RELIGIOUS_CULTURAL (25)
 * - ADVOCACY (20)
 * - GLOBAL_HEALTH (10)
 * - EDUCATION (10)
 * - DOMESTIC_POVERTY (8)
 * - Plus various edge cases: EXTREME_POVERTY, EDUCATION_GLOBAL, etc.
 */

/**
 * Normalized cause categories displayed to users.
 * Maps multiple raw cause_area values to cleaner labels.
 */
export type CauseCategory =
  | 'emergency-relief'
  | 'education'
  | 'health'
  | 'muslim-community'
  | 'advocacy'
  | 'domestic-poverty';

export interface CauseCategoryInfo {
  id: CauseCategory;
  label: string;
  description: string;
  /** Raw cause_area values that map to this category */
  rawValues: string[];
}

/**
 * Category definitions with their mappings from raw cause_area values.
 * Order determines display order in the filter chips.
 */
export const CAUSE_CATEGORIES: CauseCategoryInfo[] = [
  {
    id: 'emergency-relief',
    label: 'Emergency Relief',
    description: 'Humanitarian aid and disaster response',
    rawValues: ['HUMANITARIAN', 'EXTREME_POVERTY', 'HUMANITARIAN & EDUCATION'],
  },
  {
    id: 'education',
    label: 'Education',
    description: 'Schools, scholarships, and learning programs',
    rawValues: [
      'EDUCATION',
      'EDUCATION_GLOBAL',
      'EDUCATION & ADVOCACY',
      'EDUCATION / SCHOLARSHIP',
      'RELIGIOUS_EDUCATION',
      'CRIMINAL JUSTICE / EDUCATION',
    ],
  },
  {
    id: 'health',
    label: 'Health',
    description: 'Medical care and health initiatives',
    rawValues: ['GLOBAL_HEALTH', 'HEALTH_ADVOCACY', 'MENTAL HEALTH', 'DISABILITY SERVICES'],
  },
  {
    id: 'muslim-community',
    label: 'Muslim Community',
    description: 'Mosques, religious services, and cultural programs',
    rawValues: ['RELIGIOUS_CULTURAL'],
  },
  {
    id: 'advocacy',
    label: 'Advocacy & Policy',
    description: 'Civil rights, policy change, and civic engagement',
    rawValues: [
      'ADVOCACY',
      'CIVIC_ADVOCACY',
      'CIVIC ENGAGEMENT',
      'CIVIL RIGHTS',
      'CRIMINAL_JUSTICE',
      'INVESTIGATIVE JOURNALISM',
    ],
  },
  {
    id: 'domestic-poverty',
    label: 'Domestic Poverty',
    description: 'Local community support and social services',
    rawValues: ['DOMESTIC_POVERTY', 'COMMUNITY_SUPPORT', 'COMMUNITY SERVICES', 'SOCIAL SERVICES', 'ENVIRONMENT'],
  },
];

// Build reverse lookup map: raw cause_area -> normalized category
const RAW_TO_CATEGORY_MAP = new Map<string, CauseCategory>();
for (const category of CAUSE_CATEGORIES) {
  for (const rawValue of category.rawValues) {
    RAW_TO_CATEGORY_MAP.set(rawValue.toUpperCase(), category.id);
  }
}

/**
 * Normalize a raw cause_area value to a CauseCategory.
 * Returns null if the value doesn't map to any category.
 */
export function normalizeCauseArea(rawCauseArea: string | null | undefined): CauseCategory | null {
  if (!rawCauseArea) return null;
  return RAW_TO_CATEGORY_MAP.get(rawCauseArea.toUpperCase()) ?? null;
}

/**
 * Get the CauseCategoryInfo for a normalized category ID.
 */
export function getCategoryInfo(categoryId: CauseCategory): CauseCategoryInfo | undefined {
  return CAUSE_CATEGORIES.find((c) => c.id === categoryId);
}

/**
 * Get the display label for a cause category.
 */
export function getCategoryLabel(categoryId: CauseCategory): string {
  return getCategoryInfo(categoryId)?.label ?? categoryId;
}

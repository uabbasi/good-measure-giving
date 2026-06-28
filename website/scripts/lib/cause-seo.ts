/**
 * Cause-area hub helpers. Pure functions.
 * Maps MECE categories (HUMANITARIAN, CIVIL_RIGHTS_LEGAL, ...) to
 * URL slugs and back.
 */

const CATEGORY_TO_SLUG: Record<string, string> = {
  HUMANITARIAN: 'humanitarian',
  RELIGIOUS_CONGREGATION: 'religious-congregation',
  CIVIL_RIGHTS_LEGAL: 'civil-rights-legal',
  MEDICAL_HEALTH: 'medical-health',
  PHILANTHROPY_GRANTMAKING: 'philanthropy-grantmaking',
  EDUCATION_INTERNATIONAL: 'education-international',
  RESEARCH_POLICY: 'research-policy',
  RELIGIOUS_OUTREACH: 'religious-outreach',
  BASIC_NEEDS: 'basic-needs',
  EDUCATION_HIGHER_RELIGIOUS: 'education-higher-religious',
  EDUCATION_K12_RELIGIOUS: 'education-k12-religious',
  ENVIRONMENT_CLIMATE: 'environment-climate',
  SOCIAL_SERVICES: 'social-services',
  WOMENS_SERVICES: 'womens-services',
  ADVOCACY_CIVIC: 'advocacy-civic',
  MEDIA_JOURNALISM: 'media-journalism',
};

const SLUG_TO_CATEGORY: Record<string, string> = Object.fromEntries(
  Object.entries(CATEGORY_TO_SLUG).map(([cat, slug]) => [slug, cat])
);

export const CAUSE_SLUGS: readonly string[] = Object.values(CATEGORY_TO_SLUG);

export function categoryToSlug(category: string | null): string | null {
  if (!category) return null;
  return CATEGORY_TO_SLUG[category] ?? null;
}

export function slugToCategory(slug: string): string | null {
  return SLUG_TO_CATEGORY[slug] ?? null;
}

export interface HubCharity {
  ein: string;
  name: string;
  primaryCategory: string | null;
  amalScore: number | null;
  walletTag: string | null;
  /** Cross-cutting flag: org self-identifies / is classified as a Muslim charity. */
  isMuslimCharity?: boolean;
  /** Hidden from curated listings (still reachable by direct URL). */
  hideFromCurated?: boolean | null;
}

/**
 * Shared sort comparator: amalScore descending, nulls last, name ascending as tiebreak.
 * Used by both the cause hubs and the Muslim-charities hub so ranking is consistent.
 */
export function byAmalScoreDesc(a: HubCharity, b: HubCharity): number {
  if (a.amalScore == null && b.amalScore == null) return a.name.localeCompare(b.name);
  if (a.amalScore == null) return 1;
  if (b.amalScore == null) return -1;
  if (b.amalScore !== a.amalScore) return b.amalScore - a.amalScore;
  return a.name.localeCompare(b.name);
}

export function filterCharitiesByCategory(pool: HubCharity[], category: string): HubCharity[] {
  return pool
    .filter((c) => c.primaryCategory === category)
    .sort(byAmalScoreDesc);
}

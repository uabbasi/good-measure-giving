/**
 * Shared tag constants and utilities for the giving system.
 *
 * Extracted from UnifiedAllocationView to allow reuse in
 * BookmarkAutoCategorize and other modules.
 */

export const TAGS = {
  geography: [
    { id: 'palestine', label: 'Palestine' },
    { id: 'pakistan', label: 'Pakistan' },
    { id: 'afghanistan', label: 'Afghanistan' },
    { id: 'bangladesh', label: 'Bangladesh' },
    { id: 'india', label: 'India' },
    { id: 'kashmir', label: 'Kashmir' },
    { id: 'somalia', label: 'Somalia' },
    { id: 'sudan', label: 'Sudan' },
    { id: 'syria', label: 'Syria' },
    { id: 'yemen', label: 'Yemen' },
    { id: 'jordan', label: 'Jordan' },
    { id: 'lebanon', label: 'Lebanon' },
    { id: 'egypt', label: 'Egypt' },
    { id: 'indonesia', label: 'Indonesia' },
    { id: 'myanmar', label: 'Myanmar' },
    { id: 'kenya', label: 'Kenya' },
    { id: 'nigeria', label: 'Nigeria' },
    { id: 'ethiopia', label: 'Ethiopia' },
    { id: 'haiti', label: 'Haiti' },
    { id: 'usa', label: 'USA' },
    { id: 'international', label: 'International' },
    { id: 'conflict-zone', label: 'Conflict Zones' },
  ],
  cause: [
    { id: 'emergency-response', label: 'Emergency' },
    { id: 'direct-relief', label: 'Direct Relief' },
    { id: 'food', label: 'Food' },
    { id: 'water-sanitation', label: 'Water' },
    { id: 'medical', label: 'Medical' },
    { id: 'shelter', label: 'Shelter' },
    { id: 'clothing', label: 'Clothing' },
    { id: 'educational', label: 'Education' },
    { id: 'vocational', label: 'Vocational' },
    { id: 'psychosocial', label: 'Mental Health' },
    { id: 'legal-aid', label: 'Legal Aid' },
    { id: 'advocacy', label: 'Advocacy' },
    { id: 'research', label: 'Research' },
    { id: 'grantmaking', label: 'Grantmaking' },
    { id: 'capacity-building', label: 'Capacity Building' },
    { id: 'long-term-development', label: 'Development' },
    { id: 'systemic-change', label: 'Systemic Change' },
    { id: 'faith-based', label: 'Faith-Based' },
  ],
  population: [
    { id: 'refugees', label: 'Refugees' },
    { id: 'orphans', label: 'Orphans' },
    { id: 'women', label: 'Women' },
    { id: 'youth', label: 'Youth' },
    { id: 'disabled', label: 'Disabled' },
    { id: 'low-income', label: 'Low Income' },
    { id: 'converts', label: 'Converts' },
    { id: 'fuqara', label: 'Fuqara' },
    { id: 'masakin', label: 'Masakin' },
    { id: 'fisabilillah', label: 'Fi Sabilillah' },
  ],
};

export const ALL_TAGS = [...TAGS.geography, ...TAGS.cause, ...TAGS.population];

export const GEO_TAG_IDS = new Set(TAGS.geography.map(t => t.id));
export const CAUSE_TAG_IDS = new Set(TAGS.cause.map(t => t.id));

/** Pick the best tag for bucket creation: geography > cause > population.
 *  Skips generic tags like 'international' in favor of specific ones. */
export function pickBestTag(tags: string[]): string | null {
  // Prefer specific geography (not "international" or "conflict-zone")
  const specificGeo = tags.find(t => GEO_TAG_IDS.has(t) && t !== 'international' && t !== 'conflict-zone');
  if (specificGeo) return specificGeo;
  // Then any cause tag
  const cause = tags.find(t => CAUSE_TAG_IDS.has(t));
  if (cause) return cause;
  // Fallback to any known tag
  const known = tags.find(t => ALL_TAGS.some(at => at.id === t));
  return known || tags[0] || null;
}

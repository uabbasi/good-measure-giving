/**
 * Best-Muslim-charities hub helpers. Pure functions.
 * Filters the cross-cutting `isMuslimCharity` flag (not a single primaryCategory)
 * and ranks by GMG score.
 */

import { byAmalScoreDesc, isCuratedMuslimCharity, type HubCharity } from './cause-seo';

export { byAmalScoreDesc };
export type { HubCharity };

/**
 * Keep only Muslim charities that aren't hidden from curated listings,
 * sorted by GMG score descending (nulls last, name tiebreak).
 */
export function filterMuslimCharities(pool: HubCharity[]): HubCharity[] {
  return pool.filter(isCuratedMuslimCharity).sort(byAmalScoreDesc);
}

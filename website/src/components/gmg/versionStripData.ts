// Pure helpers for the site-wide version strip. Kept JSX-free so the count /
// date math is unit-testable in isolation from the React component.

// Minimal shape the strip needs from each charity summary. A subset of
// CharitySummary (useCharities) so this can be fed the loaded index directly.
export interface VersionStripCharity {
  amalScore: number | null;
  walletTag: string;
  hideFromCurated?: boolean;
  lastUpdated?: string | null;
}

export interface VersionStripStats {
  /** Charities with a published GMG score that aren't hidden from curation. */
  ratedCount: number;
  /** Charities the wallet routing marks zakat-eligible. */
  zakatCount: number;
  /** Max `lastUpdated` across charities, formatted YYYY-MM-DD (null if none). */
  updated: string | null;
  /** YYYY.MM release stamp derived from the same max date (null if none). */
  release: string | null;
}

/**
 * Derive the strip's left-cluster numbers from the loaded charity index.
 * Returns null counts/dates only when no data is available (e.g. during SSR of a
 * route where the index wasn't seeded) — the component renders placeholders then
 * and the real numbers hydrate client-side.
 */
export function computeVersionStripStats(
  charities: readonly VersionStripCharity[] | null | undefined,
): VersionStripStats {
  const list = charities ?? [];

  let ratedCount = 0;
  let zakatCount = 0;
  let maxDate: string | null = null;

  for (const c of list) {
    if (c.amalScore != null && !c.hideFromCurated) ratedCount++;
    if (c.walletTag === 'ZAKAT-ELIGIBLE') zakatCount++;

    // lastUpdated is 'YYYY-MM-DD HH:MM:SS'; lexicographic max == chronological max.
    const lu = c.lastUpdated;
    if (lu && (maxDate == null || lu > maxDate)) maxDate = lu;
  }

  const updated = maxDate ? maxDate.slice(0, 10) : null;
  // RELEASE 'YYYY.MM' from the same max date (e.g. 2026-06-27 -> 2026.06).
  const release = updated ? `${updated.slice(0, 4)}.${updated.slice(5, 7)}` : null;

  return { ratedCount, zakatCount, updated, release };
}

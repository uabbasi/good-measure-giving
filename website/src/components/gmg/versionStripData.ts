// Pure helpers for the site-wide version strip. Kept JSX-free so the count /
// date / edition math is unit-testable in isolation from the React component.

// Minimal shape the strip needs from each charity summary. A subset of
// CharitySummary (useCharities) so this can be fed the loaded index directly.
export interface VersionStripCharity {
  amalScore: number | null;
  walletTag: string;
  hideFromCurated?: boolean;
  lastUpdated?: string | null;
}

export interface VersionStripStats {
  /** Every charity tracked in the index (the public catalog/coverage count). */
  totalCount: number;
  /** Charities with a published GMG score that aren't hidden from curation. */
  ratedCount: number;
  /** Charities the wallet routing marks zakat-eligible. */
  zakatCount: number;
  /** Max `lastUpdated` across charities, formatted YYYY-MM-DD (null if none). */
  updated: string | null;
  /** Edition label from the max date, e.g. "June 2026" (null if none). */
  edition: string | null;
  /** Hijri (Umm al-Qura) year for the edition date, e.g. 1447 (null if none). */
  hijriYear: number | null;
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function hijriYearFor(year: number, month: number, day: number): number | null {
  try {
    const dt = new Date(Date.UTC(year, month - 1, day));
    const parts = new Intl.DateTimeFormat('en-US-u-ca-islamic-umalqura', {
      year: 'numeric',
      timeZone: 'UTC',
    }).formatToParts(dt);
    const y = parts.find((part) => part.type === 'year')?.value;
    const n = y ? parseInt(y, 10) : NaN;
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

/**
 * Derive the strip's masthead numbers from the loaded charity index.
 * Returns null counts/dates only when no data is available (e.g. during SSR of a
 * route where the index wasn't seeded) — the component renders placeholders then
 * and the real numbers hydrate client-side.
 */
export function computeVersionStripStats(
  charities: readonly VersionStripCharity[] | null | undefined,
): VersionStripStats {
  const list = charities ?? [];

  const totalCount = list.length;
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

  let edition: string | null = null;
  let hijriYear: number | null = null;
  if (updated) {
    const year = Number(updated.slice(0, 4));
    const month = Number(updated.slice(5, 7));
    const day = Number(updated.slice(8, 10));
    edition = `${MONTHS[month - 1]} ${year}`;
    hijriYear = hijriYearFor(year, month, day);
  }

  return { totalCount, ratedCount, zakatCount, updated, edition, hijriYear };
}

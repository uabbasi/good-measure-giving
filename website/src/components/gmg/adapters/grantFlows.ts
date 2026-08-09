// src/components/gmg/adapters/grantFlows.ts
// Reduces a charity's Schedule I/F grant rows into something renderable.
// Only the most recent tax year is aggregated: the corpus holds several
// years per charity and summing them would double-count recurring
// recipients and disagree with the single-year financials on the page.

export interface GrantRecipient {
  name: string;
  ein: string | null;
  amount: number;
  purpose: string | null;
  isForeign: boolean;
  region: string | null;
}

export interface GrantFlows {
  taxYear: number | null;
  grantCount: number;
  totalAmount: number;
  domestic: { amount: number; count: number };
  foreign: { amount: number; count: number };
  /**
   * Ranked, identifiable recipients only (a reported name or EIN). Every
   * unattributed row in the corpus is a foreign grant (Schedule F, Part
   * II) — the IRS's own instructions tell filers to leave the name and EIN
   * columns blank there, for every grant regardless of size, so there is no
   * name to extract. This is IRS form design, not a gap in our parsing or a
   * data-quality problem on the filer's part. `topRecipients` can be empty
   * even when `totalAmount` is large; see `unattributed`.
   */
  topRecipients: GrantRecipient[];
  byRegion: { region: string; amount: number; count: number }[];
  /** Grants with no identifiable recipient — reported as a total, never itemized. */
  unattributed: { amount: number; count: number };
  /**
   * How the unattributed total breaks down by stated purpose (e.g. "Health",
   * "Support Somalia Country Office"). Only rows with a human-readable
   * purpose contribute; see `isCodeLikePurpose` for what's excluded. Ranked
   * and capped like `topRecipients` — purposes are far higher-cardinality
   * than `byRegion` (one corpus charity reports 101 distinct purposes), so
   * an uncapped list would be unreadable.
   */
  unattributedByPurpose: { purpose: string; amount: number; count: number }[];
  /**
   * The part of `unattributed.amount` that `unattributedByPurpose` does not
   * explain — blank purposes, code-like purposes, and the tail past the cap.
   * Render it whenever it is non-zero: without it the breakdown silently
   * accounts for a fraction of the total it sits under.
   */
  unattributedPurposeResidual: { amount: number; count: number };
}

// Some filers report `purpose` as a bare code (e.g. "14", "5,10" — sampled
// from the corpus, likely NTEE or SDG-style codes) rather than a
// human-readable category. ~24% of unattributed rows with a purpose look
// like this. Displayed verbatim these would read as meaningless categories
// ("14: $2M"), so they're excluded from `unattributedByPurpose` — the row
// still counts toward `unattributed.amount`/`count` above, only the
// breakdown-by-purpose omits it.
const isCodeLikePurpose = (s: string): boolean => /^[0-9][0-9.,;/\s-]*$/.test(s);

const TOP_N = 10;

const numOrNull = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? parseFloat(v) : NaN;
  return Number.isFinite(n) ? n : null;
};

const strOrNull = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() !== '' ? v.trim() : null;

export const aggregateGrants = (raw: unknown): GrantFlows | null => {
  if (!Array.isArray(raw) || raw.length === 0) return null;

  const rows = raw.filter(
    (r): r is Record<string, unknown> => !!r && typeof r === 'object' && !Array.isArray(r),
  );
  if (rows.length === 0) return null;

  const years = rows.map((r) => numOrNull(r.tax_year)).filter((y): y is number => y !== null);
  const taxYear = years.length > 0 ? Math.max(...years) : null;

  const inYear = taxYear === null ? rows : rows.filter((r) => numOrNull(r.tax_year) === taxYear);

  const byRecipient = new Map<string, GrantRecipient>();
  const regions = new Map<string, { amount: number; count: number }>();
  const unattributedPurposes = new Map<string, { amount: number; count: number }>();
  let totalAmount = 0;
  let grantCount = 0;
  const domestic = { amount: 0, count: 0 };
  const foreign = { amount: 0, count: 0 };
  const unattributed = { amount: 0, count: 0 };

  for (const r of inYear) {
    const amount = numOrNull(r.amount);
    if (amount === null) continue;

    const rawName = strOrNull(r.recipient_name);
    const ein = strOrNull(r.recipient_ein);
    const isForeign = r.is_foreign === true || r.is_foreign === 1;
    const region = strOrNull(r.region);

    grantCount += 1;
    totalAmount += amount;
    if (isForeign) {
      foreign.amount += amount;
      foreign.count += 1;
    } else {
      domestic.amount += amount;
      domestic.count += 1;
    }

    if (region !== null) {
      const cur = regions.get(region) ?? { amount: 0, count: 0 };
      regions.set(region, { amount: cur.amount + amount, count: cur.count + 1 });
    }

    // Rows with neither an EIN nor a name are foreign grants (Schedule F,
    // Part II) — the IRS's own instructions direct filers to leave the name
    // and EIN columns blank there, for every grant regardless of size. This
    // is IRS form design, not a parsing gap or a data-quality issue on the
    // filer's part, and these rows are not known to be the same recipient as
    // one another. They're counted in the totals above but never itemized or
    // merged into a fabricated "Unnamed recipient" that would misrepresent
    // many separate payments as a single giant one.
    if (rawName === null && ein === null) {
      unattributed.amount += amount;
      unattributed.count += 1;
      const purpose = strOrNull(r.purpose);
      if (purpose !== null && !isCodeLikePurpose(purpose)) {
        const cur = unattributedPurposes.get(purpose) ?? { amount: 0, count: 0 };
        unattributedPurposes.set(purpose, { amount: cur.amount + amount, count: cur.count + 1 });
      }
      continue;
    }

    // Merge repeat rows that identify the same recipient (by EIN, or by name
    // when no EIN is reported).
    const key = ein ?? (rawName as string).toLowerCase();
    const prev = byRecipient.get(key);
    if (prev) prev.amount += amount;
    else
      byRecipient.set(key, {
        name: rawName ?? 'Unnamed recipient', ein, amount, purpose: strOrNull(r.purpose), isForeign, region,
      });
  }

  if (grantCount === 0) return null;

  const byPurpose = Array.from(unattributedPurposes.entries())
    .map(([purpose, v]) => ({ purpose, amount: v.amount, count: v.count }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, TOP_N);

  return {
    taxYear,
    grantCount,
    totalAmount,
    domestic,
    foreign,
    topRecipients: Array.from(byRecipient.values())
      .sort((a, b) => b.amount - a.amount)
      .slice(0, TOP_N),
    byRegion: Array.from(regions.entries())
      .map(([region, v]) => ({ region, amount: v.amount, count: v.count }))
      .sort((a, b) => b.amount - a.amount),
    unattributed,
    unattributedByPurpose: byPurpose,
    // What the list above does NOT account for. Three things land here: rows
    // with no purpose at all, rows whose purpose is a bare code, and anything
    // past the TOP_N cap. It is not a rounding error — IRC's 2024 filing has 51
    // blank-purpose rows carrying $168.2M, 51% of its unattributed total, so a
    // breakdown printed without this reads as though it explains the whole
    // figure when it explains less than half of it.
    unattributedPurposeResidual: {
      amount: Math.max(0, unattributed.amount - byPurpose.reduce((s, x) => s + x.amount, 0)),
      count: Math.max(0, unattributed.count - byPurpose.reduce((s, x) => s + x.count, 0)),
    },
  };
};

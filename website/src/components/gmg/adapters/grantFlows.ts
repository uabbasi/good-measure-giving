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
  topRecipients: GrantRecipient[];
  byRegion: { region: string; amount: number; count: number }[];
}

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
  let totalAmount = 0;
  let grantCount = 0;
  const domestic = { amount: 0, count: 0 };
  const foreign = { amount: 0, count: 0 };

  for (const r of inYear) {
    const amount = numOrNull(r.amount);
    if (amount === null) continue;

    const rawName = strOrNull(r.recipient_name);
    const name = rawName ?? 'Unnamed recipient';
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

    // Merge repeat rows that identify the same recipient (by EIN, or by name
    // when no EIN is reported). Rows with neither an EIN nor a name are not
    // known to be the same recipient as one another — Schedule I/F omits
    // both for large batches of small, separately-made grants (e.g. disaster
    // relief to individual households) — so each such row stays its own
    // entry instead of collapsing into one fabricated "Unnamed recipient"
    // that would misrepresent many payments as a single giant one.
    const key = ein ?? rawName?.toLowerCase() ?? `__anon-${grantCount}`;
    const prev = byRecipient.get(key);
    if (prev) prev.amount += amount;
    else
      byRecipient.set(key, {
        name, ein, amount, purpose: strOrNull(r.purpose), isForeign, region,
      });
  }

  if (grantCount === 0) return null;

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
  };
};

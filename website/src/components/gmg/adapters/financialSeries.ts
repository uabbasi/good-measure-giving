// The pipeline writes 0 into yearly_financials for figures it does not have
// — the current year's expenses and net assets are commonly 0 while revenue
// is real. Rendering that literally draws a cliff, so 0 becomes null here.

export interface FinancialYear {
  year: number;
  revenue: number | null;
  expenses: number | null;
  netAssets: number | null;
}

const figure = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? parseFloat(v) : NaN;
  if (!Number.isFinite(n) || n === 0) return null;
  return n;
};

const year = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? parseInt(v, 10) : NaN;
  return Number.isFinite(n) && n > 1800 ? n : null;
};

export const buildFinancialSeries = (raw: unknown): FinancialYear[] => {
  if (!Array.isArray(raw)) return [];

  const rows: FinancialYear[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const rec = item as Record<string, unknown>;
    const y = year(rec.year);
    if (y === null) continue;
    const row: FinancialYear = {
      year: y,
      revenue: figure(rec.revenue),
      expenses: figure(rec.expenses),
      netAssets: figure(rec.net_assets),
    };
    if (row.revenue === null && row.expenses === null && row.netAssets === null) continue;
    rows.push(row);
  }

  return rows.sort((a, b) => a.year - b.year);
};

// One set of money formats for the motif pages, so the same figure never reads
// "$24.0M" in one place and "$24M" in another.

const INTL_COMPACT = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});
const INTL_WHOLE = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

/** Whole dollars below $1M, compact from there up ("$851,150", "$1.5M"). */
export const usd = (n: number | null): string =>
  n == null ? '—' : (Math.abs(n) >= 1_000_000 ? INTL_COMPACT : INTL_WHOLE).format(n);

/** Whole dollars at every size ("$1,234,567"). */
export const usdFull = (n: number | null): string => (n == null ? '—' : INTL_WHOLE.format(n));

/** Compact at every size, for dense table cells ("$851K", "$3M", "$1.5B"). */
export const usdCompact = (n: number | null): string => {
  if (n == null) return '—';
  const trim = (v: number) => String(Math.round(v * 10) / 10);
  if (n >= 1e9) return `$${trim(n / 1e9)}B`;
  if (n >= 1e6) return `$${trim(n / 1e6)}M`;
  if (n >= 1e3) return `$${Math.round(n / 1e3)}K`;
  return `$${Math.round(n)}`;
};

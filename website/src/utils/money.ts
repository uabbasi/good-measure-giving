// The one set of money formats for the whole app, so the same figure reads the same on
// the public pages and in the giving plan. A missing value is an em dash everywhere.

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
const INTL_CENTS = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const INTL_COUNT = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

/** Whole dollars below $1M, compact from there up ("$851,150", "$1.5M"). */
export const usd = (n: number | null): string =>
  n == null ? '—' : (Math.abs(n) >= 1_000_000 ? INTL_COMPACT : INTL_WHOLE).format(n);

/** Whole dollars at every size ("$1,234,567"). */
export const usdFull = (n: number | null): string => (n == null ? '—' : INTL_WHOLE.format(n));

/** Whole dollars, with cents only when the amount has them ("$250", "$12.50"). */
export const usdExact = (n: number | null): string => {
  if (n == null) return '—';
  return (Math.round(n * 100) % 100 === 0 ? INTL_WHOLE : INTL_CENTS).format(n);
};

/** Always two decimals ("$1,234.50"), for prices and line items. */
export const usdCents = (n: number | null): string => (n == null ? '—' : INTL_CENTS.format(n));

/** Compact at every size, for dense cells and chart labels ("$851K", "$3M", "$1.5B", "-$3K"). */
export const usdCompact = (n: number | null): string => {
  if (n == null) return '—';
  const sign = n < 0 ? '-' : '';
  const a = Math.abs(n);
  const trim = (v: number) => String(Math.round(v * 10) / 10);
  if (a >= 1e9) return `${sign}$${trim(a / 1e9)}B`;
  if (a >= 1e6) return `${sign}$${trim(a / 1e6)}M`;
  if (a >= 1e3) return `${sign}$${Math.round(a / 1e3)}K`;
  return `${sign}$${Math.round(a)}`;
};

/** A plain count with thousands separators ("1,204"). */
export const count = (n: number | null): string => (n == null ? '—' : INTL_COUNT.format(n));

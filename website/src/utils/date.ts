/**
 * Parse a stored 'YYYY-MM-DD' date string as local midnight.
 *
 * `new Date('YYYY-MM-DD')` parses the string as UTC midnight (per the ES spec
 * for date-only ISO strings), so in any timezone behind UTC it displays as
 * the previous day — and for dates near Jan 1, `.getFullYear()` can return
 * the wrong year entirely. Donation dates are calendar dates, not instants,
 * so they should always be read back as local midnight on that same day.
 */
export function parseLocalDate(dateStr: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  if (!match) return new Date(dateStr);
  const [, y, m, d] = match;
  return new Date(Number(y), Number(m) - 1, Number(d));
}

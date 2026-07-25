/**
 * Shared sanitizer for free-text dollar inputs.
 *
 * The giving dashboard's inline money fields used to run `value.replace(/\D/g, '')`,
 * which silently *deletes* the decimal point rather than rejecting it: typing
 * "12.50" produced 1250, a 100x overstatement with no feedback. These helpers
 * keep the same "only sane characters survive a keystroke" behaviour while
 * treating the decimal point as meaningful, and cap the magnitude so a stray
 * key-repeat can't push a plan into the trillions and overflow the stat cards.
 */

/** Ceiling for any single money field. Far above real personal giving, low enough to render. */
export const MAX_MONEY_INPUT = 1_000_000_000;

/**
 * Normalize a raw money keystroke into what the field should display.
 *
 * Keeps digits and a single decimal point, truncates to cents, and clamps to
 * MAX_MONEY_INPUT. A trailing "." is preserved so "12." is a valid intermediate
 * state on the way to "12.5" — stripping it would fight the user mid-typing.
 */
export function sanitizeMoneyInput(raw: string): string {
  if (!raw) return '';

  // Digits and dots only; everything else (minus signs, letters, commas) is dropped.
  const cleaned = raw.replace(/[^0-9.]/g, '');
  if (!cleaned) return '';

  // Collapse to at most one decimal point, keeping the first.
  const firstDot = cleaned.indexOf('.');
  let whole = firstDot === -1 ? cleaned : cleaned.slice(0, firstDot);
  let cents = firstDot === -1 ? null : cleaned.slice(firstDot + 1).replace(/\./g, '').slice(0, 2);

  // Drop leading zeros ("007" -> "7") but keep a lone "0" typeable.
  whole = whole.replace(/^0+(?=\d)/, '');

  if (whole && Number(whole) > MAX_MONEY_INPUT) {
    whole = String(MAX_MONEY_INPUT);
    cents = cents === null ? null : '';
  }

  if (cents === null) return whole;
  return `${whole}.${cents}`;
}

/**
 * Parse a sanitized money string to a number. Returns 0 for empty/partial input
 * ("", ".", "12." all read as their numeric prefix or 0) so callers can use it
 * directly in arithmetic without guarding.
 */
export function parseMoneyInput(raw: string): number {
  const n = parseFloat(sanitizeMoneyInput(raw));
  if (!Number.isFinite(n)) return 0;
  return Math.min(n, MAX_MONEY_INPUT);
}

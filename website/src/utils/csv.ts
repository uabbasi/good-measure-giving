/**
 * CSV field escaping for the donation / in-kind exports.
 *
 * Both exports used to hand-quote only the fields someone remembered were
 * free text, leaving others bare. Payment Source was one of the bare ones —
 * and its own placeholder ("e.g., Chase Credit Card, Bank Transfer") invites a
 * comma, which split the field in two and shifted every later column by one.
 * Escaping every field uniformly removes the judgement call.
 */

/**
 * Quote a single CSV field per RFC 4180.
 *
 * Fields containing a comma, quote, or newline are wrapped in quotes with
 * internal quotes doubled. A leading =, +, -, or @ is prefixed with a single
 * quote so spreadsheets treat it as text rather than a formula — a charity
 * named "=cmd|..." should not execute when the donor opens their own export.
 */
export function csvField(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  let s = String(value);
  if (s === '') return '';

  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;

  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

/** Join a row of already-raw values into a CSV line. */
export function csvRow(values: (string | number | null | undefined)[]): string {
  return values.map(csvField).join(',');
}

/** Build a full CSV document from a header row and data rows. */
export function toCSV(
  headers: string[],
  rows: (string | number | null | undefined)[][],
): string {
  return [csvRow(headers), ...rows.map(csvRow)].join('\n');
}

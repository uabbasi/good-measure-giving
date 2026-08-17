/**
 * Regression test: `new Date('YYYY-MM-DD')` parses as UTC midnight, which
 * displays as the previous calendar day (or the previous year, near Jan 1)
 * in any timezone behind UTC. Confirmed live: 'en-US' locale in Pacific time
 * rendered a donation dated 2026-08-17 as "Aug 16, 2026".
 */
import { describe, it, expect } from 'vitest';
import { parseLocalDate } from './date';

describe('parseLocalDate', () => {
  it('parses a YYYY-MM-DD string to local midnight on that same day, not the previous day', () => {
    const d = parseLocalDate('2026-08-17');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(7); // 0-indexed: August
    expect(d.getDate()).toBe(17);
  });

  it('does not roll back to the previous year for a Jan 1 date', () => {
    const d = parseLocalDate('2026-01-01');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(0);
    expect(d.getDate()).toBe(1);
  });

  it('does not roll forward to the next year for a Dec 31 date', () => {
    const d = parseLocalDate('2025-12-31');
    expect(d.getFullYear()).toBe(2025);
    expect(d.getMonth()).toBe(11);
    expect(d.getDate()).toBe(31);
  });

  it('falls back to native Date parsing for non-YYYY-MM-DD input', () => {
    const iso = '2026-08-17T12:00:00.000Z';
    expect(parseLocalDate(iso).getTime()).toBe(new Date(iso).getTime());
  });
});

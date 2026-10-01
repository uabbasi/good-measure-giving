import { describe, it, expect } from 'vitest';
import { usd, usdFull, usdExact, usdCents, usdCompact, count } from './money';

describe('money formats', () => {
  it('usdCompact drops a trailing .0 and handles negatives', () => {
    expect(usdCompact(24_000_000)).toBe('$24M');
    expect(usdCompact(147_232_858)).toBe('$147.2M');
    expect(usdCompact(1_500_000_000)).toBe('$1.5B');
    expect(usdCompact(851_150)).toBe('$851K');
    expect(usdCompact(420)).toBe('$420');
    expect(usdCompact(-3_400)).toBe('-$3K');
  });

  it('usd is whole dollars below $1M and compact above', () => {
    expect(usd(851_150)).toBe('$851,150');
    expect(usd(24_000_000)).toBe('$24M');
    expect(usdFull(1_234_567)).toBe('$1,234,567');
  });

  it('usdExact shows cents only when there are some; usdCents always does', () => {
    expect(usdExact(250)).toBe('$250');
    expect(usdExact(12.5)).toBe('$12.50');
    expect(usdCents(1234.5)).toBe('$1,234.50');
  });

  it('count groups thousands', () => {
    expect(count(1204)).toBe('1,204');
  });

  it('every format renders a missing value as an em dash', () => {
    expect([usd(null), usdFull(null), usdExact(null), usdCents(null), usdCompact(null), count(null)]).toEqual(Array(6).fill('—'));
  });
});

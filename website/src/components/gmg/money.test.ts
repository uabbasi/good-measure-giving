import { describe, it, expect } from 'vitest';
import { usd, usdFull, usdCompact } from './money';

describe('money formats', () => {
  it('usdCompact drops a trailing .0 so the same figure reads the same everywhere', () => {
    expect(usdCompact(24_000_000)).toBe('$24M');
    expect(usdCompact(147_232_858)).toBe('$147.2M');
    expect(usdCompact(1_500_000_000)).toBe('$1.5B');
    expect(usdCompact(851_150)).toBe('$851K');
    expect(usdCompact(420)).toBe('$420');
  });

  it('usd is whole dollars below $1M and compact above', () => {
    expect(usd(851_150)).toBe('$851,150');
    expect(usd(24_000_000)).toBe('$24M');
    expect(usdFull(1_234_567)).toBe('$1,234,567');
  });

  it('all three render a missing value as an em dash', () => {
    expect([usd(null), usdFull(null), usdCompact(null)]).toEqual(['—', '—', '—']);
  });
});

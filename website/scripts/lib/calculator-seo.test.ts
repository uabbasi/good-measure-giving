import { describe, it, expect } from 'vitest';
import { isValidAssetSlug, KNOWN_ASSET_SLUGS } from './calculator-seo';

describe('isValidAssetSlug', () => {
  it('accepts every known asset slug', () => {
    for (const slug of KNOWN_ASSET_SLUGS) {
      expect(isValidAssetSlug(slug)).toBe(true);
    }
  });

  it('rejects unknown slugs', () => {
    expect(isValidAssetSlug('not-an-asset')).toBe(false);
    expect(isValidAssetSlug('')).toBe(false);
  });
});

describe('KNOWN_ASSET_SLUGS', () => {
  it('includes all 7 asset types from the spec', () => {
    expect(KNOWN_ASSET_SLUGS).toContain('cash-savings');
    expect(KNOWN_ASSET_SLUGS).toContain('gold-silver');
    expect(KNOWN_ASSET_SLUGS).toContain('stocks');
    expect(KNOWN_ASSET_SLUGS).toContain('401k-retirement');
    expect(KNOWN_ASSET_SLUGS).toContain('crypto');
    expect(KNOWN_ASSET_SLUGS).toContain('business-assets');
    expect(KNOWN_ASSET_SLUGS).toContain('real-estate');
    expect(KNOWN_ASSET_SLUGS).toHaveLength(7);
  });
});

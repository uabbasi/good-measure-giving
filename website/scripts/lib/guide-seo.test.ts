import { describe, it, expect } from 'vitest';
import { isValidGuideSlug } from './guide-seo';

describe('isValidGuideSlug', () => {
  it('accepts kebab-case slugs', () => {
    expect(isValidGuideSlug('what-makes-a-charity-zakat-eligible')).toBe(true);
    expect(isValidGuideSlug('sadaqah-vs-zakat')).toBe(true);
  });

  it('rejects slugs with uppercase, spaces, underscores, or leading/trailing dashes', () => {
    expect(isValidGuideSlug('What-Makes')).toBe(false);
    expect(isValidGuideSlug('some guide')).toBe(false);
    expect(isValidGuideSlug('some_guide')).toBe(false);
    expect(isValidGuideSlug('-leading-dash')).toBe(false);
    expect(isValidGuideSlug('trailing-dash-')).toBe(false);
    expect(isValidGuideSlug('')).toBe(false);
  });
});

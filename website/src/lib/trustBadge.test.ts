import { describe, it, expect } from 'vitest';
import {
  buildTrustBadgeSnippet,
  buildTextLinkSnippets,
  charityUrl,
  SITE_URL,
} from './trustBadge';

describe('charityUrl', () => {
  it('builds a trailing-slash charity detail URL', () => {
    expect(charityUrl('41-2046295')).toBe(`${SITE_URL}/charity/41-2046295/`);
  });
});

describe('buildTrustBadgeSnippet', () => {
  const snippet = buildTrustBadgeSnippet({
    ein: '41-2046295',
    name: 'The Citizens Foundation USA',
    score: 87,
  });

  it('links dofollow (no rel="nofollow") to the charity detail page', () => {
    expect(snippet).toContain(`href="${SITE_URL}/charity/41-2046295/"`);
    expect(snippet).not.toContain('nofollow');
  });

  it('surfaces the GMG score and the rated-by line', () => {
    expect(snippet).toContain('87');
    expect(snippet).toContain('Independently rated by');
    expect(snippet).toContain('Good Measure Giving');
  });

  it('is self-contained with inline styles (no class= dependency)', () => {
    expect(snippet).toContain('style=');
    expect(snippet).not.toContain('class=');
  });
});

describe('buildTextLinkSnippets', () => {
  it('returns dofollow links with descriptive anchor text', () => {
    const snippets = buildTextLinkSnippets();
    expect(snippets.length).toBeGreaterThan(0);
    for (const s of snippets) {
      expect(s.html).toContain(`href="${SITE_URL}`);
      expect(s.html).not.toContain('nofollow');
    }
  });
});

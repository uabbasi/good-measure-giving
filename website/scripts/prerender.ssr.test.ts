import { isSsrRoute } from './prerender';

test('classifies SSR vs meta-only routes', () => {
  expect(isSsrRoute('/charity/81-2822877')).toBe(true);
  expect(isSsrRoute('/guides')).toBe(true);
  expect(isSsrRoute('/guides/zakat-101')).toBe(true);
  expect(isSsrRoute('/about')).toBe(true);
  // Home and Browse are indexable and listed in the sitemap, so they must be
  // SSR'd with real content — empty shells caused "Discovered – not indexed".
  expect(isSsrRoute('/')).toBe(true);
  expect(isSsrRoute('/browse')).toBe(true);
  // User-only pages stay meta-only (they're noindex and out of the sitemap).
  expect(isSsrRoute('/profile')).toBe(false);
  expect(isSsrRoute('/compare')).toBe(false);
  expect(isSsrRoute('/bookmarks')).toBe(false);
});

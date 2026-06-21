import { isSsrRoute } from './prerender';

test('classifies SSR vs meta-only routes', () => {
  expect(isSsrRoute('/charity/81-2822877')).toBe(true);
  expect(isSsrRoute('/guides')).toBe(true);
  expect(isSsrRoute('/guides/zakat-101')).toBe(true);
  expect(isSsrRoute('/about')).toBe(true);
  expect(isSsrRoute('/')).toBe(false);
  expect(isSsrRoute('/browse')).toBe(false);
  expect(isSsrRoute('/profile')).toBe(false);
});

// @vitest-environment node
import { render } from './entry-server';

test('render() returns full HTML with seeded guide content', async () => {
  const html = await render('/guides', [
    { queryKey: ['guides'], data: { guides: [{ slug: 'zakat-101', title: 'Zakat 101', description: 'x', readingTimeMinutes: 5 }] } },
  ]);
  expect(html).toContain('Zakat 101');
  expect(html).toContain('Skip to main content');
}, 20000);

// Regression: /browse must SSR without throwing. BrowsePage → useTour → useNuxState
// read localStorage in a useState initializer, which runs during server render.
// Node 22+ exposes a bare (unbacked) `localStorage` global with no `window`, so an
// unguarded read throws "localStorage.getItem is not a function" and the page fell
// back to an empty meta-only shell (bad for SEO indexing).
test('render() SSRs /browse without touching localStorage', async () => {
  const html = await render('/browse', []);
  expect(html).toContain('Skip to main content');
}, 20000);

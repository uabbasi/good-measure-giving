// @vitest-environment node
import { render } from './entry-server';

test('render() returns full HTML with seeded guide content', async () => {
  const html = await render('/guides', [
    { queryKey: ['guides'], data: { guides: [{ slug: 'zakat-101', title: 'Zakat 101', description: 'x', readingTimeMinutes: 5 }] } },
  ]);
  expect(html).toContain('Zakat 101');
  expect(html).toContain('Skip to main content');
}, 20000);

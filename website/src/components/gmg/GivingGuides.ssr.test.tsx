// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { render } from '../../../entry-server';
import index from '../../../data/charities.json';
import shortlist from '../../../data/guides/top-zakat-eligible-charities-2026.json';
import { buildCharitiesIndex, type CharitiesIndex } from '../../hooks/useCharities';

const seed = { queryKey: ['charities'], data: buildCharitiesIndex(index as CharitiesIndex) };
const rankedPath = '/best-muslim-charities-in-usa/';
const shortlistPath = '/guides/top-zakat-eligible-charities-2026/';

describe('giving guides in prerendered HTML', () => {
  it.each(['/', '/browse/'])('links from %s to both guides', async (route) => {
    const html = await render(route, [seed]);
    expect(html).toContain(`href="${rankedPath}"`);
    expect(html).toContain(`href="${shortlistPath}"`);
  });

  it('shows the ranked comparison with evidence and canonical review links', async () => {
    const html = await render(rankedPath, [seed]);
    const table = html.match(/<table[\s\S]*?<\/table>/)?.[0] ?? '';
    expect(table).toContain('Evidence stage');
    expect(table).toContain('GMG rating');
    expect(table).toContain('href="/charity/83-3464851/"');
  });

  it('shows all featured reviews and published zakat claims before the guide sections', async () => {
    const html = await render(shortlistPath, [seed, { queryKey: ['guide', shortlist.slug], data: shortlist }]);
    const table = html.match(/<table[\s\S]*?<\/table>/)?.[0] ?? '';
    expect(table).toContain('Published zakat claim');
    expect(table).toContain('https://icnarelief.org/zakat');
    for (const { ein } of shortlist.featuredCharities) {
      expect(table).toContain(`href="/charity/${ein}/"`);
    }
    expect(html.indexOf('</table>')).toBeLessThan(html.indexOf('How this list is built'));
  });
});

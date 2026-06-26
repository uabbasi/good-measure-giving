// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { test, expect } from 'vitest';
import { ZakatMetalChart } from './ZakatMetalChart';
import { buildChartRows, GOLD_WEIGHTS } from '../../utils/zakatChart';

test('renders the title, a highlighted nisab row, and formatted values', () => {
  const html = renderToStaticMarkup(
    <ZakatMetalChart title="Gold" rows={buildChartRows(150, GOLD_WEIGHTS)} nisabNote="85g of gold is the nisab threshold." />,
  );
  // title
  expect(html).toContain('Gold');
  // nisab row present and visually highlighted
  expect(html).toContain('85 g (nisab)');
  expect(html).toContain('emerald');
  // value column: 100 g × $150 = $15,000
  expect(html).toContain('$15,000');
  // zakat column (2.5% of $15,000 = $375.00)
  expect(html).toContain('$375.00');
  // note rendered
  expect(html).toContain('nisab threshold');
});

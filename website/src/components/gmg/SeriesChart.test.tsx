import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { SeriesChart } from './SeriesChart';
import { gmgPalette } from './tokens';
import { adaptCharity } from './charityAdapter';

const p = gmgPalette(false);
const series = [
  { year: 2022, revenue: 1000, expenses: 900, netAssets: 500 },
  { year: 2023, revenue: 1200, expenses: 1100, netAssets: 600 },
  { year: 2024, revenue: 1500, expenses: null, netAssets: null },
];

// Pull the (x, y) pairs out of a `d="M x,y L x,y ..."` path string in order.
const points = (d: string): [number, number][] =>
  Array.from(d.matchAll(/[ML]\s*([\d.-]+),([\d.-]+)/g)).map((m) => [
    parseFloat(m[1]),
    parseFloat(m[2]),
  ]);

describe('SeriesChart', () => {
  it('renders nothing for an empty series rather than an empty axis', () => {
    const { container } = render(<SeriesChart series={[]} p={p} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('renders nothing for a single year, which is not a series', () => {
    const { container } = render(<SeriesChart series={[series[0]]} p={p} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('labels every year in the series', () => {
    const { getByText } = render(<SeriesChart series={series} p={p} />);
    for (const y of ['2022', '2023', '2024']) expect(getByText(y)).toBeInTheDocument();
  });

  it('breaks the line at a null instead of plotting it as zero', () => {
    const { container } = render(<SeriesChart series={series} p={p} />);
    const expensePath = container.querySelector('[data-series="expenses"]');
    expect(expensePath).not.toBeNull();
    // Three years, one null -> the drawn path must cover 2 points, not 3.
    const d = expensePath?.getAttribute('d') ?? '';
    expect((d.match(/[ML]/g) ?? []).length).toBe(2);
  });

  it('restarts the path after a middle null, not just after a trailing one', () => {
    // The only null in the top-level fixture is trailing (2024). A regression
    // that stops drawing entirely on the first null instead of resuming after
    // it would still pass that test — this fixture puts the gap in the middle
    // so the points after it must still show up.
    const withMiddleGap = [
      { year: 2021, revenue: 1000, expenses: 900, netAssets: 500 },
      { year: 2022, revenue: 1100, expenses: null, netAssets: 550 },
      { year: 2023, revenue: 1200, expenses: 1000, netAssets: 600 },
      { year: 2024, revenue: 1300, expenses: 1050, netAssets: 650 },
    ];
    const { container } = render(<SeriesChart series={withMiddleGap} p={p} />);
    const expensePath = container.querySelector('[data-series="expenses"]');
    const d = expensePath?.getAttribute('d') ?? '';

    // Two subpaths (2021 alone; 2023-2024 joined), three points total.
    expect((d.match(/M/g) ?? []).length).toBe(2);
    expect((d.match(/[ML]/g) ?? []).length).toBe(3);

    // The points after the gap must actually be drawn, not dropped.
    const pts = points(d);
    expect(pts).toHaveLength(3);
    expect(pts[1][0]).toBeCloseTo((2 / 3) * 100, 1); // 2023 is index 2 of 4
    expect(pts[2][0]).toBeCloseTo(100, 1); // 2024 is the last point
  });

  it('plots a negative value strictly below the zero baseline, not clamped to it', () => {
    const withNegative = [
      { year: 2022, revenue: 1000, expenses: 900, netAssets: -200 },
      { year: 2023, revenue: 1200, expenses: 1100, netAssets: 400 },
    ];
    const { container } = render(<SeriesChart series={withNegative} p={p} />);
    const baseline = container.querySelector('[data-baseline="zero"]');
    expect(baseline).not.toBeNull();
    const baselineY = parseFloat(baseline?.getAttribute('y1') ?? 'NaN');
    expect(Number.isNaN(baselineY)).toBe(false);

    // SVG y grows downward, so "below the baseline" means a strictly larger y.
    // A naive implementation that clamps negatives to 0 instead of letting them
    // go below the line would place this point ON the baseline, not past it —
    // this is the exact bug the brief warns against.
    const netAssetsPath = container.querySelector('[data-series="netAssets"]');
    const d = netAssetsPath?.getAttribute('d') ?? '';
    const [firstPoint] = points(d);
    expect(firstPoint).toBeDefined();
    expect(firstPoint[1]).toBeGreaterThan(baselineY);
  });

  it('is labelled for screen readers', () => {
    const { container } = render(<SeriesChart series={series} p={p} />);
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('role')).toBe('img');
    expect(svg?.getAttribute('aria-label')).toMatch(/2022/);
    expect(svg?.getAttribute('aria-label')).toMatch(/2024/);
  });

  it('degrades the aria-label to "not reported" for a series with no values at all', () => {
    const expensesAlwaysNull = [
      { year: 2022, revenue: 1000, expenses: null, netAssets: 500 },
      { year: 2023, revenue: 1200, expenses: null, netAssets: 600 },
    ];
    const { container } = render(<SeriesChart series={expensesAlwaysNull} p={p} />);
    const label = container.querySelector('svg')?.getAttribute('aria-label') ?? '';
    expect(label).toMatch(/Expenses not reported/);
    // The series that did report should still carry real figures, not have
    // "not reported" bleed over from the null one.
    expect(label).toMatch(/Revenue 1K in 2023/);
    expect(label).toMatch(/Net assets 600 in 2023/);
  });

  it('labels the last reported point of each series with its actual value', () => {
    // Otherwise-identical charts render as flat, numberless lines — this is
    // the exact bug the fix addresses. `series`'s 2024 row has expenses and
    // netAssets null, so their "last reported" point is 2023, not 2024;
    // revenue's is 2024. A regression that always reads the final row
    // (rather than searching backward per series) would mislabel or drop
    // the expenses/netAssets figures.
    const { container } = render(<SeriesChart series={series} p={p} />);
    expect(container.querySelector('[data-value-label="revenue"]')?.textContent).toBe('$2K');
    expect(container.querySelector('[data-value-label="expenses"]')?.textContent).toBe('$1K');
    expect(container.querySelector('[data-value-label="netAssets"]')?.textContent).toBe('$600');
  });

  it('omits the value label for a series that never reported', () => {
    const expensesAlwaysNull = [
      { year: 2022, revenue: 1000, expenses: null, netAssets: 500 },
      { year: 2023, revenue: 1200, expenses: null, netAssets: 600 },
    ];
    const { container } = render(<SeriesChart series={expensesAlwaysNull} p={p} />);
    expect(container.querySelector('[data-value-label="expenses"]')).toBeNull();
    expect(container.querySelector('[data-value-label="revenue"]')).not.toBeNull();
  });

  it('states the axis scale so a shared linear axis carries a sense of magnitude', () => {
    // The chart's actual complaint: revenue/expenses/net-assets share one
    // scale with no numbers on it, so a huge series and a small one both
    // look like flat lines. The scale caption is the minimum fix.
    const { container } = render(<SeriesChart series={series} p={p} />);
    expect(container.textContent).toContain('Scale');
    expect(container.textContent).toContain('$0'); // the axis always includes zero
    expect(container.textContent).toContain('$2K'); // max across the fixture (1500)
  });
});

describe('SeriesChart against the real corpus', () => {
  const dir = path.resolve(__dirname, '../../../data/charities');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json'));

  it('renders every charity that has a series without throwing', () => {
    let rendered = 0;
    for (const f of files) {
      const c = adaptCharity(JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));
      const { container, unmount } = render(<SeriesChart series={c.financialSeries} p={p} />);
      if (c.financialSeries.length >= 2) {
        expect(container.querySelector('svg')).not.toBeNull();
        rendered += 1;
      }
      unmount();
    }
    expect(rendered).toBeGreaterThanOrEqual(100);
  });
});

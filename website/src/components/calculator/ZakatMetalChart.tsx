import React from 'react';
import type { ChartRow } from '../../utils/zakatChart';

const fmt = (n: number, decimals = 0): string =>
  n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

interface ZakatMetalChartProps {
  title: string;
  rows: ChartRow[];
  nisabNote?: string;
}

export const ZakatMetalChart: React.FC<ZakatMetalChartProps> = ({ title, rows, nisabNote }) => {
  const headingId = `zakat-chart-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;

  return (
  <div className="mb-8">
    <h3 id={headingId} className="text-lg font-semibold mb-3">{title}</h3>
    <table aria-labelledby={headingId} className="w-full text-sm border-collapse">
      <thead>
        <tr className="text-left border-b border-slate-300 dark:border-slate-700">
          <th scope="col" className="py-2 pr-4 font-medium">Weight</th>
          <th scope="col" className="py-2 pr-4 font-medium text-right">Market value</th>
          <th scope="col" className="py-2 font-medium text-right">Zakat due (2.5%)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.label}
            className={`border-b border-slate-100 dark:border-slate-800 ${
              row.isNisab ? 'bg-emerald-50 dark:bg-emerald-900/20 font-semibold' : ''
            }`}
          >
            <td className="py-2 pr-4">{row.label}</td>
            <td className="py-2 pr-4 text-right">${fmt(row.value)}</td>
            <td className="py-2 text-right">${fmt(row.zakat, 2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
    {nisabNote && <p className="mt-2 text-xs text-slate-500">{nisabNote}</p>}
  </div>
  );
};

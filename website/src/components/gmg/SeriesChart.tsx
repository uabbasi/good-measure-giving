// A small multi-year revenue/expense/net-asset plot. Inline SVG in the same
// idiom as HarveyBall and Star8 — this codebase uses no charting library.
//
// Two data facts drive the design. A null figure means "not reported" (the
// pipeline writes 0 for absent expenses and net assets, which financialSeries
// normalizes to null), so a null must BREAK the line rather than plot as zero.
// And negative net assets are real for indebted charities, so the scale must
// include zero and draw a baseline rather than clamping.

import React from 'react';
import type { FinancialYear } from './adapters/financialSeries';
import { GmgPalette, FONT_MONO } from './tokens';

type Key = 'revenue' | 'expenses' | 'netAssets';

const SERIES: { key: Key; label: string }[] = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'expenses', label: 'Expenses' },
  { key: 'netAssets', label: 'Net assets' },
];

const compact = (n: number): string => {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${Math.round(n / 1e3)}K`;
  return `${Math.round(n)}`;
};

export const SeriesChart: React.FC<{
  series: FinancialYear[];
  p: GmgPalette;
  height?: number;
}> = ({ series, p, height = 120 }) => {
  // One point is not a series; an empty one has nothing to say.
  if (series.length < 2) return null;

  const colors: Record<Key, string> = {
    revenue: p.accent,
    expenses: p.accent2,
    netAssets: p.warn,
  };

  const values = SERIES.flatMap(({ key }) =>
    series.map((r) => r[key]).filter((v): v is number => v !== null),
  );
  if (values.length === 0) return null;

  // Always include zero so a negative reads as below the line, not rebased.
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;

  const W = 100;
  const padTop = 8;
  const plotH = height - padTop - 18;
  const x = (i: number) => (series.length === 1 ? W / 2 : (i / (series.length - 1)) * W);
  const y = (v: number) => padTop + plotH - ((v - min) / span) * plotH;

  // A null breaks the path: start a new subpath after any gap.
  const pathFor = (key: Key): string => {
    let d = '';
    let penDown = false;
    series.forEach((row, i) => {
      const v = row[key];
      if (v === null) {
        penDown = false;
        return;
      }
      d += `${penDown ? 'L' : 'M'}${x(i).toFixed(2)},${y(v).toFixed(2)} `;
      penDown = true;
    });
    return d.trim();
  };

  const years = series.map((r) => r.year);
  const label = `Financial series ${years[0]} to ${years[years.length - 1]}: ${SERIES.map(
    ({ key, label: l }) => {
      const last = [...series].reverse().find((r) => r[key] !== null);
      return last ? `${l} ${compact(last[key] as number)} in ${last.year}` : `${l} not reported`;
    },
  ).join('; ')}`;

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${height}`}
        preserveAspectRatio="none"
        style={{ width: '100%', height, display: 'block' }}
        role="img"
        aria-label={label}
      >
        {min < 0 && (
          <line
            data-baseline="zero"
            x1={0}
            x2={W}
            y1={y(0)}
            y2={y(0)}
            stroke={p.rule}
            strokeWidth={0.5}
            vectorEffect="non-scaling-stroke"
          />
        )}
        {SERIES.map(({ key }) => {
          const d = pathFor(key);
          if (d === '') return null;
          return (
            <path
              key={key}
              data-series={key}
              d={d}
              fill="none"
              stroke={colors[key]}
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </svg>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontFamily: FONT_MONO,
          fontSize: 10,
          color: p.sub2,
          marginTop: 2,
        }}
      >
        {series.map((r) => (
          <span key={r.year}>{r.year}</span>
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 6, fontSize: 11, color: p.sub }}>
        {SERIES.map(({ key, label: l }) => (
          <span key={key}>
            <span style={{ color: colors[key] }}>■</span> {l}
          </span>
        ))}
      </div>
    </div>
  );
};

export default SeriesChart;

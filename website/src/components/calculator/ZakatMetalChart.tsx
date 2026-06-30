import React from 'react';
import type { ChartRow } from '../../utils/zakatChart';
import { FONT_DISPLAY, FONT_MONO, type GmgPalette } from '../gmg/tokens';

const fmt = (n: number, decimals = 0): string =>
  n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

interface ZakatMetalChartProps {
  p: GmgPalette;
  title: string;
  rows: ChartRow[];
  nisabNote?: string;
}

// Presentational metal-weight table, motif-styled (palette-driven, inline).
export const ZakatMetalChart: React.FC<ZakatMetalChartProps> = ({ p, title, rows, nisabNote }) => {
  const headingId = `zakat-chart-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  const cell: React.CSSProperties = { padding: '8px 0', fontSize: 14, color: p.fg };

  return (
    <div style={{ marginBottom: 28 }}>
      <h3 id={headingId} style={{ fontFamily: FONT_DISPLAY, fontSize: 18, color: p.fg, margin: '0 0 12px' }}>{title}</h3>
      <table aria-labelledby={headingId} style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${p.rule2}`, textAlign: 'left' }}>
            <th scope="col" style={{ ...cell, fontWeight: 600, color: p.sub }}>Weight</th>
            <th scope="col" style={{ ...cell, fontWeight: 600, color: p.sub, textAlign: 'right' }}>Market value</th>
            <th scope="col" style={{ ...cell, fontWeight: 600, color: p.sub, textAlign: 'right' }}>Zakat due (2.5%)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.label}
              style={{
                borderBottom: `1px solid ${p.rule}`,
                background: row.isNisab ? p.posBg : 'transparent',
                fontWeight: row.isNisab ? 600 : 400,
              }}
            >
              <td style={{ ...cell, paddingLeft: row.isNisab ? 8 : 0 }}>{row.label}</td>
              <td style={{ ...cell, textAlign: 'right', fontFamily: FONT_MONO }}>${fmt(row.value)}</td>
              <td style={{ ...cell, textAlign: 'right', fontFamily: FONT_MONO, paddingRight: row.isNisab ? 8 : 0 }}>${fmt(row.zakat, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {nisabNote && <p style={{ fontSize: 12, color: p.sub2, margin: '8px 0 0' }}>{nisabNote}</p>}
    </div>
  );
};

import type { CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { charityPath } from '../../lib/paths';
import type { GmgPalette } from './tokens';

interface ComparisonRow {
  ein: string;
  name: string;
  cells: ReactNode[];
}

export function CharityComparisonTable({ p, label, columns, rows }: {
  p: GmgPalette;
  label: string;
  columns: string[];
  rows: ComparisonRow[];
}) {
  const cell: CSSProperties = {
    padding: '10px 12px',
    borderBottom: `1px solid ${p.rule}`,
    textAlign: 'left',
    verticalAlign: 'top',
  };

  return (
    <div role="region" aria-label={label} tabIndex={0} style={{ overflowX: 'auto' }}>
      <table aria-label={label} style={{ width: '100%', minWidth: 530, borderCollapse: 'collapse', fontSize: 14 }}>
        <thead style={{ background: p.bg2 }}>
          <tr>
            <th scope="col" style={cell}>Charity review</th>
            {columns.map((column) => <th key={column} scope="col" style={cell}>{column}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ ein, name, cells }) => (
            <tr key={ein}>
              <th scope="row" style={cell}>
                <Link to={charityPath(ein)} style={{ color: p.accent }}>{name}</Link>
              </th>
              {cells.map((content, index) => <td key={columns[index]} style={cell}>{content}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

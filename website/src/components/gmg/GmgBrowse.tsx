// Good Measure Giving — "Modern" motif Index / Browse (proof surface #2).
// Reachable via /browse?design=gmg. Dense Harvey-ball table on desktop,
// stacked cards on mobile, fed by the real charity list.

import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useCharities } from '../../hooks/useCharities';
import {
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEMES,
  resolveFontVariant,
  type FontVariant,
} from './tokens';
import { Rating, ratingColor, riskTone } from './rating';
import { HarveyBall, Tag, Kicker, Figure } from './primitives';
import { GmgNav, TypeSwitcher } from './chrome';
import { useIsMobile } from './useIsMobile';
import { adaptRow, GmgRow } from './charityAdapter';

const RANK: Record<Rating, number> = { Strong: 5, Good: 4, Moderate: 3, Fair: 2, Weak: 1 };
type SortKey = 'score' | 'impact' | 'alignment' | 'name';

export const GmgBrowse: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const padX = isMobile ? 16 : 24;
  const { charities, loading } = useCharities();

  const variant: FontVariant = resolveFontVariant(
    typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('type') : null,
  );
  const ft = FONT_THEMES[variant];
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  };

  const [query, setQuery] = useState('');
  const [wallet, setWallet] = useState<'all' | 'zakat' | 'sadaqah'>('all');
  const [sortBy, setSortBy] = useState<SortKey>('score');

  const allRows: GmgRow[] = useMemo(
    () => (charities || []).map(adaptRow).filter((r) => r.ein),
    [charities],
  );
  const zakatCount = allRows.filter((r) => r.walletIsZakat).length;

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let r = allRows.filter((row) => {
      if (wallet === 'zakat' && !row.walletIsZakat) return false;
      if (wallet === 'sadaqah' && row.walletIsZakat) return false;
      if (q && !(`${row.name} ${row.ein} ${row.cause}`.toLowerCase().includes(q))) return false;
      return true;
    });
    r = [...r].sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      if (sortBy === 'impact') return RANK[b.impact] - RANK[a.impact] || b.amalScore - a.amalScore;
      if (sortBy === 'alignment')
        return RANK[b.alignment] - RANK[a.alignment] || b.amalScore - a.amalScore;
      return b.amalScore - a.amalScore;
    });
    return r;
  }, [allRows, query, wallet, sortBy]);

  const sectionBorder = `1px solid ${p.rule}`;

  const RatingCell: React.FC<{ rating: Rating }> = ({ rating }) => (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <HarveyBall rating={rating} p={p} size={14} />
      <span style={{ fontSize: 11.5, color: ratingColor(rating, p) }}>{rating}</span>
    </span>
  );

  const inputStyle: React.CSSProperties = {
    flex: '1 1 240px',
    minWidth: 0,
    padding: '8px 12px',
    borderRadius: 99,
    border: sectionBorder,
    background: p.bg,
    color: p.fg,
    fontFamily: FONT_TEXT,
    fontSize: 13,
    outline: 'none',
  };

  const FilterPills: React.FC = () => (
    <section
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 10,
        alignItems: 'center',
        padding: `10px ${padX}px`,
        background: p.bg2,
        borderBottom: sectionBorder,
        fontSize: 12,
      }}
    >
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search charities, EINs, causes…"
        style={inputStyle}
      />
      <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <Kicker p={p}>Wallet</Kicker>
        {(
          [
            ['all', `All ${allRows.length}`],
            ['zakat', `Zakat ${zakatCount}`],
            ['sadaqah', `Sadaqah ${allRows.length - zakatCount}`],
          ] as [typeof wallet, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setWallet(key)}
            style={{
              padding: '3px 9px',
              borderRadius: 99,
              cursor: 'pointer',
              fontFamily: FONT_MONO,
              fontSize: 9.5,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              border: `1px solid ${wallet === key ? p.chip : p.rule}`,
              background: wallet === key ? p.chip : 'transparent',
              color: wallet === key ? p.chipFg : p.sub,
            }}
          >
            {label}
          </button>
        ))}
      </span>
      <span style={{ flex: 1 }} />
      <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <Kicker p={p}>Sort</Kicker>
        {(
          [
            ['score', 'GMG ↓'],
            ['impact', 'Impact ↓'],
            ['alignment', 'Alignment ↓'],
            ['name', 'Name'],
          ] as [SortKey, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setSortBy(key)}
            style={{
              padding: '3px 9px',
              borderRadius: 99,
              cursor: 'pointer',
              fontFamily: FONT_MONO,
              fontSize: 9.5,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              border: `1px solid ${sortBy === key ? p.chip : p.rule}`,
              background: sortBy === key ? p.chip : 'transparent',
              color: sortBy === key ? p.chipFg : p.sub,
            }}
          >
            {label}
          </button>
        ))}
      </span>
    </section>
  );

  const SubHeader: React.FC = () => (
    <section style={{ padding: `20px ${padX}px 14px`, borderBottom: sectionBorder }}>
      <Kicker p={p}>The Index · {allRows.length} charities</Kicker>
      <h1 style={{ fontFamily: FONT_DISPLAY, fontSize: isMobile ? 34 : 46, margin: '4px 0 0', lineHeight: 1, letterSpacing: ft.displayTracking }}>
        Every charity, <em style={{ color: p.accent }}>weighed.</em>
      </h1>
    </section>
  );

  const shell = (children: React.ReactNode) => (
    <div style={{ background: p.bg, color: p.fg, fontFamily: FONT_TEXT, minHeight: '100vh', ...fontVars }}>
      <GmgNav p={p} isMobile={isMobile} active="Browse" />
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexWrap: 'wrap',
          padding: `6px ${padX}px`,
          background: p.bg2,
          borderBottom: sectionBorder,
          color: p.sub,
          fontFamily: FONT_MONO,
          fontSize: 10.5,
          letterSpacing: '0.06em',
        }}
      >
        <span>GOOD MEASURE GIVING · THE INDEX</span>
        <span style={{ flex: 1 }} />
        <TypeSwitcher p={p} variant={variant} basePath="/browse" />
      </div>
      {children}
    </div>
  );

  if (loading) {
    return shell(
      <div style={{ padding: 48, textAlign: 'center', color: p.sub, fontFamily: FONT_MONO, fontSize: 12 }}>
        Loading the index…
      </div>,
    );
  }

  return shell(
    <>
      <SubHeader />
      <FilterPills />

      {isMobile ? (
        /* Mobile: stacked cards */
        <section style={{ padding: `12px ${padX}px 28px`, display: 'grid', gap: 10 }}>
          {rows.map((row, i) => (
            <Link
              key={row.ein}
              to={`/charity/${row.ein}?design=gmg`}
              style={{ textDecoration: 'none', color: 'inherit', border: sectionBorder, borderRadius: 8, padding: 14, background: p.bg2, display: 'block' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                <span style={{ fontFamily: FONT_MONO, fontSize: 10, color: p.sub2 }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <Tag tone={row.walletIsZakat ? 'accent' : 'muted'} p={p}>{row.wallet}</Tag>
              </div>
              <div style={{ fontFamily: FONT_DISPLAY, fontSize: 22, lineHeight: 1.1, marginTop: 4, letterSpacing: ft.displayTracking }}>
                {row.name}
              </div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 10, color: p.sub2, marginTop: 2 }}>
                {row.cause} · {row.region} · EIN {row.ein}
              </div>
              <div style={{ display: 'flex', gap: 18, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Kicker p={p}>Impact</Kicker>
                  <RatingCell rating={row.impact} />
                </span>
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Kicker p={p}>Alignment</Kicker>
                  <RatingCell rating={row.alignment} />
                </span>
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Kicker p={p}>GMG</Kicker>
                  <Figure size={16} color={p.accent}>{row.amalScore}</Figure>
                </span>
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Kicker p={p}>Risk</Kicker>
                  <span style={{ fontSize: 11.5, color: p[riskTone(row.risk)] as string }}>{row.risk}</span>
                </span>
              </div>
            </Link>
          ))}
        </section>
      ) : (
        /* Desktop: dense table */
        <section style={{ padding: `0 ${padX}px 28px` }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead>
              <tr
                style={{
                  borderBottom: sectionBorder,
                  color: p.sub2,
                  fontFamily: FONT_MONO,
                  fontSize: 9.5,
                  letterSpacing: '0.14em',
                  textTransform: 'uppercase',
                  textAlign: 'left',
                }}
              >
                <th style={{ padding: '10px 6px', width: 36 }}>№</th>
                <th style={{ padding: '10px 6px' }}>Charity / EIN</th>
                <th style={{ padding: '10px 6px', width: 150 }}>Cause</th>
                <th style={{ padding: '10px 6px', width: 110 }}>Region</th>
                <th style={{ padding: '10px 6px', width: 80 }}>Wallet</th>
                <th style={{ padding: '10px 6px', width: 110 }}>Impact</th>
                <th style={{ padding: '10px 6px', width: 110 }}>Alignment</th>
                <th style={{ padding: '10px 6px', width: 64 }}>GMG</th>
                <th style={{ padding: '10px 6px', width: 64 }}>Risk</th>
                <th style={{ padding: '10px 6px', width: 90 }}>Verif.</th>
                <th style={{ padding: '10px 6px', width: 52 }}>Prog.%</th>
                <th style={{ padding: '10px 6px', width: 24 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.ein}
                  onClick={() => {
                    window.location.href = `/charity/${row.ein}?design=gmg`;
                  }}
                  style={{ borderBottom: sectionBorder, background: i % 2 === 0 ? 'transparent' : p.bg2, cursor: 'pointer' }}
                >
                  <td style={{ padding: '8px 6px', fontFamily: FONT_MONO, fontSize: 10.5, color: p.sub2 }}>
                    {String(i + 1).padStart(2, '0')}
                  </td>
                  <td style={{ padding: '8px 6px' }}>
                    <div style={{ fontFamily: FONT_DISPLAY, fontSize: 17, color: p.fg, lineHeight: 1.1, letterSpacing: ft.displayTracking }}>
                      {row.name}
                    </div>
                    <div style={{ fontFamily: FONT_MONO, fontSize: 9.5, color: p.sub2 }}>EIN {row.ein}</div>
                  </td>
                  <td style={{ padding: '8px 6px', color: p.sub }}>{row.cause}</td>
                  <td style={{ padding: '8px 6px', color: p.sub }}>{row.region}</td>
                  <td style={{ padding: '8px 6px' }}>
                    <Tag tone={row.walletIsZakat ? 'accent' : 'muted'} p={p}>{row.wallet}</Tag>
                  </td>
                  <td style={{ padding: '8px 6px' }}><RatingCell rating={row.impact} /></td>
                  <td style={{ padding: '8px 6px' }}><RatingCell rating={row.alignment} /></td>
                  <td style={{ padding: '8px 6px' }}>
                    <Figure size={16} color={p.accent}>{row.amalScore}</Figure>
                  </td>
                  <td style={{ padding: '8px 6px', fontFamily: FONT_MONO, fontSize: 11, color: p[riskTone(row.risk)] as string }}>
                    {row.risk}
                  </td>
                  <td style={{ padding: '8px 6px', fontFamily: FONT_MONO, fontSize: 10.5, color: p.sub }}>{row.verification}</td>
                  <td style={{ padding: '8px 6px', fontFamily: FONT_MONO, fontSize: 11, color: p.fg }}>
                    {row.programPct != null ? row.programPct : '—'}
                  </td>
                  <td style={{ padding: '8px 6px', color: p.sub2, fontSize: 14 }}>›</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 12, fontFamily: FONT_MONO, fontSize: 10.5, color: p.sub, letterSpacing: '0.06em' }}>
            Showing {rows.length} of {allRows.length}
          </div>
        </section>
      )}
    </>,
  );
};

export default GmgBrowse;

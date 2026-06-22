// Good Measure Giving — "Modern" motif Index / Browse (proof surface #2).
// Reachable via /browse. Dense Harvey-ball table on desktop,
// stacked cards on mobile, fed by the real charity list.

import React, { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCharities } from '../../hooks/useCharities';
import {
  GmgPalette,
  FontTheme,
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEMES,
  resolveFontVariant,
  type FontVariant,
} from './tokens';
import { Rating, ratingColor } from './rating';
import { HarveyBall, Tag, Kicker, Figure } from './primitives';
import { GmgNav, TypeSwitcher } from './chrome';
import { useIsMobile } from './useIsMobile';
import { adaptRow, GmgRow } from './charityAdapter';

const RANK: Record<Rating, number> = { Strong: 5, Good: 4, Moderate: 3, Fair: 2, Weak: 1 };
type SortKey = 'score' | 'impact' | 'alignment' | 'name';
type WalletFilter = 'all' | 'zakat' | 'sadaqah';

// Module-scope leaf/section components — defining these inside the parent's
// render body gives them a new identity each render, which remounts the search
// input (dropping focus on every keystroke). Kept out here so they're stable.

const RatingCell: React.FC<{ rating: Rating; p: GmgPalette }> = ({ rating, p }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
    <HarveyBall rating={rating} p={p} size={14} />
    <span style={{ fontSize: 11.5, color: ratingColor(rating, p) }}>{rating}</span>
  </span>
);

const FilterPills: React.FC<{
  p: GmgPalette;
  padX: number;
  query: string;
  setQuery: (v: string) => void;
  wallet: WalletFilter;
  setWallet: (v: WalletFilter) => void;
  sortBy: SortKey;
  setSortBy: (v: SortKey) => void;
  total: number;
  zakatCount: number;
}> = ({ p, padX, query, setQuery, wallet, setWallet, sortBy, setSortBy, total, zakatCount }) => {
  const sectionBorder = `1px solid ${p.rule}`;
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
  const pill = (active: boolean): React.CSSProperties => ({
    padding: '3px 9px',
    borderRadius: 99,
    cursor: 'pointer',
    fontFamily: FONT_MONO,
    fontSize: 9.5,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    border: `1px solid ${active ? p.chip : p.rule}`,
    background: active ? p.chip : 'transparent',
    color: active ? p.chipFg : p.sub,
  });
  return (
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
      <label htmlFor="gmg-browse-search" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
        Search charities
      </label>
      <input
        id="gmg-browse-search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search charities, EINs, causes…"
        style={inputStyle}
      />
      <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <Kicker p={p}>Wallet</Kicker>
        {(
          [
            ['all', `All ${total}`],
            ['zakat', `Zakat ${zakatCount}`],
            ['sadaqah', `Sadaqah ${total - zakatCount}`],
          ] as [WalletFilter, string][]
        ).map(([key, label]) => (
          <button key={key} onClick={() => setWallet(key)} style={pill(wallet === key)}>
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
          <button key={key} onClick={() => setSortBy(key)} style={pill(sortBy === key)}>
            {label}
          </button>
        ))}
      </span>
    </section>
  );
};

const SubHeader: React.FC<{ p: GmgPalette; padX: number; isMobile: boolean; ft: FontTheme; count: number }> = ({
  p,
  padX,
  isMobile,
  ft,
  count,
}) => (
  <section style={{ padding: `20px ${padX}px 14px`, borderBottom: `1px solid ${p.rule}` }}>
    <Kicker p={p}>The Index · {count} charities</Kicker>
    <h1 style={{ fontFamily: FONT_DISPLAY, fontSize: isMobile ? 34 : 46, margin: '4px 0 0', lineHeight: 1, letterSpacing: ft.displayTracking }}>
      Every charity, <em style={{ color: p.accent }}>weighed.</em>
    </h1>
  </section>
);

export const GmgBrowse: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const navigate = useNavigate();
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
  const [wallet, setWallet] = useState<WalletFilter>('all');
  const [sortBy, setSortBy] = useState<SortKey>('score');
  // Compare selection (up to 4).
  const [selected, setSelected] = useState<string[]>([]);
  const MAX_COMPARE = 4;
  const toggleSelect = (ein: string) =>
    setSelected((prev) =>
      prev.includes(ein)
        ? prev.filter((e) => e !== ein)
        : prev.length < MAX_COMPARE
          ? [...prev, ein]
          : prev,
    );

  const allRows: GmgRow[] = useMemo(
    () => (charities || []).map(adaptRow).filter((r) => r.ein),
    [charities],
  );
  const zakatCount = useMemo(() => allRows.filter((r) => r.walletIsZakat).length, [allRows]);

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
  const hrefFor = (ein: string) => `/charity/${ein}`;

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
      <SubHeader p={p} padX={padX} isMobile={isMobile} ft={ft} count={allRows.length} />
      <FilterPills
        p={p}
        padX={padX}
        query={query}
        setQuery={setQuery}
        wallet={wallet}
        setWallet={setWallet}
        sortBy={sortBy}
        setSortBy={setSortBy}
        total={allRows.length}
        zakatCount={zakatCount}
      />

      {isMobile ? (
        /* Mobile: stacked cards. Container tap navigates (mouse); the name is a
           real Link (keyboard/SPA); the compare control is a real checkbox. */
        <section style={{ padding: `12px ${padX}px 28px`, display: 'grid', gap: 10 }}>
          {rows.map((row, i) => (
            <div
              key={row.ein}
              onClick={() => navigate(hrefFor(row.ein))}
              style={{ border: sectionBorder, borderRadius: 8, padding: 14, background: p.bg2, cursor: 'pointer' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={selected.includes(row.ein)}
                  aria-label={`Select ${row.name} to compare`}
                  onClick={(e) => { e.stopPropagation(); toggleSelect(row.ein); }}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: FONT_MONO, fontSize: 10, color: selected.includes(row.ein) ? p.accent : p.sub2, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}
                >
                  <span style={{ width: 15, height: 15, borderRadius: 4, border: `1px solid ${selected.includes(row.ein) ? p.accent : p.rule2}`, background: selected.includes(row.ein) ? p.accent : 'transparent', display: 'inline-block' }} />
                  {String(i + 1).padStart(2, '0')} · Compare
                </button>
                <Tag tone={row.walletIsZakat ? 'accent' : 'muted'} p={p}>{row.wallet}</Tag>
              </div>
              <Link
                to={hrefFor(row.ein)}
                onClick={(e) => e.stopPropagation()}
                style={{ display: 'block', textDecoration: 'none', color: 'inherit' }}
              >
                <div style={{ fontFamily: FONT_DISPLAY, fontSize: 22, lineHeight: 1.1, marginTop: 4, letterSpacing: ft.displayTracking }}>
                  {row.name}
                </div>
              </Link>
              <div style={{ fontFamily: FONT_MONO, fontSize: 10, color: p.sub2, marginTop: 2 }}>
                {row.cause} · {row.region} · EIN {row.ein}
              </div>
              <div style={{ display: 'flex', gap: 18, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Kicker p={p}>Impact</Kicker>
                  <RatingCell rating={row.impact} p={p} />
                </span>
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Kicker p={p}>Alignment</Kicker>
                  <RatingCell rating={row.alignment} p={p} />
                </span>
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Kicker p={p}>GMG</Kicker>
                  <Figure size={16} color={p.accent}>{row.amalScore || '—'}</Figure>
                </span>
              </div>
            </div>
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
                <th style={{ padding: '10px 6px', width: 28 }} />
                <th style={{ padding: '10px 6px', width: 36 }}>№</th>
                <th style={{ padding: '10px 6px' }}>Charity / EIN</th>
                <th style={{ padding: '10px 6px', width: 150 }}>Cause</th>
                <th style={{ padding: '10px 6px', width: 110 }}>Region</th>
                <th style={{ padding: '10px 6px', width: 80 }}>Wallet</th>
                <th style={{ padding: '10px 6px', width: 110 }}>Impact</th>
                <th style={{ padding: '10px 6px', width: 110 }}>Alignment</th>
                <th style={{ padding: '10px 6px', width: 64 }}>GMG</th>
                <th style={{ padding: '10px 6px', width: 90 }}>Verif.</th>
                <th style={{ padding: '10px 6px', width: 52 }}>Prog.%</th>
                <th style={{ padding: '10px 6px', width: 24 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.ein}
                  onClick={() => navigate(hrefFor(row.ein))}
                  style={{ borderBottom: sectionBorder, background: selected.includes(row.ein) ? p.bg3 : i % 2 === 0 ? 'transparent' : p.bg2, cursor: 'pointer' }}
                >
                  <td style={{ padding: '8px 6px' }} onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(row.ein)}
                      onChange={() => toggleSelect(row.ein)}
                      aria-label={`Select ${row.name} to compare`}
                      style={{ accentColor: p.accent, cursor: 'pointer' }}
                    />
                  </td>
                  <td style={{ padding: '8px 6px', fontFamily: FONT_MONO, fontSize: 10.5, color: p.sub2 }}>
                    {String(i + 1).padStart(2, '0')}
                  </td>
                  <td style={{ padding: '8px 6px' }}>
                    <Link
                      to={hrefFor(row.ein)}
                      onClick={(e) => e.stopPropagation()}
                      style={{ textDecoration: 'none', color: 'inherit' }}
                    >
                      <div style={{ fontFamily: FONT_DISPLAY, fontSize: 17, color: p.fg, lineHeight: 1.1, letterSpacing: ft.displayTracking }}>
                        {row.name}
                      </div>
                    </Link>
                    <div style={{ fontFamily: FONT_MONO, fontSize: 9.5, color: p.sub2 }}>EIN {row.ein}</div>
                  </td>
                  <td style={{ padding: '8px 6px', color: p.sub }}>{row.cause}</td>
                  <td style={{ padding: '8px 6px', color: p.sub }}>{row.region}</td>
                  <td style={{ padding: '8px 6px' }}>
                    <Tag tone={row.walletIsZakat ? 'accent' : 'muted'} p={p}>{row.wallet}</Tag>
                  </td>
                  <td style={{ padding: '8px 6px' }}><RatingCell rating={row.impact} p={p} /></td>
                  <td style={{ padding: '8px 6px' }}><RatingCell rating={row.alignment} p={p} /></td>
                  <td style={{ padding: '8px 6px' }}>
                    <Figure size={16} color={p.accent}>{row.amalScore || '—'}</Figure>
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

      {/* Sticky compare bar */}
      {selected.length > 0 && (
        <div style={{ position: 'fixed', left: 0, right: 0, bottom: 0, zIndex: 50, display: 'flex', justifyContent: 'center', padding: 16, pointerEvents: 'none' }}>
          <div style={{ pointerEvents: 'auto', display: 'flex', alignItems: 'center', gap: 14, padding: '10px 14px 10px 18px', borderRadius: 99, background: p.chip, color: p.chipFg, boxShadow: '0 8px 28px rgba(0,0,0,0.28)' }}>
            <span style={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: '0.06em' }}>
              {selected.length} selected{selected.length >= MAX_COMPARE ? ' · max' : ''}
            </span>
            <button onClick={() => setSelected([])} style={{ background: 'transparent', border: 'none', color: p.chipFg, opacity: 0.7, fontSize: 11, cursor: 'pointer', fontFamily: FONT_MONO }}>
              Clear
            </button>
            {selected.length >= 2 ? (
              <Link to={`/compare?eins=${selected.join(',')}`} style={{ padding: '7px 16px', borderRadius: 99, background: p.bg, color: p.fg, fontSize: 12, fontWeight: 500, textDecoration: 'none' }}>
                Compare {selected.length} →
              </Link>
            ) : (
              <span style={{ padding: '7px 16px', borderRadius: 99, background: p.bg, color: p.sub2, fontSize: 12 }}>Pick 2+ to compare</span>
            )}
          </div>
        </div>
      )}
    </>,
  );
};

export default GmgBrowse;

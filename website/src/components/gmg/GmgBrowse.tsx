// Good Measure Giving — "Modern" motif Index / Browse (/browse).
// A scan of qualitative signals (Harvey balls) + facts rather than a single-score
// leaderboard: charity, cause, wallet, financial health, risk, donor fit, size.
// Sortable by any column; neutral A–Z default. Dense table on desktop, stacked
// cards on mobile. The numeric GMG score lives on each charity's page, not here.

import React, { useEffect, useMemo, useReducer, useState } from 'react';
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
import { HarveyBall, Tag, Kicker } from './primitives';
import { GmgNav } from './chrome';
import { GmgFooter } from './content';
import { useIsMobile } from './useIsMobile';
import { adaptRow, GmgRow } from './charityAdapter';
import { charityPath } from '../../lib/paths';
import { BrowseFacets } from './BrowseFacets';
import {
  facetReducer,
  applyFacets,
  facetStateToSearch,
  facetStateFromSearch,
  isFacetActive,
} from './facetState';

const RANK: Record<Rating, number> = { Strong: 5, Good: 4, Moderate: 3, Fair: 2, Weak: 1 };
const EVIDENCE_RANK: Record<string, number> = { Verified: 4, Established: 3, Building: 2, Early: 1 };
type SortKey = 'name' | 'cause' | 'overall' | 'finances' | 'risk' | 'donorFit' | 'programPct' | 'evidence' | 'size';
type SortDir = 'asc' | 'desc';

const ascByDefault = (k: SortKey): boolean => k === 'name' || k === 'cause';

// Annual revenue → compact money ($85K / $3.0M / $1.5B).
const fmtMoney = (n: number | null): string => {
  if (n == null) return '—';
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${Math.round(n / 1e3)}K`;
  return `$${Math.round(n)}`;
};

const titleCaseCause = (s: string): string =>
  s.replace(/[_&]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/\b\w/g, (m) => m.toUpperCase());

// Module-scope leaf components — defining these inside the parent's render body
// gives them a new identity each render, which remounts the search input (dropping
// focus on every keystroke). Kept out here so they're stable.

const RatingCell: React.FC<{ rating: Rating; p: GmgPalette; size?: number }> = ({ rating, p, size = 14 }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
    <HarveyBall rating={rating} p={p} size={size} />
    <span style={{ fontSize: 11.5, color: ratingColor(rating, p) }}>{rating}</span>
  </span>
);

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

// Sortable column descriptor. `tip` becomes a native hover tooltip on the header.
interface Col {
  key: SortKey;
  label: string;
  tip?: string;
  width?: number;
  align?: 'left' | 'right' | 'center';
}
const COLS: Col[] = [
  { key: 'cause', label: 'Cause', width: 150 },
  { key: 'overall', label: 'GMG', tip: 'Overall GMG rating — Impact + Alignment minus Risk, shown as a band rather than a precise score. Default sort. Blank = not scored yet.', width: 72, align: 'center' },
  { key: 'finances', label: 'Finances', tip: 'Financial health — reserves, program spending and stability. Strong = healthiest.', width: 120 },
  // A governance-completeness/red-flag SIGNAL, not the charity's full risk
  // assessment (that lives on its own page as a named, described risk
  // register — score_details.risks). Missing governance data can lower this
  // signal even when the full assessment finds no red flags — found via
  // manual QA: Against Malaria Foundation shows Weak here (unknown board
  // size) and LOW risk on its own page. Said explicitly rather than making
  // the two numbers agree, since browse's lightweight index doesn't carry
  // the full risk register to agree WITH — see bd for the real fix.
  { key: 'risk', label: 'Risk', tip: 'A lighter governance/red-flag signal, not the full risk assessment — missing governance data can lower it even with no red flags found. See the charity\'s own page for the complete, named risk assessment.', width: 120 },
  { key: 'donorFit', label: 'Donor fit', tip: 'Fit for Muslim donors — cause alignment and zakat signals. Strong = best fit.', width: 120 },
  { key: 'programPct', label: 'Program %', tip: 'Share of spending that went to programs in the latest filing. Blank = not reported.', width: 88, align: 'right' },
  { key: 'evidence', label: 'Evidence', tip: 'How well this charity\'s impact claims are evidenced — Verified, Established, Building or Early.', width: 100 },
  { key: 'size', label: 'Size', tip: 'Annual revenue from the latest filing.', width: 76, align: 'right' },
];

const SortableTh: React.FC<{
  col: Col;
  p: GmgPalette;
  sortBy: SortKey;
  sortDir: SortDir;
  onSort: (k: SortKey) => void;
}> = ({ col, p, sortBy, sortDir, onSort }) => {
  const active = sortBy === col.key;
  return (
    <th
      style={{ padding: '10px 6px', width: col.width, textAlign: col.align ?? 'left', cursor: 'pointer', userSelect: 'none', color: active ? p.fg : undefined }}
      title={col.tip}
      onClick={() => onSort(col.key)}
      aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      {col.label}
      {col.tip && <span style={{ color: p.sub2, marginLeft: 3 }}>ⓘ</span>}
      <span style={{ marginLeft: 4, color: active ? p.accent : 'transparent' }}>{sortDir === 'asc' ? '▲' : '▼'}</span>
    </th>
  );
};

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

  const [state, dispatch] = useReducer(
    facetReducer,
    undefined,
    () => facetStateFromSearch(typeof window === 'undefined' ? '' : window.location.search),
  );

  // Facet state is shareable but must never create a crawlable URL or a
  // history entry: replaceState only, and the prerender emits just /browse.
  // Merge into the existing query string rather than replacing it wholesale —
  // params this page doesn't own (utm_source, gclid, the ?type= font preview,
  // …) must survive both mount and every later facet change.
  //
  // Debounced: `query` lives in this same state, so every keystroke in the
  // search box would otherwise fire its own history.replaceState — browsers
  // rate-limit the history API and Safari has historically thrown
  // SecurityError past that limit. The cleanup below cancels a pending write
  // whenever state changes again before it fires, so a burst of keystrokes
  // (or facet clicks) collapses into one write, 300ms after things go quiet.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const timer = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      for (const k of ['q', 'wallet', 'scope', 'cause', 'asnaf', 'region', 'size', 'evidence']) params.delete(k);
      for (const [k, v] of new URLSearchParams(facetStateToSearch(state))) params.set(k, v);
      const qs = params.toString();
      const url = `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash}`;
      window.history.replaceState(window.history.state, '', url);
    }, 300);
    return () => clearTimeout(timer);
  }, [state]);

  // The static /browse/index.html is indexable and canonical. A filtered view is
  // the same page with a query string; ?type= previously leaked crawl budget
  // here, so tell a JS-rendering crawler explicitly not to index filtered states.
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const active = isFacetActive(state);
    const tag = document.querySelector('meta[name="robots"][data-gmg-facets]');
    if (active && !tag) {
      const newTag = document.createElement('meta');
      newTag.setAttribute('name', 'robots');
      newTag.setAttribute('content', 'noindex,follow');
      newTag.setAttribute('data-gmg-facets', '');
      document.head.appendChild(newTag);
    }
    return () => { document.querySelector('meta[name="robots"][data-gmg-facets]')?.remove(); };
  }, [state]);
  // Default: by overall GMG band (best first). It's a band, not a numeric rank,
  // and unscored charities fall to the bottom rather than getting a fake score.
  const [sortBy, setSortBy] = useState<SortKey>('overall');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const onSort = (k: SortKey) => {
    if (k === sortBy) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortBy(k);
      setSortDir(ascByDefault(k) ? 'asc' : 'desc');
    }
  };

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

  const rows = useMemo(() => {
    const r = applyFacets(allRows, state);
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...r].sort((a, b) => {
      let v = 0;
      switch (sortBy) {
        case 'name':
          v = a.name.localeCompare(b.name);
          break;
        case 'cause':
          v = (a.cause || '').localeCompare(b.cause || '');
          break;
        case 'overall':
          // Order by the underlying score (best-first) so within-band ordering is
          // sensible; the cell still shows only the band ball, never the number.
          v = a.amalScore - b.amalScore;
          break;
        case 'finances':
          v = RANK[a.financialHealth] - RANK[b.financialHealth];
          break;
        case 'risk':
          v = RANK[a.risk] - RANK[b.risk];
          break;
        case 'donorFit':
          v = RANK[a.donorFit] - RANK[b.donorFit];
          break;
        case 'programPct':
          v = (a.programPct ?? -1) - (b.programPct ?? -1);
          break;
        case 'evidence':
          v = (EVIDENCE_RANK[a.verification] ?? 0) - (EVIDENCE_RANK[b.verification] ?? 0);
          break;
        case 'size':
          v = (a.revenue ?? -1) - (b.revenue ?? -1);
          break;
      }
      v = v * dir;
      // Stable A–Z tiebreak within a band (never inverted by sort direction).
      if (v === 0 && sortBy !== 'name') v = a.name.localeCompare(b.name);
      return v;
    });
  }, [allRows, state, sortBy, sortDir]);

  const sectionBorder = `1px solid ${p.rule}`;
  const hrefFor = charityPath;

  const shell = (children: React.ReactNode) => (
    <div style={{ background: p.bg, color: p.fg, fontFamily: FONT_TEXT, minHeight: '100vh', ...fontVars }}>
      <GmgNav p={p} isMobile={isMobile} active="Browse" />
      {children}
      <GmgFooter p={p} isMobile={isMobile} />
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
      <BrowseFacets
        state={state}
        dispatch={dispatch}
        rows={allRows}
        p={p}
        padX={padX}
        isMobile={isMobile}
        total={allRows.length}
        resultCount={rows.length}
      />

      {rows.length === 0 ? (
        /* Without this, a search that matches nothing rendered bare column
           headers above the footer — no explanation, no way back. */
        <section style={{ padding: `48px ${padX}px 56px`, textAlign: 'center' }}>
          <p style={{ fontFamily: FONT_MONO, fontSize: 12, color: p.sub, margin: 0, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            No charities match
          </p>
          <p style={{ fontSize: 15, color: p.sub2, margin: '10px 0 20px' }}>
            {state.query.trim()
              ? <>Nothing in the index matches “{state.query.trim()}”.</>
              : 'No charities match the current filter.'}
          </p>
          <button
            type="button"
            onClick={() => dispatch({ type: 'clearAll' })}
            style={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', padding: '10px 18px', borderRadius: 999, border: `1px solid ${p.rule}`, background: 'transparent', color: p.fg, cursor: 'pointer' }}
          >
            Clear filters
          </button>
        </section>
      ) : isMobile ? (
        /* Mobile: stacked cards.

           Rebuilt because the phone layout had grown a hierarchy nobody chose.
           "Compare" — a secondary action — was the first thing in every card,
           above the charity's own name. The six signals sat in a flex-wrap row
           that broke 4 + 2 at 393px, so every card ended with a short orphan
           line and a ragged gap, and all six read at the same weight even
           though GMG is the headline verdict. EIN took a third of the meta
           line for a number nobody scans a list by.

           Now: name first, a fixed grid that cannot wrap raggedly at any phone
           width, GMG on its own row, and Compare demoted to the footer.
           Container tap navigates; the name is a real Link so keyboard and
           crawlers both work; the compare control is a real checkbox. */
        <section style={{ padding: `12px ${padX}px 28px`, display: 'grid', gap: 10 }}>
          {rows.map((row) => {
            const isSelected = selected.includes(row.ein);
            return (
              <div
                key={row.ein}
                data-charity-card={row.ein}
                onClick={() => navigate(hrefFor(row.ein))}
                style={{ border: sectionBorder, borderRadius: 8, padding: '13px 14px', background: p.bg2, cursor: 'pointer' }}
              >
                {/* Identity leads. */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                  <Link
                    to={hrefFor(row.ein)}
                    onClick={(e) => e.stopPropagation()}
                    style={{ display: 'block', textDecoration: 'none', color: 'inherit', flex: 1, minWidth: 0 }}
                  >
                    <div style={{ fontFamily: FONT_DISPLAY, fontSize: 21, lineHeight: 1.12, letterSpacing: ft.displayTracking }}>
                      {row.name}
                    </div>
                  </Link>
                  <span style={{ flexShrink: 0, marginTop: 1 }}>
                    <Tag tone={row.walletIsZakat ? 'accent' : 'muted'} p={p}>{row.wallet}</Tag>
                  </span>
                </div>

                {/* EIN lives on the detail page; a donor scans by cause and size. */}
                <div style={{ fontFamily: FONT_MONO, fontSize: 10.5, color: p.sub2, marginTop: 3 }}>
                  {titleCaseCause(row.cause)} · {fmtMoney(row.revenue)}
                </div>

                <div style={{ height: 1, background: p.rule, opacity: 0.6, margin: '11px 0 9px' }} />

                {/* The headline verdict, on its own line, paired with the one
                    number donors ask for first. */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                    <Kicker p={p}>GMG</Kicker>
                    {row.overall
                      ? <RatingCell rating={row.overall} p={p} size={20} />
                      : <span style={{ fontFamily: FONT_MONO, fontSize: 12.5, color: p.sub2 }}>—</span>}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 7, flexShrink: 0 }}>
                    <Kicker p={p}>Program %</Kicker>
                    <span style={{ fontFamily: FONT_MONO, fontSize: 12.5, color: p.fg }}>
                      {row.programPct == null ? '—' : `${row.programPct}%`}
                    </span>
                  </span>
                </div>

                {/* Three equal supporting signals. A fixed 3-column grid rather
                    than flex-wrap, so the row is identical on every card and at
                    every phone width instead of breaking wherever it happens to
                    run out of room. */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 10 }}>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                    <Kicker p={p}>Finances</Kicker>
                    <RatingCell rating={row.financialHealth} p={p} />
                  </span>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                    <Kicker p={p}>Risk</Kicker>
                    <RatingCell rating={row.risk} p={p} />
                  </span>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
                    <Kicker p={p}>Donor fit</Kicker>
                    <RatingCell rating={row.donorFit} p={p} />
                  </span>
                </div>

                {/* Footer: evidence stage, and Compare demoted to where a
                    secondary action belongs. Padding keeps the tap target at
                    44px without the control looking that large. */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, marginTop: 11 }}>
                  <Tag tone="muted" p={p}>{row.verification}</Tag>
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={isSelected}
                    aria-label={`Select ${row.name} to compare`}
                    onClick={(e) => { e.stopPropagation(); toggleSelect(row.ein); }}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: FONT_MONO, fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: isSelected ? p.accent : p.sub2, cursor: 'pointer', background: 'none', border: 'none', padding: '12px 2px 12px 12px', margin: '-12px -2px -12px -12px' }}
                  >
                    <span style={{ width: 15, height: 15, borderRadius: 4, border: `1px solid ${isSelected ? p.accent : p.rule2}`, background: isSelected ? p.accent : 'transparent', display: 'inline-block' }} />
                    Compare
                  </button>
                </div>
              </div>
            );
          })}
        </section>
      ) : (
        /* Desktop: dense, sortable table.
           The table needs ~960px, but the layout switches to it at 768px, so
           between those widths (tablet) it was pushing the whole page body
           sideways and cutting off the last column. Scroll it inside its own
           container instead — same treatment GmgCompare already uses. */
        <section style={{ padding: `0 ${padX}px 28px`, overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5, minWidth: 900 }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 2, background: p.bg }}>
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
                <th
                  style={{ padding: '10px 6px', cursor: 'pointer', userSelect: 'none', color: sortBy === 'name' ? p.fg : undefined }}
                  onClick={() => onSort('name')}
                  aria-sort={sortBy === 'name' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                >
                  Charity / EIN
                  <span style={{ marginLeft: 4, color: sortBy === 'name' ? p.accent : 'transparent' }}>
                    {sortDir === 'asc' ? '▲' : '▼'}
                  </span>
                </th>
                {/* Cause then Wallet (wallet is filter-only, not sortable) */}
                <SortableTh col={COLS[0]} p={p} sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
                <th style={{ padding: '10px 6px', width: 90 }} title="Zakat-eligible (the charity publicly accepts zakat) or Sadaqah.">
                  Wallet<span style={{ color: p.sub2, marginLeft: 3 }}>ⓘ</span>
                </th>
                {COLS.slice(1).map((col) => (
                  <SortableTh key={col.key} col={col} p={p} sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
                ))}
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
                  <td style={{ padding: '8px 6px', color: p.sub }}>{titleCaseCause(row.cause)}</td>
                  <td style={{ padding: '8px 6px' }}>
                    <Tag tone={row.walletIsZakat ? 'accent' : 'muted'} p={p}>{row.wallet}</Tag>
                  </td>
                  <td style={{ padding: '8px 6px', textAlign: 'center' }}>
                    {row.overall ? (
                      <RatingCell rating={row.overall} p={p} size={22} />
                    ) : (
                      <span style={{ fontFamily: FONT_MONO, fontSize: 11, color: p.sub2 }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: '8px 6px' }}><RatingCell rating={row.financialHealth} p={p} /></td>
                  <td style={{ padding: '8px 6px' }}><RatingCell rating={row.risk} p={p} /></td>
                  <td style={{ padding: '8px 6px' }}><RatingCell rating={row.donorFit} p={p} /></td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontFamily: FONT_MONO, fontSize: 11.5, color: p.fg }}>
                    {row.programPct == null ? '—' : `${row.programPct}%`}
                  </td>
                  <td style={{ padding: '8px 6px' }}>
                    <Tag tone="muted" p={p}>{row.verification}</Tag>
                  </td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontFamily: FONT_MONO, fontSize: 11.5, color: p.fg }}>
                    {fmtMoney(row.revenue)}
                  </td>
                  <td style={{ padding: '8px 6px', color: p.sub2, fontSize: 14 }}>›</td>
                </tr>
              ))}
            </tbody>
          </table>
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
              <Link to={`/compare/?eins=${selected.join(',')}`} style={{ padding: '7px 16px', borderRadius: 99, background: p.bg, color: p.fg, fontSize: 12, fontWeight: 500, textDecoration: 'none' }}>
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

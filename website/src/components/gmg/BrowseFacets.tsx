// The /browse filter bar — search, wallet, size, evidence, scope always
// visible, and a "More filters" expander for cause/region/asnaf. Deliberately
// styled as more of the same pill strip that was already there (`pill()` is
// lifted from the old `FilterPills` verbatim) rather than a new component
// bolted onto the page.

import React, { useMemo, useState } from 'react';
import { GmgPalette, FONT_TEXT, FONT_MONO } from './tokens';
import { Kicker } from './primitives';
import type { GmgRow, SizeBand } from './charityAdapter';
import {
  FacetState, FacetAction, FacetKey, Scope, WalletFilter,
  applyFacets, facetCounts, isFacetActive, CAUSE_KEYS, EVIDENCE_VALUES,
} from './facetState';
import { REGION_TAGS, ASNAF_TAGS } from './adapters/regions';

// Fixed display order + labels for size bands — facetState.ts keeps this
// vocabulary private (unlike CAUSE_KEYS/EVIDENCE_VALUES), so it's repeated
// here rather than imported.
const SIZE_LABELS: [SizeBand, string][] = [
  ['lt1m', '<$1M'],
  ['1to10m', '$1–10M'],
  ['10to100m', '$10–100M'],
  ['gte100m', '$100M+'],
];

interface FacetOption {
  key: string;
  label: string;
  count: number;
  selected: boolean;
  // Only set where the visible "{label} {count}" text collides with another
  // group's (e.g. Wallet's and Scope's "All" both read "All 166" by
  // default) — otherwise the button's accessible name is just its text, as
  // before.
  ariaLabel?: string;
}

// Module-scope so identity is stable across renders (see the note in
// GmgBrowse.tsx about leaf components remounting and dropping input focus).
const FacetGroup: React.FC<{
  label: string;
  p: GmgPalette;
  options: FacetOption[];
  pill: (active: boolean) => React.CSSProperties;
  onSelect: (key: string) => void;
}> = ({ label, p, options, pill, onSelect }) => {
  if (options.length === 0) return null;
  return (
    <span role="group" aria-label={label} style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
      <Kicker p={p}>{label}</Kicker>
      {options.map((opt) => (
        <button
          key={opt.key}
          type="button"
          aria-pressed={opt.selected}
          aria-label={opt.ariaLabel}
          onClick={() => onSelect(opt.key)}
          style={pill(opt.selected)}
        >
          {opt.label} {opt.count}
        </button>
      ))}
    </span>
  );
};

export const BrowseFacets: React.FC<{
  state: FacetState;
  dispatch: React.Dispatch<FacetAction>;
  rows: GmgRow[];
  p: GmgPalette;
  padX: number;
  isMobile: boolean;
  total: number;
  resultCount: number;
}> = ({ state, dispatch, rows, p, padX, isMobile, total, resultCount }) => {
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
    fontSize: 16,
    outline: 'none',
  };

  // Verbatim from the old FilterPills.
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

  const toggle = (facet: FacetKey) => (value: string) => dispatch({ type: 'toggle', facet, value });

  const walletOptions: FacetOption[] = useMemo(() => {
    const allCount = applyFacets(rows, { ...state, wallet: 'all' }).length;
    return [
      { key: 'all', label: 'All', ariaLabel: `Wallet: All ${allCount}`, count: allCount, selected: state.wallet === 'all' },
      { key: 'zakat', label: 'Zakat', count: applyFacets(rows, { ...state, wallet: 'zakat' }).length, selected: state.wallet === 'zakat' },
      { key: 'sadaqah', label: 'Sadaqah', count: applyFacets(rows, { ...state, wallet: 'sadaqah' }).length, selected: state.wallet === 'sadaqah' },
    ];
  }, [rows, state]);

  const scopeOptions: FacetOption[] = useMemo(() => {
    const allCount = applyFacets(rows, { ...state, scope: 'all' }).length;
    return [
      { key: 'all', label: 'All', ariaLabel: `Scope: All ${allCount}`, count: allCount, selected: state.scope === 'all' },
      { key: 'muslim', label: 'Muslim-led', count: applyFacets(rows, { ...state, scope: 'muslim' }).length, selected: state.scope === 'muslim' },
    ];
  }, [rows, state]);

  const sizeCounts = useMemo(() => facetCounts(rows, state, 'size'), [rows, state]);
  const sizeOptions: FacetOption[] = useMemo(
    () => SIZE_LABELS
      .map(([key, label]) => ({ key, label, count: sizeCounts[key] ?? 0, selected: state.size.includes(key) }))
      .filter((opt) => opt.count > 0 || opt.selected),
    [sizeCounts, state.size],
  );

  const evidenceCounts = useMemo(() => facetCounts(rows, state, 'evidence'), [rows, state]);
  const evidenceOptions: FacetOption[] = useMemo(
    () => EVIDENCE_VALUES
      .map((key) => ({ key, label: key, count: evidenceCounts[key] ?? 0, selected: state.evidence.includes(key) }))
      .filter((opt) => opt.count > 0 || opt.selected),
    [evidenceCounts, state.evidence],
  );

  // Cause enum keys don't carry a human label of their own — derive one from
  // any row that has it, rather than hardcoding a second copy of the 16 names.
  const causeLabels = useMemo(() => {
    const map: Record<string, string> = {};
    for (const row of rows) {
      if (row.causeKey && !(row.causeKey in map)) map[row.causeKey] = row.cause;
    }
    return map;
  }, [rows]);

  const causeCounts = useMemo(() => facetCounts(rows, state, 'cause'), [rows, state]);
  const causeOptions: FacetOption[] = useMemo(
    () => CAUSE_KEYS
      .map((key) => ({ key, label: causeLabels[key] ?? key, count: causeCounts[key] ?? 0, selected: state.cause.includes(key) }))
      .filter((opt) => opt.count > 0 || opt.selected),
    [causeCounts, causeLabels, state.cause],
  );

  const regionCounts = useMemo(() => facetCounts(rows, state, 'region'), [rows, state]);
  const regionOptions: FacetOption[] = useMemo(
    () => Object.keys(REGION_TAGS)
      .map((key) => ({ key, label: REGION_TAGS[key], count: regionCounts[key] ?? 0, selected: state.region.includes(key) }))
      .filter((opt) => opt.count > 0 || opt.selected),
    [regionCounts, state.region],
  );

  const asnafCounts = useMemo(() => facetCounts(rows, state, 'asnaf'), [rows, state]);
  const asnafOptions: FacetOption[] = useMemo(
    () => Object.keys(ASNAF_TAGS)
      .map((key) => ({ key, label: ASNAF_TAGS[key], count: asnafCounts[key] ?? 0, selected: state.asnaf.includes(key) }))
      .filter((opt) => opt.count > 0 || opt.selected),
    [asnafCounts, state.asnaf],
  );

  const moreCount = state.cause.length + state.asnaf.length + state.region.length;
  // Starts open when a facet inside it is already selected — except on
  // mobile, where the expander stays closed by default regardless (it still
  // shows the count) so the page doesn't open onto a long pill list.
  const [open, setOpen] = useState(() => !isMobile && moreCount > 0);

  const showClearAll = isFacetActive(state) || state.query.trim() !== '';

  return (
    <section
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: `10px ${padX}px`,
        background: p.bg2,
        borderBottom: sectionBorder,
        fontSize: 12,
      }}
    >
      {/* Row 1: search + result count */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
        <label htmlFor="gmg-browse-search" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
          Search charities
        </label>
        <input
          id="gmg-browse-search"
          value={state.query}
          onChange={(e) => dispatch({ type: 'query', value: e.target.value })}
          placeholder="Search charities, EINs, causes…"
          style={inputStyle}
        />
        <span style={{ flex: 1 }} />
        <span aria-live="polite" style={{ fontFamily: FONT_MONO, fontSize: 9.5, letterSpacing: '0.06em', color: p.sub2, textTransform: 'uppercase' }}>
          {resultCount} of {total}{!isMobile ? ' · Click a column to sort' : ''}
        </span>
      </div>

      {/* Row 2: always-visible facets */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
        <FacetGroup label="Wallet" p={p} pill={pill} options={walletOptions} onSelect={(v) => dispatch({ type: 'wallet', value: v as WalletFilter })} />
        <FacetGroup label="Size" p={p} pill={pill} options={sizeOptions} onSelect={toggle('size')} />
        <FacetGroup label="Evidence" p={p} pill={pill} options={evidenceOptions} onSelect={toggle('evidence')} />
        <FacetGroup label="Scope" p={p} pill={pill} options={scopeOptions} onSelect={(v) => dispatch({ type: 'scope', value: v as Scope })} />
        {showClearAll && (
          <button
            type="button"
            onClick={() => dispatch({ type: 'clearAll' })}
            style={{
              fontFamily: FONT_MONO,
              fontSize: 9.5,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              textDecoration: 'underline',
              background: 'transparent',
              border: 'none',
              color: p.sub2,
              cursor: 'pointer',
              padding: '3px 4px',
            }}
          >
            Clear all
          </button>
        )}
      </div>

      {/* Row 3: collapsed cause / region / asnaf */}
      <div>
        <button
          type="button"
          aria-expanded={open}
          aria-controls="gmg-browse-more-filters"
          onClick={() => setOpen((o) => !o)}
          style={pill(open)}
        >
          More filters{moreCount > 0 ? ` (${moreCount})` : ''} {open ? '▴' : '▾'}
        </button>
        {open && (
          <div id="gmg-browse-more-filters" style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
            <FacetGroup label="Cause" p={p} pill={pill} options={causeOptions} onSelect={toggle('cause')} />
            <FacetGroup label="Where it works" p={p} pill={pill} options={regionOptions} onSelect={toggle('region')} />
            <FacetGroup label="Zakat asnaf" p={p} pill={pill} options={asnafOptions} onSelect={toggle('asnaf')} />
          </div>
        )}
      </div>
    </section>
  );
};

export default BrowseFacets;

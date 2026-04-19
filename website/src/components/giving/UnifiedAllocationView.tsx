/**
 * UnifiedAllocationView — the unified record (M4 rewrite).
 *
 * Design shift from the old spreadsheet:
 *  - Every charity has an intended amount, a given amount, and a status
 *    (intended → sent → confirmed). Status is shown as a colored chip.
 *  - No percent math, no drag-drop, no bucket sliders. Category membership
 *    is just a visual grouping — `bucketId` on the assignment.
 *  - Per-charity actions ("Log donation" / "Mark confirmed") mutate profile
 *    state directly via parent callbacks; giving-history writes happen in
 *    AddDonationModal with a writeBatch that also updates the assignment.
 *
 * Preserved: category grouping + collapsible, custom charity entry, zakat
 * lens toggle, zakat anniversary prompt, mobile-card / desktop-table layouts,
 * Starter Plan fallback. Per-row rendering lives in ./CharityRecordRow.tsx.
 * Pure status transitions live in ../../utils/recordStatus.ts.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CalendarDays, Calculator, Check, ChevronDown, Download, Plus, Search, X,
} from 'lucide-react';
import type { GivingBucket, GivingHistoryEntry } from '../../../types';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { SHOW_AMAL_SCORE } from '../../featureFlags';
import { useCharities } from '../../hooks/useCharities';
import { ALL_TAGS, TAGS, pickBestTag } from '../../constants/givingTags';
import { getWalletType } from '../../utils/walletUtils';
import { StarterPlan } from './StarterPlan';
import { ZakatEstimator } from './ZakatEstimator';
import { CharityRecordRow } from './CharityRecordRow';
import type { CharityRecordHistoryEntry } from './CharityRecordRow';
import type { CharitySummary } from '../../hooks/useCharities';
import type { AssignmentStatus } from '../../utils/recordStatus';

// --------------------------------------------------------------------------
// Constants / types
// --------------------------------------------------------------------------

const COLORS = [
  '#5ba88a', '#5b8fb8', '#8b7cb8', '#7a9e6e',
  '#7aab7a', '#8a9eb8', '#a8849e', '#7ab5a8',
];

/** Soft-cap: charities after this index in a bucket collapse into "Saved for later". */
const ACTIVE_CAP = 5;

interface BookmarkedCharity {
  ein: string;
  name: string;
  amalScore: number | null;
  walletTag: string | null;
  causeTags: string[] | null;
  notes?: string | null;
}

/** v2 assignment fields surfaced to this component (subset of CharityBucketAssignment). */
export interface UnifiedAssignmentInput {
  ein: string;
  bucketId: string;
  status?: AssignmentStatus;
  intended?: number;
  given?: number;
}

interface UnifiedAllocationViewProps {
  initialBuckets?: GivingBucket[];
  initialAssignments?: UnifiedAssignmentInput[];
  targetAmount?: number | null;
  bookmarkedCharities: BookmarkedCharity[];
  donations: GivingHistoryEntry[];
  /** Save buckets + target (no more % splits). */
  onSave: (buckets: GivingBucket[], targetAmount: number | null) => Promise<void>;
  onLogDonation: (charityEin?: string, charityName?: string) => void;
  onAddCharity?: (charityEin: string, charityName: string, bucketId: string) => Promise<void>;
  onRemoveCharity?: (charityEin: string) => Promise<void>;
  onSetCharityIntended?: (ein: string, amount: number) => Promise<void>;
  onMarkConfirmed?: (ein: string) => Promise<void>;
  allCharities?: CharitySummary[];
  zakatAnniversary?: string | null;
  onSaveAnniversary?: (date: string | null) => Promise<void>;
  /** Optional CSV export trigger. Rendered next to the Add Charity / Category buttons when provided. */
  onExportCSV?: () => void;
}

type LocalBucket = { id: string; tagId: string; label: string; color: string };
type RowCharity = {
  ein: string; name: string; bucketColor?: string;
  status: AssignmentStatus; intended: number; given: number;
};

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------

function fmt(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`;
  return `$${n}`;
}
function isZakatEligible(walletTag: string | null): boolean {
  return getWalletType(walletTag) === 'zakat';
}

// --------------------------------------------------------------------------
// Sub-component: anniversary prompt
// --------------------------------------------------------------------------

function ZakatAnniversaryPrompt({
  isDark, onSave,
}: { isDark: boolean; onSave: (date: string | null) => Promise<void> }) {
  const [date, setDate] = useState('');
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <div className={`flex items-center gap-3 px-4 py-2.5 border-b ${isDark ? 'bg-slate-800/30 border-slate-700' : 'bg-amber-50/50 border-amber-100'}`}>
      <CalendarDays className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
      <span className={`text-xs ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>When is your zakat anniversary?</span>
      <input
        type="date"
        value={date}
        onChange={e => setDate(e.target.value)}
        className={`text-xs px-2 py-1 rounded border ${isDark ? 'bg-slate-800 border-slate-600 text-white' : 'bg-white border-slate-300 text-slate-900'} focus:outline-none focus:ring-1 focus:ring-emerald-500`}
      />
      {date && (
        <button onClick={() => void onSave(date)} className="text-xs font-medium px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700">Save</button>
      )}
      <button
        onClick={() => setDismissed(true)}
        className={`ml-auto p-1 rounded ${isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-500'}`}
        aria-label="Dismiss zakat anniversary prompt"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------
// Main component
// --------------------------------------------------------------------------

export function UnifiedAllocationView({
  initialBuckets = [],
  initialAssignments = [],
  targetAmount: initialTarget,
  bookmarkedCharities,
  donations,
  onSave,
  onLogDonation,
  onAddCharity,
  onRemoveCharity,
  onSetCharityIntended,
  onMarkConfirmed,
  allCharities,
  zakatAnniversary,
  onSaveAnniversary,
  onExportCSV,
}: UnifiedAllocationViewProps) {
  const { isDark } = useLandingTheme();
  const { charities } = useCharities();

  // Local state ------------------------------------------------------------
  const [target, setTarget] = useState(initialTarget?.toString() || '');
  const [saving, setSaving] = useState(false);
  const [showEstimator, setShowEstimator] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [showCharitySearch, setShowCharitySearch] = useState(false);
  const [charitySearchQuery, setCharitySearchQuery] = useState('');
  const [recentlyAdded, setRecentlyAdded] = useState<Set<string>>(new Set());
  const [customCategoryName, setCustomCategoryName] = useState('');
  const [zakatLens, setZakatLens] = useState(false);
  const [collapsedBuckets, setCollapsedBuckets] = useState<Set<string>>(new Set());
  const [expandedSaved, setExpandedSaved] = useState<Set<string>>(new Set());
  const [buckets, setBuckets] = useState<LocalBucket[]>([]);
  const targetInputRef = useRef<HTMLInputElement | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasInitialized = useRef(false);

  // Seed once from props ---------------------------------------------------
  useEffect(() => {
    if (hasInitialized.current) return;
    const hasData = (initialTarget ?? 0) > 0 || initialBuckets.length > 0 || initialAssignments.length > 0;
    if (!hasData) return;
    setTarget(initialTarget && initialTarget > 0 ? initialTarget.toString() : '');
    setBuckets(initialBuckets.map((b, i) => {
      const tag = ALL_TAGS.find(t => t.id === b.tags?.[0]) || { id: b.tags?.[0] || '', label: b.name };
      return { id: b.id, tagId: tag.id, label: b.name || tag.label, color: b.color || COLORS[i % COLORS.length] };
    }));
    hasInitialized.current = true;
  }, [initialTarget, initialBuckets, initialAssignments]);

  useEffect(() => () => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
  }, []);

  const targetNum = parseInt(target, 10) || 0;

  // Assignment maps --------------------------------------------------------
  const charityToBucket = useMemo(() => {
    const m = new Map<string, string>();
    for (const a of initialAssignments) m.set(a.ein, a.bucketId);
    return m;
  }, [initialAssignments]);

  const charityIntendedMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of initialAssignments) m.set(a.ein, Number(a.intended) || 0);
    return m;
  }, [initialAssignments]);

  const charityGivenMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of initialAssignments) {
      if (typeof a.given === 'number') m.set(a.ein, a.given);
    }
    // Fallback to donation sums for any ein not already filled in.
    const byEin = new Map<string, number>();
    for (const d of donations) {
      if (!d.charityEin) continue;
      byEin.set(d.charityEin, (byEin.get(d.charityEin) ?? 0) + d.amount);
    }
    for (const [ein, total] of byEin) if (!m.has(ein)) m.set(ein, total);
    return m;
  }, [initialAssignments, donations]);

  const charityStatusMap = useMemo(() => {
    const m = new Map<string, AssignmentStatus>();
    for (const a of initialAssignments) m.set(a.ein, (a.status as AssignmentStatus) || 'intended');
    return m;
  }, [initialAssignments]);

  // History-per-charity — pre-sliced for row-level inline expansion. Sorted by
  // date desc so the most recent entry shows first. No additional Firestore
  // read — reuses the `donations` prop already passed in.
  const charityHistoryMap = useMemo(() => {
    const m = new Map<string, CharityRecordHistoryEntry[]>();
    for (const d of donations) {
      if (!d.charityEin) continue;
      const entry: CharityRecordHistoryEntry = {
        id: d.id,
        date: d.date,
        amount: d.amount,
        category: d.category,
        receiptReceived: d.receiptReceived,
      };
      const list = m.get(d.charityEin);
      if (list) list.push(entry);
      else m.set(d.charityEin, [entry]);
    }
    for (const list of m.values()) {
      list.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    }
    return m;
  }, [donations]);

  const lastYearZakat = useMemo(() => {
    const ly = new Date().getFullYear() - 1;
    return donations.filter(d => d.category === 'zakat' && d.zakatYear === ly).reduce((s, d) => s + d.amount, 0);
  }, [donations]);

  // Aggregates -------------------------------------------------------------
  const visibleCharities = useMemo(
    () => bookmarkedCharities.filter(c => !zakatLens || isZakatEligible(c.walletTag)),
    [bookmarkedCharities, zakatLens],
  );
  const totalIntended = useMemo(
    () => visibleCharities.reduce((s, c) => s + (charityIntendedMap.get(c.ein) || 0), 0),
    [visibleCharities, charityIntendedMap],
  );
  const totalGiven = useMemo(
    () => visibleCharities.reduce((s, c) => s + (charityGivenMap.get(c.ein) || 0), 0),
    [visibleCharities, charityGivenMap],
  );
  const unallocated = targetNum - totalIntended;

  // Tag counts for Category picker ---------------------------------------
  const tagCounts = useMemo(() => {
    const c = new Map<string, number>();
    charities
      .filter(ch => !zakatLens || isZakatEligible((ch as any).amalEvaluation?.wallet_tag))
      .forEach(ch => ((ch as any).causeTags || []).forEach((t: string) => c.set(t, (c.get(t) || 0) + 1)));
    return c;
  }, [charities, zakatLens]);
  const usedTags = new Set(buckets.map(b => b.tagId));

  // Save plumbing ----------------------------------------------------------
  const triggerSave = useCallback((nextBuckets?: LocalBucket[], nextTarget?: number) => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    const b = nextBuckets ?? buckets;
    const t = nextTarget ?? targetNum;
    saveTimeoutRef.current = setTimeout(async () => {
      setSaving(true);
      try {
        const fb = b.map(x => ({
          id: x.id, name: x.label, tags: [x.tagId], percentage: 0, color: x.color,
        }));
        await onSave(fb, t > 0 ? t : null);
      } finally { setSaving(false); }
    }, 300);
  }, [buckets, targetNum, onSave]);

  // Bucket operations -----------------------------------------------------
  const addBucket = (tag: { id: string; label: string }) => {
    const id = crypto.randomUUID();
    const next = [...buckets, { id, tagId: tag.id, label: tag.label, color: COLORS[buckets.length % COLORS.length] }];
    setBuckets(next);
    triggerSave(next);
    setCollapsedBuckets(prev => { const n = new Set(prev); n.delete(id); return n; });
  };
  const addCustomCategory = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const tagId = `custom-${trimmed.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
    addBucket({ id: tagId, label: trimmed });
    setCustomCategoryName('');
  };
  const removeBucket = (id: string) => {
    const next = buckets.filter(b => b.id !== id);
    setBuckets(next);
    triggerSave(next);
  };
  const setBucketLabel = (id: string, label: string) =>
    setBuckets(prev => prev.map(b => (b.id === id ? { ...b, label } : b)));
  const toggleCollapse = (id: string) =>
    setCollapsedBuckets(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleSaved = (id: string) =>
    setExpandedSaved(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  // Row action handlers ---------------------------------------------------
  const handleSetIntended = useCallback((ein: string, amt: number) => {
    if (onSetCharityIntended) void onSetCharityIntended(ein, Math.max(0, amt));
  }, [onSetCharityIntended]);
  const handleMarkConfirmed = useCallback((ein: string) => {
    if (onMarkConfirmed) void onMarkConfirmed(ein);
  }, [onMarkConfirmed]);
  const handleRemove = useCallback((ein: string) => {
    if (onRemoveCharity) void onRemoveCharity(ein);
  }, [onRemoveCharity]);

  const handleTargetBlur = () => triggerSave();
  const handleTargetKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
      triggerSave();
    }
  };

  // Auto-pick a bucket for a newly-added charity.
  const pickBucketForCharity = (causeTags: string[]): string => {
    const existing = buckets.find(b => causeTags.includes(b.tagId));
    if (existing) return existing.id;
    const primary = pickBestTag(causeTags);
    if (!primary) return '';
    const tagDef = ALL_TAGS.find(t => t.id === primary);
    if (!tagDef) return '';
    const newBucket: LocalBucket = {
      id: crypto.randomUUID(), tagId: tagDef.id, label: tagDef.label,
      color: COLORS[buckets.length % COLORS.length],
    };
    const next = [...buckets, newBucket];
    setBuckets(next);
    triggerSave(next);
    return newBucket.id;
  };

  // Charities-per-bucket helpers -----------------------------------------
  const charitiesForBucket = useCallback((bucketId: string | null, color?: string): RowCharity[] =>
    bookmarkedCharities
      .filter(c => (charityToBucket.get(c.ein) ?? null) === bucketId)
      .filter(c => !zakatLens || isZakatEligible(c.walletTag))
      .map(c => ({
        ein: c.ein, name: c.name, bucketColor: color,
        status: charityStatusMap.get(c.ein) || 'intended',
        intended: charityIntendedMap.get(c.ein) || 0,
        given: charityGivenMap.get(c.ein) || 0,
      })),
  [bookmarkedCharities, charityToBucket, charityStatusMap, charityIntendedMap, charityGivenMap, zakatLens]);

  const unassignedCharities = useMemo(() => charitiesForBucket(null, undefined), [charitiesForBucket]);
  const splitSoftCap = (rows: RowCharity[]) =>
    rows.length <= ACTIVE_CAP ? { active: rows, saved: [] as RowCharity[] } :
    { active: rows.slice(0, ACTIVE_CAP), saved: rows.slice(ACTIVE_CAP) };

  // Shared row props (eliminate boilerplate in the category/unassigned render) --
  const rowProps = {
    isDark,
    onSetIntended: handleSetIntended,
    onLogDonation,
    onMarkConfirmed: handleMarkConfirmed,
    onRemove: onRemoveCharity ? handleRemove : undefined,
  };

  // --------------------------------------------------------------------
  // Small inline renderers to keep the main return scannable
  // --------------------------------------------------------------------

  const BucketHeader = ({ b, count }: { b: LocalBucket; count: number }) => {
    const collapsed = collapsedBuckets.has(b.id);
    return (
      <div
        className={`flex items-center justify-between gap-2 px-3 py-2 ${isDark ? 'bg-slate-800/60' : 'bg-slate-50'} border-b`}
        style={{ borderLeft: `4px solid ${b.color}`, borderBottomColor: isDark ? undefined : `${b.color}25` }}
      >
        <button
          type="button"
          onClick={() => toggleCollapse(b.id)}
          className="flex items-center gap-2 min-w-0 flex-1 text-left"
          aria-expanded={!collapsed}
        >
          <ChevronDown className={`w-4 h-4 transition-transform ${collapsed ? '-rotate-90' : ''} ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: b.color }} />
          <input
            type="text"
            value={b.label}
            onChange={e => setBucketLabel(b.id, e.target.value)}
            onBlur={handleTargetBlur}
            onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
            onClick={e => e.stopPropagation()}
            className={`font-semibold text-sm truncate bg-transparent border-0 focus:outline-none p-0 max-w-[14rem] ${isDark ? 'text-slate-100' : 'text-slate-800'}`}
            aria-label={`Rename ${b.label}`}
          />
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-semibold border"
            style={{ backgroundColor: `${b.color}15`, borderColor: `${b.color}30`, color: b.color }}
          >
            {count} {count === 1 ? 'charity' : 'charities'}
          </span>
        </button>
        <button
          type="button"
          onClick={() => removeBucket(b.id)}
          className={`p-1.5 rounded-md opacity-60 hover:opacity-100 ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}
          aria-label={`Remove ${b.label}`}
        >
          <X className={`w-3.5 h-3.5 ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`} />
        </button>
      </div>
    );
  };

  const EmptyBucketRow = () => (
    <div className="px-3 py-3 flex items-center gap-3">
      <button
        type="button"
        onClick={() => { setShowCharitySearch(true); setCharitySearchQuery(''); }}
        className={`inline-flex items-center gap-1 text-[11px] font-semibold px-3 py-1.5 rounded-lg border ${isDark ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20' : 'text-emerald-700 border-emerald-200 bg-emerald-50 hover:bg-emerald-100'}`}
      >
        <Plus className="w-3 h-3" /> Add charity
      </button>
      <span className={`text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>No charities in this category yet.</span>
    </div>
  );

  const renderRows = (rows: RowCharity[], desktop: boolean) =>
    rows.map((row, i) => (
      <CharityRecordRow
        key={row.ein}
        charity={row}
        desktop={desktop}
        isEvenRow={i % 2 === 0}
        history={charityHistoryMap.get(row.ein)}
        {...rowProps}
      />
    ));

  const renderBucket = (b: LocalBucket) => {
    const rows = charitiesForBucket(b.id, b.color);
    const collapsed = collapsedBuckets.has(b.id);
    const { active, saved } = splitSoftCap(rows);
    const savedOpen = expandedSaved.has(b.id);
    const savedToggleLabel = (open: boolean, n: number) => `${open ? '▾' : '▸'} Saved for later (${n})`;
    return (
      <div key={b.id} className={`rounded-lg border overflow-hidden ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
        <BucketHeader b={b} count={rows.length} />
        {!collapsed && (
          <>
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className={`text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-400'} border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
                    <th className="w-1" />
                    <th className="px-2.5 py-2 text-left">Charity</th>
                    <th className="px-2.5 py-2 text-right w-28">Intended</th>
                    <th className="px-2.5 py-2 text-right w-24">Given</th>
                    <th className="px-2.5 py-2 text-left w-28">Status</th>
                    <th className="px-2.5 py-2 text-right w-48">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr><td colSpan={6}><EmptyBucketRow /></td></tr>
                  ) : (
                    <>
                      {renderRows(active, true)}
                      {saved.length > 0 && (
                        <tr>
                          <td colSpan={6}>
                            <button
                              type="button"
                              onClick={() => toggleSaved(b.id)}
                              className={`w-full text-left px-3 py-2 text-[11px] font-medium border-t ${isDark ? 'border-slate-800 text-slate-400 hover:bg-slate-800/40' : 'border-slate-100 text-slate-500 hover:bg-slate-50'}`}
                              aria-expanded={savedOpen}
                            >
                              {savedToggleLabel(savedOpen, saved.length)}
                            </button>
                          </td>
                        </tr>
                      )}
                      {saved.length > 0 && savedOpen && renderRows(saved, true)}
                    </>
                  )}
                </tbody>
              </table>
            </div>
            <div className="sm:hidden p-2 space-y-2">
              {rows.length === 0 && <EmptyBucketRow />}
              {renderRows(active, false)}
              {saved.length > 0 && (
                <button
                  type="button"
                  onClick={() => toggleSaved(b.id)}
                  className={`w-full text-left px-2 py-1.5 text-[11px] font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}
                >
                  {savedToggleLabel(savedOpen, saved.length)}
                </button>
              )}
              {saved.length > 0 && savedOpen && renderRows(saved, false)}
            </div>
          </>
        )}
      </div>
    );
  };

  const renderUnassigned = () => {
    if (unassignedCharities.length === 0) return null;
    return (
      <div className={`rounded-lg border overflow-hidden ${isDark ? 'border-amber-500/30' : 'border-amber-200'}`}>
        <div className={`flex items-center gap-2 px-3 py-2 border-b ${isDark ? 'bg-amber-500/10 border-amber-500/20 text-amber-300' : 'bg-amber-50 border-amber-100 text-amber-700'}`}>
          <div className="w-2 h-2 rounded-full bg-amber-500" />
          <span className="text-[10px] font-bold tracking-wider">NEEDS CATEGORY ({unassignedCharities.length})</span>
        </div>
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full"><tbody>{renderRows(unassignedCharities, true)}</tbody></table>
        </div>
        <div className="sm:hidden p-2 space-y-2">{renderRows(unassignedCharities, false)}</div>
      </div>
    );
  };

  // --------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------
  return (
    <div className={`rounded-xl border overflow-hidden text-sm shadow-sm ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`}>
      {/* Header bar */}
      <div className={`flex flex-col gap-2 px-3 py-2.5 border-b sm:flex-row sm:items-center sm:justify-between ${isDark ? 'border-slate-700 bg-gradient-to-r from-slate-800/50 to-slate-900' : 'border-slate-200 bg-gradient-to-r from-slate-50 to-white'}`}>
        <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:gap-3">
          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md ${isDark ? 'bg-emerald-500/10' : 'bg-emerald-50'}`}>
              <span className={`text-[10px] font-bold tracking-wide ${isDark ? 'text-emerald-500' : 'text-emerald-600'}`}>ZAKAT</span>
            </div>
            <div data-tour="giving-target" className={`flex items-center border rounded-lg px-3 py-1.5 shadow-sm ${isDark ? 'bg-slate-800/80 border-slate-700' : 'bg-white border-slate-200'}`}>
              <span className={`text-sm font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>$</span>
              <input
                ref={targetInputRef}
                type="text"
                inputMode="numeric"
                value={target}
                onChange={e => setTarget(e.target.value.replace(/\D/g, ''))}
                onBlur={handleTargetBlur}
                onKeyDown={handleTargetKey}
                placeholder="e.g. 10,000"
                className={`w-20 py-0.5 bg-transparent text-lg font-bold focus:outline-none ${isDark ? 'text-white placeholder-slate-600' : 'text-slate-900 placeholder-slate-300'}`}
                aria-label="Annual zakat target"
              />
            </div>
            <button
              onClick={() => setShowEstimator(true)}
              className={`p-1.5 rounded-lg transition-colors ${isDark ? 'text-slate-500 hover:text-emerald-400 hover:bg-slate-800' : 'text-slate-400 hover:text-emerald-600 hover:bg-slate-100'}`}
              aria-label="Open zakat estimator"
            >
              <Calculator className="w-4 h-4" />
            </button>
          </div>
          {targetNum > 0 && (
            <div className="flex items-center gap-3 flex-wrap">
              <div className={`h-2 w-28 rounded-full overflow-hidden shadow-inner ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all rounded-full"
                  style={{ width: `${Math.min(100, Math.round((totalGiven / targetNum) * 100))}%` }}
                />
              </div>
              <span className={`text-xs font-medium tabular-nums ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                <span className="text-emerald-500 font-semibold">{fmt(totalGiven)}</span>
                <span className="opacity-50 mx-1">/</span>
                {fmt(targetNum)}
              </span>
              <button
                onClick={() => setZakatLens(z => !z)}
                aria-pressed={zakatLens}
                className={`text-[11px] font-medium px-2.5 py-1 rounded-md border transition-all ${
                  zakatLens
                    ? (isDark ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-emerald-50 text-emerald-600 border-emerald-200')
                    : (isDark ? 'text-slate-500 border-slate-700 hover:text-slate-400 hover:bg-slate-800' : 'text-slate-400 border-slate-200 hover:text-slate-600 hover:bg-slate-50')
                }`}
              >
                {zakatLens ? 'Showing zakat-eligible only' : 'Hide sadaqah'}
              </button>
              {totalIntended > 0 && (
                <span className={`text-[11px] font-medium px-2.5 py-1 rounded-md border ${
                  unallocated === 0
                    ? (isDark ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-emerald-600 border-emerald-200 bg-emerald-50')
                    : unallocated < 0
                    ? (isDark ? 'text-blue-400 border-blue-500/30 bg-blue-500/10' : 'text-blue-500 border-blue-200 bg-blue-50')
                    : (isDark ? 'text-amber-400 border-amber-500/30 bg-amber-500/10' : 'text-amber-600 border-amber-200 bg-amber-50')
                }`}>
                  {unallocated === 0 ? `${fmt(totalIntended)} planned` : unallocated < 0 ? `${fmt(Math.abs(unallocated))} over` : `${fmt(unallocated)} to plan`}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex w-full flex-wrap items-center gap-1.5 sm:w-auto sm:justify-end">
          {saving && (
            <span className={`text-[10px] px-2 py-1 rounded ${isDark ? 'text-emerald-400 bg-emerald-500/10' : 'text-emerald-600 bg-emerald-50'}`}>Saving...</span>
          )}
          {onExportCSV && donations.length > 0 && (
            <button
              data-testid="record-export-csv"
              onClick={onExportCSV}
              title="Export donation history as CSV"
              className={`text-[11px] font-medium px-3 py-1.5 rounded-lg border flex items-center gap-1 ${
                isDark
                  ? 'text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300'
                  : 'text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700'
              }`}
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Export CSV</span>
              <span className="sm:hidden">CSV</span>
            </button>
          )}
          <button
            data-tour="giving-add-charity"
            onClick={() => { setShowCharitySearch(s => !s); setCharitySearchQuery(''); setRecentlyAdded(new Set()); }}
            className={`text-[11px] font-semibold px-3 py-1.5 rounded-lg border flex items-center gap-1 ${
              showCharitySearch
                ? (isDark ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' : 'bg-blue-50 text-blue-600 border-blue-200')
                : (isDark ? 'bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-500' : 'bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700')
            }`}
          >
            <Plus className="w-3.5 h-3.5" /> Add Charity
          </button>
          <button
            data-tour="giving-add-category"
            onClick={() => setShowPicker(s => !s)}
            className={`text-[11px] font-medium px-3 py-1.5 rounded-lg border flex items-center gap-1 ${
              showPicker
                ? (isDark ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-emerald-50 text-emerald-600 border-emerald-200')
                : (isDark ? 'text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300' : 'text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700')
            }`}
          >
            <Plus className="w-3.5 h-3.5" /> Category
          </button>
        </div>
      </div>

      {targetNum > 0 && !zakatAnniversary && onSaveAnniversary && (
        <ZakatAnniversaryPrompt isDark={isDark} onSave={onSaveAnniversary} />
      )}

      {/* Charity search */}
      {showCharitySearch && (
        <div className={`px-4 py-4 border-b ${isDark ? 'border-slate-700 bg-slate-800/30' : 'border-slate-200 bg-blue-50/30'}`}>
          <div className="flex items-center gap-2 mb-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={charitySearchQuery}
                onChange={e => setCharitySearchQuery(e.target.value)}
                placeholder="Search charities to add..."
                autoFocus
                className={`w-full pl-9 pr-3 py-2 text-sm rounded-lg border shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 ${isDark ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-400'}`}
                aria-label="Search charities"
              />
              <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
            </div>
            <button
              onClick={() => { setShowCharitySearch(false); setCharitySearchQuery(''); setRecentlyAdded(new Set()); }}
              className={`p-2 rounded-lg ${isDark ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-slate-200 text-slate-500'}`}
              aria-label="Close charity search"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          {charitySearchQuery.length >= 2 ? (
            <SearchResults
              isDark={isDark}
              query={charitySearchQuery}
              charities={charities}
              bookmarkedEins={new Set(bookmarkedCharities.map(c => c.ein))}
              recentlyAdded={recentlyAdded}
              setRecentlyAdded={setRecentlyAdded}
              onAddCharity={onAddCharity}
              pickBucketForCharity={pickBucketForCharity}
            />
          ) : (
            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Type at least 2 characters to search. You can add multiple charities.
            </p>
          )}
        </div>
      )}

      {/* Category picker */}
      {showPicker && (
        <div className={`px-4 py-4 border-b ${isDark ? 'border-slate-700 bg-slate-800/30' : 'border-slate-200 bg-emerald-50/30'}`}>
          <div className="flex items-center gap-2 mb-3">
            <input
              type="text"
              value={customCategoryName}
              onChange={e => setCustomCategoryName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') addCustomCategory(customCategoryName); }}
              placeholder="Type a custom category name..."
              className={`flex-1 text-sm px-3 py-2 rounded-lg border shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 ${isDark ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500' : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-emerald-400'}`}
              aria-label="Custom category name"
            />
            <button
              onClick={() => addCustomCategory(customCategoryName)}
              disabled={!customCategoryName.trim()}
              className={`text-[11px] font-semibold px-3 py-2 rounded-lg ${
                customCategoryName.trim()
                  ? (isDark ? 'bg-emerald-600 text-white hover:bg-emerald-500' : 'bg-emerald-600 text-white hover:bg-emerald-700')
                  : (isDark ? 'bg-slate-700 text-slate-500 cursor-not-allowed' : 'bg-slate-200 text-slate-400 cursor-not-allowed')
              }`}
            >
              Create
            </button>
          </div>
          <div className={`text-[10px] font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Or pick from tags
          </div>
          <div className="space-y-3">
            {Object.entries(TAGS).map(([group, tags]) => (
              <div key={group} className="flex flex-wrap items-start gap-2">
                <span className={`text-[10px] font-bold uppercase tracking-wider w-24 pt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{group}</span>
                <div className="flex-1 flex flex-wrap gap-1.5">
                  {tags.map(tag => {
                    const used = usedTags.has(tag.id);
                    const cnt = tagCounts.get(tag.id) || 0;
                    return (
                      <button
                        key={tag.id}
                        onClick={() => !used && cnt > 0 && addBucket(tag)}
                        disabled={used || cnt === 0}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
                          used
                            ? (isDark ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' : 'bg-emerald-50 border-emerald-200 text-emerald-600')
                            : cnt === 0
                            ? (isDark ? 'border-slate-800 text-slate-700 cursor-not-allowed' : 'border-slate-100 text-slate-300 cursor-not-allowed')
                            : (isDark ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-800 shadow-sm')
                        }`}
                      >
                        {tag.label}
                        {cnt > 0 && !used && <span className={`tabular-nums ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{cnt}</span>}
                        {used && <Check className="w-3 h-3" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Body: categories + unassigned */}
      {targetNum > 0 && buckets.length > 0 && (
        <div className="p-3 space-y-3">
          {buckets.map(renderBucket)}
          {renderUnassigned()}
        </div>
      )}

      {/* Fallback: StarterPlan when user has target but no buckets */}
      {targetNum > 0 && buckets.length === 0 && allCharities && allCharities.length > 0 && (
        <div className={`px-4 py-4 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
          <StarterPlan target={targetNum} charities={allCharities} onAccepted={() => window.location.reload()} />
        </div>
      )}

      {/* Empty state: no target, no bookmarks */}
      {!targetNum && bookmarkedCharities.length === 0 && (
        <div className={`px-6 py-12 text-center ${isDark ? 'bg-slate-800/20' : 'bg-slate-50/50'}`}>
          <p className={`text-sm font-medium mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Set your zakat target</p>
          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Enter your target amount above to start planning.</p>
        </div>
      )}

      {/* Empty state: no target, have bookmarks */}
      {!targetNum && bookmarkedCharities.length > 0 && (
        <div className={`px-6 py-8 ${isDark ? 'bg-slate-800/20' : 'bg-slate-50/50'}`}>
          <p className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            Your saved charities ({bookmarkedCharities.length}):
          </p>
          <ul className="space-y-2 mb-4">
            {bookmarkedCharities.map(c => (
              <li key={c.ein} className={`flex items-center justify-between px-3 py-2 rounded-lg border ${isDark ? 'bg-slate-700/50 border-slate-600' : 'bg-white border-slate-200'}`}>
                <Link
                  to={`/charity/${c.ein.replace(/^(\d{2})(\d+)$/, '$1-$2')}`}
                  className={`text-sm font-medium hover:underline ${isDark ? 'text-slate-200' : 'text-slate-800'}`}
                >
                  {c.name}
                </Link>
                {onRemoveCharity && (
                  <button
                    onClick={() => void onRemoveCharity(c.ein)}
                    className={`p-1 rounded-md ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`}
                    aria-label={`Remove ${c.name}`}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </li>
            ))}
          </ul>
          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Set a zakat target above to start planning.</p>
        </div>
      )}

      <ZakatEstimator
        isOpen={showEstimator}
        onClose={() => setShowEstimator(false)}
        onUseAmount={(amount) => { setTarget(String(amount)); triggerSave(); }}
        lastYearZakat={lastYearZakat}
      />
    </div>
  );
}

// --------------------------------------------------------------------------
// Search results sub-component (extracted to keep the main function lean)
// --------------------------------------------------------------------------

function SearchResults({
  isDark, query, charities, bookmarkedEins, recentlyAdded, setRecentlyAdded,
  onAddCharity, pickBucketForCharity,
}: {
  isDark: boolean;
  query: string;
  charities: any[];
  bookmarkedEins: Set<string>;
  recentlyAdded: Set<string>;
  setRecentlyAdded: React.Dispatch<React.SetStateAction<Set<string>>>;
  onAddCharity?: (ein: string, name: string, bucketId: string) => Promise<void>;
  pickBucketForCharity: (causeTags: string[]) => string;
}) {
  const results = charities
    .filter((c: any) => c.ein && c.name.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 12);

  const addCustomRow = (
    <div
      className={`flex items-center justify-between px-3 py-2.5 ${results.length > 0 ? `border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}` : ''} ${isDark ? 'hover:bg-slate-700/50' : 'hover:bg-slate-50'}`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <Plus className={`w-3.5 h-3.5 shrink-0 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
        <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Add "<span className="font-medium">{query}</span>" as custom charity
        </span>
      </div>
      <button
        onClick={async () => {
          if (!onAddCharity) return;
          const customId = `custom-${crypto.randomUUID()}`;
          await onAddCharity(customId, query.trim(), '');
          setRecentlyAdded(prev => new Set(prev).add(customId));
        }}
        className={`text-[11px] px-3 py-1.5 rounded-lg font-semibold shadow-sm ${isDark ? 'bg-emerald-600 text-white hover:bg-emerald-500' : 'bg-emerald-500 text-white hover:bg-emerald-600'}`}
      >
        + Add
      </button>
    </div>
  );

  return (
    <div className={`max-h-64 overflow-y-auto rounded-lg border shadow-sm ${isDark ? 'border-slate-700 bg-slate-800/50' : 'border-slate-200 bg-white'}`}>
      {results.map((c: any, i: number) => {
        const alreadyAdded = bookmarkedEins.has(c.ein) || recentlyAdded.has(c.ein);
        return (
          <div
            key={c.ein}
            className={`flex items-center justify-between px-3 py-2.5 ${i !== results.length - 1 ? `border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}` : ''} ${alreadyAdded ? (isDark ? 'bg-emerald-500/5' : 'bg-emerald-50/50') : (isDark ? 'hover:bg-slate-700/50' : 'hover:bg-slate-50')}`}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <span className={`text-sm font-medium truncate ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{c.name}</span>
              {SHOW_AMAL_SCORE && (
                <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-md font-semibold border ${isDark ? 'bg-slate-700 border-slate-600 text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-500'}`}>
                  {(c as any).amalScore || '—'}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0 ml-2">
              {alreadyAdded ? (
                <span className={`inline-flex items-center gap-1 text-[11px] px-3 py-1.5 rounded-lg font-semibold ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                  <Check className="w-3.5 h-3.5" /> Added
                </span>
              ) : (
                <button
                  onClick={async () => {
                    if (!onAddCharity) return;
                    const causeTags = (c as any).causeTags || [];
                    const bucketId = pickBucketForCharity(causeTags);
                    await onAddCharity(c.ein, c.name, bucketId);
                    setRecentlyAdded(prev => new Set(prev).add(c.ein));
                  }}
                  className={`text-[11px] px-3 py-1.5 rounded-lg font-semibold shadow-sm ${isDark ? 'bg-emerald-600 text-white hover:bg-emerald-500' : 'bg-emerald-500 text-white hover:bg-emerald-600'}`}
                >
                  + Add
                </button>
              )}
            </div>
          </div>
        );
      })}
      {addCustomRow}
    </div>
  );
}

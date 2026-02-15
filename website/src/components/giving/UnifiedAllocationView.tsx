/**
 * UnifiedAllocationView - Smart Spreadsheet
 *
 * Design: Airtable-style inline editing
 * - Auto-save on blur/enter (no save button)
 * - All fields inline-editable
 * - Bidirectional % ↔ target editing
 * - Subtle hover states, clean typography
 */

import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Plus, X, Check, GripVertical, ChevronDown, ArrowRight } from 'lucide-react';
import {
  DndContext,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useCharities } from '../../hooks/useCharities';
import { getWalletType } from '../../utils/walletUtils';
import type { GivingBucket, GivingHistoryEntry } from '../../../types';

interface BookmarkedCharity {
  ein: string;
  name: string;
  amalScore: number | null;
  walletTag: string | null;
  causeTags: string[] | null;
  notes?: string | null;
}

interface CharityAssignment {
  ein: string;
  bucketId: string;
}

interface UnifiedAllocationViewProps {
  initialBuckets?: GivingBucket[];
  initialAssignments?: CharityAssignment[];
  targetAmount?: number | null;
  bookmarkedCharities: BookmarkedCharity[];
  donations: GivingHistoryEntry[];
  charityTargets?: Map<string, number>;
  onSave: (buckets: GivingBucket[], targetAmount: number | null, assignments: CharityAssignment[]) => Promise<void>;
  onLogDonation: (charityEin?: string, charityName?: string) => void;
  onAddCharity?: (charityEin: string, charityName: string, bucketId: string) => Promise<void>;
  onRemoveCharity?: (charityEin: string) => Promise<void>;
  onSetCharityTarget?: (ein: string, amount: number) => Promise<void>;
}

const TAGS = {
  geography: [
    { id: 'palestine', label: 'Palestine' },
    { id: 'pakistan', label: 'Pakistan' },
    { id: 'afghanistan', label: 'Afghanistan' },
    { id: 'bangladesh', label: 'Bangladesh' },
    { id: 'india', label: 'India' },
    { id: 'kashmir', label: 'Kashmir' },
    { id: 'somalia', label: 'Somalia' },
    { id: 'sudan', label: 'Sudan' },
    { id: 'syria', label: 'Syria' },
    { id: 'yemen', label: 'Yemen' },
    { id: 'jordan', label: 'Jordan' },
    { id: 'lebanon', label: 'Lebanon' },
    { id: 'egypt', label: 'Egypt' },
    { id: 'indonesia', label: 'Indonesia' },
    { id: 'myanmar', label: 'Myanmar' },
    { id: 'kenya', label: 'Kenya' },
    { id: 'nigeria', label: 'Nigeria' },
    { id: 'ethiopia', label: 'Ethiopia' },
    { id: 'haiti', label: 'Haiti' },
    { id: 'usa', label: 'USA' },
    { id: 'international', label: 'International' },
    { id: 'conflict-zone', label: 'Conflict Zones' },
  ],
  cause: [
    { id: 'emergency-response', label: 'Emergency' },
    { id: 'direct-relief', label: 'Direct Relief' },
    { id: 'food', label: 'Food' },
    { id: 'water-sanitation', label: 'Water' },
    { id: 'medical', label: 'Medical' },
    { id: 'shelter', label: 'Shelter' },
    { id: 'clothing', label: 'Clothing' },
    { id: 'educational', label: 'Education' },
    { id: 'vocational', label: 'Vocational' },
    { id: 'psychosocial', label: 'Mental Health' },
    { id: 'legal-aid', label: 'Legal Aid' },
    { id: 'advocacy', label: 'Advocacy' },
    { id: 'research', label: 'Research' },
    { id: 'grantmaking', label: 'Grantmaking' },
    { id: 'capacity-building', label: 'Capacity Building' },
    { id: 'long-term-development', label: 'Development' },
    { id: 'systemic-change', label: 'Systemic Change' },
    { id: 'faith-based', label: 'Faith-Based' },
  ],
  population: [
    { id: 'refugees', label: 'Refugees' },
    { id: 'orphans', label: 'Orphans' },
    { id: 'women', label: 'Women' },
    { id: 'youth', label: 'Youth' },
    { id: 'disabled', label: 'Disabled' },
    { id: 'low-income', label: 'Low Income' },
    { id: 'converts', label: 'Converts' },
    { id: 'fuqara', label: 'Fuqara' },
    { id: 'masakin', label: 'Masakin' },
    { id: 'fisabilillah', label: 'Fi Sabilillah' },
  ],
};

const ALL_TAGS = [...TAGS.geography, ...TAGS.cause, ...TAGS.population];
const COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16'];
const PERCENT_DECIMALS = 2;
const PERCENT_EPSILON = 0.01;

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function roundPercent(value: number): number {
  return Math.round(value * (10 ** PERCENT_DECIMALS)) / (10 ** PERCENT_DECIMALS);
}

function parsePercentInput(raw: string): number {
  const sanitized = raw.replace(/[^0-9.]/g, '');
  const [whole, ...fractionParts] = sanitized.split('.');
  const normalized = fractionParts.length > 0 ? `${whole || '0'}.${fractionParts.join('')}` : whole;
  const parsed = Number.parseFloat(normalized);
  if (!Number.isFinite(parsed)) return 0;
  return roundPercent(clampPercent(parsed));
}

function formatPercent(value: number): string {
  const rounded = roundPercent(value);
  if (Number.isInteger(rounded)) return rounded.toString();
  return rounded.toFixed(PERCENT_DECIMALS).replace(/\.?0+$/, '');
}

// Draggable charity row
function DraggableCharityRow({
  charity,
  bucketId,
  bucketColor,
  given,
  target,
  isDark,
  onLogDonation,
  onRemove,
  onSetTarget,
  dimmed = false,
}: {
  charity: BookmarkedCharity;
  bucketId: string | null;
  bucketColor?: string;
  given: number;
  target?: number;
  isDark: boolean;
  onLogDonation: (ein: string, name: string) => void;
  onRemove?: (ein: string) => void;
  onSetTarget?: (ein: string, amount: number) => void;
  dimmed?: boolean;
}) {
  const [localTarget, setLocalTarget] = useState<string>(target ? String(target) : '');
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: charity.ein,
    data: { charity, bucketId },
  });

  // Sync local state when prop changes
  useEffect(() => {
    setLocalTarget(target ? String(target) : '');
  }, [target]);

  const style = transform ? {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.4 : dimmed ? 0.4 : 1,
  } : dimmed ? { opacity: 0.4 } : undefined;

  const wt = getWalletType(charity.walletTag);
  const isZakat = wt === 'zakat';
  const cell = `px-3 py-2.5 text-[13px] ${isDark ? 'text-slate-300' : 'text-slate-700'}`;
  const border = isDark ? 'border-slate-800/50' : 'border-slate-100';
  const inputStyle = `bg-transparent border-0 focus:outline-none focus:ring-0 p-0 ${isDark ? 'text-slate-200 placeholder-slate-600' : 'text-slate-700 placeholder-slate-300'}`;

  const handleTargetBlur = () => {
    const num = parseInt(localTarget.replace(/\D/g, '')) || 0;
    if (onSetTarget) {
      onSetTarget(charity.ein, num);
    }
  };

  const handleTargetKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  return (
    <tr
      ref={setNodeRef}
      style={style}
      className={`hidden sm:table-row border-b ${border} group transition-all ${isDragging ? 'z-50 shadow-lg' : ''} ${isDark ? 'hover:bg-slate-800/40' : 'hover:bg-slate-50'} ${dimmed ? 'pointer-events-auto' : ''}`}
    >
      <td className={`${cell} w-0 pr-0`} style={{ borderLeft: bucketColor ? `4px solid ${bucketColor}40` : undefined }}>
        <button {...listeners} {...attributes} className={`cursor-grab active:cursor-grabbing p-1 rounded-md opacity-100 sm:opacity-30 sm:group-hover:opacity-100 transition-opacity ${isDark ? 'hover:bg-slate-700' : 'hover:bg-slate-200'}`}>
          <GripVertical className="w-3.5 h-3.5" />
        </button>
      </td>
      <td className={`${cell} pl-1`}>
        <Link to={`/charity/${charity.ein}`} className={`hover:underline font-medium ${isDark ? 'text-slate-200 hover:text-white' : 'text-slate-700 hover:text-slate-900'}`}>{charity.name}</Link>
      </td>
      <td className={`${cell} text-right`}>
        <span className={`text-[10px] px-2 py-0.5 rounded-md font-bold border ${
          wt === 'zakat'
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600'
            : isDark
            ? 'bg-slate-800 border-slate-700 text-slate-400'
            : 'bg-slate-100 border-slate-200 text-slate-500'
        }`}>
          {charity.amalScore || '—'}
        </span>
      </td>
      <td className={`${cell} text-right`}>
        <div className={`inline-flex items-center ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          <span className="text-[11px] mr-0.5">$</span>
          <input
            type="text"
            inputMode="numeric"
            value={localTarget}
            onChange={e => setLocalTarget(e.target.value.replace(/\D/g, ''))}
            onBlur={handleTargetBlur}
            onKeyDown={handleTargetKeyDown}
            className={`w-16 text-right ${inputStyle} text-[13px] tabular-nums`}
            placeholder="—"
          />
        </div>
      </td>
      <td className={`${cell} text-right tabular-nums`}>
        <span className={given > 0 ? 'font-semibold text-emerald-600' : isDark ? 'text-slate-600' : 'text-slate-300'}>{given > 0 ? fmt(given) : '—'}</span>
      </td>
      <td className={`${cell} text-right`}>
        <div className="flex items-center justify-end gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onLogDonation(charity.ein, charity.name)}
            className={`text-[11px] font-semibold px-2.5 py-1 rounded-md border transition-colors ${
              isDark
                ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20'
                : 'text-emerald-600 border-emerald-200 bg-emerald-50 hover:bg-emerald-100'
            }`}
          >
            + Log
          </button>
          {onRemove && (
            <button
              onClick={() => onRemove(charity.ein)}
              className={`p-1.5 rounded-md transition-colors ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}
              title="Remove from saved"
            >
              <X className={`w-3.5 h-3.5 ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`} />
            </button>
          )}
        </div>
      </td>
      <td className={cell}></td>
    </tr>
  );
}

function MobileCharityAllocationRow({
  charity,
  given,
  target,
  categoryTarget,
  currentBucketId,
  bucketOptions,
  isDark,
  onLogDonation,
  onSetTarget,
  onMoveCharity,
  onRemove,
}: {
  charity: BookmarkedCharity;
  given: number;
  target?: number;
  categoryTarget: number;
  currentBucketId: string | null;
  bucketOptions: Array<{ id: string; label: string }>;
  isDark: boolean;
  onLogDonation: (ein: string, name: string) => void;
  onSetTarget?: (ein: string, amount: number) => void | Promise<void>;
  onMoveCharity?: (ein: string, bucketId: string | null) => void;
  onRemove?: (ein: string) => void | Promise<void>;
}) {
  const [localTarget, setLocalTarget] = useState<string>(target ? String(target) : '');
  const inputStyle = `bg-transparent border-0 focus:outline-none focus:ring-0 p-0 ${isDark ? 'text-slate-200 placeholder-slate-600' : 'text-slate-700 placeholder-slate-300'}`;
  const currentTarget = target || 0;
  const shareOfCategory = categoryTarget > 0 ? roundPercent((currentTarget / categoryTarget) * 100) : 0;

  useEffect(() => {
    setLocalTarget(target ? String(target) : '');
  }, [target]);

  const commitTarget = () => {
    if (!onSetTarget) return;
    const amount = parseInt(localTarget.replace(/\D/g, '')) || 0;
    void onSetTarget(charity.ein, amount);
  };

  const onTargetKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  const onBucketChange = (value: string) => {
    if (!onMoveCharity) return;
    const nextBucketId = value || null;
    if (nextBucketId === currentBucketId) return;
    onMoveCharity(charity.ein, nextBucketId);
  };

  return (
    <div className={`rounded-md border px-2 py-1.5 ${isDark ? 'border-slate-700 bg-slate-800/40' : 'border-slate-200 bg-slate-50/60'}`}>
      <div className="flex items-center justify-between gap-2">
        <Link
          to={`/charity/${charity.ein}`}
          className={`min-w-0 truncate text-[12px] font-medium ${isDark ? 'text-slate-200 hover:text-white' : 'text-slate-700 hover:text-slate-900'} hover:underline`}
        >
          {charity.name}
        </Link>
        <div className="shrink-0 flex items-center gap-1">
          <button
            onClick={() => onLogDonation(charity.ein, charity.name)}
            className={`text-[10px] font-semibold px-2 py-1 rounded-md border transition-colors ${
              isDark
                ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20'
                : 'text-emerald-600 border-emerald-200 bg-emerald-50 hover:bg-emerald-100'
            }`}
          >
            + Log
          </button>
          {onRemove && (
            <button
              onClick={() => void onRemove(charity.ein)}
              className={`p-1 rounded-md transition-colors ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}
              aria-label={`Remove ${charity.name}`}
            >
              <X className={`w-3.5 h-3.5 ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`} />
            </button>
          )}
        </div>
      </div>
      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className={`text-[10px] ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
          {categoryTarget > 0
            ? `Given ${fmt(given)} • ${formatPercent(shareOfCategory)}% of category`
            : `Given ${fmt(given)}`}
        </span>
        <div className={`inline-flex items-center px-2 py-1 rounded-md border ${isDark ? 'border-slate-700 bg-slate-900/60' : 'border-slate-200 bg-white'}`}>
          <span className={`text-[11px] mr-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>$</span>
          <input
            type="text"
            inputMode="numeric"
            value={localTarget}
            onChange={e => setLocalTarget(e.target.value.replace(/\D/g, ''))}
            onBlur={commitTarget}
            onKeyDown={onTargetKeyDown}
            className={`w-14 text-right ${inputStyle} text-[12px] font-semibold tabular-nums`}
            placeholder="0"
            aria-label={`Target for ${charity.name}`}
          />
        </div>
      </div>
      {onMoveCharity && bucketOptions.length > 0 && (
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <span className={`text-[10px] ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Category</span>
          <select
            value={currentBucketId || ''}
            onChange={e => onBucketChange(e.target.value)}
            className={`max-w-[10rem] text-[11px] rounded-md border px-2 py-1 ${
              isDark
                ? 'bg-slate-900 border-slate-700 text-slate-300'
                : 'bg-white border-slate-200 text-slate-700'
            }`}
            aria-label={`Category for ${charity.name}`}
          >
            <option value="">Needs category</option>
            {bucketOptions.map(option => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

// Droppable category zone
function DroppableCategory({ id, color, children, isDark }: { id: string; color: string; children: React.ReactNode; isDark: boolean }) {
  const { isOver, setNodeRef } = useDroppable({ id });

  return (
    <tbody
      ref={setNodeRef}
      className={`transition-all ${isOver ? (isDark ? 'bg-emerald-500/10' : 'bg-emerald-50/80') : ''}`}
      style={{ borderLeft: isOver ? `3px solid ${color}` : undefined }}
    >
      {children}
    </tbody>
  );
}

// Ghost suggestion row - faint row for suggested charity
function GhostSuggestionRow({
  charity,
  isDark,
  onAdd,
}: {
  charity: { ein: string; name: string; amalScore: number | null };
  isDark: boolean;
  onAdd: () => void;
}) {
  const cell = `px-3 py-2 text-[13px]`;

  return (
    <tr
      onClick={onAdd}
      className={`hidden sm:table-row border-b border-dashed cursor-pointer transition-all group ${
        isDark
          ? 'border-slate-700/50 text-slate-600 hover:text-slate-300 hover:bg-emerald-500/5'
          : 'border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-emerald-50/50'
      }`}
    >
      <td className={`${cell} w-0 pr-0`}>
        <Plus className={`w-3.5 h-3.5 opacity-40 group-hover:opacity-100 ${isDark ? 'group-hover:text-emerald-400' : 'group-hover:text-emerald-500'}`} />
      </td>
      <td className={`${cell} pl-1 italic font-medium`}>
        {charity.name}
      </td>
      <td className={`${cell} text-right`}>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-medium opacity-50 group-hover:opacity-80 ${isDark ? 'bg-slate-800 border border-slate-700' : 'bg-slate-100 border border-slate-200'}`}>
          {charity.amalScore || '—'}
        </span>
      </td>
      <td className={cell}></td>
      <td className={cell}></td>
      <td className={cell}></td>
      <td className={`${cell} text-right`}>
        <span className={`text-[10px] font-semibold px-2 py-1 rounded-md opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity ${
          isDark ? 'text-emerald-400 bg-emerald-500/10' : 'text-emerald-600 bg-emerald-50'
        }`}>+ Add</span>
      </td>
    </tr>
  );
}

// Droppable uncategorized zone
function DroppableUncategorized({ children, isDark, isActive }: { children: React.ReactNode; isDark: boolean; isActive: boolean }) {
  const { isOver, setNodeRef } = useDroppable({ id: 'uncategorized' });

  return (
    <div
      ref={setNodeRef}
      className={`border-t transition-colors ${
        isOver
          ? isDark ? 'border-amber-500/50 bg-amber-500/10' : 'border-amber-300 bg-amber-100/50'
          : isDark ? 'border-amber-500/20' : 'border-amber-100'
      } ${isActive && !isOver ? (isDark ? 'border-dashed' : 'border-dashed') : ''}`}
    >
      {children}
    </div>
  );
}

function fmt(n: number): string {
  if (n >= 1000) return `$${(n/1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`;
  return `$${n}`;
}

export function UnifiedAllocationView({
  initialBuckets = [],
  initialAssignments = [],
  targetAmount: initialTarget,
  bookmarkedCharities,
  donations,
  charityTargets,
  onSave,
  onLogDonation,
  onAddCharity,
  onRemoveCharity,
  onSetCharityTarget,
}: UnifiedAllocationViewProps) {
  const { isDark } = useLandingTheme();
  const { charities } = useCharities();

  const [showPicker, setShowPicker] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showCharitySearch, setShowCharitySearch] = useState(false);
  const [charitySearchQuery, setCharitySearchQuery] = useState('');
  const [zakatLens, setZakatLens] = useState(false);
  const [collapsedBuckets, setCollapsedBuckets] = useState<Set<string>>(new Set());
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);
  const [target, setTarget] = useState(initialTarget?.toString() || '');
  const [saving, setSaving] = useState(false);
  const [buckets, setBuckets] = useState<Array<{
    id: string; tagId: string; label: string; percent: number; color: string;
  }>>([]);
  const [assignments, setAssignments] = useState<Map<string, string>>(new Map());
  const [charityTargetDrafts, setCharityTargetDrafts] = useState<Map<string, number>>(new Map());
  const targetInputRef = useRef<HTMLInputElement | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasInitialized = useRef(false);

  // Sync profile props once when we actually have saved data.
  useEffect(() => {
    if (hasInitialized.current) return;
    const hasInitialData =
      (initialTarget ?? 0) > 0 ||
      initialBuckets.length > 0 ||
      initialAssignments.length > 0;
    if (!hasInitialData) return;

    setTarget(initialTarget && initialTarget > 0 ? initialTarget.toString() : '');
    setBuckets(initialBuckets.map((b, i) => {
      const tag = ALL_TAGS.find(t => t.id === b.tags?.[0]) || { id: b.tags?.[0] || '', label: b.name };
      return { id: b.id, tagId: tag.id, label: tag.label, percent: b.percentage || 0, color: b.color || COLORS[i % COLORS.length] };
    }));

    const map = new Map<string, string>();
    initialAssignments.forEach(a => map.set(a.ein, a.bucketId));
    setAssignments(map);
    hasInitialized.current = true;
  }, [initialTarget, initialBuckets, initialAssignments]);

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const targetNum = parseInt(target) || 0;
  const totalPct = roundPercent(buckets.reduce((s, b) => s + b.percent, 0));
  const isTotalBalanced = Math.abs(totalPct - 100) <= PERCENT_EPSILON;
  const isTotalUnder = totalPct < 100 - PERCENT_EPSILON;
  const isTotalOver = totalPct > 100 + PERCENT_EPSILON;
  const totalPctLabel = formatPercent(totalPct);
  const mobileBucketOptions = useMemo(
    () => buckets.map(bucket => ({ id: bucket.id, label: bucket.label })),
    [buckets]
  );
  const usedTags = new Set(buckets.map(b => b.tagId));

  // Auto-save with debounce
  const triggerSave = useCallback(async (newBuckets?: typeof buckets, newTarget?: number, newAssignments?: Map<string, string>) => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    const b = newBuckets || buckets;
    const t = newTarget ?? targetNum;
    const a = newAssignments || assignments;

    saveTimeoutRef.current = setTimeout(async () => {
      setSaving(true);
      try {
        const fb = b.map(bucket => ({ id: bucket.id, name: bucket.label, tags: [bucket.tagId], percentage: bucket.percent, color: bucket.color }));
        const fa: CharityAssignment[] = []; a.forEach((bid, ein) => fa.push({ ein, bucketId: bid }));
        await onSave(fb, t > 0 ? t : null, fa);
      } finally { setSaving(false); }
    }, 300);
  }, [buckets, targetNum, assignments, onSave]);

  const charityToBucket = useMemo(() => {
    const result = new Map<string, string>();
    for (const c of bookmarkedCharities) {
      if (assignments.has(c.ein) && buckets.some(b => b.id === assignments.get(c.ein))) {
        result.set(c.ein, assignments.get(c.ein)!);
        continue;
      }
      for (const b of buckets) {
        if ((c.causeTags || []).includes(b.tagId)) { result.set(c.ein, b.id); break; }
      }
    }
    return result;
  }, [bookmarkedCharities, buckets, assignments]);

  const getCharityTarget = useCallback((ein: string): number => {
    const draft = charityTargetDrafts.get(ein);
    if (draft !== undefined) return draft;
    return charityTargets?.get(ein) || 0;
  }, [charityTargetDrafts, charityTargets]);

  // Clear optimistic draft values once parent props reflect the same saved target.
  useEffect(() => {
    if (!charityTargets) return;
    setCharityTargetDrafts(prev => {
      if (prev.size === 0) return prev;
      const next = new Map(prev);
      let changed = false;
      prev.forEach((draft, ein) => {
        if ((charityTargets.get(ein) || 0) === draft) {
          next.delete(ein);
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [charityTargets]);

  const unassigned = useMemo(() => bookmarkedCharities.filter(c => !charityToBucket.has(c.ein)), [bookmarkedCharities, charityToBucket]);

  const bucketGiven = useMemo(() => {
    const g = new Map<string, number>();
    buckets.forEach(b => {
      let t = 0;
      donations.forEach(d => { if (charityToBucket.get(d.charityEin || '') === b.id) t += d.amount; });
      g.set(b.id, t);
    });
    return g;
  }, [buckets, donations, charityToBucket]);

  const totalGiven = Array.from(bucketGiven.values()).reduce((s, v) => s + v, 0);
  const hasTarget = targetNum > 0;
  const hasSavedCharities = bookmarkedCharities.length > 0;
  const hasLoggedDonation = donations.length > 0;
  const showOnboarding =
    !onboardingDismissed &&
    (!hasTarget || !hasSavedCharities || !hasLoggedDonation);

  const onboardingStep = !hasTarget
    ? 1
    : !hasSavedCharities
    ? 2
    : !hasLoggedDonation
    ? 3
    : 0;

  // Zakat eligibility helper
  const isZakatEligible = useCallback((walletTag: string | null) => {
    return getWalletType(walletTag) === 'zakat';
  }, []);

  // Calculate zakat-only totals
  const zakatStats = useMemo(() => {
    let zakatGiven = 0;
    const zakatBucketGiven = new Map<string, number>();
    const bucketHasZakat = new Map<string, boolean>();

    // Check which charities are zakat-eligible and sum their donations
    bookmarkedCharities.forEach(c => {
      if (isZakatEligible(c.walletTag)) {
        const bucketId = charityToBucket.get(c.ein);
        if (bucketId) {
          bucketHasZakat.set(bucketId, true);
        }
        const charityDonations = donations
          .filter(d => d.charityEin === c.ein)
          .reduce((sum, d) => sum + d.amount, 0);
        zakatGiven += charityDonations;
        if (bucketId) {
          zakatBucketGiven.set(bucketId, (zakatBucketGiven.get(bucketId) || 0) + charityDonations);
        }
      }
    });

    return { zakatGiven, zakatBucketGiven, bucketHasZakat };
  }, [bookmarkedCharities, charityToBucket, donations, isZakatEligible]);

  const tagCounts = useMemo(() => {
    const c = new Map<string, number>();
    charities
      .filter(ch => !zakatLens || isZakatEligible((ch as any).amalEvaluation?.wallet_tag))
      .forEach(ch => ((ch as any).causeTags || []).forEach((t: string) => c.set(t, (c.get(t) || 0) + 1)));
    return c;
  }, [charities, zakatLens, isZakatEligible]);

  const add = (tag: { id: string; label: string }) => {
    const newBuckets = [...buckets, { id: crypto.randomUUID(), tagId: tag.id, label: tag.label, percent: 0, color: COLORS[buckets.length % COLORS.length] }];
    setBuckets(newBuckets);
    triggerSave(newBuckets);
  };

  const autoCreateBucketsForCharity = (charity: { causeTags: string[] | null }) => {
    const tags = charity.causeTags || [];
    const causeTagIds = new Set(TAGS.cause.map(t => t.id));
    const newBuckets = [...buckets];
    let created = 0;

    for (const tagId of tags) {
      if (created >= 3) break;
      if (!causeTagIds.has(tagId)) continue;
      if (newBuckets.some(b => b.tagId === tagId)) continue;

      const tagDef = TAGS.cause.find(t => t.id === tagId)!;
      newBuckets.push({
        id: crypto.randomUUID(),
        tagId: tagDef.id,
        label: tagDef.label,
        percent: 0,
        color: COLORS[newBuckets.length % COLORS.length],
      });
      created++;
    }

    if (created > 0) {
      setBuckets(newBuckets);
      triggerSave(newBuckets);
    }

    const firstMatch = newBuckets.find(b => tags.includes(b.tagId));
    return firstMatch?.id || '';
  };

  const remove = (id: string) => {
    const newBuckets = buckets.filter(b => b.id !== id);
    setBuckets(newBuckets);
    triggerSave(newBuckets);
  };

  const setPct = (id: string, v: number) => {
    const newBuckets = buckets.map(b => b.id === id ? { ...b, percent: roundPercent(clampPercent(v)) } : b);
    setBuckets(newBuckets);
  };

  const setTargetAmt = (id: string, amt: number) => {
    if (targetNum === 0) return;
    const pct = roundPercent(clampPercent((amt / targetNum) * 100));
    const newBuckets = buckets.map(b => b.id === id ? { ...b, percent: pct } : b);
    setBuckets(newBuckets);
  };

  const handleSetCharityTarget = useCallback(async (ein: string, amount: number) => {
    const normalized = Math.max(0, amount);
    setCharityTargetDrafts(prev => {
      const next = new Map(prev);
      next.set(ein, normalized);
      return next;
    });

    const bucketId = charityToBucket.get(ein);
    if (bucketId && targetNum > 0) {
      const bucketTargetSum = bookmarkedCharities.reduce((sum, charity) => {
        if (charityToBucket.get(charity.ein) !== bucketId) return sum;
        if (charity.ein === ein) return sum + normalized;
        return sum + getCharityTarget(charity.ein);
      }, 0);
      const syncedPct = roundPercent(clampPercent((bucketTargetSum / targetNum) * 100));
      const newBuckets = buckets.map(bucket => (
        bucket.id === bucketId ? { ...bucket, percent: syncedPct } : bucket
      ));
      setBuckets(newBuckets);
      triggerSave(newBuckets);
    }

    if (!onSetCharityTarget) return;
    try {
      await onSetCharityTarget(ein, normalized);
    } catch {
      // Revert optimistic value on failure.
      setCharityTargetDrafts(prev => {
        const next = new Map(prev);
        next.delete(ein);
        return next;
      });
    }
  }, [bookmarkedCharities, buckets, charityToBucket, getCharityTarget, onSetCharityTarget, targetNum, triggerSave]);

  const distributeRemainingEvenly = () => {
    if (buckets.length === 0 || !isTotalUnder) return;
    const remaining = 100 - totalPct;
    const perBucket = remaining / buckets.length;
    let newBuckets = buckets.map((bucket, i) => {
      const increment = i === buckets.length - 1
        ? remaining - (perBucket * (buckets.length - 1))
        : perBucket;
      return { ...bucket, percent: roundPercent(clampPercent(bucket.percent + increment)) };
    });
    const correctedTotal = roundPercent(newBuckets.reduce((sum, bucket) => sum + bucket.percent, 0));
    const correction = roundPercent(100 - correctedTotal);
    if (newBuckets.length > 0 && Math.abs(correction) > PERCENT_EPSILON) {
      const last = newBuckets[newBuckets.length - 1];
      newBuckets = [
        ...newBuckets.slice(0, -1),
        { ...last, percent: roundPercent(clampPercent(last.percent + correction)) },
      ];
    }
    setBuckets(newBuckets);
    triggerSave(newBuckets);
  };

  const move = (ein: string, bid: string | null) => {
    const newAssignments = new Map(assignments);
    bid ? newAssignments.set(ein, bid) : newAssignments.delete(ein);
    setAssignments(newAssignments);
    const hasAnyCharityTargets = bookmarkedCharities.some(charity => getCharityTarget(charity.ein) > 0);
    if (!hasAnyCharityTargets || targetNum === 0) {
      triggerSave(undefined, undefined, newAssignments);
      return;
    }

    const validBucketIds = new Set(buckets.map(bucket => bucket.id));
    const resolveBucket = (charity: BookmarkedCharity): string | null => {
      const assignedBucketId = newAssignments.get(charity.ein);
      if (assignedBucketId && validBucketIds.has(assignedBucketId)) return assignedBucketId;
      for (const bucket of buckets) {
        if ((charity.causeTags || []).includes(bucket.tagId)) return bucket.id;
      }
      return null;
    };

    const sumByBucket = new Map<string, number>();
    bookmarkedCharities.forEach(charity => {
      const bucketId = resolveBucket(charity);
      if (!bucketId) return;
      sumByBucket.set(bucketId, (sumByBucket.get(bucketId) || 0) + getCharityTarget(charity.ein));
    });

    const syncedBuckets = buckets.map(bucket => {
      const bucketTargetSum = sumByBucket.get(bucket.id) || 0;
      return {
        ...bucket,
        percent: roundPercent(clampPercent((bucketTargetSum / targetNum) * 100)),
      };
    });
    setBuckets(syncedBuckets);
    triggerSave(syncedBuckets, undefined, newAssignments);
  };

  const handleBlur = () => triggerSave();
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') { (e.target as HTMLInputElement).blur(); triggerSave(); } };

  const handleOnboardingAction = () => {
    if (onboardingStep === 1) {
      targetInputRef.current?.focus();
      targetInputRef.current?.select();
      return;
    }

    if (onboardingStep === 2) {
      setShowCharitySearch(true);
      setShowPicker(false);
      return;
    }

    if (onboardingStep === 3) {
      const first = bookmarkedCharities[0];
      onLogDonation(first?.ein, first?.name);
    }
  };

  // Add a suggested charity (bookmark + assign to bucket)
  const onAddSuggestion = async (ein: string, name: string, bucketId: string) => {
    if (onAddCharity) {
      await onAddCharity(ein, name, bucketId);
      // Also update local assignments
      setAssignments(prev => {
        const next = new Map(prev);
        next.set(ein, bucketId);
        return next;
      });
    }
  };

  // Toggle category collapse
  const toggleCollapse = (bucketId: string) => {
    setCollapsedBuckets(prev => {
      const next = new Set(prev);
      if (next.has(bucketId)) {
        next.delete(bucketId);
      } else {
        next.add(bucketId);
      }
      return next;
    });
  };

  // Drag and drop
  const [activeCharity, setActiveCharity] = useState<BookmarkedCharity | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor)
  );

  const handleDragStart = (event: DragStartEvent) => {
    const charity = (event.active.data.current as any)?.charity as BookmarkedCharity;
    if (charity) setActiveCharity(charity);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveCharity(null);
    const { active, over } = event;
    if (!over) return;

    const charityEin = active.id as string;
    const targetBucketId = over.id as string;

    // "uncategorized" is a special drop zone
    if (targetBucketId === 'uncategorized') {
      move(charityEin, null);
    } else if (buckets.some(b => b.id === targetBucketId)) {
      move(charityEin, targetBucketId);
    }
  };

  // Styles - Refined & elegant
  const headerCell = `px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-400'}`;
  const cell = `px-3 py-2.5 text-[13px] ${isDark ? 'text-slate-300' : 'text-slate-700'}`;
  const rowHover = isDark ? 'hover:bg-slate-800/40' : 'hover:bg-slate-50';
  const border = isDark ? 'border-slate-800' : 'border-slate-200';
  const borderLight = isDark ? 'border-slate-800/50' : 'border-slate-100';
  const inputStyle = `bg-transparent focus:outline-none focus:ring-1 focus:ring-emerald-500/50 rounded px-1.5 -mx-1 ${isDark ? 'text-white' : 'text-slate-900'}`;

  return (
    <div className={`rounded-xl border overflow-hidden text-sm ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'} shadow-sm`}>
      {/* Header bar - gradient accent */}
      <div className={`flex flex-col gap-3 px-4 py-3.5 border-b sm:flex-row sm:items-center sm:justify-between ${border} ${isDark ? 'bg-gradient-to-r from-slate-800/50 to-slate-900' : 'bg-gradient-to-r from-slate-50 to-white'}`}>
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:gap-4">
          <div className="flex items-center gap-2.5">
            <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md ${isDark ? 'bg-emerald-500/10' : 'bg-emerald-50'}`}>
              <span className={`text-[10px] font-bold tracking-wide ${isDark ? 'text-emerald-500' : 'text-emerald-600'}`}>ZAKAT</span>
            </div>
            <div className={`flex items-center border ${isDark ? 'bg-slate-800/80 border-slate-700' : 'bg-white border-slate-200'} rounded-lg px-3 py-1.5 shadow-sm`}>
              <span className={`text-sm font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>$</span>
              <input
                ref={targetInputRef}
                type="text"
                inputMode="numeric"
                value={target}
                onChange={e => setTarget(e.target.value.replace(/\D/g, ''))}
                onBlur={handleBlur}
                onKeyDown={handleKeyDown}
                placeholder="10,000"
                className={`w-20 py-0.5 bg-transparent text-lg font-bold focus:outline-none ${isDark ? 'text-white placeholder-slate-600' : 'text-slate-900 placeholder-slate-300'}`}
              />
            </div>
          </div>
          {targetNum > 0 && (
            <div className="flex items-center gap-3">
              <div className={`h-2 w-28 rounded-full overflow-hidden ${isDark ? 'bg-slate-700' : 'bg-slate-200'} shadow-inner`}>
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all rounded-full"
                  style={{ width: `${Math.min(100, Math.round((zakatLens ? zakatStats.zakatGiven : totalGiven)/targetNum*100))}%` }}
                />
              </div>
              <span className={`text-xs font-medium tabular-nums ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                <span className="text-emerald-500 font-semibold">{fmt(zakatLens ? zakatStats.zakatGiven : totalGiven)}</span>
                <span className="opacity-50 mx-1">/</span>
                {fmt(targetNum)}
              </span>
              {/* Zakat lens toggle */}
              <button
                onClick={() => setZakatLens(!zakatLens)}
                className={`ml-2 text-[11px] font-medium px-2.5 py-1 rounded-md border transition-all ${
                  zakatLens
                    ? isDark ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-emerald-50 text-emerald-600 border-emerald-200'
                    : isDark ? 'text-slate-500 border-slate-700 hover:text-slate-400 hover:bg-slate-800' : 'text-slate-400 border-slate-200 hover:text-slate-600 hover:bg-slate-50'
                }`}
              >
                {zakatLens ? 'Zakat only' : 'Zakat'}
              </button>
            </div>
          )}
        </div>
        <div className="flex w-full flex-wrap items-center gap-1.5 sm:w-auto sm:justify-end">
          {saving && (
            <span className={`text-[10px] px-2 py-1 rounded ${isDark ? 'text-emerald-400 bg-emerald-500/10' : 'text-emerald-600 bg-emerald-50'}`}>
              Saving...
            </span>
          )}
          {buckets.length > 0 && (
            <button
              onClick={() => setShowSuggestions(!showSuggestions)}
              className={`text-[11px] font-medium px-3 py-1.5 rounded-lg border transition-all ${
                showSuggestions
                  ? isDark ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' : 'bg-blue-50 text-blue-600 border-blue-200'
                  : isDark ? 'text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300' : 'text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700'
              }`}
            >
              {showSuggestions ? 'Hide' : 'Show'} suggestions
            </button>
          )}
          <button
            onClick={() => { setShowCharitySearch(!showCharitySearch); setCharitySearchQuery(''); }}
            className={`text-[11px] font-medium px-3 py-1.5 rounded-lg border transition-all flex items-center gap-1 ${
              showCharitySearch
                ? isDark ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' : 'bg-blue-50 text-blue-600 border-blue-200'
                : isDark ? 'text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300' : 'text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />Charity
          </button>
          <button
            onClick={() => setShowPicker(!showPicker)}
            className={`text-[11px] font-medium px-3 py-1.5 rounded-lg border transition-all flex items-center gap-1 ${
              showPicker
                ? isDark ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-emerald-50 text-emerald-600 border-emerald-200'
                : isDark ? 'text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300' : 'text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />Category
          </button>
        </div>
      </div>

      {/* Guided onboarding */}
      {showOnboarding && (
        <div className={`px-4 py-3 border-b ${border} ${isDark ? 'bg-emerald-500/5' : 'bg-emerald-50/60'}`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-wide ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
                Getting Started
              </p>
              <p className={`text-sm mt-0.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                Step {onboardingStep} of 3: {
                  onboardingStep === 1 ? 'Set your annual zakat target' :
                  onboardingStep === 2 ? 'Add your first charity' :
                  'Log your first donation'
                }
              </p>
            </div>
            <button
              onClick={() => setOnboardingDismissed(true)}
              className={`text-xs font-medium px-2 py-1 rounded border transition-colors ${
                isDark
                  ? 'text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300'
                  : 'text-slate-500 border-slate-200 hover:bg-white hover:text-slate-700'
              }`}
            >
              Dismiss
            </button>
          </div>

          <div className="mt-3 flex items-center gap-2">
            {[1, 2, 3].map(step => {
              const complete = step === 1 ? hasTarget : step === 2 ? hasSavedCharities : hasLoggedDonation;
              const active = step === onboardingStep;
              return (
                <div
                  key={step}
                  className={`h-1.5 rounded-full transition-all ${complete ? 'bg-emerald-500' : active ? 'bg-emerald-300' : isDark ? 'bg-slate-700' : 'bg-slate-200'}`}
                  style={{ width: active ? 52 : 28 }}
                />
              );
            })}

            <button
              onClick={handleOnboardingAction}
              className={`ml-2 inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg shadow-sm transition-colors ${
                isDark
                  ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                  : 'bg-emerald-600 text-white hover:bg-emerald-700'
              }`}
            >
              Continue
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Charity search */}
      {showCharitySearch && (
        <div className={`px-4 py-4 border-b ${border} ${isDark ? 'bg-slate-800/30' : 'bg-blue-50/30'}`}>
          <div className="flex items-center gap-2 mb-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={charitySearchQuery}
                onChange={e => setCharitySearchQuery(e.target.value)}
                placeholder="Search charities to add..."
                autoFocus
                className={`w-full pl-9 pr-3 py-2 text-sm rounded-lg border shadow-sm ${
                  isDark
                    ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500 focus:border-blue-500'
                    : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-400'
                } focus:outline-none focus:ring-2 focus:ring-blue-500/20`}
              />
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <button
              onClick={() => { setShowCharitySearch(false); setCharitySearchQuery(''); }}
              className={`p-2 rounded-lg transition-colors ${isDark ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-slate-200 text-slate-500'}`}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          {charitySearchQuery.length >= 2 && (
            <div className={`max-h-52 overflow-y-auto rounded-lg border shadow-sm ${isDark ? 'border-slate-700 bg-slate-800/50' : 'border-slate-200 bg-white'}`}>
              {(() => {
                const bookmarkedEins = new Set(bookmarkedCharities.map(c => c.ein));
                const results = charities
                  .filter(c => !bookmarkedEins.has(c.ein) && c.name.toLowerCase().includes(charitySearchQuery.toLowerCase()))
                  .slice(0, 10);

                if (results.length === 0) {
                  return (
                    <div className={`px-4 py-3 text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      No matching charities found
                    </div>
                  );
                }

                return results.map((c, i) => (
                  <div
                    key={c.ein}
                    className={`flex items-center justify-between px-3 py-2.5 ${i !== results.length - 1 ? `border-b ${borderLight}` : ''} ${
                      isDark ? 'hover:bg-slate-700/50' : 'hover:bg-slate-50'
                    } transition-colors`}
                  >
                    <div className="flex items-center gap-2.5">
                      <span className={`text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>{c.name}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-semibold border ${
                        isDark ? 'bg-slate-700 border-slate-600 text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-500'
                      }`}>
                        {(c as any).amalScore || '—'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={async () => {
                          if (onAddCharity) {
                            const fullCharity = charities.find(ch => ch.ein === c.ein);
                            const causeTags = fullCharity ? (fullCharity as any).causeTags || [] : [];
                            const bucketId = autoCreateBucketsForCharity({ causeTags });
                            await onAddCharity(c.ein, c.name, bucketId);
                            if (bucketId) {
                              setAssignments(prev => {
                                const next = new Map(prev);
                                next.set(c.ein, bucketId);
                                return next;
                              });
                            }
                            setCharitySearchQuery('');
                          }
                        }}
                        className={`text-[11px] px-3 py-1.5 rounded-lg font-semibold shadow-sm ${isDark ? 'bg-emerald-600 text-white hover:bg-emerald-500' : 'bg-emerald-500 text-white hover:bg-emerald-600'}`}
                      >
                        + Add
                      </button>
                    </div>
                  </div>
                ));
              })()}
            </div>
          )}
          {charitySearchQuery.length < 2 && (
            <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Type at least 2 characters to search
            </div>
          )}
        </div>
      )}

      {/* Category picker */}
      {showPicker && (
        <div className={`px-4 py-4 border-b ${border} ${isDark ? 'bg-slate-800/30' : 'bg-emerald-50/30'}`}>
          <div className="space-y-3">
            {Object.entries(TAGS).map(([group, tags]) => (
              <div key={group} className="flex flex-wrap items-start gap-2">
                <span className={`text-[10px] font-bold uppercase tracking-wider w-24 pt-1.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  {group}
                </span>
                <div className="flex-1 flex flex-wrap gap-1.5">
                  {tags.map(tag => {
                    const used = usedTags.has(tag.id);
                    const cnt = tagCounts.get(tag.id) || 0;
                    return (
                      <button
                        key={tag.id}
                        onClick={() => !used && cnt > 0 && add(tag)}
                        disabled={used || cnt === 0}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-all ${
                          used
                            ? isDark
                              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                              : 'bg-emerald-50 border-emerald-200 text-emerald-600'
                            : cnt === 0
                            ? isDark
                              ? 'border-slate-800 text-slate-700 cursor-not-allowed'
                              : 'border-slate-100 text-slate-300 cursor-not-allowed'
                            : isDark
                            ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:border-slate-600 hover:text-white'
                            : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-800 shadow-sm'
                        }`}
                      >
                        {tag.label}
                        {cnt > 0 && !used && (
                          <span className={`tabular-nums ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{cnt}</span>
                        )}
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

      {/* Table with drag-and-drop */}
      {targetNum > 0 && (
        <>
        <div className="sm:hidden px-3 py-3 space-y-2.5">
          {buckets.map(b => {
            const amt = Math.round(targetNum * b.percent / 100);
            const gvn = bucketGiven.get(b.id) || 0;
            const pct = amt > 0 ? Math.min(100, Math.round(gvn / amt * 100)) : 0;
            const chars = bookmarkedCharities.filter(c => charityToBucket.get(c.ein) === b.id);
            const charityTargetsSum = chars.reduce((sum, c) => sum + getCharityTarget(c.ein), 0);
            const visibleChars = zakatLens
              ? chars.filter(c => isZakatEligible(c.walletTag))
              : chars;
            const displayCount = visibleChars.length;
            const bookmarkedEins = new Set(bookmarkedCharities.map(c => c.ein));
            const suggestions = charities
              .filter(c => {
                const tags = (c as any).causeTags || [];
                return tags.includes(b.tagId) && !bookmarkedEins.has(c.ein);
              })
              .sort((a, c) => ((c as any).amalScore || 0) - ((a as any).amalScore || 0))
              .slice(0, 3)
              .map(c => ({ ein: c.ein, name: c.name, amalScore: (c as any).amalScore || null }));
            const bucketHasZakatCharities = zakatStats.bucketHasZakat.get(b.id) || false;
            const categoryDimmed = zakatLens && !bucketHasZakatCharities;

            return (
              <div
                key={b.id}
                className={`rounded-lg border p-3 ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'} ${categoryDimmed ? 'opacity-50' : ''}`}
                style={{ borderLeft: `4px solid ${b.color}` }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: b.color }} />
                      <span className={`font-semibold text-sm truncate ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{b.label}</span>
                    </div>
                    <div className={`mt-1 text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                      {displayCount} {displayCount === 1 ? 'charity' : 'charities'} • Given {fmt(gvn)} • {pct}%
                    </div>
                  </div>
                  <button
                    onClick={() => remove(b.id)}
                    className={`p-1 -m-1 rounded-md transition-colors ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}
                    aria-label={`Remove ${b.label}`}
                  >
                    <X className={`w-3.5 h-3.5 ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`} />
                  </button>
                </div>

                <div className="mt-2 grid grid-cols-2 gap-2">
                  <div>
                    <label className={`block text-[10px] font-semibold uppercase tracking-wide mb-1 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>%</label>
                    <div className={`inline-flex w-full items-center justify-end px-2 py-1 rounded-md border ${isDark ? 'border-slate-700 bg-slate-800/50' : 'border-slate-200 bg-slate-50'}`}>
                      <input
                        type="text"
                        inputMode="decimal"
                        value={b.percent || ''}
                        onChange={e => setPct(b.id, parsePercentInput(e.target.value))}
                        onBlur={handleBlur}
                        onKeyDown={handleKeyDown}
                        className={`w-12 text-right ${inputStyle} font-semibold tabular-nums`}
                        placeholder="0"
                      />
                      <span className={`text-[11px] ml-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>%</span>
                    </div>
                  </div>
                  <div>
                    <label className={`block text-[10px] font-semibold uppercase tracking-wide mb-1 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Target</label>
                    <div className="flex flex-col items-end gap-0.5">
                      <div className={`inline-flex w-full items-center justify-end px-2 py-1 rounded-md border ${isDark ? 'border-slate-700 bg-slate-800/50' : 'border-slate-200 bg-slate-50'}`}>
                        <span className={`text-[11px] mr-1 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>$</span>
                        <input
                          type="text"
                          inputMode="numeric"
                          value={amt || ''}
                          onChange={e => setTargetAmt(b.id, parseInt(e.target.value.replace(/\D/g, '')) || 0)}
                          onBlur={handleBlur}
                          onKeyDown={handleKeyDown}
                          className={`w-16 text-right ${inputStyle} font-semibold tabular-nums`}
                          placeholder="0"
                        />
                      </div>
                      {charityTargetsSum > 0 && (
                        <span className={`text-[10px] tabular-nums ${
                          charityTargetsSum === amt
                            ? 'text-emerald-500'
                            : charityTargetsSum > amt
                            ? 'text-amber-500'
                            : isDark ? 'text-slate-500' : 'text-slate-400'
                        }`}>
                          {fmt(charityTargetsSum)} allocated
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className={`mt-2 h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(pct, 100)}%`, background: `linear-gradient(90deg, ${b.color}, ${b.color}cc)` }} />
                </div>

                <div className={`mt-2.5 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
                  <div className={`text-[10px] font-semibold uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                    Charities
                  </div>
                  {visibleChars.length > 0 ? (
                    <div className="mt-1.5 space-y-1.5">
                      {visibleChars.map(c => {
                        const cGiven = donations
                          .filter(d => d.charityEin === c.ein)
                          .reduce((sum, d) => sum + d.amount, 0);
                        return (
                          <MobileCharityAllocationRow
                            key={c.ein}
                            charity={c}
                            given={cGiven}
                            target={getCharityTarget(c.ein)}
                            categoryTarget={amt}
                            currentBucketId={b.id}
                            bucketOptions={mobileBucketOptions}
                            isDark={isDark}
                            onLogDonation={onLogDonation}
                            onSetTarget={handleSetCharityTarget}
                            onMoveCharity={move}
                            onRemove={onRemoveCharity}
                          />
                        );
                      })}
                    </div>
                  ) : (
                    <div className={`mt-1.5 text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      No charities in this category yet.
                    </div>
                  )}
                  {showSuggestions && suggestions.length > 0 && (
                    <div className={`mt-2.5 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
                      <div className={`text-[10px] font-semibold uppercase tracking-wide mb-1.5 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                        Suggestions
                      </div>
                      <div className="space-y-1.5">
                        {suggestions.map(s => (
                          <div key={s.ein} className="flex items-center justify-between gap-2">
                            <div className="min-w-0 flex items-center gap-1.5">
                              <span className={`text-[12px] truncate ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{s.name}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-semibold border ${
                                isDark ? 'bg-slate-800 border-slate-700 text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-500'
                              }`}>
                                {s.amalScore || '—'}
                              </span>
                            </div>
                            <button
                              onClick={() => onAddSuggestion(s.ein, s.name, b.id)}
                              className={`shrink-0 text-[10px] px-2 py-1 rounded-md font-semibold border transition-colors ${
                                isDark
                                  ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20'
                                  : 'text-emerald-600 border-emerald-200 bg-emerald-50 hover:bg-emerald-100'
                              }`}
                            >
                              + Add
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {buckets.length > 0 && (
            <div className={`rounded-lg border px-3 py-2.5 ${isDark ? 'bg-slate-800/60 border-slate-700' : 'bg-slate-100/80 border-slate-200'}`}>
              <div className="flex items-center justify-between">
                <span className={`font-semibold ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>Total</span>
                <span className={`font-bold tabular-nums px-2 py-0.5 rounded ${
                  isTotalBalanced
                    ? isDark ? 'text-emerald-400 bg-emerald-500/10' : 'text-emerald-600 bg-emerald-50'
                    : isTotalOver
                    ? isDark ? 'text-amber-400 bg-amber-500/10' : 'text-amber-600 bg-amber-50'
                    : isDark ? 'text-red-400 bg-red-500/10' : 'text-red-600 bg-red-50'
                }`}>
                  {totalPctLabel}%
                </span>
              </div>
              <div className={`mt-1 text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Target {fmt(Math.round(targetNum * totalPct / 100))} • Given {fmt(totalGiven)}
              </div>
            </div>
          )}

          {!isTotalBalanced && buckets.length > 0 && (
            <div className={`rounded-lg border px-3 py-2.5 ${isDark ? 'border-red-500/20 bg-red-500/5' : 'border-red-100 bg-red-50/50'}`}>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isTotalUnder ? 'bg-red-500' : 'bg-amber-500'} animate-pulse`} />
                <span className={`text-xs font-medium ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                  {isTotalUnder
                    ? `${formatPercent(100 - totalPct)}% unallocated (${fmt(Math.round(targetNum * (100 - totalPct) / 100))})`
                    : `${formatPercent(totalPct - 100)}% over-allocated`
                  }
                </span>
              </div>
              {isTotalUnder && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button
                    onClick={distributeRemainingEvenly}
                    className={`text-[11px] px-2.5 py-1.5 rounded-lg font-semibold border transition-colors ${
                      isDark
                        ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                        : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 shadow-sm'
                    }`}
                  >
                    Distribute evenly
                  </button>
                  <button
                    onClick={() => setShowPicker(true)}
                    className={`text-[11px] px-2.5 py-1.5 rounded-lg font-semibold shadow-sm transition-colors ${
                      isDark
                        ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                        : 'bg-emerald-500 text-white hover:bg-emerald-600'
                    }`}
                  >
                    + Category
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="hidden sm:block overflow-x-auto">
          <div className="min-w-full sm:min-w-[780px]">
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
          <table className="w-full">
            <thead>
              <tr className={`border-b-2 ${border} ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                <th className={`${headerCell} w-6 hidden sm:table-cell`}></th>
                <th className={`${headerCell} text-left`}>Category</th>
                <th className={`${headerCell} text-right w-20`}>%</th>
                <th className={`${headerCell} text-right w-24`}>Target</th>
                <th className={`${headerCell} text-right w-20 hidden sm:table-cell`}>Given</th>
                <th className={`${headerCell} w-28 hidden sm:table-cell`}>Progress</th>
                <th className={`${headerCell} w-8 hidden sm:table-cell`}></th>
              </tr>
            </thead>
            {buckets.map(b => {
              const amt = Math.round(targetNum * b.percent / 100);
              const gvn = bucketGiven.get(b.id) || 0;
              const pct = amt > 0 ? Math.min(100, Math.round(gvn / amt * 100)) : 0;
              const chars = bookmarkedCharities.filter(c => charityToBucket.get(c.ein) === b.id);
              // Sum of charity targets within this bucket
              const charityTargetsSum = chars.reduce((sum, c) => sum + getCharityTarget(c.ein), 0);
              // Count for display - filters by zakat eligibility when lens is active
              const displayCount = zakatLens
                ? chars.filter(c => isZakatEligible(c.walletTag)).length
                : chars.length;

              // Get suggested charities for this category (matching tag, not bookmarked, limit 3)
              const bookmarkedEins = new Set(bookmarkedCharities.map(c => c.ein));
              const suggestions = charities
                .filter(c => {
                  const tags = (c as any).causeTags || [];
                  return tags.includes(b.tagId) && !bookmarkedEins.has(c.ein);
                })
                .sort((a, b) => ((b as any).amalScore || 0) - ((a as any).amalScore || 0))
                .slice(0, 3)
                .map(c => ({ ein: c.ein, name: c.name, amalScore: (c as any).amalScore || null }));

              // Check if bucket has any zakat-eligible charities
              const bucketHasZakatCharities = zakatStats.bucketHasZakat.get(b.id) || false;
              const categoryDimmed = zakatLens && !bucketHasZakatCharities;

              const isCollapsed = collapsedBuckets.has(b.id);

              return (
                <DroppableCategory key={b.id} id={b.id} color={b.color} isDark={isDark}>
                  <tr
                    className={`border-b ${borderLight} ${rowHover} group transition-all ${categoryDimmed ? 'opacity-40' : ''}`}
                    style={{
                      background: isDark
                        ? `linear-gradient(90deg, ${b.color}15 ${pct}%, transparent ${pct}%)`
                        : `linear-gradient(90deg, ${b.color}08 ${pct}%, transparent ${pct}%)`,
                      borderLeft: `4px solid ${b.color}`,
                    }}
                  >
                    <td className={`${cell} hidden sm:table-cell`}>
                      {chars.length > 0 && (
                        <ChevronDown
                          className={`w-4 h-4 transition-transform ${isCollapsed ? '-rotate-90' : ''} ${isDark ? 'text-slate-500' : 'text-slate-400'}`}
                        />
                      )}
                    </td>
                    <td
                      className={`${cell} sm:cursor-pointer select-none`}
                      onClick={() => chars.length > 0 && toggleCollapse(b.id)}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="w-3 h-3 rounded-md shadow-sm" style={{ background: b.color }} />
                          <span className="font-semibold truncate">{b.label}</span>
                          {displayCount > 0 && (
                            <span
                              className="text-[10px] px-2 py-0.5 rounded-full font-semibold border"
                              style={{
                                backgroundColor: `${b.color}15`,
                                borderColor: `${b.color}30`,
                                color: b.color,
                              }}
                            >
                              {displayCount} {displayCount === 1 ? 'charity' : 'charities'}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            remove(b.id);
                          }}
                          className={`sm:hidden p-1 -m-1 rounded-md transition-colors ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}
                          aria-label={`Remove ${b.label}`}
                        >
                          <X className={`w-3.5 h-3.5 ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`} />
                        </button>
                      </div>
                      <div className={`sm:hidden mt-1 text-[11px] ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                        Given {fmt(gvn)} • {pct}%
                      </div>
                    </td>
                    <td className={`${cell} text-right`}>
                      <div className={`inline-flex items-center px-2 py-0.5 rounded-md border ${isDark ? 'border-slate-700 bg-slate-800/50' : 'border-slate-200 bg-slate-50'}`}>
                        <input
                          type="text"
                          inputMode="decimal"
                          value={b.percent || ''}
                          onChange={e => setPct(b.id, parsePercentInput(e.target.value))}
                          onBlur={handleBlur}
                          onKeyDown={handleKeyDown}
                          className={`w-12 text-right ${inputStyle} font-semibold tabular-nums`}
                          placeholder="0"
                        />
                        <span className={`text-[11px] ml-0.5 font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>%</span>
                      </div>
                    </td>
                    <td className={`${cell} text-right`}>
                      <div className="flex flex-col items-end gap-0.5">
                        <div className={`inline-flex items-center px-2 py-0.5 rounded-md border ${isDark ? 'border-slate-700 bg-slate-800/50' : 'border-slate-200 bg-slate-50'}`}>
                          <span className={`text-[11px] mr-0.5 font-medium ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>$</span>
                          <input
                            type="text"
                            inputMode="numeric"
                            value={amt || ''}
                            onChange={e => setTargetAmt(b.id, parseInt(e.target.value.replace(/\D/g, '')) || 0)}
                            onBlur={handleBlur}
                            onKeyDown={handleKeyDown}
                            className={`w-16 text-right ${inputStyle} font-semibold tabular-nums`}
                            placeholder="0"
                          />
                        </div>
                        {charityTargetsSum > 0 && (
                          <span className={`text-[10px] tabular-nums ${
                            charityTargetsSum === amt
                              ? 'text-emerald-500'
                              : charityTargetsSum > amt
                              ? 'text-amber-500'
                              : isDark ? 'text-slate-500' : 'text-slate-400'
                          }`}>
                            {fmt(charityTargetsSum)} allocated
                          </span>
                        )}
                      </div>
                    </td>
                    <td className={`${cell} text-right tabular-nums hidden sm:table-cell`}>
                      <span className={gvn > 0 ? 'font-medium' : isDark ? 'text-slate-600' : 'text-slate-300'}>{fmt(gvn)}</span>
                    </td>
                    <td className={`${cell} hidden sm:table-cell`}>
                      <div className="flex items-center gap-2.5">
                        <div className={`flex-1 h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-slate-700' : 'bg-slate-200'} shadow-inner`}>
                          <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(pct, 100)}%`, background: `linear-gradient(90deg, ${b.color}, ${b.color}cc)` }} />
                        </div>
                        {pct >= 100 ? (
                          <div className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500/15">
                            <Check className="w-3.5 h-3.5 text-emerald-500" />
                          </div>
                        ) : (
                          <span className={`text-[11px] font-medium tabular-nums w-8 text-right ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{pct}%</span>
                        )}
                      </div>
                    </td>
                    <td className={`${cell} hidden sm:table-cell`}>
                      <button onClick={() => remove(b.id)} className={`opacity-100 sm:opacity-0 sm:group-hover:opacity-100 p-1.5 -m-1 rounded-lg transition-all ${isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'}`}>
                        <X className={`w-3.5 h-3.5 ${isDark ? 'text-slate-500 hover:text-red-400' : 'text-slate-400 hover:text-red-500'}`} />
                      </button>
                    </td>
                  </tr>
                  {/* Child rows - draggable charities (collapsible) */}
                  {!isCollapsed && chars.map(c => {
                    const cGvn = donations.filter(d => d.charityEin === c.ein).reduce((s, d) => s + d.amount, 0);
                    const charityIsZakat = isZakatEligible(c.walletTag);
                    return (
                      <DraggableCharityRow
                        key={c.ein}
                        charity={c}
                        bucketId={b.id}
                        bucketColor={b.color}
                        given={cGvn}
                        target={getCharityTarget(c.ein)}
                        isDark={isDark}
                        onLogDonation={onLogDonation}
                        onRemove={onRemoveCharity}
                        onSetTarget={handleSetCharityTarget}
                        dimmed={zakatLens && !charityIsZakat}
                      />
                    );
                  })}
                  {/* Ghost suggestion rows - only when toggled on and not collapsed */}
                  {!isCollapsed && showSuggestions && suggestions.map(s => (
                    <GhostSuggestionRow
                      key={s.ein}
                      charity={s}
                      isDark={isDark}
                      onAdd={() => onAddSuggestion(s.ein, s.name, b.id)}
                    />
                  ))}
                </DroppableCategory>
              );
            })}
            {/* Total row */}
            {buckets.length > 0 && (
              <tbody>
                <tr className={`border-t-2 ${border} ${isDark ? 'bg-slate-800/60' : 'bg-slate-100/80'}`}>
                  <td className={`${cell} hidden sm:table-cell`}></td>
                  <td className={`${cell} font-bold text-base`}>Total</td>
                  <td className={`${cell} text-right`}>
                    <span className={`font-bold text-base tabular-nums px-2.5 py-1 rounded-lg ${
                      isTotalBalanced
                        ? isDark ? 'text-emerald-400 bg-emerald-500/10' : 'text-emerald-600 bg-emerald-50'
                        : isTotalOver
                        ? isDark ? 'text-amber-400 bg-amber-500/10' : 'text-amber-600 bg-amber-50'
                        : isDark ? 'text-red-400 bg-red-500/10' : 'text-red-600 bg-red-50'
                    }`}>
                      {totalPctLabel}%
                    </span>
                  </td>
                  <td className={`${cell} text-right font-bold text-base tabular-nums`}>{fmt(Math.round(targetNum * totalPct / 100))}</td>
                  <td className={`${cell} text-right font-bold text-base tabular-nums hidden sm:table-cell`}>
                    <span className="text-emerald-600">{fmt(totalGiven)}</span>
                  </td>
                  <td className={`${cell} hidden sm:table-cell`}></td>
                  <td className={`${cell} hidden sm:table-cell`}></td>
                </tr>
                {/* Warning row when not at 100% */}
                {!isTotalBalanced && (
                  <tr className={`hidden sm:table-row border-t ${isDark ? 'border-red-500/20 bg-red-500/5' : 'border-red-100 bg-red-50/50'}`}>
                    <td colSpan={7} className="px-4 py-2.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${isTotalUnder ? 'bg-red-500' : 'bg-amber-500'} animate-pulse`} />
                          <span className={`text-xs font-medium ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                            {isTotalUnder
                              ? `${formatPercent(100 - totalPct)}% unallocated (${fmt(Math.round(targetNum * (100 - totalPct) / 100))})`
                              : `${formatPercent(totalPct - 100)}% over-allocated`
                            }
                          </span>
                        </div>
                        {isTotalUnder && (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={distributeRemainingEvenly}
                              className={`text-[11px] px-3 py-1.5 rounded-lg font-semibold border transition-colors ${
                                isDark
                                  ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                                  : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 shadow-sm'
                              }`}
                            >
                              Distribute evenly
                            </button>
                            <button
                              onClick={() => setShowPicker(true)}
                              className={`text-[11px] px-3 py-1.5 rounded-lg font-semibold shadow-sm transition-colors ${
                                isDark
                                  ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                                  : 'bg-emerald-500 text-white hover:bg-emerald-600'
                              }`}
                            >
                              + Add category
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
                {!isTotalBalanced && (
                  <tr className={`sm:hidden border-t ${isDark ? 'border-red-500/20 bg-red-500/5' : 'border-red-100 bg-red-50/50'}`}>
                    <td colSpan={3} className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${isTotalUnder ? 'bg-red-500' : 'bg-amber-500'} animate-pulse`} />
                        <span className={`text-xs font-medium ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                          {isTotalUnder
                            ? `${formatPercent(100 - totalPct)}% unallocated (${fmt(Math.round(targetNum * (100 - totalPct) / 100))})`
                            : `${formatPercent(totalPct - 100)}% over-allocated`
                          }
                        </span>
                      </div>
                      {isTotalUnder && (
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <button
                            onClick={distributeRemainingEvenly}
                            className={`text-[11px] px-2.5 py-1.5 rounded-lg font-semibold border transition-colors ${
                              isDark
                                ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700'
                                : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 shadow-sm'
                            }`}
                          >
                            Distribute evenly
                          </button>
                          <button
                            onClick={() => setShowPicker(true)}
                            className={`text-[11px] px-2.5 py-1.5 rounded-lg font-semibold shadow-sm transition-colors ${
                              isDark
                                ? 'bg-emerald-600 text-white hover:bg-emerald-500'
                                : 'bg-emerald-500 text-white hover:bg-emerald-600'
                            }`}
                          >
                            + Category
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </tbody>
            )}
          </table>

          {/* Uncategorized - droppable zone inside DndContext */}
          {(unassigned.length > 0 || activeCharity) && (
            <div className="hidden sm:block">
            <DroppableUncategorized isDark={isDark} isActive={!!activeCharity}>
              <div className={`px-4 py-2.5 flex items-center gap-2.5 border-t ${isDark ? 'bg-amber-500/5 border-amber-500/20' : 'bg-amber-50/70 border-amber-200/50'}`}>
                <div className="w-2.5 h-2.5 rounded-md bg-amber-500" />
                <span className={`text-[10px] font-bold tracking-wider ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                  {unassigned.length > 0 ? 'NEEDS CATEGORY' : 'DROP TO UNASSIGN'}
                </span>
                {unassigned.length > 0 && (
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                    isDark ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' : 'bg-amber-100 border-amber-200 text-amber-700'
                  }`}>
                    {unassigned.length}
                  </span>
                )}
              </div>
              {unassigned.length > 0 && (
                <table className="w-full">
                  <tbody>
                    {unassigned.map(c => {
                      const cGvn = donations.filter(d => d.charityEin === c.ein).reduce((s, d) => s + d.amount, 0);
                      const charityIsZakat = isZakatEligible(c.walletTag);
                      return (
                        <DraggableCharityRow
                          key={c.ein}
                          charity={c}
                          bucketId={null}
                          given={cGvn}
                          target={getCharityTarget(c.ein)}
                          isDark={isDark}
                          onLogDonation={onLogDonation}
                          onRemove={onRemoveCharity}
                          onSetTarget={handleSetCharityTarget}
                          dimmed={zakatLens && !charityIsZakat}
                        />
                      );
                    })}
                  </tbody>
                </table>
              )}
            </DroppableUncategorized>
            </div>
          )}

          {/* Drag overlay - shows what's being dragged */}
          <DragOverlay>
            {activeCharity && (
              <div className={`px-4 py-3 rounded-xl shadow-2xl ${isDark ? 'bg-slate-800 text-white' : 'bg-white text-slate-900'} border-2 ${isDark ? 'border-emerald-500/50' : 'border-emerald-400'} ring-4 ring-emerald-500/20`}>
                <div className="flex items-center gap-3">
                  <GripVertical className="w-4 h-4 text-emerald-500" />
                  <span className="font-semibold">{activeCharity.name}</span>
                  {activeCharity.amalScore && (
                    <span className={`text-[10px] px-2 py-0.5 rounded-md font-bold ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-100 text-slate-500'}`}>
                      {activeCharity.amalScore}
                    </span>
                  )}
                </div>
              </div>
            )}
          </DragOverlay>
            </DndContext>
          </div>
        </div>
        </>
      )}

      {targetNum > 0 && unassigned.length > 0 && (
        <div className={`sm:hidden px-3 pb-3`}>
          <div className={`rounded-lg border px-3 py-2.5 ${isDark ? 'border-amber-500/30 bg-amber-500/5' : 'border-amber-100 bg-amber-50/50'}`}>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span className={`text-xs font-semibold ${isDark ? 'text-amber-400' : 'text-amber-700'}`}>
                Needs Category ({unassigned.length})
              </span>
            </div>
            <div className="mt-2 space-y-1.5">
              {unassigned.map(c => {
                const cGiven = donations.filter(d => d.charityEin === c.ein).reduce((sum, d) => sum + d.amount, 0);
                return (
                  <MobileCharityAllocationRow
                    key={c.ein}
                    charity={c}
                    given={cGiven}
                    target={getCharityTarget(c.ein)}
                    categoryTarget={0}
                    currentBucketId={null}
                    bucketOptions={mobileBucketOptions}
                    isDark={isDark}
                    onLogDonation={onLogDonation}
                    onSetTarget={handleSetCharityTarget}
                    onMoveCharity={move}
                    onRemove={onRemoveCharity}
                  />
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Empty states */}
      {targetNum > 0 && buckets.length === 0 && (
        <div className={`px-6 py-12 text-center border-t ${border} ${isDark ? 'bg-slate-800/20' : 'bg-slate-50/50'}`}>
          <div className={`w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center ${isDark ? 'bg-emerald-500/10' : 'bg-emerald-50'}`}>
            <Plus className={`w-6 h-6 ${isDark ? 'text-emerald-400' : 'text-emerald-500'}`} />
          </div>
          <p className={`text-sm font-medium mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>No categories yet</p>
          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Add a charity via <span className="font-semibold text-emerald-600">+ Charity</span> to auto-create categories, or use <span className="font-semibold text-emerald-600">+ Category</span> to add manually
          </p>
        </div>
      )}
      {!targetNum && (
        <div className={`px-6 py-12 text-center ${isDark ? 'bg-slate-800/20' : 'bg-slate-50/50'}`}>
          <div className={`w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center ${isDark ? 'bg-slate-700' : 'bg-slate-100'}`}>
            <svg className={`w-6 h-6 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className={`text-sm font-medium mb-1 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Set your zakat target</p>
          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            Enter your target amount above to start allocating
          </p>
        </div>
      )}
    </div>
  );
}

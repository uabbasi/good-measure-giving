/**
 * CategorySplit — one-screen guided allocation that runs after target is set,
 * before Starter Plan. Presents the 4 default categories with sum-locked
 * sliders and "Looks good — create my plan" to persist the buckets.
 *
 * Sliders are rebalanced proportionally when one moves so the total is always
 * exactly 100%. When three sliders are pinned (at 0 or 100), the fourth
 * absorbs the remainder.
 */

import { useCallback, useMemo, useState } from 'react';
import { m } from 'motion/react';
import { writeBatch, doc, Timestamp } from 'firebase/firestore';
import { db } from '../../auth/firebase';
import { useAuth } from '../../auth/useAuth';
import { useProfileState } from '../../contexts/UserFeaturesContext';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { GivingBucket } from '../../../types';

/**
 * Default categories for the split screen. Tags come from
 * src/constants/givingTags.ts so BookmarkAutoCategorize and useAddToGiving
 * can match the buckets created here.
 */
export interface SplitCategory {
  id: string;
  name: string;
  percentage: number;
  color: string;
  /** Tags associated with this bucket (used for auto-assignment). */
  tags: string[];
}

export const DEFAULT_SPLIT_CATEGORIES: SplitCategory[] = [
  {
    id: 'global-humanitarian',
    name: 'Global Humanitarian',
    percentage: 40,
    color: '#5ba88a',
    tags: ['international', 'emergency-response', 'direct-relief', 'food', 'water-sanitation', 'shelter'],
  },
  {
    id: 'domestic',
    name: 'Domestic',
    percentage: 20,
    color: '#5b8fb8',
    tags: ['usa', 'legal-aid', 'advocacy'],
  },
  {
    id: 'education',
    name: 'Education',
    percentage: 20,
    color: '#8b7cb8',
    tags: ['educational', 'vocational', 'research'],
  },
  {
    id: 'local',
    name: 'Local',
    percentage: 20,
    color: '#7a9e6e',
    tags: ['faith-based', 'low-income', 'capacity-building'],
  },
];

function formatUsd(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

/**
 * Rebalance so percentages sum to exactly 100.
 *
 * The slider at `changedIndex` snaps to `nextValue`. The remaining `100 - nextValue`
 * is distributed across the other sliders in proportion to their current values.
 * If the "others" currently sum to 0, the remainder is split evenly.
 *
 * Invariant: the returned array has integer values that always sum to 100.
 * Exported for unit tests.
 */
export function rebalanceSliders(current: number[], changedIndex: number, nextValue: number): number[] {
  const n = current.length;
  const clamped = Math.max(0, Math.min(100, Math.round(nextValue)));
  const result = new Array<number>(n).fill(0);
  result[changedIndex] = clamped;

  const remainder = 100 - clamped;
  const othersIdxs = current.map((_, i) => i).filter(i => i !== changedIndex);
  const othersSum = othersIdxs.reduce((s, i) => s + current[i], 0);

  if (othersIdxs.length === 0) return [clamped];

  if (remainder === 0) {
    // All others should be zero
    return result;
  }

  if (othersSum === 0) {
    // Distribute remainder evenly across the others
    const base = Math.floor(remainder / othersIdxs.length);
    let leftover = remainder - base * othersIdxs.length;
    for (const i of othersIdxs) {
      result[i] = base + (leftover > 0 ? 1 : 0);
      if (leftover > 0) leftover--;
    }
    return result;
  }

  // Proportional distribution. Track rounding drift explicitly and
  // push any residual into the largest "other" so the sum stays == 100.
  let allocated = 0;
  const shares: { i: number; raw: number }[] = othersIdxs.map(i => ({
    i,
    raw: (current[i] / othersSum) * remainder,
  }));
  for (const s of shares) {
    const v = Math.floor(s.raw);
    result[s.i] = v;
    allocated += v;
  }
  let drift = remainder - allocated;
  // Distribute drift to the entries with largest fractional remainder first.
  const byFrac = [...shares].sort((a, b) => (b.raw - Math.floor(b.raw)) - (a.raw - Math.floor(a.raw)));
  let k = 0;
  while (drift > 0 && k < byFrac.length) {
    result[byFrac[k].i] += 1;
    drift--;
    k++;
  }
  // If still drifting (shouldn't happen), push into the first "other"
  if (drift !== 0 && othersIdxs.length > 0) {
    result[othersIdxs[0]] += drift;
  }

  return result;
}

interface CategorySplitProps {
  target: number;
  categories?: SplitCategory[];
  /** Called after buckets are persisted — parent navigates forward. */
  onDone: () => void;
  /** Called if the user wants to skip / customize later. */
  onSkip?: () => void;
}

export function CategorySplit({
  target,
  categories = DEFAULT_SPLIT_CATEGORIES,
  onDone,
  onSkip,
}: CategorySplitProps) {
  const { isDark } = useLandingTheme();
  const { uid } = useAuth();
  const { updateProfile } = useProfileState();
  const [percents, setPercents] = useState<number[]>(() => categories.map(c => c.percentage));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const total = useMemo(() => percents.reduce((s, p) => s + p, 0), [percents]);

  const onSliderChange = useCallback(
    (idx: number, next: number) => {
      setPercents(prev => rebalanceSliders(prev, idx, next));
    },
    [],
  );

  const handleConfirm = useCallback(async () => {
    if (!db || !uid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const now = Timestamp.now();
      const buckets: GivingBucket[] = categories
        .map((c, i) => ({ cat: c, pct: percents[i] }))
        .filter(({ pct }) => pct > 0)
        .map(({ cat, pct }) => ({
          id: crypto.randomUUID(),
          name: cat.name,
          tags: cat.tags,
          percentage: pct,
          color: cat.color,
        }));

      // Use writeBatch for the atomic primary write (matches the StarterPlan
      // pattern), then also call updateProfile so the local profile cache
      // refreshes and downstream gates (Starter Plan, etc) advance.
      const batch = writeBatch(db);
      const userRef = doc(db, 'users', uid);
      batch.update(userRef, {
        givingBuckets: buckets,
        updatedAt: now,
      });
      await batch.commit();
      // Refresh the local profile cache so gates re-evaluate.
      await updateProfile({ givingBuckets: buckets });
      onDone();
    } catch (err) {
      console.error('Failed to save category split:', err);
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }, [uid, saving, categories, percents, onDone, updateProfile]);

  return (
    <m.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      data-testid="category-split"
      className={`rounded-xl border overflow-hidden ${isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'}`}
    >
      <div className={`px-5 py-4 border-b ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
        <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
          How would you like to split your giving?
        </h2>
        <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Pick a starting point - you can always change it later.
        </p>
      </div>

      <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        {categories.map((cat, i) => {
          const pct = percents[i];
          const dollars = Math.round((target * pct) / 100);
          return (
            <div
              key={cat.id}
              data-testid={`split-row-${cat.id}`}
              className={`p-4 rounded-lg border ${isDark ? 'bg-slate-900/40 border-slate-700' : 'bg-slate-50 border-slate-200'}`}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    aria-hidden="true"
                    className="inline-block w-1 h-5 rounded"
                    style={{ backgroundColor: cat.color }}
                  />
                  <span className={`font-medium text-sm ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
                    {cat.name}
                  </span>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-semibold tabular-nums ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {pct}%
                  </div>
                  <div className={`text-xs tabular-nums ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    = {formatUsd(dollars)} of {formatUsd(target)}
                  </div>
                </div>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={pct}
                aria-label={`${cat.name} percentage`}
                data-testid={`split-slider-${cat.id}`}
                onChange={e => onSliderChange(i, parseInt(e.target.value, 10) || 0)}
                className="w-full accent-emerald-600"
                style={{ accentColor: cat.color }}
              />
            </div>
          );
        })}
      </div>

      <div className={`px-5 py-4 border-t flex items-center justify-between gap-3 ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
        <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Total: <span className="font-semibold tabular-nums">{total}%</span>
        </div>
        <div className="flex items-center gap-2">
          {onSkip && (
            <button
              type="button"
              onClick={onSkip}
              className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${isDark ? 'text-slate-400 hover:text-white hover:bg-slate-700' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'}`}
            >
              Skip, I'll customize later
            </button>
          )}
          <button
            type="button"
            onClick={handleConfirm}
            disabled={saving || total !== 100}
            data-testid="split-confirm"
            className="px-4 py-2 rounded-lg font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Looks good - create my plan'}
          </button>
        </div>
      </div>

      {error && (
        <div className={`px-5 py-3 border-t text-xs ${isDark ? 'border-slate-700 text-rose-400' : 'border-slate-100 text-rose-600'}`}>
          {error}
        </div>
      )}
    </m.div>
  );
}

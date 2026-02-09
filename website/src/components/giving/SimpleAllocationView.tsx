/**
 * SimpleAllocationView - Radically simple allocation interface
 *
 * Design principles:
 * - Show only what's needed: target, categories, progress
 * - Tags hidden behind "+ Add" (not sprawled across screen)
 * - No charities inline (allocation is about allocation)
 * - Clean, minimal, world-class simplicity
 */

import React, { useState, useMemo, useEffect } from 'react';
import { Plus, X } from 'lucide-react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useCharities } from '../../hooks/useCharities';
import type { GivingBucket, GivingHistoryEntry } from '../../../types';

interface SimpleAllocationViewProps {
  initialBuckets?: GivingBucket[];
  targetAmount?: number | null;
  donations: GivingHistoryEntry[];
  onSave: (buckets: GivingBucket[], targetAmount: number | null) => Promise<void>;
}

// Tags - just the essentials
const TAGS = [
  // Geography - top ones
  { id: 'palestine', label: 'Palestine' },
  { id: 'pakistan', label: 'Pakistan' },
  { id: 'usa', label: 'USA' },
  { id: 'syria', label: 'Syria' },
  { id: 'yemen', label: 'Yemen' },
  { id: 'afghanistan', label: 'Afghanistan' },
  { id: 'international', label: 'International' },
  // Cause
  { id: 'emergency-response', label: 'Emergency' },
  { id: 'educational', label: 'Education' },
  { id: 'direct-relief', label: 'Direct Relief' },
  { id: 'medical', label: 'Medical' },
  { id: 'food', label: 'Food' },
  { id: 'water-sanitation', label: 'Water' },
  // Population
  { id: 'refugees', label: 'Refugees' },
  { id: 'orphans', label: 'Orphans' },
];

const COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4'];

function formatCurrency(amount: number): string {
  if (amount >= 1000) {
    return `$${(amount / 1000).toFixed(amount % 1000 === 0 ? 0 : 1)}k`;
  }
  return `$${amount}`;
}

function formatFullCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function SimpleAllocationView({
  initialBuckets = [],
  targetAmount: initialTarget,
  donations,
  onSave,
}: SimpleAllocationViewProps) {
  const { isDark } = useLandingTheme();
  const { charities } = useCharities();

  // State
  const [showPicker, setShowPicker] = useState(false);
  const [target, setTarget] = useState(initialTarget?.toString() || '');
  const [buckets, setBuckets] = useState<Array<{
    id: string;
    tagId: string;
    label: string;
    percent: number;
    color: string;
  }>>([]);
  const [isSaving, setIsSaving] = useState(false);

  // Sync from props
  useEffect(() => {
    if (initialTarget && !target) {
      setTarget(initialTarget.toString());
    }
  }, [initialTarget, target]);

  useEffect(() => {
    if (initialBuckets.length > 0 && buckets.length === 0) {
      setBuckets(initialBuckets.map((b, i) => {
        const tag = TAGS.find(t => t.id === b.tags?.[0]) || { id: b.tags?.[0] || '', label: b.name };
        return {
          id: b.id,
          tagId: tag.id,
          label: tag.label,
          percent: b.percentage || 0,
          color: b.color || COLORS[i % COLORS.length],
        };
      }));
    }
  }, [initialBuckets, buckets.length]);

  const targetNum = parseInt(target) || 0;
  const totalPercent = buckets.reduce((sum, b) => sum + b.percent, 0);
  const usedTags = new Set(buckets.map(b => b.tagId));

  // Calculate given per bucket from donations
  const bucketGiven = useMemo(() => {
    const given = new Map<string, number>();
    for (const bucket of buckets) {
      let total = 0;
      for (const donation of donations) {
        if (!donation.charityEin) continue;
        const charity = charities.find(c => c.ein === donation.charityEin);
        const tags = (charity as { causeTags?: string[] })?.causeTags || [];
        if (tags.includes(bucket.tagId)) {
          total += donation.amount;
        }
      }
      given.set(bucket.id, total);
    }
    return given;
  }, [buckets, donations, charities]);

  const totalGiven = Array.from(bucketGiven.values()).reduce((sum, v) => sum + v, 0);

  const addBucket = (tag: { id: string; label: string }) => {
    setBuckets(prev => [...prev, {
      id: crypto.randomUUID(),
      tagId: tag.id,
      label: tag.label,
      percent: 0,
      color: COLORS[prev.length % COLORS.length],
    }]);
    setShowPicker(false);
  };

  const updatePercent = (id: string, percent: number) => {
    setBuckets(prev => prev.map(b => b.id === id ? { ...b, percent: Math.max(0, percent) } : b));
  };

  const removeBucket = (id: string) => {
    setBuckets(prev => prev.filter(b => b.id !== id));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const finalBuckets: GivingBucket[] = buckets.map(b => ({
        id: b.id,
        name: b.label,
        tags: [b.tagId],
        percentage: b.percent,
        color: b.color,
      }));
      await onSave(finalBuckets, targetNum > 0 ? targetNum : null);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className={`rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
      {/* Header */}
      <div className={`flex items-center justify-between p-4 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
        <div className="flex items-center gap-3">
          <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Zakat</span>
          <div className={`flex items-center rounded-lg border ${isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-white'}`}>
            <span className={`pl-3 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>$</span>
            <input
              type="text"
              inputMode="numeric"
              value={target}
              onChange={(e) => setTarget(e.target.value.replace(/\D/g, ''))}
              placeholder="10000"
              className={`w-24 px-2 py-2 bg-transparent text-lg font-semibold focus:outline-none ${isDark ? 'text-white' : 'text-slate-900'}`}
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          {targetNum > 0 && (
            <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {formatFullCurrency(totalGiven)} given
              {totalPercent === 100 && <span className="ml-2 text-emerald-500">Complete</span>}
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={isSaving || buckets.length === 0}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              buckets.length > 0
                ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                : isDark ? 'bg-slate-800 text-slate-500' : 'bg-slate-100 text-slate-400'
            }`}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Allocation list */}
      {targetNum > 0 && (
        <div className="p-4">
          {buckets.length === 0 ? (
            <p className={`text-center py-8 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Add categories to start allocating your zakat
            </p>
          ) : (
            <div className="space-y-3">
              {buckets.map((bucket) => {
                const amount = Math.round(targetNum * bucket.percent / 100);
                const given = bucketGiven.get(bucket.id) || 0;
                const progress = amount > 0 ? Math.min(100, Math.round((given / amount) * 100)) : 0;

                return (
                  <div key={bucket.id} className="flex items-center gap-3">
                    {/* Color dot + name */}
                    <div className="flex items-center gap-2 w-32">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: bucket.color }} />
                      <span className={`text-sm font-medium truncate ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        {bucket.label}
                      </span>
                    </div>

                    {/* Percent input */}
                    <div className="flex items-center gap-1">
                      <input
                        type="text"
                        inputMode="numeric"
                        value={bucket.percent || ''}
                        onChange={(e) => updatePercent(bucket.id, parseInt(e.target.value.replace(/\D/g, '')) || 0)}
                        className={`w-12 px-2 py-1 text-sm text-right rounded border ${
                          isDark
                            ? 'bg-slate-800 border-slate-700 text-white'
                            : 'bg-white border-slate-200 text-slate-900'
                        } focus:outline-none focus:border-emerald-500`}
                        placeholder="0"
                      />
                      <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>%</span>
                    </div>

                    {/* Amount (calculated) */}
                    <span className={`w-20 text-sm text-right ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      {formatCurrency(amount)}
                    </span>

                    {/* Progress bar */}
                    <div className="flex-1 flex items-center gap-2">
                      <div className={`flex-1 h-1.5 rounded-full ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${progress}%`, backgroundColor: progress >= 100 ? '#10b981' : bucket.color }}
                        />
                      </div>
                      <span className={`text-xs w-8 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        {progress}%
                      </span>
                    </div>

                    {/* Remove */}
                    <button
                      onClick={() => removeBucket(bucket.id)}
                      className={`p-1 rounded opacity-40 hover:opacity-100 ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100'}`}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}

              {/* Total */}
              <div className={`flex items-center gap-3 pt-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
                <div className="w-32" />
                <div className={`w-16 text-sm text-right font-medium ${
                  totalPercent === 100 ? 'text-emerald-500' : totalPercent > 100 ? 'text-amber-500' : isDark ? 'text-slate-400' : 'text-slate-600'
                }`}>
                  {totalPercent}%
                </div>
                <span className={`w-20 text-sm text-right font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {formatCurrency(Math.round(targetNum * totalPercent / 100))}
                </span>
                <div className="flex-1" />
                <div className="w-4" />
              </div>
            </div>
          )}

          {/* Add category button */}
          <div className="mt-4">
            {showPicker ? (
              <div className={`p-3 rounded-lg border ${isDark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
                <div className="flex flex-wrap gap-2">
                  {TAGS.filter(t => !usedTags.has(t.id)).map(tag => (
                    <button
                      key={tag.id}
                      onClick={() => addBucket(tag)}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                        isDark
                          ? 'bg-slate-700 text-slate-300 hover:bg-slate-600 hover:text-white'
                          : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
                      }`}
                    >
                      {tag.label}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setShowPicker(false)}
                  className={`mt-2 text-xs ${isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-600'}`}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowPicker(true)}
                className={`flex items-center gap-2 text-sm ${isDark ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}`}
              >
                <Plus className="w-4 h-4" />
                Add category
              </button>
            )}
          </div>
        </div>
      )}

      {/* No target state */}
      {!targetNum && (
        <div className={`p-8 text-center ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          Enter your zakat amount to start
        </div>
      )}
    </div>
  );
}

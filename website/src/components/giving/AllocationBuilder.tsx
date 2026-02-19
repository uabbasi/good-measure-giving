/**
 * AllocationBuilder - Clean, progressive allocation interface
 *
 * Flow:
 * 1. Set total zakat amount
 * 2. Click tags to add categories
 * 3. Set dollar amounts for each
 * 4. See running total, easy to adjust
 *
 * Design: Consistent with site theme - no emojis, clean typography
 */

import React, { useState, useMemo } from 'react';
import { X, DollarSign } from 'lucide-react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useCharities } from '../../hooks/useCharities';
import type { GivingBucket } from '../../../types';

interface AllocationBuilderProps {
  initialBuckets?: GivingBucket[];
  targetAmount?: number | null;
  onSave: (buckets: GivingBucket[], targetAmount: number | null) => Promise<void>;
}

// All available tags organized by type (from actual charity data)
const AVAILABLE_TAGS = {
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
    { id: 'emergency-response', label: 'Emergency Response' },
    { id: 'direct-relief', label: 'Direct Relief' },
    { id: 'food', label: 'Food' },
    { id: 'water-sanitation', label: 'Water' },
    { id: 'medical', label: 'Medical' },
    { id: 'shelter', label: 'Shelter' },
    { id: 'clothing', label: 'Clothing' },
    { id: 'educational', label: 'Education' },
    { id: 'vocational', label: 'Vocational Training' },
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

// Colors for buckets (cycle through)
const BUCKET_COLORS = [
  '#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

function generateId(): string {
  return crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

// Get all tags as a flat list
const ALL_TAGS = [...AVAILABLE_TAGS.geography, ...AVAILABLE_TAGS.cause];

export function AllocationBuilder({
  initialBuckets = [],
  targetAmount: initialTarget,
  onSave,
}: AllocationBuilderProps) {
  const { isDark } = useLandingTheme();
  const { charities } = useCharities();

  // Filter state
  const [zakatOnly, setZakatOnly] = useState(false);

  // Filter charities based on zakat eligibility
  const filteredCharities = useMemo(() => {
    if (!zakatOnly) return charities;
    return charities.filter(c => {
      const walletTag = (c as { amalEvaluation?: { wallet_tag?: string } }).amalEvaluation?.wallet_tag || '';
      return walletTag.includes('ZAKAT');
    });
  }, [charities, zakatOnly]);

  // Count charities per tag
  const tagCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const charity of filteredCharities) {
      const tags = (charity as { causeTags?: string[] | null }).causeTags || [];
      for (const tag of tags) {
        counts.set(tag, (counts.get(tag) || 0) + 1);
      }
    }
    return counts;
  }, [filteredCharities]);

  // State
  const [targetAmount, setTargetAmount] = useState<string>(initialTarget?.toString() || '');
  const [buckets, setBuckets] = useState<Array<{
    id: string;
    tagId: string;
    label: string;
    amount: number;
    percent: number;
    color: string;
  }>>(() => {
    if (initialBuckets.length > 0) {
      const target = initialTarget || 0;
      return initialBuckets.map((b, i) => {
        // Find matching tag by id or name
        const matchingTag = ALL_TAGS.find(t =>
          t.id === b.tags?.[0] ||
          t.label.toLowerCase() === b.name.toLowerCase()
        );
        return {
          id: b.id,
          tagId: matchingTag?.id || b.tags?.[0] || b.name.toLowerCase(),
          label: matchingTag?.label || b.name,
          amount: target > 0 ? Math.round(target * b.percentage / 100) : 0,
          percent: b.percentage || 0,
          color: b.color || BUCKET_COLORS[i % BUCKET_COLORS.length],
        };
      });
    }
    return [];
  });

  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);

  const target = targetAmount ? parseFloat(targetAmount) : 0;
  const totalAllocated = buckets.reduce((sum, b) => sum + b.amount, 0);
  const totalPercent = buckets.reduce((sum, b) => sum + b.percent, 0);
  const remaining = target - totalAllocated;

  // Track which tags are already added
  const usedTagIds = new Set(buckets.map(b => b.tagId));

  // Toggle a tag (add if not present, remove if present)
  const toggleTag = (tag: { id: string; label: string }) => {
    if (usedTagIds.has(tag.id)) {
      // Remove the bucket with this tag
      setBuckets(prev => prev.filter(b => b.tagId !== tag.id));
    } else {
      // Add new bucket
      const newBucket = {
        id: generateId(),
        tagId: tag.id,
        label: tag.label,
        amount: 0,
        percent: 0,
        color: BUCKET_COLORS[buckets.length % BUCKET_COLORS.length],
      };
      setBuckets(prev => [...prev, newBucket]);
    }
  };

  // Allocate remaining amount to a bucket
  const allocateRemaining = (id: string) => {
    if (remaining <= 0) return;
    const remainingPercent = 100 - totalPercent;
    setBuckets(prev => prev.map(b =>
      b.id === id
        ? { ...b, amount: b.amount + remaining, percent: b.percent + remainingPercent }
        : b
    ));
  };

  // Split remaining evenly across buckets with $0
  const splitEvenly = () => {
    const zeroBuckets = buckets.filter(b => b.amount === 0);
    if (zeroBuckets.length === 0 || remaining <= 0) return;

    const amountEach = Math.floor(remaining / zeroBuckets.length);
    const percentEach = Math.floor((100 - totalPercent) / zeroBuckets.length);
    const zeroIds = new Set(zeroBuckets.map(b => b.id));

    setBuckets(prev => prev.map(b =>
      zeroIds.has(b.id)
        ? { ...b, amount: amountEach, percent: percentEach }
        : b
    ));
  };

  // Update bucket amount (and auto-calculate percent)
  const updateBucketAmount = (id: string, amount: number) => {
    const newAmount = Math.max(0, amount);
    const newPercent = target > 0 ? Math.round((newAmount / target) * 100) : 0;
    setBuckets(prev => prev.map(b =>
      b.id === id ? { ...b, amount: newAmount, percent: newPercent } : b
    ));
  };

  // Update bucket percent (and auto-calculate amount)
  const updateBucketPercent = (id: string, percent: number) => {
    const newPercent = Math.max(0, percent);
    const newAmount = target > 0 ? Math.round((newPercent / 100) * target) : 0;
    setBuckets(prev => prev.map(b =>
      b.id === id ? { ...b, percent: newPercent, amount: newAmount } : b
    ));
  };

  // Remove bucket
  const removeBucket = (id: string) => {
    setBuckets(prev => prev.filter(b => b.id !== id));
  };

  // Save buckets
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

      await onSave(finalBuckets, target > 0 ? target : null);
      setLastSaved(new Date());
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Step 1: Total Zakat Amount */}
      <div className={`p-6 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <label className={`block text-sm font-medium mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          What's your total zakat for this year?
        </label>
        <div className="flex items-center gap-3">
          <div className={`
            flex items-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors flex-grow max-w-xs
            ${isDark
              ? 'bg-slate-800 border-slate-700 focus-within:border-emerald-500'
              : 'bg-white border-slate-200 focus-within:border-emerald-500'
            }
          `}>
            <DollarSign className={`w-5 h-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={targetAmount}
              onChange={(e) => setTargetAmount(e.target.value.replace(/\D/g, ''))}
              placeholder="10000"
              className={`
                flex-grow text-2xl font-semibold bg-transparent border-0 p-0 focus:outline-none
                ${isDark ? 'text-white placeholder-slate-600' : 'text-slate-900 placeholder-slate-300'}
              `}
            />
          </div>
          {target > 0 && (
            <div className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              {formatCurrency(remaining)} remaining
            </div>
          )}
        </div>
      </div>

      {/* Step 2: Choose Categories */}
      {target > 0 && (
        <div className={`p-6 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <label className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Click to add categories
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={zakatOnly}
                  onChange={(e) => setZakatOnly(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className={`text-xs font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Zakat eligible only
                </span>
              </label>
            </div>
            {buckets.length > 0 && (
              <div className={`text-sm font-medium ${
                totalPercent === 100
                  ? 'text-emerald-500'
                  : totalPercent > 100
                  ? 'text-amber-500'
                  : isDark ? 'text-slate-400' : 'text-slate-600'
              }`}>
                {formatCurrency(totalAllocated)} of {formatCurrency(target)} ({totalPercent}%)
              </div>
            )}
          </div>

          {/* Geography tags */}
          <div className="mb-4">
            <div className={`text-xs font-medium mb-2 uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              Geography
            </div>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_TAGS.geography.map(tag => {
                const isAdded = usedTagIds.has(tag.id);
                const count = tagCounts.get(tag.id) || 0;
                return (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => toggleTag(tag)}
                    className={`
                      px-2.5 py-1 rounded text-xs font-medium transition-all cursor-pointer
                      ${isAdded
                        ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                        : count === 0
                        ? isDark
                          ? 'bg-slate-900 text-slate-600 border border-slate-800 cursor-not-allowed'
                          : 'bg-slate-50 text-slate-400 border border-slate-100 cursor-not-allowed'
                        : isDark
                        ? 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 border border-slate-200'
                      }
                    `}
                    disabled={count === 0 && !isAdded}
                    title={count === 0 ? 'No charities with this tag' : `${count} charities`}
                  >
                    {tag.label}
                    <span className={`ml-1 ${isAdded ? 'text-emerald-200' : count === 0 ? '' : isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Cause tags */}
          <div className="mb-4">
            <div className={`text-xs font-medium mb-2 uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              Cause
            </div>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_TAGS.cause.map(tag => {
                const isAdded = usedTagIds.has(tag.id);
                const count = tagCounts.get(tag.id) || 0;
                return (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => toggleTag(tag)}
                    className={`
                      px-2.5 py-1 rounded text-xs font-medium transition-all cursor-pointer
                      ${isAdded
                        ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                        : count === 0
                        ? isDark
                          ? 'bg-slate-900 text-slate-600 border border-slate-800 cursor-not-allowed'
                          : 'bg-slate-50 text-slate-400 border border-slate-100 cursor-not-allowed'
                        : isDark
                        ? 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 border border-slate-200'
                      }
                    `}
                    disabled={count === 0 && !isAdded}
                    title={count === 0 ? 'No charities with this tag' : `${count} charities`}
                  >
                    {tag.label}
                    <span className={`ml-1 ${isAdded ? 'text-emerald-200' : count === 0 ? '' : isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Population tags */}
          <div className="mb-6">
            <div className={`text-xs font-medium mb-2 uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              Population
            </div>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_TAGS.population.map(tag => {
                const isAdded = usedTagIds.has(tag.id);
                const count = tagCounts.get(tag.id) || 0;
                return (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => toggleTag(tag)}
                    className={`
                      px-2.5 py-1 rounded text-xs font-medium transition-all cursor-pointer
                      ${isAdded
                        ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                        : count === 0
                        ? isDark
                          ? 'bg-slate-900 text-slate-600 border border-slate-800 cursor-not-allowed'
                          : 'bg-slate-50 text-slate-400 border border-slate-100 cursor-not-allowed'
                        : isDark
                        ? 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 border border-slate-200'
                      }
                    `}
                    disabled={count === 0 && !isAdded}
                    title={count === 0 ? 'No charities with this tag' : `${count} charities`}
                  >
                    {tag.label}
                    <span className={`ml-1 ${isAdded ? 'text-emerald-200' : count === 0 ? '' : isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Added buckets with amounts */}
          {buckets.length > 0 && (
            <div className={`border-t pt-4 ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <div className={`text-xs font-medium mb-3 uppercase tracking-wide ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                Your allocations
              </div>
              <div className="space-y-2">
                {buckets.map((bucket) => (
                  <div
                    key={bucket.id}
                    className={`
                      flex items-center gap-3 p-3 rounded-lg group
                      ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}
                    `}
                  >
                    {/* Color indicator */}
                    <div
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: bucket.color }}
                    />

                    {/* Name */}
                    <span className={`flex-grow font-medium text-sm ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      {bucket.label}
                    </span>

                    {/* Percentage input */}
                    <div className={`
                      flex items-center gap-1 px-2 py-1 rounded border
                      ${isDark
                        ? 'bg-slate-900 border-slate-700 focus-within:border-emerald-500'
                        : 'bg-white border-slate-200 focus-within:border-emerald-500'
                      }
                    `}>
                      <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={bucket.percent || ''}
                        onChange={(e) => updateBucketPercent(bucket.id, parseInt(e.target.value.replace(/\D/g, '')) || 0)}
                        className={`
                          w-10 text-right text-sm font-medium bg-transparent border-0 p-0 focus:outline-none
                          ${isDark ? 'text-white' : 'text-slate-900'}
                        `}
                        placeholder="0"
                      />
                      <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>%</span>
                    </div>

                    {/* OR divider */}
                    <span className={`text-xs ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>or</span>

                    {/* Amount input */}
                    <div className={`
                      flex items-center gap-1 px-2 py-1 rounded border
                      ${isDark
                        ? 'bg-slate-900 border-slate-700 focus-within:border-emerald-500'
                        : 'bg-white border-slate-200 focus-within:border-emerald-500'
                      }
                    `}>
                      <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>$</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={bucket.amount || ''}
                        onChange={(e) => updateBucketAmount(bucket.id, parseInt(e.target.value.replace(/\D/g, '')) || 0)}
                        className={`
                          w-16 text-right text-sm font-medium bg-transparent border-0 p-0 focus:outline-none
                          ${isDark ? 'text-white' : 'text-slate-900'}
                        `}
                        placeholder="0"
                      />
                    </div>

                    {/* Allocate remaining button */}
                    {remaining > 0 && (
                      <button
                        type="button"
                        onClick={() => allocateRemaining(bucket.id)}
                        className={`
                          px-2 py-1 rounded text-xs font-medium transition-colors
                          ${isDark
                            ? 'bg-slate-700 text-slate-300 hover:bg-slate-600 hover:text-white'
                            : 'bg-slate-200 text-slate-600 hover:bg-slate-300 hover:text-slate-900'
                          }
                        `}
                        title={`Add remaining ${formatCurrency(remaining)}`}
                      >
                        +rest
                      </button>
                    )}

                    {/* Remove button */}
                    <button
                      type="button"
                      onClick={() => removeBucket(bucket.id)}
                      className={`
                        p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity
                        ${isDark ? 'hover:bg-slate-700 text-slate-500' : 'hover:bg-slate-200 text-slate-400'}
                      `}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Split evenly button */}
              {remaining > 0 && buckets.some(b => b.amount === 0) && (
                <button
                  type="button"
                  onClick={splitEvenly}
                  className={`
                    mt-3 px-3 py-1.5 rounded text-xs font-medium transition-colors
                    ${isDark
                      ? 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700'
                      : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-slate-200'
                    }
                  `}
                >
                  Split {formatCurrency(remaining)} evenly across {buckets.filter(b => b.amount === 0).length} empty
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Summary & Save */}
      {buckets.length > 0 && (
        <div className={`p-6 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
          {/* Visual breakdown */}
          <div className="mb-6">
            <div className={`h-3 rounded-full overflow-hidden flex ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`}>
              {buckets.map((bucket) => {
                const percent = target > 0 ? (bucket.amount / target) * 100 : 0;
                return (
                  <div
                    key={bucket.id}
                    className="h-full transition-all duration-300"
                    style={{
                      width: `${Math.min(percent, 100)}%`,
                      backgroundColor: bucket.color,
                    }}
                    title={`${bucket.label}: ${formatCurrency(bucket.amount)}`}
                  />
                );
              })}
            </div>
            {totalPercent > 100 && (
              <p className="mt-2 text-sm text-amber-500">
                You're {formatCurrency(totalAllocated - target)} over your target — adjust amounts above
              </p>
            )}
            {totalPercent < 100 && totalPercent > 0 && (
              <p className={`mt-2 text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                {formatCurrency(remaining)} unallocated — add more categories or adjust amounts
              </p>
            )}
          </div>

          {/* Save button */}
          <div className="flex items-center justify-between">
            <div>
              {lastSaved && (
                <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  Last saved {lastSaved.toLocaleTimeString()}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving || buckets.length === 0}
              className={`
                px-6 py-2.5 rounded-lg font-medium transition-colors
                ${buckets.length > 0 && !isSaving
                  ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                  : `${isDark ? 'bg-slate-800 text-slate-500' : 'bg-slate-200 text-slate-400'} cursor-not-allowed`
                }
              `}
            >
              {isSaving ? 'Saving...' : 'Save Allocation'}
            </button>
          </div>
        </div>
      )}

    </div>
  );
}

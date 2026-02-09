/**
 * Rich allocation settings with user-defined buckets and tags
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { GivingBucket, CharityBucketAssignment, CharitySummary } from '../../../types';

interface AllocationSettingsProps {
  buckets: GivingBucket[];
  charityAssignments: CharityBucketAssignment[];
  targetZakatAmount: number | null;
  charities?: CharitySummary[]; // For showing matched charities
  onSaveBuckets: (buckets: GivingBucket[]) => Promise<void>;
  onSaveAssignments: (assignments: CharityBucketAssignment[]) => Promise<void>;
  onSaveTargetAmount: (amount: number | null) => Promise<void>;
}

// Available tags organized by type
const AVAILABLE_TAGS = {
  cause: [
    { id: 'education', label: 'Education' },
    { id: 'poverty', label: 'Poverty Relief' },
    { id: 'healthcare', label: 'Healthcare' },
    { id: 'humanitarian', label: 'Humanitarian' },
    { id: 'dawah', label: 'Dawah & Islamic' },
    { id: 'environment', label: 'Environment' },
    { id: 'research', label: 'Research & Policy' },
    { id: 'orphans', label: 'Orphan Care' },
    { id: 'refugees', label: 'Refugee Support' },
    { id: 'water', label: 'Water & Sanitation' },
    { id: 'food', label: 'Food Security' },
  ],
  geography: [
    { id: 'pakistan', label: 'Pakistan' },
    { id: 'india', label: 'India' },
    { id: 'bangladesh', label: 'Bangladesh' },
    { id: 'palestine', label: 'Palestine' },
    { id: 'syria', label: 'Syria' },
    { id: 'yemen', label: 'Yemen' },
    { id: 'afghanistan', label: 'Afghanistan' },
    { id: 'somalia', label: 'Somalia' },
    { id: 'usa', label: 'United States' },
    { id: 'local', label: 'Local Community' },
    { id: 'global', label: 'Global' },
    { id: 'middle-east', label: 'Middle East' },
    { id: 'africa', label: 'Africa' },
    { id: 'south-asia', label: 'South Asia' },
  ],
};

const BUCKET_COLORS = [
  '#10b981', // emerald
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#f59e0b', // amber
  '#ec4899', // pink
  '#14b8a6', // teal
  '#f97316', // orange
  '#6366f1', // indigo
];

function generateId(): string {
  return crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// Tag chip component
function TagChip({
  label,
  selected,
  onClick,
  isDark,
  size = 'md',
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  isDark: boolean;
  size?: 'sm' | 'md';
}) {
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        ${sizeClasses} rounded-full font-medium transition-all
        ${selected
          ? 'bg-emerald-600 text-white'
          : isDark
          ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
        }
      `}
    >
      {label}
    </button>
  );
}

// Single bucket editor
function BucketEditor({
  bucket,
  index,
  onUpdate,
  onDelete,
  isDark,
}: {
  bucket: GivingBucket;
  index: number;
  onUpdate: (updates: Partial<GivingBucket>) => void;
  onDelete: () => void;
  isDark: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(bucket.tags.length === 0);
  const [showTagPicker, setShowTagPicker] = useState(false);

  const toggleTag = (tagId: string) => {
    const newTags = bucket.tags.includes(tagId)
      ? bucket.tags.filter(t => t !== tagId)
      : [...bucket.tags, tagId];
    onUpdate({ tags: newTags });
  };

  const allTags = [...AVAILABLE_TAGS.cause, ...AVAILABLE_TAGS.geography];
  const selectedTagLabels = bucket.tags
    .map(id => allTags.find(t => t.id === id)?.label || id)
    .join(', ');

  return (
    <div className={`
      rounded-xl border transition-all
      ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}
    `}>
      {/* Header - always visible */}
      <div className="p-4">
        <div className="flex items-center gap-3">
          {/* Color indicator */}
          <div
            className="w-4 h-4 rounded-full flex-shrink-0 ring-2 ring-offset-2"
            style={{
              backgroundColor: bucket.color || BUCKET_COLORS[index % BUCKET_COLORS.length],
              ['--tw-ring-color' as string]: bucket.color || BUCKET_COLORS[index % BUCKET_COLORS.length],
              ['--tw-ring-offset-color' as string]: isDark ? '#0f172a' : '#ffffff',
            }}
          />

          {/* Name input */}
          <input
            type="text"
            value={bucket.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            placeholder="Bucket name (e.g., Pakistan Relief)"
            className={`
              flex-grow text-base font-medium px-3 py-1.5 rounded-lg border
              transition-colors
              ${isDark
                ? 'bg-slate-800/50 border-slate-700 text-white placeholder-slate-500 focus:border-slate-500 focus:bg-slate-800'
                : 'bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400 focus:border-slate-400 focus:bg-white'
              }
              focus:outline-none
            `}
          />

          {/* Percentage input */}
          <div className={`
            flex items-center gap-1 px-3 py-1.5 rounded-lg border
            ${isDark
              ? 'bg-slate-800/50 border-slate-700 focus-within:border-slate-500 focus-within:bg-slate-800'
              : 'bg-slate-50 border-slate-200 focus-within:border-slate-400 focus-within:bg-white'
            }
            transition-colors
          `}>
            <input
              type="number"
              value={bucket.percentage || ''}
              onChange={(e) => onUpdate({ percentage: parseInt(e.target.value) || 0 })}
              placeholder="0"
              min="0"
              max="100"
              className={`
                w-12 text-right text-base font-semibold bg-transparent border-0 p-0
                focus:outline-none focus:ring-0
                ${isDark ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'}
              `}
            />
            <span className={`text-base ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>%</span>
          </div>

          {/* Expand/collapse */}
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className={`p-1.5 rounded-lg transition-colors ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100'}`}
          >
            <svg
              className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''} ${isDark ? 'text-slate-400' : 'text-slate-500'}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Delete */}
          <button
            type="button"
            onClick={onDelete}
            className={`p-1.5 rounded-lg transition-colors ${isDark ? 'hover:bg-red-500/20 text-slate-400 hover:text-red-400' : 'hover:bg-red-50 text-slate-400 hover:text-red-500'}`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>

        {/* Tags preview (when collapsed) */}
        {!isExpanded && bucket.tags.length > 0 && (
          <p className={`mt-2 text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
            Tags: {selectedTagLabels}
          </p>
        )}
      </div>

      {/* Expanded section - tag picker */}
      {isExpanded && (
        <div className={`px-4 pb-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
          {/* Description input */}
          <div className="mt-4">
            <label className={`text-xs font-medium mb-1.5 block ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              DESCRIPTION
            </label>
            <input
              type="text"
              value={bucket.description || ''}
              onChange={(e) => onUpdate({ description: e.target.value })}
              placeholder="Optional description..."
              className={`
                w-full text-sm px-3 py-2 rounded-lg border transition-colors
                ${isDark
                  ? 'bg-slate-800/50 border-slate-700 text-slate-300 placeholder-slate-600 focus:border-slate-500 focus:bg-slate-800'
                  : 'bg-slate-50 border-slate-200 text-slate-600 placeholder-slate-400 focus:border-slate-400 focus:bg-white'
                }
                focus:outline-none
              `}
            />
          </div>

          {/* Tag sections */}
          <div className="mt-4 space-y-3">
            <div>
              <p className={`text-xs font-medium mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                CAUSE TAGS
              </p>
              <div className="flex flex-wrap gap-1.5">
                {AVAILABLE_TAGS.cause.map(tag => (
                  <TagChip
                    key={tag.id}
                    label={tag.label}
                    selected={bucket.tags.includes(tag.id)}
                    onClick={() => toggleTag(tag.id)}
                    isDark={isDark}
                    size="sm"
                  />
                ))}
              </div>
            </div>

            <div>
              <p className={`text-xs font-medium mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                GEOGRAPHY TAGS
              </p>
              <div className="flex flex-wrap gap-1.5">
                {AVAILABLE_TAGS.geography.map(tag => (
                  <TagChip
                    key={tag.id}
                    label={tag.label}
                    selected={bucket.tags.includes(tag.id)}
                    onClick={() => toggleTag(tag.id)}
                    isDark={isDark}
                    size="sm"
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Color picker */}
          <div className="mt-4">
            <p className={`text-xs font-medium mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              COLOR
            </p>
            <div className="flex gap-2">
              {BUCKET_COLORS.map((color, i) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => onUpdate({ color })}
                  className={`
                    w-6 h-6 rounded-full transition-transform
                    ${bucket.color === color ? 'ring-2 ring-offset-2 ring-emerald-500 scale-110' : 'hover:scale-110'}
                    ${isDark ? 'ring-offset-slate-900' : 'ring-offset-white'}
                  `}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function AllocationSettings({
  buckets,
  charityAssignments,
  targetZakatAmount,
  charities,
  onSaveBuckets,
  onSaveAssignments,
  onSaveTargetAmount,
}: AllocationSettingsProps) {
  const { isDark } = useLandingTheme();

  // Local state for editing
  const [localBuckets, setLocalBuckets] = useState<GivingBucket[]>([]);
  const [localTarget, setLocalTarget] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Initialize local state from props
  useEffect(() => {
    setLocalBuckets(buckets.length > 0 ? buckets : []);
    setLocalTarget(targetZakatAmount?.toString() || '');
    setHasChanges(false);
  }, [buckets, targetZakatAmount]);

  const totalPercentage = localBuckets.reduce((sum, b) => sum + (b.percentage || 0), 0);
  const isValidTotal = totalPercentage === 100 || totalPercentage === 0;

  const addBucket = () => {
    const newBucket: GivingBucket = {
      id: generateId(),
      name: '',
      tags: [],
      percentage: 0,
      color: BUCKET_COLORS[localBuckets.length % BUCKET_COLORS.length],
    };
    setLocalBuckets([...localBuckets, newBucket]);
    setHasChanges(true);
  };

  const updateBucket = (id: string, updates: Partial<GivingBucket>) => {
    setLocalBuckets(prev =>
      prev.map(b => b.id === id ? { ...b, ...updates } : b)
    );
    setHasChanges(true);
  };

  const deleteBucket = (id: string) => {
    setLocalBuckets(prev => prev.filter(b => b.id !== id));
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!isValidTotal && totalPercentage !== 0) return;

    setIsSaving(true);
    try {
      // Filter out empty buckets
      const validBuckets = localBuckets.filter(b => b.name.trim() && b.percentage > 0);
      await onSaveBuckets(validBuckets);

      const numericTarget = localTarget ? parseFloat(localTarget) : null;
      await onSaveTargetAmount(numericTarget && numericTarget > 0 ? numericTarget : null);

      setHasChanges(false);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setLocalBuckets(buckets.length > 0 ? buckets : []);
    setLocalTarget(targetZakatAmount?.toString() || '');
    setHasChanges(false);
  };

  // Quick-add preset buckets
  const addPreset = (preset: 'cause' | 'geography' | 'balanced') => {
    let newBuckets: GivingBucket[] = [];

    if (preset === 'cause') {
      newBuckets = [
        { id: generateId(), name: 'Humanitarian Aid', tags: ['humanitarian', 'refugees'], percentage: 30, color: BUCKET_COLORS[0] },
        { id: generateId(), name: 'Education', tags: ['education'], percentage: 25, color: BUCKET_COLORS[1] },
        { id: generateId(), name: 'Healthcare', tags: ['healthcare'], percentage: 20, color: BUCKET_COLORS[2] },
        { id: generateId(), name: 'Poverty Relief', tags: ['poverty', 'food'], percentage: 15, color: BUCKET_COLORS[3] },
        { id: generateId(), name: 'Islamic Causes', tags: ['dawah'], percentage: 10, color: BUCKET_COLORS[4] },
      ];
    } else if (preset === 'geography') {
      newBuckets = [
        { id: generateId(), name: 'Pakistan', tags: ['pakistan'], percentage: 30, color: BUCKET_COLORS[0] },
        { id: generateId(), name: 'Palestine', tags: ['palestine'], percentage: 25, color: BUCKET_COLORS[1] },
        { id: generateId(), name: 'Local Community', tags: ['local', 'usa'], percentage: 25, color: BUCKET_COLORS[2] },
        { id: generateId(), name: 'Global', tags: ['global'], percentage: 20, color: BUCKET_COLORS[3] },
      ];
    } else {
      newBuckets = [
        { id: generateId(), name: 'Pakistan Humanitarian', tags: ['pakistan', 'humanitarian'], percentage: 25, color: BUCKET_COLORS[0] },
        { id: generateId(), name: 'Local Education', tags: ['local', 'education'], percentage: 20, color: BUCKET_COLORS[1] },
        { id: generateId(), name: 'Global Healthcare', tags: ['global', 'healthcare'], percentage: 20, color: BUCKET_COLORS[2] },
        { id: generateId(), name: 'Islamic Causes', tags: ['dawah'], percentage: 15, color: BUCKET_COLORS[4] },
        { id: generateId(), name: 'Refugee Support', tags: ['refugees', 'humanitarian'], percentage: 20, color: BUCKET_COLORS[5] },
      ];
    }

    setLocalBuckets(newBuckets);
    setHasChanges(true);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const targetAmount = localTarget ? parseFloat(localTarget) : 0;

  return (
    <div className="space-y-6">
      {/* Zakat Target Amount */}
      <div className={`p-6 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <h3 className={`text-lg font-semibold mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
          Annual Zakat Target
        </h3>
        <div className="flex items-center gap-4">
          <div className="relative">
            <span className={`absolute left-4 top-1/2 -translate-y-1/2 text-xl ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              $
            </span>
            <input
              type="number"
              value={localTarget}
              onChange={(e) => {
                setLocalTarget(e.target.value);
                setHasChanges(true);
              }}
              className={`
                w-48 pl-10 pr-4 py-3 text-2xl font-bold rounded-xl border
                ${isDark
                  ? 'bg-slate-800 border-slate-700 text-white focus:border-emerald-500'
                  : 'bg-slate-50 border-slate-200 text-slate-900 focus:border-emerald-500'
                }
                focus:outline-none focus:ring-2 focus:ring-emerald-500/20
              `}
              placeholder="10,000"
              min="0"
              step="100"
            />
          </div>
          <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
            Your total zakat obligation for the year
          </p>
        </div>
      </div>

      {/* Allocation Buckets */}
      <div className={`p-6 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Allocation Buckets
            </h3>
            <p className={`text-sm mt-1 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              Create custom categories with cause and geography tags
            </p>
          </div>
          <div className={`
            text-sm font-semibold px-3 py-1.5 rounded-lg
            ${isValidTotal
              ? 'bg-emerald-500/20 text-emerald-500'
              : 'bg-red-500/20 text-red-500'
            }
          `}>
            {totalPercentage}% / 100%
          </div>
        </div>

        {/* Presets */}
        {localBuckets.length === 0 && (
          <div className={`mb-6 p-4 rounded-xl ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
            <p className={`text-sm mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Start with a preset or create your own:
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => addPreset('cause')}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-colors
                  ${isDark
                    ? 'bg-slate-700 text-white hover:bg-slate-600'
                    : 'bg-white text-slate-900 hover:bg-slate-100 border border-slate-200'
                  }
                `}
              >
                By Cause
              </button>
              <button
                type="button"
                onClick={() => addPreset('geography')}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-colors
                  ${isDark
                    ? 'bg-slate-700 text-white hover:bg-slate-600'
                    : 'bg-white text-slate-900 hover:bg-slate-100 border border-slate-200'
                  }
                `}
              >
                By Geography
              </button>
              <button
                type="button"
                onClick={() => addPreset('balanced')}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-colors
                  ${isDark
                    ? 'bg-slate-700 text-white hover:bg-slate-600'
                    : 'bg-white text-slate-900 hover:bg-slate-100 border border-slate-200'
                  }
                `}
              >
                Balanced Mix
              </button>
            </div>
          </div>
        )}

        {/* Bucket list */}
        <div className="space-y-3">
          {localBuckets.map((bucket, index) => (
            <BucketEditor
              key={bucket.id}
              bucket={bucket}
              index={index}
              onUpdate={(updates) => updateBucket(bucket.id, updates)}
              onDelete={() => deleteBucket(bucket.id)}
              isDark={isDark}
            />
          ))}
        </div>

        {/* Add bucket button */}
        <button
          type="button"
          onClick={addBucket}
          className={`
            w-full mt-4 py-3 rounded-xl border-2 border-dashed font-medium transition-colors
            flex items-center justify-center gap-2
            ${isDark
              ? 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'
              : 'border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700'
            }
          `}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Add Bucket
        </button>

        {/* Validation message */}
        {!isValidTotal && totalPercentage !== 0 && (
          <p className="mt-4 text-sm text-red-500">
            Allocations must sum to exactly 100% (currently {totalPercentage}%)
          </p>
        )}

        {/* Summary */}
        {targetAmount > 0 && localBuckets.length > 0 && (
          <div className={`mt-6 p-4 rounded-xl ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
            <p className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              Allocation Summary
            </p>
            <div className="space-y-2">
              {localBuckets.filter(b => b.percentage > 0).map(bucket => (
                <div key={bucket.id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: bucket.color || BUCKET_COLORS[0] }}
                    />
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>
                      {bucket.name || 'Unnamed'}
                    </span>
                  </div>
                  <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {formatCurrency(targetAmount * bucket.percentage / 100)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Save/Reset buttons */}
      {hasChanges && (
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={handleReset}
            disabled={isSaving}
            className={`
              px-5 py-2.5 rounded-xl font-medium transition-colors
              ${isDark
                ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }
              disabled:opacity-50
            `}
          >
            Reset
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving || (!isValidTotal && totalPercentage !== 0)}
            className="px-5 py-2.5 rounded-xl font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isSaving && (
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            Save Changes
          </button>
        </div>
      )}
    </div>
  );
}

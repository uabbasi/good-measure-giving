/**
 * Allocation Wizard - Step-by-step flow for setting up giving buckets
 *
 * Flow:
 * 1. Pick causes (what matters to you)
 * 2. Pick regions (where to give)
 * 3. Set percentages (visual pie chart)
 * 4. Review & save
 */

import React, { useState, useMemo } from 'react';
import { AnimatePresence, m, useReducedMotion } from 'motion/react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import type { GivingBucket } from '../../../types';

interface AllocationWizardProps {
  initialBuckets?: GivingBucket[];
  targetAmount?: number | null;
  onComplete: (buckets: GivingBucket[], targetAmount: number | null) => Promise<void>;
  onCancel?: () => void;
}

// Cause options with icons and colors
const CAUSES = [
  { id: 'humanitarian', label: 'Humanitarian Aid', icon: '🌍', color: '#ef4444', description: 'Emergency relief & disaster response' },
  { id: 'education', label: 'Education', icon: '📚', color: '#3b82f6', description: 'Schools, scholarships & learning' },
  { id: 'healthcare', label: 'Healthcare', icon: '🏥', color: '#10b981', description: 'Medical care & health services' },
  { id: 'poverty', label: 'Poverty Relief', icon: '🏠', color: '#f59e0b', description: 'Housing, food & economic support' },
  { id: 'orphans', label: 'Orphan Care', icon: '👶', color: '#ec4899', description: 'Support for orphaned children' },
  { id: 'refugees', label: 'Refugees', icon: '🏃', color: '#8b5cf6', description: 'Displaced persons & resettlement' },
  { id: 'water', label: 'Water & Sanitation', icon: '💧', color: '#06b6d4', description: 'Clean water access' },
  { id: 'dawah', label: 'Islamic Causes', icon: '🕌', color: '#14b8a6', description: 'Mosques, dawah & Islamic education' },
  { id: 'food', label: 'Food Security', icon: '🍞', color: '#84cc16', description: 'Food banks & nutrition programs' },
];

// Geography options
const REGIONS = [
  { id: 'palestine', label: 'Palestine', flag: '🇵🇸' },
  { id: 'pakistan', label: 'Pakistan', flag: '🇵🇰' },
  { id: 'syria', label: 'Syria', flag: '🇸🇾' },
  { id: 'yemen', label: 'Yemen', flag: '🇾🇪' },
  { id: 'afghanistan', label: 'Afghanistan', flag: '🇦🇫' },
  { id: 'somalia', label: 'Somalia', flag: '🇸🇴' },
  { id: 'bangladesh', label: 'Bangladesh', flag: '🇧🇩' },
  { id: 'india', label: 'India', flag: '🇮🇳' },
  { id: 'usa', label: 'United States', flag: '🇺🇸' },
  { id: 'local', label: 'Local Community', flag: '📍' },
  { id: 'global', label: 'Global / Anywhere', flag: '🌐' },
];

function generateId(): string {
  return crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// Step indicator
function StepIndicator({ currentStep, totalSteps, isDark }: { currentStep: number; totalSteps: number; isDark: boolean }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-8">
      {Array.from({ length: totalSteps }).map((_, i) => (
        <div
          key={i}
          className={`
            h-2 rounded-full transition-all duration-300
            ${i === currentStep ? 'w-8 bg-emerald-500' : i < currentStep ? 'w-2 bg-emerald-500' : `w-2 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}
          `}
        />
      ))}
    </div>
  );
}

// Selectable card component
function SelectCard({
  selected,
  onClick,
  isDark,
  children,
  color,
}: {
  selected: boolean;
  onClick: () => void;
  isDark: boolean;
  children: React.ReactNode;
  color?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        relative p-4 rounded-2xl border-2 text-left transition-all duration-200
        ${selected
          ? 'border-emerald-500 bg-emerald-500/10 scale-[1.02] shadow-lg'
          : isDark
          ? 'border-slate-700 bg-slate-800/50 hover:border-slate-600 hover:bg-slate-800'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-md'
        }
      `}
      style={selected && color ? { borderColor: color, backgroundColor: `${color}15` } : undefined}
    >
      {selected && (
        <div
          className="absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center text-white"
          style={{ backgroundColor: color || '#10b981' }}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )}
      {children}
    </button>
  );
}

// Pie chart component
function AllocationPieChart({
  allocations,
  isDark,
}: {
  allocations: { label: string; percent: number; color: string }[];
  isDark: boolean;
}) {
  const total = allocations.reduce((sum, a) => sum + a.percent, 0);
  let currentAngle = -90; // Start from top

  const segments = allocations.filter(a => a.percent > 0).map(allocation => {
    const angle = (allocation.percent / 100) * 360;
    const startAngle = currentAngle;
    currentAngle += angle;

    // Calculate arc path
    const startRad = (startAngle * Math.PI) / 180;
    const endRad = ((startAngle + angle) * Math.PI) / 180;
    const radius = 80;
    const cx = 100;
    const cy = 100;

    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;

    const path = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`;

    return { ...allocation, path };
  });

  return (
    <div className="flex flex-col items-center">
      <svg width="200" height="200" viewBox="0 0 200 200">
        {/* Background circle */}
        <circle
          cx="100"
          cy="100"
          r="80"
          fill={isDark ? '#1e293b' : '#f1f5f9'}
          stroke={isDark ? '#334155' : '#e2e8f0'}
          strokeWidth="2"
        />
        {/* Segments */}
        {segments.map((seg, i) => (
          <path key={i} d={seg.path} fill={seg.color} className="transition-all duration-300" />
        ))}
        {/* Center circle for donut effect */}
        <circle cx="100" cy="100" r="50" fill={isDark ? '#0f172a' : '#ffffff'} />
        {/* Center text */}
        <text
          x="100"
          y="95"
          textAnchor="middle"
          className={`text-2xl font-bold ${isDark ? 'fill-white' : 'fill-slate-900'}`}
        >
          {total}%
        </text>
        <text
          x="100"
          y="115"
          textAnchor="middle"
          className={`text-sm ${isDark ? 'fill-slate-400' : 'fill-slate-500'}`}
        >
          allocated
        </text>
      </svg>

      {/* Legend */}
      <div className="mt-4 grid grid-cols-2 gap-2 w-full max-w-xs">
        {allocations.filter(a => a.percent > 0).map((a, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: a.color }} />
            <span className={`truncate ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{a.label}</span>
            <span className={`ml-auto font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>{a.percent}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AllocationWizard({
  initialBuckets = [],
  targetAmount: initialTarget,
  onComplete,
  onCancel,
}: AllocationWizardProps) {
  const { isDark } = useLandingTheme();
  const prefersReducedMotion = useReducedMotion();

  const [step, setStep] = useState(0);
  const [selectedCauses, setSelectedCauses] = useState<string[]>(() => {
    // Initialize from existing buckets
    const causes = new Set<string>();
    initialBuckets.forEach(b => b.tags.forEach(t => {
      if (CAUSES.some(c => c.id === t)) causes.add(t);
    }));
    return Array.from(causes);
  });
  const [selectedRegions, setSelectedRegions] = useState<string[]>(() => {
    const regions = new Set<string>();
    initialBuckets.forEach(b => b.tags.forEach(t => {
      if (REGIONS.some(r => r.id === t)) regions.add(t);
    }));
    return Array.from(regions);
  });
  const [allocations, setAllocations] = useState<Record<string, number>>(() => {
    const allocs: Record<string, number> = {};
    initialBuckets.forEach(b => {
      allocs[b.id] = b.percentage;
    });
    return allocs;
  });
  const [targetAmount, setTargetAmount] = useState<string>(initialTarget?.toString() || '');
  const [isSaving, setIsSaving] = useState(false);

  // Generate buckets from selections
  const generatedBuckets = useMemo((): GivingBucket[] => {
    const buckets: GivingBucket[] = [];

    // If both causes and regions selected, create combinations
    if (selectedCauses.length > 0 && selectedRegions.length > 0) {
      // Create a bucket for each cause, with all regions as secondary tags
      selectedCauses.forEach((causeId, i) => {
        const cause = CAUSES.find(c => c.id === causeId);
        if (!cause) return;

        buckets.push({
          id: `bucket-${causeId}`,
          name: cause.label,
          tags: [causeId, ...selectedRegions],
          percentage: allocations[`bucket-${causeId}`] || 0,
          color: cause.color,
        });
      });
    } else if (selectedCauses.length > 0) {
      // Just causes
      selectedCauses.forEach((causeId, i) => {
        const cause = CAUSES.find(c => c.id === causeId);
        if (!cause) return;

        buckets.push({
          id: `bucket-${causeId}`,
          name: cause.label,
          tags: [causeId],
          percentage: allocations[`bucket-${causeId}`] || 0,
          color: cause.color,
        });
      });
    } else if (selectedRegions.length > 0) {
      // Just regions
      selectedRegions.forEach((regionId, i) => {
        const region = REGIONS.find(r => r.id === regionId);
        if (!region) return;

        const colors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];
        buckets.push({
          id: `bucket-${regionId}`,
          name: region.label,
          tags: [regionId],
          percentage: allocations[`bucket-${regionId}`] || 0,
          color: colors[i % colors.length],
        });
      });
    }

    return buckets;
  }, [selectedCauses, selectedRegions, allocations]);

  const totalPercent = generatedBuckets.reduce((sum, b) => sum + b.percentage, 0);
  const isValidTotal = totalPercent === 100;

  const toggleCause = (id: string) => {
    setSelectedCauses(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  const toggleRegion = (id: string) => {
    setSelectedRegions(prev =>
      prev.includes(id) ? prev.filter(r => r !== id) : [...prev, id]
    );
  };

  const updateAllocation = (bucketId: string, percent: number) => {
    setAllocations(prev => ({ ...prev, [bucketId]: Math.max(0, Math.min(100, percent)) }));
  };

  const distributeEvenly = () => {
    const count = generatedBuckets.length;
    if (count === 0) return;

    const base = Math.floor(100 / count);
    const remainder = 100 - base * count;

    const newAllocs: Record<string, number> = {};
    generatedBuckets.forEach((b, i) => {
      newAllocs[b.id] = base + (i < remainder ? 1 : 0);
    });
    setAllocations(newAllocs);
  };

  const handleComplete = async () => {
    setIsSaving(true);
    try {
      const finalBuckets = generatedBuckets.map(b => ({
        ...b,
        percentage: allocations[b.id] || 0,
      }));
      const numericTarget = targetAmount ? parseFloat(targetAmount) : null;
      await onComplete(finalBuckets, numericTarget);
    } finally {
      setIsSaving(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 0: return selectedCauses.length > 0 || selectedRegions.length > 0;
      case 1: return true; // Regions are optional
      case 2: return isValidTotal;
      default: return true;
    }
  };

  const steps = ['Causes', 'Regions', 'Allocate', 'Review'];

  return (
    <div className={`rounded-2xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
      {/* Header */}
      <div className="text-center mb-2">
        <h2 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
          {step === 0 && 'What causes matter to you?'}
          {step === 1 && 'Where do you want to give?'}
          {step === 2 && 'How much to each?'}
          {step === 3 && 'Review your allocation'}
        </h2>
        <p className={`mt-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          {step === 0 && 'Select the causes you care about most'}
          {step === 1 && 'Choose regions or skip for global giving'}
          {step === 2 && 'Distribute your zakat across your buckets'}
          {step === 3 && 'Confirm your giving plan'}
        </p>
      </div>

      <StepIndicator currentStep={step} totalSteps={4} isDark={isDark} />

      <AnimatePresence mode="wait">
      {/* Step 0: Causes */}
      {step === 0 && (
        <m.div
          key="step-0"
          initial={prefersReducedMotion ? false : { opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: -40 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.25 }}
          className="grid grid-cols-2 sm:grid-cols-3 gap-3"
        >
          {CAUSES.map(cause => (
            <SelectCard
              key={cause.id}
              selected={selectedCauses.includes(cause.id)}
              onClick={() => toggleCause(cause.id)}
              isDark={isDark}
              color={cause.color}
            >
              <div className="text-3xl mb-2">{cause.icon}</div>
              <div className={`font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {cause.label}
              </div>
              <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                {cause.description}
              </div>
            </SelectCard>
          ))}
        </m.div>
      )}

      {/* Step 1: Regions */}
      {step === 1 && (
        <m.div
          key="step-1"
          initial={prefersReducedMotion ? false : { opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: -40 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.25 }}
        >
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {REGIONS.map(region => (
              <SelectCard
                key={region.id}
                selected={selectedRegions.includes(region.id)}
                onClick={() => toggleRegion(region.id)}
                isDark={isDark}
              >
                <div className="text-2xl mb-1">{region.flag}</div>
                <div className={`font-medium text-sm ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {region.label}
                </div>
              </SelectCard>
            ))}
          </div>
          <p className={`text-center mt-4 text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
            Skip this step to give globally across all regions
          </p>
        </m.div>
      )}

      {/* Step 2: Allocations */}
      {step === 2 && (
        <m.div
          key="step-2"
          initial={prefersReducedMotion ? false : { opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: -40 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.25 }}
          className="flex flex-col lg:flex-row gap-8 items-start"
        >
          {/* Pie chart */}
          <div className="flex-shrink-0 mx-auto lg:mx-0">
            <AllocationPieChart
              allocations={generatedBuckets.map(b => ({
                label: b.name,
                percent: allocations[b.id] || 0,
                color: b.color || '#10b981',
              }))}
              isDark={isDark}
            />
          </div>

          {/* Allocation inputs */}
          <div className="flex-grow w-full space-y-3">
            <div className="flex items-center justify-between mb-4">
              <span className={`text-sm font-medium tabular-nums ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {totalPercent}% of 100% allocated
              </span>
              <button
                type="button"
                onClick={distributeEvenly}
                className={`text-sm px-3 py-1 rounded-lg transition-colors ${
                  isDark
                    ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                Distribute evenly
              </button>
            </div>

            {generatedBuckets.map(bucket => (
              <div
                key={bucket.id}
                className={`flex items-center gap-4 p-3 rounded-xl ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}
              >
                <div
                  className="w-4 h-4 rounded-full flex-shrink-0"
                  style={{ backgroundColor: bucket.color }}
                />
                <span className={`flex-grow font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {bucket.name}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => updateAllocation(bucket.id, (allocations[bucket.id] || 0) - 5)}
                    className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                      isDark ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                    }`}
                  >
                    −
                  </button>
                  <input
                    type="number"
                    value={allocations[bucket.id] || 0}
                    onChange={(e) => updateAllocation(bucket.id, parseInt(e.target.value) || 0)}
                    className={`w-16 text-center text-lg font-bold rounded-lg border py-1 ${
                      isDark
                        ? 'bg-slate-900 border-slate-700 text-white'
                        : 'bg-white border-slate-200 text-slate-900'
                    } focus:outline-none focus:ring-2 focus:ring-emerald-500`}
                  />
                  <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>%</span>
                  <button
                    type="button"
                    onClick={() => updateAllocation(bucket.id, (allocations[bucket.id] || 0) + 5)}
                    className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                      isDark ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                    }`}
                  >
                    +
                  </button>
                </div>
              </div>
            ))}

            {!isValidTotal && totalPercent !== 0 && (
              <p className="text-red-500 text-sm text-center mt-2">
                Must equal 100% ({totalPercent > 100 ? `${totalPercent - 100}% over` : `${100 - totalPercent}% remaining`})
              </p>
            )}
          </div>
        </m.div>
      )}

      {/* Step 3: Review */}
      {step === 3 && (
        <m.div
          key="step-3"
          initial={prefersReducedMotion ? false : { opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: -40 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.25 }}
          className="space-y-6"
        >
          {/* Target amount */}
          <div className={`p-4 rounded-xl ${isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
            <label className={`block text-sm font-medium mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              What's your annual zakat target?
            </label>
            <div className="flex items-center gap-2">
              <span className={`text-2xl ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>$</span>
              <input
                type="number"
                value={targetAmount}
                onChange={(e) => setTargetAmount(e.target.value)}
                placeholder="10,000"
                className={`text-3xl font-bold bg-transparent border-0 w-full focus:outline-none ${
                  isDark ? 'text-white placeholder-slate-600' : 'text-slate-900 placeholder-slate-300'
                }`}
              />
            </div>
          </div>

          {/* Summary */}
          <div className={`rounded-xl border ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
            <div className={`px-4 py-3 border-b ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
              <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>Your Giving Plan</h3>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-slate-700">
              {generatedBuckets.filter(b => (allocations[b.id] || 0) > 0).map(bucket => {
                const percent = allocations[bucket.id] || 0;
                const amount = targetAmount ? (parseFloat(targetAmount) * percent / 100) : 0;

                return (
                  <div key={bucket.id} className="flex items-center gap-3 px-4 py-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: bucket.color }} />
                    <span className={`flex-grow ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                      {bucket.name}
                    </span>
                    <span className={`font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                      {percent}%
                    </span>
                    {amount > 0 && (
                      <span className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        ${amount.toLocaleString()}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </m.div>
      )}
      </AnimatePresence>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-8 pt-6 border-t border-slate-200 dark:border-slate-800">
        <button
          type="button"
          onClick={() => step === 0 ? onCancel?.() : setStep(step - 1)}
          className={`px-5 py-2.5 rounded-xl font-medium transition-colors ${
            isDark
              ? 'text-slate-400 hover:text-white hover:bg-slate-800'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          {step === 0 ? 'Cancel' : '← Back'}
        </button>

        <button
          type="button"
          onClick={() => step === 3 ? handleComplete() : setStep(step + 1)}
          disabled={!canProceed() || isSaving}
          className={`
            px-6 py-2.5 rounded-xl font-semibold transition-all
            ${canProceed() && !isSaving
              ? 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-500/25'
              : 'bg-slate-300 text-slate-500 cursor-not-allowed'
            }
          `}
        >
          {isSaving ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Saving...
            </span>
          ) : step === 3 ? (
            'Save Plan'
          ) : (
            'Continue →'
          )}
        </button>
      </div>
    </div>
  );
}

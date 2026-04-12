import { useState, useMemo, useCallback } from 'react';
import { m } from 'motion/react';
import { Sparkles, Check } from 'lucide-react';
import { writeBatch, doc, Timestamp } from 'firebase/firestore';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { generateStarterPlan, DEFAULT_CATEGORIES, type StarterGroup } from '../../utils/starterPlanGenerator';
import { db } from '../../auth/firebase';
import { useAuth } from '../../auth/useAuth';
import type { CharitySummary } from '../../hooks/useCharities';
import type { GivingBucket } from '../../../types';

interface StarterPlanProps {
  target: number;
  charities: CharitySummary[];
  bookmarkedEins?: Set<string>;
  onAccepted: () => void;
}

function formatUsd(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

export function StarterPlan({ target, charities, bookmarkedEins, onAccepted }: StarterPlanProps) {
  const { isDark } = useLandingTheme();
  const { uid } = useAuth();
  const [saving, setSaving] = useState(false);
  const [accepted, setAccepted] = useState(false);

  const groups = useMemo(() =>
    generateStarterPlan(target, charities, DEFAULT_CATEGORIES, { excludeEins: bookmarkedEins }),
    [target, charities, bookmarkedEins]
  );

  const hasAllocations = groups.some(g => g.allocations.length > 0);

  const handleAccept = useCallback(async () => {
    if (!db || !uid || saving) return;
    setSaving(true);
    try {
      const now = Timestamp.now();
      const batch = writeBatch(db);

      // Create giving buckets
      const buckets: GivingBucket[] = groups
        .filter(g => g.allocations.length > 0)
        .map(g => ({
          id: crypto.randomUUID(),
          name: g.category.name,
          tags: [g.category.id],
          percentage: g.category.percentage,
          color: g.category.color,
        }));

      // Create charity bucket assignments
      const assignments: { charityEin: string; bucketId: string }[] = [];
      for (const group of groups) {
        const bucket = buckets.find(b => b.name === group.category.name);
        if (!bucket) continue;
        for (const alloc of group.allocations) {
          assignments.push({ charityEin: alloc.ein, bucketId: bucket.id });
        }
      }

      // Write charity targets to subcollection
      for (const group of groups) {
        for (const alloc of group.allocations) {
          const targetRef = doc(db, 'users', uid, 'charity_targets', alloc.ein);
          batch.set(targetRef, {
            charityEin: alloc.ein,
            targetAmount: alloc.amount,
            createdAt: now,
            updatedAt: now,
          });
        }
      }

      // Update user profile
      const userRef = doc(db, 'users', uid);
      batch.update(userRef, {
        givingBuckets: buckets,
        charityBucketAssignments: assignments,
        targetZakatAmount: target,
        updatedAt: now,
      });

      await batch.commit();
      setAccepted(true);
      onAccepted();
    } catch (err) {
      console.error('Failed to save starter plan:', err);
    } finally {
      setSaving(false);
    }
  }, [db, uid, saving, groups, target, onAccepted]);

  if (!hasAllocations) return null;

  if (accepted) {
    return (
      <m.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className={`rounded-xl border p-6 text-center ${isDark ? 'bg-emerald-900/20 border-emerald-800' : 'bg-emerald-50 border-emerald-200'}`}
      >
        <Check className={`w-8 h-8 mx-auto mb-2 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
        <p className={`font-medium ${isDark ? 'text-emerald-300' : 'text-emerald-700'}`}>
          Plan saved! Your giving plan has been set up.
        </p>
      </m.div>
    );
  }

  return (
    <m.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`rounded-xl border overflow-hidden ${isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'}`}
    >
      {/* Header */}
      <div className={`px-5 py-4 border-b ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
          <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>Starter Plan</h3>
        </div>
        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          A suggested allocation of {formatUsd(target)} across top-scoring charities
        </p>
      </div>

      {/* Groups */}
      <div className="divide-y ${isDark ? 'divide-slate-700' : 'divide-slate-100'}">
        {groups.filter(g => g.allocations.length > 0).map((group, gi) => (
          <GroupRow key={group.category.id} group={group} isDark={isDark} delay={gi * 0.05} />
        ))}
      </div>

      {/* Footer */}
      <div className={`px-5 py-4 border-t ${isDark ? 'border-slate-700' : 'border-slate-100'}`}>
        <button
          onClick={handleAccept}
          disabled={saving}
          className="w-full px-4 py-2.5 rounded-lg font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Start with this plan'}
        </button>
        <p className={`text-xs text-center mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
          You can customize amounts and charities anytime
        </p>
      </div>
    </m.div>
  );
}

function GroupRow({ group, isDark, delay }: { group: StarterGroup; isDark: boolean; delay: number }) {
  return (
    <m.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, delay }}
      className="px-5 py-3"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: group.category.color }} />
          <span className={`text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
            {group.category.name}
          </span>
        </div>
        <span className={`text-sm font-medium tabular-nums ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
          {formatUsd(group.subtotal)}
        </span>
      </div>
      <div className="space-y-1 ml-[18px]">
        {group.allocations.map(alloc => (
          <div key={alloc.ein} className="flex items-center justify-between">
            <span className={`text-sm truncate mr-3 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {alloc.name}
            </span>
            <span className={`text-sm tabular-nums flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {formatUsd(alloc.amount)}
            </span>
          </div>
        ))}
      </div>
    </m.div>
  );
}

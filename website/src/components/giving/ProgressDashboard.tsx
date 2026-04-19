/**
 * ProgressDashboard - read-only top-of-record summary for the signed-in
 * profile page. Shows four stats (Target, Allocated, Given, Remaining),
 * a progress bar, and a celebratory banner when the donor has met their
 * target.
 *
 * All state is derived from existing hooks (useProfileState +
 * useGivingDashboard + useCharities) - this component never writes.
 *
 * See: `~/.claude/plans/where-are-we-right-cozy-torvalds.md` (M3).
 */

import { useMemo } from 'react';
import { m } from 'motion/react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useProfileState } from '../../contexts/UserFeaturesContext';
import { useCharities } from '../../hooks/useCharities';
import { formatCurrency } from '../../utils/formatters';
import type { CharityBucketAssignment } from '../../../types';

interface ProgressDashboardProps {
  /** Optional: callback to scroll the user to the target input when they
   *  haven't set one. Falls back to a scrollIntoView on `[data-tour="giving-target"]`. */
  onRequestSetTarget?: () => void;
}

/** Pick the first non-confirmed assignment (ordered by `intendedAt` ascending). */
function pickNextUp(
  assignments: CharityBucketAssignment[],
): CharityBucketAssignment | undefined {
  const candidates = assignments.filter(a => a.status !== 'confirmed');
  if (candidates.length === 0) return undefined;
  return [...candidates].sort((a, b) => {
    const ta = a.intendedAt ? Date.parse(a.intendedAt) : 0;
    const tb = b.intendedAt ? Date.parse(b.intendedAt) : 0;
    return ta - tb;
  })[0];
}

/** Convert an EIN like "13-5660870" to URL slug form (no change, kept for clarity). */
function einToSlug(ein: string): string {
  return ein;
}

/** Scroll to (or trigger) the zakat target UI as a fallback for the empty state CTA. */
function focusTargetInput(): void {
  if (typeof document === 'undefined') return;
  const el = document.querySelector<HTMLElement>('[data-tour="giving-target"]');
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const input = el.querySelector<HTMLInputElement>('input');
    if (input) {
      // Defer focus so scroll finishes first on mobile.
      setTimeout(() => input.focus(), 350);
    }
  }
}

export function ProgressDashboard({ onRequestSetTarget }: ProgressDashboardProps = {}) {
  const { isDark } = useLandingTheme();
  const { profile } = useProfileState();
  // Pull `summaries` only to resolve the "Next up" charity name from its EIN.
  const { summaries } = useCharities();

  const target = profile?.targetZakatAmount ?? 0;
  const assignments = profile?.charityBucketAssignments ?? [];

  const stats = useMemo(() => {
    let allocated = 0;
    let given = 0;
    let confirmedCount = 0;
    for (const a of assignments) {
      allocated += Number(a.intended) || 0;
      given += Number(a.given) || 0;
      if (a.status === 'confirmed') confirmedCount += 1;
    }
    return {
      allocated,
      given,
      remaining: Math.max(0, target - given),
      confirmedCount,
      totalCount: assignments.length,
    };
  }, [assignments, target]);

  const nextUp = useMemo(() => pickNextUp(assignments), [assignments]);
  const nextUpName = useMemo(() => {
    if (!nextUp) return null;
    const s = summaries?.find(c => c.ein === nextUp.charityEin);
    return s?.name ?? nextUp.charityEin;
  }, [nextUp, summaries]);

  // --- Empty state: no target set --------------------------------------
  if (!target || target <= 0) {
    return (
      <div
        data-testid="progress-dashboard-empty"
        className={`rounded-xl border p-5 text-center ${
          isDark ? 'bg-slate-900 border-slate-800 text-slate-400' : 'bg-white border-slate-200 text-slate-500'
        }`}
      >
        <p className="text-sm">Set your zakat target to see progress.</p>
        <button
          type="button"
          onClick={onRequestSetTarget ?? focusTargetInput}
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-emerald-600 hover:text-emerald-500 transition-colors"
        >
          Set target
          <span aria-hidden="true">-&gt;</span>
        </button>
      </div>
    );
  }

  const progressRatio = target > 0 ? Math.min(100, Math.max(0, (stats.given / target) * 100)) : 0;
  const isComplete = target > 0 && stats.given >= target;
  const overAllocated = stats.allocated > target;
  const underAllocated = stats.allocated < target;

  return (
    <m.section
      data-testid="progress-dashboard"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`rounded-xl border overflow-hidden ${
        isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'
      }`}
      aria-label="Zakat giving progress"
    >
      {/* Stat cards: 2 columns on mobile, 4 on md+ */}
      <div
        className={`grid grid-cols-2 md:grid-cols-4 gap-px ${
          isDark ? 'bg-slate-800' : 'bg-slate-100'
        }`}
      >
        <StatCard
          label="Target"
          value={formatCurrency(target)}
          isDark={isDark}
          testId="dash-target"
        />
        <StatCard
          label="Allocated"
          value={formatCurrency(stats.allocated)}
          sub={
            overAllocated
              ? `over by ${formatCurrency(stats.allocated - target)}`
              : underAllocated
              ? `${formatCurrency(target - stats.allocated)} unallocated`
              : undefined
          }
          subTone={overAllocated ? 'warning' : 'muted'}
          isDark={isDark}
          testId="dash-allocated"
        />
        <StatCard
          label="Given"
          value={formatCurrency(stats.given)}
          isDark={isDark}
          testId="dash-given"
        />
        <StatCard
          label="Remaining"
          value={isComplete ? '$0' : formatCurrency(stats.remaining)}
          sub={isComplete ? 'complete' : undefined}
          subTone={isComplete ? 'success' : 'muted'}
          isDark={isDark}
          testId="dash-remaining"
        />
      </div>

      {/* Progress bar + sub-summary */}
      <div
        className={`px-5 py-4 border-t ${
          isDark ? 'border-slate-800' : 'border-slate-200'
        }`}
      >
        <div className="flex items-center justify-between mb-2">
          <span
            className={`text-xs font-medium uppercase tracking-wide ${
              isDark ? 'text-slate-500' : 'text-slate-500'
            }`}
          >
            Progress
          </span>
          <span
            className={`text-xs tabular-nums ${
              isDark ? 'text-slate-400' : 'text-slate-500'
            }`}
            data-testid="dash-progress-pct"
          >
            {Math.round(progressRatio)}%
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={Math.round(progressRatio)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Zakat given vs. target"
          data-testid="dash-progress-bar"
          className={`w-full h-2 rounded-full overflow-hidden ${
            isDark ? 'bg-slate-800' : 'bg-slate-100'
          }`}
        >
          <div
            className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-[width] duration-500"
            style={{ width: `${progressRatio}%` }}
          />
        </div>

        {stats.totalCount > 0 && (
          <div
            className={`mt-3 text-xs ${
              isDark ? 'text-slate-400' : 'text-slate-500'
            }`}
            data-testid="dash-sub-summary"
          >
            <span className="tabular-nums">
              {stats.confirmedCount} of {stats.totalCount}
            </span>{' '}
            {stats.totalCount === 1 ? 'charity' : 'charities'} confirmed
            {nextUp && nextUpName && !isComplete && (
              <>
                {' '}
                <span aria-hidden="true">·</span>{' '}
                <span>
                  Next up:{' '}
                  <Link
                    to={`/charity/${einToSlug(nextUp.charityEin)}`}
                    className={`font-medium underline-offset-2 hover:underline ${
                      isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                    }`}
                  >
                    {nextUpName}
                  </Link>
                </span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Reinforcement banner -- shown only when target is met */}
      {isComplete && (
        <m.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          data-testid="dash-complete-banner"
          className={`px-5 py-3 border-t font-merriweather text-sm text-center ${
            isDark
              ? 'border-emerald-900/60 bg-gradient-to-r from-emerald-900/40 via-emerald-800/30 to-emerald-900/40 text-emerald-200'
              : 'border-emerald-200 bg-gradient-to-r from-emerald-50 via-emerald-100/60 to-emerald-50 text-emerald-800'
          }`}
        >
          You&apos;ve completed your zakat for this year <span aria-hidden="true">✓</span>
        </m.div>
      )}
    </m.section>
  );
}

// --- StatCard --------------------------------------------------------------

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  subTone?: 'muted' | 'warning' | 'success';
  isDark: boolean;
  testId?: string;
}

function StatCard({ label, value, sub, subTone = 'muted', isDark, testId }: StatCardProps) {
  const subColor =
    subTone === 'warning'
      ? isDark
        ? 'text-amber-400'
        : 'text-amber-600'
      : subTone === 'success'
      ? isDark
        ? 'text-emerald-400'
        : 'text-emerald-600'
      : isDark
      ? 'text-slate-500'
      : 'text-slate-500';

  return (
    <div
      data-testid={testId}
      className={`px-5 py-4 ${isDark ? 'bg-slate-900' : 'bg-white'}`}
    >
      <div
        className={`text-xs font-medium uppercase tracking-wide ${
          isDark ? 'text-slate-500' : 'text-slate-500'
        }`}
      >
        {label}
      </div>
      <div
        className={`mt-1 text-2xl font-semibold tabular-nums ${
          isDark ? 'text-white' : 'text-slate-900'
        }`}
      >
        {value}
      </div>
      {sub && <div className={`mt-0.5 text-xs tabular-nums ${subColor}`}>{sub}</div>}
    </div>
  );
}

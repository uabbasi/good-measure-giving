/**
 * AddToFamilyPlanButton — the bridge from a charity (anywhere it appears) to a
 * shared/family giving plan. Money-free: it only adds the charity (weight 1) to
 * the plan's shared proportions; dollars stay personal.
 *
 * Render rules:
 *  - signed out, or no shared plans → renders nothing (no plan to add to).
 *  - exactly 1 plan  → a single button "Add to {plan name}".
 *  - 2+ plans        → a button that opens a small menu to pick the plan.
 * After a successful add (or if the charity is already there) the control shows
 * "Added ✓" briefly.
 */

import { useCallback, useRef, useState } from 'react';
import { Users, Check, ChevronDown } from 'lucide-react';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useSharedPlans } from '../../hooks/useSharedPlans';

interface Props {
  charityEin: string;
  charityName?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export function AddToFamilyPlanButton({ charityEin, charityName, size = 'md', className = '' }: Props) {
  const { isDark } = useLandingTheme();
  const { plans, addCharityToPlan } = useSharedPlans();

  const [menuOpen, setMenuOpen] = useState(false);
  const [busyPlanId, setBusyPlanId] = useState<string | null>(null);
  const [addedName, setAddedName] = useState<string | null>(null);
  const clearTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showAdded = useCallback((name: string) => {
    setAddedName(name);
    if (clearTimer.current) clearTimeout(clearTimer.current);
    clearTimer.current = setTimeout(() => setAddedName(null), 2500);
  }, []);

  const add = useCallback(
    async (planId: string, planName: string) => {
      setMenuOpen(false);
      setBusyPlanId(planId);
      try {
        await addCharityToPlan(planId, charityEin);
        showAdded(planName);
      } catch {
        /* surfaced by the mutation; leave the control idle so the user can retry */
      } finally {
        setBusyPlanId(null);
      }
    },
    [addCharityToPlan, charityEin, showAdded],
  );

  // Nothing to bridge to.
  if (plans.length === 0) return null;

  const padding = size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-2.5 py-1.5 text-xs';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';
  const baseBtn =
    'inline-flex items-center gap-1 rounded-full font-semibold border transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500 whitespace-nowrap';
  const activeCls = isDark
    ? 'bg-violet-500/10 border-violet-700 text-violet-300 hover:bg-violet-500/20'
    : 'bg-violet-50 border-violet-200 text-violet-700 hover:bg-violet-100';
  const doneCls = isDark
    ? 'bg-slate-800 border-slate-700 text-slate-400 cursor-default'
    : 'bg-slate-100 border-slate-200 text-slate-500 cursor-default';

  const busy = busyPlanId !== null;

  // "Added ✓" confirmation state (shared across single/menu modes).
  if (addedName) {
    return (
      <div className={`relative inline-flex ${className}`}>
        <span className={`${baseBtn} ${padding} ${doneCls}`} role="status">
          <Check className={iconSize} aria-hidden="true" />
          Added to {addedName} <span aria-hidden="true">✓</span>
        </span>
      </div>
    );
  }

  // Exactly one plan → direct add.
  if (plans.length === 1) {
    const plan = plans[0];
    return (
      <div className={`relative inline-flex ${className}`}>
        <button
          type="button"
          onClick={e => {
            e.preventDefault();
            e.stopPropagation();
            void add(plan.id, plan.name);
          }}
          disabled={busy}
          aria-label={`Add ${charityName || 'charity'} to ${plan.name}`}
          className={`${baseBtn} ${padding} ${activeCls}`}
        >
          <Users className={iconSize} aria-hidden="true" />
          {busy ? 'Adding…' : `Add to ${plan.name}`}
        </button>
      </div>
    );
  }

  // 2+ plans → menu to pick which.
  return (
    <div className={`relative inline-flex ${className}`}>
      <button
        type="button"
        onClick={e => {
          e.preventDefault();
          e.stopPropagation();
          setMenuOpen(o => !o);
        }}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        aria-label={`Add ${charityName || 'charity'} to a family plan`}
        className={`${baseBtn} ${padding} ${activeCls}`}
      >
        <Users className={iconSize} aria-hidden="true" />
        {busy ? 'Adding…' : 'Add to family plan'}
        <ChevronDown className={iconSize} aria-hidden="true" />
      </button>

      {menuOpen && (
        <div
          role="menu"
          className={`absolute top-full left-0 mt-2 min-w-[12rem] rounded-lg border shadow-lg py-1 z-50 ${
            isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200'
          }`}
        >
          {plans.map(plan => (
            <button
              key={plan.id}
              type="button"
              role="menuitem"
              onClick={e => {
                e.preventDefault();
                e.stopPropagation();
                void add(plan.id, plan.name);
              }}
              className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs ${
                isDark ? 'text-slate-200 hover:bg-slate-700' : 'text-slate-700 hover:bg-slate-50'
              }`}
            >
              <Users className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              <span className="truncate">{plan.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

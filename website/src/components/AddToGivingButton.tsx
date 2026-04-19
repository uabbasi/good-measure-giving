/**
 * AddToGivingButton — small action button that writes an 'intended' assignment
 * for a charity. Lives next to BookmarkButton on CharityCard.
 *
 * States:
 *  - signed out              → "Sign in to add" (opens sign-in hint, like BookmarkButton)
 *  - signed in, not in plan  → "Add to giving"
 *  - signed in, no target    → "Add to giving" (opens ZakatEstimator first, then adds)
 *  - already in plan         → "In your giving ✓" (disabled)
 *
 * Soft-cap guardrail: after an add that brings the intended count to ≥6, we
 * show a one-time dismissible inline banner nudging the user to narrow down.
 * Dismissal is persisted in localStorage.
 */

import { useCallback, useRef, useState } from 'react';
import { Plus, Check, X } from 'lucide-react';
import { useAuth } from '../auth/useAuth';
import { useProfileState } from '../contexts/UserFeaturesContext';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { useAddToGiving } from '../hooks/useAddToGiving';
import { ZakatEstimator } from './giving/ZakatEstimator';

const SOFTCAP_KEY = 'gmg_softcap_nudge_dismissed';
const SOFTCAP_THRESHOLD = 6;

interface Props {
  charityEin: string;
  charityName?: string;
  size?: 'sm' | 'md';
  /** Optional className for the outer wrapper. */
  className?: string;
}

function readSoftcapDismissed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(SOFTCAP_KEY) === '1';
  } catch {
    return false;
  }
}

function writeSoftcapDismissed() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(SOFTCAP_KEY, '1');
  } catch {
    /* ignore */
  }
}

export function AddToGivingButton({ charityEin, charityName, size = 'md', className = '' }: Props) {
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();
  const { profile, updateProfile } = useProfileState();
  const { addToGiving, isInPlan, saving } = useAddToGiving();

  const inPlan = isInPlan(charityEin);
  const needsTarget = isSignedIn && !profile?.targetZakatAmount;

  const [showSignInHint, setShowSignInHint] = useState(false);
  const [showEstimator, setShowEstimator] = useState(false);
  const [showSoftCap, setShowSoftCap] = useState(false);
  // When we open the estimator from the button, proceed with the add after saving.
  const pendingAddRef = useRef(false);

  const doAdd = useCallback(async () => {
    if (!profile) return;
    const intendedCountBefore = (profile.charityBucketAssignments || []).filter(
      a => a.status === 'intended',
    ).length;
    await addToGiving(charityEin, charityName);
    // Dispatch the same toast event bookmark uses, so BookmarkToast confirms.
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('gmg:bookmark-added', {
          detail: { charityEin, charityName: charityName || 'Charity' },
        }),
      );
    }
    // Softcap nudge: trigger when the add brings us to >= 6 intended entries
    // (i.e., the add pushes from 5+ to 6+), one time per localStorage.
    if (intendedCountBefore + 1 >= SOFTCAP_THRESHOLD && !readSoftcapDismissed()) {
      setShowSoftCap(true);
    }
  }, [profile, addToGiving, charityEin, charityName]);

  const handleClick = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (!isSignedIn) {
        setShowSignInHint(true);
        setTimeout(() => setShowSignInHint(false), 3000);
        return;
      }

      if (inPlan || saving) return;

      if (needsTarget) {
        pendingAddRef.current = true;
        setShowEstimator(true);
        return;
      }

      await doAdd();
    },
    [isSignedIn, inPlan, saving, needsTarget, doAdd],
  );

  const onEstimatorUse = useCallback(
    async (amount: number) => {
      // ZakatEstimator will close itself after this callback
      await updateProfile({ targetZakatAmount: amount });
      if (pendingAddRef.current) {
        pendingAddRef.current = false;
        await doAdd();
      }
    },
    [updateProfile, doAdd],
  );

  const padding = size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-2.5 py-1.5 text-xs';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  const label = !isSignedIn
    ? 'Sign in to add'
    : inPlan
    ? 'In your giving'
    : saving
    ? 'Adding...'
    : 'Add to giving';

  const baseBtn =
    'inline-flex items-center gap-1 rounded-full font-semibold border transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500';
  const activeCls = isDark
    ? 'bg-emerald-500/10 border-emerald-700 text-emerald-300 hover:bg-emerald-500/20'
    : 'bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100';
  const doneCls = isDark
    ? 'bg-slate-800 border-slate-700 text-slate-400 cursor-default'
    : 'bg-slate-100 border-slate-200 text-slate-500 cursor-default';

  return (
    <div className={`relative inline-flex flex-col items-end gap-1 ${className}`}>
      <button
        type="button"
        onClick={handleClick}
        disabled={saving || inPlan}
        aria-label={label}
        aria-pressed={inPlan}
        className={`${baseBtn} ${padding} ${inPlan ? doneCls : activeCls}`}
      >
        {inPlan ? (
          <Check className={iconSize} aria-hidden="true" />
        ) : (
          <Plus className={iconSize} aria-hidden="true" />
        )}
        <span className="whitespace-nowrap">
          {inPlan ? (
            <>
              In your giving <span aria-hidden="true">✓</span>
            </>
          ) : (
            label
          )}
        </span>
      </button>

      {showSignInHint && (
        <div
          className={`absolute top-full right-0 mt-2 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap z-50 ${
            isDark ? 'bg-slate-700 text-white' : 'bg-slate-800 text-white'
          }`}
        >
          Sign in to add charities
        </div>
      )}

      {showSoftCap && (
        <div
          role="status"
          className={`absolute top-full right-0 mt-2 w-72 rounded-lg border shadow-lg p-3 z-50 ${
            isDark ? 'bg-slate-800 border-slate-700 text-slate-200' : 'bg-white border-slate-200 text-slate-700'
          }`}
        >
          <div className="flex items-start gap-2">
            <p className="text-xs flex-1">
              Most people choose 3-5 charities - want help narrowing this down?
            </p>
            <button
              type="button"
              onClick={() => {
                writeSoftcapDismissed();
                setShowSoftCap(false);
              }}
              aria-label="Dismiss"
              className={`p-0.5 rounded ${isDark ? 'hover:bg-slate-700' : 'hover:bg-slate-100'}`}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      <ZakatEstimator
        isOpen={showEstimator}
        onClose={() => {
          setShowEstimator(false);
          pendingAddRef.current = false;
        }}
        onUseAmount={amount => { void onEstimatorUse(amount); }}
      />
    </div>
  );
}

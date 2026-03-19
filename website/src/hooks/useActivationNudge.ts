/**
 * useActivationNudge — Rules engine for post-signup contextual nudges.
 *
 * Checks user profile state, bookmark count, and view count to determine
 * which nudge (if any) to show. Each nudge shows once, is dismissible,
 * and doesn't appear if the feature is already set up.
 */

import { useMemo, useCallback } from 'react';
import { useAuth } from '../auth/useAuth';
import { useProfile } from './useProfile';
import { useBookmarks } from './useBookmarks';

const DISMISSED_KEY = 'gmg_dismissed_nudges';
const SIGNED_IN_VIEWS_KEY = 'gmg_signed_in_views';

export interface NudgeConfig {
  id: string;
  icon: string;
  title: string;
  description: string;
  actionLabel: string;
  actionPath: string;
}

const NUDGE_DEFINITIONS: {
  id: string;
  icon: string;
  title: string;
  description: string;
  actionLabel: string;
  actionPath: string;
  featureCheck: (profile: { targetZakatAmount: number | null; givingBuckets: unknown[] }) => boolean;
  triggerCheck: (ctx: { bookmarkCount: number; signedInViews: number; donationCount: number }) => boolean;
}[] = [
  {
    id: 'buckets_nudge',
    icon: '🗂️',
    title: 'Organize your saved charities?',
    description: 'Create giving buckets to group charities by cause area',
    actionLabel: 'Set up buckets →',
    actionPath: '/profile',
    featureCheck: (p) => (p.givingBuckets?.length ?? 0) > 0,
    triggerCheck: (ctx) => ctx.bookmarkCount >= 3,
  },
  {
    id: 'zakat_target_nudge',
    icon: '🎯',
    title: 'Doing your research — nice',
    description: 'Set a zakat target to track your giving plan as you explore',
    actionLabel: 'Set target →',
    actionPath: '/profile',
    featureCheck: (p) => p.targetZakatAmount != null && p.targetZakatAmount > 0,
    triggerCheck: (ctx) => ctx.signedInViews >= 5,
  },
  {
    id: 'zakat_donation_nudge',
    icon: '📊',
    title: 'First donation recorded!',
    description: 'Set a zakat target to see how this fits your annual giving plan',
    actionLabel: 'Set target →',
    actionPath: '/profile',
    featureCheck: (p) => p.targetZakatAmount != null && p.targetZakatAmount > 0,
    triggerCheck: (ctx) => ctx.donationCount >= 1,
  },
];

function getDismissedNudges(): string[] {
  try {
    const stored = localStorage.getItem(DISMISSED_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveDismissedNudge(nudgeId: string): void {
  try {
    const dismissed = getDismissedNudges();
    if (!dismissed.includes(nudgeId)) {
      dismissed.push(nudgeId);
      localStorage.setItem(DISMISSED_KEY, JSON.stringify(dismissed));
    }
  } catch {
    // fail silently
  }
}

export function getSignedInViews(): number {
  try {
    return parseInt(localStorage.getItem(SIGNED_IN_VIEWS_KEY) || '0', 10);
  } catch {
    return 0;
  }
}

export function incrementSignedInViews(): void {
  try {
    const current = getSignedInViews();
    localStorage.setItem(SIGNED_IN_VIEWS_KEY, String(current + 1));
  } catch {
    // fail silently
  }
}

interface UseActivationNudgeResult {
  activeNudge: NudgeConfig | null;
  dismiss: (nudgeId: string) => void;
}

export function useActivationNudge(donationCount: number = 0): UseActivationNudgeResult {
  const { isSignedIn } = useAuth();
  const { profile } = useProfile();
  const { bookmarks } = useBookmarks();

  const dismiss = useCallback((nudgeId: string) => {
    saveDismissedNudge(nudgeId);
  }, []);

  const activeNudge = useMemo<NudgeConfig | null>(() => {
    if (!isSignedIn || !profile) return null;

    const dismissed = getDismissedNudges();
    const signedInViews = getSignedInViews();
    const ctx = {
      bookmarkCount: bookmarks.length,
      signedInViews,
      donationCount,
    };

    for (const nudge of NUDGE_DEFINITIONS) {
      if (dismissed.includes(nudge.id)) continue;
      if (nudge.featureCheck({
        targetZakatAmount: profile.targetZakatAmount ?? null,
        givingBuckets: profile.givingBuckets ?? [],
      })) continue;
      if (nudge.triggerCheck(ctx)) {
        return {
          id: nudge.id,
          icon: nudge.icon,
          title: nudge.title,
          description: nudge.description,
          actionLabel: nudge.actionLabel,
          actionPath: nudge.actionPath,
        };
      }
    }

    return null;
  }, [isSignedIn, profile, bookmarks.length, donationCount]);

  return { activeNudge, dismiss };
}

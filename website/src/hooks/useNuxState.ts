/**
 * useNuxState: Shared hook for New User Experience dismissal state.
 * Shows NUX tips for all signed-in users who haven't dismissed them.
 * Dismissal tracked in localStorage (persists per browser).
 */

import { useState } from 'react';
import { useAuth } from '../auth/useAuth';

export type NuxKey = 'browse-tip' | 'details-tip' | 'giving-plan-tip';

export function useNuxState(key: NuxKey) {
  const { isSignedIn } = useAuth();
  const storageKey = `gmg-nux-${key}`;
  const [dismissed, setDismissed] = useState(() => {
    // Guard SSR: Node 22+ exposes a bare, unbacked `localStorage` global (no
    // `window`), so reading it during server render throws. Match the
    // codebase's window-guard convention (see BetaBanner, useCompare).
    if (typeof window === 'undefined') return false;
    return localStorage.getItem(storageKey) === '1';
  });

  const shouldShow = isSignedIn && !dismissed;

  const dismiss = () => {
    localStorage.setItem(storageKey, '1');
    setDismissed(true);
  };

  return { shouldShow, dismiss };
}

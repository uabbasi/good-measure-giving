/**
 * useRichAccess — Progressive reveal metering for anonymous visitors.
 *
 * Signed-in users always get rich access.
 * Anonymous users get 3 free full charity detail views (unique EINs),
 * tracked via localStorage. After 3, content gates activate.
 */

import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../auth/useAuth';

const STORAGE_KEY = 'gmg_viewed_charities';
const FREE_VIEW_LIMIT = 3;

function getViewedEins(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveViewedEins(eins: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(eins));
  } catch {
    // localStorage full or unavailable — fail silently
  }
}

export function clearViewedEins(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // fail silently
  }
}

interface RichAccess {
  canViewRich: boolean;
  viewsUsed: number;
  viewsRemaining: number;
  recordView: (ein: string) => void;
}

export function useRichAccess(): RichAccess {
  const { isSignedIn } = useAuth();
  const [viewedEins, setViewedEins] = useState<string[]>(getViewedEins);

  // Sync state if localStorage changes externally (e.g., another tab)
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setViewedEins(getViewedEins());
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const recordView = useCallback((ein: string) => {
    setViewedEins((prev) => {
      if (prev.includes(ein)) return prev;
      const updated = [...prev, ein];
      saveViewedEins(updated);
      return updated;
    });
  }, []);

  const viewsUsed = viewedEins.length;
  const viewsRemaining = Math.max(0, FREE_VIEW_LIMIT - viewsUsed);
  const canViewRich = isSignedIn || viewsUsed < FREE_VIEW_LIMIT;

  return { canViewRich, viewsUsed, viewsRemaining, recordView };
}

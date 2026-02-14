/**
 * Hook for managing per-charity dollar targets
 * Allows users to set giving goals for specific charities
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { collection, doc, getDocs, setDoc, deleteDoc, orderBy, query, Timestamp } from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import type { CharityTarget } from '../../types';

interface UseCharityTargetsResult {
  targets: Map<string, number>; // Map<ein, targetAmount>
  targetsList: CharityTarget[];
  isLoading: boolean;
  error: string | null;
  setTarget: (ein: string, amount: number) => Promise<void>;
  removeTarget: (ein: string) => Promise<void>;
  getTarget: (ein: string) => number | undefined;
  getTotalTargeted: () => number;
  refreshTargets: () => Promise<void>;
}

function docToTarget(data: Record<string, unknown>, docId: string, userId: string): CharityTarget {
  return {
    id: docId,
    userId,
    charityEin: data.charityEin as string,
    targetAmount: Number(data.targetAmount),
    createdAt: data.createdAt instanceof Timestamp
      ? data.createdAt.toDate().toISOString()
      : (data.createdAt as string) || new Date().toISOString(),
    updatedAt: data.updatedAt instanceof Timestamp
      ? data.updatedAt.toDate().toISOString()
      : (data.updatedAt as string) || new Date().toISOString(),
  };
}

export function useCharityTargets(): UseCharityTargetsResult {
  const { db, userId } = useFirebaseData();
  const [targetsList, setTargetsList] = useState<CharityTarget[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create a Map for O(1) lookups
  const targets = useMemo(() => {
    return new Map(targetsList.map(t => [t.charityEin, t.targetAmount]));
  }, [targetsList]);

  // Fetch all targets
  const fetchTargets = useCallback(async () => {
    if (!db || !userId) {
      setTargetsList([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const colRef = collection(db, 'users', userId, 'charity_targets');
      const q = query(colRef, orderBy('createdAt', 'desc'));
      const snapshot = await getDocs(q);
      setTargetsList(snapshot.docs.map(d => docToTarget(d.data(), d.id, userId)));
    } catch (err) {
      console.error('Error fetching charity targets:', err);
      setError(err instanceof Error ? err.message : 'Failed to load targets');
    } finally {
      setIsLoading(false);
    }
  }, [db, userId]);

  useEffect(() => {
    fetchTargets();
  }, [fetchTargets]);

  // Set or update a target (upsert via EIN as doc ID)
  const setTarget = useCallback(async (ein: string, amount: number) => {
    if (!db || !userId) {
      throw new Error('Not authenticated');
    }

    if (amount <= 0) {
      throw new Error('Target amount must be positive');
    }

    const existing = targetsList.find(t => t.charityEin === ein);
    setError(null);

    try {
      const docRef = doc(db, 'users', userId, 'charity_targets', ein);
      const now = Timestamp.now();

      if (existing) {
        await setDoc(docRef, {
          charityEin: ein,
          targetAmount: amount,
          createdAt: existing.createdAt,
          updatedAt: now,
        });

        setTargetsList(prev =>
          prev.map(t => t.charityEin === ein
            ? { ...t, targetAmount: amount, updatedAt: now.toDate().toISOString() }
            : t
          )
        );
      } else {
        const data = {
          charityEin: ein,
          targetAmount: amount,
          createdAt: now,
          updatedAt: now,
        };
        await setDoc(docRef, data);
        setTargetsList(prev => [docToTarget(data as Record<string, unknown>, ein, userId), ...prev]);
      }
    } catch (err) {
      console.error('Error setting target:', err);
      const message = err instanceof Error ? err.message : 'Failed to set target';
      setError(message);
      throw new Error(message);
    }
  }, [db, userId, targetsList]);

  // Remove a target
  const removeTarget = useCallback(async (ein: string) => {
    if (!db || !userId) {
      throw new Error('Not authenticated');
    }

    const existing = targetsList.find(t => t.charityEin === ein);
    if (!existing) return;

    // Optimistic update
    setTargetsList(prev => prev.filter(t => t.charityEin !== ein));
    setError(null);

    try {
      const docRef = doc(db, 'users', userId, 'charity_targets', ein);
      await deleteDoc(docRef);
    } catch (err) {
      // Rollback
      setTargetsList(prev => [...prev, existing]);
      console.error('Error removing target:', err);
      const message = err instanceof Error ? err.message : 'Failed to remove target';
      setError(message);
      throw new Error(message);
    }
  }, [db, userId, targetsList]);

  // Get target for a specific charity
  const getTarget = useCallback((ein: string): number | undefined => {
    return targets.get(ein);
  }, [targets]);

  // Get total of all targets
  const getTotalTargeted = useCallback((): number => {
    return targetsList.reduce((sum, t) => sum + t.targetAmount, 0);
  }, [targetsList]);

  return {
    targets,
    targetsList,
    isLoading,
    error,
    setTarget,
    removeTarget,
    getTarget,
    getTotalTargeted,
    refreshTargets: fetchTargets,
  };
}

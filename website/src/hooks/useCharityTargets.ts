/**
 * Hook for managing per-charity dollar targets
 * Allows users to set giving goals for specific charities
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSupabase } from '../auth/SupabaseProvider';
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

// Convert snake_case DB row to camelCase
function dbToTarget(row: Record<string, unknown>): CharityTarget {
  return {
    id: row.id as string,
    userId: row.user_id as string,
    charityEin: row.charity_ein as string,
    targetAmount: Number(row.target_amount),
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  };
}

export function useCharityTargets(): UseCharityTargetsResult {
  const { supabase, session } = useSupabase();
  const [targetsList, setTargetsList] = useState<CharityTarget[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const userId = session?.user?.id;

  // Create a Map for O(1) lookups
  const targets = useMemo(() => {
    return new Map(targetsList.map(t => [t.charityEin, t.targetAmount]));
  }, [targetsList]);

  // Fetch all targets
  const fetchTargets = useCallback(async () => {
    if (!supabase || !userId) {
      setTargetsList([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const { data, error: fetchError } = await supabase
        .from('charity_targets')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: false });

      if (fetchError) throw fetchError;
      setTargetsList((data || []).map(dbToTarget));
    } catch (err) {
      console.error('Error fetching charity targets:', err);
      setError(err instanceof Error ? err.message : 'Failed to load targets');
    } finally {
      setIsLoading(false);
    }
  }, [supabase, userId]);

  useEffect(() => {
    fetchTargets();
  }, [fetchTargets]);

  // Set or update a target (upsert)
  const setTarget = useCallback(async (ein: string, amount: number) => {
    if (!supabase || !userId) {
      throw new Error('Not authenticated');
    }

    if (amount <= 0) {
      throw new Error('Target amount must be positive');
    }

    const existing = targetsList.find(t => t.charityEin === ein);
    setError(null);

    try {
      if (existing) {
        // Update existing target
        const { error: updateError } = await supabase
          .from('charity_targets')
          .update({ target_amount: amount, updated_at: new Date().toISOString() })
          .eq('user_id', userId)
          .eq('charity_ein', ein);

        if (updateError) throw updateError;

        setTargetsList(prev =>
          prev.map(t => t.charityEin === ein
            ? { ...t, targetAmount: amount, updatedAt: new Date().toISOString() }
            : t
          )
        );
      } else {
        // Insert new target
        const { data, error: insertError } = await supabase
          .from('charity_targets')
          .insert({
            user_id: userId,
            charity_ein: ein,
            target_amount: amount,
          })
          .select()
          .single();

        if (insertError) throw insertError;
        setTargetsList(prev => [dbToTarget(data), ...prev]);
      }
    } catch (err) {
      console.error('Error setting target:', err);
      const message = err instanceof Error ? err.message : 'Failed to set target';
      setError(message);
      throw new Error(message);
    }
  }, [supabase, userId, targetsList]);

  // Remove a target
  const removeTarget = useCallback(async (ein: string) => {
    if (!supabase || !userId) {
      throw new Error('Not authenticated');
    }

    const existing = targetsList.find(t => t.charityEin === ein);
    if (!existing) return;

    // Optimistic update
    setTargetsList(prev => prev.filter(t => t.charityEin !== ein));
    setError(null);

    try {
      const { error: deleteError } = await supabase
        .from('charity_targets')
        .delete()
        .eq('user_id', userId)
        .eq('charity_ein', ein);

      if (deleteError) throw deleteError;
    } catch (err) {
      // Rollback
      setTargetsList(prev => [...prev, existing]);
      console.error('Error removing target:', err);
      const message = err instanceof Error ? err.message : 'Failed to remove target';
      setError(message);
      throw new Error(message);
    }
  }, [supabase, userId, targetsList]);

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

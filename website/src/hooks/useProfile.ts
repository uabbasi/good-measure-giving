/**
 * Hook for managing user profile data
 * Handles CRUD operations for user_profiles table in Supabase
 */

import { useState, useEffect, useCallback } from 'react';
import { useSupabase } from '../auth/SupabaseProvider';
import type {
  UserProfile,
  GivingPriorities,
  GeographicPreference,
  FiqhPreferences,
  GivingBucket,
  CharityBucketAssignment,
} from '../../types';

interface UseProfileResult {
  profile: UserProfile | null;
  isLoading: boolean;
  error: string | null;
  updateProfile: (updates: Partial<ProfileUpdates>) => Promise<void>;
  refreshProfile: () => Promise<void>;
}

interface ProfileUpdates {
  givingPriorities: GivingPriorities;
  geographicPreferences: GeographicPreference[];
  fiqhPreferences: FiqhPreferences;
  zakatAnniversary: string | null;
  targetZakatAmount: number | null;
  givingBuckets: GivingBucket[];
  charityBucketAssignments: CharityBucketAssignment[];
}

// Convert snake_case DB row to camelCase
function dbToProfile(row: Record<string, unknown>): UserProfile {
  return {
    id: row.id as string,
    givingPriorities: (row.giving_priorities as GivingPriorities) || {},
    geographicPreferences: (row.geographic_preferences as GeographicPreference[]) || [],
    fiqhPreferences: (row.fiqh_preferences as FiqhPreferences) || {},
    zakatAnniversary: row.zakat_anniversary as string | null,
    targetZakatAmount: row.target_zakat_amount ? Number(row.target_zakat_amount) : null,
    givingBuckets: (row.giving_buckets as GivingBucket[]) || [],
    charityBucketAssignments: (row.charity_bucket_assignments as CharityBucketAssignment[]) || [],
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  };
}

// Convert camelCase updates to snake_case for DB
function updatesToDb(updates: Partial<ProfileUpdates>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  if (updates.givingPriorities !== undefined) {
    result.giving_priorities = updates.givingPriorities;
  }
  if (updates.geographicPreferences !== undefined) {
    result.geographic_preferences = updates.geographicPreferences;
  }
  if (updates.fiqhPreferences !== undefined) {
    result.fiqh_preferences = updates.fiqhPreferences;
  }
  if (updates.zakatAnniversary !== undefined) {
    result.zakat_anniversary = updates.zakatAnniversary;
  }
  if (updates.targetZakatAmount !== undefined) {
    result.target_zakat_amount = updates.targetZakatAmount;
  }
  if (updates.givingBuckets !== undefined) {
    result.giving_buckets = updates.givingBuckets;
  }
  if (updates.charityBucketAssignments !== undefined) {
    result.charity_bucket_assignments = updates.charityBucketAssignments;
  }
  return result;
}

export function useProfile(): UseProfileResult {
  const { supabase, session } = useSupabase();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const userId = session?.user?.id;

  // Fetch profile from Supabase
  const fetchProfile = useCallback(async () => {
    if (!supabase || !userId) {
      setProfile(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const { data, error: fetchError } = await supabase
        .from('user_profiles')
        .select('*')
        .eq('id', userId)
        .single();

      if (fetchError) {
        // PGRST116 = no rows found, which is OK for new users
        if (fetchError.code === 'PGRST116') {
          // Create a new profile for this user
          const { data: newData, error: insertError } = await supabase
            .from('user_profiles')
            .insert({ id: userId })
            .select()
            .single();

          if (insertError) {
            throw insertError;
          }
          setProfile(dbToProfile(newData));
        } else {
          throw fetchError;
        }
      } else {
        setProfile(dbToProfile(data));
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setIsLoading(false);
    }
  }, [supabase, userId]);

  // Load profile when user changes
  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  // Update profile
  const updateProfile = useCallback(async (updates: Partial<ProfileUpdates>) => {
    if (!supabase || !userId) {
      throw new Error('Not authenticated');
    }

    setError(null);

    try {
      const dbUpdates = updatesToDb(updates);
      const { data, error: updateError } = await supabase
        .from('user_profiles')
        .update(dbUpdates)
        .eq('id', userId)
        .select()
        .single();

      if (updateError) {
        throw updateError;
      }

      setProfile(dbToProfile(data));
    } catch (err) {
      console.error('Error updating profile:', err);
      const message = err instanceof Error ? err.message : 'Failed to update profile';
      setError(message);
      throw new Error(message);
    }
  }, [supabase, userId]);

  return {
    profile,
    isLoading,
    error,
    updateProfile,
    refreshProfile: fetchProfile,
  };
}

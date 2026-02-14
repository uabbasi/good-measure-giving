/**
 * Hook for managing user profile data
 * Handles CRUD operations for user profile in Firestore
 */

import { useState, useEffect, useCallback } from 'react';
import { doc, getDoc, setDoc, updateDoc, Timestamp } from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
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

function docToProfile(data: Record<string, unknown>, id: string): UserProfile {
  return {
    id,
    givingPriorities: (data.givingPriorities as GivingPriorities) || {},
    geographicPreferences: (data.geographicPreferences as GeographicPreference[]) || [],
    fiqhPreferences: (data.fiqhPreferences as FiqhPreferences) || {},
    zakatAnniversary: (data.zakatAnniversary as string) || null,
    targetZakatAmount: data.targetZakatAmount != null ? Number(data.targetZakatAmount) : null,
    givingBuckets: (data.givingBuckets as GivingBucket[]) || [],
    charityBucketAssignments: (data.charityBucketAssignments as CharityBucketAssignment[]) || [],
    createdAt: data.createdAt instanceof Timestamp
      ? data.createdAt.toDate().toISOString()
      : (data.createdAt as string) || new Date().toISOString(),
    updatedAt: data.updatedAt instanceof Timestamp
      ? data.updatedAt.toDate().toISOString()
      : (data.updatedAt as string) || new Date().toISOString(),
  };
}

export function useProfile(): UseProfileResult {
  const { db, userId } = useFirebaseData();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch profile from Firestore
  const fetchProfile = useCallback(async () => {
    if (!db || !userId) {
      setProfile(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const docRef = doc(db, 'users', userId);
      const snap = await getDoc(docRef);

      if (snap.exists()) {
        setProfile(docToProfile(snap.data(), userId));
      } else {
        // Auto-create profile for new users
        const now = Timestamp.now();
        const newData = {
          givingPriorities: {},
          geographicPreferences: [],
          fiqhPreferences: {},
          zakatAnniversary: null,
          targetZakatAmount: null,
          givingBuckets: [],
          charityBucketAssignments: [],
          createdAt: now,
          updatedAt: now,
        };
        await setDoc(docRef, newData);
        setProfile(docToProfile(newData as Record<string, unknown>, userId));
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setIsLoading(false);
    }
  }, [db, userId]);

  // Load profile when user changes
  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  // Update profile
  const updateProfile = useCallback(async (updates: Partial<ProfileUpdates>) => {
    if (!db || !userId) {
      throw new Error('Not authenticated');
    }

    setError(null);

    try {
      const docRef = doc(db, 'users', userId);
      await updateDoc(docRef, {
        ...updates,
        updatedAt: Timestamp.now(),
      });

      // Refresh to get server timestamps
      const snap = await getDoc(docRef);
      if (snap.exists()) {
        setProfile(docToProfile(snap.data(), userId));
      }
    } catch (err) {
      console.error('Error updating profile:', err);
      const message = err instanceof Error ? err.message : 'Failed to update profile';
      setError(message);
      throw new Error(message);
    }
  }, [db, userId]);

  return {
    profile,
    isLoading,
    error,
    updateProfile,
    refreshProfile: fetchProfile,
  };
}

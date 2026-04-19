/**
 * useAddToGiving — atomic "add a charity to my giving plan" hook.
 *
 * Used by CharityCard and detail views. On add:
 *  1) Picks a category tag from the charity's causeTags via pickBestTag.
 *  2) Finds an existing GivingBucket that covers that tag, or creates a new one.
 *  3) Appends a v2 CharityBucketAssignment in the 'intended' state.
 *  4) Writes both (profile doc update) atomically via writeBatch.
 *
 * Idempotent: if the ein is already assigned, the hook no-ops.
 */

import { useCallback, useMemo, useState } from 'react';
import { writeBatch, doc, Timestamp } from 'firebase/firestore';
import { db } from '../auth/firebase';
import { useAuth } from '../auth/useAuth';
import { useProfileState } from '../contexts/UserFeaturesContext';
import { useCharities } from './useCharities';
import { ALL_TAGS, pickBestTag } from '../constants/givingTags';
import { makeIntendedAssignment } from '../utils/assignments';
import type { GivingBucket } from '../../types';

const BUCKET_COLORS = [
  '#10b981', '#3b82f6', '#8b5cf6', '#f59e0b',
  '#ef4444', '#ec4899', '#06b6d4', '#84cc16',
];

interface UseAddToGivingResult {
  /** Atomic add-to-plan. No-op if not signed in or already in plan. */
  addToGiving: (ein: string, charityName?: string) => Promise<void>;
  /** True when this ein already has an assignment in the current profile. */
  isInPlan: (ein: string) => boolean;
  /** True while a write is in flight. */
  saving: boolean;
}

export function useAddToGiving(): UseAddToGivingResult {
  const { uid } = useAuth();
  const { profile } = useProfileState();
  const { summaries } = useCharities();
  const [saving, setSaving] = useState(false);

  // Lookup map: ein -> causeTags (for auto-category picking)
  const causeTagsByEin = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const s of summaries || []) {
      if (s.causeTags && s.causeTags.length > 0) m.set(s.ein, s.causeTags);
    }
    return m;
  }, [summaries]);

  const isInPlan = useCallback(
    (ein: string): boolean => {
      if (!profile) return false;
      return (profile.charityBucketAssignments || []).some(a => a.charityEin === ein);
    },
    [profile],
  );

  const addToGiving = useCallback(
    async (ein: string, _charityName?: string): Promise<void> => {
      if (!db || !uid || !profile || saving) return;
      // Idempotent: already in plan
      if (isInPlan(ein)) return;

      const causeTags = causeTagsByEin.get(ein) || [];
      const primaryTag = pickBestTag(causeTags);

      setSaving(true);
      try {
        const currentBuckets = profile.givingBuckets || [];
        const currentAssignments = profile.charityBucketAssignments || [];

        // Try to find an existing bucket whose tags include the picked tag
        let bucketId: string | null = null;
        let newBucket: GivingBucket | null = null;

        if (primaryTag) {
          const existing = currentBuckets.find(b => b.tags.includes(primaryTag));
          if (existing) {
            bucketId = existing.id;
          }
        }

        if (!bucketId) {
          // Create a new bucket (either from primary tag, or a fallback "Uncategorized")
          const tagDef = primaryTag ? ALL_TAGS.find(t => t.id === primaryTag) : null;
          const label = tagDef?.label
            || (primaryTag
              ? primaryTag.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
              : 'Uncategorized');
          newBucket = {
            id: crypto.randomUUID(),
            name: label,
            tags: primaryTag ? [primaryTag] : [],
            percentage: 0,
            color: BUCKET_COLORS[currentBuckets.length % BUCKET_COLORS.length],
          };
          bucketId = newBucket.id;
        }

        const nextBuckets = newBucket ? [...currentBuckets, newBucket] : currentBuckets;
        const nextAssignments = [
          ...currentAssignments,
          makeIntendedAssignment(ein, bucketId),
        ];

        const batch = writeBatch(db);
        const userRef = doc(db, 'users', uid);
        batch.update(userRef, {
          givingBuckets: nextBuckets,
          charityBucketAssignments: nextAssignments,
          updatedAt: Timestamp.now(),
        });
        await batch.commit();
      } finally {
        setSaving(false);
      }
    },
    [uid, profile, saving, isInPlan, causeTagsByEin],
  );

  return { addToGiving, isInPlan, saving };
}

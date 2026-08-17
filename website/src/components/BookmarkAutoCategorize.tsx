/**
 * BookmarkAutoCategorize: Always-mounted component that auto-assigns
 * bookmarked charities to giving plan buckets based on cause tags.
 *
 * Two triggers:
 * 1. Real-time: listens for 'gmg:bookmark-added' events (new bookmarks)
 * 2. Backfill: on mount, categorizes any existing uncategorized bookmarks
 */

import { useEffect, useRef } from 'react';
import { doc, getDoc } from 'firebase/firestore';
import { useBookmarkState, useProfileState } from '../contexts/UserFeaturesContext';
import { useFirebaseData } from '../auth/FirebaseProvider';
import { useCharities } from '../hooks/useCharities';
import { ALL_TAGS, pickBestTag } from '../constants/givingTags';
import { makeIntendedAssignment } from '../utils/assignments';
import type { GivingBucket, CharityBucketAssignment } from '../../types';

const BUCKET_COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16'];

/** Find or create a bucket for the given causeTags, returns updated buckets + the matched bucketId */
function findOrCreateBucket(
  causeTags: string[],
  currentBuckets: GivingBucket[],
): { bucketId: string; newBucket?: GivingBucket } {
  // Try to match an existing bucket
  for (const bucket of currentBuckets) {
    if (bucket.tags.some(tag => causeTags.includes(tag))) {
      return { bucketId: bucket.id };
    }
  }

  // Pick best tag: geography > cause > population
  const primaryTag = pickBestTag(causeTags);
  if (!primaryTag) return { bucketId: '' };
  const tagDef = ALL_TAGS.find(t => t.id === primaryTag);
  const label = tagDef?.label || primaryTag.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const newBucketId = crypto.randomUUID();
  const newBucket: GivingBucket = {
    id: newBucketId,
    name: label,
    tags: [primaryTag],
    percentage: 0,
    color: BUCKET_COLORS[currentBuckets.length % BUCKET_COLORS.length],
  };
  return { bucketId: newBucketId, newBucket };
}

export function BookmarkAutoCategorize() {
  const { profile, updateProfile } = useProfileState();
  const { bookmarks } = useBookmarkState();
  const { summaries } = useCharities();
  const { db, userId } = useFirebaseData();
  const backfillDone = useRef(false);

  // 1. Real-time: handle new bookmarks via custom event
  useEffect(() => {
    const handleBookmarkAdded = (e: Event) => {
      const detail = (e as CustomEvent<{ charityEin: string; charityName: string; causeTags?: string[] }>).detail;
      const { charityEin, causeTags } = detail;
      if (!charityEin || !causeTags || causeTags.length === 0 || !profile) return;

      const currentBuckets = profile.givingBuckets || [];
      const currentAssignments = profile.charityBucketAssignments || [];

      if (currentAssignments.some(a => a.charityEin === charityEin)) return;

      const { bucketId, newBucket } = findOrCreateBucket(causeTags, currentBuckets);

      void updateProfile({
        ...(newBucket ? { givingBuckets: [...currentBuckets, newBucket] } : {}),
        charityBucketAssignments: [
          ...currentAssignments,
          makeIntendedAssignment(charityEin, bucketId),
        ],
      });
    };

    window.addEventListener('gmg:bookmark-added', handleBookmarkAdded);
    return () => window.removeEventListener('gmg:bookmark-added', handleBookmarkAdded);
  }, [profile, updateProfile]);

  // 2. Backfill: categorize existing uncategorized bookmarks.
  //
  // `profile` here can be stale relative to `bookmarks`: they're two
  // independent hooks that refetch on their own schedules (most visibly
  // right after a dev-only seeded quick-login, but the same ordering gap
  // exists for any real user whose profile hasn't finished loading yet
  // when their bookmarks have). Computing `assignedEins` from a stale
  // `profile` and then writing that back can clobber real buckets/
  // assignments — including already-given amounts — with fabricated
  // placeholders. To stay correct regardless of ordering, re-read the
  // profile document directly right before writing instead of trusting
  // the closed-over React state.
  useEffect(() => {
    if (backfillDone.current) return;
    if (!profile || !summaries || summaries.length === 0 || bookmarks.length === 0 || !db || !userId) return;

    backfillDone.current = true;

    void (async () => {
      const snap = await getDoc(doc(db, 'users', userId));
      const data = snap.exists() ? snap.data() : {};
      const currentBuckets = (data.givingBuckets as GivingBucket[]) || [];
      const currentAssignments = (data.charityBucketAssignments as CharityBucketAssignment[]) || [];
      const assignedEins = new Set(currentAssignments.map(a => a.charityEin));

      // Find bookmarks that have no assignment
      const unassigned = bookmarks.filter(b => !assignedEins.has(b.charityEin));
      if (unassigned.length === 0) return;

      // Build a map of EIN -> causeTags from summaries
      const causeTagsMap = new Map<string, string[]>();
      for (const s of summaries) {
        if (s.causeTags && s.causeTags.length > 0) {
          causeTagsMap.set(s.ein, s.causeTags);
        }
      }

      let bucketsAccum = [...currentBuckets];
      const newAssignments = [...currentAssignments];
      let changed = false;

      for (const bookmark of unassigned) {
        const tags = causeTagsMap.get(bookmark.charityEin);
        if (!tags || tags.length === 0) continue;

        const { bucketId, newBucket } = findOrCreateBucket(tags, bucketsAccum);
        if (newBucket) {
          bucketsAccum = [...bucketsAccum, newBucket];
        }
        newAssignments.push(makeIntendedAssignment(bookmark.charityEin, bucketId));
        changed = true;
      }

      if (changed) {
        await updateProfile({
          givingBuckets: bucketsAccum,
          charityBucketAssignments: newAssignments,
        });
      }
    })();
  }, [profile, bookmarks, summaries, updateProfile, db, userId]);

  return null;
}

/**
 * Regression test: the backfill effect used to compute "which bookmarks are
 * unassigned" from the React `profile` prop, which can be stale relative to
 * Firestore — `useProfile` and `useBookmarks` refetch independently, so
 * there's a window where bookmarks have loaded but the profile hasn't
 * refetched its real (already-seeded) buckets/assignments yet. In that
 * window, the old code treated an *already-assigned* charity as unassigned
 * and overwrote the real Firestore assignment with a fabricated placeholder,
 * silently destroying real given/intended amounts.
 *
 * The fix reads the profile document fresh via `getDoc` right before writing,
 * instead of trusting the closed-over `profile` state.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';

const getDoc = vi.fn();
const doc = vi.fn((...args: unknown[]) => ({ _ref: args }));

vi.mock('firebase/firestore', () => ({
  getDoc: (...args: unknown[]) => getDoc(...args),
  doc: (...args: unknown[]) => doc(...args),
}));

vi.mock('../auth/FirebaseProvider', () => ({
  useFirebaseData: () => ({ db: { _fake: true }, userId: 'user-1' }),
}));

const updateProfile = vi.fn(async (_updates: Record<string, unknown>) => {});

// The React-state `profile` is stale on purpose: empty buckets/assignments,
// simulating that useProfile hasn't refetched the real seeded data yet.
vi.mock('../contexts/UserFeaturesContext', () => ({
  useProfileState: () => ({
    profile: { id: 'user-1', givingBuckets: [], charityBucketAssignments: [] },
    updateProfile,
  }),
  useBookmarkState: () => ({
    bookmarks: [
      { charityEin: 'REAL1', charityName: 'Already Assigned Charity' },
      { charityEin: 'NEW1', charityName: 'Newly Bookmarked Charity' },
    ],
  }),
}));

vi.mock('../hooks/useCharities', () => ({
  useCharities: () => ({
    summaries: [
      { ein: 'REAL1', causeTags: ['yemen'] },
      { ein: 'NEW1', causeTags: ['yemen'] },
    ],
  }),
}));

import { BookmarkAutoCategorize } from './BookmarkAutoCategorize';

beforeEach(() => {
  updateProfile.mockClear();
  getDoc.mockClear();
});

describe('BookmarkAutoCategorize backfill', () => {
  it('does not clobber a real Firestore assignment that the stale profile prop is missing', async () => {
    // Firestore's actual current state, ahead of what the stale `profile` prop shows.
    const realAssignment = {
      charityEin: 'REAL1', bucketId: 'existing-bucket', status: 'confirmed',
      intended: 500, given: 500, intendedAt: '2026-01-01T00:00:00.000Z',
    };
    const realBucket = { id: 'existing-bucket', name: 'Yemen', tags: ['yemen'], percentage: 50, color: '#10b981' };

    getDoc.mockResolvedValue({
      exists: () => true,
      data: () => ({
        givingBuckets: [realBucket],
        charityBucketAssignments: [realAssignment],
      }),
    });

    render(<BookmarkAutoCategorize />);

    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1));

    const payload = updateProfile.mock.calls[0][0] as {
      givingBuckets: Array<{ id: string }>;
      charityBucketAssignments: Array<{ charityEin: string; given: number }>;
    };

    // The real, already-given assignment must survive untouched.
    const survivingReal = payload.charityBucketAssignments.find(
      (a) => a.charityEin === 'REAL1',
    );
    expect(survivingReal).toEqual(realAssignment);

    // Only the genuinely-unassigned bookmark gets a fresh assignment.
    const newAssignment = payload.charityBucketAssignments.find(
      (a) => a.charityEin === 'NEW1',
    );
    expect(newAssignment).toBeDefined();
    expect(newAssignment?.given).toBe(0);

    // The existing bucket is preserved, not replaced.
    expect(payload.givingBuckets).toEqual(
      expect.arrayContaining([expect.objectContaining({ id: 'existing-bucket' })]),
    );
  });
});

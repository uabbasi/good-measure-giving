/**
 * Unit tests for useAddToGiving.
 *
 * Covers:
 *  - idempotent add (no-op when ein is already in plan)
 *  - new-bucket creation when no existing bucket covers the tag
 *  - existing-bucket append when a bucket with the tag already exists
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// --- Firestore mocks (defined inline inside factory for hoist-safety) -----
vi.mock('firebase/firestore', () => {
  const commit = vi.fn().mockResolvedValue(undefined);
  const update = vi.fn();
  const writeBatch = vi.fn(() => ({ update, commit }));
  const doc = vi.fn((...args: unknown[]) => ({ _ref: args }));
  const Timestamp = { now: () => ({ toDate: () => new Date('2026-01-01T00:00:00Z') }) };
  // Expose for assertions
  (writeBatch as any).__commit = commit;
  (writeBatch as any).__update = update;
  return { writeBatch, doc, Timestamp };
});

vi.mock('../auth/firebase', () => ({
  db: { _fake: true },
}));

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ uid: 'test-user', isSignedIn: true, isLoaded: true }),
}));

const profileRef = { current: null as any };
const updateProfileMock = vi.fn(async () => {});
vi.mock('../contexts/UserFeaturesContext', () => ({
  useProfileState: () => ({
    profile: profileRef.current,
    isLoading: false,
    error: null,
    updateProfile: updateProfileMock,
  }),
}));

vi.mock('./useCharities', () => ({
  useCharities: () => ({
    summaries: [
      { ein: 'E1', name: 'Alpha', causeTags: ['palestine', 'emergency-response'] },
      { ein: 'E2', name: 'Beta', causeTags: ['usa', 'legal-aid'] },
      { ein: 'E3', name: 'Gamma', causeTags: [] },
    ],
    loading: false,
  }),
}));

import { useAddToGiving } from './useAddToGiving';
import * as fsMod from 'firebase/firestore';

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  if (!globalThis.crypto) {
    // @ts-expect-error - polyfill for test env
    globalThis.crypto = {};
  }
  // @ts-expect-error - deterministic uuid
  globalThis.crypto.randomUUID = () => `uuid-${++uuidCounter}`;
  (fsMod.writeBatch as any).__commit.mockClear();
  (fsMod.writeBatch as any).__update.mockClear();
  updateProfileMock.mockClear();
});

describe('useAddToGiving', () => {
  it('is a no-op when ein is already in plan (idempotent)', async () => {
    profileRef.current = {
      id: 'test-user',
      givingBuckets: [],
      charityBucketAssignments: [
        {
          charityEin: 'E1', bucketId: 'B1', status: 'intended',
          intended: 0, given: 0, intendedAt: 'x',
        },
      ],
    };
    const { result } = renderHook(() => useAddToGiving());
    expect(result.current.isInPlan('E1')).toBe(true);
    await act(async () => { await result.current.addToGiving('E1'); });
    expect((fsMod.writeBatch as any).__commit).not.toHaveBeenCalled();
  });

  it('creates a new bucket when no existing bucket covers the picked tag', async () => {
    profileRef.current = {
      id: 'test-user',
      givingBuckets: [],
      charityBucketAssignments: [],
    };
    const { result } = renderHook(() => useAddToGiving());

    await act(async () => { await result.current.addToGiving('E1', 'Alpha'); });

    expect((fsMod.writeBatch as any).__commit).toHaveBeenCalledTimes(1);
    const updateArgs = (fsMod.writeBatch as any).__update.mock.calls[0];
    const payload = updateArgs[1];
    // Exactly one new bucket, tag = 'palestine' (pickBestTag favors specific geo)
    expect(payload.givingBuckets).toHaveLength(1);
    expect(payload.givingBuckets[0].tags).toEqual(['palestine']);
    // Assignment appended in 'intended' state
    expect(payload.charityBucketAssignments).toHaveLength(1);
    expect(payload.charityBucketAssignments[0]).toMatchObject({
      charityEin: 'E1',
      bucketId: payload.givingBuckets[0].id,
      status: 'intended',
      intended: 0,
      given: 0,
    });
  });

  it('appends to an existing bucket when one already covers the tag', async () => {
    profileRef.current = {
      id: 'test-user',
      givingBuckets: [
        { id: 'bucket-A', name: 'Palestine', tags: ['palestine'], percentage: 100, color: '#111' },
      ],
      charityBucketAssignments: [],
    };
    const { result } = renderHook(() => useAddToGiving());

    await act(async () => { await result.current.addToGiving('E1'); });

    const payload = (fsMod.writeBatch as any).__update.mock.calls[0][1];
    // No new bucket created
    expect(payload.givingBuckets).toHaveLength(1);
    expect(payload.givingBuckets[0].id).toBe('bucket-A');
    expect(payload.charityBucketAssignments[0].bucketId).toBe('bucket-A');
  });

  it('still writes a bucket for a charity with no causeTags (fallback)', async () => {
    profileRef.current = {
      id: 'test-user',
      givingBuckets: [],
      charityBucketAssignments: [],
    };
    const { result } = renderHook(() => useAddToGiving());

    await act(async () => { await result.current.addToGiving('E3'); });

    expect((fsMod.writeBatch as any).__commit).toHaveBeenCalledTimes(1);
    const payload = (fsMod.writeBatch as any).__update.mock.calls[0][1];
    expect(payload.charityBucketAssignments).toHaveLength(1);
    // Falls back to an "Uncategorized" bucket with empty tags
    expect(payload.givingBuckets).toHaveLength(1);
    expect(payload.givingBuckets[0].tags).toEqual([]);
  });
});

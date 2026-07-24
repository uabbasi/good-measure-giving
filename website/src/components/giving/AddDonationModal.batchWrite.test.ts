/**
 * Regression test for commit 8caccf5 (see giving-plan-undefined-field-writes
 * memory). This directly reproduces the live bug: logging a donation against
 * a plan charity while an *untouched sibling* charity in the same plan has
 * never been sent/confirmed. Before the fix, Firestore rejected the whole
 * `writeBatch.update()` — visibly, as an error banner in this exact modal —
 * because the sibling's assignment object carried an explicit
 * `confirmedAt: undefined`.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('firebase/firestore', () => {
  const update = vi.fn();
  const set = vi.fn();
  const commit = vi.fn().mockResolvedValue(undefined);
  const writeBatch = vi.fn(() => ({ update, set, commit }));
  const doc = vi.fn((...args: unknown[]) => ({ _ref: args }));
  const collection = vi.fn((...args: unknown[]) => ({ _ref: args }));
  const Timestamp = { now: () => 'TIMESTAMP' };
  (writeBatch as unknown as Record<string, unknown>).__update = update;
  (writeBatch as unknown as Record<string, unknown>).__set = set;
  (writeBatch as unknown as Record<string, unknown>).__commit = commit;
  return { writeBatch, doc, collection, Timestamp };
});

vi.mock('../../auth/firebase', () => ({
  db: { _fake: true },
}));

import { batchWriteDonationAndAssignment } from './AddDonationModal';
import * as fsMod from 'firebase/firestore';
import { assertFirestoreWritable } from '../../test-utils/assertFirestoreWritable';
import type { CharityBucketAssignment } from '../../../types';

function batchMock() {
  return fsMod.writeBatch as unknown as {
    __update: ReturnType<typeof vi.fn>;
    __set: ReturnType<typeof vi.fn>;
    __commit: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  batchMock().__update.mockClear();
  batchMock().__set.mockClear();
  batchMock().__commit.mockClear();
});

describe('batchWriteDonationAndAssignment', () => {
  it('produces a Firestore-writable payload when a sibling plan charity has never been sent/confirmed', async () => {
    const updateProfile = vi.fn(async (_updates: Record<string, unknown>) => {});

    // The charity actually being donated to — 'intended', no sentAt/confirmedAt yet.
    const matching: CharityBucketAssignment = {
      charityEin: 'INTL-AID', bucketId: 'B1', status: 'intended',
      intended: 300, given: 0, intendedAt: '2026-01-01T00:00:00.000Z',
    };
    // An untouched sibling in the same plan — 'sent' but not yet confirmed.
    // This is the assignment that broke the whole batch write pre-fix.
    const sibling: CharityBucketAssignment = {
      charityEin: 'UNICEF', bucketId: 'B1', status: 'sent',
      intended: 500, given: 250, intendedAt: '2026-01-01T00:00:00.000Z',
      sentAt: '2026-01-02T00:00:00.000Z',
    };

    await batchWriteDonationAndAssignment({
      uid: 'user-1',
      donation: {
        charityEin: 'INTL-AID',
        charityName: 'International Aid Charity',
        amount: 300,
        date: '2026-07-24',
        category: 'zakat',
        receiptReceived: false,
      },
      matching,
      profile: { id: 'user-1', charityBucketAssignments: [matching, sibling] } as unknown as Parameters<
        typeof batchWriteDonationAndAssignment
      >[0]['profile'],
      updateProfile,
    });

    expect(batchMock().__commit).toHaveBeenCalledTimes(1);

    // The `users/{uid}` document patch — this is the call that threw
    // "Unsupported field value: undefined" before the fix.
    const updatePayload = batchMock().__update.mock.calls[0][1];
    expect(() => assertFirestoreWritable(updatePayload)).not.toThrow();

    // The donation's own giving_history document.
    const setPayload = batchMock().__set.mock.calls[0][1];
    expect(() => assertFirestoreWritable(setPayload)).not.toThrow();

    // Sanity: the targeted charity actually transitioned to 'sent'.
    const updatedMatch = updatePayload.charityBucketAssignments.find(
      (a: CharityBucketAssignment) => a.charityEin === 'INTL-AID',
    );
    expect(updatedMatch.status).toBe('sent');
    expect(updatedMatch.given).toBe(300);

    // The cache-refresh write to useProfile's updateProfile must also be clean.
    expect(updateProfile).toHaveBeenCalledTimes(1);
    expect(() => assertFirestoreWritable(updateProfile.mock.calls[0][0])).not.toThrow();
  });
});

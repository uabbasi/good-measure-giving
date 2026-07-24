import { describe, it, expect } from 'vitest';
import { docToProfile, normalizeAssignment } from './useProfile';
import { assertFirestoreWritable } from '../test-utils/assertFirestoreWritable';

describe('normalizeAssignment', () => {
  const fallback = '2026-01-01T00:00:00.000Z';

  it('default-fills missing v2 fields for legacy {charityEin, bucketId}', () => {
    const out = normalizeAssignment({ charityEin: 'E1', bucketId: 'B1' }, fallback);
    expect(out).toEqual({
      charityEin: 'E1',
      bucketId: 'B1',
      status: 'intended',
      intended: 0,
      given: 0,
      intendedAt: fallback,
      sentAt: undefined,
      confirmedAt: undefined,
    });
  });

  it('preserves existing v2 fields when present', () => {
    const out = normalizeAssignment(
      {
        charityEin: 'E1',
        bucketId: 'B1',
        status: 'sent',
        intended: 500,
        given: 250,
        intendedAt: '2025-12-01T00:00:00.000Z',
        sentAt: '2025-12-15T00:00:00.000Z',
      },
      fallback,
    );
    expect(out.status).toBe('sent');
    expect(out.intended).toBe(500);
    expect(out.given).toBe(250);
    expect(out.intendedAt).toBe('2025-12-01T00:00:00.000Z');
    expect(out.sentAt).toBe('2025-12-15T00:00:00.000Z');
  });

  it('keeps numeric zero values instead of falsily replacing them', () => {
    const out = normalizeAssignment(
      { charityEin: 'E1', bucketId: 'B1', intended: 0, given: 0 },
      fallback,
    );
    expect(out.intended).toBe(0);
    expect(out.given).toBe(0);
  });

  // Regression test for commit 8caccf5: normalizeAssignment used to assign
  // `sentAt: raw.sentAt` / `confirmedAt: raw.confirmedAt` unconditionally,
  // which sets the key to literal `undefined` (not absent) whenever the
  // Firestore doc doesn't have it. `toEqual`/`toBeUndefined()` above can't
  // catch that — they treat a missing key and an undefined-valued key as
  // equal. This asserts the structural property that actually matters:
  // Firestore's WriteBatch/updateDoc reject explicit `undefined` anywhere in
  // a payload, so the omitted fields must be genuinely absent.
  it('omits sentAt/confirmedAt entirely (not just undefined) when unset — Firestore rejects explicit undefined', () => {
    const out = normalizeAssignment({ charityEin: 'E1', bucketId: 'B1' }, fallback);
    expect('sentAt' in out).toBe(false);
    expect('confirmedAt' in out).toBe(false);
    expect(() => assertFirestoreWritable(out)).not.toThrow();
  });
});

describe('docToProfile', () => {
  it('fills v2 assignment fields using the doc createdAt as fallback intendedAt', () => {
    const docCreatedAt = '2025-05-01T12:00:00.000Z';
    const data = {
      createdAt: docCreatedAt,
      updatedAt: docCreatedAt,
      charityBucketAssignments: [
        { charityEin: 'E1', bucketId: 'B1' }, // legacy shape
      ],
    };
    const profile = docToProfile(data, 'user-1');
    expect(profile.createdAt).toBe(docCreatedAt);
    expect(profile.charityBucketAssignments).toHaveLength(1);
    const a = profile.charityBucketAssignments[0];
    expect(a.status).toBe('intended');
    expect(a.intended).toBe(0);
    expect(a.given).toBe(0);
    expect(a.intendedAt).toBe(docCreatedAt);
  });

  it('returns an empty assignments array when missing from doc', () => {
    const profile = docToProfile({ createdAt: '2025-01-01T00:00:00.000Z' }, 'user-2');
    expect(profile.charityBucketAssignments).toEqual([]);
  });

  it('preserves extended v2 assignments untouched', () => {
    const data = {
      createdAt: '2025-01-01T00:00:00.000Z',
      updatedAt: '2025-01-01T00:00:00.000Z',
      charityBucketAssignments: [
        {
          charityEin: 'E1',
          bucketId: 'B1',
          status: 'confirmed',
          intended: 1000,
          given: 1000,
          intendedAt: '2024-12-01T00:00:00.000Z',
          sentAt: '2024-12-10T00:00:00.000Z',
          confirmedAt: '2024-12-15T00:00:00.000Z',
        },
      ],
    };
    const profile = docToProfile(data, 'user-3');
    const a = profile.charityBucketAssignments[0];
    expect(a.status).toBe('confirmed');
    expect(a.intended).toBe(1000);
    expect(a.given).toBe(1000);
    expect(a.sentAt).toBe('2024-12-10T00:00:00.000Z');
    expect(a.confirmedAt).toBe('2024-12-15T00:00:00.000Z');
  });

  // Regression test for commit 8caccf5. Reproduces the exact live bug: a
  // plan with charities at different stages (some 'intended' — no sentAt/
  // confirmedAt at all; a 'sent' one with sentAt but no confirmedAt yet) is
  // the NORMAL state of a giving plan, not an edge case. Several UI actions
  // (Mark Confirmed, Set Intended Amount, Log Donation) round-trip the
  // *whole* charityBucketAssignments array back to Firestore via
  // `updateDoc({ charityBucketAssignments: array })` — a single untouched
  // sibling assignment carrying an explicit `undefined` optional field was
  // enough to fail that entire write, for every charity in the plan, not
  // just the one missing the field.
  it('produces a full assignments array that survives a Firestore round-trip write, even with mixed intended/sent/confirmed charities', () => {
    const data = {
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-01-01T00:00:00.000Z',
      charityBucketAssignments: [
        // 'sent': has sentAt, no confirmedAt yet (the normal pre-confirmation state)
        {
          charityEin: 'UNICEF', bucketId: 'B1', status: 'sent',
          intended: 500, given: 250, intendedAt: '2026-01-01T00:00:00.000Z',
          sentAt: '2026-01-02T00:00:00.000Z',
        },
        // 'intended': neither sentAt nor confirmedAt set (never donated yet)
        {
          charityEin: 'ICNA', bucketId: 'B2', status: 'intended',
          intended: 200, given: 0, intendedAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    };
    const profile = docToProfile(data, 'user-1');
    // This is exactly the payload shape sent by ProfilePage.tsx's
    // onMarkConfirmed/onSetCharityIntended handlers.
    expect(() =>
      assertFirestoreWritable({ charityBucketAssignments: profile.charityBucketAssignments }),
    ).not.toThrow();
  });
});

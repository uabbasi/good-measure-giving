import { describe, it, expect } from 'vitest';
import { docToProfile, normalizeAssignment } from './useProfile';

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
});

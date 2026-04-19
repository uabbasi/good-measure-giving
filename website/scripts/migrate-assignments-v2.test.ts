import { describe, it, expect } from 'vitest';
import {
  deriveAssignmentV2,
  needsMigration,
  type LegacyAssignment,
  type DonationRecord,
} from './migrate-assignments-v2.logic';

const USER_CREATED_AT = '2025-03-01T00:00:00.000Z';

function mkAssignment(overrides: Partial<LegacyAssignment> = {}): LegacyAssignment {
  return { charityEin: 'EIN-1', bucketId: 'BUCKET-1', ...overrides };
}

describe('needsMigration', () => {
  it('returns true when no status is set', () => {
    expect(needsMigration(mkAssignment())).toBe(true);
  });
  it('returns false when status is already present', () => {
    expect(needsMigration(mkAssignment({ status: 'intended' }))).toBe(false);
  });
});

describe('deriveAssignmentV2', () => {
  it('0 donations → status=intended, given=0, no sent/confirmed timestamps', () => {
    const out = deriveAssignmentV2({
      assignment: mkAssignment(),
      donations: [],
      userCreatedAt: USER_CREATED_AT,
    });
    expect(out.status).toBe('intended');
    expect(out.given).toBe(0);
    expect(out.sentAt).toBeUndefined();
    expect(out.confirmedAt).toBeUndefined();
    expect(out.intendedAt).toBe(USER_CREATED_AT);
    expect(out.intended).toBe(0);
  });

  it('1 donation without receipt → status=sent, given=amount, sentAt populated', () => {
    const donations: DonationRecord[] = [
      { charityEin: 'EIN-1', amount: 250, receiptReceived: false, createdAt: '2025-07-04T12:00:00.000Z' },
    ];
    const out = deriveAssignmentV2({
      assignment: mkAssignment(),
      donations,
      userCreatedAt: USER_CREATED_AT,
    });
    expect(out.status).toBe('sent');
    expect(out.given).toBe(250);
    expect(out.sentAt).toBe('2025-07-04T12:00:00.000Z');
    expect(out.confirmedAt).toBeUndefined();
  });

  it('1 donation with receipt → status=confirmed, given=amount, both timestamps populated', () => {
    const donations: DonationRecord[] = [
      { charityEin: 'EIN-1', amount: 500, receiptReceived: true, createdAt: '2025-09-15T12:00:00.000Z' },
    ];
    const out = deriveAssignmentV2({
      assignment: mkAssignment(),
      donations,
      userCreatedAt: USER_CREATED_AT,
    });
    expect(out.status).toBe('confirmed');
    expect(out.given).toBe(500);
    expect(out.sentAt).toBe('2025-09-15T12:00:00.000Z');
    expect(out.confirmedAt).toBe('2025-09-15T12:00:00.000Z');
  });

  it('2 donations mixed (1 with receipt, 1 without) → status=confirmed, given=sum', () => {
    const donations: DonationRecord[] = [
      { charityEin: 'EIN-1', amount: 100, receiptReceived: false, createdAt: '2025-06-01T00:00:00.000Z' },
      { charityEin: 'EIN-1', amount: 400, receiptReceived: true, createdAt: '2025-08-01T00:00:00.000Z' },
    ];
    const out = deriveAssignmentV2({
      assignment: mkAssignment(),
      donations,
      userCreatedAt: USER_CREATED_AT,
    });
    expect(out.status).toBe('confirmed');
    expect(out.given).toBe(500);
    // sentAt = latest of any matching
    expect(out.sentAt).toBe('2025-08-01T00:00:00.000Z');
    // confirmedAt = latest of receipt=true matching
    expect(out.confirmedAt).toBe('2025-08-01T00:00:00.000Z');
  });

  it('ignores donations for other charity EINs', () => {
    const donations: DonationRecord[] = [
      { charityEin: 'EIN-OTHER', amount: 999, receiptReceived: true, createdAt: '2025-08-01T00:00:00.000Z' },
    ];
    const out = deriveAssignmentV2({
      assignment: mkAssignment(),
      donations,
      userCreatedAt: USER_CREATED_AT,
    });
    expect(out.status).toBe('intended');
    expect(out.given).toBe(0);
    expect(out.sentAt).toBeUndefined();
    expect(out.confirmedAt).toBeUndefined();
  });

  it('preserves existing intendedAt on the assignment if already set', () => {
    const out = deriveAssignmentV2({
      assignment: mkAssignment({ intendedAt: '2024-01-01T00:00:00.000Z' }),
      donations: [],
      userCreatedAt: USER_CREATED_AT,
    });
    expect(out.intendedAt).toBe('2024-01-01T00:00:00.000Z');
  });

  it('preserves existing intended amount when set on the assignment', () => {
    const out = deriveAssignmentV2({
      assignment: mkAssignment({ intended: 1200 }),
      donations: [],
      userCreatedAt: USER_CREATED_AT,
    });
    expect(out.intended).toBe(1200);
  });
});

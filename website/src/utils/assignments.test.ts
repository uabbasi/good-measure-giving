import { describe, it, expect } from 'vitest';
import { adjustAssignmentGiven } from './assignments';
import type { CharityBucketAssignment } from '../../types';

function assignment(overrides: Partial<CharityBucketAssignment> = {}): CharityBucketAssignment {
  return {
    charityEin: 'EIN1',
    bucketId: 'B1',
    status: 'sent',
    intended: 1000,
    given: 500,
    intendedAt: '2026-01-01T00:00:00.000Z',
    ...overrides,
  };
}

describe('adjustAssignmentGiven', () => {
  it('bumps the matching assignment by a positive delta (edit increased the amount)', () => {
    const next = adjustAssignmentGiven([assignment()], 'EIN1', 1000);
    expect(next[0].given).toBe(1500);
  });

  it('reduces the matching assignment by a negative delta (edit decreased the amount, or a delete)', () => {
    const next = adjustAssignmentGiven([assignment()], 'EIN1', -300);
    expect(next[0].given).toBe(200);
  });

  it('clamps at 0 instead of going negative', () => {
    const next = adjustAssignmentGiven([assignment({ given: 100 })], 'EIN1', -500);
    expect(next[0].given).toBe(0);
  });

  it('is a no-op (same array reference) when the ein matches no assignment', () => {
    const assignments = [assignment()];
    const next = adjustAssignmentGiven(assignments, 'OTHER-EIN', -100);
    expect(next).toBe(assignments);
  });

  it('is a no-op when ein is null/undefined (off-plan donation)', () => {
    const assignments = [assignment()];
    expect(adjustAssignmentGiven(assignments, null, 100)).toBe(assignments);
    expect(adjustAssignmentGiven(assignments, undefined, 100)).toBe(assignments);
  });

  it('is a no-op when delta is 0', () => {
    const assignments = [assignment()];
    expect(adjustAssignmentGiven(assignments, 'EIN1', 0)).toBe(assignments);
  });

  it('leaves sibling assignments untouched', () => {
    const sibling = assignment({ charityEin: 'EIN2', given: 42 });
    const next = adjustAssignmentGiven([assignment(), sibling], 'EIN1', 100);
    expect(next.find(a => a.charityEin === 'EIN2')).toEqual(sibling);
  });
});

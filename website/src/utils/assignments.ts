/**
 * Helpers for building v2 CharityBucketAssignment records.
 *
 * The v2 shape (added in Milestone 1) has status/intended/given + timestamps on
 * top of the legacy {charityEin, bucketId} pair. These helpers keep the shape
 * consistent across every write site (bookmark auto-categorize, starter plan,
 * add-to-giving, unified allocation view).
 */

import type { CharityBucketAssignment } from '../../types';

/** Build a fresh v2 assignment in the 'intended' state. */
export function makeIntendedAssignment(
  charityEin: string,
  bucketId: string,
  intended: number = 0,
): CharityBucketAssignment {
  return {
    charityEin,
    bucketId,
    status: 'intended',
    intended,
    given: 0,
    intendedAt: new Date().toISOString(),
  };
}

/**
 * Adjust a matching assignment's `given` by `delta` (positive or negative).
 * No-op (returns the same array reference) if `ein` is unset or matches no
 * assignment, so callers can chain calls and check reference equality to
 * decide whether a write is needed. Clamped at 0 so an out-of-order edit/
 * delete can't push the cached total negative.
 */
export function adjustAssignmentGiven(
  assignments: CharityBucketAssignment[],
  ein: string | null | undefined,
  delta: number,
): CharityBucketAssignment[] {
  if (!ein || delta === 0) return assignments;
  if (!assignments.some(a => a.charityEin === ein)) return assignments;
  return assignments.map(a =>
    a.charityEin === ein ? { ...a, given: Math.max(0, a.given + delta) } : a
  );
}

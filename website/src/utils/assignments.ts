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

/**
 * Pure derivation logic for migrate-assignments-v2.
 *
 * Kept isolated from the CLI entry point (which imports firebase-admin) so that
 * Vite/Vitest can statically analyze this module without needing node-only deps.
 */

export type AssignmentStatus = 'intended' | 'sent' | 'confirmed';

export interface LegacyAssignment {
  charityEin: string;
  bucketId: string;
  // v2 fields may or may not exist on legacy docs
  status?: AssignmentStatus;
  intended?: number;
  given?: number;
  intendedAt?: string;
  sentAt?: string;
  confirmedAt?: string;
}

export interface DerivedAssignment {
  charityEin: string;
  bucketId: string;
  status: AssignmentStatus;
  intended: number;
  given: number;
  intendedAt: string;
  sentAt?: string;
  confirmedAt?: string;
}

export interface DonationRecord {
  charityEin?: string | null;
  amount: number;
  receiptReceived?: boolean;
  createdAt?: string; // ISO
}

export interface DeriveInput {
  assignment: LegacyAssignment;
  donations: DonationRecord[];
  userCreatedAt: string; // ISO
}

/**
 * Derive the v2 fields for a single assignment from its existing state
 * plus the user's giving_history. Pure — no I/O.
 */
export function deriveAssignmentV2(input: DeriveInput): DerivedAssignment {
  const { assignment, donations, userCreatedAt } = input;
  const matching = donations.filter(d => d.charityEin === assignment.charityEin);

  const given = matching.reduce((sum, d) => sum + (Number(d.amount) || 0), 0);

  const confirmedMatches = matching.filter(d => d.receiptReceived === true);
  const hasConfirmed = confirmedMatches.length > 0;
  const hasAnySent = matching.length > 0;

  const status: AssignmentStatus = hasConfirmed
    ? 'confirmed'
    : hasAnySent
    ? 'sent'
    : 'intended';

  const intendedAt = assignment.intendedAt || userCreatedAt;

  // Latest matching donation timestamp = sentAt
  const sentAt = hasAnySent ? latestCreatedAt(matching) : undefined;
  const confirmedAt = hasConfirmed ? latestCreatedAt(confirmedMatches) : undefined;

  return {
    charityEin: assignment.charityEin,
    bucketId: assignment.bucketId,
    status,
    intended: typeof assignment.intended === 'number' ? assignment.intended : 0,
    given,
    intendedAt,
    sentAt: assignment.sentAt || sentAt,
    confirmedAt: assignment.confirmedAt || confirmedAt,
  };
}

function latestCreatedAt(records: DonationRecord[]): string | undefined {
  let latest: string | undefined;
  for (const r of records) {
    if (!r.createdAt) continue;
    if (!latest || r.createdAt > latest) latest = r.createdAt;
  }
  return latest;
}

/** Returns true if the assignment still needs to be migrated. */
export function needsMigration(a: LegacyAssignment): boolean {
  return !a.status;
}

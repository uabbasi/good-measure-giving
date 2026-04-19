/**
 * Migrate-Assignments-v2: backfill the extended CharityBucketAssignment shape.
 *
 * For each user doc in `users/{userId}`:
 *   1. Load `charityBucketAssignments` + `giving_history` subcollection
 *   2. For each assignment:
 *      - `given`       = sum of giving_history entries matching charityEin
 *      - `status`      = 'confirmed' if any matching donation has receiptReceived=true
 *                      else 'sent' if any donation exists
 *                      else 'intended'
 *      - `intendedAt`  = user's createdAt (fallback: now)
 *      - `sentAt`      = latest matching donation's createdAt (if any)
 *      - `confirmedAt` = latest matching donation with receiptReceived=true (if any)
 *   3. Atomic write via `writeBatch` (one per user)
 *
 * Idempotent: if `assignment.status` already exists, skip that user.
 *
 * Usage:
 *   npx tsx scripts/migrate-assignments-v2.ts --dry-run
 *   npx tsx scripts/migrate-assignments-v2.ts
 *
 * Requires GOOGLE_APPLICATION_CREDENTIALS or a service-account key.
 *
 * NOTE: The pure derivation logic lives in ./migrate-assignments-v2.logic.ts so
 * unit tests can import it without pulling in firebase-admin.
 */

import {
  deriveAssignmentV2,
  needsMigration,
  type LegacyAssignment,
  type DonationRecord,
} from './migrate-assignments-v2.logic';

// Hide the firebase-admin import from Vite's static analyzer AND from tsc
// (firebase-admin isn't a direct dep of this repo — the CLI expects it to be
// installed at runtime on the operator's machine). The pure derivation logic
// lives in `.logic.ts` so unit tests never go through this loader.
//
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FirebaseAdmin = any;
async function loadAdmin(): Promise<FirebaseAdmin> {
  const modName = 'firebase-admin';
  // eslint-disable-next-line @typescript-eslint/no-implied-eval, no-new-func
  const dynImport = new Function('m', 'return import(m)') as (m: string) => Promise<unknown>;
  return (await dynImport(modName)) as FirebaseAdmin;
}

async function runCli(): Promise<void> {
  const dryRun = process.argv.includes('--dry-run');
  const label = dryRun ? 'DRY RUN' : 'LIVE';
  console.log(`[migrate-assignments-v2] ${label} starting…`);

  const admin = await loadAdmin();

  if (admin.apps.length === 0) {
    admin.initializeApp({
      credential: admin.applicationDefault(),
    });
  }
  const db = admin.firestore();

  const usersSnap = await db.collection('users').get();
  console.log(`[migrate-assignments-v2] scanning ${usersSnap.size} users`);

  let touched = 0;
  let skipped = 0;
  let updatedAssignmentCount = 0;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  for (const userDoc of usersSnap.docs as any[]) {
    const userId = userDoc.id;
    const data = userDoc.data() || {};
    const assignments: LegacyAssignment[] = Array.isArray(data.charityBucketAssignments)
      ? data.charityBucketAssignments
      : [];

    if (assignments.length === 0) {
      skipped++;
      continue;
    }

    // Idempotency: if every assignment already has status, skip.
    if (assignments.every(a => !needsMigration(a))) {
      skipped++;
      continue;
    }

    const createdAt: string = data.createdAt && typeof data.createdAt.toDate === 'function'
      ? data.createdAt.toDate().toISOString()
      : typeof data.createdAt === 'string'
      ? data.createdAt
      : new Date().toISOString();

    const historySnap = await db
      .collection('users').doc(userId)
      .collection('giving_history')
      .get();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const donations: DonationRecord[] = historySnap.docs.map((d: any) => {
      const v = d.data() || {};
      return {
        charityEin: (v.charityEin as string) || null,
        amount: Number(v.amount) || 0,
        receiptReceived: v.receiptReceived === true,
        createdAt: v.createdAt && typeof v.createdAt.toDate === 'function'
          ? v.createdAt.toDate().toISOString()
          : typeof v.createdAt === 'string'
          ? v.createdAt
          : undefined,
      };
    });

    const nextAssignments = assignments.map(a =>
      needsMigration(a)
        ? deriveAssignmentV2({ assignment: a, donations, userCreatedAt: createdAt })
        : a,
    );

    const migratedCount = nextAssignments.filter((_, i) => needsMigration(assignments[i])).length;

    console.log(
      `[migrate-assignments-v2] user=${userId} assignments=${assignments.length} ` +
      `migrated=${migratedCount}`,
    );

    if (!dryRun) {
      const batch = db.batch();
      batch.update(userDoc.ref, { charityBucketAssignments: nextAssignments });
      await batch.commit();
    }

    touched++;
    updatedAssignmentCount += migratedCount;
  }

  console.log(
    `[migrate-assignments-v2] ${label} done. users_touched=${touched} skipped=${skipped} ` +
    `assignments_migrated=${updatedAssignmentCount}`,
  );
}

void runCli().catch(err => {
  console.error('[migrate-assignments-v2] fatal:', err);
  process.exit(1);
});

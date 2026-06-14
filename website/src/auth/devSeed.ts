/**
 * Dev/emulator-only seeding for the "Active Donor" quick-login test user.
 *
 * Firestore data in the emulator is ephemeral, so this runs on every login and
 * is made idempotent via a `__seeded` marker on the `users/{uid}` document:
 * if the marker is present we return early without writing anything.
 *
 * The shapes below mirror the REAL Firestore paths the app reads:
 *  - profile:        `users/{uid}` document  (see src/hooks/useProfile.ts)
 *  - bookmarks:      `users/{uid}/bookmarks/{ein}` subcollection (see useBookmarks.ts)
 *  - giving history: `users/{uid}/giving_history/{id}` subcollection (see useGivingHistory.ts)
 *
 * NOT for production: only called from the localhost/emulator quick-login pill.
 */

import { doc, collection, getDoc, setDoc, Timestamp } from 'firebase/firestore';
import { db } from './firebase';

// Real EINs that exist in the exported charity data so names resolve in the UI.
const EIN_INTERNATIONAL_AID = '46-3973114'; // International Aid Charity (known-good)
const EIN_ICNA_RELIEF = '04-3810161'; // ICNA Relief
const EIN_UNICEF = '13-1760110'; // UNICEF USA

const SEED_BUCKET_ID = 'seed-bucket-global-relief';
const SEED_BUCKET_ID_LOCAL = 'seed-bucket-local';

/**
 * Idempotently populate the "Active Donor" test user with realistic state:
 * a giving plan (buckets + assignments), bookmarks, logged donations, and
 * zakat/fiqh preferences. Safe to call repeatedly — a `__seeded` marker on the
 * user doc short-circuits subsequent runs.
 */
export async function seedActiveDonor(uid: string): Promise<void> {
  if (!db) return;

  const userRef = doc(db, 'users', uid);
  const snap = await getDoc(userRef);
  if (snap.exists() && (snap.data() as Record<string, unknown>).__seeded === true) {
    return; // already seeded this emulator session
  }

  const now = Timestamp.now();
  const nowIso = new Date().toISOString();
  const thisYear = new Date().getFullYear();

  // --- Profile: users/{uid} (merge so we don't clobber auto-created fields) ---
  // One assignment (UNICEF) is marked 'sent' to match a logged donation below.
  const charityBucketAssignments = [
    {
      charityEin: EIN_UNICEF,
      bucketId: SEED_BUCKET_ID,
      status: 'sent' as const,
      intended: 500,
      given: 250,
      intendedAt: nowIso,
      sentAt: nowIso,
    },
    {
      charityEin: EIN_INTERNATIONAL_AID,
      bucketId: SEED_BUCKET_ID,
      status: 'intended' as const,
      intended: 300,
      given: 0,
      intendedAt: nowIso,
    },
    {
      charityEin: EIN_ICNA_RELIEF,
      bucketId: SEED_BUCKET_ID_LOCAL,
      status: 'intended' as const,
      intended: 200,
      given: 0,
      intendedAt: nowIso,
    },
  ];

  await setDoc(
    userRef,
    {
      fiqhPreferences: {
        madhab: 'hanafi',
        zakatOnJewelry: true,
        zakatOnBusinessAssets: true,
        zakatOnStocks: 'market_value',
        zakatOnRental: false,
      },
      geographicPreferences: ['global', 'south-asia'],
      zakatAnniversary: `${thisYear}-04-01`,
      targetZakatAmount: 5000,
      givingBuckets: [
        {
          id: SEED_BUCKET_ID,
          name: 'Global Relief',
          tags: ['global', 'humanitarian'],
          percentage: 70,
        },
        {
          id: SEED_BUCKET_ID_LOCAL,
          name: 'Local Community',
          tags: ['domestic', 'community'],
          percentage: 30,
        },
      ],
      charityBucketAssignments,
      __seeded: true,
      updatedAt: now,
    },
    { merge: true },
  );

  // --- Bookmarks: users/{uid}/bookmarks/{ein} (doc id is the EIN) ---
  const bookmarks: Array<{ ein: string; name: string; notes: string | null }> = [
    { ein: EIN_INTERNATIONAL_AID, name: 'International Aid Charity', notes: 'High impact, considering for Ramadan.' },
    { ein: EIN_ICNA_RELIEF, name: 'ICNA Relief', notes: null },
    { ein: EIN_UNICEF, name: 'UNICEF USA', notes: null },
  ];
  for (const b of bookmarks) {
    await setDoc(doc(db, 'users', uid, 'bookmarks', b.ein), {
      charityEin: b.ein,
      charityName: b.name,
      notes: b.notes,
      createdAt: now,
    });
  }

  // --- Giving history: users/{uid}/giving_history/{id} ---
  // Deterministic ids so re-running before the marker is set stays idempotent.
  const donations: Array<{ id: string; data: Record<string, unknown> }> = [
    {
      id: 'seed-donation-unicef',
      data: {
        charityEin: EIN_UNICEF,
        charityName: 'UNICEF USA',
        amount: 250,
        date: `${thisYear}-04-15`,
        category: 'zakat',
        zakatYear: thisYear,
        paymentSource: 'Chase Credit Card',
        receiptReceived: true,
        taxDeductible: true,
        matchEligible: true,
        matchStatus: 'submitted',
        matchAmount: 250,
        notes: null,
        createdAt: now,
      },
    },
    {
      id: 'seed-donation-icna',
      data: {
        charityEin: EIN_ICNA_RELIEF,
        charityName: 'ICNA Relief',
        amount: 100,
        date: `${thisYear}-05-02`,
        category: 'sadaqah',
        zakatYear: null,
        paymentSource: 'Bank Transfer',
        receiptReceived: false,
        taxDeductible: true,
        matchEligible: false,
        matchStatus: null,
        matchAmount: null,
        notes: null,
        createdAt: now,
      },
    },
  ];
  for (const d of donations) {
    await setDoc(doc(collection(db, 'users', uid, 'giving_history'), d.id), d.data);
  }
}

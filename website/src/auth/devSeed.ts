/**
 * Dev/emulator-only seeding for the seeded quick-login test users
 * ("Active Donor" and "Zakat Donor").
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

export type SeededPersona = 'active-donor' | 'zakat-focused';

interface SeedPayload {
  /** Fields merged into the `users/{uid}` profile doc (without the `__seeded`/`updatedAt` marker). */
  profile: Record<string, unknown>;
  bookmarks: Array<{ ein: string; name: string; notes: string | null }>;
  donations: Array<{ id: string; data: Record<string, unknown> }>;
}

// Real EINs that exist in the exported charity data so names resolve in the UI.
const EIN_INTERNATIONAL_AID = '46-3973114'; // International Aid Charity (known-good)
const EIN_ICNA_RELIEF = '04-3810161'; // ICNA Relief (ZAKAT-ELIGIBLE)
const EIN_UNICEF = '13-1760110'; // UNICEF USA
// Zakat-eligible (wallet_tag ZAKAT-ELIGIBLE in the export) for the Zakat Donor.
const EIN_SAMS = '16-1717058'; // Syrian American Medical Society Foundation
const EIN_BAITULMAAL = '20-0942434'; // Baitulmaal, Inc.

/** Active Donor: a broad giving profile mixing zakat + sadaqah across global/local causes. */
function activeDonorPayload(now: Timestamp, nowIso: string, year: number): SeedPayload {
  const BUCKET_GLOBAL = 'seed-bucket-global-relief';
  const BUCKET_LOCAL = 'seed-bucket-local';
  return {
    profile: {
      fiqhPreferences: {
        madhab: 'hanafi',
        zakatOnJewelry: true,
        zakatOnBusinessAssets: true,
        zakatOnStocks: 'market_value',
        zakatOnRental: false,
      },
      geographicPreferences: ['global', 'south-asia'],
      zakatAnniversary: `${year}-04-01`,
      targetZakatAmount: 5000,
      givingBuckets: [
        { id: BUCKET_GLOBAL, name: 'Global Relief', tags: ['global', 'humanitarian'], percentage: 70 },
        { id: BUCKET_LOCAL, name: 'Local Community', tags: ['domestic', 'community'], percentage: 30 },
      ],
      charityBucketAssignments: [
        { charityEin: EIN_UNICEF, bucketId: BUCKET_GLOBAL, status: 'sent' as const, intended: 500, given: 250, intendedAt: nowIso, sentAt: nowIso },
        { charityEin: EIN_INTERNATIONAL_AID, bucketId: BUCKET_GLOBAL, status: 'intended' as const, intended: 300, given: 0, intendedAt: nowIso },
        { charityEin: EIN_ICNA_RELIEF, bucketId: BUCKET_LOCAL, status: 'intended' as const, intended: 200, given: 0, intendedAt: nowIso },
      ],
    },
    bookmarks: [
      { ein: EIN_INTERNATIONAL_AID, name: 'International Aid Charity', notes: 'High impact, considering for Ramadan.' },
      { ein: EIN_ICNA_RELIEF, name: 'ICNA Relief', notes: null },
      { ein: EIN_UNICEF, name: 'UNICEF USA', notes: null },
    ],
    donations: [
      {
        id: 'seed-donation-unicef',
        data: {
          charityEin: EIN_UNICEF, charityName: 'UNICEF USA', amount: 250, date: `${year}-04-15`,
          category: 'zakat', zakatYear: year, paymentSource: 'Chase Credit Card',
          receiptReceived: true, taxDeductible: true, matchEligible: true, matchStatus: 'submitted',
          matchAmount: 250, notes: null, createdAt: now,
        },
      },
      {
        id: 'seed-donation-icna',
        data: {
          charityEin: EIN_ICNA_RELIEF, charityName: 'ICNA Relief', amount: 100, date: `${year}-05-02`,
          category: 'sadaqah', zakatYear: null, paymentSource: 'Bank Transfer',
          receiptReceived: false, taxDeductible: true, matchEligible: false, matchStatus: null,
          matchAmount: null, notes: null, createdAt: now,
        },
      },
    ],
  };
}

/**
 * Zakat Donor: a purely zakat-driven profile — only ZAKAT-ELIGIBLE charities, a meaningful
 * zakat obligation + anniversary, all giving categorized as zakat, and full fiqh preferences.
 */
function zakatDonorPayload(now: Timestamp, nowIso: string, year: number): SeedPayload {
  const BUCKET_RELIEF = 'seed-bucket-zakat-relief';
  const BUCKET_MEDICAL = 'seed-bucket-zakat-medical';
  return {
    profile: {
      fiqhPreferences: {
        madhab: 'hanafi',
        zakatOnJewelry: true,
        zakatOnBusinessAssets: true,
        zakatOnStocks: 'market_value',
        zakatOnRental: true,
      },
      geographicPreferences: ['global', 'middle-east', 'south-asia'],
      zakatAnniversary: `${year}-03-15`,
      targetZakatAmount: 8000,
      givingBuckets: [
        { id: BUCKET_RELIEF, name: 'Zakat — Relief', tags: ['zakat', 'humanitarian'], percentage: 60 },
        { id: BUCKET_MEDICAL, name: 'Zakat — Medical', tags: ['zakat', 'health'], percentage: 40 },
      ],
      charityBucketAssignments: [
        { charityEin: EIN_BAITULMAAL, bucketId: BUCKET_RELIEF, status: 'sent' as const, intended: 4000, given: 4000, intendedAt: nowIso, sentAt: nowIso },
        { charityEin: EIN_ICNA_RELIEF, bucketId: BUCKET_RELIEF, status: 'intended' as const, intended: 800, given: 0, intendedAt: nowIso },
        { charityEin: EIN_SAMS, bucketId: BUCKET_MEDICAL, status: 'intended' as const, intended: 3200, given: 0, intendedAt: nowIso },
      ],
    },
    bookmarks: [
      { ein: EIN_BAITULMAAL, name: 'Baitulmaal, Inc.', notes: 'Zakat-eligible; fulfilling this year obligation.' },
      { ein: EIN_SAMS, name: 'Syrian American Medical Society Foundation', notes: null },
      { ein: EIN_ICNA_RELIEF, name: 'ICNA Relief', notes: null },
    ],
    donations: [
      {
        id: 'seed-donation-baitulmaal',
        data: {
          charityEin: EIN_BAITULMAAL, charityName: 'Baitulmaal, Inc.', amount: 4000, date: `${year}-03-20`,
          category: 'zakat', zakatYear: year, paymentSource: 'Bank Transfer',
          receiptReceived: true, taxDeductible: true, matchEligible: false, matchStatus: null,
          matchAmount: null, notes: 'Annual zakat — relief.', createdAt: now,
        },
      },
      {
        id: 'seed-donation-sams',
        data: {
          charityEin: EIN_SAMS, charityName: 'Syrian American Medical Society Foundation', amount: 1500, date: `${year}-03-22`,
          category: 'zakat', zakatYear: year, paymentSource: 'Chase Credit Card',
          receiptReceived: true, taxDeductible: true, matchEligible: true, matchStatus: 'submitted',
          matchAmount: 1500, notes: 'Zakat — medical relief.', createdAt: now,
        },
      },
    ],
  };
}

const PAYLOADS: Record<SeededPersona, (now: Timestamp, nowIso: string, year: number) => SeedPayload> = {
  'active-donor': activeDonorPayload,
  'zakat-focused': zakatDonorPayload,
};

/**
 * Idempotently populate a seeded test user (`active-donor` or `zakat-focused`) with realistic
 * Firestore state: a giving plan (buckets + assignments), bookmarks, logged donations, and
 * zakat/fiqh preferences. Safe to call repeatedly — a `__seeded` marker on the user doc
 * short-circuits subsequent runs.
 */
export async function seedTestUser(uid: string, persona: SeededPersona): Promise<void> {
  if (!db) return;

  const userRef = doc(db, 'users', uid);
  const snap = await getDoc(userRef);
  if (snap.exists() && (snap.data() as Record<string, unknown>).__seeded === true) {
    return; // already seeded this emulator session
  }

  const now = Timestamp.now();
  const nowIso = new Date().toISOString();
  const thisYear = new Date().getFullYear();
  const payload = PAYLOADS[persona](now, nowIso, thisYear);

  // --- Profile: users/{uid} (merge so we don't clobber auto-created fields) ---
  await setDoc(userRef, { ...payload.profile, __seeded: true, updatedAt: now }, { merge: true });

  // --- Bookmarks: users/{uid}/bookmarks/{ein} (doc id is the EIN) ---
  for (const b of payload.bookmarks) {
    await setDoc(doc(db, 'users', uid, 'bookmarks', b.ein), {
      charityEin: b.ein,
      charityName: b.name,
      notes: b.notes,
      createdAt: now,
    });
  }

  // --- Giving history: users/{uid}/giving_history/{id} (deterministic ids → idempotent) ---
  for (const d of payload.donations) {
    await setDoc(doc(collection(db, 'users', uid, 'giving_history'), d.id), d.data);
  }
}

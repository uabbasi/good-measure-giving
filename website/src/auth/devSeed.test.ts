import { describe, it, expect, vi, beforeEach } from 'vitest';

const setDoc = vi.fn(async (..._a: unknown[]) => {});
const getDoc = vi.fn();
vi.mock('firebase/firestore', () => ({
  doc: vi.fn((...a: unknown[]) => ({ _ref: a })),
  collection: vi.fn((...a: unknown[]) => ({ _col: a })),
  setDoc: (...a: unknown[]) => setDoc(...a),
  getDoc: (...a: unknown[]) => getDoc(...a),
  serverTimestamp: () => 'TS',
  Timestamp: { fromDate: (d: Date) => ({ _d: d }), now: () => ({ _now: true }) },
}));
vi.mock('./firebase', () => ({ db: { _fake: true } }));

import { seedActiveDonor } from './devSeed';

beforeEach(() => { setDoc.mockClear(); getDoc.mockReset(); });

describe('seedActiveDonor', () => {
  it('writes seed data when the user is not yet seeded', async () => {
    getDoc.mockResolvedValue({ exists: () => true, data: () => ({}) });
    await seedActiveDonor('uid-1');
    expect(setDoc).toHaveBeenCalled();
  });
  it('is idempotent — does nothing when already seeded', async () => {
    getDoc.mockResolvedValue({ exists: () => true, data: () => ({ __seeded: true }) });
    await seedActiveDonor('uid-1');
    expect(setDoc).not.toHaveBeenCalled();
  });
});

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

import { seedTestUser } from './devSeed';

beforeEach(() => { setDoc.mockClear(); getDoc.mockReset(); });

// Pull the data object from every setDoc(ref, data) call.
const writtenData = () => setDoc.mock.calls.map((c) => c[1] as Record<string, unknown>);

describe('seedTestUser', () => {
  it('writes seed data for the active donor when not yet seeded', async () => {
    getDoc.mockResolvedValue({ exists: () => true, data: () => ({}) });
    await seedTestUser('uid-1', 'active-donor');
    expect(setDoc).toHaveBeenCalled();
  });

  it('writes seed data for the zakat donor when not yet seeded', async () => {
    getDoc.mockResolvedValue({ exists: () => true, data: () => ({}) });
    await seedTestUser('uid-2', 'zakat-focused');
    expect(setDoc).toHaveBeenCalled();
  });

  it('seeds the zakat donor with all-zakat giving (no sadaqah)', async () => {
    getDoc.mockResolvedValue({ exists: () => true, data: () => ({}) });
    await seedTestUser('uid-3', 'zakat-focused');
    const categories = writtenData()
      .map((d) => d.category)
      .filter((c): c is string => typeof c === 'string');
    expect(categories.length).toBeGreaterThan(0);
    expect(categories.every((c) => c === 'zakat')).toBe(true);
    expect(categories).not.toContain('sadaqah');
  });

  it('is idempotent — does nothing when already seeded', async () => {
    getDoc.mockResolvedValue({ exists: () => true, data: () => ({ __seeded: true }) });
    await seedTestUser('uid-1', 'active-donor');
    expect(setDoc).not.toHaveBeenCalled();
  });
});

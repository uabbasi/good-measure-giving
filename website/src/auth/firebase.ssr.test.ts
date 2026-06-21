// @vitest-environment node
// Regression guard: importing firebase.ts under Node must not throw and must
// yield auth === null and db === null (no window → canInit is false).
// Note: this test is green-on-arrival after the canInit guard is in place;
// it exists to prevent regressions where firebase init is added unconditionally.

import { describe, it, expect, vi } from 'vitest';

// Mock firebase/app and firebase/auth + firebase/firestore so that if the
// guard were ever removed, the spy would catch initializeApp being called.
vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({ name: 'mock-app' })),
}));
vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  connectAuthEmulator: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock('firebase/firestore', () => ({
  getFirestore: vi.fn(() => ({})),
  connectFirestoreEmulator: vi.fn(),
}));

describe('firebase module under Node (no window)', () => {
  it('exports auth and db as null when window is undefined', async () => {
    // Confirm no window in this node environment
    expect(typeof window).toBe('undefined');

    const { auth, db } = await import('./firebase');

    expect(auth).toBeNull();
    expect(db).toBeNull();
  });

  it('does not call initializeApp when window is undefined', async () => {
    const { initializeApp } = await import('firebase/app');
    expect(initializeApp).not.toHaveBeenCalled();
  });
});

/**
 * Firebase configuration and initialization.
 *
 * Local testing: set `VITE_USE_FIREBASE_EMULATOR=true` to point auth + firestore
 * at the local Firebase Emulator Suite (auth :9099, firestore :8080). In that
 * mode a demo project config is used, the emulators are connected, and a
 * `window.__TEST_AUTH__` seam is exposed so e2e tests can sign in test users
 * with email/password (the production app uses popup sign-in only). This seam
 * is IMPOSSIBLE in production: the env flag is never set in prod builds.
 */

import { initializeApp } from 'firebase/app';
import {
  getAuth,
  connectAuthEmulator,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth';
import { getFirestore, connectFirestoreEmulator } from 'firebase/firestore';

const useEmulator = import.meta.env.VITE_USE_FIREBASE_EMULATOR === 'true';

const config = useEmulator
  ? { apiKey: 'demo-api-key', projectId: 'good-measure-giving', authDomain: 'localhost' }
  : {
      apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
      authDomain:
        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ||
        `${import.meta.env.VITE_FIREBASE_PROJECT_ID}.firebaseapp.com`,
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
      storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
      appId: import.meta.env.VITE_FIREBASE_APP_ID,
    };

const isConfigured = !!(config.apiKey && config.projectId);
const app = isConfigured ? initializeApp(config) : null;
export const auth = app ? getAuth(app) : null;
export const db = app ? getFirestore(app) : null;
export { isConfigured };

if (useEmulator && auth && db) {
  // Host defaults to localhost; set VITE_EMULATOR_HOST to the laptop's LAN IP
  // (e.g. 192.168.1.50) to dogfood across devices on the same WiFi.
  const host = import.meta.env.VITE_EMULATOR_HOST || 'localhost';
  // Connect to the emulator suite (idempotent guards via try/catch).
  try {
    connectAuthEmulator(auth, `http://${host}:9099`, { disableWarnings: true });
  } catch {
    /* already connected */
  }
  try {
    connectFirestoreEmulator(db, host, 8080);
  } catch {
    /* already connected */
  }
  // Test seam for Playwright — email/password against the auth emulator.
  // Gated behind the emulator flag; never present in production builds.
  (window as unknown as { __TEST_AUTH__?: unknown }).__TEST_AUTH__ = {
    async signUp(email: string, password: string) {
      try {
        await createUserWithEmailAndPassword(auth, email, password);
      } catch {
        await signInWithEmailAndPassword(auth, email, password);
      }
    },
    async signIn(email: string, password: string) {
      await signInWithEmailAndPassword(auth, email, password);
    },
    async signOutTest() {
      await signOut(auth);
    },
  };
}

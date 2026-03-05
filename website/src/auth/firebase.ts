/**
 * Firebase configuration and initialization
 */

import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: (() => {
    const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
    const requestedAuthDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN;
    const defaultAuthDomain = projectId ? `${projectId}.firebaseapp.com` : undefined;
    const useCustomAuthDomainProxy = import.meta.env.VITE_FIREBASE_USE_CUSTOM_AUTH_DOMAIN === 'true';

    // Custom auth domains require /__/auth/* proxying in the active deploy target.
    // Fall back to Firebase-hosted auth unless explicitly opted in.
    if (!requestedAuthDomain) return defaultAuthDomain;
    if (requestedAuthDomain.endsWith('.firebaseapp.com')) return requestedAuthDomain;
    if (useCustomAuthDomainProxy) return requestedAuthDomain;
    return defaultAuthDomain ?? requestedAuthDomain;
  })(),
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

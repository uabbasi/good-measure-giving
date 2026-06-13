export const devLoginEnabled = (): boolean =>
  import.meta.env.DEV
  && import.meta.env.VITE_USE_FIREBASE_EMULATOR === 'true'
  && typeof window !== 'undefined'
  && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

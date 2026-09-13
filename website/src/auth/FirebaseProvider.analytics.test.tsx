import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { getRedirectResult, onAuthStateChanged } from 'firebase/auth';
import { FirebaseProvider } from './FirebaseProvider';
import { trackSignInSuccess } from '../utils/analytics';

vi.mock('./firebase', () => ({ auth: {}, db: null, isConfigured: true }));
vi.mock('firebase/auth', () => ({ getRedirectResult: vi.fn(), onAuthStateChanged: vi.fn() }));
vi.mock('../utils/analytics', () => ({ trackSignInSuccess: vi.fn(), trackSignInError: vi.fn() }));
vi.mock('../hooks/useRichAccess', () => ({ clearViewedEins: vi.fn() }));

const user = { uid: 'existing-user', displayName: 'Test', providerData: [{ providerId: 'google.com' }], metadata: { creationTime: '2026-01-01' } };
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getRedirectResult).mockResolvedValue(null);
  vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback: any) => {
    callback(user);
    return () => {};
  });
});
afterEach(cleanup);

it('does not count a restored Firebase session as a sign-in', async () => {
  render(<FirebaseProvider>Page</FirebaseProvider>);
  await waitFor(() => expect(getRedirectResult).toHaveBeenCalled());
  expect(trackSignInSuccess).not.toHaveBeenCalled();
});

it('counts a completed redirect once, separately from session restoration', async () => {
  const result = { user, providerId: 'google.com' } as any;
  vi.mocked(getRedirectResult).mockResolvedValue(result);
  render(<FirebaseProvider>Page</FirebaseProvider>);
  await waitFor(() => expect(trackSignInSuccess).toHaveBeenCalledExactlyOnceWith(result));
});

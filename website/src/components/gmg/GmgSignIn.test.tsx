import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { GmgSignIn } from './GmgSignIn';
import { signInWithPopup } from 'firebase/auth';
import { gmgPalette } from './tokens';

vi.mock('../../auth/firebase', () => ({ auth: {}, isConfigured: true }));
vi.mock('../../utils/analytics', () => ({ trackSignIn: vi.fn(), trackSignInError: vi.fn() }));
vi.mock('firebase/auth', () => ({
  GoogleAuthProvider: vi.fn(),
  OAuthProvider: class {
    addScope = vi.fn();
  },
  signInWithPopup: vi.fn(),
  signInWithRedirect: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  updateProfile: vi.fn(),
}));

const p = gmgPalette(false);

beforeEach(() => {
  (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockReset();
});

// Regression: signInWithGoogle/signInWithApple resolved successfully but
// never called close(), unlike the email flow. The modal only *looked* shut
// because the parent's isSignedIn-gated conditional unmounted it — the
// `open` state it was passed stayed true, so the same stale-open modal
// reappeared the next time that parent branch remounted (e.g. right after
// sign-out). See GmgChromeFrame's gateSignInOpen for the real-world case.
describe('GmgSignIn — popup sign-in closes the modal', () => {
  it('closes after a successful Google popup sign-in', async () => {
    (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { displayName: 'Test User' },
    });
    const onClose = vi.fn();
    render(<GmgSignIn p={p} open={true} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: /Continue with Google/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('closes after a successful Apple popup sign-in, even when the user needs a name', async () => {
    (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { displayName: null },
    });
    const onClose = vi.fn();
    render(<GmgSignIn p={p} open={true} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: /Continue with Apple/i }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('does NOT close when the popup sign-in fails', async () => {
    (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockRejectedValue({ code: 'auth/network-request-failed' });
    const onClose = vi.fn();
    render(<GmgSignIn p={p} open={true} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: /Continue with Google/i }));

    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(onClose).not.toHaveBeenCalled();
  });
});

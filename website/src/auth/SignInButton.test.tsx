import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SignInButton } from './SignInButton';
import { signInWithPopup } from 'firebase/auth';

vi.mock('./firebase', () => ({ auth: {}, isConfigured: true }));
vi.mock('./useAuth', () => ({ useAuth: () => ({ isSignedIn: false, firstName: null }) }));
vi.mock('../utils/analytics', () => ({ trackSignIn: vi.fn(), trackSignInError: vi.fn() }));
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
  signOut: vi.fn(),
}));

beforeEach(() => {
  (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockReset();
});

// Regression: same bug as GmgSignIn.test.tsx (see the comment there) — this
// is the other component with the identical signInWithGoogle/signInWithApple
// pair that never called closeModal() on success, so `showMenu` stayed true
// across a later sign-out and the modal reappeared unprompted. SignInButton
// is the more widely used of the two (compare, gated blocks, mobile nav),
// so it carried the same bug independently.
describe('SignInButton — popup sign-in closes the modal', () => {
  it('closes after a successful Google popup sign-in', async () => {
    (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { displayName: 'Test User' },
    });
    render(<SignInButton />);

    fireEvent.click(screen.getByRole('button', { name: /See Full Evaluations/i }));
    fireEvent.click(screen.getByRole('button', { name: /Continue with Google/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('closes after a successful Apple popup sign-in, even when the user needs a name', async () => {
    (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { displayName: null },
    });
    render(<SignInButton />);

    fireEvent.click(screen.getByRole('button', { name: /See Full Evaluations/i }));
    fireEvent.click(screen.getByRole('button', { name: /Continue with Apple/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('does NOT close when the popup sign-in fails', async () => {
    (signInWithPopup as unknown as ReturnType<typeof vi.fn>).mockRejectedValue({ code: 'auth/network-request-failed' });
    render(<SignInButton />);

    fireEvent.click(screen.getByRole('button', { name: /See Full Evaluations/i }));
    fireEvent.click(screen.getByRole('button', { name: /Continue with Google/i }));

    await waitFor(() => expect(screen.getByText(/Something went wrong/i)).toBeTruthy());
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});

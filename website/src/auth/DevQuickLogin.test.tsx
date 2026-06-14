import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DevQuickLogin } from './DevQuickLogin';
import { seedTestUser } from './devSeed';
import { updateProfile } from 'firebase/auth';

let mockEnabled = false;
let mockAuth: { isSignedIn: boolean; isLoaded: boolean; email: string | null } = {
  isSignedIn: false, isLoaded: true, email: null,
};
let mockCurrentUser: { uid: string; displayName: string | null } | null = null;

vi.mock('./devLoginEnabled', () => ({ devLoginEnabled: () => mockEnabled }));
vi.mock('./useAuth', () => ({ useAuth: () => mockAuth }));
vi.mock('./firebase', () => ({ get auth() { return { currentUser: mockCurrentUser }; } }));
vi.mock('./devSeed', () => ({ seedTestUser: vi.fn(async () => {}) }));
vi.mock('firebase/auth', () => ({ updateProfile: vi.fn(async () => {}) }));

const signUp = vi.fn(async () => {});
const signIn = vi.fn(async () => {});
const signOutTest = vi.fn(async () => {});

beforeEach(() => {
  mockEnabled = true;
  mockAuth = { isSignedIn: false, isLoaded: true, email: null };
  mockCurrentUser = { uid: 'test-uid', displayName: null };
  signUp.mockClear();
  signIn.mockReset();
  signIn.mockResolvedValue(undefined);
  signOutTest.mockClear();
  (seedTestUser as unknown as ReturnType<typeof vi.fn>).mockClear();
  (updateProfile as unknown as ReturnType<typeof vi.fn>).mockClear();
  (window as unknown as { __TEST_AUTH__?: unknown }).__TEST_AUTH__ = { signUp, signIn, signOutTest };
  try { localStorage.clear(); } catch { /* jsdom */ }
});

afterEach(() => {
  mockEnabled = false;
  delete (window as unknown as { __TEST_AUTH__?: unknown }).__TEST_AUTH__;
});

describe('DevQuickLogin — rendering', () => {
  it('renders nothing when the gate is off', () => {
    mockEnabled = false;
    const { container } = render(<DevQuickLogin />);
    expect(container.firstChild).toBeNull();
  });

  it('renders all three persona buttons when the gate is on', () => {
    render(<DevQuickLogin />);
    expect(screen.getByText(/Fresh User/)).toBeTruthy();
    expect(screen.getByText(/Active Donor/)).toBeTruthy();
    expect(screen.getByText(/Zakat Donor/)).toBeTruthy();
  });
});

describe('DevQuickLogin — login behavior', () => {
  it('signs in (fast path, no create) and seeds a seeded persona (Zakat Donor)', async () => {
    render(<DevQuickLogin />);
    fireEvent.click(screen.getByText(/Login: Zakat Donor/));
    await waitFor(() => expect(signIn).toHaveBeenCalledWith('zakat@test.local', 'test1234'));
    await waitFor(() => expect(seedTestUser).toHaveBeenCalledWith('test-uid', 'zakat-focused'));
    expect(signUp).not.toHaveBeenCalled(); // sign-in succeeded → no 400-producing create
    // displayName was null on the fake user → it gets set
    expect(updateProfile).toHaveBeenCalled();
  });

  it('falls back to create when the user does not exist yet', async () => {
    signIn.mockRejectedValueOnce(new Error('auth/user-not-found'));
    render(<DevQuickLogin />);
    fireEvent.click(screen.getByText(/Login: Active Donor/));
    await waitFor(() => expect(signUp).toHaveBeenCalledWith('donor@test.local', 'test1234'));
    await waitFor(() => expect(seedTestUser).toHaveBeenCalledWith('test-uid', 'active-donor'));
  });

  it('does NOT seed the Fresh User (seed: false)', async () => {
    render(<DevQuickLogin />);
    fireEvent.click(screen.getByText(/Login: Fresh User/));
    await waitFor(() => expect(signIn).toHaveBeenCalledWith('fresh@test.local', 'test1234'));
    expect(seedTestUser).not.toHaveBeenCalled();
  });

  it('shows an error when the emulator test-auth seam is missing', async () => {
    delete (window as unknown as { __TEST_AUTH__?: unknown }).__TEST_AUTH__;
    render(<DevQuickLogin />);
    fireEvent.click(screen.getByText(/Login: Active Donor/));
    await waitFor(() => expect(screen.getByText(/test-auth seam not available/i)).toBeTruthy());
    expect(signUp).not.toHaveBeenCalled();
  });
});

describe('DevQuickLogin — signed-in state', () => {
  it('shows the email + Sign out, and signs out on click', async () => {
    mockAuth = { isSignedIn: true, isLoaded: true, email: 'zakat@test.local' };
    render(<DevQuickLogin />);
    expect(screen.getByText(/zakat@test.local/)).toBeTruthy();
    const signOutBtn = screen.getByRole('button', { name: /sign out/i });
    fireEvent.click(signOutBtn);
    await waitFor(() => expect(signOutTest).toHaveBeenCalled());
  });
});

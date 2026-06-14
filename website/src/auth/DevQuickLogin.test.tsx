import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { DevQuickLogin } from './DevQuickLogin';

let mockEnabled = false;
vi.mock('./devLoginEnabled', () => ({ devLoginEnabled: () => mockEnabled }));
vi.mock('./useAuth', () => ({ useAuth: () => ({ isSignedIn: false, isLoaded: true, email: null, uid: null }) }));
vi.mock('./firebase', () => ({ auth: { currentUser: null } }));
vi.mock('./devSeed', () => ({ seedActiveDonor: vi.fn() }));

afterEach(() => { mockEnabled = false; });

describe('DevQuickLogin', () => {
  it('renders nothing when the gate is off', () => {
    mockEnabled = false;
    const { container } = render(<DevQuickLogin />);
    expect(container.firstChild).toBeNull();
  });
  it('renders persona buttons when the gate is on', () => {
    mockEnabled = true;
    const { getByText } = render(<DevQuickLogin />);
    expect(getByText(/Fresh User/)).toBeTruthy();
    expect(getByText(/Active Donor/)).toBeTruthy();
  });
});

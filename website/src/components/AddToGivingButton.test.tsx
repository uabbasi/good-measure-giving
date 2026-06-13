/**
 * AddToGivingButton — add-only, with add-side family sync.
 *
 * Covers:
 *  - no family plan: adds to the personal plan only
 *  - family plan present: adding also mirrors into the family plan(s)
 *  - never destructive: once in the plan it's a disabled confirmation (no remove)
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../contexts/LandingThemeContext', () => ({
  useLandingTheme: () => ({ isDark: false }),
}));

let signedIn = true;
vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ isSignedIn: signedIn }),
}));

vi.mock('../contexts/UserFeaturesContext', () => ({
  useProfileState: () => ({
    profile: { targetZakatAmount: 1000, charityBucketAssignments: [] },
    updateProfile: vi.fn(),
  }),
}));

vi.mock('./giving/ZakatEstimator', () => ({ ZakatEstimator: () => null }));

const addToGiving = vi.fn(async () => {});
let inPlan = false;
vi.mock('../hooks/useAddToGiving', () => ({
  useAddToGiving: () => ({
    addToGiving,
    isInPlan: () => inPlan,
    saving: false,
  }),
}));

const addCharityToAllPlans = vi.fn(async () => {});
let hasPlans = false;
vi.mock('../hooks/useSharedPlans', () => ({
  useSharedPlans: () => ({
    hasPlans,
    addCharityToAllPlans,
  }),
}));

import { AddToGivingButton } from './AddToGivingButton';

beforeEach(() => {
  signedIn = true;
  inPlan = false;
  hasPlans = false;
  addToGiving.mockClear();
  addCharityToAllPlans.mockClear();
});

describe('AddToGivingButton (add-only + family sync)', () => {
  it('no family plan: adds to personal only', async () => {
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(addToGiving).toHaveBeenCalledWith('13-5660870', 'Acme'));
    expect(addCharityToAllPlans).not.toHaveBeenCalled();
  });

  it('family plan present: adding also mirrors into the family plan(s)', async () => {
    hasPlans = true;
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(addToGiving).toHaveBeenCalledWith('13-5660870', 'Acme'));
    await waitFor(() => expect(addCharityToAllPlans).toHaveBeenCalledWith('13-5660870'));
  });

  it('in plan: button is a disabled confirmation — never removes (with a family plan)', () => {
    hasPlans = true;
    inPlan = true;
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
  });

  it('in plan: button is a disabled confirmation — never removes (no family plan)', () => {
    inPlan = true;
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
  });
});

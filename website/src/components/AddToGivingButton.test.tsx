/**
 * AddToGivingButton — the unified personal+family sync toggle.
 *
 * Covers the sync semantics:
 *  - no family plan: add-only, "in plan" is a disabled confirmation (legacy)
 *  - family plan present: adding writes to BOTH; clicking again removes from BOTH
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
const removeFromGiving = vi.fn(async () => {});
let inPlan = false;
vi.mock('../hooks/useAddToGiving', () => ({
  useAddToGiving: () => ({
    addToGiving,
    removeFromGiving,
    isInPlan: () => inPlan,
    saving: false,
  }),
}));

const addCharityToAllPlans = vi.fn(async () => {});
const removeCharityFromAllPlans = vi.fn(async () => {});
let hasPlans = false;
vi.mock('../hooks/useSharedPlans', () => ({
  useSharedPlans: () => ({
    hasPlans,
    addCharityToAllPlans,
    removeCharityFromAllPlans,
  }),
}));

import { AddToGivingButton } from './AddToGivingButton';

beforeEach(() => {
  signedIn = true;
  inPlan = false;
  hasPlans = false;
  addToGiving.mockClear();
  removeFromGiving.mockClear();
  addCharityToAllPlans.mockClear();
  removeCharityFromAllPlans.mockClear();
});

describe('AddToGivingButton sync toggle', () => {
  it('no family plan: adds to personal only', async () => {
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(addToGiving).toHaveBeenCalledWith('13-5660870', 'Acme'));
    expect(addCharityToAllPlans).not.toHaveBeenCalled();
  });

  it('family plan present: adding writes to both personal and family', async () => {
    hasPlans = true;
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(addToGiving).toHaveBeenCalledWith('13-5660870', 'Acme'));
    await waitFor(() => expect(addCharityToAllPlans).toHaveBeenCalledWith('13-5660870'));
  });

  it('family plan present + in plan: clicking removes from both', async () => {
    hasPlans = true;
    inPlan = true;
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    const btn = screen.getByRole('button') as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    fireEvent.click(btn);
    await waitFor(() => expect(removeFromGiving).toHaveBeenCalledWith('13-5660870'));
    await waitFor(() => expect(removeCharityFromAllPlans).toHaveBeenCalledWith('13-5660870'));
  });

  it('no family plan + in plan: confirmation is disabled (no removal)', () => {
    inPlan = true;
    render(<AddToGivingButton charityEin="13-5660870" charityName="Acme" />);
    expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
  });
});

/**
 * AddToFamilyPlanButton — the "Add to family plan" bridge.
 *
 * Covers the three render modes:
 *  - no shared plans          → renders nothing
 *  - exactly one shared plan  → a direct "Add to {name}" button that calls addCharityToPlan
 *  - two or more shared plans → a menu to pick which plan
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../../contexts/LandingThemeContext', () => ({
  useLandingTheme: () => ({ isDark: false }),
}));

const addCharityToPlan = vi.fn(async () => 'added' as const);
let mockPlans: { id: string; name: string }[] = [];

vi.mock('../../hooks/useSharedPlans', () => ({
  useSharedPlans: () => ({
    plans: mockPlans,
    isLoading: false,
    createPlan: vi.fn(),
    addCharityToPlan,
  }),
}));

import { AddToFamilyPlanButton } from './AddToFamilyPlanButton';

beforeEach(() => {
  addCharityToPlan.mockClear();
  mockPlans = [];
});

describe('AddToFamilyPlanButton', () => {
  it('renders nothing when the user has no shared plans', () => {
    const { container } = render(<AddToFamilyPlanButton charityEin="13-5660870" charityName="Acme" />);
    expect(container.childElementCount).toBe(0);
  });

  it('one plan → adds directly and shows confirmation', async () => {
    mockPlans = [{ id: 'p1', name: 'Khan Family' }];
    render(<AddToFamilyPlanButton charityEin="13-5660870" charityName="Acme" />);

    const btn = screen.getByRole('button', { name: /add acme to khan family/i });
    fireEvent.click(btn);

    await waitFor(() => expect(addCharityToPlan).toHaveBeenCalledWith('p1', '13-5660870'));
    // Confirmation text is split across nodes ("Added to " / "Khan Family" / "✓").
    await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/added to khan family/i));
  });

  it('two plans → opens a menu and adds to the chosen plan', async () => {
    mockPlans = [
      { id: 'p1', name: 'Khan Family' },
      { id: 'p2', name: 'Masjid Circle' },
    ];
    render(<AddToFamilyPlanButton charityEin="13-5660870" charityName="Acme" />);

    fireEvent.click(screen.getByRole('button', { name: /add acme to a family plan/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: /masjid circle/i }));

    await waitFor(() => expect(addCharityToPlan).toHaveBeenCalledWith('p2', '13-5660870'));
  });
});

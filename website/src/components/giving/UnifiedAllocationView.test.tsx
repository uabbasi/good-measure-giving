/**
 * Smoke tests for UnifiedAllocationView (M4).
 *
 * Renders the component with mocked hooks + deps and asserts:
 *  - Empty state renders for a fresh profile (no target, no bookmarks).
 *  - A single intended charity renders with the "Planned" status chip.
 *  - Status chip + action button reflect status transitions.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// --- Deep mocks -----------------------------------------------------------
vi.mock('../../../contexts/LandingThemeContext', () => ({
  useLandingTheme: () => ({ isDark: false }),
}));

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: [], loading: false, summaries: [] }),
}));

vi.mock('../../featureFlags', () => ({
  SHOW_AMAL_SCORE: false,
}));

vi.mock('./StarterPlan', () => ({
  StarterPlan: () => <div data-testid="mock-starter-plan" />,
}));

vi.mock('./ZakatEstimator', () => ({
  ZakatEstimator: () => null,
}));

import { UnifiedAllocationView } from './UnifiedAllocationView';

function renderView(props: Partial<Parameters<typeof UnifiedAllocationView>[0]>) {
  const defaultProps: Parameters<typeof UnifiedAllocationView>[0] = {
    initialBuckets: [],
    initialAssignments: [],
    targetAmount: null,
    bookmarkedCharities: [],
    donations: [],
    onSave: vi.fn(async () => {}),
    onLogDonation: vi.fn(),
    onAddCharity: vi.fn(async () => {}),
    onRemoveCharity: vi.fn(async () => {}),
    onSetCharityIntended: vi.fn(async () => {}),
    onMarkConfirmed: vi.fn(async () => {}),
    allCharities: [],
    zakatAnniversary: '2026-01-01',
    onSaveAnniversary: vi.fn(async () => {}),
  };
  return render(
    <MemoryRouter>
      <UnifiedAllocationView {...defaultProps} {...props} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  if (!globalThis.crypto) {
    // @ts-expect-error - polyfill for test env
    globalThis.crypto = {};
  }
  let counter = 0;
  // @ts-expect-error - deterministic UUID for tests
  globalThis.crypto.randomUUID = () => `uuid-${++counter}`;
});

describe('<UnifiedAllocationView /> — smoke', () => {
  it('renders the "Set your zakat target" empty state with no target + no bookmarks', () => {
    renderView({});
    expect(screen.getByText(/Set your zakat target/i)).toBeTruthy();
  });

  it('renders the "Planned" chip for an intended charity', () => {
    renderView({
      targetAmount: 1000,
      initialBuckets: [{ id: 'b1', name: 'Global', tags: ['global'], percentage: 0, color: '#5ba88a' }],
      initialAssignments: [{
        ein: 'E1', bucketId: 'b1', status: 'intended', intended: 500, given: 0,
      }],
      bookmarkedCharities: [{
        ein: 'E1', name: 'Alpha Relief', amalScore: null, walletTag: null,
        causeTags: ['global'],
      }],
    });
    const chip = screen.getAllByTestId('record-status-E1')[0];
    expect(chip.textContent).toMatch(/Planned/i);
    // Action button: "Log donation" for intended.
    expect(screen.getAllByTestId('record-log-E1').length).toBeGreaterThan(0);
  });

  it('renders the "Sent" chip + "Mark confirmed" button for a sent assignment', () => {
    renderView({
      targetAmount: 1000,
      initialBuckets: [{ id: 'b1', name: 'Global', tags: ['global'], percentage: 0, color: '#5ba88a' }],
      initialAssignments: [{
        ein: 'E1', bucketId: 'b1', status: 'sent', intended: 500, given: 200,
      }],
      bookmarkedCharities: [{
        ein: 'E1', name: 'Alpha Relief', amalScore: null, walletTag: null,
        causeTags: ['global'],
      }],
    });
    const chip = screen.getAllByTestId('record-status-E1')[0];
    expect(chip.textContent).toMatch(/Sent/i);
    expect(screen.getAllByTestId('record-confirm-E1').length).toBeGreaterThan(0);
  });

  it('renders the "Confirmed" pill for a confirmed assignment (disabled CTA)', () => {
    renderView({
      targetAmount: 1000,
      initialBuckets: [{ id: 'b1', name: 'Global', tags: ['global'], percentage: 0, color: '#5ba88a' }],
      initialAssignments: [{
        ein: 'E1', bucketId: 'b1', status: 'confirmed', intended: 500, given: 500,
      }],
      bookmarkedCharities: [{
        ein: 'E1', name: 'Alpha Relief', amalScore: null, walletTag: null,
        causeTags: ['global'],
      }],
    });
    const chip = screen.getAllByTestId('record-status-E1')[0];
    expect(chip.textContent).toMatch(/Confirmed/i);
    expect(screen.getAllByTestId('record-done-E1').length).toBeGreaterThan(0);
  });
});

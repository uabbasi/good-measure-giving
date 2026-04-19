/**
 * Unit tests for ProgressDashboard.
 *
 * Covers:
 *  - Empty state (no target set) — placeholder, no stats
 *  - Partial giving — target=1000, allocated=800, given=300
 *  - Fully given — target met, reinforcement banner visible
 *  - Overfunded — target=1000, given=1500, Remaining=$0, bar clamped
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// --- Mocks -----------------------------------------------------------------
const profileRef = { current: null as any };
vi.mock('../../contexts/UserFeaturesContext', () => ({
  useProfileState: () => ({
    profile: profileRef.current,
    isLoading: false,
    error: null,
    updateProfile: vi.fn(async () => {}),
  }),
}));

const charitiesRef = { current: [] as any[] };
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: charitiesRef.current, loading: false }),
}));

vi.mock('../../../contexts/LandingThemeContext', () => ({
  useLandingTheme: () => ({ isDark: false }),
}));

// motion/react: render children plainly
vi.mock('motion/react', () => ({
  m: new Proxy({}, {
    get: () => (props: any) => {
      const { initial, animate, transition, ...rest } = props;
      return React.createElement('div', rest, rest.children);
    },
  }),
}));

import { ProgressDashboard } from './ProgressDashboard';

function renderWithRouter(ui: React.ReactNode) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

beforeEach(() => {
  profileRef.current = null;
  charitiesRef.current = [];
});

describe('<ProgressDashboard />', () => {
  it('renders the empty-state placeholder when no target is set', () => {
    profileRef.current = {
      id: 'test-user',
      targetZakatAmount: null,
      givingBuckets: [],
      charityBucketAssignments: [],
    };
    renderWithRouter(<ProgressDashboard />);
    expect(screen.getByTestId('progress-dashboard-empty')).toBeTruthy();
    expect(screen.queryByTestId('progress-dashboard')).toBeNull();
    expect(screen.getByText(/set your zakat target/i)).toBeTruthy();
  });

  it('renders four stat cards and progress bar for a partial-giving state', () => {
    profileRef.current = {
      id: 'test-user',
      targetZakatAmount: 1000,
      givingBuckets: [{ id: 'b1', name: 'Global', tags: [], percentage: 100, color: '#111' }],
      charityBucketAssignments: [
        {
          charityEin: 'E1', bucketId: 'b1', status: 'intended',
          intended: 500, given: 200, intendedAt: '2026-01-01T00:00:00Z',
        },
        {
          charityEin: 'E2', bucketId: 'b1', status: 'sent',
          intended: 300, given: 100, intendedAt: '2026-02-01T00:00:00Z',
          sentAt: '2026-02-02T00:00:00Z',
        },
      ],
    };
    charitiesRef.current = [
      { ein: 'E1', name: 'Alpha' },
      { ein: 'E2', name: 'Beta' },
    ];

    renderWithRouter(<ProgressDashboard />);

    // Target / Allocated / Given / Remaining
    expect(screen.getByTestId('dash-target').textContent).toMatch(/\$1,000/);
    // allocated = 500 + 300 = 800
    expect(screen.getByTestId('dash-allocated').textContent).toMatch(/\$800/);
    // given = 200 + 100 = 300
    expect(screen.getByTestId('dash-given').textContent).toMatch(/\$300/);
    // remaining = 1000 - 300 = 700
    expect(screen.getByTestId('dash-remaining').textContent).toMatch(/\$700/);

    // "unallocated" hint since allocated < target
    expect(screen.getByTestId('dash-allocated').textContent).toMatch(/unallocated/i);

    // Progress bar = 30%
    expect(screen.getByTestId('dash-progress-pct').textContent).toBe('30%');
    const bar = screen.getByTestId('dash-progress-bar');
    expect(bar.getAttribute('aria-valuenow')).toBe('30');

    // Sub-summary: "0 of 2 charities confirmed" + next-up pointer
    const sub = screen.getByTestId('dash-sub-summary');
    expect(sub.textContent).toMatch(/0 of 2/);
    expect(sub.textContent).toMatch(/Alpha/); // first intended charity wins next-up

    // No completion banner
    expect(screen.queryByTestId('dash-complete-banner')).toBeNull();
  });

  it('shows the reinforcement banner at 100% progress', () => {
    profileRef.current = {
      id: 'test-user',
      targetZakatAmount: 1000,
      givingBuckets: [{ id: 'b1', name: 'Global', tags: [], percentage: 100, color: '#111' }],
      charityBucketAssignments: [
        {
          charityEin: 'E1', bucketId: 'b1', status: 'confirmed',
          intended: 500, given: 500, intendedAt: '2026-01-01T00:00:00Z',
          confirmedAt: '2026-03-01T00:00:00Z',
        },
        {
          charityEin: 'E2', bucketId: 'b1', status: 'confirmed',
          intended: 500, given: 500, intendedAt: '2026-01-02T00:00:00Z',
          confirmedAt: '2026-03-02T00:00:00Z',
        },
      ],
    };
    renderWithRouter(<ProgressDashboard />);

    expect(screen.getByTestId('dash-complete-banner')).toBeTruthy();
    expect(screen.getByTestId('dash-progress-pct').textContent).toBe('100%');
    expect(screen.getByTestId('dash-remaining').textContent).toMatch(/\$0/);
    expect(screen.getByTestId('dash-remaining').textContent).toMatch(/complete/i);

    // "X of Y confirmed" shows full — no next-up pointer when complete.
    const sub = screen.getByTestId('dash-sub-summary');
    expect(sub.textContent).toMatch(/2 of 2/);
    expect(sub.textContent).not.toMatch(/Next up/i);
  });

  it('clamps progress to 100% and shows banner when overfunded', () => {
    profileRef.current = {
      id: 'test-user',
      targetZakatAmount: 1000,
      givingBuckets: [{ id: 'b1', name: 'Global', tags: [], percentage: 100, color: '#111' }],
      charityBucketAssignments: [
        {
          charityEin: 'E1', bucketId: 'b1', status: 'confirmed',
          intended: 1500, given: 1500, intendedAt: '2026-01-01T00:00:00Z',
          confirmedAt: '2026-03-01T00:00:00Z',
        },
      ],
    };
    renderWithRouter(<ProgressDashboard />);

    expect(screen.getByTestId('dash-complete-banner')).toBeTruthy();
    // Remaining clamped to $0 when over target
    expect(screen.getByTestId('dash-remaining').textContent).toMatch(/\$0/);
    // Progress bar clamped to 100%
    expect(screen.getByTestId('dash-progress-pct').textContent).toBe('100%');
    expect(screen.getByTestId('dash-progress-bar').getAttribute('aria-valuenow')).toBe('100');
    // Allocated > Target shows the "over by" hint
    expect(screen.getByTestId('dash-allocated').textContent).toMatch(/over by \$500/i);
  });
});

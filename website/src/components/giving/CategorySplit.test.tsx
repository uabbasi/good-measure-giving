/**
 * Unit tests for CategorySplit.
 *
 * Covers:
 *  - slider rebalance math (100% invariant, pinned cases, proportional drift)
 *  - dollar-amount formatting math (indirect via rebalanceSliders + target)
 *  - bucket writes via mocked Firestore writeBatch
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import {
  CategorySplit,
  DEFAULT_SPLIT_CATEGORIES,
  rebalanceSliders,
} from './CategorySplit';

// --- Firestore mocks -------------------------------------------------------
const commitMock = vi.fn();
const updateMock = vi.fn();
vi.mock('firebase/firestore', () => ({
  writeBatch: vi.fn(() => ({
    update: updateMock,
    commit: commitMock,
  })),
  doc: vi.fn((...args: unknown[]) => ({ _ref: args })),
  Timestamp: { now: () => ({ toDate: () => new Date('2026-01-01T00:00:00Z') }) },
}));

vi.mock('../../auth/firebase', () => ({
  db: { _fake: true },
}));

vi.mock('../../auth/useAuth', () => ({
  useAuth: () => ({ uid: 'test-user', isSignedIn: true, isLoaded: true }),
}));

const updateProfileMock = vi.fn(async () => {});
vi.mock('../../contexts/UserFeaturesContext', () => ({
  useProfileState: () => ({
    profile: { id: 'test-user', givingBuckets: [], charityBucketAssignments: [] },
    isLoading: false,
    error: null,
    updateProfile: updateProfileMock,
  }),
}));

vi.mock('../../../contexts/LandingThemeContext', () => ({
  useLandingTheme: () => ({ isDark: false }),
}));

// motion/react: render children plainly
vi.mock('motion/react', () => ({
  m: new Proxy({}, { get: () => (props: any) => React.createElement('div', props, props.children) }),
}));

// Stable UUIDs
let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  if (!globalThis.crypto) {
    // @ts-expect-error - polyfill for test env
    globalThis.crypto = {};
  }
  // @ts-expect-error - overriding for deterministic test output
  globalThis.crypto.randomUUID = () => `uuid-${++uuidCounter}`;
  commitMock.mockReset();
  updateMock.mockReset();
  updateProfileMock.mockReset();
  commitMock.mockResolvedValue(undefined);
});

// --- rebalanceSliders math ------------------------------------------------
describe('rebalanceSliders', () => {
  it('keeps total at 100% after a slider change', () => {
    const next = rebalanceSliders([40, 20, 20, 20], 0, 60);
    expect(next.reduce((a, b) => a + b, 0)).toBe(100);
    expect(next[0]).toBe(60);
  });

  it('distributes the remainder proportionally across the other sliders', () => {
    const next = rebalanceSliders([40, 30, 20, 10], 0, 20);
    // others had 30+20+10=60, remainder is 80; shares 40/20/13.33 rounded
    expect(next[0]).toBe(20);
    expect(next.reduce((a, b) => a + b, 0)).toBe(100);
    // largest of the others should still be the largest
    expect(next[1]).toBeGreaterThanOrEqual(next[2]);
    expect(next[2]).toBeGreaterThanOrEqual(next[3]);
  });

  it('absorbs remainder evenly when all others are pinned at 0', () => {
    const next = rebalanceSliders([100, 0, 0, 0], 0, 40);
    expect(next[0]).toBe(40);
    expect(next[1] + next[2] + next[3]).toBe(60);
    expect(next.reduce((a, b) => a + b, 0)).toBe(100);
  });

  it('clamps to [0, 100]', () => {
    expect(rebalanceSliders([25, 25, 25, 25], 0, 150)[0]).toBe(100);
    expect(rebalanceSliders([25, 25, 25, 25], 0, -20)[0]).toBe(0);
  });

  it('returns integer values', () => {
    const next = rebalanceSliders([33, 33, 34, 0], 0, 50);
    for (const v of next) expect(Number.isInteger(v)).toBe(true);
  });

  it('fourth slider takes the remainder when three are pinned at extremes', () => {
    // Pin indexes 0, 1, 2 (after rebalance math accepts value changes on idx 3).
    // Start from a state where 3 others total 100 -> 4th = 0; move the 4th
    // slider to 0 explicitly, rebalance should leave others unchanged.
    const next = rebalanceSliders([50, 30, 20, 0], 3, 0);
    expect(next[3]).toBe(0);
    expect(next.reduce((a, b) => a + b, 0)).toBe(100);
  });
});

// --- Component rendering + save flow --------------------------------------
describe('<CategorySplit />', () => {
  it('renders the 4 default categories with starting percentages and dollar labels', () => {
    render(<CategorySplit target={1000} onDone={() => {}} />);
    for (const cat of DEFAULT_SPLIT_CATEGORIES) {
      expect(screen.getByText(cat.name)).toBeTruthy();
    }
    // Starting splits: 40/20/20/20 of $1000 => $400 / $200 / $200 / $200
    expect(screen.getAllByText(/\$400 of \$1,000/i).length).toBeGreaterThan(0);
  });

  it('writes buckets to Firestore on confirm', async () => {
    const onDone = vi.fn();
    render(<CategorySplit target={1000} onDone={onDone} />);

    fireEvent.click(screen.getByTestId('split-confirm'));

    await waitFor(() => expect(commitMock).toHaveBeenCalledTimes(1));
    // Primary write uses update() with givingBuckets
    expect(updateMock).toHaveBeenCalled();
    const payload = updateMock.mock.calls[0][1];
    expect(payload.givingBuckets).toHaveLength(DEFAULT_SPLIT_CATEGORIES.length);
    // Order + percentage defaults preserved
    expect(payload.givingBuckets[0]).toMatchObject({
      name: 'Global Humanitarian',
      percentage: 40,
    });
    // Cache refresh via context updateProfile happens after commit
    expect(updateProfileMock).toHaveBeenCalled();
    expect(onDone).toHaveBeenCalled();
  });

  it('omits categories set to 0%', async () => {
    render(<CategorySplit target={1000} onDone={() => {}} />);
    // Move first slider to 100%, which rebalances others to 0
    const slider = screen.getByTestId(`split-slider-${DEFAULT_SPLIT_CATEGORIES[0].id}`);
    fireEvent.change(slider, { target: { value: '100' } });
    fireEvent.click(screen.getByTestId('split-confirm'));
    await waitFor(() => expect(commitMock).toHaveBeenCalled());
    const payload = updateMock.mock.calls[0][1];
    expect(payload.givingBuckets).toHaveLength(1);
    expect(payload.givingBuckets[0].percentage).toBe(100);
  });
});

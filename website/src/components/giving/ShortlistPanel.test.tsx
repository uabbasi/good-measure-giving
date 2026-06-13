import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const addToShortlist = vi.fn(async () => {});
const removeFromShortlist = vi.fn(async () => {});
let shortlist: { ref: string; addedBy: string; addedAt: number }[] = [];
const members = [{ uid: 'u1', displayName: 'Dad' }];

vi.mock('../../hooks/useSharedPlan', () => ({
  useSharedPlan: () => ({
    plan: { shortlist, items: [] },
    members,
    addToShortlist,
    removeFromShortlist,
  }),
}));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: [{ ein: '11-1', name: 'Acme Relief' }] }),
}));

import { ShortlistPanel } from './ShortlistPanel';

beforeEach(() => { shortlist = []; addToShortlist.mockClear(); removeFromShortlist.mockClear(); });

describe('ShortlistPanel', () => {
  it('lists candidates with who suggested them', () => {
    shortlist = [{ ref: '11-1', addedBy: 'u1', addedAt: 1 }];
    render(<ShortlistPanel planId="p1" />);
    expect(screen.getByText('Acme Relief')).toBeTruthy();
    expect(screen.getByText(/Dad/)).toBeTruthy();
  });
  it('removes a candidate when ✕ clicked', () => {
    shortlist = [{ ref: '11-1', addedBy: 'u1', addedAt: 1 }];
    render(<ShortlistPanel planId="p1" />);
    fireEvent.click(screen.getByLabelText(/remove acme relief/i));
    expect(removeFromShortlist).toHaveBeenCalledWith('11-1');
  });
});

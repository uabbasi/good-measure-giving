/**
 * Regression: the recap headline read "supporting 3 charities across 0
 * causes this 2026" for every real plan — no code path anywhere ever
 * creates a `kind: 'category'` PlanItem, so `causeCount` is structurally
 * always 0 for plans built the only way the UI allows (adding specific
 * charities). "this {year}" also reads oddly ("this 2026"). Fixed to omit
 * the causes clause when there are none, and to say "in {year}".
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { PlanItem } from '../../types/sharedPlan';

vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ charities: [{ ein: '04-3810161', name: 'ICNA Relief' }] }),
}));

function mockPlan(items: PlanItem[]) {
  vi.doMock('../../hooks/useSharedPlan', () => ({
    useSharedPlan: () => ({
      plan: { id: 'p1', name: 'Khan Family', inviteToken: 'tok', items },
      isLoading: false,
    }),
  }));
}

describe('SessionRecap headline', () => {
  it('omits the causes clause when the plan has none (the only reachable case today)', async () => {
    vi.resetModules();
    mockPlan([
      { id: 'a', kind: 'charity', ref: '04-3810161', weight: 1, assigneeUid: null, updatedAt: 1, updatedBy: 'u1' },
    ]);
    const { SessionRecap } = await import('./SessionRecap');
    render(<SessionRecap planId="p1" />);

    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading.textContent).toMatch(/supporting 1 charity in \d{4}/);
    expect(heading.textContent).not.toMatch(/causes?/);
    expect(heading.textContent).not.toMatch(/this \d{4}/);
  });

  it('includes the causes clause when category items are present', async () => {
    vi.resetModules();
    mockPlan([
      { id: 'a', kind: 'charity', ref: '04-3810161', weight: 1, assigneeUid: null, updatedAt: 1, updatedBy: 'u1' },
      { id: 'b', kind: 'category', ref: 'palestine', weight: 1, assigneeUid: null, updatedAt: 1, updatedBy: 'u1' },
    ]);
    const { SessionRecap } = await import('./SessionRecap');
    render(<SessionRecap planId="p1" />);

    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading.textContent).toMatch(/across 1 cause in \d{4}/);
  });
});

import { describe, it, expect } from 'vitest';
import { summarize } from './recapSummary';
import type { PlanItem } from '../types/sharedPlan';

const item = (over: Partial<PlanItem>): PlanItem => ({
  id: '1', kind: 'charity', ref: '95-4453134', weight: 1, assigneeUid: null,
  updatedAt: 0, updatedBy: 'u', ...over,
});

describe('summarize', () => {
  it('counts charities and distinct causes (categories)', () => {
    const s = summarize([
      item({ id: '1', kind: 'charity', ref: 'A' }),
      item({ id: '2', kind: 'charity', ref: 'B' }),
      item({ id: '3', kind: 'category', ref: 'humanitarian' }),
    ]);
    expect(s.charityCount).toBe(2);
    expect(s.causeCount).toBe(1);
  });
  it('handles an empty plan', () => {
    expect(summarize([])).toEqual({ charityCount: 0, causeCount: 0 });
  });
});

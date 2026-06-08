import { describe, it, expect } from 'vitest';
import { replaceOrAppendItem } from './useSharedPlan';
import type { PlanItem } from '../types/sharedPlan';

const item = (over: Partial<PlanItem> = {}): PlanItem => ({
  id: 'a', kind: 'charity', ref: '95-4453134', weight: 1, assigneeUid: null,
  updatedAt: 100, updatedBy: 'u1', ...over,
});

describe('replaceOrAppendItem', () => {
  it('appends a new item by id', () => {
    expect(replaceOrAppendItem([], item({ id: 'x' })).map(i => i.id)).toEqual(['x']);
  });
  it('overwrites an existing item by id (last write wins, whole-item)', () => {
    const out = replaceOrAppendItem([item({ id: 'a', weight: 1 })], item({ id: 'a', weight: 5 }));
    expect(out.find(i => i.id === 'a')!.weight).toBe(5);
  });
  it('leaves other rows untouched', () => {
    const out = replaceOrAppendItem([item({ id: 'a' }), item({ id: 'b', weight: 2 })], item({ id: 'a', weight: 7 }));
    expect(out.find(i => i.id === 'b')!.weight).toBe(2);
  });
});

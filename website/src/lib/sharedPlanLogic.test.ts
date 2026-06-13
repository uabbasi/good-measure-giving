import { describe, it, expect } from 'vitest';
import { mergeItem, weightsToPercents, computeYourShare, newInviteToken, pruneHistory, addCharityItem } from './sharedPlanLogic';
import type { PlanItem, PlanHistoryEntry } from '../types/sharedPlan';

const item = (over: Partial<PlanItem> = {}): PlanItem => ({
  id: 'a', kind: 'charity', ref: '95-4453134', weight: 1, assigneeUid: null,
  updatedAt: 100, updatedBy: 'u1', ...over,
});

describe('addCharityItem', () => {
  it('appends a new charity at weight 1', () => {
    const out = addCharityItem([], '95-4453134', 'u1');
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ kind: 'charity', ref: '95-4453134', weight: 1, assigneeUid: null, updatedBy: 'u1' });
  });
  it('no-ops (same array ref) when the charity is already present', () => {
    const items = [item({ id: 'a', ref: '95-4453134' })];
    const out = addCharityItem(items, '95-4453134', 'u2');
    expect(out).toBe(items); // unchanged reference → caller skips the write
  });
  it('adds a different charity alongside existing ones', () => {
    const items = [item({ id: 'a', ref: '95-4453134' })];
    const out = addCharityItem(items, '36-4476244', 'u1');
    expect(out).toHaveLength(2);
    expect(out.map(i => i.ref).sort()).toEqual(['36-4476244', '95-4453134']);
  });
});

describe('mergeItem', () => {
  it('adds a new item when id absent', () => {
    const out = mergeItem([], item({ id: 'x' }));
    expect(out.map(i => i.id)).toEqual(['x']);
  });
  it('overwrites same id when incoming is newer (LWW)', () => {
    const out = mergeItem([item({ id: 'a', weight: 1, updatedAt: 100 })], item({ id: 'a', weight: 5, updatedAt: 200 }));
    expect(out.find(i => i.id === 'a')!.weight).toBe(5);
  });
  it('keeps existing when incoming is older (stale write loses)', () => {
    const out = mergeItem([item({ id: 'a', weight: 9, updatedAt: 300 })], item({ id: 'a', weight: 5, updatedAt: 200 }));
    expect(out.find(i => i.id === 'a')!.weight).toBe(9);
  });
  it('leaves other rows untouched', () => {
    const out = mergeItem([item({ id: 'a' }), item({ id: 'b', weight: 2 })], item({ id: 'a', weight: 7, updatedAt: 500 }));
    expect(out.find(i => i.id === 'b')!.weight).toBe(2);
  });
});

describe('weightsToPercents', () => {
  it('normalizes weights to percentages summing ~100', () => {
    const pct = weightsToPercents([item({ id: 'a', weight: 1 }), item({ id: 'b', weight: 3 })]);
    expect(pct['a']).toBe(25);
    expect(pct['b']).toBe(75);
  });
  it('returns 0s when all weights are 0', () => {
    const pct = weightsToPercents([item({ id: 'a', weight: 0 })]);
    expect(pct['a']).toBe(0);
  });
});

describe('computeYourShare', () => {
  it('applies a personal target to each item weight', () => {
    const shares = computeYourShare([item({ id: 'a', weight: 1 }), item({ id: 'b', weight: 1 })], 1000);
    expect(shares['a']).toBe(500);
    expect(shares['b']).toBe(500);
  });
  it('returns null map when target is null', () => {
    expect(computeYourShare([item({ id: 'a', weight: 1 })], null)).toEqual({});
  });
});

describe('newInviteToken', () => {
  it('produces a 20+ char url-safe token', () => {
    const t = newInviteToken();
    expect(t).toMatch(/^[A-Za-z0-9_-]{20,}$/);
  });
  it('produces distinct tokens', () => {
    expect(newInviteToken()).not.toBe(newInviteToken());
  });
});

describe('pruneHistory', () => {
  it('keeps only the newest N entries', () => {
    const entries: PlanHistoryEntry[] = Array.from({ length: 25 }, (_, i) => ({
      revision: i, itemId: 'a', before: null, after: null, updatedBy: 'u', at: i,
    }));
    const kept = pruneHistory(entries, 20);
    expect(kept).toHaveLength(20);
    expect(kept[0].revision).toBe(5);
  });
});

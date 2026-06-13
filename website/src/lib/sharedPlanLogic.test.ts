import { describe, it, expect } from 'vitest';
import { weightsToPercents, computeYourShare, newInviteToken, addCharityItem, applyItemLWW, removeItemById, HISTORY_MAX, historyIdToPrune, setMemberNote, addShortlistCandidate, removeShortlistCandidate, promoteCandidate } from './sharedPlanLogic';
import type { PlanItem, ShortlistCandidate } from '../types/sharedPlan';

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

describe('applyItemLWW', () => {
  it('appends when the id is absent', () => {
    const out = applyItemLWW([], item({ id: 'x', updatedAt: 5 }));
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('x');
  });
  it('newer updatedAt overwrites the stored item', () => {
    const items = [item({ id: 'a', weight: 1, updatedAt: 100 })];
    const out = applyItemLWW(items, item({ id: 'a', weight: 9, updatedAt: 200 }));
    expect(out[0].weight).toBe(9);
  });
  it('stale updatedAt loses (stored item kept)', () => {
    const items = [item({ id: 'a', weight: 1, updatedAt: 200 })];
    const out = applyItemLWW(items, item({ id: 'a', weight: 9, updatedAt: 100 }));
    expect(out[0].weight).toBe(1);
  });
  it('preserves the stored notes map when a weight edit lands', () => {
    const stored = item({ id: 'a', weight: 1, updatedAt: 100, notes: { u1: { text: 'mine', at: 1 } } });
    const incoming = item({ id: 'a', weight: 9, updatedAt: 200, notes: undefined });
    const out = applyItemLWW([stored], incoming);
    expect(out[0].weight).toBe(9);
    expect(out[0].notes).toEqual({ u1: { text: 'mine', at: 1 } });
  });
});

describe('removeItemById', () => {
  it('removes the item with the id', () => {
    const items = [item({ id: 'a' }), item({ id: 'b' })];
    expect(removeItemById(items, 'a').map(i => i.id)).toEqual(['b']);
  });
  it('is idempotent when the id is absent', () => {
    const items = [item({ id: 'a' })];
    expect(removeItemById(items, 'zzz')).toEqual(items);
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

describe('historyIdToPrune', () => {
  it('returns null while the buffer is not yet full', () => {
    expect(historyIdToPrune(1, 20)).toBeNull();
    expect(historyIdToPrune(20, 20)).toBeNull();
  });
  it('returns the revision id to delete once full', () => {
    expect(historyIdToPrune(21, 20)).toBe('1');
    expect(historyIdToPrune(25, 20)).toBe('5');
  });
  it('HISTORY_MAX is 20', () => {
    expect(HISTORY_MAX).toBe(20);
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

const cand = (ref: string, addedBy = 'u1'): ShortlistCandidate => ({ ref, addedBy, addedAt: 1 });

describe('addShortlistCandidate', () => {
  it('appends a new candidate', () => {
    const out = addShortlistCandidate([], '11-1', 'u1');
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ ref: '11-1', addedBy: 'u1' });
  });
  it('dedupes by ref (same array ref returned)', () => {
    const list = [cand('11-1')];
    expect(addShortlistCandidate(list, '11-1', 'u2')).toBe(list);
  });
});

describe('removeShortlistCandidate', () => {
  it('removes by ref', () => {
    expect(removeShortlistCandidate([cand('11-1'), cand('22-2')], '11-1').map(c => c.ref)).toEqual(['22-2']);
  });
});

describe('promoteCandidate', () => {
  it('moves a candidate from shortlist into items at weight 1', () => {
    const out = promoteCandidate([], [cand('11-1')], '11-1', 'u1');
    expect(out.shortlist).toHaveLength(0);
    expect(out.items).toHaveLength(1);
    expect(out.items[0]).toMatchObject({ kind: 'charity', ref: '11-1', weight: 1 });
  });
  it('does not duplicate an already-present charity, still drops the candidate', () => {
    const existing = [item({ id: 'a', kind: 'charity', ref: '11-1' })];
    const out = promoteCandidate(existing, [cand('11-1')], '11-1', 'u1');
    expect(out.items).toHaveLength(1);
    expect(out.shortlist).toHaveLength(0);
  });
});

describe('setMemberNote', () => {
  it('sets the calling member key, preserving other members notes', () => {
    const base = item({ id: 'a', notes: { u1: { text: 'one', at: 1 } } });
    const out = setMemberNote(base, 'u2', 'two');
    expect(out.notes?.u1).toEqual({ text: 'one', at: 1 });
    expect(out.notes?.u2?.text).toBe('two');
    expect(typeof out.notes?.u2?.at).toBe('number');
  });
  it('trims and clears the key when text is empty', () => {
    const base = item({ id: 'a', notes: { u1: { text: 'one', at: 1 }, u2: { text: 'two', at: 2 } } });
    const out = setMemberNote(base, 'u2', '   ');
    expect(out.notes?.u2).toBeUndefined();
    expect(out.notes?.u1).toEqual({ text: 'one', at: 1 });
  });
  it('works when the item has no notes yet', () => {
    const out = setMemberNote(item({ id: 'a', notes: undefined }), 'u1', 'hi');
    expect(out.notes).toEqual({ u1: { text: 'hi', at: expect.any(Number) } });
  });
});

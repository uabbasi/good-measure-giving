import type { PlanItem, PlanHistoryEntry } from '../types/sharedPlan';

/**
 * Add a charity (by EIN) to an items array at weight 1, or no-op if a charity
 * with that EIN is already in the plan. Used by the "Add to family plan" bridge.
 * Returns the same array reference when the charity is already present (so callers
 * can skip the write).
 */
export function addCharityItem(items: PlanItem[], ein: string, actorUid: string): PlanItem[] {
  if (items.some(i => i.kind === 'charity' && i.ref === ein)) return items;
  const id =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${ein}-${items.length}`;
  return [
    ...items,
    { id, kind: 'charity', ref: ein, weight: 1, assigneeUid: null, updatedAt: Date.now(), updatedBy: actorUid },
  ];
}

/**
 * Per-row last-write-wins upsert of one item into an items array. The incoming
 * value wins only if its updatedAt >= the stored item's (a stale write loses).
 * The stored item's `notes` map is always preserved — weight/assignee edits must
 * never clobber another member's niyyah note (notes are owned by setMemberNote).
 */
export function applyItemLWW(items: PlanItem[], incoming: PlanItem): PlanItem[] {
  const idx = items.findIndex(i => i.id === incoming.id);
  if (idx === -1) return [...items, incoming];
  const stored = items[idx];
  if (incoming.updatedAt >= stored.updatedAt) {
    const next = items.slice();
    next[idx] = { ...incoming, notes: stored.notes };
    return next;
  }
  return items;
}

/** Remove an item by id (idempotent). */
export function removeItemById(items: PlanItem[], id: string): PlanItem[] {
  return items.filter(i => i.id !== id);
}

/** Normalize item weights to percentages (0-100). */
export function weightsToPercents(items: PlanItem[]): Record<string, number> {
  const total = items.reduce((s, i) => s + (i.weight || 0), 0);
  const out: Record<string, number> = {};
  for (const i of items) out[i.id] = total > 0 ? Math.round((i.weight / total) * 100) : 0;
  return out;
}

/** Each item's dollar share of a member's PERSONAL target (never stored). */
export function computeYourShare(items: PlanItem[], personalTarget: number | null): Record<string, number> {
  if (personalTarget == null) return {};
  const total = items.reduce((s, i) => s + (i.weight || 0), 0);
  const out: Record<string, number> = {};
  for (const i of items) out[i.id] = total > 0 ? Math.round((i.weight / total) * personalTarget) : 0;
  return out;
}

/** Unguessable url-safe invite token. */
export function newInviteToken(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Ring-buffer size for the per-plan edit history subcollection. */
export const HISTORY_MAX = 20;

/**
 * History docs are keyed by the monotonic `revision`. After writing revision R,
 * the entry to delete to keep the last `max` is `R - max` — but only once it
 * exists (revisions start at 1). Returns the doc id string, or null if nothing
 * to prune yet.
 */
export function historyIdToPrune(revision: number, max: number): string | null {
  const target = revision - max;
  return target >= 1 ? String(target) : null;
}

/**
 * Merge one member's niyyah note onto an item, preserving every other member's
 * note. Empty/whitespace text deletes the caller's note. Pure — apply it to a
 * freshly re-read item inside the write transaction.
 */
export function setMemberNote(item: PlanItem, uid: string, text: string): PlanItem {
  const trimmed = text.trim();
  const notes = { ...(item.notes ?? {}) };
  if (trimmed === '') delete notes[uid];
  else notes[uid] = { text: trimmed, at: Date.now() };
  return { ...item, notes };
}


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

/** Per-row last-write-wins merge of one item into an items array. */
export function mergeItem(items: PlanItem[], incoming: PlanItem): PlanItem[] {
  const idx = items.findIndex(i => i.id === incoming.id);
  if (idx === -1) return [...items, incoming];
  if (incoming.updatedAt >= items[idx].updatedAt) {
    const next = items.slice();
    next[idx] = incoming;
    return next;
  }
  return items;
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

/** Keep only the newest `max` history entries (input ordered oldest→newest). */
export function pruneHistory(entries: PlanHistoryEntry[], max: number): PlanHistoryEntry[] {
  return entries.length <= max ? entries : entries.slice(entries.length - max);
}

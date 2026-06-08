# Shared Household Giving Plans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a shared, multi-editor household giving plan that holds proportions (not dollars), joinable by an invite link, as the product's first growth loop.

**Architecture:** A new Firestore tree `shared_plans/{planId}` (money-free: charities/categories + weights + assignees) with a `members` subcollection. The plan doc has an unguessable auto-id and is **publicly readable** (no sensitive data) so an invited person sees a read-only preview before signing up; an `inviteToken` gates only the join-write. Per-row last-write-wins via a transaction that patches one `items[]` element by id, bumps a `revision`, and appends a bounded `history`. Each member applies the shared weights to their **own** private zakat target client-side ("your share") — dollars never enter the shared doc. A plan switcher on the profile keeps the existing personal plan untouched.

**Tech Stack:** React 19, TypeScript 5.8, Firebase Firestore (web SDK), TanStack Query, React Router 6, Vitest (unit, `vi.mock` firestore), Playwright (e2e). Spec: `docs/superpowers/specs/2026-06-08-shared-household-giving-plans-design.md`.

---

## File Structure

**New files:**
- `website/src/types/sharedPlan.ts` — `SharedPlan`, `PlanItem`, `PlanMember`, `PlanHistoryEntry` types. Pure types.
- `website/src/lib/sharedPlanLogic.ts` — pure functions: `mergeItem`, `weightsToPercents`, `computeYourShare`, `newInviteToken`, `pruneHistory`. No Firebase imports. Unit-tested.
- `website/src/lib/sharedPlanLogic.test.ts` — Vitest unit tests for the above.
- `website/src/hooks/useSharedPlan.ts` — load one plan + members; mutations (`upsertItem`, `removeItem`, `rename`, `rotateToken`, `removeMember`, `join`) via TanStack Query + Firestore transaction.
- `website/src/hooks/useSharedPlan.test.ts` — Vitest, mocked firestore, covers the transaction merge + join.
- `website/src/hooks/useSharedPlans.ts` — list the plans a user belongs to (from `users/{uid}.sharedPlanIds`), plus `createPlan`.
- `website/src/components/giving/SharedPlanView.tsx` — proportional allocation UI (weights + assignees, no dollars) + per-member "your share".
- `website/src/components/giving/InviteFamilyPanel.tsx` — owner: create/rotate/revoke link + native share; member list with remove.
- `website/src/components/giving/PlanSwitcher.tsx` — `[ My plan ▾ ] [ Khan Family ]` selector.
- `website/pages/JoinPlanPage.tsx` — `/plan/join/:planId/:token` public read-only preview + sign-in-to-join CTA.
- `website/tests/e2e/shared-plan.spec.ts` — Playwright: create → invite → preview (signed out) → join flow.

**Modified files:**
- `website/types.ts` — add `sharedPlanIds?: string[]` to the user profile interface.
- `website/firestore.rules` — rules for `shared_plans` + `members` + `history`.
- `website/App.tsx` — route `/plan/join/:planId/:token`.
- `website/pages/ProfilePage.tsx` — mount `PlanSwitcher`; render `SharedPlanView` when a shared plan is selected.
- `website/src/utils/analytics.ts` — add `trackInviteCreated`, `trackPlanPreview`, `trackPlanJoined` (follow existing event helpers).

---

## Task 1: Types + pure plan logic

**Files:**
- Create: `website/src/types/sharedPlan.ts`
- Create: `website/src/lib/sharedPlanLogic.ts`
- Test: `website/src/lib/sharedPlanLogic.test.ts`

- [ ] **Step 1: Create the types**

```typescript
// website/src/types/sharedPlan.ts
export interface PlanItem {
  id: string;                       // client-generated uuid, stable
  kind: 'charity' | 'category';
  ref: string;                      // EIN (charity) or category slug
  weight: number;                   // proportion / relative weight (NOT dollars)
  assigneeUid: string | null;       // member covering this item, or null
  updatedAt: number;                // epoch ms — drives per-row last-write-wins
  updatedBy: string;                // uid
}

export interface SharedPlan {
  id: string;
  name: string;
  ownerId: string;
  createdAt: number;
  updatedAt: number;
  revision: number;
  inviteToken: string;
  items: PlanItem[];
}

export interface PlanMember {
  uid: string;
  role: 'owner' | 'editor';
  displayName: string;
  joinedAt: number;
}

export interface PlanHistoryEntry {
  revision: number;
  itemId: string;
  before: PlanItem | null;
  after: PlanItem | null;
  updatedBy: string;
  at: number;
}
```

- [ ] **Step 2: Write the failing tests**

```typescript
// website/src/lib/sharedPlanLogic.test.ts
import { describe, it, expect } from 'vitest';
import { mergeItem, weightsToPercents, computeYourShare, newInviteToken, pruneHistory } from './sharedPlanLogic';
import type { PlanItem, PlanHistoryEntry } from '../types/sharedPlan';

const item = (over: Partial<PlanItem> = {}): PlanItem => ({
  id: 'a', kind: 'charity', ref: '95-4453134', weight: 1, assigneeUid: null,
  updatedAt: 100, updatedBy: 'u1', ...over,
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
    expect(kept[0].revision).toBe(5); // oldest 5 dropped
  });
});
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: FAIL — module `./sharedPlanLogic` not found.

- [ ] **Step 4: Implement the logic**

```typescript
// website/src/lib/sharedPlanLogic.ts
import type { PlanItem, PlanHistoryEntry } from '../types/sharedPlan';

/** Per-row last-write-wins merge of one item into an items array. */
export function mergeItem(items: PlanItem[], incoming: PlanItem): PlanItem[] {
  const idx = items.findIndex(i => i.id === incoming.id);
  if (idx === -1) return [...items, incoming];
  if (incoming.updatedAt >= items[idx].updatedAt) {
    const next = items.slice();
    next[idx] = incoming;
    return next;
  }
  return items; // stale write loses
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

/** Keep only the newest `max` history entries (assumes input ordered oldest→newest). */
export function pruneHistory(entries: PlanHistoryEntry[], max: number): PlanHistoryEntry[] {
  return entries.length <= max ? entries : entries.slice(entries.length - max);
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: PASS (all cases).

- [ ] **Step 6: Commit**

```bash
git add website/src/types/sharedPlan.ts website/src/lib/sharedPlanLogic.ts website/src/lib/sharedPlanLogic.test.ts
git commit -m "feat(shared-plan): types + pure plan logic (LWW merge, percents, your-share)"
```

---

## Task 2: Firestore security rules

**Files:**
- Modify: `website/firestore.rules`

Rules approach (no Cloud Function): the plan doc is money-free with an unguessable auto-id, so it is publicly readable for the preview. The `inviteToken` only gates the join-write: a user may create their own member doc only if the member payload carries a `token` equal to the parent plan's `inviteToken`. Item writes are members-only; owner-only fields are guarded with a helper.

- [ ] **Step 1: Replace the rules file**

```javascript
// website/firestore.rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    match /users/{userId}/{sub}/{docId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    match /reported_issues/{issueId} {
      allow create: if true;
      allow read, update, delete: if false;
    }

    match /shared_plans/{planId} {
      function isMember() {
        return request.auth != null &&
          exists(/databases/$(database)/documents/shared_plans/$(planId)/members/$(request.auth.uid));
      }
      function isOwner() {
        return request.auth != null && resource.data.ownerId == request.auth.uid;
      }
      // Money-free doc, unguessable id → public read enables the pre-signup preview.
      allow read: if true;
      // Creator sets themselves as owner.
      allow create: if request.auth != null && request.resource.data.ownerId == request.auth.uid;
      // Members may edit plan content; only the owner may change owner-only fields.
      allow update: if isMember() &&
        (isOwner() ||
          (request.resource.data.ownerId == resource.data.ownerId &&
           request.resource.data.inviteToken == resource.data.inviteToken &&
           request.resource.data.name == resource.data.name));
      allow delete: if isOwner();

      match /members/{uid} {
        // Join: create only your own member doc, and only with a token matching the plan.
        allow create: if request.auth != null && request.auth.uid == uid &&
          request.resource.data.token ==
            get(/databases/$(database)/documents/shared_plans/$(planId)).data.inviteToken;
        allow read: if true; // member list shown in preview is non-sensitive (names only)
        // Leave (self) or owner removes a member.
        allow delete: if request.auth != null && (request.auth.uid == uid ||
          get(/databases/$(database)/documents/shared_plans/$(planId)).data.ownerId == request.auth.uid);
      }

      match /history/{entryId} {
        allow read: if isMember();
        allow write: if isMember();
      }
    }
  }
}
```

- [ ] **Step 2: Validate the rules syntax**

Run (uses the Firebase MCP `firestore_validate_security_rules`, or CLI):
`cd website && npx firebase deploy --only firestore:rules --dry-run` (if dry-run unsupported, run `firebase firestore:rules:check` or validate via the Firebase MCP tool `mcp__plugin_firebase_firebase__firebase_validate_security_rules` against `firestore.rules`).
Expected: "Rules are valid" / no syntax errors. **Do not deploy** (deploy happens with the app deploy).

- [ ] **Step 3: Commit**

```bash
git add website/firestore.rules
git commit -m "feat(shared-plan): firestore rules — public read, token-gated join, member-only writes"
```

---

## Task 3: `useSharedPlan` hook (load + per-row LWW writes)

**Files:**
- Create: `website/src/hooks/useSharedPlan.ts`
- Test: `website/src/hooks/useSharedPlan.test.ts`

The hook loads `shared_plans/{planId}` + its `members`, and exposes mutations. `upsertItem` runs a Firestore **transaction**: re-read the plan, `mergeItem` the single incoming item (per-row LWW), bump `revision`, write a `history` entry, prune history to 20. This keeps "different rows never collide" honest even though items share one document.

- [ ] **Step 1: Write the failing test (transaction merge)**

```typescript
// website/src/hooks/useSharedPlan.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { applyItemTransaction } from './useSharedPlan';
import type { SharedPlan, PlanItem } from '../types/sharedPlan';

const basePlan = (items: PlanItem[]): SharedPlan => ({
  id: 'p1', name: 'Khan Family', ownerId: 'u1', createdAt: 1, updatedAt: 1,
  revision: 3, inviteToken: 'tok', items,
});
const item = (over: Partial<PlanItem> = {}): PlanItem => ({
  id: 'a', kind: 'charity', ref: '95-4453134', weight: 1, assigneeUid: null,
  updatedAt: 100, updatedBy: 'u1', ...over,
});

describe('applyItemTransaction', () => {
  it('merges the incoming item, bumps revision, appends history', () => {
    const current = basePlan([item({ id: 'a', weight: 1, updatedAt: 100 })]);
    const result = applyItemTransaction(current, item({ id: 'a', weight: 4, updatedAt: 200 }), 'u2');
    expect(result.plan.items.find(i => i.id === 'a')!.weight).toBe(4);
    expect(result.plan.revision).toBe(4);
    expect(result.historyEntry.itemId).toBe('a');
    expect(result.historyEntry.after!.weight).toBe(4);
    expect(result.historyEntry.before!.weight).toBe(1);
  });
  it('adds a new row without touching others', () => {
    const current = basePlan([item({ id: 'a' })]);
    const result = applyItemTransaction(current, item({ id: 'b', weight: 2 }), 'u2');
    expect(result.plan.items.map(i => i.id).sort()).toEqual(['a', 'b']);
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd website && npx vitest run src/hooks/useSharedPlan.test.ts`
Expected: FAIL — `applyItemTransaction` not exported.

- [ ] **Step 3: Implement the hook (export the pure transaction core for testing)**

```typescript
// website/src/hooks/useSharedPlan.ts
import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  doc, collection, getDoc, getDocs, setDoc, deleteDoc, runTransaction, Timestamp,
} from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import { mergeItem } from '../lib/sharedPlanLogic';
import type { SharedPlan, PlanItem, PlanMember, PlanHistoryEntry } from '../types/sharedPlan';

/** Pure core of the item-upsert transaction (unit-tested). */
export function applyItemTransaction(
  current: SharedPlan,
  incoming: PlanItem,
  actorUid: string,
): { plan: SharedPlan; historyEntry: PlanHistoryEntry } {
  const before = current.items.find(i => i.id === incoming.id) ?? null;
  const items = mergeItem(current.items, incoming);
  const after = items.find(i => i.id === incoming.id) ?? null;
  const revision = current.revision + 1;
  return {
    plan: { ...current, items, revision, updatedAt: Date.now() },
    historyEntry: { revision, itemId: incoming.id, before, after, updatedBy: actorUid, at: Date.now() },
  };
}

export function useSharedPlan(planId: string | null) {
  const { db, userId } = useFirebaseData();
  const qc = useQueryClient();
  const key = ['sharedPlan', planId];

  const { data, isLoading, error } = useQuery({
    queryKey: key,
    enabled: !!db && !!planId,
    queryFn: async (): Promise<{ plan: SharedPlan | null; members: PlanMember[] }> => {
      if (!db || !planId) return { plan: null, members: [] };
      const snap = await getDoc(doc(db, 'shared_plans', planId));
      if (!snap.exists()) return { plan: null, members: [] };
      const plan = { id: snap.id, ...(snap.data() as Omit<SharedPlan, 'id'>) };
      const memSnap = await getDocs(collection(db, 'shared_plans', planId, 'members'));
      const members = memSnap.docs.map(d => ({ uid: d.id, ...(d.data() as Omit<PlanMember, 'uid'>) }));
      return { plan, members };
    },
  });

  const upsertItem = useMutation({
    mutationFn: async (incoming: PlanItem) => {
      if (!db || !planId || !userId) throw new Error('Not authenticated');
      await runTransaction(db, async (tx) => {
        const ref = doc(db, 'shared_plans', planId);
        const snap = await tx.get(ref);
        if (!snap.exists()) throw new Error('Plan not found');
        const current = { id: snap.id, ...(snap.data() as Omit<SharedPlan, 'id'>) };
        const stamped = { ...incoming, updatedAt: Date.now(), updatedBy: userId };
        const { plan, historyEntry } = applyItemTransaction(current, stamped, userId);
        tx.set(ref, { items: plan.items, revision: plan.revision, updatedAt: Timestamp.now() }, { merge: true });
        tx.set(doc(collection(db, 'shared_plans', planId, 'history')), historyEntry);
      });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeItem = useMutation({
    mutationFn: async (itemId: string) => {
      if (!db || !planId || !userId) throw new Error('Not authenticated');
      await runTransaction(db, async (tx) => {
        const ref = doc(db, 'shared_plans', planId);
        const snap = await tx.get(ref);
        if (!snap.exists()) return;
        const current = { id: snap.id, ...(snap.data() as Omit<SharedPlan, 'id'>) };
        const items = current.items.filter(i => i.id !== itemId);
        tx.set(ref, { items, revision: current.revision + 1, updatedAt: Timestamp.now() }, { merge: true });
      });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const join = useMutation({
    mutationFn: async ({ token, displayName }: { token: string; displayName: string }) => {
      if (!db || !planId || !userId) throw new Error('Not authenticated');
      // Member-create rule checks token matches the plan's inviteToken.
      await setDoc(doc(db, 'shared_plans', planId, 'members', userId), {
        role: 'editor', displayName, joinedAt: Timestamp.now(), token,
      });
      // Point the user's profile at this plan (array-union via merge).
      const userRef = doc(db, 'users', userId);
      const userSnap = await getDoc(userRef);
      const existing: string[] = (userSnap.data()?.sharedPlanIds as string[]) || [];
      if (!existing.includes(planId)) {
        await setDoc(userRef, { sharedPlanIds: [...existing, planId] }, { merge: true });
      }
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeMember = useMutation({
    mutationFn: async (uid: string) => {
      if (!db || !planId) throw new Error('Not authenticated');
      await deleteDoc(doc(db, 'shared_plans', planId, 'members', uid));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const rename = useMutation({
    mutationFn: async (name: string) => {
      if (!db || !planId) throw new Error('Not authenticated');
      await setDoc(doc(db, 'shared_plans', planId), { name, updatedAt: Timestamp.now() }, { merge: true });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const rotateToken = useMutation({
    mutationFn: async (token: string) => {
      if (!db || !planId) throw new Error('Not authenticated');
      await setDoc(doc(db, 'shared_plans', planId), { inviteToken: token, updatedAt: Timestamp.now() }, { merge: true });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const isOwner = useCallback(() => !!data?.plan && data.plan.ownerId === userId, [data, userId]);

  return {
    plan: data?.plan ?? null,
    members: data?.members ?? [],
    isLoading,
    error: error ? (error instanceof Error ? error.message : 'Failed to load plan') : null,
    isOwner,
    upsertItem: (i: PlanItem) => upsertItem.mutateAsync(i),
    removeItem: (id: string) => removeItem.mutateAsync(id),
    join: (token: string, displayName: string) => join.mutateAsync({ token, displayName }),
    removeMember: (uid: string) => removeMember.mutateAsync(uid),
    rename: (n: string) => rename.mutateAsync(n),
    rotateToken: (t: string) => rotateToken.mutateAsync(t),
  };
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd website && npx vitest run src/hooks/useSharedPlan.test.ts`
Expected: PASS.

- [ ] **Step 5: Typecheck the new files**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "sharedPlan|useSharedPlan" || echo "clean"`
Expected: `clean` (no new type errors in these files).

- [ ] **Step 6: Commit**

```bash
git add website/src/hooks/useSharedPlan.ts website/src/hooks/useSharedPlan.test.ts
git commit -m "feat(shared-plan): useSharedPlan hook with per-row LWW transaction + join"
```

---

## Task 4: `useSharedPlans` (list + create) and profile pointer

**Files:**
- Modify: `website/types.ts` (add `sharedPlanIds`)
- Create: `website/src/hooks/useSharedPlans.ts`

- [ ] **Step 1: Add the profile field**

Find the user profile interface in `website/types.ts` (the one with `givingBuckets: GivingBucket[]`) and add:

```typescript
  /** Ids of shared household plans this user belongs to. */
  sharedPlanIds?: string[];
```

- [ ] **Step 2: Implement the list+create hook**

```typescript
// website/src/hooks/useSharedPlans.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { doc, getDoc, setDoc, collection, Timestamp } from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import { newInviteToken } from '../lib/sharedPlanLogic';
import type { SharedPlan } from '../types/sharedPlan';

export function useSharedPlans() {
  const { db, userId, user } = useFirebaseData();
  const qc = useQueryClient();
  const key = ['sharedPlans', userId];

  const { data: plans = [], isLoading } = useQuery({
    queryKey: key,
    enabled: !!db && !!userId,
    queryFn: async (): Promise<{ id: string; name: string }[]> => {
      if (!db || !userId) return [];
      const userSnap = await getDoc(doc(db, 'users', userId));
      const ids: string[] = (userSnap.data()?.sharedPlanIds as string[]) || [];
      const out: { id: string; name: string }[] = [];
      for (const id of ids) {
        const snap = await getDoc(doc(db, 'shared_plans', id));
        if (snap.exists()) out.push({ id, name: (snap.data().name as string) || 'Shared plan' }); // dangling ids filtered
      }
      return out;
    },
  });

  const createPlan = useMutation({
    mutationFn: async (name: string): Promise<string> => {
      if (!db || !userId) throw new Error('Not authenticated');
      const ref = doc(collection(db, 'shared_plans'));
      const now = Date.now();
      const plan: Omit<SharedPlan, 'id'> = {
        name, ownerId: userId, createdAt: now, updatedAt: now, revision: 0,
        inviteToken: newInviteToken(), items: [],
      };
      await setDoc(ref, plan);
      await setDoc(doc(db, 'shared_plans', ref.id, 'members', userId), {
        role: 'owner', displayName: user?.displayName || 'You', joinedAt: Timestamp.now(),
        token: plan.inviteToken,
      });
      const userRef = doc(db, 'users', userId);
      const existing: string[] = ((await getDoc(userRef)).data()?.sharedPlanIds as string[]) || [];
      await setDoc(userRef, { sharedPlanIds: [...existing, ref.id] }, { merge: true });
      return ref.id;
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  return { plans, isLoading, createPlan: (n: string) => createPlan.mutateAsync(n) };
}
```

- [ ] **Step 3: Typecheck**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "useSharedPlans|types.ts" || echo "clean"`
Expected: `clean`.

- [ ] **Step 4: Commit**

```bash
git add website/types.ts website/src/hooks/useSharedPlans.ts
git commit -m "feat(shared-plan): useSharedPlans list+create; sharedPlanIds on profile"
```

---

## Task 5: SharedPlanView component (proportional, money-free, your-share)

**Files:**
- Create: `website/src/components/giving/SharedPlanView.tsx`

Renders the shared plan's items as proportional rows (charity/category name + weight control + assignee), shows each row's percentage via `weightsToPercents`, and a private "your share" column via `computeYourShare(items, personalTarget)` where `personalTarget` comes from the signed-in user's own profile (read with the existing `useProfile` hook — never written to the shared doc). Editing a row calls `upsertItem`. Adding a charity reuses the existing `ItemPicker` from `website/src/components/giving/ItemPicker.tsx`.

- [ ] **Step 1: Implement the component**

```tsx
// website/src/components/giving/SharedPlanView.tsx
import React from 'react';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { useProfile } from '../../hooks/useProfile';
import { weightsToPercents, computeYourShare } from '../../lib/sharedPlanLogic';
import type { PlanItem } from '../../types/sharedPlan';
import { InviteFamilyPanel } from './InviteFamilyPanel';

export const SharedPlanView: React.FC<{ planId: string }> = ({ planId }) => {
  const { plan, members, isLoading, isOwner, upsertItem, removeItem } = useSharedPlan(planId);
  const { profile } = useProfile();
  const personalTarget = (profile?.targetZakatAmount as number | null) ?? null;

  if (isLoading || !plan) return <div className="p-6 text-slate-500">Loading plan…</div>;

  const percents = weightsToPercents(plan.items);
  const shares = computeYourShare(plan.items, personalTarget);

  const setWeight = (item: PlanItem, weight: number) =>
    upsertItem({ ...item, weight, updatedAt: Date.now(), updatedBy: '' /* stamped in hook */ });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">{plan.name}</h2>
        <span className="text-sm text-slate-500">{members.length} member{members.length === 1 ? '' : 's'}</span>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500">
            <th>What we support</th><th>Share</th><th>Weight</th>
            {personalTarget != null && <th>Your share</th>}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {plan.items.map(item => (
            <tr key={item.id} className="border-t border-slate-200 dark:border-slate-700">
              <td className="py-2">{item.kind === 'charity' ? item.ref : item.ref.replace(/-/g, ' ')}</td>
              <td>{percents[item.id]}%</td>
              <td>
                <input type="number" min={0} value={item.weight}
                  onChange={e => setWeight(item, parseFloat(e.target.value) || 0)}
                  className="w-16 px-2 py-1 rounded border border-slate-300 dark:bg-slate-800" />
              </td>
              {personalTarget != null && <td>${(shares[item.id] || 0).toLocaleString()}</td>}
              <td><button onClick={() => removeItem(item.id)} className="text-slate-400 hover:text-red-500">✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {personalTarget == null && (
        <p className="text-sm text-amber-700">Set your zakat target on your personal plan to see your share of each.</p>
      )}

      <InviteFamilyPanel planId={planId} canManage={isOwner()} />
    </div>
  );
};
```

> Adding new charities/categories: wire the existing `ItemPicker` to call `upsertItem` with a fresh `{ id: crypto.randomUUID(), kind, ref, weight: 1, assigneeUid: null, updatedAt: Date.now(), updatedBy: '' }`. Place an "Add charity" button above the table that opens `ItemPicker`; mirror how `UnifiedAllocationView.tsx` invokes `ItemPicker` today.

- [ ] **Step 2: Typecheck**

Run: `cd website && npx tsc --noEmit 2>&1 | grep "SharedPlanView" || echo "clean"`
Expected: `clean` (note: `InviteFamilyPanel` lands in Task 6 — if running tasks in order, create a temporary stub export first, or implement Task 6 before typechecking).

- [ ] **Step 3: Commit**

```bash
git add website/src/components/giving/SharedPlanView.tsx
git commit -m "feat(shared-plan): SharedPlanView — proportional rows + private your-share"
```

---

## Task 6: InviteFamilyPanel (link, rotate/revoke, members)

**Files:**
- Create: `website/src/components/giving/InviteFamilyPanel.tsx`
- Modify: `website/src/utils/analytics.ts` (add `trackInviteCreated`)

- [ ] **Step 1: Add the analytics helper**

In `website/src/utils/analytics.ts`, following the existing `trackEvent` helpers, add:

```typescript
export function trackInviteCreated(planId: string): void {
  trackEvent('invite_created', { plan_id: planId });
}
```

(If the file exports a generic `trackEvent(name, params)`, reuse it exactly as the other helpers do. Match the existing signature — do not invent a new logging path.)

- [ ] **Step 2: Implement the panel**

```tsx
// website/src/components/giving/InviteFamilyPanel.tsx
import React, { useState } from 'react';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { newInviteToken } from '../../lib/sharedPlanLogic';
import { trackInviteCreated } from '../../utils/analytics';

export const InviteFamilyPanel: React.FC<{ planId: string; canManage: boolean }> = ({ planId, canManage }) => {
  const { plan, members, rotateToken, removeMember } = useSharedPlan(planId);
  const [copied, setCopied] = useState(false);
  if (!plan) return null;

  const link = `${window.location.origin}/plan/join/${planId}/${plan.inviteToken}`;

  const share = async () => {
    trackInviteCreated(planId);
    if (navigator.share) {
      await navigator.share({ title: `${plan.name} — plan giving together`, url: link }).catch(() => {});
    } else {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Invite family</h3>
        <button onClick={share} className="px-3 py-1.5 rounded bg-emerald-600 text-white text-sm">
          {copied ? 'Link copied' : 'Invite family'}
        </button>
      </div>
      <ul className="text-sm text-slate-600 dark:text-slate-300">
        {members.map(m => (
          <li key={m.uid} className="flex justify-between py-1">
            <span>{m.displayName}{m.role === 'owner' ? ' (owner)' : ''}</span>
            {canManage && m.role !== 'owner' && (
              <button onClick={() => removeMember(m.uid)} className="text-slate-400 hover:text-red-500">Remove</button>
            )}
          </li>
        ))}
      </ul>
      {canManage && (
        <button onClick={() => rotateToken(newInviteToken())} className="text-xs text-slate-500 hover:underline">
          Revoke &amp; regenerate link
        </button>
      )}
    </div>
  );
};
```

- [ ] **Step 3: Typecheck**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "InviteFamilyPanel|SharedPlanView" || echo "clean"`
Expected: `clean`.

- [ ] **Step 4: Commit**

```bash
git add website/src/components/giving/InviteFamilyPanel.tsx website/src/utils/analytics.ts
git commit -m "feat(shared-plan): InviteFamilyPanel — share link, rotate, member management"
```

---

## Task 7: JoinPlanPage (public preview + join) and route

**Files:**
- Create: `website/pages/JoinPlanPage.tsx`
- Modify: `website/App.tsx` (route)
- Modify: `website/src/utils/analytics.ts` (add `trackPlanPreview`, `trackPlanJoined`)

- [ ] **Step 1: Add analytics helpers**

```typescript
export function trackPlanPreview(planId: string): void {
  trackEvent('plan_preview_view', { plan_id: planId });
}
export function trackPlanJoined(planId: string): void {
  trackEvent('plan_joined', { plan_id: planId });
}
```

- [ ] **Step 2: Implement the page**

```tsx
// website/pages/JoinPlanPage.tsx
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Navigate } from 'react-router-dom';
import { doc, getDoc, collection, getDocs } from 'firebase/firestore';
import { db } from '../src/auth/firebase';
import { useFirebaseData } from '../src/auth/FirebaseProvider';
import { useSharedPlan } from '../src/hooks/useSharedPlan';
import { weightsToPercents } from '../src/lib/sharedPlanLogic';
import { trackPlanPreview, trackPlanJoined } from '../src/utils/analytics';
import type { SharedPlan, PlanMember } from '../src/types/sharedPlan';

export const JoinPlanPage: React.FC = () => {
  const { planId, token } = useParams<{ planId: string; token: string }>();
  const { userId, user } = useFirebaseData();
  const navigate = useNavigate();
  const { join } = useSharedPlan(planId ?? null);
  const [plan, setPlan] = useState<SharedPlan | null>(null);
  const [members, setMembers] = useState<PlanMember[]>([]);
  const [state, setState] = useState<'loading' | 'ok' | 'notfound'>('loading');

  // Public read of the money-free plan for the preview.
  useEffect(() => {
    if (!db || !planId) return;
    (async () => {
      const snap = await getDoc(doc(db, 'shared_plans', planId));
      if (!snap.exists()) { setState('notfound'); return; }
      const p = { id: snap.id, ...(snap.data() as Omit<SharedPlan, 'id'>) };
      if (p.inviteToken !== token) { setState('notfound'); return; } // revoked/old link
      const mem = await getDocs(collection(db, 'shared_plans', planId, 'members'));
      setPlan(p);
      setMembers(mem.docs.map(d => ({ uid: d.id, ...(d.data() as Omit<PlanMember, 'uid'>) })));
      setState('ok');
      trackPlanPreview(planId);
    })();
  }, [planId, token]);

  if (state === 'notfound') return <Navigate to="/" replace />;
  if (state === 'loading' || !plan) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading…</div>;

  const percents = weightsToPercents(plan.items);
  const alreadyMember = !!userId && members.some(m => m.uid === userId);

  const onJoin = async () => {
    if (!userId) { navigate('/profile'); return; } // sign-in surface; returns here after auth
    await join(token!, user?.displayName || 'Family member');
    trackPlanJoined(planId!);
    navigate('/profile');
  };

  return (
    <div className="min-h-screen max-w-2xl mx-auto px-4 py-12">
      <p className="text-sm uppercase tracking-wide text-emerald-700">You're invited</p>
      <h1 className="text-3xl font-semibold mb-2">The {plan.name} is planning their giving</h1>
      <p className="text-slate-600 mb-8">Here's how they're splitting it. Join to add your own giving.</p>

      <ul className="divide-y divide-slate-200 dark:divide-slate-700 mb-8">
        {plan.items.map(i => (
          <li key={i.id} className="flex justify-between py-2">
            <span>{i.kind === 'charity' ? i.ref : i.ref.replace(/-/g, ' ')}</span>
            <span className="text-slate-500">{percents[i.id]}%</span>
          </li>
        ))}
      </ul>

      <button onClick={onJoin} className="px-5 py-2.5 rounded-lg bg-emerald-600 text-white font-semibold">
        {alreadyMember ? 'Open this plan' : userId ? 'Join your family' : 'Sign in to join your family'}
      </button>
    </div>
  );
};
```

> Note: charity rows show the `ref` (EIN) verbatim here. Optionally enrich to the charity name via the existing `useCharities` lookup, mirroring how other pages resolve EIN→name; keep it a non-blocking enhancement.

- [ ] **Step 3: Add the route**

In `website/App.tsx`, after the other public routes, add:

```tsx
            <Route path="/plan/join/:planId/:token" element={<JoinPlanPage />} />
```

and import it at the top: `import { JoinPlanPage } from './pages/JoinPlanPage';`

- [ ] **Step 4: Typecheck**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "JoinPlanPage|App.tsx" || echo "clean"`
Expected: `clean`.

- [ ] **Step 5: Commit**

```bash
git add website/pages/JoinPlanPage.tsx website/App.tsx website/src/utils/analytics.ts
git commit -m "feat(shared-plan): public preview + join page and route"
```

---

## Task 8: Plan switcher on ProfilePage

**Files:**
- Create: `website/src/components/giving/PlanSwitcher.tsx`
- Modify: `website/pages/ProfilePage.tsx`

- [ ] **Step 1: Implement the switcher**

```tsx
// website/src/components/giving/PlanSwitcher.tsx
import React from 'react';
import { useSharedPlans } from '../../hooks/useSharedPlans';

export const PlanSwitcher: React.FC<{
  selected: string | null;                 // null = personal plan
  onSelect: (planId: string | null) => void;
}> = ({ selected, onSelect }) => {
  const { plans, createPlan } = useSharedPlans();

  const onCreate = async () => {
    const name = window.prompt('Name this shared plan (e.g., "Khan Family")');
    if (!name) return;
    const id = await createPlan(name);
    onSelect(id);
  };

  return (
    <div className="flex items-center gap-2 mb-6">
      <button onClick={() => onSelect(null)}
        className={`px-3 py-1.5 rounded-full text-sm ${selected === null ? 'bg-emerald-600 text-white' : 'border border-slate-300'}`}>
        My plan
      </button>
      {plans.map(p => (
        <button key={p.id} onClick={() => onSelect(p.id)}
          className={`px-3 py-1.5 rounded-full text-sm ${selected === p.id ? 'bg-emerald-600 text-white' : 'border border-slate-300'}`}>
          {p.name}
        </button>
      ))}
      <button onClick={onCreate} className="px-3 py-1.5 rounded-full text-sm border border-dashed border-slate-300 text-slate-500">
        + Shared plan
      </button>
    </div>
  );
};
```

- [ ] **Step 2: Wire into ProfilePage**

In `website/pages/ProfilePage.tsx`: add `const [selectedPlan, setSelectedPlan] = useState<string | null>(null);`, render `<PlanSwitcher selected={selectedPlan} onSelect={setSelectedPlan} />` above the giving section, and conditionally render `selectedPlan ? <SharedPlanView planId={selectedPlan} /> : <existing personal plan JSX>`. Import both components. Do not modify the existing personal plan rendering — only gate it behind the `selectedPlan === null` branch.

- [ ] **Step 3: Typecheck + build**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "ProfilePage|PlanSwitcher" || echo "clean"` then `cd website && npm run build > /tmp/sp-build.log 2>&1; echo exit=$?`
Expected: `clean`, build `exit=0`.

- [ ] **Step 4: Commit**

```bash
git add website/src/components/giving/PlanSwitcher.tsx website/pages/ProfilePage.tsx
git commit -m "feat(shared-plan): plan switcher on profile (personal vs shared)"
```

---

## Task 9: End-to-end test (create → invite → preview → join)

**Files:**
- Create: `website/tests/e2e/shared-plan.spec.ts`

This e2e mirrors the existing Playwright pattern (`tests/e2e/intro-presentation.spec.ts`). It requires an authenticated session; reuse whatever auth bootstrap other authenticated e2e specs use (e.g., the test user seeded in `tests/e2e/`), or skip the join leg with `test.skip` if no auth fixture exists and assert the public preview only.

- [ ] **Step 1: Write the e2e**

```typescript
// website/tests/e2e/shared-plan.spec.ts
import { test, expect } from '@playwright/test';

// Public preview must render without authentication and without exposing money.
test('join page shows a read-only money-free preview', async ({ page }) => {
  // Seed a known plan id+token via the app's create flow in an authed context,
  // OR point at a fixture plan. Here we assert the preview surface and CTA.
  // Replace PLAN_ID/TOKEN with values produced by the create step or a fixture.
  const PLAN_ID = process.env.E2E_PLAN_ID;
  const TOKEN = process.env.E2E_PLAN_TOKEN;
  test.skip(!PLAN_ID || !TOKEN, 'no seeded plan; set E2E_PLAN_ID/E2E_PLAN_TOKEN');

  await page.goto(`/plan/join/${PLAN_ID}/${TOKEN}`);
  await expect(page.getByText('planning their giving', { exact: false })).toBeVisible();
  // Money must never appear in the preview.
  await expect(page.locator('body')).not.toContainText('$');
  await expect(page.getByRole('button', { name: /join your family|sign in to join/i })).toBeVisible();
});

// Revoked/old token → bounced home.
test('stale invite token redirects home', async ({ page }) => {
  await page.goto('/plan/join/nonexistent/badtoken');
  await expect(page).toHaveURL(/\/$/);
});
```

- [ ] **Step 2: Run the e2e (chromium)**

Run: `cd website && npx playwright test shared-plan --project=chromium --reporter=line`
Expected: the stale-token test PASSES; the preview test PASSES or SKIPS (if no seeded plan). No failures.

- [ ] **Step 3: Commit**

```bash
git add website/tests/e2e/shared-plan.spec.ts
git commit -m "test(shared-plan): e2e for public preview + stale-token redirect"
```

---

## Task 10: Deploy note + manual verification checklist

**Files:** none (verification only)

- [ ] **Step 1: Confirm rules ship with deploy**

`website/firebase.json` already maps `firestore.rules`. The new rules deploy when the site deploys (`firebase deploy`). **Do not deploy from this plan** — deploy is a separate, user-initiated step (the repo convention is no pushes/deploys without explicit instruction).

- [ ] **Step 2: Manual smoke (against a preview build, signed in)**

Run `cd website && npm run build && npx vite preview --port 4173`, then in a browser:
- Profile → "+ Shared plan" → name it → switcher shows it.
- Add 2 charities, set weights → percentages update; "your share" appears if a personal zakat target is set.
- "Invite family" → copy link → open in a private window (signed out) → preview renders, **no dollar signs**, CTA says "Sign in to join."
- Sign in via the link → becomes a member → lands on the plan.
- Owner: "Revoke & regenerate link" → old link now redirects home.

- [ ] **Step 3: Final commit (if any verification fixes were needed)**

```bash
git add -A
git commit -m "fix(shared-plan): address manual verification findings"
```

---

## Self-review notes (coverage vs spec)

- Proportions-shared / dollars-personal → Tasks 1 (`computeYourShare`), 5 (no dollar fields written), rules (no money in doc). ✓
- Per-row LWW + revision + history → Task 1 (`mergeItem`), Task 3 (`applyItemTransaction` + transaction). ✓
- Owner/editor roles, invite, revoke, remove → Tasks 3, 6; rules Task 2. ✓
- Public pre-signup preview, token gates join only → Task 7 + rules Task 2. ✓
- Separate plan + switcher, no migration → Tasks 4, 8. ✓
- Success-metric instrumentation (invite_created, plan_preview_view, plan_joined) → Tasks 6, 7. ✓
- Edge cases: revoked link (Task 7 token check), dangling sharedPlanIds (Task 4 filter), no personal target (Task 5 nudge), item cap — **add a guard in Task 5's add-charity handler: refuse beyond 100 items** (matches spec edge case).
- Phase 2 (combined dollar rollups, Ramadan prompt, owner transfer) intentionally excluded.

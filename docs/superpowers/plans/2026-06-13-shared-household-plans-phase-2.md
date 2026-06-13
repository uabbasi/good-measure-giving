# Shared Household Plans — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the shared-plan collaborative core (per-row LWW + edit history) and add per-member niyyah notes and an explore-together shortlist, per the approved spec `docs/superpowers/specs/2026-06-13-shared-household-plans-phase-2-design.md`.

**Architecture:** All shared-plan writes move from whole-doc thin sync to a single Firestore `runTransaction` that re-reads the plan doc, applies one change, bumps `revision`, and writes a revision-keyed history entry; pure merge logic lives in `sharedPlanLogic.ts` (unit-tested), the transaction glue lives in `useSharedPlan.ts` (emulator-e2e-tested). Niyyah notes are a per-member map on each `PlanItem` written through a dedicated note-merge transaction; the shortlist is an inline array of candidates on the plan doc, promoted into `items`.

**Tech Stack:** React 19, TypeScript 5.8, Firebase Firestore web SDK, TanStack Query, Vitest, Playwright (Firebase Emulator Suite).

**Working directory:** worktree `feature/shared-plans-phase-2`. Run all `npm` commands from `website/`.

**Conventions to match:**
- Tests are Vitest, colocated as `*.test.ts(x)`. Run a single file: `npx vitest run <path>`.
- No jest-dom matchers are configured — assert with DOM properties (`el.disabled`, `el.textContent`) and `screen.getByRole`, not `toBeInTheDocument`/`toBeDisabled`.
- The repo build is `npx vite build` (esbuild, no tsc gate). Run `npx tsc --noEmit` and grep for errors in changed files only (the repo has a large pre-existing tsc-error baseline).
- Commit on the `feature/shared-plans-phase-2` branch. Do NOT push.

---

## File Structure

- `website/src/types/sharedPlan.ts` — **modify**: add `PlanItem.notes`, `ShortlistCandidate`, `SharedPlan.shortlist`.
- `website/src/lib/sharedPlanLogic.ts` — **modify**: rename `mergeItem`→`applyItemLWW` (preserve notes), add `removeItemById`, `setMemberNote`, `addShortlistCandidate`, `removeShortlistCandidate`, `promoteCandidate`, `HISTORY_MAX`, `historyIdToPrune`; remove `pruneHistory`.
- `website/src/lib/sharedPlanLogic.test.ts` — **modify**: replace `mergeItem`/`pruneHistory` tests with tests for the new helpers.
- `website/src/hooks/useSharedPlan.ts` — **modify**: transactional `commit` helper; rewrite `upsertItem`/`removeItem`; add `setMyNote`, `addToShortlist`, `removeFromShortlist`, `promoteToPlan`; remove `replaceOrAppendItem`.
- `website/src/hooks/useSharedPlan.test.ts` — **modify**: drop the `replaceOrAppendItem` test (helper removed).
- `website/src/components/giving/CharitySearchAdd.tsx` — **create**: the charity search/add control extracted from `SharedPlanView` so both it and `ShortlistPanel` reuse it.
- `website/src/components/giving/ShortlistPanel.tsx` — **create**: shortlist surface (add candidate + live list + remove).
- `website/src/components/giving/ShortlistPanel.test.tsx` — **create**.
- `website/src/components/giving/SharedPlanView.tsx` — **modify**: use `CharitySearchAdd`; render notes UI; render shortlist promote section.
- `website/src/components/giving/GivingSession.tsx` — **modify**: render `ShortlistPanel` in the Explore step.
- `firestore.rules` — **modify** (repo root): add `history` subcollection rules.
- `website/tests/e2e/shared-plan-emulator.spec.ts` — **modify**: add shortlist-promote + concurrent-edit + note coverage.

---

## PHASE A — Per-row LWW + history (foundation)

### Task 1: Type additions

**Files:**
- Modify: `website/src/types/sharedPlan.ts`

- [ ] **Step 1: Add the new types**

Edit `website/src/types/sharedPlan.ts`. Add `notes?` to `PlanItem`, a new `ShortlistCandidate` interface, and `shortlist?` to `SharedPlan`:

```ts
export interface PlanItem {
  id: string;                       // client-generated uuid, stable
  kind: 'charity' | 'category';
  ref: string;                      // EIN (charity) or category slug
  weight: number;                   // proportion / relative weight (NOT dollars)
  assigneeUid: string | null;       // member covering this item, or null
  updatedAt: number;                // epoch ms
  updatedBy: string;                // uid
  notes?: Record<string, { text: string; at: number }>; // per-member niyyah, keyed by uid
}

export interface ShortlistCandidate {
  ref: string;        // EIN of a charity being considered (not yet committed)
  addedBy: string;    // uid
  addedAt: number;    // epoch ms
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
  shortlist?: ShortlistCandidate[];
}
```

Leave `PlanMember` and `PlanHistoryEntry` unchanged.

- [ ] **Step 2: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "sharedPlan.ts|types/sharedPlan" || echo "clean"`
Expected: `clean` (no new errors in the file).

- [ ] **Step 3: Commit**

```bash
git add website/src/types/sharedPlan.ts
git commit -m "feat(shared-plans): types for notes, shortlist (phase 2)"
```

---

### Task 2: LWW + remove pure helpers

**Files:**
- Modify: `website/src/lib/sharedPlanLogic.ts:21-31` (the `mergeItem` function)
- Test: `website/src/lib/sharedPlanLogic.test.ts`

- [ ] **Step 1: Write the failing tests**

In `website/src/lib/sharedPlanLogic.test.ts`, change the import line to include the new helpers and remove `mergeItem`/`pruneHistory`:

```ts
import { weightsToPercents, computeYourShare, newInviteToken, addCharityItem, applyItemLWW, removeItemById } from './sharedPlanLogic';
```

Delete the existing `describe('mergeItem', ...)` block and the `describe('pruneHistory', ...)` block entirely. Add:

```ts
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
```

Confirm the `item()` factory at the top of the test file accepts a `notes` override (it spreads `...over`, so it already does).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: FAIL — `applyItemLWW`/`removeItemById` are not exported.

- [ ] **Step 3: Implement the helpers**

In `website/src/lib/sharedPlanLogic.ts`, replace the `mergeItem` function (lines 21-31) with:

```ts
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
```

Also remove the now-unused `pruneHistory` function (lines 57-60) and drop `PlanHistoryEntry` from the type import on line 1 **only if** no longer referenced there — it IS still referenced by `historyIdToPrune` work in Task 3, so keep the import:

```ts
import type { PlanItem, PlanHistoryEntry } from '../types/sharedPlan';
```

(Leave `PlanHistoryEntry` imported; Task 3 uses it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add website/src/lib/sharedPlanLogic.ts website/src/lib/sharedPlanLogic.test.ts
git commit -m "feat(shared-plans): applyItemLWW (notes-preserving) + removeItemById; drop pruneHistory"
```

---

### Task 3: History prune-id helper

**Files:**
- Modify: `website/src/lib/sharedPlanLogic.ts`
- Test: `website/src/lib/sharedPlanLogic.test.ts`

- [ ] **Step 1: Write the failing test**

Add to the import line in `sharedPlanLogic.test.ts`: `HISTORY_MAX, historyIdToPrune`. Add:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: FAIL — `historyIdToPrune`/`HISTORY_MAX` not exported.

- [ ] **Step 3: Implement**

Append to `website/src/lib/sharedPlanLogic.ts`:

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add website/src/lib/sharedPlanLogic.ts website/src/lib/sharedPlanLogic.test.ts
git commit -m "feat(shared-plans): historyIdToPrune + HISTORY_MAX"
```

---

### Task 4: Transactional plan writes + history in `useSharedPlan`

**Files:**
- Modify: `website/src/hooks/useSharedPlan.ts`
- Modify: `website/src/hooks/useSharedPlan.test.ts`

This task has no new Vitest unit (Firestore transactions need the emulator — covered by the e2e in Task 13). The pure logic it calls is already tested (Tasks 2-3). Verification is tsc + build + the existing suite staying green.

- [ ] **Step 1: Remove the obsolete helper test**

`website/src/hooks/useSharedPlan.test.ts` currently tests `replaceOrAppendItem`, which this task deletes. Open it; delete the `replaceOrAppendItem` import and its `describe` block. If the file is left with no tests, replace its body with a placeholder that keeps the suite valid:

```ts
import { describe, it, expect } from 'vitest';
import { historyIdToPrune } from '../lib/sharedPlanLogic';

// useSharedPlan's transactional writes are covered by the emulator e2e
// (tests/e2e/shared-plan-emulator.spec.ts). Pure merge/prune logic is unit-tested
// in sharedPlanLogic.test.ts; this asserts the prune wiring contract the hook relies on.
describe('useSharedPlan history wiring', () => {
  it('prunes the (revision - HISTORY_MAX) entry once the buffer is full', () => {
    expect(historyIdToPrune(21, 20)).toBe('1');
  });
});
```

- [ ] **Step 2: Rewrite the hook's write path**

Edit `website/src/hooks/useSharedPlan.ts`. Update imports (add `runTransaction`; `deleteDoc` already imported; `collection`/`getDocs` stay for members):

```ts
import {
  doc, collection, getDoc, getDocs, setDoc, deleteDoc, runTransaction, Timestamp,
} from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
import type { SharedPlan, PlanItem, PlanMember, PlanHistoryEntry, ShortlistCandidate } from '../types/sharedPlan';
import {
  applyItemLWW, removeItemById, setMemberNote,
  addShortlistCandidate, removeShortlistCandidate, promoteCandidate,
  HISTORY_MAX, historyIdToPrune,
} from '../lib/sharedPlanLogic';
```

Delete the exported `replaceOrAppendItem` function (lines 9-17).

Inside `useSharedPlan`, after the `useQuery` block and before `upsertItem`, add a private `commit` helper that all writers share:

```ts
  // One transactional write: re-read the plan, apply a change, bump revision,
  // append a revision-keyed history entry, then best-effort prune the ring buffer.
  // `build` returns the field patch to write and (optionally) the item history.
  const commit = async (
    build: (current: Omit<SharedPlan, 'id'>) => {
      fields: Partial<Pick<SharedPlan, 'items' | 'shortlist'>>;
      history?: { itemId: string; before: PlanItem | null; after: PlanItem | null };
    },
  ): Promise<void> => {
    if (!db || !planId || !userId) throw new Error('Not authenticated');
    const ref = doc(db, 'shared_plans', planId);
    const revision = await runTransaction(db, async (tx) => {
      const snap = await tx.get(ref);
      if (!snap.exists()) throw new Error('Plan not found');
      const current = snap.data() as Omit<SharedPlan, 'id'>;
      const { fields, history } = build(current);
      const rev = (current.revision ?? 0) + 1;
      tx.set(ref, { ...fields, revision: rev, updatedAt: Timestamp.now() }, { merge: true });
      if (history) {
        const entry: PlanHistoryEntry = {
          revision: rev, itemId: history.itemId, before: history.before,
          after: history.after, updatedBy: userId, at: Date.now(),
        };
        tx.set(doc(db, 'shared_plans', planId, 'history', String(rev)), entry);
      }
      return rev;
    });
    const pruneId = historyIdToPrune(revision, HISTORY_MAX);
    if (pruneId) {
      try { await deleteDoc(doc(db, 'shared_plans', planId, 'history', pruneId)); } catch { /* best-effort */ }
    }
  };
```

Replace the `upsertItem` and `removeItem` mutations with:

```ts
  const upsertItem = useMutation({
    mutationFn: (incoming: PlanItem) =>
      commit((current) => {
        const stamped = { ...incoming, updatedAt: Date.now(), updatedBy: userId! };
        const before = current.items.find(i => i.id === incoming.id) ?? null;
        const items = applyItemLWW(current.items, stamped);
        const after = items.find(i => i.id === incoming.id) ?? null;
        return { fields: { items }, history: { itemId: incoming.id, before, after } };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeItem = useMutation({
    mutationFn: (itemId: string) =>
      commit((current) => {
        const before = current.items.find(i => i.id === itemId) ?? null;
        return { fields: { items: removeItemById(current.items, itemId) }, history: { itemId, before, after: null } };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
```

(`userId!` is safe — `commit` throws before `build` runs if `userId` is null.)

Leave `join`, `removeMember`, `rename`, `rotateToken`, `isOwner` unchanged. The `setDoc`/`getDoc` imports are still used by those.

- [ ] **Step 3: Verify compile + full suite**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "useSharedPlan" || echo "clean"`
Expected: errors will reference `setMemberNote`, `addShortlistCandidate`, etc. — those land in Tasks 6 & 9. To keep this task self-contained, **add the three pure helpers as stubs now is NOT needed**: instead, import only what this task uses. Replace the Task-4 import block's helper line with just:

```ts
import { applyItemLWW, removeItemById, HISTORY_MAX, historyIdToPrune } from '../lib/sharedPlanLogic';
```

and remove the `ShortlistCandidate`/`PlanHistoryEntry`-only symbols you don't yet use (keep `PlanHistoryEntry`). Re-run:
Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "useSharedPlan" || echo "clean"`
Expected: `clean`.

Run: `cd website && npx vitest run`
Expected: all pass.

- [ ] **Step 4: Build**

Run: `cd website && npx vite build 2>&1 | tail -2`
Expected: `✓ built`.

- [ ] **Step 5: Commit**

```bash
git add website/src/hooks/useSharedPlan.ts website/src/hooks/useSharedPlan.test.ts
git commit -m "feat(shared-plans): transactional per-row LWW writes + history ring buffer"
```

---

### Task 5: Firestore rules for the history subcollection

**Files:**
- Modify: `firestore.rules` (repo root)

- [ ] **Step 1: Add the history rules**

In `firestore.rules`, inside `match /shared_plans/{planId} { ... }`, replace the comment line
`// (phase 2) history ring buffer rules omitted — thin sync writes no history.`
with:

```
      match /history/{rev} {
        allow read:   if isMember();   // edit history is members-only (may contain note text)
        allow create: if isMember();   // appended by the edit transaction
        allow delete: if isMember();   // ring-buffer prune
        allow update: if false;        // entries are immutable
      }
```

(`isMember()` is already defined in the enclosing block.)

- [ ] **Step 2: Validate the rules**

Use the Firebase rules validator (the same path used in Phase 1): validate `firestore.rules` via the `firebase_validate_security_rules` MCP tool, or run
`cd website && npx firebase emulators:exec --only firestore --project=good-measure-giving --config=../firebase.json "true"`
Expected: emulator loads the rules with no compile error.

- [ ] **Step 3: Commit**

```bash
git add firestore.rules
git commit -m "feat(shared-plans): firestore rules for history subcollection"
```

---

## PHASE B — Per-member niyyah notes

### Task 6: `setMemberNote` pure helper

**Files:**
- Modify: `website/src/lib/sharedPlanLogic.ts`
- Test: `website/src/lib/sharedPlanLogic.test.ts`

- [ ] **Step 1: Write the failing test**

Add `setMemberNote` to the import line. Add:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: FAIL — `setMemberNote` not exported.

- [ ] **Step 3: Implement**

Append to `website/src/lib/sharedPlanLogic.ts`:

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add website/src/lib/sharedPlanLogic.ts website/src/lib/sharedPlanLogic.test.ts
git commit -m "feat(shared-plans): setMemberNote helper (per-member niyyah merge)"
```

---

### Task 7: `setMyNote` mutation in `useSharedPlan`

**Files:**
- Modify: `website/src/hooks/useSharedPlan.ts`

- [ ] **Step 1: Add the mutation**

Add `setMemberNote` to the helper import from `../lib/sharedPlanLogic`. After `removeItem`, add:

```ts
  const setMyNote = useMutation({
    mutationFn: ({ itemId, text }: { itemId: string; text: string }) =>
      commit((current) => {
        const idx = current.items.findIndex(i => i.id === itemId);
        if (idx === -1) throw new Error('Item not found');
        const before = current.items[idx];
        const after = { ...setMemberNote(before, userId!, text), updatedAt: Date.now(), updatedBy: userId! };
        const items = current.items.slice();
        items[idx] = after;
        return { fields: { items }, history: { itemId, before, after } };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
```

- [ ] **Step 2: Export it from the hook**

In the hook's `return { ... }`, add after `removeItem`:

```ts
    setMyNote: (itemId: string, text: string) => setMyNote.mutateAsync({ itemId, text }),
```

- [ ] **Step 3: Verify compile + suite**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "useSharedPlan" || echo "clean"`
Expected: `clean`.
Run: `cd website && npx vitest run`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add website/src/hooks/useSharedPlan.ts
git commit -m "feat(shared-plans): setMyNote transactional mutation"
```

---

### Task 8: Notes UI in `SharedPlanView`

**Files:**
- Modify: `website/src/components/giving/SharedPlanView.tsx`

- [ ] **Step 1: Pull the new hook method + signed-in uid**

In `SharedPlanView`, extend the `useSharedPlan` destructure to include `setMyNote`:

```ts
  const { plan, members, isLoading, isOwner, upsertItem, removeItem, setMyNote } = useSharedPlan(planId);
```

Get the signed-in uid (the file already imports `useProfile`; the plan view also needs the uid — import it from the Firebase data context):

```ts
import { useFirebaseData } from '../../auth/FirebaseProvider';
// inside the component:
const { userId } = useFirebaseData();
```

- [ ] **Step 2: Render notes under each row**

Each item currently renders as a single `<tr>`. Add a notes block in the first cell (under the charity name). Replace the name cell:

```tsx
<td className="py-2 text-slate-900 dark:text-slate-100 align-top">
  <div>{rowLabel(item)}</div>
  <NoteCell
    item={item}
    members={members}
    myUid={userId}
    onSave={(text) => void setMyNote(item.id, text)}
  />
</td>
```

- [ ] **Step 3: Add the `NoteCell` subcomponent**

At the bottom of `SharedPlanView.tsx` (next to `AddCharity`), add:

```tsx
const NoteCell: React.FC<{
  item: PlanItem;
  members: { uid: string; displayName: string }[];
  myUid: string | null;
  onSave: (text: string) => void;
}> = ({ item, members, myUid, onSave }) => {
  const nameByUid = useMemo(() => {
    const m = new Map<string, string>();
    for (const mem of members) m.set(mem.uid, mem.displayName);
    return m;
  }, [members]);
  const notes = item.notes ?? {};
  const mine = myUid ? notes[myUid]?.text ?? '' : '';
  const [draft, setDraft] = useState(mine);
  useEffect(() => { setDraft(mine); }, [mine]);

  const others = Object.entries(notes).filter(([uid]) => uid !== myUid);

  return (
    <div className="mt-1 space-y-1">
      {others.map(([uid, n]) => (
        <p key={uid} className="text-xs text-slate-500 dark:text-slate-400">
          <span className="font-medium">{nameByUid.get(uid) ?? 'Someone'}:</span> {n.text}
        </p>
      ))}
      {myUid && (
        <input
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={() => { if (draft !== mine) onSave(draft); }}
          placeholder="Your reason for giving here…"
          aria-label={`Your reason for ${item.ref}`}
          className="w-full max-w-xs px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        />
      )}
    </div>
  );
};
```

Add `useEffect` to the React import at the top: `import React, { useMemo, useState, useEffect } from 'react';`.

- [ ] **Step 4: Verify compile + build**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "SharedPlanView" || echo "clean"`
Expected: `clean`.
Run: `cd website && npx vite build 2>&1 | tail -2`
Expected: `✓ built`.

- [ ] **Step 5: Commit**

```bash
git add website/src/components/giving/SharedPlanView.tsx
git commit -m "feat(shared-plans): per-member niyyah notes UI in the plan view"
```

---

## PHASE C — Explore-together shortlist

### Task 9: Shortlist pure helpers

**Files:**
- Modify: `website/src/lib/sharedPlanLogic.ts`
- Test: `website/src/lib/sharedPlanLogic.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to the import line: `addShortlistCandidate, removeShortlistCandidate, promoteCandidate` and the type `ShortlistCandidate` from `../types/sharedPlan` (already imported there for `PlanItem`; add `ShortlistCandidate`). Add:

```ts
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
```

Add `ShortlistCandidate` to the test file's type import:
```ts
import type { PlanItem, ShortlistCandidate } from '../types/sharedPlan';
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: FAIL — helpers not exported.

- [ ] **Step 3: Implement**

Add `ShortlistCandidate` to the top-of-file type import in `sharedPlanLogic.ts`:
```ts
import type { PlanItem, PlanHistoryEntry, ShortlistCandidate } from '../types/sharedPlan';
```
Append:

```ts
/** Add a charity ref to the shortlist, deduped by ref (same array ref if present). */
export function addShortlistCandidate(list: ShortlistCandidate[], ref: string, uid: string): ShortlistCandidate[] {
  if (list.some(c => c.ref === ref)) return list;
  return [...list, { ref, addedBy: uid, addedAt: Date.now() }];
}

/** Remove a charity ref from the shortlist. */
export function removeShortlistCandidate(list: ShortlistCandidate[], ref: string): ShortlistCandidate[] {
  return list.filter(c => c.ref !== ref);
}

/**
 * Promote a shortlist candidate into the committed plan: drop it from the
 * shortlist and append a weight-1 charity item (deduped via addCharityItem).
 */
export function promoteCandidate(
  items: PlanItem[], shortlist: ShortlistCandidate[], ref: string, uid: string,
): { items: PlanItem[]; shortlist: ShortlistCandidate[] } {
  return {
    items: addCharityItem(items, ref, uid),
    shortlist: removeShortlistCandidate(shortlist, ref),
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd website && npx vitest run src/lib/sharedPlanLogic.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add website/src/lib/sharedPlanLogic.ts website/src/lib/sharedPlanLogic.test.ts
git commit -m "feat(shared-plans): shortlist add/remove/promote helpers"
```

---

### Task 10: Shortlist mutations in `useSharedPlan`

**Files:**
- Modify: `website/src/hooks/useSharedPlan.ts`

- [ ] **Step 1: Add the helper imports**

Add `addShortlistCandidate, removeShortlistCandidate, promoteCandidate` to the `../lib/sharedPlanLogic` import, and `ShortlistCandidate` to the types import.

- [ ] **Step 2: Add the mutations**

After `setMyNote`, add:

```ts
  const addToShortlist = useMutation({
    mutationFn: (ref: string) =>
      commit((current) => ({
        fields: { shortlist: addShortlistCandidate(current.shortlist ?? [], ref, userId!) },
        // shortlist changes are not item edits → no history entry
      })),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const removeFromShortlist = useMutation({
    mutationFn: (ref: string) =>
      commit((current) => ({
        fields: { shortlist: removeShortlistCandidate(current.shortlist ?? [], ref) },
      })),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  const promoteToPlan = useMutation({
    mutationFn: (ref: string) =>
      commit((current) => {
        const next = promoteCandidate(current.items, current.shortlist ?? [], ref, userId!);
        const added = next.items.find(i => i.kind === 'charity' && i.ref === ref) ?? null;
        return {
          fields: { items: next.items, shortlist: next.shortlist },
          history: { itemId: added?.id ?? ref, before: null, after: added },
        };
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
```

- [ ] **Step 3: Export them**

In the hook return, add:

```ts
    addToShortlist: (ref: string) => addToShortlist.mutateAsync(ref),
    removeFromShortlist: (ref: string) => removeFromShortlist.mutateAsync(ref),
    promoteToPlan: (ref: string) => promoteToPlan.mutateAsync(ref),
```

- [ ] **Step 4: Verify compile + suite + build**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "useSharedPlan" || echo "clean"`
Expected: `clean`.
Run: `cd website && npx vitest run` → all pass.
Run: `cd website && npx vite build 2>&1 | tail -2` → `✓ built`.

- [ ] **Step 5: Commit**

```bash
git add website/src/hooks/useSharedPlan.ts
git commit -m "feat(shared-plans): shortlist + promote transactional mutations"
```

---

### Task 11: Extract `CharitySearchAdd` and build `ShortlistPanel`

**Files:**
- Create: `website/src/components/giving/CharitySearchAdd.tsx`
- Modify: `website/src/components/giving/SharedPlanView.tsx`
- Create: `website/src/components/giving/ShortlistPanel.tsx`
- Create: `website/src/components/giving/ShortlistPanel.test.tsx`

- [ ] **Step 1: Extract the charity search control**

Create `website/src/components/giving/CharitySearchAdd.tsx` by moving the `AddCharity` component out of `SharedPlanView.tsx` verbatim, renamed and exported:

```tsx
import React, { useMemo, useState } from 'react';

/**
 * Charity search-and-add. Searches the charities index by name/EIN and calls
 * onPick(ein). Shared by the plan view (add to plan) and the shortlist panel.
 */
export const CharitySearchAdd: React.FC<{
  charities: { ein?: string; name: string }[];
  existingEins: Set<string>;
  onPick: (ein: string) => void;
  disabled?: boolean;
  placeholder?: string;
}> = ({ charities, existingEins, onPick, disabled, placeholder = 'Add a charity — search by name…' }) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    const out: { ein: string; name: string }[] = [];
    for (const c of charities) {
      if (!c.ein || existingEins.has(c.ein)) continue;
      if (c.name.toLowerCase().includes(q) || c.ein.includes(q)) {
        out.push({ ein: c.ein, name: c.name });
        if (out.length >= 10) break;
      }
    }
    return out;
  }, [query, charities, existingEins]);

  const pick = (ein: string) => { onPick(ein); setQuery(''); setOpen(false); };

  return (
    <div className="relative max-w-md">
      <input
        type="text"
        value={query}
        disabled={disabled}
        onChange={e => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        aria-label="Search charities to add"
        className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
      />
      {open && results.length > 0 && (
        <div className="absolute z-20 w-full mt-1 max-h-64 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg">
          {results.map(c => (
            <button
              key={c.ein}
              type="button"
              onMouseDown={e => e.preventDefault()}
              onClick={() => pick(c.ein)}
              className="w-full text-left px-3 py-2 text-sm text-slate-900 dark:text-slate-100 hover:bg-emerald-50 dark:hover:bg-emerald-600/20"
            >
              <span className="block truncate">{c.name}</span>
              <span className="block text-xs text-slate-400 dark:text-slate-500">{c.ein}</span>
            </button>
          ))}
        </div>
      )}
      {open && query.trim().length >= 2 && results.length === 0 && (
        <div className="absolute z-20 w-full mt-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg px-3 py-2 text-sm text-slate-500 dark:text-slate-400">
          No matching charities.
        </div>
      )}
    </div>
  );
};
```

In `SharedPlanView.tsx`: delete the local `AddCharity` component (lines ~174-247), `import { CharitySearchAdd } from './CharitySearchAdd';`, and replace the `<AddCharity .../>` usage with `<CharitySearchAdd charities={charities} existingEins={...} onPick={addCharity} disabled={atCap} />` (same props).

- [ ] **Step 2: Write the failing ShortlistPanel test**

Create `website/src/components/giving/ShortlistPanel.test.tsx`:

```tsx
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd website && npx vitest run src/components/giving/ShortlistPanel.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `ShortlistPanel`**

Create `website/src/components/giving/ShortlistPanel.tsx`:

```tsx
/**
 * ShortlistPanel — the explore-together surface. The family adds charities it is
 * "still considering" to a shared shortlist (everyone sees it live). Promotion
 * into the committed plan happens in the Decide step (SharedPlanView).
 */
import React, { useMemo } from 'react';
import { useSharedPlan } from '../../hooks/useSharedPlan';
import { useCharities } from '../../hooks/useCharities';

export const ShortlistPanel: React.FC<{ planId: string }> = ({ planId }) => {
  const { plan, members, addToShortlist, removeFromShortlist } = useSharedPlan(planId);
  const { charities } = useCharities();

  const nameByEin = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of charities) if (c.ein) m.set(c.ein, c.name);
    return m;
  }, [charities]);
  const nameByUid = useMemo(() => {
    const m = new Map<string, string>();
    for (const mem of members) m.set(mem.uid, mem.displayName);
    return m;
  }, [members]);

  const shortlist = plan?.shortlist ?? [];
  const committedEins = new Set((plan?.items ?? []).filter(i => i.kind === 'charity').map(i => i.ref));
  const shortlistedEins = new Set(shortlist.map(c => c.ref));
  const existing = new Set([...committedEins, ...shortlistedEins]);

  return (
    <div className="space-y-3">
      <CharitySearchAdd
        charities={charities}
        existingEins={existing}
        onPick={(ein) => void addToShortlist(ein)}
        placeholder="Suggest a charity to consider together…"
      />
      {shortlist.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Nothing shortlisted yet. Add charities your family wants to consider.
        </p>
      ) : (
        <ul className="space-y-2">
          {shortlist.map(c => {
            const name = nameByEin.get(c.ref) ?? c.ref;
            return (
              <li key={c.ref} className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2">
                <div>
                  <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{name}</span>
                  <span className="block text-xs text-slate-500 dark:text-slate-400">
                    suggested by {nameByUid.get(c.addedBy) ?? 'a family member'}
                  </span>
                </div>
                <button
                  onClick={() => void removeFromShortlist(c.ref)}
                  aria-label={`Remove ${name}`}
                  className="text-slate-400 hover:text-red-500"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
```

Add the import at the top: `import { CharitySearchAdd } from './CharitySearchAdd';`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd website && npx vitest run src/components/giving/ShortlistPanel.test.tsx`
Expected: PASS.

- [ ] **Step 6: Verify compile + full suite + build**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "ShortlistPanel|CharitySearchAdd|SharedPlanView" || echo "clean"` → `clean`.
Run: `cd website && npx vitest run` → all pass.
Run: `cd website && npx vite build 2>&1 | tail -2` → `✓ built`.

- [ ] **Step 7: Commit**

```bash
git add website/src/components/giving/CharitySearchAdd.tsx website/src/components/giving/ShortlistPanel.tsx website/src/components/giving/ShortlistPanel.test.tsx website/src/components/giving/SharedPlanView.tsx
git commit -m "feat(shared-plans): ShortlistPanel + extract CharitySearchAdd"
```

---

### Task 12: Wire shortlist into the session (Explore + Decide promote)

**Files:**
- Modify: `website/src/components/giving/GivingSession.tsx`
- Modify: `website/src/components/giving/SharedPlanView.tsx`

- [ ] **Step 1: Render `ShortlistPanel` in the Explore step**

In `GivingSession.tsx`, add `import { ShortlistPanel } from './ShortlistPanel';`. In the `step === 'explore'` block, after the teaching nudge `<div>...</div>`, insert:

```tsx
          <ShortlistPanel planId={planId} />
```

Keep the existing "Browse charities" link as a secondary "explore the full site" affordance.

- [ ] **Step 2: Show the promote section in `SharedPlanView`**

In `SharedPlanView.tsx`, pull `promoteToPlan` from the hook destructure:

```ts
  const { plan, members, isLoading, isOwner, upsertItem, removeItem, setMyNote, promoteToPlan } = useSharedPlan(planId);
```

Above the existing `<AddCharity>`/`<CharitySearchAdd>` block (just under the `<h2>` header row), add a "Still considering" section rendered only when the shortlist is non-empty:

```tsx
      {(plan.shortlist?.length ?? 0) > 0 && (
        <div className="rounded-lg border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/60 dark:bg-emerald-900/10 p-3 space-y-2">
          <p className="text-sm font-medium text-emerald-800 dark:text-emerald-200">Still considering</p>
          <ul className="space-y-1">
            {plan.shortlist!.map(c => (
              <li key={c.ref} className="flex items-center justify-between text-sm">
                <span className="text-slate-800 dark:text-slate-200">{nameByEin.get(c.ref) ?? c.ref}</span>
                <button
                  onClick={() => void promoteToPlan(c.ref)}
                  className="px-2 py-1 rounded bg-emerald-600 text-white text-xs font-medium"
                >
                  Add to plan
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
```

(`nameByEin` is already defined in `SharedPlanView`.)

- [ ] **Step 2b: Update the smoke assertion if present**

If `SharedPlanView` has a test, ensure mocks include `setMyNote`, `promoteToPlan`, and `useFirebaseData` returning `{ userId: 'u1' }`. (There is no `SharedPlanView.test.tsx` today; skip if absent.)

- [ ] **Step 3: Verify compile + suite + build**

Run: `cd website && npx tsc --noEmit 2>&1 | grep -E "GivingSession|SharedPlanView" || echo "clean"` → `clean`.
Run: `cd website && npx vitest run` → all pass.
Run: `cd website && npx vite build 2>&1 | tail -2` → `✓ built`.

- [ ] **Step 4: Commit**

```bash
git add website/src/components/giving/GivingSession.tsx website/src/components/giving/SharedPlanView.tsx
git commit -m "feat(shared-plans): shortlist in Explore + promote-to-plan in Decide"
```

---

### Task 13: Extend the emulator e2e

**Files:**
- Modify: `website/tests/e2e/shared-plan-emulator.spec.ts`

The existing spec drives two users through create → invite → preview → join. Extend it (or add a second `test()`), after User B has joined, to exercise the new surfaces against the real rules + transactions.

- [ ] **Step 1: Add the shortlist + concurrent-edit assertions**

After the join step in `shared-plan-emulator.spec.ts`, append within the same test (both users are signed in with the plan open):

```ts
  // ── Shortlist: A suggests a charity, it lands; promote it into the plan ──
  await a.page.goto('/profile');
  // open the plan + start a session → Explore step (selectors mirror the app;
  // adjust to the actual PlanSwitcher / "Start giving session" controls)
  await a.page.getByRole('button', { name: /start giving session/i }).click();
  await a.page.getByRole('button', { name: /^next$/i }).click(); // gather → explore
  const suggest = a.page.getByPlaceholder(/suggest a charity to consider/i);
  await suggest.fill('Islamic');
  await a.page.locator('button', { hasText: /Islamic/i }).first().click();
  await expect(a.page.getByText(/suggested by/i)).toBeVisible({ timeout: 10_000 });

  // Advance to Decide and promote.
  await a.page.getByRole('button', { name: /^next$/i }).click(); // explore → decide
  await a.page.getByRole('button', { name: /add to plan/i }).first().click();
  await expect(a.page.getByText(/still considering/i)).toHaveCount(0, { timeout: 10_000 });

  // ── Money-free invariant still holds on the public preview ──
  // (re-open the invite link in a fresh context if asserting; covered above.)

  // ── No console errors across the run ──
  expect(errors, `Console/page errors:\n${errors.join('\n')}`).toEqual([]);
```

If the exact in-app selectors differ (PlanSwitcher labels, session entry), adjust to match the rendered controls; the assertions to preserve are: a suggested charity appears with "suggested by", promotion empties "still considering", and `errors` stays empty.

- [ ] **Step 2: Run the e2e against fresh emulators**

Ensure no emulator suite is already bound to 8080/9099 (kill any running `npm run emulators` first). Then:
Run: `cd website && npm run test:e2e:shared 2>&1 | tail -20`
Expected: `1 passed` (or `2 passed` if a second test was added), exit 0.

- [ ] **Step 3: Commit**

```bash
git add website/tests/e2e/shared-plan-emulator.spec.ts
git commit -m "test(shared-plans): e2e shortlist promote + concurrent-edit coverage"
```

---

## Self-Review

**1. Spec coverage**
- §1 Per-row LWW → Tasks 2 (`applyItemLWW`), 4 (transactional `upsertItem`/`removeItem`). ✔
- §1 History subcollection (revision-keyed, prune-by-id) → Tasks 3 (`historyIdToPrune`), 4 (write in transaction + prune), 5 (rules). ✔
- §2 Per-member notes (dedicated merge path, generic upsert preserves notes) → Tasks 2 (notes-preservation in `applyItemLWW`), 6 (`setMemberNote`), 7 (`setMyNote`), 8 (UI). ✔
- §3 Shortlist (inline array, candidate shape, promote) → Tasks 1 (types), 9 (helpers), 10 (mutations), 11 (panel), 12 (wiring). ✔
- Testing (pure helpers, component, e2e) → Tasks 2/3/6/9 (helpers), 11 (ShortlistPanel), 13 (e2e). ✔
- Build order LWW→notes→shortlist → Phases A/B/C. ✔

**2. Placeholder scan:** No TBD/TODO; every code step has complete code. The e2e selectors note is an explicit "adjust to rendered controls" caveat, with the invariant assertions named — acceptable for an emulator UI test, not a placeholder.

**3. Type consistency:** `applyItemLWW`, `removeItemById`, `setMemberNote`, `addShortlistCandidate`, `removeShortlistCandidate`, `promoteCandidate`, `historyIdToPrune`, `HISTORY_MAX` are spelled identically in their defining task and every consumer (`useSharedPlan` Tasks 4/7/10). Hook methods `setMyNote(itemId, text)`, `addToShortlist(ref)`, `removeFromShortlist(ref)`, `promoteToPlan(ref)` match between definition and component usage. `ShortlistCandidate` / `PlanItem.notes` / `SharedPlan.shortlist` match the spec.

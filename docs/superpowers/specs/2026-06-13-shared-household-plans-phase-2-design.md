# Shared Household Plans — Phase 2 Design

**Status:** Approved design (brainstorm 2026-06-13). Builds on Phase 1 (Family
Giving Night), merged to local `main` at `181f7b7`, not yet deployed.

**Scope:** Three of the six deferred Phase-2 items from `TODOS.md`:
1. **Per-row last-write-wins (LWW) + history** — replace whole-doc thin sync with a
   transactional per-item write plus an edit-history ring buffer.
2. **Per-member niyyah / intention notes** — each member records their own "why we
   chose this" on a charity.
3. **Explore-together shortlist** — a shared "considering" list gathered during the
   session's Explore step, promoted into the plan during Decide.

Out of scope (still deferred): Ramadan-timed session CTA, combined household dollar
rollups, owner transfer.

---

## Motivation

Phase 1 shipped ritual-first on **thin sync** (whole-doc `setDoc` read-modify-write,
no transaction, no history). That was the right first bet — demand evidence said
"one person does all the giving," so concurrent multi-device editing was rare. Phase 2
hardens the collaborative core (LWW + history) and adds the two pieces that make a
*Family Giving Night* feel like a shared ritual rather than one person's data entry:
everyone gathers options together (shortlist) and records their own intention (niyyah).

The three items share one foundation: a **transactional per-item write path**. Niyyah
notes and shortlist mutations ride on it, so concurrent family edits never clobber.

---

## 1. Per-row LWW + history

### Today

`useSharedPlan.upsertItem` / `removeItem` do a whole-doc read-modify-write:
`getDoc` → `replaceOrAppendItem` (replace-by-id, no timestamp compare) → `setDoc(...,
{merge:true})` bumping `revision`. Two members editing different items in the same
window can clobber each other because the loser's whole `items` array overwrites the
winner's.

### Change

Move both mutations to a single Firestore **`runTransaction`**:

1. Re-read the plan doc inside the transaction.
2. Apply the change to exactly one `PlanItem` by `id`:
   - **upsert (weight/assignee):** if an item with that `id` exists, the incoming value
     wins **only if** `incoming.updatedAt >= stored.updatedAt` (honest LWW); otherwise
     the stored value is kept (a stale write loses). If absent, append. **The `notes`
     map is always carried over from the stored item** — a weight/assignee edit never
     overwrites notes (notes are owned solely by the dedicated note path in §2). This
     prevents a member's allocation edit from clobbering another member's intention.
   - **remove:** filter the item out by `id` (idempotent).
3. Bump plan-level `revision` to `R = (current.revision ?? 0) + 1`.
4. Write a history entry (see below) in the **same transaction**.
5. `transaction.set(planRef, { items, revision: R, updatedAt })`.

Firestore serializes conflicting transactions and auto-retries on contention, so the
"different rows never collide" guarantee holds even though all items live in one array
field. The pure merge logic is extracted so it is unit-testable without Firestore:

```ts
// sharedPlanLogic.ts
applyItemLWW(items: PlanItem[], incoming: PlanItem): PlanItem[]   // upsert w/ updatedAt compare; preserves stored notes
removeItemById(items: PlanItem[], id: string): PlanItem[]         // idempotent remove
```

### History subcollection

`shared_plans/{planId}/history/{revision}` — **keyed by the `revision` number** (a
string of the monotonic integer), not an auto-id. This makes the ring buffer prune with
**no query**: after writing revision `R`, delete the doc whose id is `String(R - HISTORY_MAX)`.

```ts
const HISTORY_MAX = 20;
```

Entry shape is the existing `PlanHistoryEntry` type:
`{ revision, itemId, before: PlanItem | null, after: PlanItem | null, updatedBy, at }`.

The history entry is `transaction.set` inside the same transaction as the item write
(its doc ref is known: `doc(db, 'shared_plans', planId, 'history', String(R))`). The
prune delete runs **after** the transaction commits, best-effort (a failed prune leaves
one extra stale entry — harmless for a safety net).

The existing `pruneHistory(entries, max)` helper operated on an inline array; with a
revision-keyed subcollection it is **not needed** and will be removed (orphan from the
Phase-1 thin-sync design). `PlanHistoryEntry` is kept.

### Firestore rules

Add under `match /shared_plans/{planId}`:

```
match /history/{rev} {
  allow read:   if isMember();          // edit history is members-only, not public
  allow create: if isMember();          // appended by the edit transaction (by convention)
  allow delete: if isMember();          // ring-buffer prune
  allow update: if false;               // entries are immutable
}
```

`isMember()` already exists in the rules. History is **members-only** (unlike the
public-read plan doc) because entries may contain niyyah note text in `before`/`after`.

### Recovery UI

Out of scope for this pass — the history is a **safety net the data layer writes**, not
a user-facing time machine. A "restore" UI is a later item if anyone ever needs it. We
build the write + prune + rules now so the net exists.

---

## 2. Per-member niyyah / intention notes

### Data

Add an optional field to `PlanItem`:

```ts
notes?: Record<string, { text: string; at: number }>;   // keyed by member uid
```

Each member edits **only their own** uid key. Firestore rules cannot enforce
map-key-level authorship, but members can already write the whole `items` array, so this
is by-convention (the same trust model as `weight`/`assigneeUid` today).

**Notes get their own transactional mutation — not the generic item upsert** — because
the generic upsert does whole-item LWW (it would clobber other members' note keys, and a
racing weight edit would clobber notes; see §1, where the generic path deliberately
preserves the stored `notes` map). Inside the transaction we re-read the item and **merge
only the caller's uid key**, preserving every other member's note and the item's other
fields:

```ts
// useSharedPlan
setMyNote(itemId: string, text: string): Promise<void>;   // merges notes[myUid] in-transaction, bumps revision + history
```

```ts
// sharedPlanLogic.ts — pure helper applied to the freshly re-read item
setMemberNote(item: PlanItem, uid: string, text: string): PlanItem
// returns { ...item, notes: { ...item.notes, [uid]: { text, at } } };
// empty/whitespace text deletes notes[uid] instead (don't store empty notes).
```

This means concurrent note edits by different members on the same charity both survive
(each merges its own key onto the latest re-read item), and an allocation edit can never
drop a note.

### UI (`SharedPlanView`)

Under each charity row, render existing notes as `name: "text"` lines (one per member
who wrote one, name resolved via `nameByUid`). The signed-in member gets an editable
"Your reason" field that saves on blur. Notes are **not** rendered in the public join
preview (`JoinPlanPage`) — personal intentions stay private. The money-free invariant is
unaffected (notes are text, never dollars).

---

## 3. Explore-together shortlist

### Data

Add an optional field to the **plan doc** (inline array, read with the plan — no extra
round-trip):

```ts
// SharedPlan
shortlist?: ShortlistCandidate[];

interface ShortlistCandidate {
  ref: string;        // EIN
  addedBy: string;    // uid
  addedAt: number;    // epoch ms
}
```

A candidate is a charity the family is *considering* but has not committed to the plan.
Dedup by `ref`. Shortlist add/remove/promote are **transactional** (re-read, mutate the
`shortlist` array, write) — concurrent adds during a live session don't clobber. Pure
helpers:

```ts
addShortlistCandidate(list, ref, uid): ShortlistCandidate[]   // dedup by ref
removeShortlistCandidate(list, ref): ShortlistCandidate[]
```

Promotion is a two-array transaction: remove the candidate from `shortlist` **and**
append a `PlanItem` (`kind:'charity'`, `ref`, `weight:1`) to `items`, bumping `revision`
+ history once. A pure helper `promoteCandidate(plan, ref, uid)` returns the next
`{ items, shortlist }`.

### Hook surface (`useSharedPlan`)

```ts
addToShortlist(ref: string): Promise<void>;
removeFromShortlist(ref: string): Promise<void>;
promoteToPlan(ref: string): Promise<void>;
```

### UI

New `ShortlistPanel.tsx` (its own file, one responsibility):
- **Explore step (`GivingSession`)** — replace the bare "Browse charities" link with the
  panel: a charity search/add (reuse the existing `AddCharity` search pattern from
  `SharedPlanView`) writing to the shortlist, and the live candidate list showing each
  charity name + "suggested by {name}" + a remove ✕. The teaching nudge stays.
- **Decide step (`SharedPlanView`)** — when the plan has a non-empty shortlist, show it
  above the plan table as "Still considering" with an **"Add to plan"** button per
  candidate (calls `promoteToPlan`), which moves it into the table.

The `/browse` link can remain as a secondary "explore the full site" affordance, but the
in-session shortlist is the primary surface.

---

## Build order

1. **Per-row LWW + history** — the transactional foundation (`useSharedPlan`,
   `sharedPlanLogic`, `firestore.rules`, `types`). Niyyah + shortlist depend on it.
2. **Niyyah notes** — `PlanItem.notes`, note merge helper, `SharedPlanView` UI.
3. **Shortlist** — `SharedPlan.shortlist`, `ShortlistCandidate`, shortlist/promote
   helpers + hook methods, `ShortlistPanel`, wire into `GivingSession` + `SharedPlanView`.

## Files

- **Modify:** `website/src/types/sharedPlan.ts` (`PlanItem.notes`, `ShortlistCandidate`,
  `SharedPlan.shortlist`), `website/src/hooks/useSharedPlan.ts` (transactional upsert/
  remove + history + shortlist/promote/note methods), `website/src/lib/sharedPlanLogic.ts`
  (LWW/remove/shortlist/promote helpers; drop unused `pruneHistory`),
  `website/src/components/giving/SharedPlanView.tsx` (notes UI + shortlist promote),
  `website/src/components/giving/GivingSession.tsx` (Explore shortlist surface),
  `firestore.rules` (history rules).
- **Create:** `website/src/components/giving/ShortlistPanel.tsx`,
  `website/src/components/giving/ShortlistPanel.test.tsx` (if component logic warrants),
  plus Vitest specs for the new pure helpers in `sharedPlanLogic.test.ts`.

## Testing

- **Pure helpers (Vitest):** `applyItemLWW` (newer wins, stale loses, append-when-absent,
  **and a weight edit preserves the stored `notes` map**), `removeItemById` (idempotent),
  history prune-by-revision math, `setMemberNote` (set own key preserving others' keys,
  clear own key with empty text), `addShortlistCandidate`/`removeShortlistCandidate`
  (dedup), `promoteCandidate` (moves ref from shortlist to items at weight 1).
- **Component:** `SharedPlanView` renders members' notes + an editable own-note field;
  shortlist promote button calls `promoteToPlan`.
- **e2e (emulator):** extend `shared-plan-emulator.spec.ts` — two users: A shortlists a
  charity → B sees it → A promotes it into the plan; A and B edit *different* item weights
  concurrently and both survive (LWW); assert zero console errors and money-free preview.

## Security / invariants (unchanged from Phase 1)

- Money-free shared doc; dollars never written (your-share stays client-only).
- Public read of the plan doc enables the pre-signup preview; **history and notes are not
  exposed in that preview** (history is members-only by rule; notes are simply not
  rendered on `JoinPlanPage`).
- Owner-only fields (`ownerId`, `inviteToken`, `name`) still guarded by the existing
  update rule; `items`/`shortlist`/`notes` are member-writable as today.

## Risks / notes

- **Map field in a transaction:** writing `notes` (a nested map) via whole-`items`
  re-write is fine; no Firestore array-element-path gymnastics (we always rewrite the
  whole `items` array inside the transaction).
- **History entry size:** entries embed `before`/`after` `PlanItem`s including `notes`.
  A pathologically long note inflates an entry, but the ring buffer is capped at 20 and
  the doc-size limit is per-history-doc (1 MB) — not a practical concern for a family.
- **Revision-keyed history under concurrency:** two transactions targeting revision `R`
  cannot both commit — Firestore retries the loser, which re-reads and targets `R+1`, so
  history doc ids stay unique and monotonic.

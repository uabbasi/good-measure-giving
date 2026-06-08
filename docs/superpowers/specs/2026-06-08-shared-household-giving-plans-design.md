# Shared Household Giving Plans — Design

**Date:** 2026-06-08
**Status:** Approved, ready for implementation plan
**Author:** brainstormed with Usman

## Demand evidence (office-hours, 2026-06-08)

This is the founder's own behavior, externalized: he and his family **sit together,
explore the site, find charities, and decide their giving as a group** — a recurring
family ritual he wants to do more of. That is the strongest starting signal (build
what you already do, watched working in your own home).

**Implication for the build — lead with the ritual, not the plumbing.** The hook is
the *synchronous, sit-together exploration + decide-as-a-family* experience and the
invite that brings family into it. The multi-editor / last-write-wins machinery is
**support** (it makes kids-on-their-own-phones-during-the-session work), not the
headline. Build the explore-and-decide-together surface and the invite first; the
conflict engine is infrastructure behind it. Caveat from the diagnostic: demand
beyond the founder's own family is still unproven — dogfood with his family on the
shipped product is the validation loop.

## Context

The onboarding funnel converts during Ramadan and goes dormant after: 22 registered
users, all signed up Feb 15 – Mar 19 (Ramadan window), zero new signups in the ~11
weeks since. The shipped activation work (March 19 conversion spec: progressive
reveal, welcome tour, nudges) optimizes the *individual* journey but provides **no
growth loop** — nothing makes an existing user bring another user.

This feature adds the growth loop: a **shared household giving plan** that multiple
family members co-edit. The invite link is the acquisition channel; co-planning is
the retention payoff. It attacks the flat-since-Ramadan signup line directly.

## Core principle: proportions are shared, dollars are personal

The variation in how families want to plan together (spouse full-transparency, kids
charity-selection-only, some people no-money-sharing) is *entirely about money*.
Remove money from the shared object and the privacy matrix disappears — there is
nothing to configure.

A family plan is fundamentally **proportions**: "who do we support and how do we
split it" (e.g., 40% Humanitarian, 30% Education, 30% local masjid; within
Humanitarian: Islamic Relief, Anera, ICNA Relief). That is meaningful and shareable
to everyone — spouse, kids, parents — and contains zero sensitive information. Each
member applies those proportions to their **own private zakat amount**, which never
enters the shared plan.

This covers every case the user named with **no settings**:

| Case | Handling |
|---|---|
| Kids — charities + proportions only | That *is* the shared plan; no money exposure |
| Just charity selection | A subset — proportions optional |
| Don't want to share money | Money is structurally never in the shared object |
| Spouse — full transparency with real numbers | Deferred to phase 2 (combined-dollar rollup) |

## Non-goals (phase 1)

- **No dollar amounts in the shared plan.** No combined household target, no shared
  donation amounts. (Phase 2.)
- **No migration of existing personal plans.** Personal giving plan (`givingBuckets`,
  `charityBucketAssignments` on the user profile) is left exactly as is.
- **No real-time collaborative cursors / live presence.** Per-row last-write-wins on
  save is sufficient.
- **No email/push invite delivery.** Share a link via the device's native share sheet
  / copy-link. (Consistent with the March spec's "no email re-engagement" non-goal.)
- **No approval gate on joining.** Anyone with a valid invite link joins as an editor.

## Data model

New Firestore tree, separate from the user profile. No money fields anywhere in it.

### `shared_plans/{planId}`

| Field | Type | Notes |
|---|---|---|
| `name` | string | e.g. "Khan Family" |
| `ownerId` | string (uid) | Creator; the only role that can manage members/link/name |
| `createdAt` | timestamp | |
| `updatedAt` | timestamp | Plan-level, bumped on any write |
| `revision` | integer | Bumped on every write; used for history + optimistic checks |
| `inviteToken` | string | Random, unguessable; rotatable/revocable by owner |
| `items` | array<PlanItem> | The proportional plan (see below) |

**PlanItem** (element of `items`):

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable per-item id (client-generated uuid) |
| `kind` | `'charity' \| 'category'` | |
| `ref` | string | EIN (charity) or category slug |
| `weight` | number | Proportion / relative weight (not dollars) |
| `assigneeUid` | string \| null | Which member is covering this item (optional) |
| `updatedAt` | timestamp | Per-item — drives last-write-wins |
| `updatedBy` | string (uid) | |

### `shared_plans/{planId}/members/{uid}`

| Field | Type | Notes |
|---|---|---|
| `role` | `'owner' \| 'editor'` | |
| `displayName` | string | Snapshot of member name for display |
| `joinedAt` | timestamp | |

### `shared_plans/{planId}/history/{autoId}` (safety net, not full VC)

A bounded ring buffer (keep last N≈20). Each entry: `{ revision, itemId, before, after,
updatedBy, at }`. Lets the team recover from a same-row clobber. Pruned to N on write.

### User profile pointer

Add to the user document a lightweight list so the plan switcher can enumerate
without a collection-group query on every load:

- `sharedPlanIds: string[]` — plan ids this user belongs to (maintained on join/leave).

## Conflict / versioning model

- **Granularity: per-row.** A save patches a single `PlanItem` by `id`, stamping its
  `updatedAt`/`updatedBy`. Two members editing different items never collide.
- **Same-item collision: last write wins** (later `updatedAt` overwrites).
- Each write also bumps the plan-level `revision` and appends a `history` entry, so a
  clobbered edit is recoverable.
- Adds/removes operate on the `items` array by id (add appends; remove filters by id).
  Concurrent add of two different items is safe; concurrent remove of the same item is
  idempotent.

> Implementation note: patching one element of an array field in Firestore means a
> read-modify-write of `items`. To keep per-row LWW honest under concurrency, the write
> is wrapped in a transaction that re-reads `items`, applies the single-item change by
> id (respecting `updatedAt`), bumps `revision`, and appends history. This preserves the
> "different rows never collide" guarantee even though they share one document.

## Membership & roles

- **Owner** (creator): rename plan, remove members, rotate/revoke `inviteToken`, plus
  all editor powers.
- **Editor**: full per-row editing of `items`. Cannot manage members or the link.
- **Join:** open invite link → authenticate → a `members/{uid}` doc is created with
  role `editor` and the plan id is appended to the user's `sharedPlanIds`.
- **Leave/remove:** member doc deleted, plan id removed from that user's
  `sharedPlanIds`. Owner cannot be removed (must transfer or delete plan — phase 2;
  for phase 1 the owner can delete the plan).

## The growth loop (invitee flow)

1. Owner taps **"Invite family"** → app ensures an `inviteToken` exists and surfaces a
   link `/{base}/plan/join/{inviteToken}` via the native share sheet + copy-link.
2. Invitee opens the link (no account) → **read-only preview**: the real plan rendered
   from `items` (charity names + proportions + assignees, **no dollars**), headed
   "The {name} is planning their giving."
3. CTA: **"Join your family → sign in."** After auth → added as `editor`, lands in the
   live shared-plan view.
4. **The join-after-preview event is the primary acquisition metric.**

## UI surface

- **Plan switcher** on the profile/giving surface: `[ My plan ▾ ] [ Khan Family ]`.
  Personal plan view is untouched; selecting a shared plan swaps in the shared-plan view.
- **Shared-plan view** reuses the existing allocation UI in a **proportional mode**:
  weights + assignees, no dollar inputs. Each member additionally sees a private
  "your share" = (their own personal zakat target) × (item weight ÷ total weight),
  computed client-side from their own profile data — never written to the shared plan.
- **Invite affordance:** owner sees "Invite family" + a member list with remove/revoke;
  editors see the member list read-only.
- **Join/preview page** (`/plan/join/{token}`): read-only proportional render + sign-in CTA.

## Security (Firestore rules)

- **Read `shared_plans/{planId}` and its `items`:**
  - any authenticated member (has `members/{uid}`), **OR**
  - any request presenting a `inviteToken` that matches the doc's `inviteToken`
    (enables the unauthenticated/pre-signup preview). Because the doc has **no money**,
    exposing it via a known token is acceptable.
- **Write `items`:** members only (owner or editor).
- **Write owner-only fields** (`name`, `inviteToken`, member management): `ownerId` only.
- **`members` subcollection:** a user may create their own member doc only when
  presenting a valid `inviteToken`; owner may delete any member doc; a member may
  delete their own.
- **`history`:** readable by members; writable only via the same transaction that
  writes `items` (server-stamped).

> Rule feasibility note: matching `inviteToken` for an unauthenticated read requires the
> token to be supplied in a readable way. If Firestore rules cannot validate a
> client-supplied token cleanly for the public preview, the fallback is a tiny callable
> Cloud Function `getPlanPreview(token)` that returns the money-free projection. The
> implementation plan must verify which path works before building the preview page.

## Edge cases

- **Revoked link:** opening an old token → "This invite is no longer active." Existing
  members unaffected.
- **Already a member opens the link:** skip preview, go straight into the plan.
- **Owner deletes plan:** members' `sharedPlanIds` entries become dangling → switcher
  tolerates missing plans (filters them out, no crash).
- **Charity in plan later hidden/removed from catalog:** render by stored `ref` with a
  graceful "charity no longer listed" fallback; weight still counts.
- **Member with no personal zakat target:** "your share" shows proportions only, with a
  nudge to set a target (ties into existing activation nudges).
- **Concurrent add pushing the array large:** cap items at a sane max (e.g. 100) to keep
  the doc well under Firestore's 1 MiB limit.

## Success metrics

- **Primary:** invited-signup conversion — preview opens → joins (new accounts created
  via the join flow).
- Households with 2+ active members.
- Activation lift: do shared-plan members set zakat targets / log donations at a higher
  rate than solo users?

## Phasing

> **CEO review reshape (2026-06-08):** north star is **"Family Giving Night."** Phase 1
> is **ritual-first on thin sync**, NOT plumbing-first. Per-row LWW + history are deferred
> (concurrent editing is rare per the demand evidence).

- **Phase 1 (first build):** shared proportional plan (money-free); owner/editor roles;
  invite link + revoke; unauthenticated read-only preview; plan switcher; proportional
  together-view with private per-member "your share" — **on thin sync (whole-doc merge
  write, not per-row LWW).** Plus the three accepted cathedral additions:
  - **Giving-session flow** — guided gather → explore → decide → recap arc (the ritual spine).
  - **Session recap artifact** — shareable "Family Giving Plan {year}" summary (delight + growth loop).
  - **Kids/teaching mode** — assign a member a cause to research and present in the session.
- **Phase 2 (deferred — TODOS):** per-row LWW + history ring buffer; explore-together
  group-discovery surface; intention/niyyah notes per charity; Ramadan-timed session CTA;
  combined household *dollar* rollups (spouse full-transparency); owner transfer.

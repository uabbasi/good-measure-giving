# TODOS

## Shared Household Giving Plans — Phase 2 (deferred by CEO review 2026-06-08)

Phase 1 ships ritual-first ("Family Giving Night") on thin sync. These were
explicitly deferred — do NOT build them in the first pass:

- **Per-row last-write-wins + history ring buffer.** Phase 1 uses whole-doc merge
  writes. Add per-item LWW + the `shared_plans/{id}/history` safety net only when
  real concurrent multi-device editing shows up (demand evidence says it's rare:
  "one person does all the giving").
- **Explore-together group-discovery surface (#2).** A dedicated "shortlist charities
  as a family" UI. Phase 1 leans on the existing `/browse` + cause hubs from inside
  the session flow instead.
- **Intention / niyyah notes (#5).** Per-charity "why we chose this" field — turns
  allocation into meaning. Nice delight, not first-build.
- **Ramadan-timed session CTA (#6).** "Start your family's Ramadan giving night" —
  seasonal hook on the one proven conversion window. Add before Ramadan.
- **Combined household dollar rollups.** The spouse full-transparency case (shared
  target + everyone's donations). Phase 1 keeps dollars personal.
- **Owner transfer.** Phase 1 owner can only delete the plan, not hand it off.

Spec: `docs/superpowers/specs/2026-06-08-shared-household-giving-plans-design.md`
Plan: `docs/superpowers/plans/2026-06-08-shared-household-giving-plans.md`

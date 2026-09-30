---
target: whole app (all routes, 375/1440, light/dark, anon+logged-in)
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 7
target_identity: "file:/Users/uabbasi/dev/good-measure-giving/.claude/worktrees/impeccable-critique-2026-09-30/website/App.tsx"
target_fingerprint: "sha256:49bcd1ae509b16d3ee077c8a25fb8320c808891fc7e07a621f5f5a66daf109d5"
target_path: /Users/uabbasi/dev/good-measure-giving/.claude/worktrees/impeccable-critique-2026-09-30/website/App.tsx
timestamp: 2026-09-30T18-28-02Z
slug: website-app-tsx
---
Method: dual-agent (A: Opus design review, read-only · B: Sonnet detector + mechanical scans). Yardstick: PRODUCT.md (new, written this run).
Evidence: 120 full-page screenshots, 30 views × 375/1440 × light/dark, anon + logged-in (seeded donor), local dev `npm run dev:local` equivalent. Folder: ~/dev/good-measure-giving/.gstack/critique-2026-09-30/

## Design Health Score — 22/40 (Acceptable)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | Signed-in home/browse/charity pages never show plan status or "already in your plan" |
| 2 | Match with real world | 2 | "Wallet", "Fin/Prog/Fit", "Cost / benef.", "HARVEY-BALL MOTIF", raw field names on screen |
| 3 | User control and freedom | 3 | Filters/compare/modals escape fine; calculator "Save this plan" drops the computed amount |
| 4 | Consistency and standards | 1 | Two design systems; score shown 4 ways; Risk = band on browse, level on detail |
| 5 | Error prevention | 2 | Calculator link uses `?zakat=eligible` that browse ignores; missing signals become "Moderate" |
| 6 | Recognition over recall | 2 | Definitions live in `title=""` tooltips (no touch/keyboard); mobile headers abbreviated |
| 7 | Flexibility and efficiency | 3 | Sortable table, URL-kept facets, compare ×4, CSV export |
| 8 | Aesthetic and minimalist | 2 | Motif is beautiful; anon charity page stacks ~10 "Sign in to see this" rows |
| 9 | Error recovery | 2 | Good browse empty state; invalid-invite heading invisible in dark; 404 off-brand |
| 10 | Help and documentation | 3 | Guides/FAQ/methodology excellent, but not reachable at the point of confusion |

## Design specificity verdict
Public pages are authored for this audience (Bismillah bar, Hijri date, sage on bone, Spectral italics, Harvey balls). The logged-in half is a generic slate/emerald dashboard: /profile, /plan/join, donation modals, the 404 page. Those are exactly where the donor records a religious obligation and where a household member first arrives.

Detector: 20 findings / 4 rules (side-tab 9, gradient-text 5, gray-on-color 4, bounce-easing 2). 8 are in dead code, 2 confirmed false positives; the rest sit in the giving UI and CauseAreaMatrix. It does not see the inline-styled motif at all. Browser detector (5 pages, headless, no visible overlay): undersized text 685 hits, low-contrast 252 hits, dominated by the `sub2` grey.

Verification changed one claim: A ranked "prod index.css 404s, so the plan/invite/404 pages render unstyled" as a possible P0. False: Vite bundles index.css into /assets/index-*.css and the live bundle contains the Tailwind classes and the emerald focus ring. Downgraded to P1 consistency.

## What's working
1. A culturally fitted visual language nobody else in the category has.
2. Evidence honesty is visible: cited claims, "where each figure comes from", data vintage, the charity's own zakat page quoted with URL, a "case against".
3. Zakat content (planning guide, per-asset calculators, "none of this is a fatwa") is best in class for this audience.

## Priority issues (order: consistency → plain words → phone/layout → polish)

1. [P1] Second design system on the plan, invite, modals and 404. /profile + src/components/giving/* + JoinPlanPage + NotFoundPage use Tailwind slate/emerald (2,603 colour-class uses in 68 files) with a navy dark theme; the 404 still has the old logo/nav/footer and a tab bar over the footer; invite "link isn't valid" heading is near-invisible in dark (verified: auth-plan-join-invalid-375-dark.png, JoinPlanPage.tsx:49-57). Fix: port onto gmgPalette + GmgNav/footer like the content pages. → /impeccable polish (then /impeccable document)
2. [P1] The score has four faces. Cause/best-muslim/badge publish "66/100"; browse shows bands only; the charity page shows no GMG total, and its lead narrative says "97/100 from Charity Navigator"; home "Strong overall" averages bands and ignores risk (GmgLanding.tsx:27-28). Fix: one representation + one gating rule everywhere; GMG score in the charity header; label CN's number as not ours. → /impeccable clarify
3. [P1] Evaluate → plan → record has no seams. No live add-to-plan/save control anywhere (verified: AddToGivingButton only used by dead CharityCard) while the sign-in modal promises "Save charities"; calculator "See zakat-eligible charities" links `?zakat=eligible`, browse reads `?wallet=zakat` (verified: ZakatCalculatorAssetPage.tsx:133 vs facetState.ts:226-230); "Save this plan" drops the amount; plan tour targets a nonexistent "History" tab. → /impeccable shape
4. [P1] Zakat claim changes strength: home "We verify which charities are eligible" vs best-muslim "only flags charities that publicly say they accept zakat… the judgment is yours with your scholar". "We verify" reads as a ruling. Fix: one phrase, one definition, routed everywhere. → /impeccable clarify
5. [P1] Risk means two things: quality band on browse/compare ("Risk: Strong" reads as high risk), LOW/HIGH level on detail; the code comment admits AMF shows Weak on browse and LOW on its page. Unknown signals become "Moderate" (charityAdapter.ts:179-189). Fix: one scale; unknown = "—". → /impeccable clarify
6. [P2] Gating contradicts itself: compare hides bands browse shows to everyone; anon charity page stacks ~10 dashed gated rows before the (good) AnonWall; the wall lists "Donor fit" as locked though browse shows it. → /impeccable distill
7. [P1] Plain words. One dimension has three names (Alignment / Donor fit / Fit, plus a second unrelated "Fit"); "Wallet"; "Fuqara" with no gloss; "Fin/Prog/Cost / benef."; "Edition 2.0" ×4 with two date formats; "HARVEY-BALL MOTIF" rendered in the charity footer (verified GmgCharityDetail.tsx:592); the sources table title-cases raw field names ("Ntee Code", "Claims Zakat Eligible", TrustTheNumbers.tsx:33); program ratio has four names and two precisions on one page (88% vs 87.7%); "18 mo" vs "18.0 months"; 20+ separate money formatters. → /impeccable clarify
8. [P2] Phone: home bubble chart clips "39" off the right edge and hides "27" behind "19"; browse renders 169 cards unpaginated; plan category count chip sits under the × remove icon; compare shows 1.2 columns. → /impeccable adapt
9. [P1, accessibility] Light `sub2` #8a8e80 is 2.6–2.9:1 on every light surface (token file admits it; 214 detector hits) and carries 9.5–11px labels; `accent2`, caution and warn pairs 4.0–4.3:1; sortable `<th onClick>` has no keyboard path; definitions are `title` only. The global emerald focus ring does ship, but it's off-palette on motif pages. → /impeccable audit
10. [P3] Loose ends: zakat hub promises a "home-page zakat estimator" that doesn't exist; Zakat calculator missing from desktop nav; Link-to-us brand assets show the old emerald logo; prompts page says "Premium content" while every wall says "free"; "Mosques & Faith" vs "Masjids & Religious Congregations"; ~20 dead UI files. → /impeccable polish

## Persona red flags
- Jordan (first-timer from search): opens Islamic Relief, sees "GMG ● Strong" with no number and "97/100 from Charity Navigator" in the prose, then ~10 locked rows. Leaves thinking the score is 97.
- Casey (mobile): first chart clipped; 169-card scroll; tooltips never open on touch; a hurried tap on the "2 charities" chip can hit ×.
- Sam (keyboard/screen reader): can't sort browse; 2.7:1 grey labels; scale definitions only in `title`.
- Aisha (zakat the week before Ramadan): calculator not in desktop nav; hub points to a nonexistent estimator; the payoff link lands on all 169 incl. sadaqah-only; amount lost on "Save this plan".
- Bilal (invited household member): the invite page is the plainest on the site, illegible when the link is invalid in dark mode; after joining, a slate dashboard with Match columns, and no way to add a charity from its page.

## Minor observations
Tour dialog renders white in dark mode; no theme toggle on motif pages; compare passes an `active` nav item that doesn't exist; changelog "124 rated" vs 169 elsewhere (dated entry); FAQ fully expanded; ISF listed under Advocacy & Civic (possible data issue).

## Questions to consider
1. If "one score" is the position, why is the number hidden on the page built to justify it but published on every SEO list page?
2. Would one anonymous verdict ("Accepts zakat · Strong · one reason to hesitate") convert better than ten locked drawers?
3. If households are first-class, why is their front door the least-designed page?

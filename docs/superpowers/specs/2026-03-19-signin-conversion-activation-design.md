# Sign-In Conversion & Post-Signup Activation

**Date:** 2026-03-19
**Status:** Draft
**Problem:** Only 6.5% of new visitors start sign-in (3 of 46). Post-signup, only 4 of 22 users reach Champion tier — the activation gap is setting a zakat target + giving buckets.

## Context

Analytics (week of Mar 12–18, 2026):
- 91 real visits/week (Cloudflare RUM), 50% click hero CTA, but only 6.5% start sign-in
- Current UX: anonymous visitors immediately see ContentPreview gates on all rich content — the gate appears before they understand what they're missing
- Post-signup: a 5-second welcome toast, then full access with no guidance toward activation features
- PMF analysis: Champions (Tier 1) are distinguished by zakat target + giving buckets (+75pp vs Tier 2)

## Design

### 1. Progressive Reveal (Sign-In Conversion)

**Concept:** Give anonymous visitors 3 full charity detail views (including rich content) before activating content gates. This lets them experience the full product value before asking them to sign in.

**Metering:**
- Track unique charity EINs viewed in `localStorage` key `gmg_viewed_charities` (array of EIN strings)
- Only unique EINs count — revisiting the same charity does not decrement
- Counter persists across sessions (device-persistent, not session-based)
- On sign-in, clear the localStorage counter

**Views 1–3 (full access):**
- Anonymous user sees all rich content as if signed in
- Soft banner below charity header: "You're viewing **2 of 3** free full evaluations" with a "Sign in for unlimited →" link
- Banner is informational only — no blocking

**View 4+ (gated):**
- Rich content sections switch to existing `ContentPreview` gates (blurred/locked with "Sign in to unlock")
- Baseline content (summary, scores, basic financials) remains visible
- Stronger banner replaces soft banner: "You've used your free evaluations" with prominent "Sign in — Free, always" CTA
- This reuses the existing `ContentPreview` component and gating pattern — no new gate UI needed

**New hook — `useRichAccess()`:**

```typescript
interface RichAccess {
  canViewRich: boolean;       // true if signed in OR free views remaining
  viewsUsed: number;          // count of unique EINs viewed
  viewsRemaining: number;     // max(0, 3 - viewsUsed)
  recordView: (ein: string) => void;  // add EIN to localStorage
}
```

- Returns `canViewRich: true` if user is signed in (via `useAuth()`) OR `viewsUsed < 3`
- `recordView(ein)` is called in `CharityDetailsPage` on mount, only adds if EIN not already in the array

**Integration:** Replace `isSignedIn` checks in `TerminalView.tsx` and `TabbedView.tsx` with `canViewRich` from `useRichAccess()`. The existing conditional rendering pattern (`canViewRich ? <RichContent /> : <ContentPreview />`) stays the same — only the boolean source changes.

**New component — `FreeViewBanner`:**

```typescript
interface FreeViewBannerProps {
  viewsUsed: number;
  viewsRemaining: number;
}
```

- Rendered in `CharityDetailsPage` below the charity header, above the view content
- Two visual states: soft (views remaining) and strong (views exhausted)
- Contains a `SignInButton` trigger
- Hidden when user is signed in

### 2. Welcome Tour (Post-Signup Activation — Immediate)

**Concept:** Replace the current 5-second `WelcomeToast` with a lightweight modal on first sign-in. Shows what the user unlocked — not a form to fill out.

**Content:**
- Header: "Welcome to Good Measure" / "Here's what you can do now"
- Four feature cards (read-only, not interactive):
  1. Full evaluations unlocked — deep analysis on all 170+ charities
  2. Set a zakat target — track your annual giving goal
  3. Organize with giving buckets — group charities by cause area
  4. Save & compare charities — bookmark and compare side by side
- Two CTAs:
  - "Start exploring" — dismisses modal, user continues browsing
  - "Set up giving plan →" — navigates to `/profile` giving plan setup

**Behavior:**
- Shows once per user, on first sign-in only (check `isNewUser` from Firebase auth — creation time < 60 seconds)
- Dismissible via "Start exploring" button or clicking outside
- Not blocking — user can close it and continue
- Tracked in localStorage: `gmg_welcome_tour_shown`

**New component — `WelcomeTour.tsx`:**
- Replaces the existing `WelcomeToast` component rendered in `App.tsx` (not `FirebaseProvider.tsx`)
- Listens to the same `gmg:welcome` custom event dispatched by `FirebaseProvider.tsx`
- Uses `localStorage` (permanent, cross-session) instead of current `sessionStorage` — the tour should show once ever, not once per session, since it's a first-sign-in experience

### 3. Contextual Nudges (Post-Signup Activation — Ongoing)

**Concept:** Surface activation prompts at natural moments when the user's behavior indicates readiness. Each nudge shows once, is dismissible, and disappears if the user already has the feature set up.

**Nudge definitions:**

| ID | Trigger | Message | Action |
|----|---------|---------|--------|
| `buckets_nudge` | 3rd bookmark saved | "Organize your saved charities? Create giving buckets to group by cause area" | Navigate to /profile buckets setup |
| `zakat_target_nudge` | 5th charity detail view (signed in) | "Doing your research — nice. Set a zakat target to track your giving plan" | Navigate to /profile zakat setup |
| `zakat_donation_nudge` | 1st donation logged | "First donation recorded! Set a zakat target to see how this fits your plan" | Navigate to /profile zakat setup |

**Rules engine:**
1. Skip if nudge already dismissed (localStorage: `gmg_dismissed_nudges` array)
2. Skip if feature already set up (check Firestore: `givingBuckets`, `targetZakatAmount`)
3. Check trigger condition against current state
4. Show max 1 nudge per page load
5. Priority order: buckets > zakat target > zakat donation

**New hook — `useActivationNudge()`:**

```typescript
interface ActivationNudge {
  activeNudge: NudgeConfig | null;  // the nudge to show, or null
  dismiss: (nudgeId: string) => void;  // dismiss permanently
}
```

- Reads user profile from Firestore (existing auth context) to check feature completion
- Reads bookmark count via the existing `useBookmarks` hook (no additional Firestore queries)
- Tracks signed-in charity detail views in localStorage key `gmg_signed_in_views` — incremented in `CharityDetailsPage` on mount (same location as `recordView` for anonymous users, but only when signed in)
- Returns at most one nudge per render

**New component — `ActivationNudge.tsx`:**
- Small inline card (not a modal or toast) rendered within the page content
- Appears below the main content area on charity detail pages, or below the bookmarks section
- Contains: icon, title, description, action link, dismiss button
- Animates in subtly, no sound or vibration

**Design principle:** Respectful. Each nudge shows once. Dismissed = gone forever. Max 1 per page. Not shown if feature already set up.

### 4. Landing Page Copy Updates

**Concept:** The current landing page emphasizes research and evaluation but doesn't surface the giving plan / zakat planning angle. Since the activation features that define Champions are zakat target + giving buckets, the landing page should prime visitors for those tools — not just the content.

**Current copy issues:**
- Hero subtitle mentions "zakat eligibility" but not zakat planning
- "What charities don't put on their homepage" lists research features only — no planning angle
- Sign-in CTA lists "Donor fit analysis & giving plan tools" but it's the 4th bullet and vague
- No mention of zakat target, giving buckets, or organizing your giving anywhere on the page

**Changes:**

**Hero subtitle (mobile + desktop):**
- Current: "Real research on {count}+ Muslim charities — financials, impact data, and zakat eligibility. Not marketing. Not self-reported."
- New: "Real research on {count}+ Muslim charities — financials, impact evidence, and zakat eligibility. Plan your giving with confidence."

**"What charities don't put on their homepage" section — add a 4th item:**
- Add: `{ icon: Target, title: 'Zakat & giving planning', desc: 'Set a zakat target, organize charities into giving buckets, and track your annual plan.' }`
- This surfaces the planning tools to anonymous visitors and creates awareness before sign-in

**Sign-in CTA bullet list (mobile):**
- Current: `['Leadership profiles & CEO compensation', '3-year financial trends & audit results', 'Impact evidence grades with source citations', 'Donor fit analysis & giving plan tools']`
- New: `['Full charity evaluations & leadership profiles', '3-year financial trends & audit results', 'Zakat target & giving plan tools', 'Organize charities into giving buckets']`
- Moves planning tools up in prominence and makes them concrete

**Desktop "Join Community" section subtitle:**
- Current: "Unlock full evaluations — leadership profiles, financial history, impact evidence, and donor fit analysis. Free, always."
- New: "Unlock full evaluations and giving plan tools — set a zakat target, organize charities into giving buckets, and track your annual plan. Free, always."

**Files to modify:** `pages/LandingPage.tsx` — copy changes only, no structural changes. Add `Target` to lucide-react imports.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| User clears localStorage | Gets 3 more free views. Not an abuse vector — signing up is free. |
| User signs out after signing in | View counter was cleared on sign-in. Gets 3 fresh free views. Sign back in = full access. |
| Incognito/private window | Fresh localStorage = 3 free views. Acceptable — goal is nudging, not DRM. |
| Direct link to charity page | Counts as a view. If it's their 4th unique charity, gates activate. |
| User already has zakat target set | Zakat nudges never appear. Buckets nudge still appears if no buckets. |
| User bookmarks then immediately unbookmarks | Bookmark count is checked at nudge evaluation time, not cached. Unbookmarking below 3 removes the trigger. |

## Files to Create

| File | Purpose |
|------|---------|
| `src/hooks/useRichAccess.ts` | Progressive reveal metering hook |
| `src/hooks/useActivationNudge.ts` | Contextual nudge rules engine |
| `src/components/WelcomeTour.tsx` | First sign-in welcome modal |
| `src/components/ActivationNudge.tsx` | Inline nudge card component |
| `src/components/FreeViewBanner.tsx` | Free view counter banner |

## Files to Modify

| File | Change |
|------|--------|
| `src/components/views/TerminalView.tsx` | Replace `isSignedIn` with `canViewRich` from `useRichAccess()` |
| `src/components/views/TabbedView.tsx` | Replace `isSignedIn` with `canViewRich` from `useRichAccess()` |
| `pages/CharityDetailsPage.tsx` | Add `recordView(ein)` call, render `FreeViewBanner`, render `ActivationNudge` |
| `pages/LandingPage.tsx` | Update hero subtitle, add 4th value prop, update sign-in CTA bullets, update desktop subtitle |
| `src/auth/FirebaseProvider.tsx` | Clear `gmg_viewed_charities` localStorage on sign-in |
| `App.tsx` | Replace `<WelcomeToast />` with `<WelcomeTour />` |

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Sign-in start rate (new visitors) | 6.5% | 15%+ |
| Welcome tour → "Set up giving plan" click-through | N/A | 20%+ |
| Users with zakat target (of signed-in) | 14% (3/22) | 30%+ |
| Users with giving buckets (of signed-in) | 14% (3/22) | 30%+ |
| Champion tier (Tier 1) users | 18% (4/22) | 35%+ |

## Non-Goals

- No structural changes to the landing page — copy updates only. No changes to the browse page
- No email-based re-engagement or push notifications
- No A/B testing infrastructure (measure before/after instead)
- No server-side view counting (localStorage is sufficient for nudging)
- No changes to the sign-in modal itself (Google/Apple/Email flow stays the same)

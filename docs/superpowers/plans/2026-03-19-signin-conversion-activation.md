# Sign-In Conversion & Post-Signup Activation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase sign-in conversion from 6.5% to 15%+ by giving anonymous visitors 3 free full charity views before gating, then drive activation (zakat target + giving buckets) via a welcome tour and contextual nudges.

**Architecture:** A new `useRichAccess` hook wraps `useAuth` and localStorage to control content gating. The existing `isSignedIn` checks in TerminalView/TabbedView are replaced with `canViewRich` for content-related gates only. A `WelcomeTour` modal replaces the current `WelcomeToast`. A `useActivationNudge` hook + `ActivationNudge` component surface feature prompts at natural moments.

**Tech Stack:** React 19, TypeScript 5.8, localStorage, Playwright (e2e tests)

**Spec:** `docs/superpowers/specs/2026-03-19-signin-conversion-activation-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `website/src/hooks/useRichAccess.ts` | Progressive reveal metering — tracks unique EINs viewed in localStorage, exposes `canViewRich` boolean |
| `website/src/hooks/useActivationNudge.ts` | Nudge rules engine — checks profile state, bookmark count, view count against nudge triggers |
| `website/src/components/FreeViewBanner.tsx` | Banner component — soft (views remaining) or strong (views exhausted) with sign-in CTA |
| `website/src/components/WelcomeTour.tsx` | Welcome modal — shows once on first sign-in, lists unlocked features, two exit paths |
| `website/src/components/ActivationNudge.tsx` | Inline nudge card — icon, message, action link, dismiss button |
| `website/tests/e2e/progressive-reveal.spec.ts` | E2E tests for progressive reveal flow |
| `website/tests/e2e/welcome-tour.spec.ts` | E2E tests for welcome tour |

### Modified Files

| File | Change Summary |
|------|---------------|
| `website/pages/LandingPage.tsx` | Copy updates: hero subtitle, 4th value prop, sign-in CTA bullets, desktop subtitle |
| `website/src/components/views/TerminalView.tsx` | Replace ~23 content-gating `isSignedIn` refs with `canViewRich` prop; keep 4 feature-access refs |
| `website/src/components/views/TabbedView.tsx` | Replace all ~20 `isSignedIn` refs with `canViewRich` prop (all are content gating) |
| `website/pages/CharityDetailsPage.tsx` | Add `useRichAccess`, call `recordView`, render `FreeViewBanner` + `ActivationNudge`, pass `canViewRich` to views |
| `website/src/auth/FirebaseProvider.tsx` | Clear `gmg_viewed_charities` localStorage on sign-in |
| `website/App.tsx` | Replace `<WelcomeToast />` import and render with `<WelcomeTour />` |

---

## Task 1: Landing Page Copy Updates

**Files:**
- Modify: `website/pages/LandingPage.tsx`

This task is copy-only — no structural changes.

- [ ] **Step 1: Add `Target` import**

In `website/pages/LandingPage.tsx`, line 10, add `Target` to the lucide-react import:

```typescript
import { Scale, ArrowRight, CheckCircle, Search, Heart, Shield, Eye, Sparkles, Lock, Target } from 'lucide-react';
```

- [ ] **Step 2: Update hero subtitle (mobile)**

Line 61, change:
```typescript
Real research on {count}+ Muslim charities — financials, impact data, and zakat eligibility. Not marketing. Not self-reported.
```
To:
```typescript
Real research on {count}+ Muslim charities — financials, impact evidence, and zakat eligibility. Plan your giving with confidence.
```

- [ ] **Step 3: Update hero subtitle (desktop)**

Line 240, same change:
```typescript
Real research on {count}+ Muslim charities — financials, impact evidence, and zakat eligibility. Plan your giving with confidence.
```

- [ ] **Step 4: Add 4th value prop to "What charities don't put" section (mobile)**

Around line 95, add a 4th item to the array:
```typescript
{ icon: Target, title: 'Zakat & giving planning', desc: 'Set a zakat target, organize charities into giving buckets, and track your annual plan.' },
```

- [ ] **Step 5: Add 4th value prop to "What charities don't put" section (desktop)**

Around line 291, add the same 4th item:
```typescript
{ icon: Target, title: 'Zakat & giving planning', desc: 'Set a zakat target, organize charities into giving buckets, and track your annual plan.' },
```

- [ ] **Step 6: Update sign-in CTA bullet list (mobile)**

Lines 172-175, replace the 4-item array:
```typescript
{[
  'Full charity evaluations & leadership profiles',
  '3-year financial trends & audit results',
  'Zakat target & giving plan tools',
  'Organize charities into giving buckets',
].map((item) => (
```

- [ ] **Step 7: Update desktop "Join Community" subtitle**

Line 369, change:
```typescript
Unlock full evaluations — leadership profiles, financial history, impact evidence, and donor fit analysis. Free, always.
```
To:
```typescript
Unlock full evaluations and giving plan tools — set a zakat target, organize charities into giving buckets, and track your annual plan. Free, always.
```

- [ ] **Step 8: Visual check**

Run: `cd website && npm run dev 2>&1 | tee /tmp/vite-dev.log`

Check the landing page at the dev server URL (check `/tmp/vite-dev.log` for actual port). Verify:
- Hero subtitle reads "Plan your giving with confidence" on both mobile and desktop
- 4th value prop "Zakat & giving planning" appears with Target icon
- Sign-in CTA bullets mention "Zakat target & giving plan tools"
- Desktop subtitle mentions zakat target and giving buckets

- [ ] **Step 9: Commit**

```bash
git add website/pages/LandingPage.tsx
git commit -m "feat: update landing page copy to surface giving plan and zakat planning"
```

---

## Task 2: `useRichAccess` Hook

**Files:**
- Create: `website/src/hooks/useRichAccess.ts`
- Test: `website/tests/e2e/progressive-reveal.spec.ts` (later in Task 7)

- [ ] **Step 1: Create the hook**

Create `website/src/hooks/useRichAccess.ts`:

```typescript
/**
 * useRichAccess — Progressive reveal metering for anonymous visitors.
 *
 * Signed-in users always get rich access.
 * Anonymous users get 3 free full charity detail views (unique EINs),
 * tracked via localStorage. After 3, content gates activate.
 */

import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../auth/useAuth';

const STORAGE_KEY = 'gmg_viewed_charities';
const FREE_VIEW_LIMIT = 3;

function getViewedEins(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveViewedEins(eins: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(eins));
  } catch {
    // localStorage full or unavailable — fail silently
  }
}

export function clearViewedEins(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // fail silently
  }
}

interface RichAccess {
  canViewRich: boolean;
  viewsUsed: number;
  viewsRemaining: number;
  recordView: (ein: string) => void;
}

export function useRichAccess(): RichAccess {
  const { isSignedIn } = useAuth();
  const [viewedEins, setViewedEins] = useState<string[]>(getViewedEins);

  // Sync state if localStorage changes externally (e.g., another tab)
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setViewedEins(getViewedEins());
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const recordView = useCallback((ein: string) => {
    setViewedEins((prev) => {
      if (prev.includes(ein)) return prev;
      const updated = [...prev, ein];
      saveViewedEins(updated);
      return updated;
    });
  }, []);

  const viewsUsed = viewedEins.length;
  const viewsRemaining = Math.max(0, FREE_VIEW_LIMIT - viewsUsed);
  const canViewRich = isSignedIn || viewsUsed < FREE_VIEW_LIMIT;

  return { canViewRich, viewsUsed, viewsRemaining, recordView };
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

Expected: No errors related to `useRichAccess.ts`.

- [ ] **Step 3: Commit**

```bash
git add website/src/hooks/useRichAccess.ts
git commit -m "feat: add useRichAccess hook for progressive reveal metering"
```

---

## Task 3: `FreeViewBanner` Component

**Files:**
- Create: `website/src/components/FreeViewBanner.tsx`

- [ ] **Step 1: Create the component**

Create `website/src/components/FreeViewBanner.tsx`:

```typescript
/**
 * FreeViewBanner — Shows anonymous visitors their remaining free views.
 *
 * Two states:
 * - Soft: "You're viewing X of 3 free evaluations" (views remaining)
 * - Strong: "You've used your free evaluations" (views exhausted)
 */

import React from 'react';
import { SignInButton } from '../auth/SignInButton';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

interface FreeViewBannerProps {
  viewsUsed: number;
  viewsRemaining: number;
}

export const FreeViewBanner: React.FC<FreeViewBannerProps> = ({ viewsUsed, viewsRemaining }) => {
  const { isDark } = useLandingTheme();
  const isExhausted = viewsRemaining <= 0;

  if (isExhausted) {
    return (
      <div className={`flex items-center justify-between gap-3 px-4 py-3 rounded-xl mb-4 ${
        isDark
          ? 'bg-slate-800 border border-slate-700'
          : 'bg-slate-900 border border-slate-800'
      }`}>
        <span className="text-sm text-slate-300">
          You've used your free evaluations
        </span>
        <SignInButton
          variant="custom"
          context="free_view_banner_exhausted"
          className="cursor-pointer"
        >
          <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold bg-blue-600 text-white hover:bg-blue-500 transition-colors whitespace-nowrap">
            Sign in — Free, always
          </span>
        </SignInButton>
      </div>
    );
  }

  return (
    <div className={`flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl mb-4 ${
      isDark
        ? 'bg-blue-950/40 border border-blue-800/30'
        : 'bg-blue-50 border border-blue-200'
    }`}>
      <span className={`text-sm ${isDark ? 'text-blue-300/80' : 'text-blue-700'}`}>
        You're viewing{' '}
        <strong className={isDark ? 'text-blue-200' : 'text-blue-900'}>
          {viewsUsed} of 3
        </strong>{' '}
        free full evaluations
      </span>
      <SignInButton
        variant="custom"
        context="free_view_banner_soft"
        className="cursor-pointer"
      >
        <span className={`text-sm font-medium whitespace-nowrap transition-colors ${
          isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-800'
        }`}>
          Sign in for unlimited →
        </span>
      </SignInButton>
    </div>
  );
};
```

- [ ] **Step 2: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

- [ ] **Step 3: Commit**

```bash
git add website/src/components/FreeViewBanner.tsx
git commit -m "feat: add FreeViewBanner component for progressive reveal"
```

---

## Task 4: Integrate Progressive Reveal into CharityDetailsPage

**Files:**
- Modify: `website/pages/CharityDetailsPage.tsx`

- [ ] **Step 1: Add imports**

At the top of `website/pages/CharityDetailsPage.tsx`, add:

```typescript
import { useRichAccess } from '../src/hooks/useRichAccess';
import { FreeViewBanner } from '../src/components/FreeViewBanner';
```

- [ ] **Step 2: Add hook and recordView call**

Inside the `CharityDetailsPage` component (after the existing hooks around line 60-65), add:

```typescript
const { canViewRich, viewsUsed, viewsRemaining, recordView } = useRichAccess();
const { isSignedIn } = useAuth();
```

Then add a `useEffect` to record the view when the page mounts:

```typescript
import { useEffect } from 'react';

useEffect(() => {
  if (id && !isSignedIn) {
    recordView(id);
  }
}, [id, isSignedIn, recordView]);
```

Note: `id` here is the EIN from `useParams`. Only record for anonymous users.

- [ ] **Step 3: Render FreeViewBanner before the view component**

Find the view selection logic (around line 113-119):

```typescript
if (isRichTier(charity) || isBaselineTier(charity)) {
  if (useTerminal) {
    return <TerminalView charity={charity} />;
  }
  return <TabbedView charity={charity} />;
}
```

Wrap it to include the banner and pass `canViewRich`:

```typescript
if (isRichTier(charity) || isBaselineTier(charity)) {
  return (
    <>
      {!isSignedIn && <FreeViewBanner viewsUsed={viewsUsed} viewsRemaining={viewsRemaining} />}
      {useTerminal
        ? <TerminalView charity={charity} canViewRich={canViewRich} />
        : <TabbedView charity={charity} canViewRich={canViewRich} />
      }
    </>
  );
}
```

**Important:** The `FreeViewBanner` needs to be placed inside the same container/layout that the views render in. Look at where the return statement is and ensure the banner appears below the charity header but above the view content. You may need to inspect the actual rendered DOM to find the right insertion point — the banner should appear after the charity name/headline area.

- [ ] **Step 4: Verify it compiles (will error — views don't accept canViewRich yet)**

This step will produce a TypeScript error because `TerminalView` and `TabbedView` don't accept `canViewRich` yet. That's expected — Tasks 5 and 6 will fix this. For now, you can temporarily add `canViewRich?: boolean` to both view components' props to unblock, or proceed to Tasks 5-6 before running tsc.

- [ ] **Step 5: Commit**

```bash
git add website/pages/CharityDetailsPage.tsx
git commit -m "feat: integrate progressive reveal into CharityDetailsPage"
```

---

## Task 5: Update TerminalView to Use `canViewRich`

**Files:**
- Modify: `website/src/components/views/TerminalView.tsx`

This is the largest task. TerminalView has ~27 `isSignedIn` references. Most are content gating and should become `canViewRich`. A few are feature access and must stay as `isSignedIn`.

- [ ] **Step 1: Add `canViewRich` prop**

Find the component's props interface (look for `interface TerminalViewProps` or the function signature). Add `canViewRich` as a required prop:

```typescript
interface TerminalViewProps {
  charity: CharityData;
  canViewRich: boolean;
}
```

If the component is declared as `export const TerminalView: React.FC<{ charity: CharityData }>`, update to:

```typescript
export const TerminalView: React.FC<{ charity: CharityData; canViewRich: boolean }>
```

Destructure `canViewRich` from props alongside `charity`.

- [ ] **Step 2: Keep `isSignedIn` for feature-access checks**

The component already has `const { isSignedIn } = useAuth();` (line 251). **Keep this line** — it's still needed for feature-access checks.

- [ ] **Step 3: Replace content-gating `isSignedIn` with `canViewRich`**

Replace `isSignedIn` with `canViewRich` at these locations (all content gating):

**Content selection (rich vs baseline data):**
- Lines 271-274: citations selection
- Lines 380-386: strengths, headline, aboutSummary selection
- All other locations where pattern is `isSignedIn ? (rich?.X || baseline?.X) : baseline?.X`

**ContentPreview gates:**
- Line 931: `isSignedIn ? <rich> : <ContentPreview>` for case_against
- Line 1015: `!isSignedIn ? <ContentPreview> : <content>` for Best For
- Line 1497, 1502: financial_deep_dive gating
- Line 1631, 1636: long_term_outlook gating
- Line 1669, 1674: donor_fit_matrix gating
- Line 2351: organizational_capacity
- Line 2464: impact_evidence
- Lines 2578, 2583: bbb_assessment
- Lines 2699, 2704: grantmaking_profile
- Lines 2832, 2837: citation_stats

**ScoreBreakdown props:**
- Lines 1103, 1106, 1108, 1110, 2033, 2036, 2038, 2040: pass `canViewRich` instead of `isSignedIn`

**Sign-in banners:**
- Line 866: `!isSignedIn && <banner>` → `!canViewRich && <banner>`
- Line 1708: same pattern
- Line 1765: `!isSignedIn && hasRich`
- Line 1810: `!isSignedIn && baseline`
- Line 2814: `!isSignedIn && <SignInButton>` in similar orgs

**Content limits:**
- Line 2788: `isSignedIn ? 4 : 3` → `canViewRich ? 4 : 3`

**Layout conditionals:**
- Line 486 equivalent (text truncation), line 489 (gradient), line 494 (sign-in button)

- [ ] **Step 4: Keep these as `isSignedIn` (feature access, NOT content gating):**

- **Line 482-483**: Button grid layout and different button sets (donate button only for signed-in users) — this is about feature access, not content visibility
- **Line 771**: `isSignedIn ? 'See full evaluation' : 'Scroll for details'` — this is a UI affordance hint, keep as `isSignedIn` since anonymous users with free views should still be told to scroll
- **Line 2793**: `isSignedIn && linkedId ? <Link> : <text>` — linked navigation to other charities, feature access

- [ ] **Step 5: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

Expected: No errors. If `ScoreBreakdown` has a typed prop for `isSignedIn`, update that component's prop name too (or pass it with the same prop name — check what `ScoreBreakdown` expects).

- [ ] **Step 6: Commit**

```bash
git add website/src/components/views/TerminalView.tsx
git commit -m "feat: replace isSignedIn with canViewRich for content gating in TerminalView"
```

---

## Task 6: Update TabbedView to Use `canViewRich`

**Files:**
- Modify: `website/src/components/views/TabbedView.tsx`

TabbedView has ~20 `isSignedIn` references, all content gating.

- [ ] **Step 1: Add `canViewRich` prop**

Same as TerminalView — add `canViewRich: boolean` to the props interface.

- [ ] **Step 2: Replace ALL `isSignedIn` with `canViewRich`**

Every `isSignedIn` reference in TabbedView is content gating. Replace all of them:

- Line 259: Keep `const { isSignedIn } = useAuth();` — but you can remove it if no feature-access checks remain. Check if anything in TabbedView uses `isSignedIn` for non-content purposes. Per the codebase exploration, all usages are content gating, so you can **remove the `useAuth()` call entirely** and use only `canViewRich` from props.

- Lines 278-281: citations selection
- Lines 354-356: strengths, headline, aboutSummary
- Line 364: areas_for_improvement
- Line 428: gated count logic
- Line 436: dependency array
- Lines 486, 489, 494: about section truncation/sign-in
- Lines 552, 617, 685, 716: awards, governance, outlook
- Lines 822, 825, 826, 828: ScoreBreakdown props
- Line 841, 920: impact evidence
- Line 952: citation stats
- Lines 1007, 1054, 1060, 1063, 1117, 1133: Best For, Balanced View
- Lines 1207, 1224, 1270: Donor Fit, BBB, similar orgs
- Lines 1300, 1322: similar orgs slice limit

- [ ] **Step 3: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

- [ ] **Step 4: Commit**

```bash
git add website/src/components/views/TabbedView.tsx
git commit -m "feat: replace isSignedIn with canViewRich for content gating in TabbedView"
```

---

## Task 7: Clear localStorage on Sign-In + E2E Tests

**Files:**
- Modify: `website/src/auth/FirebaseProvider.tsx`
- Create: `website/tests/e2e/progressive-reveal.spec.ts`

- [ ] **Step 1: Import `clearViewedEins` in FirebaseProvider**

At the top of `website/src/auth/FirebaseProvider.tsx`, add:

```typescript
import { clearViewedEins } from '../hooks/useRichAccess';
```

- [ ] **Step 2: Clear localStorage on sign-in**

In the `onAuthStateChanged` callback (around line 69-77), after the sign-in detection, add the clear call. It should run for ALL sign-ins (not just new users), so the counter resets when a returning user logs back in:

```typescript
if (firebaseUser && !previousUid) {
  const provider = firebaseUser.providerData[0]?.providerId || 'unknown';
  const createdAt = new Date(firebaseUser.metadata.creationTime || 0).getTime();
  const isNewUser = Date.now() - createdAt < 60_000;
  trackSignInSuccess(provider, isNewUser ? 'signup' : 'login');
  clearViewedEins(); // Clear progressive reveal counter on any sign-in
  if (isNewUser) {
    window.dispatchEvent(new CustomEvent('gmg:welcome'));
  }
}
```

- [ ] **Step 3: Write E2E tests for progressive reveal**

Create `website/tests/e2e/progressive-reveal.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Progressive reveal', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage to start fresh
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.removeItem('gmg_viewed_charities');
    });
  });

  test('shows full content for first 3 unique charity views', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
    await page.reload();

    // Get first charity link
    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);

    // Should see the soft banner with view count
    const banner = page.getByText(/free full evaluations/i);
    await expect(banner).toBeVisible({ timeout: 5000 });

    // Should NOT see ContentPreview gates (rich content is visible)
    const body = await page.locator('body').textContent();
    // First view should show rich content, not gates
    const gateCount = (body?.match(/sign in to unlock/gi) || []).length;
    // With free views, there should be fewer gates than when exhausted
    // (Some gates may still appear for non-rich-tier charities, so just check the banner exists)
    expect(banner).toBeTruthy();
  });

  test('shows gated content after 3 unique charity views', async ({ page }) => {
    // Pre-seed 3 viewed charities in localStorage
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.setItem('gmg_viewed_charities', JSON.stringify([
        'fake-ein-001', 'fake-ein-002', 'fake-ein-003'
      ]));
      localStorage.setItem('gmg-browse-style', 'power');
    });
    await page.reload();

    // Navigate to a 4th charity
    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });
    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);

    // Should see the exhausted banner
    const exhaustedBanner = page.getByText(/used your free evaluations/i);
    await expect(exhaustedBanner).toBeVisible({ timeout: 5000 });
  });

  test('revisiting same charity does not count as new view', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => localStorage.setItem('gmg-browse-style', 'power'));
    await page.reload();

    const firstCard = page.locator('a[href^="/charity/"]:visible').first();
    await expect(firstCard).toBeVisible({ timeout: 10000 });

    // Visit the same charity twice
    await firstCard.click();
    await expect(page).toHaveURL(/\/charity\//);
    const url = page.url();

    await page.goto('/browse');
    await page.goto(url);

    // Check localStorage — should only have 1 EIN
    const viewedCount = await page.evaluate(() => {
      const stored = localStorage.getItem('gmg_viewed_charities');
      return stored ? JSON.parse(stored).length : 0;
    });
    expect(viewedCount).toBe(1);
  });
});
```

- [ ] **Step 4: Run E2E tests**

Run: `cd website && npx playwright test tests/e2e/progressive-reveal.spec.ts 2>&1 | tee /tmp/e2e-progressive-reveal.log`

Fix any failures.

- [ ] **Step 5: Commit**

```bash
git add website/src/auth/FirebaseProvider.tsx website/tests/e2e/progressive-reveal.spec.ts
git commit -m "feat: clear view counter on sign-in + add progressive reveal e2e tests"
```

---

## Task 8: `WelcomeTour` Component

**Files:**
- Create: `website/src/components/WelcomeTour.tsx`

- [ ] **Step 1: Create the component**

Create `website/src/components/WelcomeTour.tsx`:

```typescript
/**
 * WelcomeTour — Lightweight modal shown once on first sign-in.
 *
 * Replaces WelcomeToast. Listens for 'gmg:welcome' custom event.
 * Shows 4 feature cards + two CTAs: "Start exploring" or "Set up giving plan →".
 * Uses localStorage (permanent) so it never shows again.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Target, FolderOpen, Bookmark, X } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

const STORAGE_KEY = 'gmg_welcome_tour_shown';

const FEATURES = [
  {
    icon: BookOpen,
    title: 'Full evaluations unlocked',
    desc: 'Deep analysis on all 170+ charities',
  },
  {
    icon: Target,
    title: 'Set a zakat target',
    desc: 'Track your annual giving goal',
  },
  {
    icon: FolderOpen,
    title: 'Organize with giving buckets',
    desc: 'Group charities by cause area or priority',
  },
  {
    icon: Bookmark,
    title: 'Save & compare charities',
    desc: 'Bookmark and compare side by side',
  },
];

export const WelcomeTour: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  const { isDark } = useLandingTheme();

  const dismiss = useCallback(() => {
    setIsOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
      // fail silently
    }
  }, []);

  useEffect(() => {
    const handleWelcome = () => {
      // Only show if not already shown
      try {
        if (localStorage.getItem(STORAGE_KEY)) return;
      } catch {
        // If localStorage unavailable, show anyway
      }
      setIsOpen(true);
    };

    window.addEventListener('gmg:welcome', handleWelcome);
    return () => window.removeEventListener('gmg:welcome', handleWelcome);
  }, []);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) dismiss(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Modal */}
      <div className={`relative w-full max-w-md rounded-2xl shadow-2xl overflow-hidden ${
        isDark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
      }`}>
        {/* Close button */}
        <button
          onClick={dismiss}
          className={`absolute top-4 right-4 p-1 rounded-full transition-colors ${
            isDark ? 'text-slate-400 hover:text-white hover:bg-slate-700' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
          }`}
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className={`px-6 pt-6 pb-4 text-center ${
          isDark ? 'bg-gradient-to-b from-slate-800 to-slate-900' : 'bg-gradient-to-b from-slate-50 to-white'
        }`}>
          <h2 className={`text-xl font-bold font-merriweather ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Welcome to Good Measure
          </h2>
          <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Here's what you can do now
          </p>
        </div>

        {/* Feature cards */}
        <div className="px-6 py-4 space-y-2.5">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className={`flex items-start gap-3 p-3 rounded-xl ${
                isDark ? 'bg-slate-800/60 border border-slate-700/50' : 'bg-slate-50 border border-slate-100'
              }`}
            >
              <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
              <div>
                <div className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                  {title}
                </div>
                <div className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {desc}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* CTAs */}
        <div className="px-6 pb-6 flex gap-3">
          <button
            onClick={dismiss}
            className={`flex-1 px-4 py-3 rounded-xl text-sm font-semibold transition-colors ${
              isDark
                ? 'bg-slate-700 text-white hover:bg-slate-600'
                : 'bg-slate-900 text-white hover:bg-slate-800'
            }`}
          >
            Start exploring
          </button>
          <button
            onClick={() => { dismiss(); navigate('/profile'); }}
            className={`px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
              isDark
                ? 'bg-transparent text-slate-300 border border-slate-600 hover:bg-slate-800'
                : 'bg-transparent text-slate-600 border border-slate-300 hover:bg-slate-50'
            }`}
          >
            Set up giving plan →
          </button>
        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

- [ ] **Step 3: Commit**

```bash
git add website/src/components/WelcomeTour.tsx
git commit -m "feat: add WelcomeTour component for first sign-in onboarding"
```

---

## Task 9: Replace WelcomeToast with WelcomeTour in App.tsx

**Files:**
- Modify: `website/App.tsx`

- [ ] **Step 1: Update import**

In `website/App.tsx`, line 25, change:

```typescript
import { WelcomeToast } from './src/components/WelcomeToast';
```
To:
```typescript
import { WelcomeTour } from './src/components/WelcomeTour';
```

- [ ] **Step 2: Update render**

In `website/App.tsx`, line 88, change:

```typescript
<WelcomeToast />
```
To:
```typescript
<WelcomeTour />
```

- [ ] **Step 3: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

- [ ] **Step 4: Write E2E test for welcome tour**

Create `website/tests/e2e/welcome-tour.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Welcome Tour', () => {
  test('shows welcome modal content when gmg:welcome event fires', async ({ page }) => {
    await page.goto('/browse');

    // Ensure the tour hasn't been shown before
    await page.evaluate(() => {
      localStorage.removeItem('gmg_welcome_tour_shown');
    });

    // Simulate the welcome event (normally fired by FirebaseProvider on new user sign-in)
    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('gmg:welcome'));
    });

    // Welcome tour modal should appear
    const modal = page.getByText('Welcome to Good Measure');
    await expect(modal).toBeVisible({ timeout: 3000 });

    // Feature cards should be visible
    await expect(page.getByText('Full evaluations unlocked')).toBeVisible();
    await expect(page.getByText('Set a zakat target')).toBeVisible();
    await expect(page.getByText('Organize with giving buckets')).toBeVisible();
    await expect(page.getByText('Save & compare charities')).toBeVisible();

    // Both CTAs should be visible
    await expect(page.getByText('Start exploring')).toBeVisible();
    await expect(page.getByText('Set up giving plan →')).toBeVisible();
  });

  test('dismisses and does not show again', async ({ page }) => {
    await page.goto('/browse');
    await page.evaluate(() => {
      localStorage.removeItem('gmg_welcome_tour_shown');
    });

    // Trigger welcome event
    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('gmg:welcome'));
    });

    // Click "Start exploring"
    await page.getByText('Start exploring').click();

    // Modal should disappear
    await expect(page.getByText('Welcome to Good Measure')).not.toBeVisible();

    // Trigger event again — should NOT show
    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('gmg:welcome'));
    });
    await expect(page.getByText('Welcome to Good Measure')).not.toBeVisible();
  });
});
```

- [ ] **Step 5: Run E2E tests**

Run: `cd website && npx playwright test tests/e2e/welcome-tour.spec.ts 2>&1 | tee /tmp/e2e-welcome-tour.log`

Fix any failures.

- [ ] **Step 6: Commit**

```bash
git add website/App.tsx website/tests/e2e/welcome-tour.spec.ts
git commit -m "feat: replace WelcomeToast with WelcomeTour + add e2e tests"
```

---

## Task 10: `useActivationNudge` Hook

**Files:**
- Create: `website/src/hooks/useActivationNudge.ts`

- [ ] **Step 1: Create the hook**

Create `website/src/hooks/useActivationNudge.ts`:

```typescript
/**
 * useActivationNudge — Rules engine for post-signup contextual nudges.
 *
 * Checks user profile state, bookmark count, and view count to determine
 * which nudge (if any) to show. Each nudge shows once, is dismissible,
 * and doesn't appear if the feature is already set up.
 */

import { useMemo, useCallback } from 'react';
import { useAuth } from '../auth/useAuth';
import { useProfile } from './useProfile';
import { useBookmarks } from './useBookmarks';

const DISMISSED_KEY = 'gmg_dismissed_nudges';
const SIGNED_IN_VIEWS_KEY = 'gmg_signed_in_views';

export interface NudgeConfig {
  id: string;
  icon: string;       // emoji
  title: string;
  description: string;
  actionLabel: string;
  actionPath: string;
}

const NUDGE_DEFINITIONS: {
  id: string;
  icon: string;
  title: string;
  description: string;
  actionLabel: string;
  actionPath: string;
  featureCheck: (profile: { targetZakatAmount: number | null; givingBuckets: unknown[] }) => boolean;
  triggerCheck: (ctx: { bookmarkCount: number; signedInViews: number; donationCount: number }) => boolean;
}[] = [
  {
    id: 'buckets_nudge',
    icon: '🗂️',
    title: 'Organize your saved charities?',
    description: 'Create giving buckets to group charities by cause area',
    actionLabel: 'Set up buckets →',
    actionPath: '/profile',
    featureCheck: (p) => (p.givingBuckets?.length ?? 0) > 0,
    triggerCheck: (ctx) => ctx.bookmarkCount >= 3,
  },
  {
    id: 'zakat_target_nudge',
    icon: '🎯',
    title: 'Doing your research — nice',
    description: 'Set a zakat target to track your giving plan as you explore',
    actionLabel: 'Set target →',
    actionPath: '/profile',
    featureCheck: (p) => p.targetZakatAmount != null && p.targetZakatAmount > 0,
    triggerCheck: (ctx) => ctx.signedInViews >= 5,
  },
  {
    id: 'zakat_donation_nudge',
    icon: '📊',
    title: 'First donation recorded!',
    description: 'Set a zakat target to see how this fits your annual giving plan',
    actionLabel: 'Set target →',
    actionPath: '/profile',
    featureCheck: (p) => p.targetZakatAmount != null && p.targetZakatAmount > 0,
    triggerCheck: (ctx) => ctx.donationCount >= 1,
  },
];

function getDismissedNudges(): string[] {
  try {
    const stored = localStorage.getItem(DISMISSED_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveDismissedNudge(nudgeId: string): void {
  try {
    const dismissed = getDismissedNudges();
    if (!dismissed.includes(nudgeId)) {
      dismissed.push(nudgeId);
      localStorage.setItem(DISMISSED_KEY, JSON.stringify(dismissed));
    }
  } catch {
    // fail silently
  }
}

export function getSignedInViews(): number {
  try {
    return parseInt(localStorage.getItem(SIGNED_IN_VIEWS_KEY) || '0', 10);
  } catch {
    return 0;
  }
}

export function incrementSignedInViews(): void {
  try {
    const current = getSignedInViews();
    localStorage.setItem(SIGNED_IN_VIEWS_KEY, String(current + 1));
  } catch {
    // fail silently
  }
}

interface UseActivationNudgeResult {
  activeNudge: NudgeConfig | null;
  dismiss: (nudgeId: string) => void;
}

export function useActivationNudge(donationCount: number = 0): UseActivationNudgeResult {
  const { isSignedIn } = useAuth();
  const { profile } = useProfile();
  const { bookmarks } = useBookmarks();

  const dismiss = useCallback((nudgeId: string) => {
    saveDismissedNudge(nudgeId);
  }, []);

  const activeNudge = useMemo<NudgeConfig | null>(() => {
    if (!isSignedIn || !profile) return null;

    const dismissed = getDismissedNudges();
    const signedInViews = getSignedInViews();
    const ctx = {
      bookmarkCount: bookmarks.length,
      signedInViews,
      donationCount,
    };

    for (const nudge of NUDGE_DEFINITIONS) {
      // Skip if already dismissed
      if (dismissed.includes(nudge.id)) continue;
      // Skip if feature already set up
      if (nudge.featureCheck({
        targetZakatAmount: profile.targetZakatAmount ?? null,
        givingBuckets: profile.givingBuckets ?? [],
      })) continue;
      // Check trigger condition
      if (nudge.triggerCheck(ctx)) {
        return {
          id: nudge.id,
          icon: nudge.icon,
          title: nudge.title,
          description: nudge.description,
          actionLabel: nudge.actionLabel,
          actionPath: nudge.actionPath,
        };
      }
    }

    return null;
  }, [isSignedIn, profile, bookmarks.length, donationCount]);

  return { activeNudge, dismiss };
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

Check that `useProfile` returns `profile.targetZakatAmount` and `profile.givingBuckets` — adjust field access if the types differ from what's documented.

- [ ] **Step 3: Commit**

```bash
git add website/src/hooks/useActivationNudge.ts
git commit -m "feat: add useActivationNudge hook for contextual nudge rules engine"
```

---

## Task 11: `ActivationNudge` Component

**Files:**
- Create: `website/src/components/ActivationNudge.tsx`

- [ ] **Step 1: Create the component**

Create `website/src/components/ActivationNudge.tsx`:

```typescript
/**
 * ActivationNudge — Inline card that surfaces feature prompts at natural moments.
 *
 * Renders as a small inline card (not modal/toast) with icon, message,
 * action link, and dismiss button. Appears within page content.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import type { NudgeConfig } from '../hooks/useActivationNudge';

interface ActivationNudgeProps {
  nudge: NudgeConfig;
  onDismiss: (nudgeId: string) => void;
}

export const ActivationNudge: React.FC<ActivationNudgeProps> = ({ nudge, onDismiss }) => {
  const [dismissed, setDismissed] = useState(false);
  const navigate = useNavigate();
  const { isDark } = useLandingTheme();

  if (dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss(nudge.id);
  };

  const handleAction = () => {
    handleDismiss();
    navigate(nudge.actionPath);
  };

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-xl mt-4 animate-in fade-in slide-in-from-bottom-2 duration-300 ${
        isDark
          ? 'bg-blue-950/30 border border-blue-800/30'
          : 'bg-blue-50 border border-blue-200'
      }`}
    >
      <span className="text-xl flex-shrink-0">{nudge.icon}</span>
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
          {nudge.title}
        </div>
        <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {nudge.description}
        </div>
        <div className="flex items-center gap-3 mt-2">
          <button
            onClick={handleAction}
            className={`text-xs font-semibold transition-colors ${
              isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-800'
            }`}
          >
            {nudge.actionLabel}
          </button>
          <button
            onClick={handleDismiss}
            className={`text-xs transition-colors ${
              isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            Maybe later
          </button>
        </div>
      </div>
      <button
        onClick={handleDismiss}
        className={`flex-shrink-0 p-1 rounded-full transition-colors ${
          isDark ? 'text-slate-500 hover:text-slate-300 hover:bg-slate-700' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
        }`}
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
```

- [ ] **Step 2: Verify it compiles**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

- [ ] **Step 3: Commit**

```bash
git add website/src/components/ActivationNudge.tsx
git commit -m "feat: add ActivationNudge inline card component"
```

---

## Task 12: Integrate Nudges + Signed-In View Counter into CharityDetailsPage

**Files:**
- Modify: `website/pages/CharityDetailsPage.tsx`

- [ ] **Step 1: Add imports**

Add to `website/pages/CharityDetailsPage.tsx`:

```typescript
import { useActivationNudge, incrementSignedInViews } from '../src/hooks/useActivationNudge';
import { ActivationNudge } from '../src/components/ActivationNudge';
```

- [ ] **Step 2: Add nudge hook and signed-in view tracking**

Inside the component, after the existing hooks:

```typescript
const { activeNudge, dismiss: dismissNudge } = useActivationNudge();
```

Update the existing `useEffect` that calls `recordView` to also increment signed-in views:

```typescript
useEffect(() => {
  if (id && !isSignedIn) {
    recordView(id);
  }
  if (id && isSignedIn) {
    incrementSignedInViews();
  }
}, [id, isSignedIn, recordView]);
```

- [ ] **Step 3: Render ActivationNudge**

After the view component (TerminalView/TabbedView), render the nudge:

```typescript
if (isRichTier(charity) || isBaselineTier(charity)) {
  return (
    <>
      {!isSignedIn && <FreeViewBanner viewsUsed={viewsUsed} viewsRemaining={viewsRemaining} />}
      {useTerminal
        ? <TerminalView charity={charity} canViewRich={canViewRich} />
        : <TabbedView charity={charity} canViewRich={canViewRich} />
      }
      {activeNudge && <ActivationNudge nudge={activeNudge} onDismiss={dismissNudge} />}
    </>
  );
}
```

- [ ] **Step 4: Verify it compiles and renders**

Run: `cd website && npx tsc --noEmit 2>&1 | tee /tmp/tsc-check.log`

Then start the dev server and verify:
- Anonymous user sees FreeViewBanner on charity detail pages
- After 3 unique charities, ContentPreview gates appear
- Signed-in user sees no banner, no gates
- Nudge card appears when trigger conditions are met (hard to test manually — e2e test covers this)

- [ ] **Step 5: Commit**

```bash
git add website/pages/CharityDetailsPage.tsx
git commit -m "feat: integrate activation nudges and signed-in view tracking"
```

---

## Task 13: Final Integration Test

**Files:**
- Run all E2E tests

- [ ] **Step 1: Run full E2E suite**

Run: `cd website && npx playwright test 2>&1 | tee /tmp/e2e-full.log`

This runs all existing tests plus the new progressive-reveal and welcome-tour tests.

- [ ] **Step 2: Fix any regressions**

Check `/tmp/e2e-full.log` for failures. Common issues:
- Existing tests that check for "sign in to unlock" text may behave differently now that anonymous users get 3 free views (gates won't appear immediately)
- Tests that manipulate `localStorage` may interfere with the new keys

Fix any failures while preserving the new behavior.

- [ ] **Step 3: Visual smoke test**

Start dev server: `cd website && npm run dev 2>&1 | tee /tmp/vite-dev.log`

Check these flows manually:
1. Landing page → verify new copy
2. Browse → click 3 different charities → verify full content + soft banner
3. Click 4th charity → verify gates appear + strong banner
4. (If possible) Sign in → verify welcome tour appears → verify gates disappear

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address e2e test regressions from progressive reveal changes"
```

# Build-time SSR (SSG) via renderToString — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server-render real HTML content into SEO-critical pages at build time (no headless browser) so Google can index them, replacing the puppeteer prerender.

**Architecture:** A new `entry-server.tsx` renders the app to a fully-resolved HTML string per route using `StaticRouter` + a react-query cache pre-seeded from disk. Browser-only widgets are gated behind `<ClientOnly>` so the Node render never touches the DOM. The client stays non-hydrated (`createRoot`, unchanged). The build adds a Vite SSR pass; `scripts/prerender.ts` calls `render()` and injects the body into `#root`. `puppeteer` is removed.

**Tech Stack:** React 19, react-dom/server (`renderToPipeableStream`), react-router-dom 6 (`StaticRouter`), @tanstack/react-query 5, Vite 6 (SSR build), vitest, tsx.

## Global Constraints

- Node/React render must never touch `window`, `document`, `localStorage`, `matchMedia`, or `navigator` during render — guard with `typeof window !== 'undefined'` or `<ClientOnly>`.
- Client runtime behavior must stay identical (non-hydrated `createRoot`); no `hydrateRoot`.
- SSR scope is exactly: `/charity/:id`, `/guides`, `/guides/:slug`, `/causes`, `/causes/:slug`, `/zakat-calculator`, `/zakat-calculator/:asset`, `/prompts`, `/prompts/:id`, `/methodology`, `/about`, `/faq`. All other routes keep today's meta-only shell.
- Sitemap (`generateSitemap.ts`) and `_redirects`/308 logic (`writeRedirects`) must remain unchanged and keep running.
- Data query keys are fixed: `['charity', ein]`, `['charities']`, `['guides']`, `['guide', slug]`, `['calculator-data']`, `['prompts']`, `['prompt', id]`.
- Run all commands from `website/`. Tests: `npx vitest run <path>`.

---

### Task 1: `ClientOnly` wrapper

**Files:**
- Create: `src/components/ClientOnly.tsx`
- Test: `src/components/ClientOnly.test.tsx`

**Interfaces:**
- Produces: `ClientOnly: React.FC<{ children: React.ReactNode }>` — renders `null` until mounted (after first effect), then `children`.

- [ ] **Step 1: Write the failing test**

```tsx
// src/components/ClientOnly.test.tsx
// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { ClientOnly } from './ClientOnly';

test('renders nothing during server render', () => {
  const html = renderToStaticMarkup(<ClientOnly><span>hi</span></ClientOnly>);
  expect(html).toBe('');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/ClientOnly.test.tsx`
Expected: FAIL — cannot find module `./ClientOnly`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// src/components/ClientOnly.tsx
import React, { useEffect, useState } from 'react';

export const ClientOnly: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted ? <>{children}</> : null;
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/ClientOnly.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/ClientOnly.tsx src/components/ClientOnly.test.tsx
git commit -m "feat(ssg): add ClientOnly wrapper for browser-only widgets"
```

---

### Task 2: Split `App.tsx` into injectable providers

Extract the provider tree so server and client share it. `AppProviders` takes an injected `queryClient`. `AppContent` (the chrome + `Routes`) is exported for the server. The default `App` export keeps current client behavior.

**Files:**
- Modify: `App.tsx`
- Modify: `index.tsx`
- Test: `App.providers.test.tsx`

**Interfaces:**
- Produces:
  - `AppProviders: React.FC<{ queryClient: QueryClient; children: React.ReactNode }>` — wraps children in `QueryClientProvider` (injected client), `LazyMotion`, `ThemeProvider`, `LandingThemeProvider`, `UserFeaturesProvider`. No Router, no FirebaseProvider, no devtools.
  - `AppContent: React.FC` — existing component (Navbar + `<main><Routes/></main>` + chrome), exported.
  - `createAppQueryClient(): QueryClient` — factory returning the configured client (staleTime Infinity, refetchOnWindowFocus false).
  - default `App` — unchanged behavior for client.

- [ ] **Step 1: Write the failing test**

```tsx
// App.providers.test.tsx
// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { AppProviders, AppContent, createAppQueryClient } from './App';

test('AppProviders + AppContent render the shell server-side without throwing', () => {
  const qc = createAppQueryClient();
  const html = renderToStaticMarkup(
    <AppProviders queryClient={qc}>
      <StaticRouter location="/about">
        <AppContent />
      </StaticRouter>
    </AppProviders>
  );
  expect(html).toContain('Skip to main content');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run App.providers.test.tsx`
Expected: FAIL — `AppProviders`/`AppContent`/`createAppQueryClient` are not exported.

- [ ] **Step 3: Implement the split**

In `App.tsx`:
1. Replace the module-level `const queryClient = new QueryClient({...})` with an exported factory:

```tsx
export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: Infinity, refetchOnWindowFocus: false },
    },
  });
}
```

2. Add `export` to `AppContent` (change `const AppContent` to `export const AppContent`).

3. Add `AppProviders`:

```tsx
export const AppProviders: React.FC<{ queryClient: QueryClient; children: React.ReactNode }> = ({
  queryClient,
  children,
}) => (
  <QueryClientProvider client={queryClient}>
    <LazyMotion features={domAnimation} strict>
      <ThemeProvider>
        <LandingThemeProvider>
          <UserFeaturesProvider>{children}</UserFeaturesProvider>
        </LandingThemeProvider>
      </ThemeProvider>
    </LazyMotion>
  </QueryClientProvider>
);
```

4. Rewrite the default `App` to compose providers + client-only bits (Router, FirebaseProvider stays in `index.tsx`, devtools, DevQuickLogin):

```tsx
const App: React.FC = () => {
  const [queryClient] = React.useState(createAppQueryClient);
  return (
    <AppProviders queryClient={queryClient}>
      {import.meta.env.DEV && <DevQuickLogin />}
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ScrollToTop />
        <AppContent />
      </Router>
      <ReactQueryDevtools initialIsOpen={false} />
    </AppProviders>
  );
};
export default App;
```

(Keep the existing imports for `Router`, `ScrollToTop`, `DevQuickLogin`, `ReactQueryDevtools`.)

5. `index.tsx` already wraps `<App/>` in `<FirebaseProvider>` — leave it as is. Confirm no other file imported the removed module-level `queryClient` (it was module-private, so none did).

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run App.providers.test.tsx`
Expected: PASS (`Skip to main content` is in `AppContent`).

> If this fails because a provider touches `window` server-side, that is fixed in Task 6; for now run with the `/about` route which renders static JSX. If it still throws on `LandingThemeProvider`, do Task 6 first, then return.

- [ ] **Step 5: Commit**

```bash
git add App.tsx index.tsx App.providers.test.tsx
git commit -m "refactor(ssg): split App into injectable AppProviders + AppContent"
```

---

### Task 3: Gate browser-only widgets with `ClientOnly`

Wrap the non-SEO, DOM-dependent widgets in `AppContent` and the recharts visualizer so the server render emits nothing for them.

**Files:**
- Modify: `App.tsx` (inside `AppContent`)
- Modify: `components/ScoreVisualizer.tsx` (recharts)
- Test: extend `App.providers.test.tsx`

**Interfaces:**
- Consumes: `ClientOnly` (Task 1).

- [ ] **Step 1: Write the failing test** (add to `App.providers.test.tsx`)

```tsx
test('charts and tour widgets are absent from server markup', () => {
  const qc = createAppQueryClient();
  const html = renderToStaticMarkup(
    <AppProviders queryClient={qc}>
      <StaticRouter location="/about"><AppContent /></StaticRouter>
    </AppProviders>
  );
  // driver.js / recharts containers must not appear server-side
  expect(html).not.toContain('recharts');
  expect(html).not.toContain('driver-');
});
```

- [ ] **Step 2: Run test to verify it fails (or errors)**

Run: `npx vitest run App.providers.test.tsx`
Expected: FAIL or throw (recharts/driver render server-side).

- [ ] **Step 3: Wrap widgets**

In `App.tsx`, import `ClientOnly` and wrap the trailing widget block in `AppContent`:

```tsx
import { ClientOnly } from './src/components/ClientOnly';
// ...
      {isLandingPage ? <div className="hidden lg:block"><Footer /></div> : <Footer />}
      <ClientOnly>
        <CompareBar />
        {!isLandingPage && <MobileBottomNav />}
        <WelcomeTour />
        <IntroPresentation />
        <BookmarkToast />
        <BookmarkAutoCategorize />
        <NamePromptModal />
      </ClientOnly>
```

In `components/ScoreVisualizer.tsx`, wrap the recharts return in `ClientOnly` (import from `../src/components/ClientOnly`). Render a fixed-height placeholder `div` server-side so layout does not jump:

```tsx
import { ClientOnly } from '../src/components/ClientOnly';
// at the top of the returned JSX, wrap the recharts tree:
return (
  <ClientOnly>
    {/* existing recharts JSX unchanged */}
  </ClientOnly>
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run App.providers.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add App.tsx components/ScoreVisualizer.tsx App.providers.test.tsx
git commit -m "feat(ssg): gate browser-only widgets behind ClientOnly"
```

---

### Task 4: SSR-safe `LandingThemeContext` + firebase module

**Files:**
- Modify: `contexts/LandingThemeContext.tsx`
- Modify: `src/auth/firebase.ts`
- Test: `contexts/LandingThemeContext.ssr.test.tsx`

**Interfaces:**
- Produces: `getInitialIsDark(): boolean` (exported pure helper, returns `false` when `window` is undefined).

- [ ] **Step 1: Write the failing test**

```tsx
// contexts/LandingThemeContext.ssr.test.tsx
// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { LandingThemeProvider } from './LandingThemeContext';

test('LandingThemeProvider renders server-side without touching localStorage', () => {
  expect(() =>
    renderToStaticMarkup(<LandingThemeProvider><div /></LandingThemeProvider>)
  ).not.toThrow();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run contexts/LandingThemeContext.ssr.test.tsx`
Expected: FAIL — `localStorage is not defined` / `window is not defined`.

- [ ] **Step 3: Guard the initializer**

In `contexts/LandingThemeContext.tsx`, replace the `useState` initializer body (the part reading `localStorage`/`matchMedia`) with a guarded helper:

```tsx
export function getInitialIsDark(): boolean {
  if (typeof window === 'undefined') return false; // SSR default: light
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return false;
  }
}
// ...
const [isDark, setIsDark] = useState<boolean>(getInitialIsDark);
```

Also guard the persistence `useEffect` (it already only runs client-side, but make the `document` access defensive):

```tsx
useEffect(() => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, isDark ? 'dark' : 'light');
  document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';
  const meta = document.querySelector('meta[name="theme-color"]');
  // ...existing body...
}, [isDark]);
```

In `src/auth/firebase.ts`, ensure module import is SSR-safe: wrap any `initializeApp`/`getAuth` calls so they only run when `typeof window !== 'undefined'`, exporting `auth`/`db` as `null` on the server. Minimal pattern:

```ts
const canInit = typeof window !== 'undefined' && isConfigured;
export const auth = canInit ? getAuth(app) : null;
export const db = canInit ? getFirestore(app) : null;
```

(Adapt to the file's existing structure; the goal is: importing this module under Node throws nothing and yields `auth === null`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run contexts/LandingThemeContext.ssr.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add contexts/LandingThemeContext.tsx src/auth/firebase.ts contexts/LandingThemeContext.ssr.test.tsx
git commit -m "fix(ssg): make LandingThemeContext and firebase import SSR-safe"
```

---

### Task 5: `useGuides` hook + convert guide pages

**Files:**
- Create: `src/hooks/useGuides.ts`
- Modify: `pages/GuidesIndexPage.tsx`, `pages/GuidePage.tsx`
- Test: `src/hooks/useGuides.test.tsx`

**Interfaces:**
- Produces:
  - `useGuides(): { guides: GuideSummary[]; loading: boolean }` — query key `['guides']`, fetch `/data/guides/guides.json`, returns `data.guides ?? []`.
  - `useGuide(slug: string): { guide: Guide | null; loading: boolean; notFound: boolean }` — query key `['guide', slug]`, fetch `/data/guides/${slug}.json`; `notFound` true on non-OK response.

- [ ] **Step 1: Write the failing test**

```tsx
// src/hooks/useGuides.test.tsx
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { GuidesIndexPage } from '../../pages/GuidesIndexPage';

test('GuidesIndexPage renders seeded guides synchronously (SSR)', () => {
  const qc = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  qc.setQueryData(['guides'], { guides: [{ slug: 'zakat-101', title: 'Zakat 101', description: 'x', readingTimeMinutes: 5 }] });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter><GuidesIndexPage /></MemoryRouter>
    </QueryClientProvider>
  );
  expect(html).toContain('Zakat 101');
  expect(html).not.toContain('Loading guides');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/hooks/useGuides.test.tsx`
Expected: FAIL — page still uses `useEffect`, renders "Loading guides…".

- [ ] **Step 3: Implement the hook and convert pages**

```ts
// src/hooks/useGuides.ts
import { useQuery } from '@tanstack/react-query';
import type { GuidesIndex, Guide, GuideSummary } from '../../scripts/lib/guide-seo';

export function useGuides(): { guides: GuideSummary[]; loading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: ['guides'],
    queryFn: async (): Promise<GuidesIndex> => {
      const r = await fetch('/data/guides/guides.json');
      return r.json();
    },
  });
  return { guides: data?.guides ?? [], loading: isLoading };
}

export function useGuide(slug: string): { guide: Guide | null; loading: boolean; notFound: boolean } {
  const { data, isLoading, error } = useQuery({
    queryKey: ['guide', slug],
    queryFn: async (): Promise<Guide> => {
      const r = await fetch(`/data/guides/${slug}.json`);
      if (!r.ok) throw new Error('not-found');
      return r.json();
    },
    enabled: !!slug,
    retry: false,
  });
  return { guide: data ?? null, loading: isLoading, notFound: !!error };
}
```

In `pages/GuidesIndexPage.tsx`: remove the `useState`/`useEffect`/`fetch` block; add `import { useGuides } from '../src/hooks/useGuides';` and `const { guides, loading } = useGuides();`. Keep the `document.title` side-effect in a separate small `useEffect` (title is also set by SSR meta injection, but keep client parity):

```tsx
useEffect(() => {
  document.title = 'Guides | Good Measure Giving';
  return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
}, []);
```

The existing `{loading ? … : guides.length === 0 ? … : …}` JSX is unchanged.

In `pages/GuidePage.tsx`: remove `useState`/`useEffect`/`fetch`; add `import { useGuide } from '../src/hooks/useGuide';`… (same file) → `const { guide, loading, notFound } = useGuide(slug || '');`. Keep `if (notFound) return <Navigate to="/guides" replace />;` and the `loading || !guide` branch unchanged. Move the `document.title = data.metaTitle` into a guarded effect:

```tsx
useEffect(() => {
  if (guide) document.title = guide.metaTitle;
  return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
}, [guide]);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/hooks/useGuides.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useGuides.ts src/hooks/useGuides.test.tsx pages/GuidesIndexPage.tsx pages/GuidePage.tsx
git commit -m "feat(ssg): seedable useGuides/useGuide hooks; convert guide pages"
```

---

### Task 6: `useCalculatorData` hook + convert calculator pages

**Files:**
- Create: `src/hooks/useCalculatorData.ts`
- Modify: `pages/ZakatCalculatorHubPage.tsx`, `pages/ZakatCalculatorAssetPage.tsx`
- Test: `src/hooks/useCalculatorData.test.tsx`

**Interfaces:**
- Produces: `useCalculatorData(): { data: CalculatorData | null; loading: boolean }` — query key `['calculator-data']`, fetch `/data/zakat-calculator/assets.json`. `CalculatorData` shape is the one already declared in the asset page (`{ hub, assets }`); move it into the hook file and import it in both pages.

- [ ] **Step 1: Write the failing test**

```tsx
// src/hooks/useCalculatorData.test.tsx
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ZakatCalculatorHubPage } from '../../pages/ZakatCalculatorHubPage';

test('calculator hub renders seeded hero text synchronously', () => {
  const qc = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  qc.setQueryData(['calculator-data'], {
    hub: { metaTitle: 't', metaDescription: 'd', heroText: 'Calculate your zakat now' },
    assets: [{ slug: 'cash-savings', displayName: 'Cash', heroAnswer: 'a' }],
  });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter><ZakatCalculatorHubPage /></MemoryRouter>
    </QueryClientProvider>
  );
  expect(html).toContain('Calculate your zakat now');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/hooks/useCalculatorData.test.tsx`
Expected: FAIL — hub still fetches in `useEffect`.

- [ ] **Step 3: Implement and convert**

```ts
// src/hooks/useCalculatorData.ts
import { useQuery } from '@tanstack/react-query';
import type { ZakatAssets } from '../../types';

export interface AssetSection { heading: string; paragraphs: string[]; }
export interface AssetFaq { q: string; a: string; }
export interface AssetEntry {
  slug: string; displayName: string; metaTitle: string; metaDescription: string;
  heroAnswer: string; zakatAssetKey: keyof ZakatAssets; inputLabel: string; inputHelp: string;
  sections: AssetSection[]; faq: AssetFaq[];
}
export interface CalculatorData {
  hub: { metaTitle: string; metaDescription: string; heroText: string };
  assets: AssetEntry[];
}

export function useCalculatorData(): { data: CalculatorData | null; loading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: ['calculator-data'],
    queryFn: async (): Promise<CalculatorData> => {
      const r = await fetch('/data/zakat-calculator/assets.json');
      return r.json();
    },
  });
  return { data: data ?? null, loading: isLoading };
}
```

In `ZakatCalculatorHubPage.tsx` and `ZakatCalculatorAssetPage.tsx`: delete the local `CalculatorData`/`AssetEntry` interfaces and the `useState`/`useEffect`/`fetch` blocks; import `useCalculatorData` (and `CalculatorData`/`AssetEntry` types) from `../src/hooks/useCalculatorData`; replace with `const { data, loading } = useCalculatorData();`. All downstream uses of `data` (e.g. `data?.assets`, `data?.hub.heroText`) are unchanged. Keep the `document.title` effects guarded as in Task 5.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/hooks/useCalculatorData.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useCalculatorData.ts src/hooks/useCalculatorData.test.tsx pages/ZakatCalculatorHubPage.tsx pages/ZakatCalculatorAssetPage.tsx
git commit -m "feat(ssg): seedable useCalculatorData hook; convert calculator pages"
```

---

### Task 7: `usePrompts` hooks + convert prompt pages

**Files:**
- Create: `src/hooks/usePrompts.ts`
- Modify: `pages/PromptsPage.tsx`, `pages/PromptDetailPage.tsx`
- Test: `src/hooks/usePrompts.test.tsx`

**Interfaces:**
- Produces:
  - `usePromptsIndex(): { data: PromptsIndex | null; loading: boolean }` — key `['prompts']`, fetch `/data/prompts/index.json`.
  - `usePromptDetail(id: string): { prompt: PromptDetail | null; loading: boolean; error: string | null }` — key `['prompt', id]`, fetch `/data/prompts/${id}.json`.
  - Move `PromptsIndex` and `PromptDetail` interfaces into the hook file; import them in the pages.

- [ ] **Step 1: Write the failing test**

```tsx
// src/hooks/usePrompts.test.tsx
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { PromptDetailPage } from '../../pages/PromptDetailPage';

test('prompt detail renders seeded prompt synchronously', () => {
  const qc = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  qc.setQueryData(['prompt', 'baseline-v3'], {
    id: 'baseline-v3', name: 'Baseline Narrative', category: 'narrative_generation',
    description: 'd', status: 'active', source_file: 'x', content: 'CONTENT', annotations: [],
  });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/prompts/baseline-v3']}>
        <PromptDetailPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  expect(html).toContain('Baseline Narrative');
});
```

> Note: `PromptDetailPage` reads `useParams().promptId`; the test routes via `MemoryRouter` but the page is rendered outside a matching `<Route>`. If `promptId` is undefined under this setup, wrap the page in `<Routes><Route path="/prompts/:promptId" element={<PromptDetailPage/>}/></Routes>` inside the `MemoryRouter` instead.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/hooks/usePrompts.test.tsx`
Expected: FAIL — page fetches in `useEffect`.

- [ ] **Step 3: Implement and convert**

```ts
// src/hooks/usePrompts.ts
import { useQuery } from '@tanstack/react-query';

export interface Prompt { id: string; name: string; category: string; description: string; status: 'active' | 'planned'; }
export interface PromptCategory { id: string; name: string; description: string; }
export interface PromptsIndex { prompts: Prompt[]; categories: PromptCategory[]; total_count: number; active_count: number; planned_count: number; }
export interface Annotation { section: string; lines: string; explanation: string; }
export interface PromptDetail extends Prompt { source_file: string; content: string; annotations: Annotation[]; }

export function usePromptsIndex(): { data: PromptsIndex | null; loading: boolean } {
  const { data, isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: async (): Promise<PromptsIndex> => {
      const r = await fetch('/data/prompts/index.json');
      return r.json();
    },
  });
  return { data: data ?? null, loading: isLoading };
}

export function usePromptDetail(id: string): { prompt: PromptDetail | null; loading: boolean; error: string | null } {
  const { data, isLoading, error } = useQuery({
    queryKey: ['prompt', id],
    queryFn: async (): Promise<PromptDetail> => {
      const r = await fetch(`/data/prompts/${id}.json`);
      if (!r.ok) throw new Error('Prompt not found');
      return r.json();
    },
    enabled: !!id,
    retry: false,
  });
  return { prompt: data ?? null, loading: isLoading, error: error ? (error as Error).message : null };
}
```

In `PromptsPage.tsx`: delete local `Prompt`/`PromptCategory`/`PromptsIndex` interfaces + the fetch state; import `usePromptsIndex` (+ types); `const { data, loading } = usePromptsIndex();`. Downstream `data?.prompts` etc. unchanged.

In `PromptDetailPage.tsx`: delete local `Annotation`/`PromptDetail` interfaces + fetch state; import `usePromptDetail` (+ types); `const { prompt, loading, error } = usePromptDetail(promptId || '');`. Keep `copied`/`expandedAnnotations` local state. Existing render branches unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/hooks/usePrompts.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hooks/usePrompts.ts src/hooks/usePrompts.test.tsx pages/PromptsPage.tsx pages/PromptDetailPage.tsx
git commit -m "feat(ssg): seedable usePrompts hooks; convert prompt pages"
```

---

### Task 8: Server entry (`entry-server.tsx`)

**Files:**
- Create: `entry-server.tsx`
- Test: `entry-server.test.tsx`

**Interfaces:**
- Consumes: `AppProviders`, `AppContent`, `createAppQueryClient` (Task 2).
- Produces: `render(url: string, seed: SeedEntry[]): Promise<string>` and `type SeedEntry = { queryKey: unknown[]; data: unknown }`. Resolves with fully-rendered HTML (all Suspense/lazy resolved) via `renderToPipeableStream` + `onAllReady`.

- [ ] **Step 1: Write the failing test**

```tsx
// entry-server.test.tsx
// @vitest-environment node
import { render } from './entry-server';

test('render() returns full HTML with seeded guide content', async () => {
  const html = await render('/guides', [
    { queryKey: ['guides'], data: { guides: [{ slug: 'zakat-101', title: 'Zakat 101', description: 'x', readingTimeMinutes: 5 }] } },
  ]);
  expect(html).toContain('Zakat 101');
  expect(html).toContain('Skip to main content');
}, 20000);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run entry-server.test.tsx`
Expected: FAIL — `./entry-server` not found.

- [ ] **Step 3: Implement**

```tsx
// entry-server.tsx
import React from 'react';
import { renderToPipeableStream } from 'react-dom/server';
import { Writable } from 'node:stream';
import { StaticRouter } from 'react-router-dom/server';
import { AppProviders, AppContent, createAppQueryClient } from './App';

export type SeedEntry = { queryKey: unknown[]; data: unknown };

export function render(url: string, seed: SeedEntry[]): Promise<string> {
  const queryClient = createAppQueryClient();
  for (const { queryKey, data } of seed) queryClient.setQueryData(queryKey, data);

  return new Promise<string>((resolve, reject) => {
    const chunks: Buffer[] = [];
    const writable = new Writable({
      write(chunk, _enc, cb) { chunks.push(Buffer.from(chunk)); cb(); },
      final(cb) { cb(); },
    });
    writable.on('finish', () => resolve(Buffer.concat(chunks).toString('utf8')));

    let didError = false;
    const { pipe, abort } = renderToPipeableStream(
      <AppProviders queryClient={queryClient}>
        <StaticRouter location={url}>
          <AppContent />
        </StaticRouter>
      </AppProviders>,
      {
        onAllReady() { pipe(writable); },
        onError(err) { didError = true; reject(err); },
      }
    );
    setTimeout(() => { if (!didError) abort(); }, 15000);
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run entry-server.test.tsx`
Expected: PASS

> If render throws on a provider/component touching the DOM, that component must be wrapped in `ClientOnly` (Task 3) or guarded (Task 4). Add the guard, re-run.

- [ ] **Step 5: Commit**

```bash
git add entry-server.tsx entry-server.test.tsx
git commit -m "feat(ssg): add entry-server render() via renderToPipeableStream"
```

---

### Task 9: Vite SSR build config + npm scripts

**Files:**
- Create: `vite.config.ssr.ts`
- Modify: `package.json` (scripts)

**Interfaces:**
- Produces: `dist-server/entry-server.js` (importable Node ESM module exporting `render`).

- [ ] **Step 1: Write the failing test (build smoke)**

```bash
# manual check used as the test for this task
npx vite build --config vite.config.ssr.ts
node -e "import('./dist-server/entry-server.js').then(m => { if (typeof m.render !== 'function') throw new Error('no render export'); console.log('OK'); })"
```
Expected (before impl): FAIL — config file missing.

- [ ] **Step 2: Implement the SSR config**

```ts
// vite.config.ssr.ts
import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/',
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, '.') } },
  build: {
    ssr: 'entry-server.tsx',
    outDir: 'dist-server',
    emptyOutDir: true,
    rollupOptions: { output: { format: 'esm', entryFileNames: 'entry-server.js' } },
  },
});
```

- [ ] **Step 3: Wire npm scripts**

In `package.json`, change:

```json
"build:ssr": "vite build --config vite.config.ssr.ts",
"postbuild": "npm run build:ssr && tsx scripts/generateSitemap.ts && tsx scripts/prerender.ts",
```

(Keep `"build": "vite build"` and the existing `prebuild`.)

- [ ] **Step 4: Run the build smoke check**

Run the two commands from Step 1.
Expected: prints `OK`.

- [ ] **Step 5: Commit**

```bash
git add vite.config.ssr.ts package.json
git commit -m "build(ssg): add Vite SSR build + build:ssr script"
```

---

### Task 10: Render SEO routes in `prerender.ts`; remove puppeteer

Replace the puppeteer/browser/static branching with: for SEO routes, call `render()` from the SSR bundle and inject the body into `#root`; for all other routes, keep meta-only injection.

**Files:**
- Modify: `scripts/prerender.ts`
- Modify: `package.json` (remove `puppeteer`)
- Test: `scripts/prerender.ssr.test.ts` + post-build verification

**Interfaces:**
- Consumes: `render`, `SeedEntry` from `dist-server/entry-server.js`; existing `PageMeta` (has `.route`) and the per-route data loaders already in `prerenderPages()`.

- [ ] **Step 1: Add a seed-builder + write the failing test**

Add an exported helper in `scripts/prerender.ts` that maps a `PageMeta` (plus loaded data) to seed entries, so it is unit-testable:

```ts
// in scripts/prerender.ts
export type SeedEntry = { queryKey: unknown[]; data: unknown };

// Routes we server-render (everything else stays meta-only)
export const SSR_ROUTE_PREFIXES = ['/charity/', '/guides', '/causes', '/zakat-calculator', '/prompts', '/methodology', '/about', '/faq'];
export function isSsrRoute(route: string): boolean {
  if (route === '/guides' || route === '/causes' || route === '/zakat-calculator' || route === '/prompts') return true;
  return SSR_ROUTE_PREFIXES.some((p) => p.endsWith('/') && route.startsWith(p)) ||
    ['/methodology', '/about', '/faq'].includes(route);
}
```

```ts
// scripts/prerender.ssr.test.ts
import { isSsrRoute } from './prerender';

test('classifies SSR vs meta-only routes', () => {
  expect(isSsrRoute('/charity/81-2822877')).toBe(true);
  expect(isSsrRoute('/guides')).toBe(true);
  expect(isSsrRoute('/guides/zakat-101')).toBe(true);
  expect(isSsrRoute('/about')).toBe(true);
  expect(isSsrRoute('/')).toBe(false);
  expect(isSsrRoute('/browse')).toBe(false);
  expect(isSsrRoute('/profile')).toBe(false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run scripts/prerender.ssr.test.ts`
Expected: FAIL — `isSsrRoute` not exported.

- [ ] **Step 3: Implement seeding + SSR injection; remove browser/static modes**

In `scripts/prerender.ts`:

1. Add `isSsrRoute`/`SeedEntry` (above).
2. Add a function that builds seed entries for a route from already-loaded data. Reuse the data already read in `prerenderPages()` (charity details, guides list + per-guide JSON, calculator assets, prompts index + per-prompt JSON). Build a lookup so each `meta.route` maps to its seed:

```ts
function seedFor(route: string, ctx: {
  charityDetails: Map<string, unknown>;     // ein -> detail json
  guidesIndex: unknown; guideBySlug: Map<string, unknown>;
  calculatorData: unknown;
  promptsIndex: unknown; promptById: Map<string, unknown>;
}): SeedEntry[] {
  if (route.startsWith('/charity/')) {
    const ein = route.slice('/charity/'.length);
    const d = ctx.charityDetails.get(ein);
    return d ? [{ queryKey: ['charity', ein], data: d }] : [];
  }
  if (route === '/guides') return ctx.guidesIndex ? [{ queryKey: ['guides'], data: ctx.guidesIndex }] : [];
  if (route.startsWith('/guides/')) {
    const slug = route.slice('/guides/'.length);
    const g = ctx.guideBySlug.get(slug);
    return g ? [{ queryKey: ['guide', slug], data: g }] : [];
  }
  if (route.startsWith('/zakat-calculator')) return ctx.calculatorData ? [{ queryKey: ['calculator-data'], data: ctx.calculatorData }] : [];
  if (route === '/prompts') return ctx.promptsIndex ? [{ queryKey: ['prompts'], data: ctx.promptsIndex }] : [];
  if (route.startsWith('/prompts/')) {
    const id = route.slice('/prompts/'.length);
    const p = ctx.promptById.get(id);
    return p ? [{ queryKey: ['prompt', id], data: p }] : [];
  }
  return []; // causes + static pages need no seed
}
```

3. Replace `resolvePrerenderMode()` and the entire browser/static branch in `prerenderPages()` with a single SSR path:

```ts
const { render } = await import(path.join(DIST_DIR, '../dist-server/entry-server.js'));
const baseHtml = fs.readFileSync(path.join(DIST_DIR, 'index.html'), 'utf-8');
let written = 0;
for (const meta of metas) {
  let html = injectMeta(baseHtml, meta); // existing head/meta/canonical injection
  if (isSsrRoute(meta.route)) {
    try {
      const body = await render(meta.route, seedFor(meta.route, ctx));
      html = html.replace('<div id="root"></div>', `<div id="root">${body}</div>`);
    } catch (err) {
      console.warn(`  SSR failed for ${meta.route}; writing meta-only shell:`, (err as Error).message);
    }
  }
  const outDir = path.join(DIST_DIR, meta.route === '/' ? '' : meta.route);
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(meta.route === '/' ? path.join(DIST_DIR, 'index.html') : path.join(outDir, 'index.html'), html, 'utf-8');
  written++;
}
console.log(`Prerender complete: ${written} pages written to dist/`);
```

4. Build `ctx` from the data the function already loads (charity details from `DATA_DIR/charity-${ein}.json`, guides, calculator, prompts). Remove the `puppeteer` dynamic import, `startPreviewServer`, `processPage`, worker pool, and `writePrerenderedFromBaseHtml`/`resolvePrerenderMode`.
5. Keep `writeRedirects(metas)` and the existing `injectMeta` exactly as they are.

- [ ] **Step 4: Run unit test + full build verification**

```bash
npx vitest run scripts/prerender.ssr.test.ts
npm run build
# verify a charity page now has real body content:
node -e "const fs=require('fs');const h=fs.readFileSync('dist/charity/81-2822877/index.html','utf8');const body=h.slice(h.indexOf('<div id=\"root\">'));if(body.length<2000||!h.includes('Yaqeen'))throw new Error('charity body too small/empty');console.log('charity OK',body.length);"
node -e "const fs=require('fs');const h=fs.readFileSync('dist/about/index.html','utf8');if(!h.includes('<div id=\"root\"><'))throw new Error('about not SSR');console.log('about OK');"
```
Expected: vitest PASS; both node checks print OK with a large body length.

- [ ] **Step 5: Remove puppeteer + commit**

```bash
npm remove puppeteer
git add scripts/prerender.ts scripts/prerender.ssr.test.ts package.json package-lock.json
git commit -m "feat(ssg): SSR-render SEO routes in prerender; drop puppeteer"
```

---

### Task 11: Full verification + cleanup

**Files:**
- Verify only; possible small fixes.

- [ ] **Step 1: Run the whole test suite**

Run: `npx vitest run`
Expected: all green (including pre-existing meta/canonical/sitemap tests).

- [ ] **Step 2: Verify SSR coverage across route types**

```bash
for p in charity/81-2822877 guides guides/$(ls data/guides | grep -v guides.json | head -1 | sed 's/.json//') zakat-calculator prompts methodology about faq; do
  f="dist/$p/index.html"; [ "$p" = "about" ] && f="dist/about/index.html";
  node -e "const fs=require('fs');const h=fs.readFileSync('$f','utf8');const i=h.indexOf('<div id=\"root\">');const len=h.length-i;if(len<1500)throw new Error('$p body too small: '+len);console.log('$p OK',len);"
done
```
Expected: each prints OK with a non-trivial length.

- [ ] **Step 3: Verify non-SSR routes still ship meta-only shells (unchanged)**

```bash
node -e "const fs=require('fs');const h=fs.readFileSync('dist/browse/index.html','utf8');if(!h.includes('<div id=\"root\"></div>'))throw new Error('browse should stay meta-only');if(!h.includes('rel=\"canonical\"'))throw new Error('browse missing canonical');console.log('browse meta-only OK');"
```
Expected: prints OK.

- [ ] **Step 4: Verify sitemap + 308 redirects unaffected**

```bash
grep -c '<loc>' dist/sitemap.xml
head -3 dist/_redirects
```
Expected: sitemap count unchanged from before; `_redirects` still lists `... 308` rules.

- [ ] **Step 5: Commit any fixes + update spec status**

```bash
git add -A
git commit -m "test(ssg): full SSR build verification green"
```

---

## Self-Review Notes

- **Spec coverage:** App refactor (T2), data seeding + 6-page conversion (T5–T7), SSR-safety (T3–T4), entry-server (T8), build pipeline (T9–T10), puppeteer removal (T10), testing throughout, non-SSR routes preserved (T10/T11). Causes + static pages need no conversion (already synchronous) — covered by SSR injection in T10 and verified in T11.
- **Lazy/Suspense:** handled via `renderToPipeableStream` + `onAllReady` (T8), a refinement over the spec's `renderToString` (which cannot resolve `React.lazy`).
- **Query keys** are consistent across hooks (T5–T7) and the seed-builder (T10): `['charity', ein]`, `['guides']`, `['guide', slug]`, `['calculator-data']`, `['prompts']`, `['prompt', id]`.
- **Risk:** the entry-server render (T8) is where any remaining DOM-touching component will surface; mitigations are `ClientOnly` (T3) and provider guards (T4), applied before T8.

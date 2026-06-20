# Build-time SSR (SSG) via `renderToString`

**Date:** 2026-06-20
**Status:** Approved design
**Branch:** `worktree-ssg-renderToString`

## Problem

Production pages ship empty `<body>` shells (`<div id="root"></div>`, 45 bytes). All
content is client-rendered by React. Google must execute JS to see anything, and for a
new, low-authority site with ~173 near-identical empty shells it defers that render
budget — Search Console reports **"Discovered – currently not indexed"** for 173 pages;
only ~11 are indexed.

Root cause: `website/scripts/prerender.ts` `resolvePrerenderMode()` forces a meta-only
**"static" mode whenever it detects Cloudflare** (`CF_PAGES`). The full-content
(puppeteer "browser") render only runs locally. Cloudflare's build — the one that
deploys — ships meta tags with an empty body.

Redirect/canonical/sitemap issues from earlier passes are already fixed and deployed
(see `[[seo-trailing-slash]]`). This is the remaining blocker.

## Goal

Server-render real content into the body of SEO-critical pages **at build time, with no
headless browser**, so the output works in Cloudflare's build and Google gets indexable
content. Keep the git-push deploy workflow. Drop the flaky `puppeteer` dependency.

## Scope

**SSR (full content):** charity detail (`/charity/:id`), guides (`/guides`,
`/guides/:slug`), causes (`/causes`, `/causes/:slug`), zakat-calculator
(`/zakat-calculator`, `/zakat-calculator/:asset`), prompts (`/prompts`,
`/prompts/:id`), and static content pages (`/methodology`, `/about`, `/faq`).

**Not SSR (keep today's meta-only shell):** landing (`/` — already indexed,
animation-heavy), browse, profile, compare, bookmarks, join-plan, privacy, 404. These
still get correct per-page meta/canonical tags as today.

## Approach (approved: A — non-hydrated SSG)

Render the app to an HTML string per route using `StaticRouter` + a react-query cache
pre-seeded with that route's data (loaded from disk), inject into `#root`. **Client stays
non-hydrated** (`createRoot`, unchanged) — it re-renders over the server HTML exactly as
it does over today's puppeteer output. This eliminates the entire hydration-mismatch class
of bugs (theme, auth, dates) and keeps runtime UX identical. Hydration (`hydrateRoot`)
can be a later optimization.

## Design

### 1. App refactor (router/client-agnostic)

Split `App.tsx` so the provider tree is reusable across client and server:

- **`AppProviders`** — wraps `children` in `QueryClientProvider` (accepts an **injected**
  `queryClient` prop instead of creating its own), `LazyMotion`, `ThemeProvider`,
  `LandingThemeProvider`, `UserFeaturesProvider`. Router-agnostic.
- **Client** (`index.tsx`): `<FirebaseProvider><AppProviders qc={qc}><BrowserRouter><AppContent/></BrowserRouter></AppProviders></FirebaseProvider>`.
- **Server** (`entry-server.tsx`): `renderToString(<AppProviders qc={seededQc}><StaticRouter location={url}><AppContent/></StaticRouter></AppProviders>)`.
  **`FirebaseProvider` is omitted server-side** → auth defaults to logged-out →
  crawlers receive the baseline/anonymous view (the intended gated content).
- `AppContent` (the `Routes` + chrome) is unchanged.

### 2. Data seeding + 6-page conversion

Convert the `useEffect`+`fetch` pages to react-query hooks mirroring `useCharity`, so all
SSR routes share one seeding path:

- `pages/GuidesIndexPage.tsx`, `pages/GuidePage.tsx`
- `pages/ZakatCalculatorHubPage.tsx`, `pages/ZakatCalculatorAssetPage.tsx`
- `pages/PromptsPage.tsx`, `pages/PromptDetailPage.tsx`

Server seeds the cache per route before render:

| Query key | Disk source |
|---|---|
| `['charity', ein]` | `data/charities/charity-{ein}.json` |
| `['charities']` | `data/charities.json` (only if an SSR page needs the index) |
| `['guides']` | `data/guides/guides.json` |
| `['guide', slug]` | `data/guides/{slug}.json` |
| `['calculator-assets']` | `data/zakat-calculator/assets.json` |
| `['prompts']` | `public/data/prompts/index.json` |
| `['prompt', id]` | `public/data/prompts/{id}.json` |

Causes pages (static `import causesData`) and static pages (static JSX) need no seeding.

react-query with `staleTime: Infinity` returns seeded data synchronously during
`renderToString`; the `fetch` queryFn never runs on the server.

### 3. SSR-safety hardening

- `contexts/LandingThemeContext.tsx`: guard the `localStorage`/`matchMedia` `useState`
  initializer with `typeof window !== 'undefined'` (default light on server). The
  `useEffect` persistence is already SSR-safe (effects don't run server-side).
- `src/auth/firebase.ts`: guard so importing in Node does not crash (provider is skipped
  server-side regardless).
- **`<ClientOnly>` wrapper** (returns `null` until mounted) around non-SEO,
  browser-dependent widgets so the server emits nothing for them and never hits a DOM-only
  code path: `ScoreVisualizer`/recharts, `WelcomeTour` (driver.js), `IntroPresentation`,
  `MobileBottomNav`, `CompareBar`, `BookmarkToast`, `BookmarkAutoCategorize`,
  `NamePromptModal`, `DevQuickLogin`. Charts still render for users after mount.
- **Lazy pages**: `renderToString` cannot suspend, so `entry-server.render()` is **async**
  and `await`s the SSR'd routes' page-module imports (resolving `React.lazy`) before
  rendering.

### 4. Build pipeline

`package.json` build sequence:

1. `vite build` (client) — unchanged; emits `dist/` + base `index.html`.
2. `vite build --ssr entry-server.tsx` → server bundle (e.g. `dist-server/`).
3. New renderer (replaces the puppeteer path in `prerender.ts`): for each **SEO route**,
   load seed from disk → `await render(url, seed)` → inject body into `#root` of the base
   HTML + existing head/meta injection (`injectMeta`) → write `dist/<route>/index.html`.
   **Non-SEO routes** keep today's meta-only shell.
4. `generateSitemap.ts` and the `_redirects`/308 generation (`writeRedirects`) are
   unchanged and continue to run.

Remove `puppeteer` (devDependency), `resolvePrerenderMode()`, and the browser/static mode
branching. The new path needs no headless browser, so it runs identically locally and on
Cloudflare.

### 5. Testing (TDD)

- **Unit**: `render('/charity/<ein>', seed)` returns HTML containing the charity name in
  an `<h1>` and key facts; assert visible word count > threshold. Same for a guide,
  calculator asset, and prompt.
- **Smoke**: each SSR route type renders without throwing under a Node (no-`window`)
  environment.
- **Build verification**: post-build, a charity page's `<body>` exceeds a size threshold
  and contains the charity name; a guide page contains its title.
- Existing meta/canonical/sitemap/`_redirects` behavior stays green.

### 6. Risks & mitigations

- recharts / driver.js SSR crashes → sidestepped via `<ClientOnly>`.
- firebase import on server → module guard + provider skipped server-side.
- lazy/Suspense can't suspend in `renderToString` → async preload before render.
- Flash from non-hydrated re-render → identical to today's puppeteer output; acceptable.
- 6-page conversion scope creep → each mirrors `useCharity`; covered by tests.

## Out of scope

- Hydration (`hydrateRoot`) and dehydrated-state injection — future optimization.
- SSR for landing/browse/auth pages.
- Any visual/content changes — output content must match what the SPA renders today.

## Success criteria

- Production charity/guide/causes/calculator/prompt/static pages serve a non-empty
  `<body>` containing the page's real text content.
- Build runs with no headless browser (verified by removing puppeteer).
- Sitemap, canonical, and 308 redirect behavior unchanged.
- Over the following weeks, "Discovered – currently not indexed" count drops as Google
  recrawls.

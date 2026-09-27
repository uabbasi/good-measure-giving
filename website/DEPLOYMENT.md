# Good Measure Giving Website Deployment

The site is a Vite React app with build-time prerendering, deployed as a
Cloudflare **Worker** with static assets (`wrangler.jsonc`, entry `src/worker.ts`).
It is not a Cloudflare Pages project.

## Cloudflare Workers Builds

Pushing to `main` triggers a build (trigger "Deploy default branch"):

- Root directory: `/website`
- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`
- Branches: `main` only. Other branches and PRs get no build or preview.
- Node: Cloudflare's default (24.x as of Sep 2026)

`npm run build` runs `vite build`, then `postbuild`: the SSR bundle, `generateSitemap.ts`,
and `prerender.ts`, which writes a static page per route into `dist/`.

The prerender fails the build if any internal link lacks a trailing slash or points
at a route with no prerendered page. A failed build does not deploy; the live site
stays on the last good version.

## Routing

`src/worker.ts` handles every request:

1. Proxies `/__/auth/*` to Firebase (same-origin auth for Safari).
2. Serves the static asset. `/foo/` resolves to the prerendered `/foo/index.html`.
3. Falls back to the SPA shell only for routes with no prerendered page.

`assets.not_found_handling` must stay `"none"` so the assets layer doesn't
intercept `/__/auth/*` before the Worker runs. No-slash URLs 308-redirect to the
slash form via the `dist/_redirects` file that `prerender.ts` generates.

## Environment Variables (Cloudflare)

Set on the Workers Builds trigger (build-time variables):

- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_AUTH_DOMAIN`,
  `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_PROJECT_ID`,
  `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_GA_MEASUREMENT_ID`

`VITE_*` values are embedded client side at build time. Never put private
secrets in them.

## Release Checklist

1. Run `npm run build` locally; it fails on the same link checks Cloudflare runs
2. Run `npm run preview` and spot-check routes and charity detail pages
3. Push to `main`
4. Confirm the "Workers Builds: good-measure-giving" check on the commit succeeds
5. Spot-check production routes

## Troubleshooting

### Build failed on Cloudflare
- Read the build log in the Cloudflare dashboard, or via the API:
  `GET /accounts/<account>/builds/builds/<build_uuid>/logs`
- "Internal links that redirect or have no prerendered page": fix the listed
  href (add the trailing slash, or make sure the target route is prerendered)

### Direct route shows the home page
- The route has no prerendered page, so the Worker served the SPA shell. Check
  that `prerender.ts` emits it

### Data is stale
- Re-run the pipeline export and `npm run convert-data`
- Rebuild and redeploy

### Analytics not tracking
- Confirm `VITE_GA_MEASUREMENT_ID` is set in Cloudflare
- Confirm traffic is not from localhost

### Analytics configuration for the tracking repair

The application sends its own `page_view` events on route changes and suppresses the initial automatic GA4 page view. Keep **Page views → Advanced settings → Page changes based on browser history events** disabled in GA4 Enhanced Measurement for the GMG web stream. Leave the other Enhanced Measurement settings enabled. The API equivalent is `pageChangesEnabled: false` on property `518369044`, stream `13243971387`. Otherwise route changes will still be counted twice.

Register these event-scoped custom dimensions in GA4 so the analytics reports can query them:

| Event parameter | Display name |
| --- | --- |
| `charity_name` | Charity name |
| `auth_type` | Authentication type |
| `search_term` | Search term |

These settings require GA4 Editor access. The service account's Editor access, the disabled history setting, and all three custom dimensions were verified through the Admin and reporting APIs on 2026-09-11. Registration makes future event parameters reportable; it does not repair historical data.

Both GA4 and Cloudflare's beacon load only on `goodmeasuregiving.org` and `www.goodmeasuregiving.org`. Local and preview hosts intentionally send neither tracker. After deployment, verify one GA4 page view per page load/route change, a settled `search` event, `charity_card_click`, `charity_view`, and `donate_click`. Successful sign-ins should fire only after completed popup, redirect, or email authentication, never when restoring an existing session. A donation click records an outbound action, not a completed donation.

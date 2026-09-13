# Good Measure Giving Website Deployment

This website is a Vite React SPA deployed on Cloudflare Pages.

## Cloudflare Pages Configuration

Use these project settings:

- Framework preset: `Vite`
- Root directory: `website`
- Build command: `npm run build`
- Build output directory: `dist`
- Node version: `20` (recommended)

## SPA Routing

Client side routes must fallback to `index.html`.

Create `website/public/_redirects` with:

```text
/*  /index.html  200
```

Without this, direct loads like `/charity/<id>` can return 404.

## Environment Variables (Cloudflare)

Set in Cloudflare Pages project settings:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_GA_MEASUREMENT_ID` (optional)

Do not store private server side secrets in `VITE_*` variables.

## Release Checklist

1. Run `npm install`
2. Run `npm run build`
3. Run `npm run preview` and verify routes
4. Verify data conversion output in `src/data/charities.ts`
5. Push to `main` and confirm Cloudflare deploy succeeds
6. Validate production routes and charity detail pages

## Troubleshooting

### Direct route returns 404
- Confirm `public/_redirects` is present in deployed build
- Confirm Cloudflare project root is `website`

### Data is stale
- Re run pipeline export and `npm run convert-data`
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

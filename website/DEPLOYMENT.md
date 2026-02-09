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

# Good Measure Giving Website

React and TypeScript frontend for browsing charity evaluations.

## Quick Start

```bash
cd website
npm install
npm run dev
```

Default local URL: `http://localhost:5173`

## Build

```bash
npm run build
npm run preview
```

- Build output: `website/dist/`
- `npm run build` runs data conversion (`scripts/convertData.ts`) before Vite build

## Data Flow

Pipeline exports data into `website/data/`.
Frontend conversion script maps this into `website/src/data/charities.ts`.

```bash
npm run convert-data
```

## Environment Variables

Create local file:

```bash
cp .env.example .env.local
```

Common values:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_GA_MEASUREMENT_ID` (optional)

Notes:
- `VITE_*` values are embedded client side at build time
- Never put private secrets in `VITE_*` variables

## Deployment

Deployment target is Cloudflare Pages.
See `DEPLOYMENT.md` for build settings and SPA routing rules.

## Tests

```bash
npm run test
npm run test:e2e
```

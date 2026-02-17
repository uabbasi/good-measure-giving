# Good Measure Giving Website

React and TypeScript frontend for browsing charity evaluations.

## Quick Start

```bash
cd website
npm install
npm run dev
```

Default local URL: `http://localhost:3000`

## iOS Simulator (Xcode)

Use iOS Simulator to validate mobile layout and interactions:

```bash
cd website
npm run dev:ios:sim
```

This command:
- starts the Vite dev server on `http://127.0.0.1:3000`
- boots an iPhone simulator (or uses a booted one)
- opens Safari in the simulator at your local URL

If the server is already running, just open the simulator URL:

```bash
npm run ios:open
```

Optional:
- set `IOS_SIM_DEVICE=<device-udid>` to target a specific simulator

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

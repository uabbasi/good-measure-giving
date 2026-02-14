# Good Measure Giving

Evidence driven charity evaluation for the Muslim community.

Good Measure Giving helps Muslims direct zakat and sadaqah to charities with stronger evidence of impact, governance quality, and zakat alignment.

## What This Repo Contains

- `data-pipeline/`: Python pipeline that collects, reconciles, scores, and exports charity data
- `website/`: React and TypeScript application that presents evaluations
- `shared/` (gitignored): Local artifacts created during pipeline runs

## Quick Start

### Website

```bash
cd website
npm install
npm run dev
```

Vite runs locally at `http://localhost:5173`.

### Data Pipeline

```bash
cd data-pipeline
uv sync

# Canonical full pipeline (crawl -> extract -> discover -> synthesize ->
# baseline -> rich -> judge -> export)
uv run python streaming_runner.py --charities pilot_charities.txt --workers 10
```

## Environment Setup

```bash
cp .env.example .env
cp website/.env.example website/.env.local
```

Important notes:
- Never commit `.env` or `.env.local`
- `VITE_GA_MEASUREMENT_ID` is optional and public (not a secret)
- Supabase anon and public keys are expected to be public client keys

## Data Sources and Usage Policy

This project integrates data from third party sources such as Charity Navigator, Candid, ProPublica, BBB, CauseIQ, and official charity websites.

If you run this pipeline in production or distribute derived datasets:
- You are responsible for complying with each source Terms of Use, robots.txt, API licenses, and attribution requirements.
- Prefer official APIs where available.
- Do not commit copyrighted raw page dumps from third party sites.

## Open Source Hygiene

Before publishing:
- Verify no secrets or internal credentials are committed
- Verify no private analytics IDs are hardcoded in source
- Verify security disclosure instructions in `SECURITY.md` are correct
- Verify branding uses `Good Measure Giving` consistently in public docs

## Documentation

- `data-pipeline/README.md`: Pipeline usage and architecture
- `website/README.md`: Website development workflow
- `website/DEPLOYMENT.md`: Cloudflare deployment
- `SECURITY.md`: Vulnerability disclosure process

## License

Apache-2.0. See `LICENSE`.

## Disclaimer

This project provides informational guidance only and is not religious or legal advice. For binding zakat rulings, consult qualified scholars.

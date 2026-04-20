# SEO Track 4: Public Zakat Calculator Pages (Infrastructure + cash-savings)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/zakat-calculator` hub + `/zakat-calculator/:asset` pages for the biggest head-term SEO opportunity in the niche ("zakat calculator", "zakat on gold", "zakat on stocks"). Ship infrastructure + `cash-savings` as the seed asset; remaining 6 assets (gold-silver, stocks, 401k-retirement, crypto, business-assets, real-estate) arrive as data-only commits.

**Architecture:** `website/src/utils/zakatCalculator.ts` already exists with `calculateZakat()` and `NISAB_USD` — no extraction needed. New calculator pages reuse this pure function. Each asset page is generated from a data entry in `website/data/zakat-calculator/assets.json` that defines the asset's label, input metadata, 400–800 word explainer, and FAQ. One React page component (`ZakatCalculatorAssetPage`) handles all asset types, parametrized by slug. Schema is WebApplication + FAQPage + BreadcrumbList per asset page; CollectionPage + BreadcrumbList for the hub.

**Tech Stack:** TypeScript 5.8, React 19, React Router 6, Vitest 4, existing `calculateZakat` pure function, existing prerender pipeline.

**Spec reference:** `docs/superpowers/specs/2026-04-19-seo-strategy-design.md` — Track 4 section.

**Out of scope (follow-up data commits):** Assets #2–#7 (gold-silver, stocks, 401k-retirement, crypto, business-assets, real-estate). Each is one entry in `assets.json` plus any asset-specific fiqh content. Code ships once; content rolls out.

**Also out of scope for this plan:** Daily metal-price refresh pipeline (spec mentions this but it's an operations task, not a frontend one — handle as a separate project when the gold-silver asset ships).

---

## File Structure

**New files:**
- `website/scripts/lib/calculator-seo.ts` — pure helpers: slug validation, known-asset list. Minimal surface.
- `website/scripts/lib/calculator-seo.test.ts` — Vitest unit tests.
- `website/data/zakat-calculator/assets.json` — seed data: hub metadata + 1 asset (cash-savings).
- `website/pages/ZakatCalculatorHubPage.tsx` — `/zakat-calculator/` hub listing all assets.
- `website/pages/ZakatCalculatorAssetPage.tsx` — `/zakat-calculator/:asset` asset-specific page.
- `website/scripts/copyCalculator.ts` — copies `data/zakat-calculator/` to `public/data/zakat-calculator/` at build time.

**Modified files:**
- `website/App.tsx` — routes `/zakat-calculator` and `/zakat-calculator/:asset`.
- `website/package.json` — `predev` + `prebuild` hooks run `copyCalculator.ts`.
- `website/scripts/prerender.ts` — load calculator data, generate PageMeta for hub + each asset with WebApplication + FAQPage + BreadcrumbList schema.
- `website/scripts/generateSitemap.ts` — emit `/zakat-calculator` + 1 `/zakat-calculator/cash-savings` URL (more arrive later).
- `website/tests/e2e/seo-schema.spec.ts` — 3 new scenarios.

**Reuses** `website/src/utils/zakatCalculator.ts` (existing, unchanged).

---

## Task 1: Calculator taxonomy helpers

**Files:**
- Create: `website/scripts/lib/calculator-seo.ts`
- Create: `website/scripts/lib/calculator-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Create `website/scripts/lib/calculator-seo.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { isValidAssetSlug, KNOWN_ASSET_SLUGS } from './calculator-seo';

describe('isValidAssetSlug', () => {
  it('accepts every known asset slug', () => {
    for (const slug of KNOWN_ASSET_SLUGS) {
      expect(isValidAssetSlug(slug)).toBe(true);
    }
  });

  it('rejects unknown slugs', () => {
    expect(isValidAssetSlug('not-an-asset')).toBe(false);
    expect(isValidAssetSlug('')).toBe(false);
  });
});

describe('KNOWN_ASSET_SLUGS', () => {
  it('includes all 7 asset types from the spec', () => {
    expect(KNOWN_ASSET_SLUGS).toContain('cash-savings');
    expect(KNOWN_ASSET_SLUGS).toContain('gold-silver');
    expect(KNOWN_ASSET_SLUGS).toContain('stocks');
    expect(KNOWN_ASSET_SLUGS).toContain('401k-retirement');
    expect(KNOWN_ASSET_SLUGS).toContain('crypto');
    expect(KNOWN_ASSET_SLUGS).toContain('business-assets');
    expect(KNOWN_ASSET_SLUGS).toContain('real-estate');
    expect(KNOWN_ASSET_SLUGS).toHaveLength(7);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

From `website/`: `npm test -- --run scripts/lib/calculator-seo.test.ts`
Expected: FAIL — `Failed to resolve import './calculator-seo'`.

- [ ] **Step 3: Write minimal implementation**

Create `website/scripts/lib/calculator-seo.ts`:

```typescript
/**
 * Zakat calculator taxonomy helpers.
 *
 * The list of known asset slugs is canonical — any asset slug rendered must
 * appear here. This is intentionally stricter than a free-form pattern:
 * calculator pages depend on fiqh-accurate per-asset content, and we don't
 * want crawlers finding thin auto-generated asset pages.
 */

export const KNOWN_ASSET_SLUGS = [
  'cash-savings',
  'gold-silver',
  'stocks',
  '401k-retirement',
  'crypto',
  'business-assets',
  'real-estate',
] as const;

export type AssetSlug = (typeof KNOWN_ASSET_SLUGS)[number];

export function isValidAssetSlug(slug: string): slug is AssetSlug {
  return (KNOWN_ASSET_SLUGS as readonly string[]).includes(slug);
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/calculator-seo.test.ts`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/calculator-seo.ts website/scripts/lib/calculator-seo.test.ts
git commit -m "feat(seo): add calculator asset slug helpers"
```

---

## Task 2: Calculator data seed (hub + cash-savings)

**Files:**
- Create: `website/data/zakat-calculator/assets.json`

Defines the shape that all 7 asset pages will eventually share. Only cash-savings has content at seed time; the others appear in follow-up commits.

Shape per asset:
- `slug` — URL slug (matches `KNOWN_ASSET_SLUGS`)
- `displayName` — UI label
- `metaTitle` — SEO title
- `metaDescription` — SEO meta
- `heroAnswer` — 1-line TL;DR for the page
- `zakatAssetKey` — which key on `ZakatAssets` this page maps to (`cash`, `gold`, `silver`, `stocks`, `businessInventory`, `receivables`, `rentalIncome`, `other`)
- `inputLabel` — label for the calculator input
- `inputHelp` — helper text
- `sections` — array of `{heading, paragraphs}` for the explainer
- `faq` — array of `{q, a}` Q&A pairs

- [ ] **Step 1: Create `website/data/zakat-calculator/assets.json`**

```json
{
  "hub": {
    "metaTitle": "Zakat Calculator 2026 | Good Measure Giving",
    "metaDescription": "Free zakat calculator from Good Measure Giving. Calculate zakat on cash, gold, silver, stocks, crypto, business assets, and retirement accounts with fiqh-accurate formulas.",
    "heroText": "Calculate the zakat owed on your assets. Start with the asset type most relevant to you; you can always estimate your full portfolio in one place via the home-page zakat estimator."
  },
  "assets": [
    {
      "slug": "cash-savings",
      "displayName": "Cash & Savings",
      "metaTitle": "Zakat on Cash & Savings Calculator 2026 | Good Measure Giving",
      "metaDescription": "Calculate zakat owed on cash, checking accounts, and savings. Fiqh-accurate formula with nisab threshold and 2.5% zakat rate applied.",
      "heroAnswer": "Zakat on cash is 2.5% of the total amount you have held for one lunar year, provided your total zakat-eligible wealth exceeds the nisab threshold (approximately $6,970 as of 2026).",
      "zakatAssetKey": "cash",
      "inputLabel": "Total cash + bank balances (USD)",
      "inputHelp": "Include checking, savings, money market, and physical cash. Use the balance on your zakat anniversary date.",
      "sections": [
        {
          "heading": "When is zakat owed on cash?",
          "paragraphs": [
            "Zakat is due on cash and bank balances when two conditions are met: the total exceeds nisab (approximately $6,970 in 2026, pegged to the value of 85 grams of gold), and the wealth has been held for one lunar (Hijri) year.",
            "The one-year period is personal — it starts on the date your wealth first crossed the nisab threshold, and resets each year on that anniversary. Good Measure Giving's in-app zakat planner can help track this date; it's worth recording to avoid paying zakat twice on the same year or missing a year entirely."
          ]
        },
        {
          "heading": "What counts as cash for zakat?",
          "paragraphs": [
            "Zakat-eligible cash includes physical currency, checking and savings account balances, money-market balances, and short-term deposits you can access within the lunar year. It also includes prepaid balances (gift cards, Venmo, PayPal) that represent actual spendable money.",
            "Foreign currency held for personal or business use counts at its current USD exchange rate. Cash specifically earmarked for a known near-term expense (rent due this month, a scheduled medical bill) is still zakat-eligible — the rule is based on ownership, not intent."
          ]
        },
        {
          "heading": "Liabilities — what reduces your zakat base",
          "paragraphs": [
            "Short-term debts you owe can be subtracted from your zakat-eligible cash. Credit card balances, personal loans due within the year, and unpaid bills reduce your zakatable wealth.",
            "Long-term liabilities (a mortgage with decades remaining, a student loan on an extended repayment plan) generally don't offset zakat — only the portion due within the current lunar year does. This follows the majority scholarly view; consult your own scholar if your situation is complex."
          ]
        },
        {
          "heading": "A concrete example",
          "paragraphs": [
            "Suppose you have $15,000 in checking and savings, $2,000 on a credit card, and the nisab is $6,970. Your net zakatable cash is $15,000 − $2,000 = $13,000. Since that's above nisab and you've held it for one lunar year, you owe 2.5% × $13,000 = $325 in zakat.",
            "The calculator above does this math automatically. Enter your cash balance and any short-term liabilities, and it will compute whether you're above nisab and the zakat owed."
          ]
        }
      ],
      "faq": [
        { "q": "Do I owe zakat on cash I'm saving for a house or a wedding?", "a": "Yes. Savings for future expenses are still zakat-eligible while they're in your possession. The scholarly majority view is that ownership at the time of the zakat anniversary is what matters, not your intended use." },
        { "q": "What if my cash dropped below nisab during the year but ended above it?", "a": "Zakat is calculated on the balance at the end of the lunar year. If your total is above nisab on your anniversary date, zakat is owed on that amount, even if it temporarily dipped below during the year." },
        { "q": "How precise does the nisab figure need to be?", "a": "The $6,970 figure reflects 85 grams of gold at approximately $82/g in April 2026. Gold prices fluctuate, and some scholars prefer the silver nisab (lower threshold). Consult your scholar if you're close to the line — the calculator uses the gold nisab as a conservative default." },
        { "q": "Can I pay zakat monthly instead of annually?", "a": "Yes — many people set aside zakat as a recurring monthly amount and reconcile at year-end. What matters is that the total you pay for the year reflects 2.5% of your zakat-eligible wealth on your anniversary date." },
        { "q": "What if I have emergency savings I never spend?", "a": "Long-held savings are the most clearly zakat-eligible form of wealth. The one-lunar-year holding period is the primary qualifier; an emergency fund you've had for years definitely qualifies." }
      ]
    }
  ]
}
```

- [ ] **Step 2: Verify JSON parses**

```bash
node -e "const d = JSON.parse(require('fs').readFileSync('website/data/zakat-calculator/assets.json','utf8')); console.log('assets:', d.assets.length, 'cash-savings sections:', d.assets[0].sections.length, 'faq:', d.assets[0].faq.length)"
```
Expected: `assets: 1 cash-savings sections: 4 faq: 5`

- [ ] **Step 3: Commit**

```bash
git add website/data/zakat-calculator/assets.json
git commit -m "feat(seo): seed zakat calculator data (hub + cash-savings asset)"
```

---

## Task 3: Copy calculator data to public at build time

**Files:**
- Create: `website/scripts/copyCalculator.ts`
- Modify: `website/package.json`

- [ ] **Step 1: Write the copy script**

Create `website/scripts/copyCalculator.ts`:

```typescript
/**
 * Copies zakat calculator JSON from data/zakat-calculator/ to
 * public/data/zakat-calculator/ so runtime fetch can read it.
 */
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SRC = path.join(__dirname, '../data/zakat-calculator');
const DST = path.join(__dirname, '../public/data/zakat-calculator');

if (!fs.existsSync(SRC)) {
  console.log('No zakat-calculator source directory; skipping copy.');
  process.exit(0);
}

fs.mkdirSync(DST, { recursive: true });
const files = fs.readdirSync(SRC).filter((f) => f.endsWith('.json'));
for (const f of files) {
  fs.copyFileSync(path.join(SRC, f), path.join(DST, f));
}
console.log(`Copied ${files.length} calculator files to ${path.relative(process.cwd(), DST)}`);
```

- [ ] **Step 2: Update `website/package.json`**

Find the `predev` script (added in Track 3):
```json
"predev": "tsx scripts/copyGuides.ts"
```
Change to:
```json
"predev": "tsx scripts/copyGuides.ts && tsx scripts/copyCalculator.ts"
```

Find the `prebuild` script:
```json
"prebuild": "node scripts/syncUiSignalsConfig.mjs && tsx scripts/convertData.ts && tsx scripts/copyGuides.ts"
```
Change to:
```json
"prebuild": "node scripts/syncUiSignalsConfig.mjs && tsx scripts/convertData.ts && tsx scripts/copyGuides.ts && tsx scripts/copyCalculator.ts"
```

- [ ] **Step 3: Build and verify**

`cd website && npm run build 2>&1 | tail -5`
Expected: build succeeds; the copy log line mentioning calculator files appears.

```bash
ls website/public/data/zakat-calculator/
```
Expected: `assets.json`.

- [ ] **Step 4: Commit**

```bash
git add website/scripts/copyCalculator.ts website/package.json
git commit -m "feat(seo): copy zakat-calculator data to public/data at build time"
```

`public/data/` is already gitignored — no gitignore change needed.

---

## Task 4: ZakatCalculatorAssetPage React component

**Files:**
- Create: `website/pages/ZakatCalculatorAssetPage.tsx`

Single component handling all asset types. Reads the asset entry from `assets.json` by slug. Renders input → calculator result → explainer → FAQ → related assets + related guides.

- [ ] **Step 1: Write the component**

```tsx
import React, { useEffect, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { calculateZakat, NISAB_USD } from '../src/utils/zakatCalculator';
import { isValidAssetSlug, KNOWN_ASSET_SLUGS } from '../scripts/lib/calculator-seo';
import type { ZakatAssets } from '../types';

interface AssetSection {
  heading: string;
  paragraphs: string[];
}

interface AssetFaq {
  q: string;
  a: string;
}

interface AssetEntry {
  slug: string;
  displayName: string;
  metaTitle: string;
  metaDescription: string;
  heroAnswer: string;
  zakatAssetKey: keyof ZakatAssets;
  inputLabel: string;
  inputHelp: string;
  sections: AssetSection[];
  faq: AssetFaq[];
}

interface CalculatorData {
  hub: { metaTitle: string; metaDescription: string; heroText: string };
  assets: AssetEntry[];
}

export const ZakatCalculatorAssetPage: React.FC = () => {
  const { asset: assetSlug } = useParams<{ asset: string }>();
  const { isDark } = useLandingTheme();
  const [data, setData] = useState<CalculatorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [assetAmount, setAssetAmount] = useState('');
  const [liabilities, setLiabilities] = useState('');

  useEffect(() => {
    fetch('/data/zakat-calculator/assets.json')
      .then((r) => r.json())
      .then((d: CalculatorData) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  const asset = data?.assets.find((a) => a.slug === assetSlug);

  useEffect(() => {
    if (asset) document.title = asset.metaTitle;
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [asset]);

  if (!assetSlug || !isValidAssetSlug(assetSlug)) {
    return <Navigate to="/zakat-calculator" replace />;
  }

  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={isDark ? 'text-slate-400' : 'text-slate-600'}>Loading calculator…</div>
      </div>
    );
  }

  if (!asset) {
    // Asset slug is in KNOWN_ASSET_SLUGS but data entry is missing (not yet authored).
    return (
      <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <h1 className="text-3xl font-semibold mb-4">This calculator is coming soon</h1>
          <p className="text-slate-600 dark:text-slate-400 mb-6">
            The {assetSlug.replace(/-/g, ' ')} calculator is on our roadmap. In the meantime, the cash-savings calculator covers the simplest zakat case.
          </p>
          <Link to="/zakat-calculator" className="text-emerald-600 hover:underline">← Back to all calculators</Link>
        </div>
      </div>
    );
  }

  const amountNum = parseFloat(assetAmount) || 0;
  const liabilitiesNum = parseFloat(liabilities) || 0;
  const assets: ZakatAssets = { [asset.zakatAssetKey]: amountNum };
  const estimate = calculateZakat(assets, { other: liabilitiesNum });

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <Link to="/zakat-calculator" className="hover:underline">Zakat Calculator</Link>
          <span className="mx-2">/</span>
          <span>{asset.displayName}</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-3">Zakat on {asset.displayName}</h1>
        <p className="text-lg text-slate-700 dark:text-slate-300 mb-8">{asset.heroAnswer}</p>

        <section className="mb-10 p-6 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-sm">
          <h2 className="text-xl font-semibold mb-4">Calculate</h2>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">{asset.inputLabel}</label>
            <input
              type="number"
              inputMode="decimal"
              value={assetAmount}
              onChange={(e) => setAssetAmount(e.target.value)}
              placeholder="0"
              className="w-full px-3 py-2 rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800"
            />
            <p className="text-xs text-slate-500 mt-1">{asset.inputHelp}</p>
          </div>
          <div className="mb-6">
            <label className="block text-sm font-medium mb-1">Short-term liabilities (USD, optional)</label>
            <input
              type="number"
              inputMode="decimal"
              value={liabilities}
              onChange={(e) => setLiabilities(e.target.value)}
              placeholder="0"
              className="w-full px-3 py-2 rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800"
            />
            <p className="text-xs text-slate-500 mt-1">Credit cards, personal loans, or other debts due within the lunar year.</p>
          </div>

          <div className="p-4 rounded bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Nisab threshold (2026)</div>
            <div className="text-lg font-semibold mb-3">${NISAB_USD.toLocaleString()}</div>

            <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Net zakatable wealth</div>
            <div className="text-lg font-semibold mb-3">${estimate.netZakatable.toLocaleString()}</div>

            <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Zakat owed (2.5%)</div>
            <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
              {estimate.isAboveNisab ? `$${estimate.zakatAmount.toLocaleString()}` : 'Below nisab — no zakat owed'}
            </div>
          </div>

          {estimate.isAboveNisab && estimate.zakatAmount > 0 && (
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/browse?zakat=eligible"
                className="inline-flex items-center px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700"
              >
                See zakat-eligible charities →
              </Link>
              <Link
                to="/profile"
                className="inline-flex items-center px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm font-semibold hover:border-slate-500"
              >
                Save this plan
              </Link>
            </div>
          )}
        </section>

        {asset.sections.map((section, i) => (
          <section key={i} className="mb-10">
            <h2 className="text-2xl font-semibold mb-4">{section.heading}</h2>
            {section.paragraphs.map((p, j) => (
              <p key={j} className="mb-4 leading-relaxed text-slate-700 dark:text-slate-300">{p}</p>
            ))}
          </section>
        ))}

        <section className="mb-10">
          <h2 className="text-2xl font-semibold mb-4">Frequently Asked Questions</h2>
          <dl>
            {asset.faq.map((item, i) => (
              <div key={i} className="mb-6">
                <dt className="font-semibold text-slate-900 dark:text-slate-100">{item.q}</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Other calculators</h2>
          <ul className="flex flex-wrap gap-2">
            {KNOWN_ASSET_SLUGS.filter((s) => s !== asset.slug).map((s) => (
              <li key={s}>
                <Link to={`/zakat-calculator/${s}`} className="inline-block px-3 py-1 text-sm rounded-full border border-slate-300 dark:border-slate-700 hover:border-slate-500">
                  {s.replace(/-/g, ' ')}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Build to confirm TypeScript passes**

`cd website && npm run build 2>&1 | tail -5`
Expected: success. If `ZakatAssets` type import fails, check `website/types.ts` for the exact export path; it might be at `../types` (project root) rather than `../src/types`.

- [ ] **Step 3: Commit**

```bash
git add website/pages/ZakatCalculatorAssetPage.tsx
git commit -m "feat(seo): add ZakatCalculatorAssetPage component"
```

---

## Task 5: ZakatCalculatorHubPage React component

**Files:**
- Create: `website/pages/ZakatCalculatorHubPage.tsx`

- [ ] **Step 1: Write the component**

```tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { KNOWN_ASSET_SLUGS } from '../scripts/lib/calculator-seo';

interface AssetSummary {
  slug: string;
  displayName: string;
  heroAnswer: string;
}

interface CalculatorData {
  hub: { metaTitle: string; metaDescription: string; heroText: string };
  assets: AssetSummary[];
}

const SLUG_TO_LABEL: Record<string, string> = {
  'cash-savings': 'Cash & Savings',
  'gold-silver': 'Gold & Silver',
  'stocks': 'Stocks & Investments',
  '401k-retirement': '401(k) & Retirement',
  'crypto': 'Cryptocurrency',
  'business-assets': 'Business Assets',
  'real-estate': 'Real Estate',
};

export const ZakatCalculatorHubPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const [data, setData] = useState<CalculatorData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = 'Zakat Calculator 2026 | Good Measure Giving';
    fetch('/data/zakat-calculator/assets.json')
      .then((r) => r.json())
      .then((d: CalculatorData) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));

    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const availableSlugs = new Set((data?.assets || []).map((a) => a.slug));

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <span>Zakat Calculator</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Zakat Calculator 2026</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">
          {data?.hub.heroText ?? 'Calculate the zakat owed on your assets. Start with the asset type most relevant to you.'}
        </p>

        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {KNOWN_ASSET_SLUGS.map((slug) => {
              const available = availableSlugs.has(slug);
              const label = SLUG_TO_LABEL[slug] ?? slug.replace(/-/g, ' ');
              return (
                <li key={slug}>
                  <Link
                    to={`/zakat-calculator/${slug}`}
                    className={`block p-5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors ${available ? '' : 'opacity-60'}`}
                  >
                    <div className="flex items-center justify-between">
                      <h2 className="text-xl font-semibold">Zakat on {label}</h2>
                      {!available && (
                        <span className="text-xs uppercase tracking-wide text-slate-500">Coming soon</span>
                      )}
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Build**

`cd website && npm run build 2>&1 | tail -3`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add website/pages/ZakatCalculatorHubPage.tsx
git commit -m "feat(seo): add ZakatCalculatorHubPage listing all asset calculators"
```

---

## Task 6: Wire routes in App.tsx

**Files:**
- Modify: `website/App.tsx`

- [ ] **Step 1: Add lazy imports alongside existing ones**

Near the existing lazy-loaded page imports:

```tsx
const ZakatCalculatorHubPage = lazy(() => import('./pages/ZakatCalculatorHubPage').then(m => ({ default: m.ZakatCalculatorHubPage })));
const ZakatCalculatorAssetPage = lazy(() => import('./pages/ZakatCalculatorAssetPage').then(m => ({ default: m.ZakatCalculatorAssetPage })));
```

- [ ] **Step 2: Add routes in the `<Routes>` block**

After the existing `/guides/:slug` route (added in Track 3) and before the `*` catch-all:

```tsx
            <Route path="/zakat-calculator" element={<ZakatCalculatorHubPage />} />
            <Route path="/zakat-calculator/:asset" element={<ZakatCalculatorAssetPage />} />
```

- [ ] **Step 3: Verify dev server mounts the routes**

```bash
(cd website && npm run dev -- --port 5185 > /tmp/vite-5185.log 2>&1 &)
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5185/zakat-calculator
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5185/zakat-calculator/cash-savings
pkill -f "vite.*5185"
```
Expected: both return `200`.

- [ ] **Step 4: Commit**

```bash
git add website/App.tsx
git commit -m "feat(seo): route /zakat-calculator and /zakat-calculator/:asset"
```

---

## Task 7: Prerender calculator pages with schema

**Files:**
- Modify: `website/scripts/prerender.ts`

- [ ] **Step 1: Add imports**

Alongside the existing imports:

```typescript
import { KNOWN_ASSET_SLUGS } from './lib/calculator-seo';
```

- [ ] **Step 2: Add data types for the calculator entries**

Near the existing `CauseEntry`, `GuideSummary`, etc. interface declarations, add:

```typescript
interface CalculatorAssetSection {
  heading: string;
  paragraphs: string[];
}

interface CalculatorAssetFaq {
  q: string;
  a: string;
}

interface CalculatorAsset {
  slug: string;
  displayName: string;
  metaTitle: string;
  metaDescription: string;
  heroAnswer: string;
  zakatAssetKey: string;
  inputLabel: string;
  inputHelp: string;
  sections: CalculatorAssetSection[];
  faq: CalculatorAssetFaq[];
}

interface CalculatorData {
  hub: {
    metaTitle: string;
    metaDescription: string;
    heroText: string;
  };
  assets: CalculatorAsset[];
}
```

- [ ] **Step 3: Add `buildCalculatorHubMeta` and `buildCalculatorAssetMeta` helpers**

After the existing `buildGuideMeta` function, append:

```typescript
function buildCalculatorHubMeta(data: CalculatorData): PageMeta {
  return {
    route: '/zakat-calculator',
    title: data.hub.metaTitle,
    description: truncate(data.hub.metaDescription, 160),
    canonical: `${SITE_URL}/zakat-calculator`,
    ogType: 'website',
    jsonLd: [
      {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: 'Zakat Calculator',
        url: `${SITE_URL}/zakat-calculator`,
        description: data.hub.heroText,
        mainEntity: {
          '@type': 'ItemList',
          numberOfItems: KNOWN_ASSET_SLUGS.length,
          itemListElement: KNOWN_ASSET_SLUGS.map((slug, i) => ({
            '@type': 'ListItem',
            position: i + 1,
            url: `${SITE_URL}/zakat-calculator/${slug}`,
            name: `Zakat on ${slug.replace(/-/g, ' ')}`,
          })),
        },
      },
      buildBreadcrumbSchema([
        { name: 'Home', url: `${SITE_URL}/` },
        { name: 'Zakat Calculator', url: `${SITE_URL}/zakat-calculator` },
      ]) as object,
    ],
  };
}

function buildCalculatorAssetMeta(asset: CalculatorAsset): PageMeta {
  const webApp = {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: `Zakat on ${asset.displayName} Calculator`,
    url: `${SITE_URL}/zakat-calculator/${asset.slug}`,
    description: asset.metaDescription,
    applicationCategory: 'FinanceApplication',
    operatingSystem: 'Any (web)',
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  };

  const faqPairs = asset.faq.map((item) => ({ question: item.q, answer: item.a }));
  const faqPage = buildFaqPageSchema(faqPairs);

  const breadcrumbs = buildBreadcrumbSchema([
    { name: 'Home', url: `${SITE_URL}/` },
    { name: 'Zakat Calculator', url: `${SITE_URL}/zakat-calculator` },
    { name: asset.displayName, url: `${SITE_URL}/zakat-calculator/${asset.slug}` },
  ]);

  const schemaBlocks: object[] = [webApp];
  if (faqPage) schemaBlocks.push(faqPage);
  if (breadcrumbs) schemaBlocks.push(breadcrumbs);

  return {
    route: `/zakat-calculator/${asset.slug}`,
    title: asset.metaTitle,
    description: truncate(asset.metaDescription, 160),
    canonical: `${SITE_URL}/zakat-calculator/${asset.slug}`,
    ogType: 'website',
    jsonLd: schemaBlocks,
  };
}
```

- [ ] **Step 4: Load calculator data and push metas in `prerenderPages`**

After the existing guide-loading block inside `prerenderPages`, add:

```typescript
  // Load zakat calculator data
  const CALCULATOR_PATH = path.join(__dirname, '../data/zakat-calculator/assets.json');
  let calculatorData: CalculatorData | null = null;
  if (fs.existsSync(CALCULATOR_PATH)) {
    calculatorData = JSON.parse(fs.readFileSync(CALCULATOR_PATH, 'utf-8'));
  }

  if (calculatorData) {
    metas.push(buildCalculatorHubMeta(calculatorData));
    for (const asset of calculatorData.assets) {
      metas.push(buildCalculatorAssetMeta(asset));
    }
  }
```

Update the `Prerender:` log line to include calculator counts:

```typescript
  const causeCount = causes.length > 0 ? causes.length + 1 : 0;
  const guideCount = guideSummaries.length > 0 ? guideSummaries.length + 1 : 0;
  const calculatorCount = calculatorData ? 1 + calculatorData.assets.length : 0;
  console.log(`Prerender: ${metas.length} pages (${metas.length - charities.length - prompts.length - causeCount - guideCount - calculatorCount} static + ${charities.length} charities + ${prompts.length} prompts + ${causeCount} causes + ${guideCount} guides + ${calculatorCount} calculator)`);
```

- [ ] **Step 5: Build and verify**

`cd website && npm run build 2>&1 | tail -10`
Expected: log shows `+ 2 calculator` (hub + cash-savings).

```bash
ls website/dist/zakat-calculator/
ls website/dist/zakat-calculator/cash-savings/
grep -o '"@type":"WebApplication"\|"@type":"FAQPage"\|"@type":"BreadcrumbList"' website/dist/zakat-calculator/cash-savings/index.html | sort -u
```
Expected: directories exist, index.html present, all 3 schema types detected on cash-savings.

- [ ] **Step 6: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): prerender /zakat-calculator and asset pages with schema"
```

---

## Task 8: Add calculator URLs to sitemap

**Files:**
- Modify: `website/scripts/generateSitemap.ts`

- [ ] **Step 1: Extend generator**

Near the existing path constants:

```typescript
const CALCULATOR_JSON = path.join(__dirname, '../data/zakat-calculator/assets.json');
```

Near the existing interfaces (after the `GuideSummary` interface):

```typescript
interface CalculatorAsset {
  slug: string;
}

interface CalculatorData {
  assets: CalculatorAsset[];
}
```

After the existing guide-URL block in `generateSitemap()`:

```typescript
  // Zakat calculator pages
  let calculatorAssets: CalculatorAsset[] = [];
  if (fs.existsSync(CALCULATOR_JSON)) {
    const d: CalculatorData = JSON.parse(fs.readFileSync(CALCULATOR_JSON, 'utf-8'));
    calculatorAssets = d.assets || [];
  }
  urls.push(`  <url>
    <loc>${SITE_URL}/zakat-calculator</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>`);
  for (const asset of calculatorAssets) {
    urls.push(`  <url>
    <loc>${SITE_URL}/zakat-calculator/${asset.slug}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
  }
```

Update the log line:

```typescript
  const causeCount = causes.length > 0 ? causes.length + 1 : 0;
  const guideCount = guides.length > 0 ? guides.length + 1 : 0;
  const calculatorCount = 1 + calculatorAssets.length;
  console.log(`Sitemap: ${urls.length} URLs (${staticPages.length} static + ${charities.length} charities + ${prompts.length} prompts + ${causeCount} causes + ${guideCount} guides + ${calculatorCount} calculator)`);
```

- [ ] **Step 2: Build and verify**

`cd website && npm run build 2>&1 | tail -3`

```bash
grep -c '/zakat-calculator' website/dist/sitemap.xml
```
Expected: 2 (hub + cash-savings).

- [ ] **Step 3: Commit**

```bash
git add website/scripts/generateSitemap.ts
git commit -m "feat(seo): add zakat calculator URLs to sitemap"
```

---

## Task 9: E2E coverage for calculator

**Files:**
- Modify: `website/tests/e2e/seo-schema.spec.ts`

- [ ] **Step 1: Append scenarios**

Insert before the closing `});` of the `test.describe` block:

```typescript
  test('/zakat-calculator hub has CollectionPage and BreadcrumbList schemas', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'zakat-calculator', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('CollectionPage');
    expect(types).toContain('BreadcrumbList');
  });

  test('/zakat-calculator/cash-savings has WebApplication, FAQPage, and BreadcrumbList schemas', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'zakat-calculator', 'cash-savings', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('WebApplication');
    expect(types).toContain('FAQPage');
    expect(types).toContain('BreadcrumbList');
  });

  test('sitemap includes /zakat-calculator URLs', () => {
    const xml = fs.readFileSync(path.join(DIST_DIR, 'sitemap.xml'), 'utf-8');
    expect(xml).toMatch(/\/zakat-calculator/);
  });
```

- [ ] **Step 2: Run E2E**

```bash
cd website && npm run build 2>&1 | tail -3
npx playwright test tests/e2e/seo-schema.spec.ts --project=chromium 2>&1 | tail -5
```
Expected: 17 tests pass (14 existing + 3 new).

- [ ] **Step 3: Commit**

```bash
git add website/tests/e2e/seo-schema.spec.ts
git commit -m "test(seo): extend E2E coverage to zakat calculator pages"
```

---

## Task 10: Rich Results validation (manual)

**Files:** none.

- [ ] **Step 1: Deploy to preview**

Per `website/DEPLOYMENT.md`.

- [ ] **Step 2: Validate**

Paste these URLs into https://search.google.com/test/rich-results:
- `<preview-url>/zakat-calculator` — expects CollectionPage + Breadcrumbs, 0 errors.
- `<preview-url>/zakat-calculator/cash-savings` — expects WebApplication + FAQ + Breadcrumbs, 0 errors.

- [ ] **Step 3: Test the calculator interactively**

Navigate to `<preview-url>/zakat-calculator/cash-savings` and enter $10,000 cash + $500 liabilities. Confirm the result shows approximately $237 zakat owed and "Above nisab".

- [ ] **Step 4: Resubmit sitemap in Search Console**

- [ ] **Step 5: No commit — validation only**

---

## Acceptance criteria

When every task is checked off:

1. `website/scripts/lib/calculator-seo.ts` exports `KNOWN_ASSET_SLUGS` (7 items), `AssetSlug` type, `isValidAssetSlug`. Unit tests passing.
2. `website/data/zakat-calculator/assets.json` contains the hub metadata + `cash-savings` asset with 4-section explainer and 5 FAQ.
3. Routes `/zakat-calculator` and `/zakat-calculator/:asset` serve the two React pages.
4. Build generates `website/dist/zakat-calculator/index.html` + `website/dist/zakat-calculator/cash-savings/index.html` with correct schema.
5. Sitemap includes both URLs.
6. E2E spec passes 17 scenarios.
7. Rich Results Test validates 0 errors; calculator produces correct math.

## Adding the remaining 6 assets (follow-up work)

Each asset is a 1-file commit: add an entry to the `assets` array in `website/data/zakat-calculator/assets.json`. No code changes needed. The hub page auto-detects availability; the asset page renders from the JSON. Missing assets on the hub show as "Coming soon" until authored.

Rough priority order by search volume + unique fiqh content:
1. gold-silver (high volume, Ramadan peaks)
2. stocks
3. 401k-retirement
4. crypto
5. business-assets
6. real-estate

## Out of scope

- Daily metal-price refresh pipeline for the gold-silver calculator (ship when gold-silver asset ships; requires a pipeline job and cache at `public/data/metal-prices.json`).
- Replacing the in-app `ZakatEstimator` modal — these public pages complement the modal; both share `calculateZakat()` already.
- HowTo schema (mentioned in the spec) — skip for now; it's an optional enhancement with modest SEO lift and more maintenance cost than it's worth at launch.
- Authenticated "save this plan" handling — the CTA points to `/profile` which handles auth; no new work needed here.

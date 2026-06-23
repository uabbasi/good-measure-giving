# Gold & Silver Zakat Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an SSR'd reference chart on `/zakat-calculator/gold-silver/` mapping common gold and silver weights → live market value → zakat due (2.5%), to win the search query "gold zakat chart".

**Architecture:** A pure module (`zakatChart.ts`) holds the weight tables and row math. The existing `nisabPrice.ts` gold-fetch machinery is extended with a parallel silver live-fetch hook (`useSilverPricePerGram`). A presentational `ZakatMetalChart` component renders one metal's table. `ZakatCalculatorAssetPage` renders two tables (gold + silver) only for the `gold-silver` asset, right after the Calculate box. Both price hooks return a fallback constant on the server, so the chart SSRs with sane numbers at build time and live-updates on the client.

**Tech Stack:** TypeScript 5.8, React 19, Vite 6, Vitest, react-dom/server (SSR/prerender), Tailwind.

## Global Constraints

- **Commit on branch `seo-gold-silver-zakat-chart` only. Do NOT push.**
- Full test suite must stay green at 269+ passing (`npm test`).
- `npm run build` must succeed and the built `dist/zakat-calculator/gold-silver/index.html` must contain the chart heading + a nisab row (SSR proof).
- Gold nisab = **85g**, silver nisab = **595g**, zakat rate = **2.5%** (verified against fiqh: 595g is the lower, cautious-toward-the-poor contemporary figure and matches the page's existing prose; note ~612g tradition in a one-liner).
- `GRAMS_PER_TROY_OUNCE = 31.1034768` (already defined in `nisabPrice.ts`).
- Silver live API: `https://api.gold-api.com/price/XAG` (mirrors the gold `XAU` call).
- Silver plausibility bounds: `0.3`–`5.0` USD/g.
- Surgical changes only — gold-silver asset scoped; do not alter other assets or the unpushed motif work.
- All paths below are relative to `website/`.

---

### Task 1: Pure chart module (`zakatChart.ts`)

**Files:**
- Create: `src/utils/zakatChart.ts`
- Test: `src/utils/zakatChart.test.ts`

**Interfaces:**
- Consumes: `ZAKAT_RATE` from `src/utils/zakatCalculator.ts` (value `0.025`).
- Produces:
  - `interface MetalWeight { label: string; grams: number; isNisab?: boolean }`
  - `interface ChartRow { label: string; grams: number; value: number; zakat: number; isNisab: boolean }`
  - `const GOLD_WEIGHTS: MetalWeight[]`, `const SILVER_WEIGHTS: MetalWeight[]`
  - `function buildChartRows(pricePerGram: number, weights: MetalWeight[]): ChartRow[]`

- [ ] **Step 1: Write the failing test**

```ts
// src/utils/zakatChart.test.ts
import { describe, it, expect } from 'vitest';
import { buildChartRows, GOLD_WEIGHTS, SILVER_WEIGHTS } from './zakatChart';

describe('buildChartRows', () => {
  it('computes value = grams × pricePerGram and zakat = value × 2.5%', () => {
    const rows = buildChartRows(100, [{ label: '10 g', grams: 10 }]);
    expect(rows).toHaveLength(1);
    expect(rows[0].value).toBeCloseTo(1000, 6);
    expect(rows[0].zakat).toBeCloseTo(25, 6);
    expect(rows[0].isNisab).toBe(false);
  });

  it('passes through the isNisab flag', () => {
    const rows = buildChartRows(100, [{ label: '85 g (nisab)', grams: 85, isNisab: true }]);
    expect(rows[0].isNisab).toBe(true);
  });

  it('scales linearly with price', () => {
    const low = buildChartRows(50, GOLD_WEIGHTS);
    const high = buildChartRows(100, GOLD_WEIGHTS);
    expect(high[0].value).toBeCloseTo(low[0].value * 2, 6);
    expect(high[0].zakat).toBeCloseTo(low[0].zakat * 2, 6);
  });
});

describe('weight tables', () => {
  it('gold table marks exactly the 85g row as nisab', () => {
    const nisabRows = GOLD_WEIGHTS.filter((w) => w.isNisab);
    expect(nisabRows).toHaveLength(1);
    expect(nisabRows[0].grams).toBe(85);
  });

  it('silver table marks exactly the 595g row as nisab', () => {
    const nisabRows = SILVER_WEIGHTS.filter((w) => w.isNisab);
    expect(nisabRows).toHaveLength(1);
    expect(nisabRows[0].grams).toBe(595);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/utils/zakatChart.test.ts`
Expected: FAIL — cannot find module `./zakatChart`.

- [ ] **Step 3: Write minimal implementation**

```ts
// src/utils/zakatChart.ts
/**
 * Pure helpers for the gold & silver zakat reference chart.
 *
 * Maps common metal weights to current market value and zakat due (2.5%).
 * No I/O, no React — fully unit-testable. Live prices are injected by the
 * caller (see nisabPrice.ts hooks); this module only does the arithmetic.
 */
import { ZAKAT_RATE } from './zakatCalculator';

export interface MetalWeight {
  label: string;
  grams: number;
  isNisab?: boolean;
}

export interface ChartRow {
  label: string;
  grams: number;
  value: number;
  zakat: number;
  isNisab: boolean;
}

const TROY_OUNCE_GRAMS = 31.1034768;

// Gold nisab = 85g. 1 tola is a culturally familiar South-Asian unit (11.66g).
export const GOLD_WEIGHTS: MetalWeight[] = [
  { label: '1 tola (11.66 g)', grams: 11.66 },
  { label: '10 g', grams: 10 },
  { label: '1 oz', grams: TROY_OUNCE_GRAMS },
  { label: '50 g', grams: 50 },
  { label: '85 g (nisab)', grams: 85, isNisab: true },
  { label: '100 g', grams: 100 },
];

// Silver nisab = 595g (some scholars cite ~612g).
export const SILVER_WEIGHTS: MetalWeight[] = [
  { label: '1 oz', grams: TROY_OUNCE_GRAMS },
  { label: '100 g', grams: 100 },
  { label: '250 g', grams: 250 },
  { label: '500 g', grams: 500 },
  { label: '595 g (nisab)', grams: 595, isNisab: true },
  { label: '1 kg', grams: 1000 },
];

export function buildChartRows(pricePerGram: number, weights: MetalWeight[]): ChartRow[] {
  return weights.map((w) => {
    const value = w.grams * pricePerGram;
    return {
      label: w.label,
      grams: w.grams,
      value,
      zakat: value * ZAKAT_RATE,
      isNisab: w.isNisab ?? false,
    };
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/utils/zakatChart.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/utils/zakatChart.ts src/utils/zakatChart.test.ts
git commit -m "feat(zakat-chart): pure weight→value→zakat row builder"
```

---

### Task 2: Silver fallback constant + live-price hook (`nisabPrice.ts`)

**Files:**
- Modify: `src/utils/zakatCalculator.ts` (add `SILVER_USD_PER_GRAM` next to `NISAB_USD`)
- Modify: `src/utils/nisabPrice.ts` (generalize cache helpers; add silver fns + hook)
- Test: `src/utils/nisabPrice.test.ts` (extend)

**Interfaces:**
- Consumes: `SILVER_USD_PER_GRAM` from `src/utils/zakatCalculator.ts`; existing `GRAMS_PER_TROY_OUNCE` constant in `nisabPrice.ts`.
- Produces:
  - `function computeSilverPricePerGramFromOunce(pricePerOunce: number): number`
  - `function isPlausibleSilverPrice(pricePerGram: number): boolean`
  - `function useSilverPricePerGram(): number`

- [ ] **Step 1: Write the failing test (extend existing file)**

Append to `src/utils/nisabPrice.test.ts`:

```ts
import {
  computeSilverPricePerGramFromOunce,
  isPlausibleSilverPrice,
} from './nisabPrice';

describe('computeSilverPricePerGramFromOunce', () => {
  it('converts a per-troy-ounce price to per-gram', () => {
    // $31.10/oz silver → $1.00/g (31.10/31.1034768 ≈ 1.0)
    expect(computeSilverPricePerGramFromOunce(31.1034768)).toBeCloseTo(1.0, 4);
  });

  it('scales linearly with price', () => {
    const low = computeSilverPricePerGramFromOunce(30);
    const high = computeSilverPricePerGramFromOunce(60);
    expect(high).toBeCloseTo(low * 2, 6);
  });
});

describe('isPlausibleSilverPrice', () => {
  it('accepts values in the $0.3-$5.0/g sanity range', () => {
    expect(isPlausibleSilverPrice(0.9)).toBe(true);
    expect(isPlausibleSilverPrice(1.7)).toBe(true);
    expect(isPlausibleSilverPrice(3.0)).toBe(true);
  });

  it('rejects implausibly low or high values', () => {
    expect(isPlausibleSilverPrice(0.05)).toBe(false);
    expect(isPlausibleSilverPrice(50)).toBe(false);
    expect(isPlausibleSilverPrice(0)).toBe(false);
  });

  it('rejects non-finite values', () => {
    expect(isPlausibleSilverPrice(NaN)).toBe(false);
    expect(isPlausibleSilverPrice(Infinity)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/utils/nisabPrice.test.ts`
Expected: FAIL — `computeSilverPricePerGramFromOunce` / `isPlausibleSilverPrice` not exported.

- [ ] **Step 3a: Add the fallback constant**

In `src/utils/zakatCalculator.ts`, immediately after the `NISAB_USD` declaration (line ~15), add:

```ts
/**
 * Fallback silver price in USD per gram — consistent with the NISAB_USD epoch
 * (gold ~$4,790/oz; at a ~90:1 gold:silver ratio, silver ≈ $1.70/g).
 *
 * Used as the last-resort fallback and the server-render value for the
 * gold & silver zakat chart, which refreshes live via useSilverPricePerGram()
 * from gold-api.com (XAG). When updating: bump to current silver spot per gram.
 */
export const SILVER_USD_PER_GRAM = 1.7;
```

- [ ] **Step 3b: Generalize the cache helpers and add silver machinery**

In `src/utils/nisabPrice.ts`:

(i) Update the import line to also pull in the silver constant:

```ts
import { NISAB_USD, SILVER_USD_PER_GRAM } from './zakatCalculator';
```

(ii) Add silver constants next to the existing nisab cache constants (after line ~22):

```ts
const SILVER_CACHE_KEY = 'gmg_silver_per_gram_v1';
// Sanity bounds — silver has run ≈ $0.8-1.1/g lately; bound generously.
const MIN_PLAUSIBLE_SILVER = 0.3;
const MAX_PLAUSIBLE_SILVER = 5.0;
```

(iii) Generalize `readCache`/`writeCache` to take a key argument (rename the
`CachedNisab` interface to `CachedValue`). Replace the existing
interface + `readCache` + `writeCache` definitions with:

```ts
interface CachedValue {
  value: number;
  fetchedAt: number;
}

function readCache(key: string): CachedValue | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedValue;
    if (typeof parsed.value !== 'number' || typeof parsed.fetchedAt !== 'number') return null;
    if (Date.now() - parsed.fetchedAt > CACHE_TTL_MS) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeCache(key: string, value: number): void {
  if (typeof window === 'undefined') return;
  try {
    const payload: CachedValue = { value, fetchedAt: Date.now() };
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // localStorage full or blocked — fail silently
  }
}
```

(iv) Update the two existing gold call sites in `useNisab` to pass `CACHE_KEY`:

- `const cached = readCache();` → `const cached = readCache(CACHE_KEY);` (both occurrences, lines ~82 and ~87)
- `writeCache(live);` → `writeCache(CACHE_KEY, live);` (line ~93)

(v) Append the silver functions and hook at the end of the file:

```ts
export function isPlausibleSilverPrice(pricePerGram: number): boolean {
  return (
    Number.isFinite(pricePerGram) &&
    pricePerGram >= MIN_PLAUSIBLE_SILVER &&
    pricePerGram <= MAX_PLAUSIBLE_SILVER
  );
}

export function computeSilverPricePerGramFromOunce(pricePerOunce: number): number {
  return pricePerOunce / GRAMS_PER_TROY_OUNCE;
}

async function fetchLiveSilverPerGram(): Promise<number | null> {
  try {
    const res = await fetch('https://api.gold-api.com/price/XAG');
    if (!res.ok) return null;
    const data = (await res.json()) as { price?: number };
    if (typeof data.price !== 'number') return null;
    const perGram = computeSilverPricePerGramFromOunce(data.price);
    return isPlausibleSilverPrice(perGram) ? perGram : null;
  } catch {
    return null;
  }
}

/**
 * React hook returning the current silver price in USD per gram.
 * Mirrors useNisab(): returns the fallback immediately (and on the server),
 * then updates to the live value once the API resolves (if plausible).
 */
export function useSilverPricePerGram(): number {
  const [price, setPrice] = useState<number>(() => {
    const cached = readCache(SILVER_CACHE_KEY);
    return cached?.value ?? SILVER_USD_PER_GRAM;
  });

  useEffect(() => {
    const cached = readCache(SILVER_CACHE_KEY);
    if (cached) return; // fresh cache — skip fetch

    let cancelled = false;
    fetchLiveSilverPerGram().then((live) => {
      if (cancelled || live == null) return;
      writeCache(SILVER_CACHE_KEY, live);
      setPrice(live);
    });
    return () => { cancelled = true; };
  }, []);

  return price;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/utils/nisabPrice.test.ts`
Expected: PASS (existing gold tests + 6 new silver tests).

- [ ] **Step 5: Commit**

```bash
git add src/utils/zakatCalculator.ts src/utils/nisabPrice.ts src/utils/nisabPrice.test.ts
git commit -m "feat(zakat-chart): live silver price hook + SILVER_USD_PER_GRAM fallback"
```

---

### Task 3: Presentational chart component (`ZakatMetalChart.tsx`)

**Files:**
- Create: `src/components/calculator/ZakatMetalChart.tsx`
- Test: `src/components/calculator/ZakatMetalChart.test.tsx`

**Interfaces:**
- Consumes: `ChartRow` type and `buildChartRows`, `GOLD_WEIGHTS` from `../../utils/zakatChart`.
- Produces: `const ZakatMetalChart: React.FC<{ title: string; rows: ChartRow[]; nisabNote?: string }>`

- [ ] **Step 1: Write the failing test (SSR string, node env — mirrors ClientOnly.test.tsx)**

```tsx
// src/components/calculator/ZakatMetalChart.test.tsx
// @vitest-environment node
import { renderToStaticMarkup } from 'react-dom/server';
import { test, expect } from 'vitest';
import { ZakatMetalChart } from './ZakatMetalChart';
import { buildChartRows, GOLD_WEIGHTS } from '../../utils/zakatChart';

test('renders the title, a highlighted nisab row, and formatted values', () => {
  const html = renderToStaticMarkup(
    <ZakatMetalChart title="Gold" rows={buildChartRows(150, GOLD_WEIGHTS)} nisabNote="85g of gold is the nisab threshold." />,
  );
  // title
  expect(html).toContain('Gold');
  // nisab row present and visually highlighted
  expect(html).toContain('85 g (nisab)');
  expect(html).toContain('emerald');
  // value column: 100 g × $150 = $15,000
  expect(html).toContain('$15,000');
  // zakat column (2.5% of $15,000 = $375.00)
  expect(html).toContain('$375.00');
  // note rendered
  expect(html).toContain('nisab threshold');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/calculator/ZakatMetalChart.test.tsx`
Expected: FAIL — cannot find module `./ZakatMetalChart`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// src/components/calculator/ZakatMetalChart.tsx
import React from 'react';
import type { ChartRow } from '../../utils/zakatChart';

const fmt = (n: number, decimals = 0): string =>
  n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

interface ZakatMetalChartProps {
  title: string;
  rows: ChartRow[];
  nisabNote?: string;
}

export const ZakatMetalChart: React.FC<ZakatMetalChartProps> = ({ title, rows, nisabNote }) => (
  <div className="mb-8">
    <h3 className="text-lg font-semibold mb-3">{title}</h3>
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="text-left border-b border-slate-300 dark:border-slate-700">
          <th scope="col" className="py-2 pr-4 font-medium">Weight</th>
          <th scope="col" className="py-2 pr-4 font-medium text-right">Market value</th>
          <th scope="col" className="py-2 font-medium text-right">Zakat due (2.5%)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.label}
            className={`border-b border-slate-100 dark:border-slate-800 ${
              row.isNisab ? 'bg-emerald-50 dark:bg-emerald-900/20 font-semibold' : ''
            }`}
          >
            <td className="py-2 pr-4">{row.label}</td>
            <td className="py-2 pr-4 text-right">${fmt(row.value)}</td>
            <td className="py-2 text-right">${fmt(row.zakat, 2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
    {nisabNote && <p className="mt-2 text-xs text-slate-500">{nisabNote}</p>}
  </div>
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/calculator/ZakatMetalChart.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/components/calculator/ZakatMetalChart.tsx src/components/calculator/ZakatMetalChart.test.tsx
git commit -m "feat(zakat-chart): presentational ZakatMetalChart table component"
```

---

### Task 4: Wire chart into the page + metaTitle tweak

**Files:**
- Modify: `pages/ZakatCalculatorAssetPage.tsx`
- Modify: `data/zakat-calculator/assets.json` (gold-silver `metaTitle`)
- Test: `src/components/calculator/ZakatMetalChart.test.tsx` already covers the table; the SSR proof is the build grep in Task 5. No new unit test — page wiring is verified by the build + dist grep, which is the meaningful integration assertion here.

**Interfaces:**
- Consumes: `useSilverPricePerGram` from `../src/utils/nisabPrice`; `buildChartRows`, `GOLD_WEIGHTS`, `SILVER_WEIGHTS` from `../src/utils/zakatChart`; `ZakatMetalChart` from `../src/components/calculator/ZakatMetalChart`.

- [ ] **Step 1: Update the gold-silver metaTitle**

In `data/zakat-calculator/assets.json`, change the `gold-silver` asset's `metaTitle` (currently `"Zakat on Gold & Silver Calculator 2026 | Good Measure Giving"`) to:

```json
      "metaTitle": "Zakat on Gold & Silver: Calculator & Chart (2026) | Good Measure Giving",
```

- [ ] **Step 2: Add imports to the page**

In `pages/ZakatCalculatorAssetPage.tsx`, update the existing import of `useNisab` and add two new import lines:

```tsx
import { useNisab, useSilverPricePerGram } from '../src/utils/nisabPrice';
import { buildChartRows, GOLD_WEIGHTS, SILVER_WEIGHTS } from '../src/utils/zakatChart';
import { ZakatMetalChart } from '../src/components/calculator/ZakatMetalChart';
```

- [ ] **Step 3: Call the silver hook at the top of the component**

Immediately after `const nisab = useNisab();` (line ~16), add:

```tsx
  const silverPerGram = useSilverPricePerGram();
```

(Both hooks are called before the early returns, satisfying the Rules of Hooks.)

- [ ] **Step 4: Render the chart section (gold-silver only), right after the Calculate `</section>`**

Insert this block immediately after the closing `</section>` of the Calculate box (the section ending at line ~128) and before the `{asset.sections.map(...)}` block:

```tsx
        {asset.slug === 'gold-silver' && (
          <section className="mb-10" aria-labelledby="gold-silver-chart-heading">
            <h2 id="gold-silver-chart-heading" className="text-2xl font-semibold mb-4">
              Gold &amp; Silver Zakat Chart (2026)
            </h2>
            <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Prices update live based on current spot; refresh for the latest.
            </p>
            <ZakatMetalChart
              title="Gold"
              rows={buildChartRows(nisab / 85, GOLD_WEIGHTS)}
              nisabNote="85 g of gold is the nisab threshold for gold."
            />
            <ZakatMetalChart
              title="Silver"
              rows={buildChartRows(silverPerGram, SILVER_WEIGHTS)}
              nisabNote="595 g of silver is the nisab threshold (some scholars cite ~612 g)."
            />
            <p className="mt-2 text-xs text-slate-500">
              Jewelry worn for personal use may be exempt under the majority Maliki, Shafi'i, and Hanbali view;
              the Hanafi school holds all gold and silver zakatable. Follow the ruling of the school you adhere to.
            </p>
          </section>
        )}
```

- [ ] **Step 5: Typecheck + run the focused tests**

Run: `npx tsc --noEmit && npx vitest run src/utils/zakatChart.test.ts src/utils/nisabPrice.test.ts src/components/calculator/ZakatMetalChart.test.tsx`
Expected: no type errors; all listed tests PASS.

- [ ] **Step 6: Commit**

```bash
git add pages/ZakatCalculatorAssetPage.tsx data/zakat-calculator/assets.json
git commit -m "feat(zakat-chart): render gold+silver chart on gold-silver page; title includes Chart"
```

---

### Task 5: Full verification (suite + build + SSR proof)

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `npm test -- run`
Expected: all tests PASS; total count ≥ 269 (275 after the new tests: +5 chart, +6 silver, +1 component).

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 3: Prove the chart SSRs into the built HTML**

Run:
```bash
grep -c "Gold &amp; Silver Zakat Chart (2026)" dist/zakat-calculator/gold-silver/index.html
grep -o "85 g (nisab)" dist/zakat-calculator/gold-silver/index.html | head -1
grep -o "595 g (nisab)" dist/zakat-calculator/gold-silver/index.html | head -1
grep -o "Zakat on Gold &amp; Silver: Calculator &amp; Chart (2026)" dist/zakat-calculator/gold-silver/index.html | head -1
```
Expected: heading count ≥ 1; both nisab row labels present; the updated `<title>` present. (Note: entities may render as `&amp;` — match accordingly; if a grep misses, inspect the file to confirm the literal encoding before concluding failure.)

- [ ] **Step 4: Confirm other asset pages did NOT get the chart (scoping check)**

Run:
```bash
grep -c "Gold &amp; Silver Zakat Chart" dist/zakat-calculator/cash-savings/index.html
```
Expected: `0` (chart is scoped to the gold-silver asset only).

- [ ] **Step 5: Final report**

Summarize: files changed, `npm test` count, build result, and the dist grep output proving SSR. Leave all work committed on `seo-gold-silver-zakat-chart`, unpushed.

---

## Self-Review

**Spec coverage:**
- Pricing/data flow (gold via `useNisab()/85`, new silver `useSilverPricePerGram` via XAG, 6h cache, fallback, plausibility, SSR fallbacks) → Tasks 2 + 4. ✓
- Units (`zakatChart.ts` pure builder + weight tables) → Task 1. ✓
- `nisabPrice.ts` extensions (`useSilverPricePerGram`, `computeSilverPricePerGramFromOunce`, `isPlausibleSilverPrice`) → Task 2. ✓
- `SILVER_USD_PER_GRAM` fallback constant next to `NISAB_USD` → Task 2. ✓
- `ZakatMetalChart` presentational component, nisab row highlighted, currency formatting, reused for both metals → Task 3 + 4. ✓
- Page edit scoped to `gold-silver`, H2 after Calculate box → Task 4. ✓
- Fiqh: 85g/595g/2.5%, jewelry caveat, 595-vs-612 note → Task 1 labels + Task 4 caveat. ✓
- "Prices update live…refresh" note → Task 4. ✓
- SSR test/proof + 269 green → Tasks 3 (component SSR string test) + 5 (build grep). ✓
- metaTitle includes "Chart", traced through `useCalculatorData` → `assets.json` data source → Task 4 Step 1. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code. ✓

**Type consistency:** `MetalWeight`/`ChartRow`/`buildChartRows`/`GOLD_WEIGHTS`/`SILVER_WEIGHTS` defined in Task 1 and consumed verbatim in Tasks 3–4. `useSilverPricePerGram`/`computeSilverPricePerGramFromOunce`/`isPlausibleSilverPrice`/`SILVER_USD_PER_GRAM` defined in Task 2 and consumed verbatim in Task 4. `ZakatMetalChart` prop shape `{ title, rows, nisabNote? }` consistent across Tasks 3–4. ✓

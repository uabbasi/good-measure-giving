# SEO Track 1: Charity Page Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 115 charity pages rank for their highest-intent branded queries ("is [charity] zakat eligible", "[charity] review") by rewriting title/meta, injecting FAQPage + BreadcrumbList JSON-LD per charity, adding a "Similar charities" block for internal linking, and marking user-state pages `noindex`.

**Architecture:** All build-time SEO work lives in `website/scripts/prerender.ts` and reuses the schema builders shipped in Track 0 (`website/scripts/lib/schema.ts`). Zakat-eligibility classification from `wallet_tag` and `zakat_classification` fields drives a conditional title template. FAQPage Q&A are templated from existing data — no new pipeline work. "Similar charities" is a new React component rendered inside the existing baseline view of `CharityDetailsPage.tsx`; Google's JS rendering picks it up. `noindex` meta tag injection is build-time for the three pages crawlers should skip.

**Tech Stack:** TypeScript 5.8, Vitest 4, React 19, existing prerender pipeline.

**Spec reference:** `docs/superpowers/specs/2026-04-19-seo-strategy-design.md` — Track 1 section.

---

## File Structure

**New files:**
- `website/scripts/lib/charity-seo.ts` — pure helpers: title template, description template, FAQPage Q&A builder, Similar charities selector. Pure functions, unit-tested.
- `website/scripts/lib/charity-seo.test.ts` — Vitest unit tests.
- `website/src/components/SimilarCharities.tsx` — React component rendering 3–5 charity links. Reuses existing charity card styling where possible.

**Modified files:**
- `website/scripts/prerender.ts` — `buildCharityMeta` rewrites title/meta/JSON-LD using the new helpers; `buildStaticMeta` adds `noindex` metadata to `/profile`, `/compare`, `/bookmarks`; `injectMeta` learns to emit `<meta name="robots" content="noindex">` when flagged.
- `website/pages/CharityDetailsPage.tsx` — renders `<SimilarCharities />` inside the baseline content tree (NOT auth-gated).
- `website/tests/e2e/seo-schema.spec.ts` — extends the existing spec with 3 new scenarios: charity FAQPage, charity BreadcrumbList, `/profile` noindex.

**No data pipeline changes.** `wallet_tag`, `zakat_classification`, `amal_score`, `mission`, `category`, `location` are all already present on charity data.

---

## Task 1: Add zakat-status helper in charity-seo lib

**Files:**
- Create: `website/scripts/lib/charity-seo.ts`
- Create: `website/scripts/lib/charity-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Write to `website/scripts/lib/charity-seo.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { classifyZakatStatus } from './charity-seo';

describe('classifyZakatStatus', () => {
  it('returns ZAKAT_ELIGIBLE for any wallet_tag containing ZAKAT-ELIGIBLE', () => {
    expect(classifyZakatStatus({ walletTag: 'ZAKAT-ELIGIBLE', zakatClassification: null }))
      .toBe('ZAKAT_ELIGIBLE');
    expect(classifyZakatStatus({ walletTag: 'WIDELY-ZAKAT-ELIGIBLE', zakatClassification: null }))
      .toBe('ZAKAT_ELIGIBLE');
    expect(classifyZakatStatus({ walletTag: 'NARROWLY-ZAKAT-ELIGIBLE', zakatClassification: null }))
      .toBe('ZAKAT_ELIGIBLE');
  });

  it('returns SADAQAH_ONLY when wallet_tag is SADAQAH-ELIGIBLE', () => {
    expect(classifyZakatStatus({ walletTag: 'SADAQAH-ELIGIBLE', zakatClassification: 'sadaqah_only' }))
      .toBe('SADAQAH_ONLY');
  });

  it('returns UNCLEAR when classification is unclear or data is missing', () => {
    expect(classifyZakatStatus({ walletTag: null, zakatClassification: 'unclear' }))
      .toBe('UNCLEAR');
    expect(classifyZakatStatus({ walletTag: null, zakatClassification: null }))
      .toBe('UNCLEAR');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

From `website/`:
`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: FAIL — `Failed to resolve import './charity-seo'`.

- [ ] **Step 3: Write minimal implementation**

Write to `website/scripts/lib/charity-seo.ts`:

```typescript
/**
 * SEO helpers for charity detail pages.
 * Title/meta/FAQ templates driven by charity data fields.
 * Pure functions only — no I/O, no mutation.
 */

export type ZakatStatus = 'ZAKAT_ELIGIBLE' | 'SADAQAH_ONLY' | 'UNCLEAR' | 'NEW_ORG';

export interface ZakatStatusInput {
  walletTag: string | null;
  zakatClassification: string | null;
}

export function classifyZakatStatus(input: ZakatStatusInput): ZakatStatus {
  const tag = (input.walletTag ?? '').toUpperCase();
  if (tag.includes('ZAKAT-ELIGIBLE')) return 'ZAKAT_ELIGIBLE';
  if (tag === 'SADAQAH-ELIGIBLE') return 'SADAQAH_ONLY';
  return 'UNCLEAR';
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: PASS — all 3 test cases green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/charity-seo.ts website/scripts/lib/charity-seo.test.ts
git commit -m "feat(seo): add classifyZakatStatus helper"
```

---

## Task 2: Add charity title template

**Files:**
- Modify: `website/scripts/lib/charity-seo.ts`
- Modify: `website/scripts/lib/charity-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `website/scripts/lib/charity-seo.test.ts`:

```typescript
import { buildCharityTitle } from './charity-seo';

describe('buildCharityTitle', () => {
  it('uses zakat-eligibility framing when ZAKAT_ELIGIBLE', () => {
    expect(buildCharityTitle({
      name: 'Islamic Relief',
      score: 78,
      zakatStatus: 'ZAKAT_ELIGIBLE',
    })).toBe('Is Islamic Relief Zakat Eligible? 78/100 Rating & Review | GMG');
  });

  it('uses review framing with zakat status suffix when SADAQAH_ONLY', () => {
    expect(buildCharityTitle({
      name: 'Doctors Without Borders',
      score: 72,
      zakatStatus: 'SADAQAH_ONLY',
    })).toBe('Doctors Without Borders Review: 72/100 Rating & Zakat Status | GMG');
  });

  it('uses review framing when UNCLEAR', () => {
    expect(buildCharityTitle({
      name: 'ICNA Relief',
      score: 74,
      zakatStatus: 'UNCLEAR',
    })).toBe('ICNA Relief Review: 74/100 Rating & Zakat Status | GMG');
  });

  it('uses early-stage framing when NEW_ORG regardless of score', () => {
    expect(buildCharityTitle({
      name: 'Example New Org',
      score: null,
      zakatStatus: 'NEW_ORG',
    })).toBe('Example New Org Review: Early-Stage Muslim Charity | GMG');
  });

  it('falls back to Evaluated when score is null on a rated status', () => {
    expect(buildCharityTitle({
      name: 'Unknown Charity',
      score: null,
      zakatStatus: 'UNCLEAR',
    })).toBe('Unknown Charity Review: Evaluated | GMG');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: FAIL — `buildCharityTitle` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `website/scripts/lib/charity-seo.ts`:

```typescript
export interface CharityTitleInput {
  name: string;
  score: number | null;
  zakatStatus: ZakatStatus;
}

export function buildCharityTitle(input: CharityTitleInput): string {
  if (input.zakatStatus === 'NEW_ORG') {
    return `${input.name} Review: Early-Stage Muslim Charity | GMG`;
  }
  const scorePart = input.score != null ? `${input.score}/100 Rating` : 'Evaluated';
  if (input.zakatStatus === 'ZAKAT_ELIGIBLE' && input.score != null) {
    return `Is ${input.name} Zakat Eligible? ${input.score}/100 Rating & Review | GMG`;
  }
  if (input.score != null) {
    return `${input.name} Review: ${scorePart} & Zakat Status | GMG`;
  }
  return `${input.name} Review: ${scorePart} | GMG`;
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: PASS — 8 tests green (3 classify + 5 title).

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/charity-seo.ts website/scripts/lib/charity-seo.test.ts
git commit -m "feat(seo): add charity title template builder"
```

---

## Task 3: Add charity meta description template

**Files:**
- Modify: `website/scripts/lib/charity-seo.ts`
- Modify: `website/scripts/lib/charity-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `website/scripts/lib/charity-seo.test.ts`:

```typescript
import { buildCharityDescription } from './charity-seo';

describe('buildCharityDescription', () => {
  it('leads with zakat-eligibility sentence for ZAKAT_ELIGIBLE', () => {
    const desc = buildCharityDescription({
      name: 'Islamic Relief',
      score: 78,
      zakatStatus: 'ZAKAT_ELIGIBLE',
      missionFragment: 'Global humanitarian aid organization.',
    });
    expect(desc).toContain('Zakat Eligible');
    expect(desc).toContain('78/100');
    expect(desc).toContain('Global humanitarian');
    expect(desc.length).toBeLessThanOrEqual(160);
  });

  it('leads with sadaqah-only sentence for SADAQAH_ONLY', () => {
    const desc = buildCharityDescription({
      name: 'Doctors Without Borders',
      score: 72,
      zakatStatus: 'SADAQAH_ONLY',
      missionFragment: 'Medical humanitarian organization.',
    });
    expect(desc).toContain('sadaqah');
    expect(desc.length).toBeLessThanOrEqual(160);
  });

  it('truncates long mission fragments at 160 chars with ellipsis', () => {
    const longMission = 'X'.repeat(400);
    const desc = buildCharityDescription({
      name: 'Test',
      score: 50,
      zakatStatus: 'UNCLEAR',
      missionFragment: longMission,
    });
    expect(desc.length).toBeLessThanOrEqual(160);
    expect(desc.endsWith('\u2026')).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: FAIL — `buildCharityDescription` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `website/scripts/lib/charity-seo.ts`:

```typescript
export interface CharityDescriptionInput {
  name: string;
  score: number | null;
  zakatStatus: ZakatStatus;
  missionFragment: string;
}

function truncate(text: string, max: number): string {
  return text.length <= max ? text : text.slice(0, max - 1) + '\u2026';
}

export function buildCharityDescription(input: CharityDescriptionInput): string {
  let lead: string;
  switch (input.zakatStatus) {
    case 'ZAKAT_ELIGIBLE':
      lead = `${input.name} is classified as Zakat Eligible by Good Measure Giving.`;
      break;
    case 'SADAQAH_ONLY':
      lead = `${input.name} is sadaqah-eligible but not zakat-eligible per Good Measure Giving.`;
      break;
    case 'NEW_ORG':
      lead = `${input.name} is an early-stage Muslim charity, too new to rate numerically.`;
      break;
    default:
      lead = `${input.name} evaluated by Good Measure Giving.`;
  }
  const scorePart = input.score != null ? ` Rated ${input.score}/100 on impact and transparency.` : '';
  const raw = `${lead}${scorePart} ${input.missionFragment}`.trim();
  return truncate(raw, 160);
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: PASS — 11 tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/charity-seo.ts website/scripts/lib/charity-seo.test.ts
git commit -m "feat(seo): add charity meta description template"
```

---

## Task 4: Add charity FAQPage Q&A builder

**Files:**
- Modify: `website/scripts/lib/charity-seo.ts`
- Modify: `website/scripts/lib/charity-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `website/scripts/lib/charity-seo.test.ts`:

```typescript
import { buildCharityFaqPairs } from './charity-seo';

describe('buildCharityFaqPairs', () => {
  it('generates 3 Q&A pairs from charity data', () => {
    const pairs = buildCharityFaqPairs({
      name: 'Islamic Relief',
      score: 78,
      zakatStatus: 'ZAKAT_ELIGIBLE',
      mission: 'Global humanitarian aid.',
      city: 'Burbank',
      state: 'CA',
    });
    expect(pairs).toHaveLength(3);
    expect(pairs[0].question).toBe('Is Islamic Relief zakat eligible?');
    expect(pairs[0].answer).toContain('Zakat Eligible');
    expect(pairs[1].question).toBe("What is Islamic Relief's impact rating?");
    expect(pairs[1].answer).toContain('78');
    expect(pairs[2].question).toContain('Where is Islamic Relief based');
    expect(pairs[2].answer).toContain('Burbank');
  });

  it('handles SADAQAH_ONLY in the zakat Q&A answer', () => {
    const pairs = buildCharityFaqPairs({
      name: 'Doctors Without Borders',
      score: 72,
      zakatStatus: 'SADAQAH_ONLY',
      mission: 'Medical aid.',
      city: 'New York',
      state: 'NY',
    });
    expect(pairs[0].answer).toContain('sadaqah');
    expect(pairs[0].answer).not.toContain('Zakat Eligible');
  });

  it('omits location parts gracefully when city/state missing', () => {
    const pairs = buildCharityFaqPairs({
      name: 'Test',
      score: 50,
      zakatStatus: 'UNCLEAR',
      mission: 'Test mission.',
      city: null,
      state: null,
    });
    expect(pairs[2].answer).not.toContain('null');
    expect(pairs[2].answer).toContain('Test mission');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: FAIL — `buildCharityFaqPairs` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `website/scripts/lib/charity-seo.ts`:

```typescript
import type { FaqPair } from './schema';

export interface CharityFaqInput {
  name: string;
  score: number | null;
  zakatStatus: ZakatStatus;
  mission: string;
  city: string | null;
  state: string | null;
}

export function buildCharityFaqPairs(input: CharityFaqInput): FaqPair[] {
  const zakatQ = `Is ${input.name} zakat eligible?`;
  let zakatA: string;
  switch (input.zakatStatus) {
    case 'ZAKAT_ELIGIBLE':
      zakatA = `Yes — ${input.name} is classified as Zakat Eligible by Good Measure Giving based on its programs and beneficiary alignment with the 8 zakat categories.`;
      break;
    case 'SADAQAH_ONLY':
      zakatA = `No — ${input.name} is sadaqah-eligible but does not meet the criteria for zakat eligibility in Good Measure Giving's evaluation.`;
      break;
    case 'NEW_ORG':
      zakatA = `${input.name} is an early-stage organization; zakat eligibility has not yet been determined.`;
      break;
    default:
      zakatA = `${input.name}'s zakat eligibility is currently unclear in Good Measure Giving's evaluation.`;
  }

  const ratingQ = `What is ${input.name}'s impact rating?`;
  const ratingA = input.score != null
    ? `Good Measure Giving rates ${input.name} ${input.score}/100 on impact, alignment, and financial transparency.`
    : `${input.name} is evaluated by Good Measure Giving but does not yet have a numeric rating.`;

  const locationQ = `Where is ${input.name} based and what do they do?`;
  const locationParts: string[] = [];
  if (input.city && input.state) {
    locationParts.push(`${input.name} is based in ${input.city}, ${input.state}.`);
  } else {
    locationParts.push(`${input.name} operates as an independent Muslim charity.`);
  }
  if (input.mission) {
    locationParts.push(input.mission);
  }
  const locationA = locationParts.join(' ');

  return [
    { question: zakatQ, answer: zakatA },
    { question: ratingQ, answer: ratingA },
    { question: locationQ, answer: locationA },
  ];
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: PASS — 14 tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/charity-seo.ts website/scripts/lib/charity-seo.test.ts
git commit -m "feat(seo): add charity FAQPage Q&A builder"
```

---

## Task 5: Add Similar charities selector

**Files:**
- Modify: `website/scripts/lib/charity-seo.ts`
- Modify: `website/scripts/lib/charity-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `website/scripts/lib/charity-seo.test.ts`:

```typescript
import { selectSimilarCharities } from './charity-seo';

describe('selectSimilarCharities', () => {
  const pool = [
    { ein: '1', name: 'A', category: 'Humanitarian', amalScore: 80, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '2', name: 'B', category: 'Humanitarian', amalScore: 90, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '3', name: 'C', category: 'Humanitarian', amalScore: 70, zakatStatus: 'SADAQAH_ONLY' as const },
    { ein: '4', name: 'D', category: 'Education', amalScore: 85, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '5', name: 'E', category: 'Humanitarian', amalScore: 75, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
    { ein: '6', name: 'F', category: 'Humanitarian', amalScore: 95, zakatStatus: 'ZAKAT_ELIGIBLE' as const },
  ];

  it('returns up to 5 charities from the same category and same zakat tier, sorted by score desc', () => {
    const result = selectSimilarCharities({
      currentEin: '1',
      category: 'Humanitarian',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 5,
    });
    expect(result.map(c => c.ein)).toEqual(['6', '2', '5']);
  });

  it('excludes the current charity', () => {
    const result = selectSimilarCharities({
      currentEin: '6',
      category: 'Humanitarian',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 5,
    });
    expect(result.map(c => c.ein)).not.toContain('6');
  });

  it('respects the limit', () => {
    const result = selectSimilarCharities({
      currentEin: '1',
      category: 'Humanitarian',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 2,
    });
    expect(result).toHaveLength(2);
  });

  it('returns empty array when no same-category same-tier charities exist', () => {
    const result = selectSimilarCharities({
      currentEin: '1',
      category: 'NonexistentCategory',
      zakatStatus: 'ZAKAT_ELIGIBLE',
      pool,
      limit: 5,
    });
    expect(result).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: FAIL — `selectSimilarCharities` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `website/scripts/lib/charity-seo.ts`:

```typescript
export interface SimilarCharityCandidate {
  ein: string;
  name: string;
  category: string;
  amalScore: number | null;
  zakatStatus: ZakatStatus;
}

export interface SimilarSelectorInput {
  currentEin: string;
  category: string;
  zakatStatus: ZakatStatus;
  pool: SimilarCharityCandidate[];
  limit: number;
}

export function selectSimilarCharities(input: SimilarSelectorInput): SimilarCharityCandidate[] {
  return input.pool
    .filter((c) => c.ein !== input.currentEin)
    .filter((c) => c.category === input.category)
    .filter((c) => c.zakatStatus === input.zakatStatus)
    .sort((a, b) => (b.amalScore ?? 0) - (a.amalScore ?? 0))
    .slice(0, input.limit);
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/charity-seo.test.ts`
Expected: PASS — 18 tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/charity-seo.ts website/scripts/lib/charity-seo.test.ts
git commit -m "feat(seo): add selectSimilarCharities helper"
```

---

## Task 6: Wire new title/meta into `buildCharityMeta`

**Files:**
- Modify: `website/scripts/prerender.ts`

- [ ] **Step 1: Read the current `buildCharityMeta`**

Open `website/scripts/prerender.ts`. Locate the function starting at `function buildCharityMeta(detail: CharityDetail): PageMeta {`. Understand its current flow:
- Reads `amal_score`, `wallet_tag`, narratives from `detail.amalEvaluation`
- Builds `description` from score + walletTag + headline
- Builds `title` as `${name} | Good Measure Giving`
- Builds NonprofitOrganization JSON-LD (plus the Review schema we added in the post-Track-0 fix)

- [ ] **Step 2: Add imports at the top of `prerender.ts`**

Alongside the existing imports from `./lib/schema`, add imports from the new helper module:

```typescript
import {
  classifyZakatStatus,
  buildCharityTitle,
  buildCharityDescription,
  buildCharityFaqPairs,
  type ZakatStatus,
  type SimilarCharityCandidate,
} from './lib/charity-seo';
```

- [ ] **Step 3: Replace the title + description logic inside `buildCharityMeta`**

Find these lines inside `buildCharityMeta`:

```typescript
  const scorePart = isNewOrg ? 'Too early to rate numerically' : score != null ? `${score}/100` : 'Evaluated';
  const walletPart = walletTag ? ` ${walletTag[0].toUpperCase() + walletTag.slice(1)}.` : '';
  const headlinePart = headline ? ` ${headline}` : '';
  const raw = `${name}: ${scorePart}.${walletPart}${headlinePart}`;
  const description = truncate(raw, 160);

  const title = `${name} | Good Measure Giving`;
```

Replace with:

```typescript
  const zakatStatus: ZakatStatus = isNewOrg
    ? 'NEW_ORG'
    : classifyZakatStatus({
        walletTag: amal?.wallet_tag ?? null,
        zakatClassification: (detail as unknown as { zakat_classification?: string }).zakat_classification ?? null,
      });

  const title = buildCharityTitle({
    name,
    score: isNewOrg ? null : (score ?? null),
    zakatStatus,
  });

  const description = buildCharityDescription({
    name,
    score: isNewOrg ? null : (score ?? null),
    zakatStatus,
    missionFragment: headline || detail.mission || '',
  });
```

Nothing else in this function changes yet — NonprofitOrganization + Review schema builders stay as they are. The FAQPage addition is Task 7.

- [ ] **Step 4: Build and verify titles use the new template**

`cd website && npm run build 2>&1 | tee /tmp/t6-build.log | tail -5`
Expected: build succeeds.

`grep -o '<title>[^<]*</title>' website/dist/charity/*/index.html | head -5`
Expected: titles in the new shape. Look for at least one `Is ... Zakat Eligible?` title and at least one `... Review:` title.

- [ ] **Step 5: Run tests to confirm no regression**

`cd website && npm test -- --run 2>&1 | tail -5`
Expected: all tests (including the 18 new `charity-seo` tests) pass.

- [ ] **Step 6: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): rewrite charity page title and meta description"
```

---

## Task 7: Inject FAQPage + BreadcrumbList into charity pages

**Files:**
- Modify: `website/scripts/prerender.ts`

- [ ] **Step 1: Update `buildCharityMeta` to return multiple JSON-LD blocks**

Inside `buildCharityMeta`, find the section that currently builds a single `jsonLd` object (the NonprofitOrganization with the nested Review). At the end of the function, before the `return { ... }` statement, compute the FAQPage and BreadcrumbList blocks and collect all three into an array.

Replace the end of the function — the `return { ... }` block — with:

```typescript
  const faqPairs = buildCharityFaqPairs({
    name,
    score: isNewOrg ? null : (score ?? null),
    zakatStatus,
    mission: detail.mission ?? '',
    city: detail.location?.city ?? null,
    state: detail.location?.state ?? null,
  });

  const breadcrumbs = buildBreadcrumbSchema([
    { name: 'Home', url: `${SITE_URL}/` },
    { name: 'Browse Charities', url: `${SITE_URL}/browse` },
    { name, url: `${SITE_URL}/charity/${detail.ein}` },
  ]);

  const faqPageJsonLd = buildFaqPageSchema(faqPairs);

  const schemaBlocks: object[] = [jsonLd];
  if (faqPageJsonLd) schemaBlocks.push(faqPageJsonLd);
  if (breadcrumbs) schemaBlocks.push(breadcrumbs);

  return {
    route: `/charity/${detail.ein}`,
    title,
    description,
    canonical: `${SITE_URL}/charity/${detail.ein}`,
    ogType: 'article',
    jsonLd: schemaBlocks,
  };
```

(Keep the existing `jsonLd` local variable — the NonprofitOrganization object with the Review schema nested — and simply add the new blocks alongside it.)

- [ ] **Step 2: Build**

`cd website && npm run build 2>&1 | tee /tmp/t7-build.log | tail -5`
Expected: success.

- [ ] **Step 3: Verify all three schema types land on a sample charity page**

```bash
grep -o '"@type":"NonprofitOrganization"\|"@type":"FAQPage"\|"@type":"BreadcrumbList"' website/dist/charity/04-3810161/index.html | sort -u
```
Expected output (three lines, alphabetical):
```
"@type":"BreadcrumbList"
"@type":"FAQPage"
"@type":"NonprofitOrganization"
```

- [ ] **Step 4: Verify FAQ Q&A count on a charity page**

`grep -c '"@type":"Question"' website/dist/charity/04-3810161/index.html`
Expected: 3.

- [ ] **Step 5: Confirm no regression on other pages**

```bash
grep -c '"@type":"FAQPage"' website/dist/faq/index.html
grep -c '"@type":"Organization"' website/dist/about/index.html
```
Expected: 1 each.

- [ ] **Step 6: Run unit tests**

`cd website && npm test -- --run 2>&1 | tail -5`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): inject FAQPage + BreadcrumbList schema into charity pages"
```

---

## Task 8: Add `SimilarCharities` React component

**Files:**
- Create: `website/src/components/SimilarCharities.tsx`

- [ ] **Step 1: Check existing charity card pattern**

Run: `grep -l "CharityCard\|charity-card" website/src/components/*.tsx website/components/*.tsx 2>/dev/null | head -3`
Read one of the existing charity-card components to understand the styling/prop pattern used elsewhere. If there's a reusable `CharityCard` component, the `SimilarCharities` component can render a grid of them. If not, render simple anchored text cards with name + score + zakat tag.

- [ ] **Step 2: Write the component**

Create `website/src/components/SimilarCharities.tsx`:

```tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { useCharities } from '../hooks/useCharities';
import {
  selectSimilarCharities,
  classifyZakatStatus,
  type SimilarCharityCandidate,
  type ZakatStatus,
} from '../../scripts/lib/charity-seo';

interface SimilarCharitiesProps {
  currentEin: string;
  category: string;
  zakatStatus: ZakatStatus;
  limit?: number;
}

export const SimilarCharities: React.FC<SimilarCharitiesProps> = ({
  currentEin,
  category,
  zakatStatus,
  limit = 4,
}) => {
  const { charities, loading } = useCharities();

  if (loading || !charities || charities.length === 0) return null;

  const pool: SimilarCharityCandidate[] = charities.map((c) => ({
    ein: c.ein ?? c.id ?? '',
    name: c.name ?? '',
    category: c.primaryCategory ?? c.category ?? '',
    amalScore: c.amalScore ?? null,
    zakatStatus: classifyZakatStatus({
      walletTag: c.walletTag ?? null,
      zakatClassification: (c as unknown as { zakatClassification?: string }).zakatClassification ?? null,
    }),
  }));

  const similar = selectSimilarCharities({
    currentEin,
    category,
    zakatStatus,
    pool,
    limit,
  });

  if (similar.length === 0) return null;

  return (
    <section aria-labelledby="similar-charities-heading" className="mt-12">
      <h2
        id="similar-charities-heading"
        className="text-2xl font-semibold mb-4 text-slate-900 dark:text-slate-100"
      >
        Similar Charities
      </h2>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {similar.map((c) => (
          <li key={c.ein}>
            <Link
              to={`/charity/${c.ein}`}
              className="block p-4 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
            >
              <div className="font-medium text-slate-900 dark:text-slate-100">{c.name}</div>
              {c.amalScore != null && (
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  {c.amalScore}/100 · {c.zakatStatus === 'ZAKAT_ELIGIBLE' ? 'Zakat Eligible' : c.zakatStatus === 'SADAQAH_ONLY' ? 'Sadaqah-Eligible' : 'Under Review'}
                </div>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
};
```

If the import `useCharities` path differs from `../hooks/useCharities`, adjust it — check `website/src/hooks/useCharities.ts` exists and exports a hook returning `{ charities, loading }`.

- [ ] **Step 3: Build to confirm TypeScript passes**

`cd website && npm run build 2>&1 | tee /tmp/t8-build.log | tail -10`
Expected: success. If there's a type mismatch on `CharitySummary` fields (e.g. `primaryCategory` doesn't exist), adjust the field accessors to match the actual shape — don't add `as any`.

- [ ] **Step 4: Commit**

```bash
git add website/src/components/SimilarCharities.tsx
git commit -m "feat(seo): add SimilarCharities component"
```

---

## Task 9: Render `SimilarCharities` in baseline view of `CharityDetailsPage`

**Files:**
- Modify: `website/pages/CharityDetailsPage.tsx`

- [ ] **Step 1: Find the baseline render section**

Read `website/pages/CharityDetailsPage.tsx`. The file uses `useRichAccess` (imported around line 31, destructured around line 76). The component likely renders baseline content first, then rich content conditionally. The `SimilarCharities` component must render regardless of rich-access state — place it OUTSIDE any `{canViewRich && ...}` guard.

Look for a stable point near the end of the page JSX — after the charity header/summary/facts but before any rich-only blocks or footer. A good anchor: find where the component returns `</div>` before its outer wrapper, and insert `<SimilarCharities />` just before that outermost-but-one close.

- [ ] **Step 2: Add import**

At the top of the file alongside other component imports:

```tsx
import { SimilarCharities } from '../src/components/SimilarCharities';
import { classifyZakatStatus } from '../scripts/lib/charity-seo';
```

- [ ] **Step 3: Compute the props and render the component**

Near the other derived values in the component body (where `canViewRich`, `viewsUsed`, etc. are destructured), add:

```tsx
  const zakatStatusForSimilar = detail ? classifyZakatStatus({
    walletTag: detail.amalEvaluation?.wallet_tag ?? null,
    zakatClassification: (detail as unknown as { zakat_classification?: string }).zakat_classification ?? null,
  }) : 'UNCLEAR';
```

(Adjust `detail` to match whatever the actual charity-detail variable name is in this file — likely `charity`, `detail`, or `data`.)

Then in the JSX, insert the component as the last section before the outermost wrapper's closing tag, always visible:

```tsx
  {detail && (
    <SimilarCharities
      currentEin={detail.ein}
      category={detail.category ?? ''}
      zakatStatus={zakatStatusForSimilar}
      limit={4}
    />
  )}
```

Place this AFTER any rich-gated blocks but INSIDE the main container. Do NOT wrap it in the `canViewRich` guard.

- [ ] **Step 4: Run dev server and manually verify the component renders**

```bash
(cd website && npm run dev -- --port 5182 > /tmp/vite-5182.log 2>&1 &)
sleep 5
curl -s http://localhost:5182/charity/04-3810161 | grep -c "Similar Charities"
pkill -f "vite.*5182"
```

Expected: the grep finds 0 (content renders client-side, curl sees only the shell) — which is fine, we just need to confirm the dev server doesn't crash. Check `/tmp/vite-5182.log` — no errors.

For a real visual check: open `http://localhost:5182/charity/04-3810161` in a browser during development.

- [ ] **Step 5: Run unit tests**

`cd website && npm test -- --run 2>&1 | tail -5`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add website/pages/CharityDetailsPage.tsx
git commit -m "feat(seo): render SimilarCharities in charity detail baseline view"
```

---

## Task 10: Add `noindex` meta to `/profile`, `/compare`, `/bookmarks`

**Files:**
- Modify: `website/scripts/prerender.ts`

- [ ] **Step 1: Extend `PageMeta` to support `noindex`**

In `PageMeta` interface near the top of the file, add a `noindex?: boolean` field:

```typescript
interface PageMeta {
  route: string;
  title: string;
  description: string;
  canonical: string;
  ogType: string;
  jsonLd?: object | object[];
  noindex?: boolean;
}
```

- [ ] **Step 2: Emit `<meta name="robots">` in `injectMeta`**

In `injectMeta`, after the canonical-link block and before the OG-tag block, add:

```typescript
  // Robots directive — emit noindex,nofollow when flagged, else keep default (index,follow implicit)
  if (meta.noindex) {
    if (html.includes('name="robots"')) {
      html = html.replace(
        /<meta\s+name="robots"\s+content="[^"]*"\s*\/?>/,
        '<meta name="robots" content="noindex,nofollow" />'
      );
    } else {
      html = html.replace('</title>', '</title>\n    <meta name="robots" content="noindex,nofollow" />');
    }
  }
```

- [ ] **Step 3: Add the three pages to `buildStaticMeta`**

Append to the returned array inside `buildStaticMeta` (after the existing `/about` entry):

```typescript
    {
      route: '/profile',
      title: 'Profile | Good Measure Giving',
      description: 'Your Good Measure Giving profile.',
      canonical: `${SITE_URL}/profile`,
      ogType: 'website',
      noindex: true,
    },
    {
      route: '/compare',
      title: 'Compare Charities | Good Measure Giving',
      description: 'Compare charities side by side on Good Measure Giving.',
      canonical: `${SITE_URL}/compare`,
      ogType: 'website',
      noindex: true,
    },
    {
      route: '/bookmarks',
      title: 'Bookmarks | Good Measure Giving',
      description: 'Your bookmarked charities.',
      canonical: `${SITE_URL}/bookmarks`,
      ogType: 'website',
      noindex: true,
    },
```

- [ ] **Step 4: Build**

`cd website && npm run build 2>&1 | tee /tmp/t10-build.log | tail -10`
Expected: success; prerender log shows 3 more static pages than before.

- [ ] **Step 5: Verify noindex is present on the three pages**

```bash
grep -o 'name="robots"[^>]*noindex' website/dist/profile/index.html website/dist/compare/index.html website/dist/bookmarks/index.html
```
Expected: 3 matches, one per file.

- [ ] **Step 6: Verify no regression — robots tag NOT present on indexable pages**

```bash
grep -c 'noindex' website/dist/faq/index.html website/dist/charity/04-3810161/index.html website/dist/about/index.html
```
Expected: `0` on every line (three files, no noindex match).

- [ ] **Step 7: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): noindex /profile, /compare, /bookmarks"
```

---

## Task 11: Extend E2E schema test to cover charity pages and noindex

**Files:**
- Modify: `website/tests/e2e/seo-schema.spec.ts`

- [ ] **Step 1: Read the existing test shape**

Open `website/tests/e2e/seo-schema.spec.ts`. It has helpers `extractJsonLdBlocks` and `topLevelTypes`, plus 5 scenarios. This task appends 3 more scenarios.

- [ ] **Step 2: Append 3 new tests inside the existing `test.describe` block**

Insert before the closing `});` of the `test.describe('SEO schema injection (Track 0)', ...)` block:

```typescript
  test('a charity page has NonprofitOrganization, FAQPage, and BreadcrumbList schemas', () => {
    const charityDir = path.join(DIST_DIR, 'charity');
    const dirs = fs.readdirSync(charityDir, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name);
    expect(dirs.length).toBeGreaterThan(0);

    const sample = dirs[0];
    const html = fs.readFileSync(path.join(charityDir, sample, 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('NonprofitOrganization');
    expect(types).toContain('FAQPage');
    expect(types).toContain('BreadcrumbList');
  });

  test('charity page title uses new template (either "Is ... Zakat Eligible" or "... Review")', () => {
    const charityDir = path.join(DIST_DIR, 'charity');
    const dirs = fs.readdirSync(charityDir, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name);

    // Check at least one charity page matches the new title pattern
    let anyMatches = false;
    for (const d of dirs) {
      const html = fs.readFileSync(path.join(charityDir, d, 'index.html'), 'utf-8');
      const titleMatch = html.match(/<title>([^<]+)<\/title>/);
      if (titleMatch && /Is .+ Zakat Eligible\?|\bReview:/.test(titleMatch[1])) {
        anyMatches = true;
        break;
      }
    }
    expect(anyMatches).toBe(true);
  });

  test('/profile, /compare, /bookmarks have noindex meta', () => {
    for (const route of ['profile', 'compare', 'bookmarks']) {
      const html = fs.readFileSync(path.join(DIST_DIR, route, 'index.html'), 'utf-8');
      expect(html).toMatch(/name="robots"[^>]*noindex/);
    }
  });
```

- [ ] **Step 3: Build, then run the extended test**

```bash
cd website && npm run build 2>&1 | tail -3
npx playwright test tests/e2e/seo-schema.spec.ts --project=chromium 2>&1 | tail -10
```
Expected: build succeeds; all 8 tests pass (5 original + 3 new).

- [ ] **Step 4: Commit**

```bash
git add website/tests/e2e/seo-schema.spec.ts
git commit -m "test(seo): extend schema E2E to cover charity pages and noindex"
```

---

## Task 12: Rich Results validation (manual)

**Files:** none (manual verification)

- [ ] **Step 1: Deploy to preview environment**

Per the project's existing deploy process (see `website/DEPLOYMENT.md`), push the branch and get a Cloudflare Pages preview URL.

- [ ] **Step 2: Validate with Google Rich Results Test**

For each URL below, paste into https://search.google.com/test/rich-results and confirm 0 errors:

- `<preview-url>/charity/04-3810161` (or any charity) → should detect Review, FAQ, Breadcrumbs
- `<preview-url>/charity/<another-ein>` → spot-check a second charity
- `<preview-url>/faq` → should detect FAQ (regression check)
- `<preview-url>/methodology` → should detect Article + Breadcrumbs (regression check)

Record results in `/tmp/rich-results-track-1.txt`.

- [ ] **Step 3: Verify `noindex` is respected**

Fetch `<preview-url>/profile` and inspect HTML — confirm `<meta name="robots" content="noindex,nofollow">` is present in the served HTML (not just the dev-server version).

- [ ] **Step 4: Submit the updated sitemap to Search Console (optional if already submitted)**

Good Measure Giving's sitemap should be resubmitted if new static pages are added. `/profile`, `/compare`, `/bookmarks` intentionally stay OUT of the sitemap (they're noindex).

- [ ] **Step 5: No commit — this is validation only**

---

## Acceptance criteria

When every task above is checked off:

1. `website/scripts/lib/charity-seo.ts` exports `classifyZakatStatus`, `buildCharityTitle`, `buildCharityDescription`, `buildCharityFaqPairs`, `selectSimilarCharities`. All pure functions, all unit-tested (18 new tests passing).
2. `website/scripts/prerender.ts` uses the new helpers for charity page titles, meta descriptions, and JSON-LD. Each charity page now has 3 schema blocks: `NonprofitOrganization` (with nested `Review`), `FAQPage` (3 Q&A), `BreadcrumbList`.
3. `website/src/components/SimilarCharities.tsx` renders in the baseline view of `CharityDetailsPage` — visible to users and crawlers regardless of auth state.
4. `/profile`, `/compare`, `/bookmarks` emit `<meta name="robots" content="noindex,nofollow">` in their prerendered HTML.
5. `website/tests/e2e/seo-schema.spec.ts` passes 8 scenarios (5 from Track 0 + 3 new).
6. Google Rich Results Test validates 0 errors on charity pages.

## Out of scope for this plan (saved for future plans)

- Cause-area hubs (Track 2 — Plan 3)
- Calculator pages (Track 4 — Plan 4)
- Editorial guides (Track 3 — Plan 5)
- Related guides block on charity pages (requires guides to exist first — will be added in Track 3)
- Rewriting the rich narrative body or charity page layout
- Public `<noscript>` fallback for Similar charities (Google renders JS; revisit only if indexation lags)

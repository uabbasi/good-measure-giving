# SEO Track 0: Existing Content Indexing + Shared Schema Infrastructure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index the 31 existing `/prompts/:id` pages, inject structured-data schema (FAQPage, TechArticle, Organization, BreadcrumbList) into `/faq`, `/methodology`, and `/about` via the prerender pipeline, and extract a reusable schema-builder library that every later SEO track will use.

**Architecture:** New `website/scripts/lib/schema.ts` module exports typed builders for the five schema shapes this plan uses (FAQPage, BreadcrumbList, Article, TechArticle, Organization). The existing `website/scripts/prerender.ts` is extended to (a) accept multiple JSON-LD blocks per page (array), (b) load prompt data and produce a PageMeta per prompt, (c) inject FAQPage schema into `/faq`. The existing `website/scripts/generateSitemap.ts` gains a prompts section. FAQ data moves from inline `FAQPage.tsx` to `website/src/data/faq.ts` so both runtime and build-time code read the same source.

**Tech Stack:** TypeScript 5.8, Vitest 4, Puppeteer (existing prerender), Playwright (E2E), JSON-LD 1.1 (Schema.org vocab).

**Spec reference:** `docs/superpowers/specs/2026-04-19-seo-strategy-design.md` — Track 0 and Technical SEO sections.

---

## File Structure

**New files:**
- `website/scripts/lib/schema.ts` — shared schema builders (FAQPage, BreadcrumbList, Article, TechArticle, Organization). Pure functions.
- `website/scripts/lib/schema.test.ts` — Vitest unit tests for the builders.
- `website/src/data/faq.ts` — FAQ Q&A data as a typed export. Single source of truth for runtime component and prerender.
- `website/tests/e2e/seo-schema.spec.ts` — Playwright test verifying schema presence in prerendered HTML.

**Modified files:**
- `website/scripts/prerender.ts` — extend `PageMeta.jsonLd` to support arrays; add prompt-page rendering; add FAQPage schema to `/faq`; add TechArticle + BreadcrumbList to `/methodology`; add Organization to `/about`.
- `website/scripts/generateSitemap.ts` — emit `/prompts` + 31 `/prompts/:id` URLs.
- `website/pages/FAQPage.tsx` — import FAQ data from the new shared module instead of defining inline.

**No schema or data model changes** in `website/data/` — the prompt JSON files already have what we need.

---

## Task 1: Set up shared schema builder module (FAQPage)

**Files:**
- Create: `website/scripts/lib/schema.ts`
- Create: `website/scripts/lib/schema.test.ts`

- [ ] **Step 1: Write the failing test for `buildFaqPageSchema`**

Write to `website/scripts/lib/schema.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { buildFaqPageSchema } from './schema';

describe('buildFaqPageSchema', () => {
  it('produces a valid FAQPage schema from Q&A pairs', () => {
    const result = buildFaqPageSchema([
      { question: 'What is zakat?', answer: 'An Islamic obligation.' },
      { question: 'Who pays zakat?', answer: 'Muslims meeting nisab.' },
    ]);

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: [
        {
          '@type': 'Question',
          name: 'What is zakat?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'An Islamic obligation.',
          },
        },
        {
          '@type': 'Question',
          name: 'Who pays zakat?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'Muslims meeting nisab.',
          },
        },
      ],
    });
  });

  it('returns null when given an empty array', () => {
    expect(buildFaqPageSchema([])).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: FAIL with "Failed to resolve import './schema'" (module doesn't exist yet).

- [ ] **Step 3: Write the minimal implementation**

Write to `website/scripts/lib/schema.ts`:

```typescript
/**
 * Reusable Schema.org JSON-LD builders for the prerender pipeline.
 * Each builder is a pure function that returns a serializable object
 * (or null when input is insufficient).
 */

export interface FaqPair {
  question: string;
  answer: string;
}

export function buildFaqPageSchema(pairs: FaqPair[]): object | null {
  if (pairs.length === 0) return null;
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: pairs.map((p) => ({
      '@type': 'Question',
      name: p.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: p.answer,
      },
    })),
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: PASS, both test cases green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/schema.ts website/scripts/lib/schema.test.ts
git commit -m "feat(seo): add FAQPage schema builder"
```

---

## Task 2: Add BreadcrumbList builder

**Files:**
- Modify: `website/scripts/lib/schema.ts`
- Modify: `website/scripts/lib/schema.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `website/scripts/lib/schema.test.ts`:

```typescript
import { buildBreadcrumbSchema } from './schema';

describe('buildBreadcrumbSchema', () => {
  it('produces a BreadcrumbList from ordered crumbs', () => {
    const result = buildBreadcrumbSchema([
      { name: 'Home', url: 'https://goodmeasuregiving.org/' },
      { name: 'Browse', url: 'https://goodmeasuregiving.org/browse' },
      { name: 'Islamic Relief', url: 'https://goodmeasuregiving.org/charity/95-4251543' },
    ]);

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://goodmeasuregiving.org/' },
        { '@type': 'ListItem', position: 2, name: 'Browse', item: 'https://goodmeasuregiving.org/browse' },
        { '@type': 'ListItem', position: 3, name: 'Islamic Relief', item: 'https://goodmeasuregiving.org/charity/95-4251543' },
      ],
    });
  });

  it('returns null when given an empty crumb list', () => {
    expect(buildBreadcrumbSchema([])).toBeNull();
  });
});
```

Update the first import line to include the new function:

```typescript
import { buildFaqPageSchema, buildBreadcrumbSchema } from './schema';
```

(Remove the redundant second `import` line you appended.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: FAIL with "buildBreadcrumbSchema is not exported".

- [ ] **Step 3: Write the minimal implementation**

Append to `website/scripts/lib/schema.ts`:

```typescript
export interface Breadcrumb {
  name: string;
  url: string;
}

export function buildBreadcrumbSchema(crumbs: Breadcrumb[]): object | null {
  if (crumbs.length === 0) return null;
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs.map((c, idx) => ({
      '@type': 'ListItem',
      position: idx + 1,
      name: c.name,
      item: c.url,
    })),
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: PASS, all tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/schema.ts website/scripts/lib/schema.test.ts
git commit -m "feat(seo): add BreadcrumbList schema builder"
```

---

## Task 3: Add Article / TechArticle builder

**Files:**
- Modify: `website/scripts/lib/schema.ts`
- Modify: `website/scripts/lib/schema.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `website/scripts/lib/schema.test.ts`:

```typescript
import { buildArticleSchema } from './schema';

describe('buildArticleSchema', () => {
  it('produces a TechArticle with all fields', () => {
    const result = buildArticleSchema({
      type: 'TechArticle',
      headline: 'How We Evaluate Charities',
      description: 'Methodology for scoring Muslim charities on impact and alignment.',
      url: 'https://goodmeasuregiving.org/methodology',
      datePublished: '2026-02-01',
      dateModified: '2026-04-19',
      authorName: 'Good Measure Giving',
    });

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'TechArticle',
      headline: 'How We Evaluate Charities',
      description: 'Methodology for scoring Muslim charities on impact and alignment.',
      url: 'https://goodmeasuregiving.org/methodology',
      datePublished: '2026-02-01',
      dateModified: '2026-04-19',
      author: { '@type': 'Organization', name: 'Good Measure Giving' },
      publisher: { '@type': 'Organization', name: 'Good Measure Giving' },
    });
  });

  it('defaults to Article when type is omitted', () => {
    const result = buildArticleSchema({
      headline: 'Test',
      description: 'Test description.',
      url: 'https://goodmeasuregiving.org/test',
      datePublished: '2026-04-19',
      dateModified: '2026-04-19',
      authorName: 'GMG',
    });
    expect((result as { '@type': string })['@type']).toBe('Article');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: FAIL with "buildArticleSchema is not exported".

- [ ] **Step 3: Write the minimal implementation**

Append to `website/scripts/lib/schema.ts`:

```typescript
export interface ArticleInput {
  type?: 'Article' | 'TechArticle';
  headline: string;
  description: string;
  url: string;
  datePublished: string;
  dateModified: string;
  authorName: string;
}

export function buildArticleSchema(input: ArticleInput): object {
  return {
    '@context': 'https://schema.org',
    '@type': input.type ?? 'Article',
    headline: input.headline,
    description: input.description,
    url: input.url,
    datePublished: input.datePublished,
    dateModified: input.dateModified,
    author: { '@type': 'Organization', name: input.authorName },
    publisher: { '@type': 'Organization', name: input.authorName },
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: PASS, all tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/schema.ts website/scripts/lib/schema.test.ts
git commit -m "feat(seo): add Article/TechArticle schema builder"
```

---

## Task 4: Add Organization builder

**Files:**
- Modify: `website/scripts/lib/schema.ts`
- Modify: `website/scripts/lib/schema.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `website/scripts/lib/schema.test.ts`:

```typescript
import { buildOrganizationSchema } from './schema';

describe('buildOrganizationSchema', () => {
  it('produces an Organization schema with sameAs links', () => {
    const result = buildOrganizationSchema({
      name: 'Good Measure Giving',
      url: 'https://goodmeasuregiving.org',
      description: 'Independent charity evaluator for Muslim charities.',
      foundingDate: '2025-12-01',
      sameAs: ['https://twitter.com/goodmeasure', 'https://github.com/goodmeasure'],
    });

    expect(result).toEqual({
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: 'Good Measure Giving',
      url: 'https://goodmeasuregiving.org',
      description: 'Independent charity evaluator for Muslim charities.',
      foundingDate: '2025-12-01',
      sameAs: ['https://twitter.com/goodmeasure', 'https://github.com/goodmeasure'],
    });
  });

  it('omits sameAs when empty', () => {
    const result = buildOrganizationSchema({
      name: 'GMG',
      url: 'https://goodmeasuregiving.org',
      description: 'desc',
      foundingDate: '2025-12-01',
      sameAs: [],
    });
    expect('sameAs' in result).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: FAIL with "buildOrganizationSchema is not exported".

- [ ] **Step 3: Write the minimal implementation**

Append to `website/scripts/lib/schema.ts`:

```typescript
export interface OrganizationInput {
  name: string;
  url: string;
  description: string;
  foundingDate: string;
  sameAs: string[];
}

export function buildOrganizationSchema(input: OrganizationInput): object {
  const base: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: input.name,
    url: input.url,
    description: input.description,
    foundingDate: input.foundingDate,
  };
  if (input.sameAs.length > 0) {
    base.sameAs = input.sameAs;
  }
  return base;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd website && npm test -- scripts/lib/schema.test.ts`
Expected: PASS, all tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/schema.ts website/scripts/lib/schema.test.ts
git commit -m "feat(seo): add Organization schema builder"
```

---

## Task 5: Extend prerender `PageMeta.jsonLd` to accept an array

**Files:**
- Modify: `website/scripts/prerender.ts:46-53` (`PageMeta` interface)
- Modify: `website/scripts/prerender.ts:217-224` (inside `injectMeta`, JSON-LD insertion)

- [ ] **Step 1: Update the `PageMeta` type**

In `website/scripts/prerender.ts`, change the `jsonLd` field in the `PageMeta` interface:

```typescript
interface PageMeta {
  route: string;
  title: string;
  description: string;
  canonical: string;
  ogType: string;
  jsonLd?: object | object[];
}
```

- [ ] **Step 2: Update `injectMeta` to handle arrays**

Replace the JSON-LD injection block in `injectMeta` (the code currently reads `if (meta.jsonLd) { jsonLdTag = ... }`) with:

```typescript
  // Inject JSON-LD — support single object or array of schema blocks
  let jsonLdTag = '';
  if (meta.jsonLd) {
    const blocks = Array.isArray(meta.jsonLd) ? meta.jsonLd : [meta.jsonLd];
    jsonLdTag = blocks
      .map((block) => `\n    <script type="application/ld+json">${JSON.stringify(block)}</script>`)
      .join('');
  }
```

- [ ] **Step 3: Run build to verify no regression**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Expected: build succeeds, prerender runs, charity pages still have their `NonprofitOrganization` JSON-LD.

- [ ] **Step 4: Spot-check a charity page for schema preservation**

Run: `grep -A 1 'application/ld+json' website/dist/charity/95-4251543/index.html | head -5 | tee /tmp/seo-check.log`
Expected: output contains `"@type":"NonprofitOrganization"`.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "refactor(prerender): accept array of JSON-LD blocks per page"
```

---

## Task 6: Extract FAQ data to shared module

**Files:**
- Create: `website/src/data/faq.ts`
- Modify: `website/pages/FAQPage.tsx:4-8` (remove local `FAQItem` type) and its FAQ array definition

- [ ] **Step 1: Read current FAQ array from `FAQPage.tsx`**

Run: `grep -n "q:" website/pages/FAQPage.tsx | wc -l | tee /tmp/faq-count.log`
Note the count — this is the number of Q&A pairs to move.

- [ ] **Step 2: Create the shared FAQ data module**

Write to `website/src/data/faq.ts`:

```typescript
export type FaqCategory = 'general' | 'methodology' | 'ai' | 'zakat' | 'data';

export interface FaqItem {
  q: string;
  a: string;
  category: FaqCategory;
}

// Move the full FAQ array from `website/pages/FAQPage.tsx` into this export.
// Preserve order and content verbatim — this is the SAME data, just relocated
// so both the React component and the prerender script can import it.
export const FAQ_ITEMS: FaqItem[] = [
  // PASTE the existing array from FAQPage.tsx here, unchanged.
];
```

Then open `website/pages/FAQPage.tsx` and physically move the entire `faqs` array (and its item type if useful) into `website/src/data/faq.ts`. Replace the original array in `FAQPage.tsx` with an import:

```typescript
import { FAQ_ITEMS, type FaqItem } from '../src/data/faq';
// ...inside component body:
const faqs: FaqItem[] = FAQ_ITEMS;
```

Remove the inline `interface FAQItem` declaration from `FAQPage.tsx` — it's replaced by the import.

- [ ] **Step 3: Run the app locally to verify FAQ page still works**

Run: `cd website && npm run dev -- --port 5180 2>&1 | tee /tmp/vite-dev.log &`
Wait a few seconds, then: `curl -s http://localhost:5180/faq | head -20 | tee /tmp/faq-page.log`
Expected: HTML response, no error. Kill the dev server when done (`pkill -f "vite.*5180"`).

- [ ] **Step 4: Run existing unit tests to confirm no regression**

Run: `cd website && npm test -- --run 2>&1 | tee /tmp/seo-test.log`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add website/src/data/faq.ts website/pages/FAQPage.tsx
git commit -m "refactor(faq): extract FAQ data to shared module"
```

---

## Task 7: Inject FAQPage schema into `/faq` prerender

**Files:**
- Modify: `website/scripts/prerender.ts:70-113` (`buildStaticMeta` function)

- [ ] **Step 1: Import the FAQ data and the schema builder**

At the top of `website/scripts/prerender.ts`, add imports:

```typescript
import { FAQ_ITEMS } from '../src/data/faq';
import { buildFaqPageSchema, buildArticleSchema, buildOrganizationSchema, buildBreadcrumbSchema } from './lib/schema';
```

(Pre-declare all four — later tasks use the others; adding them now avoids touching this import line twice.)

- [ ] **Step 2: Add FAQPage schema to the `/faq` static meta entry**

In the `buildStaticMeta` function, locate the `/faq` object and add a `jsonLd` field:

```typescript
    {
      route: '/faq',
      title: 'FAQ | Good Measure Giving',
      description:
        'Common questions about charity evaluations, methodology, zakat compliance, and how to use Good Measure Giving.',
      canonical: `${SITE_URL}/faq`,
      ogType: 'website',
      jsonLd: buildFaqPageSchema(
        FAQ_ITEMS.map((item) => ({ question: item.q, answer: item.a }))
      ) ?? undefined,
    },
```

- [ ] **Step 3: Build and verify FAQPage JSON-LD is present**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Expected: build succeeds.

Run: `grep -o '"@type":"FAQPage"' website/dist/faq/index.html | tee /tmp/faq-schema.log`
Expected: output is `"@type":"FAQPage"`.

- [ ] **Step 4: Verify the Q&A pairs are in the output**

Run: `grep -c '"@type":"Question"' website/dist/faq/index.html | tee /tmp/faq-q-count.log`
Expected: output is a number matching the FAQ count from Task 6 Step 1.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): inject FAQPage schema into /faq prerender"
```

---

## Task 8: Inject TechArticle + BreadcrumbList into `/methodology` prerender

**Files:**
- Modify: `website/scripts/prerender.ts` — the `/methodology` entry in `buildStaticMeta`

- [ ] **Step 1: Update the `/methodology` meta entry with schema**

In `buildStaticMeta`, replace the `/methodology` object with:

```typescript
    {
      route: '/methodology',
      title: 'Methodology | Good Measure Giving',
      description:
        'How Good Measure Giving evaluates charities using a 100-point scoring framework covering impact, alignment, and data confidence.',
      canonical: `${SITE_URL}/methodology`,
      ogType: 'article',
      jsonLd: [
        buildArticleSchema({
          type: 'TechArticle',
          headline: 'How Good Measure Giving Evaluates Charities',
          description:
            'Our 100-point scoring framework covering impact, alignment, and data confidence.',
          url: `${SITE_URL}/methodology`,
          datePublished: '2026-02-01',
          dateModified: new Date().toISOString().split('T')[0],
          authorName: 'Good Measure Giving',
        }),
        buildBreadcrumbSchema([
          { name: 'Home', url: `${SITE_URL}/` },
          { name: 'Methodology', url: `${SITE_URL}/methodology` },
        ]) as object,
      ],
    },
```

- [ ] **Step 2: Build and verify both schemas are present**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Expected: build succeeds.

Run: `grep -o '"@type":"TechArticle"\|"@type":"BreadcrumbList"' website/dist/methodology/index.html | sort -u | tee /tmp/methodology-schema.log`
Expected: output contains both `"@type":"TechArticle"` and `"@type":"BreadcrumbList"`.

- [ ] **Step 3: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): inject TechArticle + BreadcrumbList into /methodology"
```

---

## Task 9: Inject Organization schema into `/about` prerender

**Files:**
- Modify: `website/scripts/prerender.ts` — the `/about` entry in `buildStaticMeta`

- [ ] **Step 1: Update the `/about` meta entry**

In `buildStaticMeta`, replace the `/about` object with:

```typescript
    {
      route: '/about',
      title: 'About | Good Measure Giving',
      description:
        'Independent charity evaluator focused on Muslim charities, built on evidence-based research and long-term thinking.',
      canonical: `${SITE_URL}/about`,
      ogType: 'website',
      jsonLd: buildOrganizationSchema({
        name: 'Good Measure Giving',
        url: SITE_URL,
        description:
          'Independent charity evaluator focused on Muslim charities, built on evidence-based research and long-term thinking.',
        foundingDate: '2025-12-01',
        sameAs: [],
      }),
    },
```

(The `sameAs` array is empty for now — can be populated later when public profiles exist.)

- [ ] **Step 2: Build and verify Organization schema is present**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Expected: build succeeds.

Run: `grep -o '"@type":"Organization"' website/dist/about/index.html | tee /tmp/about-schema.log`
Expected: output is `"@type":"Organization"`.

- [ ] **Step 3: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): inject Organization schema into /about"
```

---

## Task 10: Add prompt-page loading and PageMeta generation to prerender

**Files:**
- Modify: `website/scripts/prerender.ts` — `prerenderPages` function, add a new helper `buildPromptMeta` and load prompt index

- [ ] **Step 1: Inspect prompt data shape**

Run: `cat website/public/data/prompts/*.json 2>/dev/null | head -40 | tee /tmp/prompts-sample.log`
Note the JSON shape. Expected fields: `id`, `name`, `category`, `description`, and the prompt content. Only `id`, `name`, `category`, `description` are used for meta.

Run: `ls website/public/data/prompts/ | wc -l | tee /tmp/prompts-total.log`
Expected: count of prompt JSON files (~31 plus index).

- [ ] **Step 2: Check whether a prompts index JSON exists**

Run: `ls website/public/data/prompts/index.json 2>&1 | tee /tmp/prompts-idx.log`

If it exists, `prerender.ts` will load it. If not, the script needs to glob the directory. Confirm behavior before proceeding.

- [ ] **Step 3: Add prompt types and helper in `prerender.ts`**

Near the other type declarations in `website/scripts/prerender.ts`, add:

```typescript
interface PromptSummary {
  id: string;
  name: string;
  category: string;
  description: string;
  status?: 'active' | 'planned';
}

interface PromptsIndex {
  prompts: PromptSummary[];
}

const PROMPT_CATEGORY_LABELS: Record<string, string> = {
  quality_validation: 'Validate Charity Data Quality',
  data_extraction: 'Extract Charity Data',
  narrative_generation: 'Generate Charity Narratives',
  category_calibration: 'Calibrate Charity Categories',
};

function buildPromptMeta(prompt: PromptSummary): PageMeta {
  const categoryLabel = PROMPT_CATEGORY_LABELS[prompt.category] ?? 'Evaluate Charities';
  const title = `${prompt.name}: How We ${categoryLabel} | AI Transparency | GMG`;
  const description = truncate(
    `${prompt.description} — part of Good Measure Giving's open AI methodology for Muslim charity evaluation.`,
    160
  );

  return {
    route: `/prompts/${prompt.id}`,
    title,
    description,
    canonical: `${SITE_URL}/prompts/${prompt.id}`,
    ogType: 'article',
    jsonLd: [
      buildArticleSchema({
        type: 'TechArticle',
        headline: prompt.name,
        description: prompt.description,
        url: `${SITE_URL}/prompts/${prompt.id}`,
        datePublished: '2026-02-01',
        dateModified: new Date().toISOString().split('T')[0],
        authorName: 'Good Measure Giving',
      }),
      buildBreadcrumbSchema([
        { name: 'Home', url: `${SITE_URL}/` },
        { name: 'AI Transparency', url: `${SITE_URL}/prompts` },
        { name: prompt.name, url: `${SITE_URL}/prompts/${prompt.id}` },
      ]) as object,
    ],
  };
}
```

- [ ] **Step 4: Load prompts and generate metas in `prerenderPages`**

Near the top of `prerenderPages()`, after `charities` is loaded but before `console.log(...)`, add:

```typescript
  // Load prompt index
  const PROMPTS_INDEX_PATH = path.join(__dirname, '../public/data/prompts/index.json');
  let prompts: PromptSummary[] = [];
  if (fs.existsSync(PROMPTS_INDEX_PATH)) {
    const promptsIndex: PromptsIndex = JSON.parse(fs.readFileSync(PROMPTS_INDEX_PATH, 'utf-8'));
    prompts = promptsIndex.prompts || [];
  }

  for (const prompt of prompts) {
    metas.push(buildPromptMeta(prompt));
  }
```

Update the progress log to include prompts:

```typescript
  console.log(`Prerender: ${metas.length} pages (${metas.length - charities.length - prompts.length} static + ${charities.length} charities + ${prompts.length} prompts)`);
```

- [ ] **Step 5: Build and verify prompt pages are prerendered with schema**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Expected: build succeeds; `Prerender: N pages` log line includes prompt count.

Run: `ls website/dist/prompts/ 2>&1 | head -5 | tee /tmp/prompts-dist.log`
Expected: multiple prompt-id subdirectories (one per prompt).

Run: `grep -o '"@type":"TechArticle"\|"@type":"BreadcrumbList"' website/dist/prompts/$(ls website/dist/prompts/ | grep -v "index.html" | head -1)/index.html | sort -u | tee /tmp/prompts-schema.log`
Expected: both schema types present in the first prompt page.

- [ ] **Step 6: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): prerender /prompts/:id pages with TechArticle schema"
```

---

## Task 11: Add prompts URLs to sitemap

**Files:**
- Modify: `website/scripts/generateSitemap.ts`

- [ ] **Step 1: Extend `generateSitemap.ts` to include prompts**

Replace the full content of `website/scripts/generateSitemap.ts` with:

```typescript
/**
 * Sitemap Generator
 * Reads charity + prompt data and generates dist/sitemap.xml at build time.
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DIST_DIR = path.join(__dirname, '../dist');
const CHARITIES_JSON = path.join(__dirname, '../data/charities/charities.json');
const PROMPTS_INDEX = path.join(__dirname, '../public/data/prompts/index.json');
const SITE_URL = 'https://goodmeasuregiving.org';

interface CharitySummary {
  ein: string;
}

interface PromptSummary {
  id: string;
}

function generateSitemap() {
  const today = new Date().toISOString().split('T')[0];

  const staticPages = [
    { path: '/', priority: '1.0', changefreq: 'weekly' },
    { path: '/browse', priority: '0.9', changefreq: 'weekly' },
    { path: '/methodology', priority: '0.7', changefreq: 'monthly' },
    { path: '/about', priority: '0.6', changefreq: 'monthly' },
    { path: '/faq', priority: '0.6', changefreq: 'monthly' },
    { path: '/prompts', priority: '0.7', changefreq: 'monthly' },
  ];

  const urls = staticPages.map(
    (p) => `  <url>
    <loc>${SITE_URL}${p.path}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>${p.changefreq}</changefreq>
    <priority>${p.priority}</priority>
  </url>`
  );

  // Charity pages
  const charityData = JSON.parse(fs.readFileSync(CHARITIES_JSON, 'utf-8'));
  const charities: CharitySummary[] = charityData.charities || [];
  for (const charity of charities) {
    urls.push(`  <url>
    <loc>${SITE_URL}/charity/${charity.ein}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
  }

  // Prompt pages
  let prompts: PromptSummary[] = [];
  if (fs.existsSync(PROMPTS_INDEX)) {
    const promptsData = JSON.parse(fs.readFileSync(PROMPTS_INDEX, 'utf-8'));
    prompts = promptsData.prompts || [];
  }
  for (const prompt of prompts) {
    urls.push(`  <url>
    <loc>${SITE_URL}/prompts/${prompt.id}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>`);
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join('\n')}
</urlset>
`;

  fs.writeFileSync(path.join(DIST_DIR, 'sitemap.xml'), xml, 'utf-8');
  console.log(`Sitemap: ${urls.length} URLs (${staticPages.length} static + ${charities.length} charities + ${prompts.length} prompts)`);
}

generateSitemap();
```

- [ ] **Step 2: Build and verify sitemap contents**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Expected: `Sitemap: N URLs (6 static + 115 charities + 31 prompts)` (or similar actual counts).

Run: `grep -c '/prompts/' website/dist/sitemap.xml | tee /tmp/sitemap-prompts.log`
Expected: a count of 32 (1 index + 31 prompt pages) or matching the actual prompt count + 1.

- [ ] **Step 3: Commit**

```bash
git add website/scripts/generateSitemap.ts
git commit -m "feat(seo): add prompts URLs to sitemap"
```

---

## Task 12: E2E test — verify schema presence in prerendered HTML

**Files:**
- Create: `website/tests/e2e/seo-schema.spec.ts`

- [ ] **Step 1: Check existing Playwright config and patterns**

Run: `cat website/playwright.config.ts | head -30 | tee /tmp/pw-config.log`
Run: `ls website/tests/e2e/ | head -5 | tee /tmp/pw-tests.log`

Note the baseURL (usually `http://localhost:4173` or similar) and any shared setup pattern used by existing specs.

- [ ] **Step 2: Write the E2E test**

Write to `website/tests/e2e/seo-schema.spec.ts`:

```typescript
/**
 * Verifies that Track 0 schema injections are present in prerendered HTML.
 * These tests run against the built `dist/` output via `vite preview`.
 * Playwright config must serve from `dist/` (current setup does).
 */

import { test, expect } from '@playwright/test';

async function getJsonLdTypes(page: { locator: (s: string) => any }): Promise<string[]> {
  const scripts = page.locator('script[type="application/ld+json"]');
  const count = await scripts.count();
  const types: string[] = [];
  for (let i = 0; i < count; i++) {
    const text = await scripts.nth(i).innerText();
    const parsed = JSON.parse(text);
    types.push(parsed['@type']);
  }
  return types;
}

test.describe('SEO schema injection (Track 0)', () => {
  test('/faq has FAQPage schema', async ({ page }) => {
    await page.goto('/faq');
    const types = await getJsonLdTypes(page);
    expect(types).toContain('FAQPage');
  });

  test('/methodology has TechArticle and BreadcrumbList schemas', async ({ page }) => {
    await page.goto('/methodology');
    const types = await getJsonLdTypes(page);
    expect(types).toContain('TechArticle');
    expect(types).toContain('BreadcrumbList');
  });

  test('/about has Organization schema', async ({ page }) => {
    await page.goto('/about');
    const types = await getJsonLdTypes(page);
    expect(types).toContain('Organization');
  });

  test('a sample /prompts/:id page has TechArticle and BreadcrumbList schemas', async ({ page }) => {
    // Navigate to /prompts first to discover an actual prompt id
    await page.goto('/prompts');
    await page.waitForLoadState('networkidle');
    const firstPromptLink = await page.locator('a[href^="/prompts/"]').first().getAttribute('href');
    expect(firstPromptLink).toBeTruthy();

    await page.goto(firstPromptLink!);
    const types = await getJsonLdTypes(page);
    expect(types).toContain('TechArticle');
    expect(types).toContain('BreadcrumbList');
  });

  test('sitemap includes /prompts URLs', async ({ request }) => {
    const res = await request.get('/sitemap.xml');
    expect(res.ok()).toBe(true);
    const body = await res.text();
    expect(body).toMatch(/\/prompts\//);
  });
});
```

- [ ] **Step 3: Build and run the E2E test**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Expected: build succeeds.

Run: `cd website && npx playwright test tests/e2e/seo-schema.spec.ts 2>&1 | tee /tmp/seo-e2e.log`
Expected: all 5 tests pass.

If the "sample prompt page" test fails because of timing (prompts list fetched client-side), fall back to reading an id from `website/public/data/prompts/index.json` directly in the test instead of scraping the page.

- [ ] **Step 4: Commit**

```bash
git add website/tests/e2e/seo-schema.spec.ts
git commit -m "test(seo): add E2E verification of Track 0 schema injection"
```

---

## Task 13: Final validation with Rich Results Test

**Files:** none (manual verification)

- [ ] **Step 1: Deploy to preview environment**

Run: `cd website && npm run build 2>&1 | tee /tmp/seo-build.log`
Deploy `dist/` to the project's preview Cloudflare Pages URL (follow standard deploy process — consult `website/DEPLOYMENT.md` if unsure).

- [ ] **Step 2: Validate each new schema surface with Google's Rich Results Test**

For each URL below, paste into https://search.google.com/test/rich-results and confirm 0 errors:

- `https://<preview-url>/faq` → should detect FAQ
- `https://<preview-url>/methodology` → should detect Article (TechArticle treated as Article by the tool) and Breadcrumbs
- `https://<preview-url>/about` → should detect Organization (not a rich-result category but should validate)
- `https://<preview-url>/prompts/<any-prompt-id>` → should detect Article and Breadcrumbs

Record the results (screenshots or pasted output) in a note file `/tmp/rich-results-track-0.txt` for reference.

- [ ] **Step 3: Submit updated sitemap to Search Console**

In Google Search Console for `goodmeasuregiving.org`:
- Sitemaps → submit `https://goodmeasuregiving.org/sitemap.xml` (resubmit if already there)
- URL Inspection → fetch 1-2 prompt pages to request re-indexing

- [ ] **Step 4: No commit needed — this is validation only**

---

## Acceptance criteria

When every task above is checked off:

1. `website/scripts/lib/schema.ts` exports 4 schema builders, each with unit tests passing (Vitest).
2. `website/scripts/prerender.ts` injects FAQPage on `/faq`, TechArticle + BreadcrumbList on `/methodology`, Organization on `/about`, and TechArticle + BreadcrumbList on each `/prompts/:id`.
3. `website/scripts/generateSitemap.ts` emits `/prompts` + 31 `/prompts/:id` entries.
4. `website/tests/e2e/seo-schema.spec.ts` passes 5 scenarios in Playwright.
5. Rich Results Test validates 0 errors on all 4 page types.
6. FAQ data lives in `website/src/data/faq.ts`; `FAQPage.tsx` imports from it (no behavior change).
7. No regression in existing charity page schema or layout.

## Out of scope for this plan (saved for future plans)

- Charity page title/meta rewrite (Track 1 — Plan 2)
- FAQPage schema on charity pages (Track 1 — Plan 2)
- Cause-area hubs (Track 2 — Plan 3)
- Calculator pages (Track 4 — Plan 4)
- Editorial guides (Track 3 — Plan 5)
- Canonical / noindex tags on `/profile`, `/compare`, `/bookmarks` (Track 1 — Plan 2)

# SEO Track 3: Editorial Pillar Guides (Infrastructure + Guide #1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/guides/:slug` pillar pages that rank for high-authority queries ("what makes a charity zakat eligible", "how to evaluate a Muslim charity"). Ship infrastructure + Guide #1 as the seed; subsequent guides arrive as small data-only commits on an ongoing cadence.

**Architecture:** Guides are structured JSON (`website/data/guides/<slug>.json`) — no markdown dependency. Each guide has a typed shape of sections (heading + paragraphs), callouts, FAQ, and cross-links. A new `GuidePage` React component renders the structure; the prerender script emits static HTML with Article + FAQPage + BreadcrumbList schema. An index page (`/guides`) lists all guides. Internal linking hooks guides to charity pages and cause hubs.

**Tech Stack:** TypeScript 5.8, React 19, React Router 6, Vitest 4, existing prerender pipeline.

**Spec reference:** `docs/superpowers/specs/2026-04-19-seo-strategy-design.md` — Track 3 section.

**Out of scope (will ship as separate commits later):** Guides #2–#8. They reuse the same infrastructure; each is a small JSON file + list entry.

---

## File Structure

**New files:**
- `website/scripts/lib/guide-seo.ts` — type definitions for guide shape, optional helper utilities.
- `website/scripts/lib/guide-seo.test.ts` — Vitest unit tests (for any pure helpers).
- `website/data/guides/guides.json` — index of all guides (slug, title, description, publishedOn).
- `website/data/guides/what-makes-a-charity-zakat-eligible.json` — Guide #1 full content.
- `website/pages/GuidePage.tsx` — render one guide from its JSON.
- `website/pages/GuidesIndexPage.tsx` — `/guides` index listing all guides.

**Modified files:**
- `website/App.tsx` — routes `/guides` and `/guides/:slug`.
- `website/scripts/prerender.ts` — load guides, generate PageMeta for index + each guide with Article + FAQPage + BreadcrumbList schema.
- `website/scripts/generateSitemap.ts` — emit `/guides` + 1 `/guides/:slug` URL (more arrive in later commits).
- `website/tests/e2e/seo-schema.spec.ts` — 3 new scenarios.

**Pipeline changes:** none.

---

## Task 1: Guide type definitions

**Files:**
- Create: `website/scripts/lib/guide-seo.ts`
- Create: `website/scripts/lib/guide-seo.test.ts`

Pure type + a small helper for slug validation.

- [ ] **Step 1: Write the failing test**

Create `website/scripts/lib/guide-seo.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { isValidGuideSlug } from './guide-seo';

describe('isValidGuideSlug', () => {
  it('accepts kebab-case slugs', () => {
    expect(isValidGuideSlug('what-makes-a-charity-zakat-eligible')).toBe(true);
    expect(isValidGuideSlug('sadaqah-vs-zakat')).toBe(true);
  });

  it('rejects slugs with uppercase, spaces, underscores, or leading/trailing dashes', () => {
    expect(isValidGuideSlug('What-Makes')).toBe(false);
    expect(isValidGuideSlug('some guide')).toBe(false);
    expect(isValidGuideSlug('some_guide')).toBe(false);
    expect(isValidGuideSlug('-leading-dash')).toBe(false);
    expect(isValidGuideSlug('trailing-dash-')).toBe(false);
    expect(isValidGuideSlug('')).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

From `website/`: `npm test -- --run scripts/lib/guide-seo.test.ts`
Expected: FAIL — `Failed to resolve import './guide-seo'`.

- [ ] **Step 3: Write minimal implementation**

Create `website/scripts/lib/guide-seo.ts`:

```typescript
/**
 * Editorial guide type definitions and helpers.
 * Guides are structured JSON with typed sections — no markdown dependency.
 */

export interface GuideSection {
  heading: string;
  paragraphs: string[];
}

export interface GuideCallout {
  label: string;
  text: string;
}

export interface GuideFaqItem {
  q: string;
  a: string;
}

export interface GuideFeaturedCharity {
  ein: string;
  blurb: string;
}

export interface Guide {
  slug: string;
  title: string;
  metaTitle: string;
  metaDescription: string;
  tldr: string;
  publishedOn: string;
  updatedOn: string;
  readingTimeMinutes: number;
  sections: GuideSection[];
  callouts?: GuideCallout[];
  featuredCharities?: GuideFeaturedCharity[];
  faq: GuideFaqItem[];
  relatedGuides?: string[];
  relatedCauses?: string[];
}

export interface GuideSummary {
  slug: string;
  title: string;
  description: string;
  publishedOn: string;
  readingTimeMinutes: number;
}

export interface GuidesIndex {
  guides: GuideSummary[];
}

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function isValidGuideSlug(slug: string): boolean {
  if (slug.length === 0) return false;
  return SLUG_PATTERN.test(slug);
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/guide-seo.test.ts`
Expected: PASS — both test cases green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/guide-seo.ts website/scripts/lib/guide-seo.test.ts
git commit -m "feat(seo): add guide type definitions and slug validator"
```

---

## Task 2: Guides index data file

**Files:**
- Create: `website/data/guides/guides.json`

- [ ] **Step 1: Create the index file**

```json
{
  "guides": [
    {
      "slug": "what-makes-a-charity-zakat-eligible",
      "title": "What Makes a Muslim Charity Zakat Eligible?",
      "description": "The criteria Good Measure Giving uses to determine whether a Muslim charity qualifies for zakat — covering the 8 asnaf, programs vs. overhead, and common scholarly disagreements.",
      "publishedOn": "2026-04-19",
      "readingTimeMinutes": 9
    }
  ]
}
```

- [ ] **Step 2: Verify JSON parses**

```bash
node -e "console.log(JSON.parse(require('fs').readFileSync('website/data/guides/guides.json','utf8')).guides.length)"
```
Expected: `1`

- [ ] **Step 3: Commit**

```bash
git add website/data/guides/guides.json
git commit -m "feat(seo): add guides index data file"
```

---

## Task 3: Guide #1 content

**Files:**
- Create: `website/data/guides/what-makes-a-charity-zakat-eligible.json`

This is the seed guide. Content is authoritative and fiqh-accurate — reviewed against the `zakat-fiqh` skill knowledge.

- [ ] **Step 1: Create the guide JSON**

```json
{
  "slug": "what-makes-a-charity-zakat-eligible",
  "title": "What Makes a Muslim Charity Zakat Eligible?",
  "metaTitle": "What Makes a Muslim Charity Zakat Eligible? | Good Measure Giving",
  "metaDescription": "The criteria Good Measure Giving uses to determine whether a Muslim charity qualifies for zakat — the 8 asnaf, programs vs. overhead, and common scholarly disagreements explained.",
  "tldr": "A charity is zakat-eligible when its programs directly benefit people in the 8 Qur'anic categories of zakat recipients (asnaf) — primarily the poor and the needy — and when funds reach those beneficiaries rather than organizational overhead. Scholars disagree at the edges (education, advocacy, mosque operations), so eligibility is a judgment, not a yes/no checklist.",
  "publishedOn": "2026-04-19",
  "updatedOn": "2026-04-19",
  "readingTimeMinutes": 9,
  "sections": [
    {
      "heading": "The 8 asnaf: who zakat is for",
      "paragraphs": [
        "The Qur'an names eight categories of people who may receive zakat (Surah At-Tawbah 9:60): the poor (fuqara), the needy (masakin), those employed to administer zakat (amileen), those whose hearts have been reconciled (mu'allafah qulubuhum), those in bondage (riqab), those in debt (gharimeen), those in the path of Allah (fi sabilillah), and travelers in need (ibn al-sabil).",
        "Every zakat-eligibility judgment comes back to whether a charity's programs serve people in these categories. The first two — the poor and the needy — cover the majority of contemporary zakat giving. The others are narrower in modern application but still valid when the conditions are met.",
        "Good Measure Giving evaluates each charity against this framework. Programs serving the poor (emergency assistance, food programs, medical care for the uninsured) fit clearly. Programs serving categories that are technically still valid but rare today (like riqab, slaves being freed) fit when the modern analog is defensible (bonded labor, trafficking victims)."
      ]
    },
    {
      "heading": "Programs vs. overhead",
      "paragraphs": [
        "Zakat is a transfer from one set of hands to another — it must eventually reach a person in the 8 asnaf. Organizational overhead is a tool that enables that transfer, not the transfer itself.",
        "When a charity's program-expense ratio is strong (typically >80%) and its programs directly serve eligible recipients, the overhead is functionally absorbed into the transfer. When programs are weak, overhead high, or both, less of your zakat reaches eligible recipients than you might assume.",
        "Some scholars are stricter — arguing that zakat must pass through beneficiaries with minimal mediation. Others are more flexible, accepting well-run humanitarian organizations as effective zakat pipelines. Both views have classical support. Good Measure Giving's scoring reflects the pragmatic-but-demanding middle: we accept organizational mediation when it demonstrably improves outcomes for eligible recipients."
      ]
    },
    {
      "heading": "The hardest cases",
      "paragraphs": [
        "Three areas produce the most disagreement in modern zakat-eligibility analysis:",
        "Education. Scholarships for needy students are broadly accepted (they serve the poor). General-enrollment scholarships are harder — the 'needy' criterion isn't automatically met. Skill training for adults in poverty (trades, literacy) is generally accepted. University endowments serving middle-class Muslims are generally not.",
        "Advocacy and civil-rights work. Most scholars restrict zakat to programs that reach individual beneficiaries in the 8 asnaf. Advocacy doesn't reach individuals directly. Sadaqah (voluntary charity) is universally appropriate for this work; zakat is not.",
        "Mosque operations. A mosque that earmarks zakat for eligible recipients (the poor in its congregation, travelers needing help) handles zakat correctly. A mosque that uses zakat for utilities, mortgage, or staff salaries is on weaker ground — those aren't transfers to people in the asnaf, they're operating costs. This is a significant practical issue for American mosques and is worth asking about directly before giving zakat to your local masjid."
      ]
    },
    {
      "heading": "How Good Measure Giving classifies charities",
      "paragraphs": [
        "We assign each charity a wallet-tag reflecting our zakat-eligibility judgment: Zakat Eligible (programs clearly serve the 8 asnaf), Sadaqah Eligible (worthy giving target, but doesn't meet the zakat criteria), or Unclear (insufficient data or scholarly disagreement).",
        "The judgment is based on the charity's stated programs (from their website, 990 filings, and public materials), not on self-identification. A charity can call itself 'zakat-accepting' without meeting the criteria; we evaluate what they actually do.",
        "Our classifications are conservative by design. When a charity's programs blur the line — say, a religious-outreach organization that also runs a small direct-service program — we lean toward Sadaqah Eligible rather than Zakat Eligible, and note the reasoning. Donors can always choose to give zakat to an Unclear charity based on their own scholar's opinion; we're trying to flag ambiguity, not resolve it for everyone."
      ]
    },
    {
      "heading": "What to do with this",
      "paragraphs": [
        "If you're planning your annual zakat and want to reach the largest number of eligible recipients per dollar, focus on charities in the Zakat Eligible tier whose programs match your priorities (humanitarian relief, basic needs, medical care for the poor). The Browse page on Good Measure Giving filters by eligibility.",
        "If you want to support work that isn't zakat-eligible but is still important (civil rights, research, education, dawah), give through sadaqah. The total can still be substantial — Islamic tradition encourages giving beyond the zakat minimum.",
        "If your local mosque handles zakat transparently and earmarks funds for eligible recipients, giving through them is legitimate and supports your community. If they don't have that structure, give mosque support as sadaqah and zakat through organizations whose programs you trust."
      ]
    }
  ],
  "callouts": [
    {
      "label": "Scholarly note",
      "text": "This guide reflects the majority scholarly view across the four Sunni madhabs. Where scholars differ, the guide notes the disagreement. When in doubt, consult a scholar you trust — this guide is an evaluation framework, not a fatwa."
    }
  ],
  "featuredCharities": [],
  "faq": [
    {
      "q": "Is zakat eligibility the same as whether a charity says it accepts zakat?",
      "a": "No. Many charities say they accept zakat without having programs that meet the criteria. Good Measure Giving evaluates the programs, not the self-identification."
    },
    {
      "q": "Can I split my zakat across multiple charities?",
      "a": "Yes — there's no scholarly restriction on splitting. In fact, diversifying across multiple zakat-eligible charities reduces concentration risk if any single charity turns out weaker than expected."
    },
    {
      "q": "What if scholars I respect disagree with Good Measure Giving's classification?",
      "a": "Follow your scholar. Our classifications reflect a specific scholarly tradition and a specific evaluation methodology. They're one input among others — not a substitute for your own reasoning or the guidance of a trusted scholar."
    },
    {
      "q": "Does a zakat-eligible rating mean a charity is a good donation target overall?",
      "a": "No. Zakat eligibility is one dimension. A charity can be zakat-eligible but poorly run, or zakat-ineligible but operationally excellent. Our separate impact and data-confidence scores address the other dimensions."
    },
    {
      "q": "Why does Good Measure Giving mark some charities as Unclear?",
      "a": "When the programs blur the line between categories, when public data is thin, or when scholarly opinion is genuinely divided, we note that rather than forcing a binary answer. Unclear is a conservative holding position until we have better evidence."
    }
  ],
  "relatedGuides": [],
  "relatedCauses": ["humanitarian", "basic-needs", "religious-congregation"]
}
```

- [ ] **Step 2: Verify JSON parses**

```bash
node -e "const g = JSON.parse(require('fs').readFileSync('website/data/guides/what-makes-a-charity-zakat-eligible.json','utf8')); console.log('sections:', g.sections.length, 'faq:', g.faq.length, 'reading:', g.readingTimeMinutes, 'min')"
```
Expected: `sections: 5 faq: 5 reading: 9 min`

- [ ] **Step 3: Commit**

```bash
git add website/data/guides/what-makes-a-charity-zakat-eligible.json
git commit -m "feat(seo): add Guide #1 - What Makes a Muslim Charity Zakat Eligible?"
```

---

## Task 4: GuidePage React component

**Files:**
- Create: `website/pages/GuidePage.tsx`

- [ ] **Step 1: Write the component**

```tsx
import React, { useEffect, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import type { Guide } from '../scripts/lib/guide-seo';

export const GuidePage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { isDark } = useLandingTheme();
  const [guide, setGuide] = useState<Guide | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!slug) return;
    fetch(`/data/guides/${slug}.json`)
      .then((r) => {
        if (!r.ok) {
          setNotFound(true);
          return null;
        }
        return r.json();
      })
      .then((data: Guide | null) => {
        if (data) {
          setGuide(data);
          document.title = data.metaTitle;
        }
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));

    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [slug]);

  if (notFound) return <Navigate to="/guides" replace />;

  if (loading || !guide) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={isDark ? 'text-slate-400' : 'text-slate-600'}>Loading guide…</div>
      </div>
    );
  }

  return (
    <article className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <Link to="/guides" className="hover:underline">Guides</Link>
          <span className="mx-2">/</span>
          <span>{guide.title}</span>
        </nav>

        <header className="mb-10">
          <h1 className="text-4xl font-semibold mb-3">{guide.title}</h1>
          <div className="text-sm text-slate-500">
            {guide.readingTimeMinutes} min read · Updated {new Date(guide.updatedOn).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
          </div>
        </header>

        <div className="mb-10 p-4 rounded-lg bg-slate-100 dark:bg-slate-800/50 border-l-4 border-emerald-500">
          <div className="text-xs uppercase tracking-wide font-semibold text-slate-500 dark:text-slate-400 mb-1">TL;DR</div>
          <p className="text-slate-800 dark:text-slate-200">{guide.tldr}</p>
        </div>

        {guide.sections.map((section, i) => (
          <section key={i} className="mb-10">
            <h2 className="text-2xl font-semibold mb-4">{section.heading}</h2>
            {section.paragraphs.map((p, j) => (
              <p key={j} className="mb-4 leading-relaxed text-slate-700 dark:text-slate-300">{p}</p>
            ))}
          </section>
        ))}

        {guide.callouts && guide.callouts.length > 0 && (
          <div className="mb-10">
            {guide.callouts.map((c, i) => (
              <div key={i} className="p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 mb-4">
                <div className="text-xs uppercase tracking-wide font-semibold text-amber-700 dark:text-amber-400 mb-1">{c.label}</div>
                <p className="text-amber-900 dark:text-amber-100">{c.text}</p>
              </div>
            ))}
          </div>
        )}

        <section className="mb-10">
          <h2 className="text-2xl font-semibold mb-4">Frequently Asked Questions</h2>
          <dl>
            {guide.faq.map((item, i) => (
              <div key={i} className="mb-6">
                <dt className="font-semibold text-slate-900 dark:text-slate-100">{item.q}</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>

        {guide.relatedCauses && guide.relatedCauses.length > 0 && (
          <section className="mb-10">
            <h2 className="text-2xl font-semibold mb-4">Related Cause Areas</h2>
            <ul className="flex flex-wrap gap-2">
              {guide.relatedCauses.map((slug) => (
                <li key={slug}>
                  <Link to={`/causes/${slug}`} className="inline-block px-3 py-1 text-sm rounded-full border border-slate-300 dark:border-slate-700 hover:border-slate-500">
                    {slug.replace(/-/g, ' ')}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </article>
  );
};
```

- [ ] **Step 2: Build**

`cd website && npm run build 2>&1 | tail -5`
Expected: success. If any import path is wrong (e.g. `useLandingTheme`), match what other pages use by inspecting `FAQPage.tsx`.

- [ ] **Step 3: Commit**

```bash
git add website/pages/GuidePage.tsx
git commit -m "feat(seo): add GuidePage component"
```

---

## Task 5: GuidesIndexPage React component

**Files:**
- Create: `website/pages/GuidesIndexPage.tsx`

- [ ] **Step 1: Write the component**

```tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import type { GuidesIndex, GuideSummary } from '../scripts/lib/guide-seo';

export const GuidesIndexPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const [guides, setGuides] = useState<GuideSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = 'Guides | Good Measure Giving';
    fetch('/data/guides/guides.json')
      .then((r) => r.json())
      .then((data: GuidesIndex) => setGuides(data.guides || []))
      .catch(() => setGuides([]))
      .finally(() => setLoading(false));

    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <span>Guides</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Guides</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">
          Evergreen guides to evaluating Muslim charities, planning zakat, and thinking about impact.
        </p>

        {loading ? (
          <div className="text-slate-500">Loading guides…</div>
        ) : guides.length === 0 ? (
          <div className="text-slate-500">No guides published yet.</div>
        ) : (
          <ul className="space-y-4">
            {guides.map((g) => (
              <li key={g.slug}>
                <Link
                  to={`/guides/${g.slug}`}
                  className="block p-5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
                >
                  <h2 className="text-xl font-semibold mb-2">{g.title}</h2>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">{g.description}</p>
                  <div className="text-xs text-slate-500">
                    {g.readingTimeMinutes} min read
                  </div>
                </Link>
              </li>
            ))}
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
git add website/pages/GuidesIndexPage.tsx
git commit -m "feat(seo): add GuidesIndexPage listing all guides"
```

---

## Task 6: Wire routes in App.tsx

**Files:**
- Modify: `website/App.tsx`

- [ ] **Step 1: Add imports**

Alongside the existing lazy-loaded page imports:

```tsx
const GuidesIndexPage = lazy(() => import('./pages/GuidesIndexPage').then(m => ({ default: m.GuidesIndexPage })));
const GuidePage = lazy(() => import('./pages/GuidePage').then(m => ({ default: m.GuidePage })));
```

- [ ] **Step 2: Add routes**

In the `<Routes>` block, after the existing `/causes/:slug` route and before the `*` catch-all:

```tsx
            <Route path="/guides" element={<GuidesIndexPage />} />
            <Route path="/guides/:slug" element={<GuidePage />} />
```

- [ ] **Step 3: Verify dev server serves the routes**

```bash
(cd website && npm run dev -- --port 5184 > /tmp/vite-5184.log 2>&1 &)
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5184/guides
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5184/guides/what-makes-a-charity-zakat-eligible
pkill -f "vite.*5184"
```
Expected: both return `200`.

- [ ] **Step 4: Commit**

```bash
git add website/App.tsx
git commit -m "feat(seo): route /guides and /guides/:slug"
```

---

## Task 7: Copy guide JSON to public/data at build time

Guides in `website/data/guides/` need to be served by the dev server and Cloudflare Pages at `/data/guides/...`. The existing pattern for charity data uses `public/data/` for client fetches — we need a build-time copy from `data/guides/` to `public/data/guides/`.

**Files:**
- Modify: `website/package.json` (scripts section)
- Create: `website/scripts/copyGuides.ts`

- [ ] **Step 1: Write the copy script**

Create `website/scripts/copyGuides.ts`:

```typescript
/**
 * Copies guide JSON files from data/guides/ to public/data/guides/
 * so they're served at /data/guides/:slug.json at runtime.
 */
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SRC = path.join(__dirname, '../data/guides');
const DST = path.join(__dirname, '../public/data/guides');

if (!fs.existsSync(SRC)) {
  console.log('No guides source directory; skipping copy.');
  process.exit(0);
}

fs.mkdirSync(DST, { recursive: true });
const files = fs.readdirSync(SRC).filter((f) => f.endsWith('.json'));
for (const f of files) {
  fs.copyFileSync(path.join(SRC, f), path.join(DST, f));
}
console.log(`Copied ${files.length} guide files to ${path.relative(process.cwd(), DST)}`);
```

- [ ] **Step 2: Update `website/package.json` `prebuild` script**

Currently:
```json
"prebuild": "node scripts/syncUiSignalsConfig.mjs && tsx scripts/convertData.ts"
```

Change to:
```json
"prebuild": "node scripts/syncUiSignalsConfig.mjs && tsx scripts/convertData.ts && tsx scripts/copyGuides.ts"
```

Also add a `predev` script so guides are available in dev mode too:
```json
"predev": "tsx scripts/copyGuides.ts"
```

And update `dev`:
```json
"dev": "vite"
```
(no change needed for the `dev` entry itself — `predev` auto-runs before)

- [ ] **Step 3: Build and verify**

`cd website && npm run build 2>&1 | tail -5`
Expected: success; copy log line appears.

```bash
ls website/public/data/guides/
```
Expected: `guides.json`, `what-makes-a-charity-zakat-eligible.json`.

- [ ] **Step 4: Add `public/data/guides/` to gitignore**

The copy script writes to `public/data/guides/`. These are generated files — source of truth is `data/guides/`. Exclude them from git.

Append to `website/.gitignore` (or root `.gitignore` — match how `public/data/charities` is handled; check existing pattern first):

```
public/data/guides/
```

- [ ] **Step 5: Commit**

```bash
git add website/scripts/copyGuides.ts website/package.json website/.gitignore
git commit -m "feat(seo): copy guide JSON to public/data at build time"
```

(Exact gitignore path may differ — adjust to match project convention.)

---

## Task 8: Prerender guides with schema

**Files:**
- Modify: `website/scripts/prerender.ts`

- [ ] **Step 1: Add imports and interfaces**

Alongside the existing `./lib/cause-seo` import:

```typescript
import type { Guide, GuideSummary, GuidesIndex } from './lib/guide-seo';
```

- [ ] **Step 2: Add helper functions**

After the existing `buildCauseMeta` function, append:

```typescript
function buildGuidesIndexMeta(guides: GuideSummary[]): PageMeta {
  return {
    route: '/guides',
    title: 'Guides | Good Measure Giving',
    description: 'Evergreen guides to evaluating Muslim charities, planning zakat, and thinking about impact.',
    canonical: `${SITE_URL}/guides`,
    ogType: 'website',
    jsonLd: [
      {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: 'Guides',
        url: `${SITE_URL}/guides`,
        description: 'Evergreen guides to evaluating Muslim charities and planning zakat.',
        mainEntity: {
          '@type': 'ItemList',
          numberOfItems: guides.length,
          itemListElement: guides.map((g, i) => ({
            '@type': 'ListItem',
            position: i + 1,
            url: `${SITE_URL}/guides/${g.slug}`,
            name: g.title,
          })),
        },
      },
      buildBreadcrumbSchema([
        { name: 'Home', url: `${SITE_URL}/` },
        { name: 'Guides', url: `${SITE_URL}/guides` },
      ]) as object,
    ],
  };
}

function buildGuideMeta(guide: Guide): PageMeta {
  const faqPairs = guide.faq.map((item) => ({ question: item.q, answer: item.a }));
  const faqPage = buildFaqPageSchema(faqPairs);

  const article = buildArticleSchema({
    type: 'Article',
    headline: guide.title,
    description: guide.metaDescription,
    url: `${SITE_URL}/guides/${guide.slug}`,
    datePublished: guide.publishedOn,
    dateModified: guide.updatedOn,
    authorName: 'Good Measure Giving',
  });

  const breadcrumbs = buildBreadcrumbSchema([
    { name: 'Home', url: `${SITE_URL}/` },
    { name: 'Guides', url: `${SITE_URL}/guides` },
    { name: guide.title, url: `${SITE_URL}/guides/${guide.slug}` },
  ]);

  const schemaBlocks: object[] = [article];
  if (faqPage) schemaBlocks.push(faqPage);
  if (breadcrumbs) schemaBlocks.push(breadcrumbs);

  return {
    route: `/guides/${guide.slug}`,
    title: guide.metaTitle,
    description: truncate(guide.metaDescription, 160),
    canonical: `${SITE_URL}/guides/${guide.slug}`,
    ogType: 'article',
    jsonLd: schemaBlocks,
  };
}
```

- [ ] **Step 3: Load guides and push metas in `prerenderPages`**

After the existing cause-loading block inside `prerenderPages`, add:

```typescript
  // Load guides
  const GUIDES_DIR = path.join(__dirname, '../data/guides');
  const GUIDES_INDEX_PATH = path.join(GUIDES_DIR, 'guides.json');
  let guideSummaries: GuideSummary[] = [];
  const guides: Guide[] = [];
  if (fs.existsSync(GUIDES_INDEX_PATH)) {
    const index: GuidesIndex = JSON.parse(fs.readFileSync(GUIDES_INDEX_PATH, 'utf-8'));
    guideSummaries = index.guides || [];
    for (const summary of guideSummaries) {
      const guidePath = path.join(GUIDES_DIR, `${summary.slug}.json`);
      if (fs.existsSync(guidePath)) {
        const guide: Guide = JSON.parse(fs.readFileSync(guidePath, 'utf-8'));
        guides.push(guide);
      } else {
        console.warn(`  Warning: guide index lists ${summary.slug} but file is missing`);
      }
    }
  }

  if (guideSummaries.length > 0) {
    metas.push(buildGuidesIndexMeta(guideSummaries));
    for (const guide of guides) {
      metas.push(buildGuideMeta(guide));
    }
  }
```

Update the prerender log line to include guides:

```typescript
  const causeCount = causes.length > 0 ? causes.length + 1 : 0;
  const guideCount = guideSummaries.length > 0 ? guideSummaries.length + 1 : 0;
  console.log(`Prerender: ${metas.length} pages (${metas.length - charities.length - prompts.length - causeCount - guideCount} static + ${charities.length} charities + ${prompts.length} prompts + ${causeCount} causes + ${guideCount} guides)`);
```

- [ ] **Step 4: Build and verify**

`cd website && npm run build 2>&1 | tee /tmp/t8-build.log | tail -10`
Expected: log line shows `+ 2 guides` (index + Guide #1).

```bash
ls website/dist/guides/
ls website/dist/guides/what-makes-a-charity-zakat-eligible/
grep -o '"@type":"Article"\|"@type":"FAQPage"\|"@type":"BreadcrumbList"' website/dist/guides/what-makes-a-charity-zakat-eligible/index.html | sort -u
```
Expected: directory exists, index.html present, all 3 schema types detected.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): prerender /guides and /guides/:slug with Article+FAQ+Breadcrumb"
```

---

## Task 9: Add guide URLs to sitemap

**Files:**
- Modify: `website/scripts/generateSitemap.ts`

- [ ] **Step 1: Extend generator**

Near the existing path constants, add:

```typescript
const GUIDES_INDEX = path.join(__dirname, '../data/guides/guides.json');
```

Near the existing interfaces:

```typescript
interface GuideSummary {
  slug: string;
}
```

After the existing cause-URL block in `generateSitemap()`:

```typescript
  // Guide pages
  let guides: GuideSummary[] = [];
  if (fs.existsSync(GUIDES_INDEX)) {
    const guidesData = JSON.parse(fs.readFileSync(GUIDES_INDEX, 'utf-8'));
    guides = guidesData.guides || [];
  }
  if (guides.length > 0) {
    urls.push(`  <url>
    <loc>${SITE_URL}/guides</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>`);
    for (const g of guides) {
      urls.push(`  <url>
    <loc>${SITE_URL}/guides/${g.slug}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>`);
    }
  }
```

Update the log line:

```typescript
  const causeCount = causes.length > 0 ? causes.length + 1 : 0;
  const guideCount = guides.length > 0 ? guides.length + 1 : 0;
  console.log(`Sitemap: ${urls.length} URLs (${staticPages.length} static + ${charities.length} charities + ${prompts.length} prompts + ${causeCount} causes + ${guideCount} guides)`);
```

- [ ] **Step 2: Build and verify**

`cd website && npm run build 2>&1 | tail -3`

```bash
grep -c '/guides' website/dist/sitemap.xml
```
Expected: 2 (index + Guide #1).

- [ ] **Step 3: Commit**

```bash
git add website/scripts/generateSitemap.ts
git commit -m "feat(seo): add guide URLs to sitemap"
```

---

## Task 10: E2E coverage for guides

**Files:**
- Modify: `website/tests/e2e/seo-schema.spec.ts`

- [ ] **Step 1: Append scenarios**

Insert before the closing `});` of the `test.describe` block:

```typescript
  test('/guides index has CollectionPage and BreadcrumbList schemas', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'guides', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('CollectionPage');
    expect(types).toContain('BreadcrumbList');
  });

  test('/guides/what-makes-a-charity-zakat-eligible has Article, FAQPage, and BreadcrumbList schemas', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'guides', 'what-makes-a-charity-zakat-eligible', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('Article');
    expect(types).toContain('FAQPage');
    expect(types).toContain('BreadcrumbList');
  });

  test('sitemap includes /guides URLs', () => {
    const xml = fs.readFileSync(path.join(DIST_DIR, 'sitemap.xml'), 'utf-8');
    expect(xml).toMatch(/\/guides\//);
  });
```

- [ ] **Step 2: Run E2E**

```bash
cd website && npm run build 2>&1 | tail -3
npx playwright test tests/e2e/seo-schema.spec.ts --project=chromium 2>&1 | tail -5
```
Expected: 14 tests pass (11 existing + 3 new).

- [ ] **Step 3: Commit**

```bash
git add website/tests/e2e/seo-schema.spec.ts
git commit -m "test(seo): extend E2E coverage to guides"
```

---

## Task 11: Rich Results validation (manual)

**Files:** none.

- [ ] **Step 1: Deploy to preview**

Per `website/DEPLOYMENT.md`.

- [ ] **Step 2: Validate the guide page**

Paste `<preview-url>/guides/what-makes-a-charity-zakat-eligible` into https://search.google.com/test/rich-results.
Expected: Article detected, FAQ detected, Breadcrumbs detected, 0 errors.

- [ ] **Step 3: Resubmit sitemap in Search Console; use URL Inspection on the guide page**

- [ ] **Step 4: No commit — validation only**

---

## Acceptance criteria

When every task above is checked off:

1. `website/scripts/lib/guide-seo.ts` exports the `Guide`, `GuideSection`, `GuideFaqItem`, `GuideSummary`, `GuidesIndex` types and a `isValidGuideSlug` helper with unit tests.
2. `website/data/guides/guides.json` lists Guide #1; `what-makes-a-charity-zakat-eligible.json` contains the full guide content.
3. Routes `/guides` and `/guides/:slug` serve the new React pages.
4. `npm run build` generates `website/dist/guides/index.html` + `website/dist/guides/what-makes-a-charity-zakat-eligible/index.html` with correct Article + FAQPage + BreadcrumbList schema.
5. Sitemap includes `/guides` + `/guides/what-makes-a-charity-zakat-eligible`.
6. E2E spec passes 14 scenarios.
7. Rich Results Test validates 0 errors on the guide page.

## Adding subsequent guides (follow-up work)

Each additional guide (#2–#8) is a 2-file commit:
1. Add a new entry to `website/data/guides/guides.json`.
2. Add `website/data/guides/<slug>.json` with full content.

The prerender, sitemap, routing, and schema all pick up the new guide automatically. No code changes needed.

Target sequence per the spec:
- Guide #2: `how-to-evaluate-a-muslim-charity`
- Guide #3: `top-zakat-eligible-charities-2026`
- Guide #4: `sadaqah-vs-zakat`
- Guide #5: `the-nisab-explained`
- Guide #6: `complete-zakat-planning-guide`
- Guide #7: `how-to-budget-giving`
- Guide #8: `who-receives-zakat-the-8-categories`

## Out of scope for this plan

- Related-guides block on charity pages (can be added once ≥3 guides exist, in a follow-up)
- Guides embedded in cause hub pages (same — wait for more guides)
- Markdown rendering (intentionally avoided — structured JSON is simpler and more controllable)
- Author profiles (for E-E-A-T signal — defer until we have a clear author-attribution strategy)

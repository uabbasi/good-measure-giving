# SEO Track 2: Cause-Area Hubs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/causes/:slug` hub pages (one per MECE category) that list the charities in that cause, present a unique intro + FAQ, and emit CollectionPage + ItemList + FAQPage + BreadcrumbList JSON-LD so Google can rank them for queries like "best Muslim humanitarian charity" or "top Muslim civil rights organizations."

**Architecture:** Hub taxonomy reuses the existing MECE categories from charity data (`primaryCategory` field — `HUMANITARIAN`, `RELIGIOUS_CONGREGATION`, etc.). A new static data file `website/data/causes/causes.json` holds per-category slug, display name, intro text, and FAQ Q&A. Two new React pages (`CausesIndexPage`, `CausePage`) render the hubs client-side. The prerender script generates static HTML with injected schema at build time. Charity detail pages link to their cause hub. No LLM calls at build time — intros are authored once and committed.

**Tech Stack:** TypeScript 5.8, React 19, React Router 6, Vitest 4, existing prerender pipeline.

**Spec reference:** `docs/superpowers/specs/2026-04-19-seo-strategy-design.md` — Track 2 section.

**Data observation (as of 2026-04-19):** 169 charities distributed across 16 MECE categories. HUMANITARIAN (35), RELIGIOUS_CONGREGATION (23), CIVIL_RIGHTS_LEGAL (20) are the largest. All 16 categories have ≥2 charities — every hub will be non-trivial.

---

## File Structure

**New files:**
- `website/scripts/lib/cause-seo.ts` — taxonomy helpers: slug <-> category, charity-filtering. Pure functions, unit-tested.
- `website/scripts/lib/cause-seo.test.ts` — Vitest unit tests.
- `website/data/causes/causes.json` — seed data for 16 hubs: slug, displayName, category, intro (2–3 sentences), faq (4 Q&A).
- `website/pages/CausePage.tsx` — single hub render (charity list + intro + FAQ).
- `website/pages/CausesIndexPage.tsx` — `/causes/` index listing all hubs.

**Modified files:**
- `website/App.tsx` — routes `/causes` → `CausesIndexPage`, `/causes/:slug` → `CausePage`.
- `website/scripts/prerender.ts` — load causes.json, generate PageMeta per hub + the index, inject CollectionPage + ItemList + FAQPage + BreadcrumbList.
- `website/scripts/generateSitemap.ts` — emit `/causes` + 16 `/causes/:slug` URLs.
- `website/pages/CharityDetailsPage.tsx` — "Browse more in [cause]" link to the cause hub.
- `website/tests/e2e/seo-schema.spec.ts` — add 3 scenarios covering `/causes/` index, a sample hub, and sitemap coverage.

**No pipeline changes.** `primaryCategory` already exists on every charity.

---

## Task 1: Taxonomy helpers in cause-seo lib

**Files:**
- Create: `website/scripts/lib/cause-seo.ts`
- Create: `website/scripts/lib/cause-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Create `website/scripts/lib/cause-seo.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { categoryToSlug, slugToCategory, CAUSE_SLUGS } from './cause-seo';

describe('categoryToSlug', () => {
  it('converts MECE category to kebab-case slug', () => {
    expect(categoryToSlug('HUMANITARIAN')).toBe('humanitarian');
    expect(categoryToSlug('RELIGIOUS_CONGREGATION')).toBe('religious-congregation');
    expect(categoryToSlug('CIVIL_RIGHTS_LEGAL')).toBe('civil-rights-legal');
    expect(categoryToSlug('EDUCATION_K12_RELIGIOUS')).toBe('education-k12-religious');
  });

  it('returns null for null/empty input', () => {
    expect(categoryToSlug(null)).toBeNull();
    expect(categoryToSlug('')).toBeNull();
  });
});

describe('slugToCategory', () => {
  it('round-trips every known slug back to its category', () => {
    for (const slug of CAUSE_SLUGS) {
      const category = slugToCategory(slug);
      expect(category).not.toBeNull();
      expect(categoryToSlug(category!)).toBe(slug);
    }
  });

  it('returns null for unknown slug', () => {
    expect(slugToCategory('not-a-real-cause')).toBeNull();
  });
});

describe('CAUSE_SLUGS', () => {
  it('contains all 16 MECE category slugs', () => {
    expect(CAUSE_SLUGS).toHaveLength(16);
    expect(CAUSE_SLUGS).toContain('humanitarian');
    expect(CAUSE_SLUGS).toContain('religious-congregation');
    expect(CAUSE_SLUGS).toContain('civil-rights-legal');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

From `website/`: `npm test -- --run scripts/lib/cause-seo.test.ts`
Expected: FAIL — `Failed to resolve import './cause-seo'`.

- [ ] **Step 3: Write minimal implementation**

Create `website/scripts/lib/cause-seo.ts`:

```typescript
/**
 * Cause-area hub helpers. Pure functions.
 * Maps MECE categories (HUMANITARIAN, CIVIL_RIGHTS_LEGAL, ...) to
 * URL slugs and back.
 */

const CATEGORY_TO_SLUG: Record<string, string> = {
  HUMANITARIAN: 'humanitarian',
  RELIGIOUS_CONGREGATION: 'religious-congregation',
  CIVIL_RIGHTS_LEGAL: 'civil-rights-legal',
  MEDICAL_HEALTH: 'medical-health',
  PHILANTHROPY_GRANTMAKING: 'philanthropy-grantmaking',
  EDUCATION_INTERNATIONAL: 'education-international',
  RESEARCH_POLICY: 'research-policy',
  RELIGIOUS_OUTREACH: 'religious-outreach',
  BASIC_NEEDS: 'basic-needs',
  EDUCATION_HIGHER_RELIGIOUS: 'education-higher-religious',
  EDUCATION_K12_RELIGIOUS: 'education-k12-religious',
  ENVIRONMENT_CLIMATE: 'environment-climate',
  SOCIAL_SERVICES: 'social-services',
  WOMENS_SERVICES: 'womens-services',
  ADVOCACY_CIVIC: 'advocacy-civic',
  MEDIA_JOURNALISM: 'media-journalism',
};

const SLUG_TO_CATEGORY: Record<string, string> = Object.fromEntries(
  Object.entries(CATEGORY_TO_SLUG).map(([cat, slug]) => [slug, cat])
);

export const CAUSE_SLUGS: readonly string[] = Object.values(CATEGORY_TO_SLUG);

export function categoryToSlug(category: string | null): string | null {
  if (!category) return null;
  return CATEGORY_TO_SLUG[category] ?? null;
}

export function slugToCategory(slug: string): string | null {
  return SLUG_TO_CATEGORY[slug] ?? null;
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/cause-seo.test.ts`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/cause-seo.ts website/scripts/lib/cause-seo.test.ts
git commit -m "feat(seo): add cause category <-> slug helpers"
```

---

## Task 2: Charity-filtering helper for hubs

**Files:**
- Modify: `website/scripts/lib/cause-seo.ts`
- Modify: `website/scripts/lib/cause-seo.test.ts`

- [ ] **Step 1: Write the failing test**

Update import at top of `cause-seo.test.ts`:
```typescript
import { categoryToSlug, slugToCategory, CAUSE_SLUGS, filterCharitiesByCategory, type HubCharity } from './cause-seo';
```

Append:

```typescript
describe('filterCharitiesByCategory', () => {
  const pool: HubCharity[] = [
    { ein: '1', name: 'A', primaryCategory: 'HUMANITARIAN', amalScore: 80, walletTag: 'ZAKAT-ELIGIBLE' },
    { ein: '2', name: 'B', primaryCategory: 'HUMANITARIAN', amalScore: 90, walletTag: 'SADAQAH-ELIGIBLE' },
    { ein: '3', name: 'C', primaryCategory: 'MEDICAL_HEALTH', amalScore: 75, walletTag: 'ZAKAT-ELIGIBLE' },
    { ein: '4', name: 'D', primaryCategory: 'HUMANITARIAN', amalScore: null, walletTag: 'UNCLEAR' },
    { ein: '5', name: 'E', primaryCategory: null, amalScore: 70, walletTag: 'ZAKAT-ELIGIBLE' },
  ];

  it('returns charities in the specified category, sorted by amalScore desc, nulls last', () => {
    const result = filterCharitiesByCategory(pool, 'HUMANITARIAN');
    expect(result.map(c => c.ein)).toEqual(['2', '1', '4']);
  });

  it('returns empty array when no charities match', () => {
    expect(filterCharitiesByCategory(pool, 'NONEXISTENT')).toEqual([]);
  });

  it('skips charities with null primaryCategory', () => {
    const result = filterCharitiesByCategory(pool, 'HUMANITARIAN');
    expect(result.map(c => c.ein)).not.toContain('5');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

`npm test -- --run scripts/lib/cause-seo.test.ts`
Expected: FAIL — `filterCharitiesByCategory` / `HubCharity` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `website/scripts/lib/cause-seo.ts`:

```typescript
export interface HubCharity {
  ein: string;
  name: string;
  primaryCategory: string | null;
  amalScore: number | null;
  walletTag: string | null;
}

export function filterCharitiesByCategory(pool: HubCharity[], category: string): HubCharity[] {
  return pool
    .filter((c) => c.primaryCategory === category)
    .sort((a, b) => {
      if (a.amalScore == null && b.amalScore == null) return 0;
      if (a.amalScore == null) return 1;
      if (b.amalScore == null) return -1;
      return b.amalScore - a.amalScore;
    });
}
```

- [ ] **Step 4: Run the test to verify it passes**

`npm test -- --run scripts/lib/cause-seo.test.ts`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add website/scripts/lib/cause-seo.ts website/scripts/lib/cause-seo.test.ts
git commit -m "feat(seo): add filterCharitiesByCategory helper"
```

---

## Task 3: Seed cause data with intros and FAQ

**Files:**
- Create: `website/data/causes/causes.json`

This task writes a static data file with 16 hub entries. Each entry has:
- `slug` — URL slug (from Task 1)
- `category` — MECE category (matches `primaryCategory` on charity data)
- `displayName` — human-readable hub title
- `intro` — 2–3 sentence unique intro differentiated per cause (NOT templated)
- `faq` — 4 Q&A pairs specific to the cause

The intros and FAQs are authored to be unique per cause to avoid thin-content flags from Google.

- [ ] **Step 1: Create `website/data/causes/causes.json`**

```json
{
  "causes": [
    {
      "slug": "humanitarian",
      "category": "HUMANITARIAN",
      "displayName": "Humanitarian Relief",
      "intro": "Muslim humanitarian charities work in conflict zones, disaster areas, and chronic-crisis regions where secular aid organizations often can't reach. The strongest organizations combine rapid emergency response with long-term recovery programs and transparent financial reporting. This is the most crowded category in our evaluation — small differences in program-expense ratios and on-the-ground presence matter a lot.",
      "faq": [
        { "q": "What makes a Muslim humanitarian charity zakat-eligible?", "a": "Zakat-eligibility for humanitarian charities depends on whether their programs align with the 8 asnaf (categories of recipients) — primarily the poor, the needy, and those burdened with debt. Organizations serving refugees, food-insecure families, and medical-care-lacking communities typically qualify, provided funds reach direct beneficiaries rather than only organizational overhead." },
        { "q": "How do we evaluate humanitarian charities?", "a": "We score on impact (evidence of outcomes, not just outputs), alignment (mission fit with evidence-based giving), and data confidence (quality of public reporting). Program-expense ratio, independent audits, and beneficiary counts all feed into the score." },
        { "q": "What are red flags in this category?", "a": "High administrative overhead (>20%), vague beneficiary counts without methodology, no independent audit, political affiliation that compromises aid neutrality, or heavy dependence on a single donor." },
        { "q": "Should I give zakat to humanitarian charities or local mosques?", "a": "Both can be zakat-eligible depending on their specific programs. Humanitarian charities typically reach more beneficiaries per dollar; local masjids provide community infrastructure. Good Measure Giving evaluates each charity individually rather than generalizing by type." }
      ]
    },
    {
      "slug": "religious-congregation",
      "category": "RELIGIOUS_CONGREGATION",
      "displayName": "Masjids & Religious Congregations",
      "intro": "Mosques and religious congregations form the spiritual and community infrastructure of American Muslim life. Evaluating them differs from evaluating service-oriented nonprofits — the ultimate 'output' is congregational life itself, which doesn't reduce to impact metrics. We focus on governance transparency, financial accountability, and whether programs serve members and neighbors alike.",
      "faq": [
        { "q": "Can I pay zakat to my local mosque?", "a": "It depends on how the mosque uses zakat funds. Mosques that earmark zakat for eligible recipients (the poor, travelers, converts) are zakat-eligible. Mosques that use zakat for operating expenses (utilities, mortgage, staff salaries) may not be — this is a matter of scholarly interpretation and specific program design." },
        { "q": "How does Good Measure Giving evaluate mosques differently from other charities?", "a": "We weight governance transparency and financial accountability more heavily than program-expense ratio, since the 'program' of a mosque is congregational life. We also look at whether the mosque publishes bylaws, financial statements, and board composition." },
        { "q": "What makes a mosque financially transparent?", "a": "Published annual financial reports, independent board oversight (not founder-controlled), disclosed executive compensation, and clear delineation between operating funds and zakat-earmarked funds." },
        { "q": "Why are some mosques not evaluated?", "a": "We prioritize registered 501(c)(3) organizations with publicly available Form 990 data. Smaller mosques or those operating under broader umbrellas may not appear in our directory yet." }
      ]
    },
    {
      "slug": "civil-rights-legal",
      "category": "CIVIL_RIGHTS_LEGAL",
      "displayName": "Civil Rights & Legal Advocacy",
      "intro": "Muslim civil-rights and legal-aid organizations defend individual Muslims and the broader community against discrimination, surveillance, and post-9/11 legal overreach. Their work is often preventive — measured in cases never filed, policies never enacted — which makes impact evaluation harder than for direct-service charities.",
      "faq": [
        { "q": "Is civil-rights work zakat-eligible?", "a": "Scholarly opinion varies. The majority view is that zakat funds should directly benefit eligible recipients (the 8 asnaf), and advocacy work often doesn't meet that standard. Sadaqah (voluntary charity) is universally appropriate for these organizations." },
        { "q": "How do you measure impact when the work is preventive?", "a": "We look at casework volume, policy wins, community trust signals (survey data when available), and organizational longevity. We're transparent when measurement is limited — a Data Confidence score reflects this." },
        { "q": "What's the difference between advocacy and civil-rights legal work?", "a": "Legal aid represents individuals in specific cases. Advocacy pursues policy change. Many organizations do both. Our evaluations call out which function is primary." },
        { "q": "How should I give to this category during Ramadan?", "a": "Sadaqah works any time and is often the better fit for civil-rights work. If you want to maximize zakat giving, pair a civil-rights sadaqah donation with a separate zakat donation to a zakat-eligible charity." }
      ]
    },
    {
      "slug": "medical-health",
      "category": "MEDICAL_HEALTH",
      "displayName": "Medical & Health Programs",
      "intro": "Muslim-led medical charities serve uninsured populations, run free clinics in underserved neighborhoods, and provide medical relief in conflict zones. This category attracts strong operational talent — many charities are staffed by volunteer physicians — and often scores well on program-expense ratio.",
      "faq": [
        { "q": "Is funding free clinics zakat-eligible?", "a": "Funding medical care for the poor who cannot afford it is zakat-eligible in most interpretations, because it supports the 'needy' asnaf. Some scholars extend this to medical equipment and facility costs when they directly enable free care; others restrict zakat to funds reaching individual patients." },
        { "q": "How do we evaluate medical charities differently?", "a": "We emphasize patient-outcome evidence when available, cost-per-patient-served, and the credentialing of medical providers. Flashy photos don't compensate for vague outcome data." },
        { "q": "What about medical relief in conflict zones?", "a": "Conflict-zone medical work gets a Data Confidence adjustment — audits are harder, so we rely more on photo-journalism documentation, third-party verification, and organizational track record." },
        { "q": "Are medical research organizations in this category?", "a": "Generally no — those are in Research & Policy. This category covers direct patient care and medical relief." }
      ]
    },
    {
      "slug": "philanthropy-grantmaking",
      "category": "PHILANTHROPY_GRANTMAKING",
      "displayName": "Philanthropy & Grantmaking",
      "intro": "Grantmaking foundations and donor-advised funds in the Muslim space pool donor dollars and distribute them to downstream implementers. They add a layer between donors and beneficiaries — sometimes bringing expertise and vetting, sometimes just adding overhead. Evaluation turns on whether the grantmaker improves what goes to the ultimate beneficiary.",
      "faq": [
        { "q": "Is giving to a foundation zakat-eligible?", "a": "Yes if the foundation passes the funds through to zakat-eligible recipients in a timely way. The key scholarly concern is delay — zakat should reach beneficiaries within a reasonable time. Foundations that hold funds as endowments for years may not qualify." },
        { "q": "Does adding a grantmaker layer reduce impact?", "a": "It depends. A skilled grantmaker with due-diligence capacity can route funds to higher-impact work than an individual donor could find alone. A thin grantmaker that just re-grants with high overhead reduces impact." },
        { "q": "How do you evaluate grantmakers?", "a": "Grant-to-overhead ratio, timeliness of disbursement, transparency of grantee lists, and whether grantmakers publish their evaluation methodology." },
        { "q": "Should I give through a foundation or directly to implementers?", "a": "Direct-to-implementer is simpler and has less overhead. A foundation adds value when you don't have capacity to evaluate implementers yourself and the foundation has genuine vetting expertise." }
      ]
    },
    {
      "slug": "education-international",
      "category": "EDUCATION_INTERNATIONAL",
      "displayName": "International Education",
      "intro": "Educational programs in Muslim-majority regions — from scholarship programs to school construction to teacher training. This category spans from tightly-run skill-building nonprofits to sprawling international-school networks. Long-horizon work with measurable but delayed outcomes.",
      "faq": [
        { "q": "Is education zakat-eligible?", "a": "Scholarly opinion varies. Education that enables the poor to earn a living (skill training, trades, basic literacy) is more broadly accepted as zakat-eligible than general-enrollment academic scholarships." },
        { "q": "How do we measure educational impact?", "a": "Enrollment and graduation are outputs, not outcomes. We look for evidence of employment, income, or continued education among graduates — and flag when this data isn't available." },
        { "q": "What's the difference between this and K-12 Religious?", "a": "K-12 Religious covers US-based Islamic schools. This category covers education programs outside the US, often in Muslim-majority countries." },
        { "q": "Are madrasas in this category?", "a": "International madrasas can be — the category is structural (geography) not curricular. Look at individual charity evaluations to understand what each program covers." }
      ]
    },
    {
      "slug": "research-policy",
      "category": "RESEARCH_POLICY",
      "displayName": "Research & Policy",
      "intro": "Research institutes, policy think tanks, and applied-research nonprofits serving the Muslim American community. Impact here is inherently indirect — influencing public discourse or policy frameworks — and is among the hardest to measure.",
      "faq": [
        { "q": "Is research-and-policy work zakat-eligible?", "a": "Generally no under the majority scholarly view, since funds don't reach individual beneficiaries directly. Sadaqah is the appropriate form of giving for this category." },
        { "q": "How do we evaluate research organizations?", "a": "Publication volume and citations, policy adoption when traceable, and whether research is peer-reviewed or self-published. We weight methodological transparency heavily." },
        { "q": "Why fund research at all?", "a": "Compounding impact — good research shapes downstream policy, public perception, and community self-understanding in ways direct service can't. The tradeoff is delayed and uncertain returns." },
        { "q": "How do you spot low-quality research?", "a": "No independent peer review, no raw data release, consistently conclusion-first analysis, and no external citation track record are warning signs." }
      ]
    },
    {
      "slug": "religious-outreach",
      "category": "RELIGIOUS_OUTREACH",
      "displayName": "Religious Outreach & Dawah",
      "intro": "Organizations whose primary program is teaching Islam to Muslims and non-Muslims — through media, seminaries, street dawah, and publishing. This category has historically grown fast and evaluated loosely; we apply extra scrutiny to governance and financial transparency.",
      "faq": [
        { "q": "Is dawah zakat-eligible?", "a": "Scholarly opinion is divided. A minority view includes dawah under 'fi sabilillah' (in the path of Allah), but the majority view restricts zakat to direct beneficiary support. Most scholars recommend giving to dawah organizations as sadaqah." },
        { "q": "How do we evaluate dawah organizations?", "a": "Governance transparency, founder-ownership structure, financial accountability, and whether content addresses topical community needs versus recycling generic material." },
        { "q": "What red flags are specific to this category?", "a": "Single-founder control without an independent board, undisclosed executive compensation, loans between the charity and the founder, and pronounced emphasis on personality-driven fundraising." },
        { "q": "Are seminaries in this category?", "a": "Yes — US-based Islamic seminaries training imams and scholars are here. International madrasas are in International Education." }
      ]
    },
    {
      "slug": "basic-needs",
      "category": "BASIC_NEEDS",
      "displayName": "Basic Needs",
      "intro": "Food pantries, homeless outreach, refugee resettlement support, and utility-bill assistance — direct-service charities meeting immediate needs. Historically the clearest-cut zakat-eligible category, with tight program-expense ratios and measurable beneficiary counts.",
      "faq": [
        { "q": "Are basic-needs charities zakat-eligible?", "a": "Yes — directly serving the poor and needy is the most universally-accepted zakat-eligible use of funds. This category has the broadest scholarly support." },
        { "q": "How are these different from humanitarian charities?", "a": "Basic-needs charities typically operate locally (US-based) with chronic-need populations. Humanitarian charities typically operate internationally in acute-crisis or conflict zones." },
        { "q": "What metrics matter most here?", "a": "Cost per family served, meals distributed, and emergency-assistance disbursement speed. Basic-needs work doesn't have complex impact theory — you fed a family or you didn't." },
        { "q": "Should I give cash or in-kind donations?", "a": "Cash is almost always more efficient. Organizations can buy at bulk rates and match purchases to actual need; in-kind donations often end up mismatched or wasted. Only give in-kind when the organization specifically requests it." }
      ]
    },
    {
      "slug": "education-higher-religious",
      "category": "EDUCATION_HIGHER_RELIGIOUS",
      "displayName": "Islamic Higher Education",
      "intro": "US-based Islamic colleges, universities, and graduate programs — including seminaries that grant accredited degrees. Younger institutions in a field with decades-long maturity timelines; expect mixed evaluation outcomes.",
      "faq": [
        { "q": "Is supporting Islamic higher education zakat-eligible?", "a": "Scholarly opinion is split. Scholarships for needy students are more clearly zakat-eligible than institutional support. Sadaqah is appropriate for general institutional giving." },
        { "q": "How do we evaluate these institutions?", "a": "Accreditation status, graduation rates, employment outcomes of graduates, financial stability, and governance transparency." },
        { "q": "What's the difference from International Education?", "a": "This category covers US-based religious higher education. International Education covers programs outside the US." },
        { "q": "Are these schools financially sustainable?", "a": "The category is still maturing — tuition + donations + endowments haven't stabilized into a consistent model. Expect to see institutional scores shift as the field develops." }
      ]
    },
    {
      "slug": "education-k12-religious",
      "category": "EDUCATION_K12_RELIGIOUS",
      "displayName": "Islamic K–12 Schools",
      "intro": "Full-time Islamic K–12 schools — typically combining standard academic curriculum with Arabic and Qur'anic studies. Community infrastructure that serves the Muslim-American family directly, evaluated on academic outcomes, financial sustainability, and governance.",
      "faq": [
        { "q": "Is tuition assistance zakat-eligible?", "a": "Assistance for families who cannot afford tuition is zakat-eligible in most interpretations. General institutional support is typically sadaqah." },
        { "q": "How do we evaluate Islamic K–12 schools?", "a": "Standardized test outcomes, teacher retention, financial health, board governance, and whether the school serves a broad community or only a select few." },
        { "q": "What about homeschool co-ops and part-time schools?", "a": "Part-time weekend Islamic programs and homeschool co-ops may fall under a different category depending on their legal structure. Look at the individual charity's rubric archetype." },
        { "q": "How does this category interact with financial aid?", "a": "Schools with strong, transparent financial-aid programs score higher on accessibility. Schools that quietly gate enrollment to affluent families score lower even if academic outcomes are strong." }
      ]
    },
    {
      "slug": "environment-climate",
      "category": "ENVIRONMENT_CLIMATE",
      "displayName": "Environment & Climate",
      "intro": "An emerging category — Muslim-led environmental and climate organizations are a small but growing field. Scholarly work on Islamic environmental ethics is well-established; organizational infrastructure is still being built.",
      "faq": [
        { "q": "Is climate work zakat-eligible?", "a": "Generally no under the majority scholarly view — environmental work is indirect and doesn't reach individual beneficiaries. Sadaqah is the appropriate form of giving." },
        { "q": "How do we evaluate climate organizations?", "a": "Concrete projects over conceptual advocacy, measurable carbon or ecosystem outcomes, and avoidance of greenwashing. Small-scale organizations with demonstrated project work score higher than large ones with vague messaging." },
        { "q": "Why is this a separate category?", "a": "Climate and environmental work has distinct evaluation criteria and distinct theological framing in the Islamic tradition. Rolling it into general advocacy would lose both." },
        { "q": "What's the relationship to humanitarian work?", "a": "Climate-caused humanitarian crises (drought, displacement) are addressed by humanitarian charities in the response phase. This category covers mitigation and advocacy, not disaster response." }
      ]
    },
    {
      "slug": "social-services",
      "category": "SOCIAL_SERVICES",
      "displayName": "Social Services",
      "intro": "Social workers, counselors, family support services, and case-management organizations serving Muslim Americans. This category sits between basic-needs direct service and religious-congregation community infrastructure, with evaluation rubrics drawn from both.",
      "faq": [
        { "q": "Are social services zakat-eligible?", "a": "Case-by-case. Services that directly benefit the poor and needy (emergency financial counseling for struggling families, for example) are more clearly zakat-eligible than general-community social services." },
        { "q": "How do we evaluate social-service organizations?", "a": "Caseload per staff member, outcome tracking, cultural competency (especially important for immigrant communities), and trauma-informed practices." },
        { "q": "What's the difference between this and Women's Services?", "a": "Women's Services is a specialized sub-category — organizations serving Muslim women specifically, including DV response, maternal health, and women's-only community spaces." },
        { "q": "Are mental-health programs in this category?", "a": "Yes, if the organization's primary mission is community mental health. Mental health programs inside a mosque would be in Religious Congregation." }
      ]
    },
    {
      "slug": "womens-services",
      "category": "WOMENS_SERVICES",
      "displayName": "Women's Services",
      "intro": "Organizations serving Muslim women specifically — domestic violence response, maternal and women's health, single-mother support, and women-only community programs. A smaller category where evaluation scrutiny is especially important because the work protects vulnerable people.",
      "faq": [
        { "q": "Is this category zakat-eligible?", "a": "Direct-support work (DV shelters, single-mother assistance) is broadly zakat-eligible. Advocacy-only work falls under civil-rights/advocacy scholarly framing." },
        { "q": "What makes a DV response organization strong?", "a": "24/7 hotline staffing, confidentiality protocols, trauma-informed services, cultural competency for Muslim clients, and documented partnership with legal and medical providers." },
        { "q": "How do we evaluate safety and trust?", "a": "We don't publish evaluations that could compromise client safety. Organizational governance and third-party audits matter more than our direct evaluation here." },
        { "q": "Why is this separated from Social Services?", "a": "The specialized nature of the work — and the specific community-trust requirements — warrant separate evaluation criteria." }
      ]
    },
    {
      "slug": "advocacy-civic",
      "category": "ADVOCACY_CIVIC",
      "displayName": "Advocacy & Civic Engagement",
      "intro": "Voter-registration drives, civic-engagement campaigns, and issue-advocacy organizations — often nonpartisan but politically engaged. A small category distinct from civil-rights work in that the focus is on participation rather than legal defense.",
      "faq": [
        { "q": "Is civic engagement zakat-eligible?", "a": "Generally no — these are not direct-beneficiary programs. Sadaqah is appropriate." },
        { "q": "How do we evaluate this category?", "a": "Voter-registration totals, turnout impact when measurable, and organizational nonpartisanship (or openly-stated political affiliation). We do not penalize political affiliation but expect transparency about it." },
        { "q": "Why separate this from Civil Rights & Legal?", "a": "Legal work defends individuals in specific cases. Advocacy pursues collective policy change. Civic engagement increases political participation. Related but evaluated differently." },
        { "q": "Are political action committees here?", "a": "No. PACs are not 501(c)(3) and don't appear in our directory. Only nonpartisan issue advocacy and civic-engagement 501(c)(3)s are here." }
      ]
    },
    {
      "slug": "media-journalism",
      "category": "MEDIA_JOURNALISM",
      "displayName": "Media & Journalism",
      "intro": "Muslim-American media outlets, investigative journalism nonprofits, and independent reporting organizations. A small but critical category — the quality of public discourse about Muslims depends heavily on who is reporting.",
      "faq": [
        { "q": "Is supporting journalism zakat-eligible?", "a": "Generally no, under majority scholarly opinion. Sadaqah is appropriate." },
        { "q": "How do we evaluate media organizations?", "a": "Editorial independence, publication frequency, topical relevance, fact-checking rigor, and whether the outlet is reporting original journalism or aggregating others' work." },
        { "q": "Why is this a separate category?", "a": "Media evaluation criteria (editorial standards, newsroom independence, reporting ethics) differ meaningfully from other nonprofit work." },
        { "q": "How do we handle potential conflicts of interest?", "a": "If a media organization depends on a single donor or has undisclosed political affiliations, we flag it. Editorial independence is the central criterion." }
      ]
    }
  ]
}
```

- [ ] **Step 2: Verify the JSON parses**

```bash
node -e "console.log(JSON.parse(require('fs').readFileSync('website/data/causes/causes.json','utf8')).causes.length)"
```
Expected: `16`

- [ ] **Step 3: Commit**

```bash
git add website/data/causes/causes.json
git commit -m "feat(seo): seed cause-area hub intros and FAQ"
```

---

## Task 4: CausePage React component

**Files:**
- Create: `website/pages/CausePage.tsx`

- [ ] **Step 1: Write the component**

```tsx
import React, { useEffect, useMemo } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { useCharities } from '../src/hooks/useCharities';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { slugToCategory, filterCharitiesByCategory, type HubCharity } from '../scripts/lib/cause-seo';
import causesData from '../data/causes/causes.json';

interface CauseData {
  slug: string;
  category: string;
  displayName: string;
  intro: string;
  faq: Array<{ q: string; a: string }>;
}

const CAUSES: CauseData[] = (causesData.causes as CauseData[]);

export const CausePage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { isDark } = useLandingTheme();
  const { summaries, loading } = useCharities();

  const cause = useMemo(() => CAUSES.find((c) => c.slug === slug), [slug]);

  useEffect(() => {
    if (cause) {
      document.title = `Best Muslim ${cause.displayName} Charities | Good Measure Giving`;
    }
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [cause]);

  if (!slug || !cause) {
    return <Navigate to="/causes" replace />;
  }

  const category = slugToCategory(slug);
  if (!category) return <Navigate to="/causes" replace />;

  const pool: HubCharity[] = (summaries ?? []).map((c) => ({
    ein: c.ein,
    name: c.name,
    primaryCategory: c.primaryCategory ?? null,
    amalScore: c.amalScore ?? null,
    walletTag: c.walletTag ?? null,
  }));

  const charities = filterCharitiesByCategory(pool, category);

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <Link to="/causes" className="hover:underline">Causes</Link>
          <span className="mx-2">/</span>
          <span>{cause.displayName}</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Best Muslim {cause.displayName} Charities</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">{cause.intro}</p>

        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-4">Evaluated Charities</h2>
          {loading ? (
            <div className="text-slate-500">Loading charities…</div>
          ) : charities.length === 0 ? (
            <div className="text-slate-500">No charities evaluated in this category yet.</div>
          ) : (
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {charities.map((c) => (
                <li key={c.ein}>
                  <Link
                    to={`/charity/${c.ein}`}
                    className="block p-4 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
                  >
                    <div className="font-medium">{c.name}</div>
                    {c.amalScore != null && (
                      <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        {c.amalScore}/100
                      </div>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Frequently Asked Questions</h2>
          <dl>
            {cause.faq.map((item, i) => (
              <div key={i} className="mb-6">
                <dt className="font-semibold text-slate-900 dark:text-slate-100">{item.q}</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Build to confirm TypeScript passes**

`cd website && npm run build 2>&1 | tail -10`
Expected: success. If `causesData.causes` type inference fails, ensure the JSON import works — Vite supports JSON imports natively. If `useLandingTheme` path differs, adjust to match what other pages use (check `FAQPage.tsx` or `AboutPage.tsx`).

- [ ] **Step 3: Commit**

```bash
git add website/pages/CausePage.tsx
git commit -m "feat(seo): add CausePage hub component"
```

---

## Task 5: CausesIndexPage React component

**Files:**
- Create: `website/pages/CausesIndexPage.tsx`

- [ ] **Step 1: Write the component**

```tsx
import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import causesData from '../data/causes/causes.json';

interface CauseData {
  slug: string;
  category: string;
  displayName: string;
  intro: string;
}

const CAUSES: CauseData[] = (causesData.causes as CauseData[]);

export const CausesIndexPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  useEffect(() => {
    document.title = 'Causes | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <span>Causes</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Browse Charities by Cause</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">
          Explore {CAUSES.length} cause areas in the Muslim charity ecosystem, each evaluated by Good Measure Giving on impact, alignment, and financial transparency.
        </p>

        <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {CAUSES.map((c) => (
            <li key={c.slug}>
              <Link
                to={`/causes/${c.slug}`}
                className="block p-5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
              >
                <h2 className="text-xl font-semibold mb-2">{c.displayName}</h2>
                <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-3">{c.intro}</p>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Build**

`cd website && npm run build 2>&1 | tail -5`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add website/pages/CausesIndexPage.tsx
git commit -m "feat(seo): add CausesIndexPage listing all hubs"
```

---

## Task 6: Wire routes in App.tsx

**Files:**
- Modify: `website/App.tsx`

- [ ] **Step 1: Add imports and routes**

Open `website/App.tsx`. Find the imports for other pages (e.g. `LandingPage`, `FAQPage`). Add alongside them:

```tsx
import { CausePage } from './pages/CausePage';
import { CausesIndexPage } from './pages/CausesIndexPage';
```

Find the `<Routes>` block. After the existing `/charity/:id` route and before the `*` catch-all `NotFoundPage` route, add:

```tsx
            <Route path="/causes" element={<CausesIndexPage />} />
            <Route path="/causes/:slug" element={<CausePage />} />
```

- [ ] **Step 2: Verify dev server mounts the routes**

```bash
(cd website && npm run dev -- --port 5183 > /tmp/vite-5183.log 2>&1 &)
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5183/causes
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5183/causes/humanitarian
pkill -f "vite.*5183"
```
Expected: both return `200`.

- [ ] **Step 3: Commit**

```bash
git add website/App.tsx
git commit -m "feat(seo): route /causes and /causes/:slug"
```

---

## Task 7: Prerender cause hub pages with schema

**Files:**
- Modify: `website/scripts/prerender.ts`

- [ ] **Step 1: Add imports and types at the top of `prerender.ts`**

Alongside existing imports from `./lib/charity-seo`, add:

```typescript
import { filterCharitiesByCategory, type HubCharity } from './lib/cause-seo';
```

Near existing `PromptSummary` / `PromptsIndex` interfaces (around lines 55–65), add:

```typescript
interface CauseEntry {
  slug: string;
  category: string;
  displayName: string;
  intro: string;
  faq: Array<{ q: string; a: string }>;
}

interface CausesIndex {
  causes: CauseEntry[];
}
```

- [ ] **Step 2: Add `buildCausesIndexMeta` and `buildCauseMeta` helpers**

After the existing `buildPromptMeta` function, append:

```typescript
function buildCausesIndexMeta(causes: CauseEntry[]): PageMeta {
  return {
    route: '/causes',
    title: 'Browse Charities by Cause | Good Measure Giving',
    description: `Explore ${causes.length} cause areas in the Muslim charity ecosystem. Humanitarian relief, masjids, civil rights, medical programs, education, and more — each evaluated on impact, alignment, and transparency.`,
    canonical: `${SITE_URL}/causes`,
    ogType: 'website',
    jsonLd: [
      {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: 'Causes',
        url: `${SITE_URL}/causes`,
        description: 'Cause-area hubs covering the Muslim charity ecosystem.',
      },
      buildBreadcrumbSchema([
        { name: 'Home', url: `${SITE_URL}/` },
        { name: 'Causes', url: `${SITE_URL}/causes` },
      ]) as object,
    ],
  };
}

function buildCauseMeta(cause: CauseEntry, allCharities: HubCharity[]): PageMeta {
  const charities = filterCharitiesByCategory(allCharities, cause.category);
  const title = `Best Muslim ${cause.displayName} Charities | Good Measure Giving`;
  const description = truncate(
    `${cause.intro} ${charities.length} evaluated charities.`,
    160
  );

  const collectionPage = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: `Best Muslim ${cause.displayName} Charities`,
    url: `${SITE_URL}/causes/${cause.slug}`,
    description: cause.intro,
    mainEntity: {
      '@type': 'ItemList',
      numberOfItems: charities.length,
      itemListElement: charities.map((c, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        url: `${SITE_URL}/charity/${c.ein}`,
        name: c.name,
      })),
    },
  };

  const faqPairs = cause.faq.map((item) => ({ question: item.q, answer: item.a }));
  const faqPage = buildFaqPageSchema(faqPairs);

  const breadcrumbs = buildBreadcrumbSchema([
    { name: 'Home', url: `${SITE_URL}/` },
    { name: 'Causes', url: `${SITE_URL}/causes` },
    { name: cause.displayName, url: `${SITE_URL}/causes/${cause.slug}` },
  ]);

  const schemaBlocks: object[] = [collectionPage];
  if (faqPage) schemaBlocks.push(faqPage);
  if (breadcrumbs) schemaBlocks.push(breadcrumbs);

  return {
    route: `/causes/${cause.slug}`,
    title,
    description,
    canonical: `${SITE_URL}/causes/${cause.slug}`,
    ogType: 'website',
    jsonLd: schemaBlocks,
  };
}
```

- [ ] **Step 3: Load causes and push metas in `prerenderPages`**

Inside `prerenderPages`, AFTER the prompt-loading block, add:

```typescript
  // Load cause-area hubs
  const CAUSES_PATH = path.join(__dirname, '../data/causes/causes.json');
  let causes: CauseEntry[] = [];
  if (fs.existsSync(CAUSES_PATH)) {
    const causesIndex: CausesIndex = JSON.parse(fs.readFileSync(CAUSES_PATH, 'utf-8'));
    causes = causesIndex.causes || [];
  }

  // Build the HubCharity pool for cause filtering
  const hubPool: HubCharity[] = charities.map((c) => ({
    ein: c.ein,
    name: c.name,
    primaryCategory: (c as unknown as { primaryCategory?: string | null }).primaryCategory ?? null,
    amalScore: c.amal_score ?? null,
    walletTag: c.wallet_tag ?? null,
  }));

  if (causes.length > 0) {
    metas.push(buildCausesIndexMeta(causes));
    for (const cause of causes) {
      metas.push(buildCauseMeta(cause, hubPool));
    }
  }
```

Update the `Prerender:` log line to include `causes.length`:

```typescript
  console.log(`Prerender: ${metas.length} pages (${metas.length - charities.length - prompts.length - (causes.length ? causes.length + 1 : 0)} static + ${charities.length} charities + ${prompts.length} prompts + ${causes.length ? causes.length + 1 : 0} causes)`);
```

- [ ] **Step 4: Note on the `CharitySummary` interface**

The existing `CharitySummary` interface inside `prerender.ts` (around line 33) doesn't include `primaryCategory`. Extend it:

Find:
```typescript
interface CharitySummary {
  ein: string;
  name: string;
  amal_score: number | null;
  wallet_tag: string | null;
}
```

Replace with:
```typescript
interface CharitySummary {
  ein: string;
  name: string;
  amal_score: number | null;
  wallet_tag: string | null;
  primaryCategory?: string | null;
}
```

(The `primaryCategory` field is already in the exported charities JSON for the frontend; the build just needs the type to include it.)

- [ ] **Step 5: Build and verify**

`cd website && npm run build 2>&1 | tee /tmp/t7-build.log | tail -15`
Expected: log line shows `X static + Y charities + Z prompts + 17 causes`.

```bash
ls website/dist/causes/
ls website/dist/causes/humanitarian/
grep -o '"@type":"CollectionPage"\|"@type":"FAQPage"\|"@type":"BreadcrumbList"\|"@type":"ItemList"' website/dist/causes/humanitarian/index.html | sort -u
```
Expected: all 4 schema types present on humanitarian hub.

- [ ] **Step 6: Commit**

```bash
git add website/scripts/prerender.ts
git commit -m "feat(seo): prerender /causes and /causes/:slug pages with schema"
```

---

## Task 8: Add cause URLs to sitemap

**Files:**
- Modify: `website/scripts/generateSitemap.ts`

- [ ] **Step 1: Extend the sitemap generator**

Open `website/scripts/generateSitemap.ts`. Near the `PROMPTS_INDEX` constant, add:

```typescript
const CAUSES_JSON = path.join(__dirname, '../data/causes/causes.json');
```

Near the existing interfaces, add:

```typescript
interface CauseEntry {
  slug: string;
}
```

After the existing prompt-URL block in `generateSitemap()`, add:

```typescript
  // Cause hub pages
  let causes: CauseEntry[] = [];
  if (fs.existsSync(CAUSES_JSON)) {
    const causesData = JSON.parse(fs.readFileSync(CAUSES_JSON, 'utf-8'));
    causes = causesData.causes || [];
  }
  if (causes.length > 0) {
    urls.push(`  <url>
    <loc>${SITE_URL}/causes</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
    for (const cause of causes) {
      urls.push(`  <url>
    <loc>${SITE_URL}/causes/${cause.slug}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
    }
  }
```

Update the `Sitemap:` log line:
```typescript
  console.log(`Sitemap: ${urls.length} URLs (${staticPages.length} static + ${charities.length} charities + ${prompts.length} prompts + ${causes.length ? causes.length + 1 : 0} causes)`);
```

- [ ] **Step 2: Build and verify**

`cd website && npm run build 2>&1 | tail -5`
Expected: sitemap log shows `+ 17 causes`.

```bash
grep -c '/causes' website/dist/sitemap.xml
```
Expected: 17 (1 index + 16 hubs).

- [ ] **Step 3: Commit**

```bash
git add website/scripts/generateSitemap.ts
git commit -m "feat(seo): add cause hub URLs to sitemap"
```

---

## Task 9: Add "Browse more in [cause]" link to charity pages

**Files:**
- Modify: `website/pages/CharityDetailsPage.tsx`

- [ ] **Step 1: Add import**

Alongside the other imports:
```tsx
import { categoryToSlug } from '../scripts/lib/cause-seo';
```

- [ ] **Step 2: Render the link in the "Similar Charities" area**

The `SimilarCharities` component already renders at the bottom of the page. Just before it (or immediately after, your call), add a small "Browse more in [cause]" link that derives from the charity's `primaryCategory`.

Find the existing block:
```tsx
        {/* Similar charities — visible to all users and crawlers */}
        {charity && (
          <SimilarCharities ... />
        )}
```

Replace with:

```tsx
        {/* Similar charities — visible to all users and crawlers */}
        {charity && (
          <SimilarCharities
            currentEin={charity.ein}
            category={charity.primaryCategory ?? charity.category ?? ''}
            zakatStatus={classifyZakatStatus({
              walletTag: charity.amalEvaluation?.wallet_tag ?? null,
              zakatClassification: charity.amalEvaluation?.zakat_classification ?? null,
            })}
            limit={4}
          />
        )}
        {charity?.primaryCategory && categoryToSlug(charity.primaryCategory) && (
          <div className="mt-6">
            <Link
              to={`/causes/${categoryToSlug(charity.primaryCategory)}`}
              className="inline-flex items-center text-sm font-medium text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
            >
              Browse more charities in this cause →
            </Link>
          </div>
        )}
```

If `Link` isn't already imported from `react-router-dom` at the top of the file, add it: check imports and confirm.

- [ ] **Step 3: Build**

`cd website && npm run build 2>&1 | tail -5`
Expected: success.

- [ ] **Step 4: Commit**

```bash
git add website/pages/CharityDetailsPage.tsx
git commit -m "feat(seo): link charity pages to their cause hub"
```

---

## Task 10: Extend E2E test for cause hubs

**Files:**
- Modify: `website/tests/e2e/seo-schema.spec.ts`

- [ ] **Step 1: Append tests**

Insert before the closing `});` of the existing `test.describe` block:

```typescript
  test('/causes index has CollectionPage and BreadcrumbList schemas', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'causes', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('CollectionPage');
    expect(types).toContain('BreadcrumbList');
  });

  test('/causes/humanitarian has CollectionPage, FAQPage, and BreadcrumbList schemas', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'causes', 'humanitarian', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('CollectionPage');
    expect(types).toContain('FAQPage');
    expect(types).toContain('BreadcrumbList');
  });

  test('sitemap includes /causes URLs', () => {
    const xml = fs.readFileSync(path.join(DIST_DIR, 'sitemap.xml'), 'utf-8');
    expect(xml).toMatch(/\/causes\//);
  });
```

- [ ] **Step 2: Build and run**

```bash
cd website && npm run build 2>&1 | tail -3
npx playwright test tests/e2e/seo-schema.spec.ts --project=chromium 2>&1 | tail -10
```
Expected: 11 tests pass (8 existing + 3 new).

- [ ] **Step 3: Commit**

```bash
git add website/tests/e2e/seo-schema.spec.ts
git commit -m "test(seo): add cause-hub schema verification"
```

---

## Task 11: Rich Results validation (manual)

**Files:** none.

- [ ] **Step 1: Deploy to preview**

Per `website/DEPLOYMENT.md`.

- [ ] **Step 2: Validate a sample hub**

Paste `<preview-url>/causes/humanitarian` into https://search.google.com/test/rich-results.
Expected: CollectionPage detected, FAQ detected, Breadcrumbs detected, 0 errors.

Paste `<preview-url>/causes/civil-rights-legal` too — different FAQ content, confirm 0 errors.

- [ ] **Step 3: Confirm `/causes` index isn't a thin-content risk**

Paste `<preview-url>/causes` into Rich Results Test. The index has a short intro + 16 card-links + 2 schema blocks. No FAQ on the index. Should pass with 0 errors.

- [ ] **Step 4: Submit the updated sitemap to Search Console**

Resubmit `sitemap.xml` in Search Console; spot-check 1–2 cause hubs with URL Inspection.

- [ ] **Step 5: No commit — validation only**

---

## Acceptance criteria

When every task above is checked off:

1. `website/scripts/lib/cause-seo.ts` exports `categoryToSlug`, `slugToCategory`, `CAUSE_SLUGS`, `filterCharitiesByCategory`, `HubCharity`. All pure, unit-tested (≥8 tests).
2. `website/data/causes/causes.json` contains 16 entries, each with unique intro and FAQ (not templated).
3. `/causes` and `/causes/:slug` routes mount via React Router; dev server serves them.
4. Build generates `website/dist/causes/index.html` + 16 `website/dist/causes/<slug>/index.html` pages with correct schema.
5. Sitemap includes 17 cause URLs (index + 16 hubs).
6. Charity detail pages link to their cause hub.
7. E2E spec passes 11 scenarios.
8. Rich Results Test validates 0 errors on sample hubs.

## Out of scope for this plan

- Cause-intent taxonomy (e.g., `/causes/orphan-support`) — current plan uses MECE categories. A separate cause-intent layer could be added later by augmenting charity data with cause-intent tags.
- LLM-generated intro/FAQ updates — intros are authored once and committed; iteration happens via direct edits to `causes.json`.
- Filter/sort UI on hub pages — charities are sorted by score desc by default; filtering is out of scope (users can use `/browse` for that).
- Related editorial guides from hubs — will be added in Track 3.
- Hub-page traffic analytics dashboards — will be handled via existing GA4/Cloudflare analytics.

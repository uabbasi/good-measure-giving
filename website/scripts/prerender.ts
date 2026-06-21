/**
 * Prerender Script
 * Uses SSR (via dist-server/entry-server.js) to render SPA pages and inject SEO meta/OG/JSON-LD tags.
 * Writes prerendered HTML to dist/ for search engine crawlers.
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { FAQ_ITEMS } from '../src/data/faq';
import { buildFaqPageSchema, buildArticleSchema, buildOrganizationSchema, buildBreadcrumbSchema } from './lib/schema';
import {
  classifyZakatStatus,
  buildCharityTitle,
  buildCharityDescription,
  buildCharityFaqPairs,
  type ZakatStatus,
} from './lib/charity-seo';
import { filterCharitiesByCategory, type HubCharity } from './lib/cause-seo';
import type { Guide, GuideSummary, GuidesIndex } from './lib/guide-seo';
import { KNOWN_ASSET_SLUGS } from './lib/calculator-seo';
import { buildCharitiesIndex } from '../src/hooks/useCharities';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DIST_DIR = path.join(__dirname, '../dist');
const DATA_DIR = path.join(__dirname, '../data/charities');
// Full charity index, rebuilt from detail files by convertData.ts at prebuild.
// (NOT data/charities/charities.json — that was a stale pilot-era subset.)
const CHARITIES_JSON = path.join(__dirname, '../data/charities.json');
const SITE_URL = 'https://goodmeasuregiving.org';

// ── Types ──────────────────────────────────────────────────────────────

export type SeedEntry = { queryKey: unknown[]; data: unknown };

interface CharitySummary {
  ein: string;
  name: string;
  amal_score: number | null;
  wallet_tag: string | null;
  primaryCategory?: string | null;
  hideFromCurated?: boolean;
}

interface CharityDetail {
  ein: string;
  name: string;
  mission?: string;
  website?: string;
  location?: { address?: string; city?: string; state?: string; zip?: string };
  evaluationTrack?: string;
  amalEvaluation?: {
    amal_score?: number;
    wallet_tag?: string;
    baseline_narrative?: { headline?: string };
    rich_narrative?: { headline?: string };
  };
}

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

const PROMPT_CATEGORY_LABELS: Record<string, string> = {
  quality_validation: 'Validate Charity Data Quality',
  data_extraction: 'Extract Charity Data',
  narrative_generation: 'Generate Charity Narratives',
  category_calibration: 'Calibrate Charity Categories',
};

interface PageMeta {
  route: string;
  title: string;
  description: string;
  canonical: string;
  ogType: string;
  jsonLd?: object | object[];
  noindex?: boolean;
}

// ── SSR route classification ───────────────────────────────────────────

export const SSR_ROUTE_PREFIXES = ['/charity/', '/guides/', '/causes/', '/zakat-calculator/', '/prompts/'];
export const SSR_EXACT_ROUTES = new Set(['/guides', '/causes', '/zakat-calculator', '/prompts', '/methodology', '/about', '/faq']);

export function isSsrRoute(route: string): boolean {
  if (SSR_EXACT_ROUTES.has(route)) return true;
  return SSR_ROUTE_PREFIXES.some((p) => route.startsWith(p));
}

function seedFor(route: string, ctx: {
  charityDetails: Map<string, unknown>;
  guidesIndex: unknown;
  guideBySlug: Map<string, unknown>;
  calculatorData: unknown;
  promptsIndex: unknown;
  promptById: Map<string, unknown>;
  charitiesIndexResult: unknown;
}): SeedEntry[] {
  if (route.startsWith('/charity/')) {
    const ein = route.slice('/charity/'.length);
    const d = ctx.charityDetails.get(ein);
    return d ? [{ queryKey: ['charity', ein], data: d }] : [];
  }
  if (route === '/causes' || route.startsWith('/causes/')) {
    return ctx.charitiesIndexResult ? [{ queryKey: ['charities'], data: ctx.charitiesIndexResult }] : [];
  }
  if (route === '/guides') return ctx.guidesIndex ? [{ queryKey: ['guides'], data: ctx.guidesIndex }] : [];
  if (route.startsWith('/guides/')) {
    const slug = route.slice('/guides/'.length);
    const g = ctx.guideBySlug.get(slug);
    return g ? [{ queryKey: ['guide', slug], data: g }] : [];
  }
  if (route.startsWith('/zakat-calculator')) return ctx.calculatorData ? [{ queryKey: ['calculator-data'], data: ctx.calculatorData }] : [];
  if (route === '/prompts') return ctx.promptsIndex ? [{ queryKey: ['prompts'], data: ctx.promptsIndex }] : [];
  if (route.startsWith('/prompts/')) {
    const id = route.slice('/prompts/'.length);
    const p = ctx.promptById.get(id);
    return p ? [{ queryKey: ['prompt', id], data: p }] : [];
  }
  return [];
}

// ── Meta builders ──────────────────────────────────────────────────────

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 1) + '…';
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function buildStaticMeta(): PageMeta[] {
  return [
    {
      route: '/',
      title: 'Good Measure Giving | Muslim Charity Evaluator',
      description:
        'Evidence-based evaluations of Muslim charities. Compare whether charities publicly say they accept zakat, along with impact scores and financial transparency across 160+ organizations.',
      canonical: `${SITE_URL}/`,
      ogType: 'website',
    },
    {
      route: '/browse',
      title: 'Browse Charities | Good Measure Giving',
      description:
        'Explore evaluated Muslim charities. Filter by whether they publicly say they accept zakat, impact score, cause area, and financial transparency.',
      canonical: `${SITE_URL}/browse`,
      ogType: 'website',
    },
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
  ];
}

function buildCharityMeta(detail: CharityDetail): PageMeta {
  const amal = detail.amalEvaluation;
  const name = detail.name;
  const score = amal?.amal_score;
  const walletTag = amal?.wallet_tag?.replace(/-/g, ' ').toLowerCase() || '';
  const isNewOrg = detail.evaluationTrack === 'NEW_ORG';
  const headline =
    amal?.rich_narrative?.headline ||
    amal?.baseline_narrative?.headline ||
    detail.mission ||
    '';

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

  const jsonLd: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'NonprofitOrganization',
    name,
    description: truncate(detail.mission || headline || name, 250),
    taxID: detail.ein,
  };

  if (detail.website) {
    jsonLd.url = detail.website;
  }

  if (detail.location) {
    const loc = detail.location;
    jsonLd.address = {
      '@type': 'PostalAddress',
      streetAddress: loc.address,
      addressLocality: loc.city,
      addressRegion: loc.state,
      postalCode: loc.zip,
      addressCountry: 'US',
    };
  }

  if (score != null) {
    // Single editorial rating from one named evaluator — that's a Review, not
    // an AggregateRating. AggregateRating with ratingCount:1 gets flagged or
    // suppressed by Google as a bad-shape markup.
    jsonLd.review = {
      '@type': 'Review',
      author: { '@type': 'Organization', name: 'Good Measure Giving' },
      reviewRating: {
        '@type': 'Rating',
        ratingValue: score,
        bestRating: 100,
        worstRating: 0,
      },
    };
  }

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
}

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

// ── HTML injection ─────────────────────────────────────────────────────

function injectMeta(html: string, meta: PageMeta): string {
  // Replace <title>
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${escapeHtml(meta.title)}</title>`);

  // Replace or inject meta description
  if (html.includes('name="description"')) {
    html = html.replace(
      /<meta\s+name="description"\s+content="[^"]*"\s*\/?>/,
      `<meta name="description" content="${escapeHtml(meta.description)}" />`
    );
  } else {
    html = html.replace('</title>', `</title>\n    <meta name="description" content="${escapeHtml(meta.description)}" />`);
  }

  // Normalize to trailing-slash form. The host (Cloudflare Pages) serves
  // prerendered pages at the slash URL with 200 and 307-redirects the no-slash
  // URL to it. Emitting no-slash canonicals made Google report "Page with
  // redirect" (sitemap URL redirects) and reject the canonical (it points at a
  // redirect), so nothing but the homepage got indexed.
  const canonicalUrl = meta.canonical.endsWith('/') ? meta.canonical : `${meta.canonical}/`;

  // Replace canonical
  if (html.includes('rel="canonical"')) {
    html = html.replace(
      /<link\s+rel="canonical"\s+href="[^"]*"\s*\/?>/,
      `<link rel="canonical" href="${canonicalUrl}" />`
    );
  } else {
    html = html.replace('</title>', `</title>\n    <link rel="canonical" href="${canonicalUrl}" />`);
  }

  // Robots directive — emit noindex,nofollow when flagged; otherwise default (index,follow implicit)
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

  // Replace OG tags
  const ogTags = [
    `<meta property="og:title" content="${escapeHtml(meta.title)}" />`,
    `<meta property="og:description" content="${escapeHtml(meta.description)}" />`,
    `<meta property="og:type" content="${meta.ogType}" />`,
    `<meta property="og:url" content="${canonicalUrl}" />`,
    `<meta property="og:site_name" content="Good Measure Giving" />`,
  ].join('\n    ');

  // Remove existing OG tags and re-inject
  html = html.replace(/<meta\s+property="og:[^"]*"\s+content="[^"]*"\s*\/?>\n?\s*/g, '');

  // Inject JSON-LD — support single object or array of schema blocks.
  // Escape `</` to prevent any string value containing "</script>" from
  // terminating the injected tag. Standard pattern used by Next.js/Gatsby.
  let jsonLdTag = '';
  if (meta.jsonLd) {
    const blocks = Array.isArray(meta.jsonLd) ? meta.jsonLd : [meta.jsonLd];
    jsonLdTag = blocks
      .map((block) => {
        const payload = JSON.stringify(block).replace(/<\//g, '\\u003c/');
        return `\n    <script type="application/ld+json">${payload}</script>`;
      })
      .join('');
  }

  // Insert all SEO tags before </head>
  html = html.replace('</head>', `    ${ogTags}${jsonLdTag}\n  </head>`);

  return html;
}

// ── Redirect writer ────────────────────────────────────────────────────

function writeRedirects(metas: PageMeta[]): number {
  // Cloudflare Pages auto-redirects the no-slash URL to its trailing-slash form
  // with a 307 (temporary), which leaves the no-slash URL "indexable" and made
  // Google report redirect issues. Emit an explicit 308 (permanent) per route so
  // search engines consolidate to the canonical slash URL. _redirects rules take
  // precedence over the automatic behavior. Exact-match rules (not a /* splat)
  // avoid the loop that would occur from re-matching the already-slashed target.
  const routes = Array.from(
    new Set(metas.map((m) => m.route).filter((route) => route !== '/' && !route.endsWith('/')))
  );
  const rules = routes.map((route) => `${route} ${route}/ 308`);
  fs.writeFileSync(path.join(DIST_DIR, '_redirects'), rules.join('\n') + '\n', 'utf-8');
  return rules.length;
}

// ── Prerender orchestration ────────────────────────────────────────────

async function prerenderPages() {
  // Load charity data — curated only; hidden charities get no static page
  const charitiesIndex = JSON.parse(fs.readFileSync(CHARITIES_JSON, 'utf-8'));
  const charities: CharitySummary[] = (charitiesIndex.charities || []).filter(
    (c: CharitySummary) => !c.hideFromCurated
  );

  // Build meta for all pages
  const metas: PageMeta[] = [...buildStaticMeta()];

  // Populate charity detail map for SSR seed
  const charityDetails = new Map<string, unknown>();

  for (const charity of charities) {
    const detailPath = path.join(DATA_DIR, `charity-${charity.ein}.json`);
    if (fs.existsSync(detailPath)) {
      const detail: CharityDetail = JSON.parse(fs.readFileSync(detailPath, 'utf-8'));
      charityDetails.set(detail.ein, detail);
      metas.push(buildCharityMeta(detail));
    } else {
      // Minimal meta from index data
      metas.push({
        route: `/charity/${charity.ein}`,
        title: `${charity.name} | Good Measure Giving`,
        description: truncate(
          `${charity.name}: ${charity.amal_score ?? 'N/A'}/100. ${(charity.wallet_tag || '').replace(/-/g, ' ').toLowerCase()}`,
          160
        ),
        canonical: `${SITE_URL}/charity/${charity.ein}`,
        ogType: 'article',
      });
    }
  }

  // Load prompt index — only active prompts get indexed; planned prompts
  // render as stubs on the SPA side and would look thin to crawlers.
  const PROMPTS_INDEX_PATH = path.join(__dirname, '../public/data/prompts/index.json');
  let prompts: PromptSummary[] = [];
  let promptsIndexObj: unknown = null;
  if (fs.existsSync(PROMPTS_INDEX_PATH)) {
    const promptsIndex: PromptsIndex = JSON.parse(fs.readFileSync(PROMPTS_INDEX_PATH, 'utf-8'));
    prompts = (promptsIndex.prompts || []).filter((p) => p.status !== 'planned');
    promptsIndexObj = promptsIndex;
  }

  for (const prompt of prompts) {
    metas.push(buildPromptMeta(prompt));
  }

  // Load full prompt JSONs for SSR seed
  const promptById = new Map<string, unknown>();
  const PROMPTS_DATA_DIR = path.join(__dirname, '../public/data/prompts');
  for (const prompt of prompts) {
    const promptPath = path.join(PROMPTS_DATA_DIR, `${prompt.id}.json`);
    if (fs.existsSync(promptPath)) {
      promptById.set(prompt.id, JSON.parse(fs.readFileSync(promptPath, 'utf-8')));
    }
  }

  // Load cause-area hubs
  const CAUSES_PATH = path.join(__dirname, '../data/causes/causes.json');
  let causes: CauseEntry[] = [];
  if (fs.existsSync(CAUSES_PATH)) {
    const causesIndex: CausesIndex = JSON.parse(fs.readFileSync(CAUSES_PATH, 'utf-8'));
    causes = causesIndex.causes || [];
  }

  // Build HubCharity pool for cause filtering (reads primaryCategory from charity summary)
  const hubPool: HubCharity[] = charities.map((c) => ({
    ein: c.ein,
    name: c.name,
    primaryCategory: c.primaryCategory ?? null,
    amalScore: c.amal_score ?? null,
    walletTag: c.wallet_tag ?? null,
  }));

  if (causes.length > 0) {
    metas.push(buildCausesIndexMeta(causes));
    for (const cause of causes) {
      metas.push(buildCauseMeta(cause, hubPool));
    }
  }

  // Load guides
  const GUIDES_DIR = path.join(__dirname, '../data/guides');
  const GUIDES_INDEX_PATH = path.join(GUIDES_DIR, 'guides.json');
  let guideSummaries: GuideSummary[] = [];
  const guides: Guide[] = [];
  let guidesIndexObj: unknown = null;
  const guideBySlug = new Map<string, unknown>();

  if (fs.existsSync(GUIDES_INDEX_PATH)) {
    const index: GuidesIndex = JSON.parse(fs.readFileSync(GUIDES_INDEX_PATH, 'utf-8'));
    guidesIndexObj = index;
    // pending-review guides get no static page until they clear review
    guideSummaries = (index.guides || []).filter((g) => g.status !== 'pending-review');
    for (const summary of guideSummaries) {
      const guidePath = path.join(GUIDES_DIR, `${summary.slug}.json`);
      if (fs.existsSync(guidePath)) {
        const guide: Guide = JSON.parse(fs.readFileSync(guidePath, 'utf-8'));
        guides.push(guide);
        guideBySlug.set(guide.slug, guide);
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

  const causeCount = causes.length > 0 ? causes.length + 1 : 0;
  const guideCount = guideSummaries.length > 0 ? guideSummaries.length + 1 : 0;
  const calculatorCount = calculatorData ? 1 + calculatorData.assets.length : 0;
  console.log(`Prerender: ${metas.length} pages (${metas.length - charities.length - prompts.length - causeCount - guideCount - calculatorCount} static + ${charities.length} charities + ${prompts.length} prompts + ${causeCount} causes + ${guideCount} guides + ${calculatorCount} calculator)`);

  const redirectCount = writeRedirects(metas);
  console.log(`Wrote ${redirectCount} trailing-slash 308 redirects to dist/_redirects`);

  // SSR rendering loop
  const { render } = await import(path.join(DIST_DIR, '../dist-server/entry-server.js'));
  const baseHtml = fs.readFileSync(path.join(DIST_DIR, 'index.html'), 'utf-8');

  const charitiesIndexResult = buildCharitiesIndex(charitiesIndex);

  const ctx = {
    charityDetails,
    guidesIndex: guidesIndexObj,
    guideBySlug,
    calculatorData,
    promptsIndex: prompts.length > 0 ? promptsIndexObj : null,
    promptById,
    charitiesIndexResult,
  };

  let written = 0;
  for (const meta of metas) {
    let html = injectMeta(baseHtml, meta);
    if (isSsrRoute(meta.route)) {
      try {
        const body = await render(meta.route, seedFor(meta.route, ctx));
        html = html.replace('<div id="root"></div>', `<div id="root">${body}</div>`);
      } catch (err) {
        console.warn(`  SSR failed for ${meta.route}; writing meta-only shell:`, (err as Error).message);
      }
    }
    const outDir = path.join(DIST_DIR, meta.route === '/' ? '' : meta.route);
    fs.mkdirSync(outDir, { recursive: true });
    const outFile = meta.route === '/' ? path.join(DIST_DIR, 'index.html') : path.join(outDir, 'index.html');
    fs.writeFileSync(outFile, html, 'utf-8');
    written++;
  }
  console.log(`Prerender complete: ${written} pages written to dist/`);
}

// Only run when executed directly (not when imported by tests)
if (process.env.VITEST == null) {
  prerenderPages().catch((err) => {
    console.error('Prerender failed:', err);
    process.exit(1);
  });
}

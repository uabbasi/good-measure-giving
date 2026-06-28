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
// Full charity index, rebuilt from detail files by convertData.ts at prebuild.
// (NOT data/charities/charities.json — that was a stale pilot-era subset.)
const CHARITIES_JSON = path.join(__dirname, '../data/charities.json');
const PROMPTS_INDEX = path.join(__dirname, '../public/data/prompts/index.json');
const CAUSES_JSON = path.join(__dirname, '../data/causes/causes.json');
const GUIDES_INDEX = path.join(__dirname, '../data/guides/guides.json');
const CALCULATOR_JSON = path.join(__dirname, '../data/zakat-calculator/assets.json');
const SITE_URL = 'https://goodmeasuregiving.org';

interface CharitySummary {
  ein: string;
  hideFromCurated?: boolean;
}

interface PromptSummary {
  id: string;
  status?: 'active' | 'planned';
}

interface CauseEntry {
  slug: string;
}

interface GuideSummary {
  slug: string;
  status?: 'published' | 'pending-review';
}

interface CalculatorAsset {
  slug: string;
}

interface CalculatorData {
  assets: CalculatorAsset[];
}

function generateSitemap() {
  const today = new Date().toISOString().split('T')[0];

  // Emit trailing-slash URLs to match what the host serves with 200. The
  // no-slash form 307-redirects to the slash form, so no-slash sitemap entries
  // were reported by Google as "Page with redirect" and never indexed.
  const loc = (p: string) => {
    const u = `${SITE_URL}${p}`;
    return u.endsWith('/') ? u : `${u}/`;
  };

  const staticPages = [
    { path: '/', priority: '1.0', changefreq: 'weekly' },
    { path: '/browse', priority: '0.9', changefreq: 'weekly' },
    { path: '/best-muslim-charities-in-usa', priority: '0.9', changefreq: 'weekly' },
    { path: '/methodology', priority: '0.7', changefreq: 'monthly' },
    { path: '/link-to-us', priority: '0.6', changefreq: 'monthly' },
    { path: '/about', priority: '0.6', changefreq: 'monthly' },
    { path: '/faq', priority: '0.6', changefreq: 'monthly' },
    { path: '/prompts', priority: '0.7', changefreq: 'monthly' },
  ];

  const urls = staticPages.map(
    (p) => `  <url>
    <loc>${loc(p.path)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>${p.changefreq}</changefreq>
    <priority>${p.priority}</priority>
  </url>`
  );

  // Charity pages — curated only; hidden charities stay out of the index
  const charityData = JSON.parse(fs.readFileSync(CHARITIES_JSON, 'utf-8'));
  const charities: CharitySummary[] = (charityData.charities || []).filter(
    (c: CharitySummary) => !c.hideFromCurated
  );
  for (const charity of charities) {
    urls.push(`  <url>
    <loc>${loc(`/charity/${charity.ein}`)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
  }

  // Prompt pages — only active prompts are indexed (planned ones are stubs).
  let prompts: PromptSummary[] = [];
  if (fs.existsSync(PROMPTS_INDEX)) {
    const promptsData = JSON.parse(fs.readFileSync(PROMPTS_INDEX, 'utf-8'));
    prompts = (promptsData.prompts || []).filter((p: PromptSummary) => p.status !== 'planned');
  }
  for (const prompt of prompts) {
    urls.push(`  <url>
    <loc>${loc(`/prompts/${prompt.id}`)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>`);
  }

  // Cause hub pages
  let causes: CauseEntry[] = [];
  if (fs.existsSync(CAUSES_JSON)) {
    const causesData = JSON.parse(fs.readFileSync(CAUSES_JSON, 'utf-8'));
    causes = causesData.causes || [];
  }
  if (causes.length > 0) {
    urls.push(`  <url>
    <loc>${loc('/causes')}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
    for (const cause of causes) {
      urls.push(`  <url>
    <loc>${loc(`/causes/${cause.slug}`)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
    }
  }

  // Guide pages
  let guides: GuideSummary[] = [];
  if (fs.existsSync(GUIDES_INDEX)) {
    const guidesData = JSON.parse(fs.readFileSync(GUIDES_INDEX, 'utf-8'));
    // pending-review guides stay out of the sitemap until they clear review
    guides = (guidesData.guides || []).filter((g: GuideSummary) => g.status !== 'pending-review');
  }
  if (guides.length > 0) {
    urls.push(`  <url>
    <loc>${loc('/guides')}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>`);
    for (const g of guides) {
      urls.push(`  <url>
    <loc>${loc(`/guides/${g.slug}`)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>`);
    }
  }

  // Zakat calculator pages
  let calculatorAssets: CalculatorAsset[] = [];
  if (fs.existsSync(CALCULATOR_JSON)) {
    const d: CalculatorData = JSON.parse(fs.readFileSync(CALCULATOR_JSON, 'utf-8'));
    calculatorAssets = d.assets || [];
  }
  urls.push(`  <url>
    <loc>${loc('/zakat-calculator')}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>`);
  for (const asset of calculatorAssets) {
    urls.push(`  <url>
    <loc>${loc(`/zakat-calculator/${asset.slug}`)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join('\n')}
</urlset>
`;

  fs.writeFileSync(path.join(DIST_DIR, 'sitemap.xml'), xml, 'utf-8');
  const causeCount = causes.length > 0 ? causes.length + 1 : 0;
  const guideCount = guides.length > 0 ? guides.length + 1 : 0;
  const calculatorCount = 1 + calculatorAssets.length;
  console.log(`Sitemap: ${urls.length} URLs (${staticPages.length} static + ${charities.length} charities + ${prompts.length} prompts + ${causeCount} causes + ${guideCount} guides + ${calculatorCount} calculator)`);
}

generateSitemap();

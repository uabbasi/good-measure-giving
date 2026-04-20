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
const CAUSES_JSON = path.join(__dirname, '../data/causes/causes.json');
const SITE_URL = 'https://goodmeasuregiving.org';

interface CharitySummary {
  ein: string;
}

interface PromptSummary {
  id: string;
  status?: 'active' | 'planned';
}

interface CauseEntry {
  slug: string;
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

  // Prompt pages — only active prompts are indexed (planned ones are stubs).
  let prompts: PromptSummary[] = [];
  if (fs.existsSync(PROMPTS_INDEX)) {
    const promptsData = JSON.parse(fs.readFileSync(PROMPTS_INDEX, 'utf-8'));
    prompts = (promptsData.prompts || []).filter((p: PromptSummary) => p.status !== 'planned');
  }
  for (const prompt of prompts) {
    urls.push(`  <url>
    <loc>${SITE_URL}/prompts/${prompt.id}</loc>
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

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join('\n')}
</urlset>
`;

  fs.writeFileSync(path.join(DIST_DIR, 'sitemap.xml'), xml, 'utf-8');
  const causeCount = causes.length > 0 ? causes.length + 1 : 0;
  console.log(`Sitemap: ${urls.length} URLs (${staticPages.length} static + ${charities.length} charities + ${prompts.length} prompts + ${causeCount} causes)`);
}

generateSitemap();

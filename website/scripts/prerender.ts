/**
 * Prerender Script
 * Uses Puppeteer to render SPA pages and inject SEO meta/OG/JSON-LD tags.
 * Writes prerendered HTML to dist/ for search engine crawlers.
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { spawn, type ChildProcess } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DIST_DIR = path.join(__dirname, '../dist');
const DATA_DIR = path.join(__dirname, '../data/charities');
const CHARITIES_JSON = path.join(DATA_DIR, 'charities.json');
const SITE_URL = 'https://goodmeasuregiving.com';
const PREVIEW_PORT = 4174;
const CONCURRENCY = 4;

// ── Types ──────────────────────────────────────────────────────────────

interface CharitySummary {
  ein: string;
  name: string;
  amal_score: number | null;
  wallet_tag: string | null;
}

interface CharityDetail {
  ein: string;
  name: string;
  mission?: string;
  website?: string;
  location?: { address?: string; city?: string; state?: string; zip?: string };
  amalEvaluation?: {
    amal_score?: number;
    wallet_tag?: string;
    baseline_narrative?: { headline?: string };
    rich_narrative?: { headline?: string };
  };
}

interface PageMeta {
  route: string;
  title: string;
  description: string;
  canonical: string;
  ogType: string;
  jsonLd?: object;
}

// ── Meta builders ──────────────────────────────────────────────────────

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 1) + '\u2026';
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
        'Evidence-based evaluations of Muslim charities. Compare zakat eligibility, impact scores, and financial transparency across 160+ organizations.',
      canonical: `${SITE_URL}/`,
      ogType: 'website',
    },
    {
      route: '/browse',
      title: 'Browse Charities | Good Measure Giving',
      description:
        'Explore evaluated Muslim charities. Filter by zakat eligibility, impact score, cause area, and financial transparency.',
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
    },
    {
      route: '/faq',
      title: 'FAQ | Good Measure Giving',
      description:
        'Common questions about charity evaluations, methodology, zakat compliance, and how to use Good Measure Giving.',
      canonical: `${SITE_URL}/faq`,
      ogType: 'website',
    },
    {
      route: '/about',
      title: 'About | Good Measure Giving',
      description:
        'Independent charity evaluator focused on Muslim charities, built on evidence-based research and long-term thinking.',
      canonical: `${SITE_URL}/about`,
      ogType: 'website',
    },
  ];
}

function buildCharityMeta(detail: CharityDetail): PageMeta {
  const amal = detail.amalEvaluation;
  const name = detail.name;
  const score = amal?.amal_score;
  const walletTag = amal?.wallet_tag?.replace(/-/g, ' ').toLowerCase() || '';
  const headline =
    amal?.rich_narrative?.headline ||
    amal?.baseline_narrative?.headline ||
    detail.mission ||
    '';

  const scorePart = score != null ? `${score}/100` : 'Evaluated';
  const walletPart = walletTag ? ` ${walletTag[0].toUpperCase() + walletTag.slice(1)}.` : '';
  const headlinePart = headline ? ` ${headline}` : '';
  const raw = `${name}: ${scorePart}.${walletPart}${headlinePart}`;
  const description = truncate(raw, 160);

  const title = `${name} | Good Measure Giving`;

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
    jsonLd.aggregateRating = {
      '@type': 'AggregateRating',
      ratingValue: score,
      bestRating: 100,
      worstRating: 0,
      ratingCount: 1,
    };
  }

  return {
    route: `/charity/${detail.ein}`,
    title,
    description,
    canonical: `${SITE_URL}/charity/${detail.ein}`,
    ogType: 'article',
    jsonLd,
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

  // Replace canonical
  if (html.includes('rel="canonical"')) {
    html = html.replace(
      /<link\s+rel="canonical"\s+href="[^"]*"\s*\/?>/,
      `<link rel="canonical" href="${meta.canonical}" />`
    );
  } else {
    html = html.replace('</title>', `</title>\n    <link rel="canonical" href="${meta.canonical}" />`);
  }

  // Replace OG tags
  const ogTags = [
    `<meta property="og:title" content="${escapeHtml(meta.title)}" />`,
    `<meta property="og:description" content="${escapeHtml(meta.description)}" />`,
    `<meta property="og:type" content="${meta.ogType}" />`,
    `<meta property="og:url" content="${meta.canonical}" />`,
    `<meta property="og:site_name" content="Good Measure Giving" />`,
  ].join('\n    ');

  // Remove existing OG tags and re-inject
  html = html.replace(/<meta\s+property="og:[^"]*"\s+content="[^"]*"\s*\/?>\n?\s*/g, '');

  // Inject JSON-LD if present
  let jsonLdTag = '';
  if (meta.jsonLd) {
    jsonLdTag = `\n    <script type="application/ld+json">${JSON.stringify(meta.jsonLd)}</script>`;
  }

  // Insert all SEO tags before </head>
  html = html.replace('</head>', `    ${ogTags}${jsonLdTag}\n  </head>`);

  return html;
}

// ── Prerender orchestration ────────────────────────────────────────────

async function startPreviewServer(): Promise<ChildProcess> {
  const server = spawn('npx', ['vite', 'preview', '--port', String(PREVIEW_PORT)], {
    cwd: path.join(__dirname, '..'),
    stdio: 'pipe',
  });

  // Wait for server to be ready
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Preview server timeout')), 15000);

    server.stdout?.on('data', (data: Buffer) => {
      if (data.toString().includes('Local:') || data.toString().includes(String(PREVIEW_PORT))) {
        clearTimeout(timeout);
        resolve();
      }
    });

    server.stderr?.on('data', (data: Buffer) => {
      const msg = data.toString();
      // Vite sometimes prints port info to stderr
      if (msg.includes(String(PREVIEW_PORT))) {
        clearTimeout(timeout);
        resolve();
      }
    });

    server.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });

  return server;
}

function writePrerenderedFromBaseHtml(metas: PageMeta[]): number {
  const baseHtmlPath = path.join(DIST_DIR, 'index.html');
  const baseHtml = fs.readFileSync(baseHtmlPath, 'utf-8');
  let written = 0;

  for (const meta of metas) {
    const html = injectMeta(baseHtml, meta);
    const outDir = path.join(DIST_DIR, meta.route === '/' ? '' : meta.route);
    fs.mkdirSync(outDir, { recursive: true });
    const outFile = meta.route === '/' ? path.join(DIST_DIR, 'index.html') : path.join(outDir, 'index.html');
    fs.writeFileSync(outFile, html, 'utf-8');
    written++;
  }

  return written;
}

function resolvePrerenderMode(): { mode: 'browser' | 'static'; reason: string } {
  const explicitMode = (process.env.PRERENDER_MODE || '').trim().toLowerCase();
  if (explicitMode === 'browser') {
    return { mode: 'browser', reason: 'PRERENDER_MODE=browser' };
  }
  if (explicitMode === 'static' || explicitMode === 'fallback' || explicitMode === 'none') {
    return { mode: 'static', reason: `PRERENDER_MODE=${explicitMode}` };
  }

  const isCloudflarePages =
    process.env.CF_PAGES === '1' ||
    !!process.env.CF_PAGES_BRANCH ||
    !!process.env.CF_PAGES_URL;
  const isCi = process.env.CI === '1' || process.env.CI === 'true';

  if (isCloudflarePages) {
    return { mode: 'static', reason: 'Cloudflare Pages environment detected' };
  }
  if (isCi) {
    return { mode: 'static', reason: 'CI environment detected' };
  }

  return { mode: 'browser', reason: 'default local build behavior' };
}

async function prerenderPages() {
  // Load charity data
  const charitiesIndex = JSON.parse(fs.readFileSync(CHARITIES_JSON, 'utf-8'));
  const charities: CharitySummary[] = charitiesIndex.charities || [];

  // Build meta for all pages
  const metas: PageMeta[] = [...buildStaticMeta()];

  for (const charity of charities) {
    const detailPath = path.join(DATA_DIR, `charity-${charity.ein}.json`);
    if (fs.existsSync(detailPath)) {
      const detail: CharityDetail = JSON.parse(fs.readFileSync(detailPath, 'utf-8'));
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

  console.log(`Prerender: ${metas.length} pages (${metas.length - charities.length} static + ${charities.length} charities)`);

  const prerenderMode = resolvePrerenderMode();
  if (prerenderMode.mode === 'static') {
    console.log(`Using fallback prerender (no headless browser): ${prerenderMode.reason}.`);
    const written = writePrerenderedFromBaseHtml(metas);
    console.log(`Prerender complete: ${written} pages written to dist/`);
    return;
  }

  // Dynamic import for puppeteer (ESM)
  const puppeteer = await import('puppeteer');
  let browser: Awaited<ReturnType<typeof puppeteer.default.launch>> | null = null;
  let server: ChildProcess | null = null;
  try {
    try {
      browser = await puppeteer.default.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      });
    } catch (launchError) {
      console.warn('Headless browser unavailable; using fallback prerender:', launchError);
      const written = writePrerenderedFromBaseHtml(metas);
      console.log(`Prerender complete: ${written} pages written to dist/`);
      return;
    }

    // Start preview server
    console.log('Starting preview server...');
    server = await startPreviewServer();

    // Process pages with concurrency limit
    let completed = 0;
    const queue = [...metas];

    async function processPage(page: Awaited<ReturnType<typeof browser.newPage>>, meta: PageMeta) {
      const url = `http://localhost:${PREVIEW_PORT}${meta.route}`;
      try {
        await page.goto(url, { waitUntil: 'networkidle0', timeout: 15000 });
      } catch {
        // Fallback: just use the base HTML with meta injection
        console.warn(`  Warning: timeout on ${meta.route}, using base HTML`);
      }

      let html = await page.content();
      html = injectMeta(html, meta);

      // Write to dist
      const outDir = path.join(DIST_DIR, meta.route === '/' ? '' : meta.route);
      fs.mkdirSync(outDir, { recursive: true });
      const outFile = meta.route === '/' ? path.join(DIST_DIR, 'index.html') : path.join(outDir, 'index.html');
      fs.writeFileSync(outFile, html, 'utf-8');

      completed++;
      if (completed % 20 === 0 || completed === metas.length) {
        console.log(`  ${completed}/${metas.length} pages rendered`);
      }
    }

    // Create worker pages
    const pages = await Promise.all(
      Array.from({ length: CONCURRENCY }, () => browser.newPage())
    );

    // Process queue
    async function worker(page: Awaited<ReturnType<typeof browser.newPage>>) {
      while (queue.length > 0) {
        const meta = queue.shift()!;
        await processPage(page, meta);
      }
    }

    await Promise.all(pages.map((page) => worker(page)));

    console.log(`Prerender complete: ${completed} pages written to dist/`);
  } finally {
    if (server) server.kill();
    if (browser) await browser.close().catch(() => undefined);
  }
}

prerenderPages().catch((err) => {
  console.error('Prerender failed:', err);
  process.exit(1);
});

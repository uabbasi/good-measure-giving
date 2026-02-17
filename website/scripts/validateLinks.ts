/**
 * Link Validator
 * Extracts all external URLs from charity JSONs and validates them via HTTP.
 *
 * Usage:
 *   npx tsx scripts/validateLinks.ts [--category=cat1,cat2] [--timeout=15000]
 *
 * Categories: charity_website, donation_url, cn_url, candid_url, bbb_url, citation_url, attribution_url
 */

import * as fs from 'fs';
import * as path from 'path';
import * as https from 'https';
import * as http from 'http';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CHARITIES_DIR = path.join(__dirname, '../data/charities');
const REPORT_JSON = path.join(__dirname, 'link-report.json');
const REPORT_MD = path.join(__dirname, 'link-report.md');

const BLOCKED_DOMAINS = ['guidestar.org', 'ngo-monitor.org', 'canarymission.org'];

const SLOW_DOMAINS: Record<string, number> = {
  'charitynavigator.org': 500,
  'www.charitynavigator.org': 500,
  'candid.org': 500,
  'app.candid.org': 500,
  'propublica.org': 500,
  'projects.propublica.org': 500,
  'bbb.org': 1000,
  'www.bbb.org': 1000,
  'give.org': 1000,
  'www.give.org': 1000,
};

const MAX_CONCURRENT_PER_DOMAIN = 2;
const MAX_RETRIES = 2;
const HEAD_TIMEOUT = 5000;

type Category =
  | 'charity_website'
  | 'donation_url'
  | 'cn_url'
  | 'candid_url'
  | 'bbb_url'
  | 'citation_url'
  | 'attribution_url';

const ALL_CATEGORIES: Category[] = [
  'charity_website',
  'donation_url',
  'cn_url',
  'candid_url',
  'bbb_url',
  'citation_url',
  'attribution_url',
];

interface UrlEntry {
  url: string;
  category: Category;
  charity_ein: string;
}

interface ResultEntry {
  url: string;
  status?: number;
  category: Category;
  charity_ein: string;
  error?: string;
  reason?: string;
}

interface Report {
  timestamp: string;
  total_urls_checked: number;
  results: {
    ok: ResultEntry[];
    broken: ResultEntry[];
    blocked: ResultEntry[];
    timeout: ResultEntry[];
  };
  summary: {
    ok: number;
    broken: number;
    blocked: number;
    timeout: number;
  };
}

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

function parseArgs(): { categories: Set<Category>; timeout: number } {
  const args = process.argv.slice(2);
  let categories: Set<Category> = new Set(ALL_CATEGORIES);
  let timeout = 15000;

  for (const arg of args) {
    if (arg.startsWith('--category=')) {
      const cats = arg.slice('--category='.length).split(',') as Category[];
      categories = new Set(cats.filter((c) => ALL_CATEGORIES.includes(c)));
      if (categories.size === 0) {
        console.error(`No valid categories provided. Valid: ${ALL_CATEGORIES.join(', ')}`);
        process.exit(1);
      }
    } else if (arg.startsWith('--timeout=')) {
      timeout = parseInt(arg.slice('--timeout='.length), 10);
      if (isNaN(timeout) || timeout <= 0) {
        console.error('Invalid timeout value');
        process.exit(1);
      }
    }
  }

  return { categories, timeout };
}

// ---------------------------------------------------------------------------
// URL extraction
// ---------------------------------------------------------------------------

function extractUrls(charityDir: string, categories: Set<Category>): UrlEntry[] {
  const entries: UrlEntry[] = [];
  const files = fs.readdirSync(charityDir).filter((f) => f.startsWith('charity-') && f.endsWith('.json'));

  for (const file of files) {
    const filePath = path.join(charityDir, file);
    let data: any;
    try {
      data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } catch {
      continue;
    }

    const ein: string = data.ein || data.id || file.replace('charity-', '').replace('.json', '');

    if (categories.has('charity_website') && data.website) {
      entries.push({ url: data.website, category: 'charity_website', charity_ein: ein });
    }
    if (categories.has('donation_url') && data.donationUrl) {
      entries.push({ url: data.donationUrl, category: 'donation_url', charity_ein: ein });
    }
    if (categories.has('cn_url') && data.awards?.cnUrl) {
      entries.push({ url: data.awards.cnUrl, category: 'cn_url', charity_ein: ein });
    }
    if (categories.has('candid_url') && data.awards?.candidUrl) {
      entries.push({ url: data.awards.candidUrl, category: 'candid_url', charity_ein: ein });
    }
    if (categories.has('bbb_url') && data.awards?.bbbReviewUrl) {
      entries.push({ url: data.awards.bbbReviewUrl, category: 'bbb_url', charity_ein: ein });
    }

    if (categories.has('citation_url')) {
      const baselineCitations = data.amalEvaluation?.baseline_narrative?.all_citations ?? [];
      for (const c of baselineCitations) {
        if (c.source_url) {
          entries.push({ url: c.source_url, category: 'citation_url', charity_ein: ein });
        }
      }
      const richCitations = data.amalEvaluation?.rich_narrative?.all_citations ?? [];
      for (const c of richCitations) {
        if (c.source_url) {
          entries.push({ url: c.source_url, category: 'citation_url', charity_ein: ein });
        }
      }
    }

    if (categories.has('attribution_url') && data.sourceAttribution) {
      for (const key of Object.keys(data.sourceAttribution)) {
        const attr = data.sourceAttribution[key];
        if (attr?.source_url) {
          entries.push({ url: attr.source_url, category: 'attribution_url', charity_ein: ein });
        }
      }
    }
  }

  return entries;
}

/** Deduplicate by URL, keeping the first occurrence (with its category/ein). */
function deduplicateUrls(entries: UrlEntry[]): UrlEntry[] {
  const seen = new Map<string, UrlEntry>();
  for (const entry of entries) {
    if (!seen.has(entry.url)) {
      seen.set(entry.url, entry);
    }
  }
  return Array.from(seen.values());
}

// ---------------------------------------------------------------------------
// Domain helpers
// ---------------------------------------------------------------------------

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

function isBlockedDomain(url: string): boolean {
  const domain = getDomain(url);
  return BLOCKED_DOMAINS.some((d) => domain === d || domain.endsWith('.' + d));
}

function getDelayForDomain(domain: string): number {
  for (const [pattern, delay] of Object.entries(SLOW_DOMAINS)) {
    if (domain === pattern || domain.endsWith('.' + pattern)) {
      return delay;
    }
  }
  return 0;
}

// ---------------------------------------------------------------------------
// HTTP checking
// ---------------------------------------------------------------------------

function httpRequest(
  url: string,
  method: 'HEAD' | 'GET',
  timeoutMs: number,
): Promise<{ status: number; error?: string }> {
  return new Promise((resolve) => {
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(url);
    } catch {
      resolve({ status: 0, error: 'Invalid URL' });
      return;
    }

    const lib = parsedUrl.protocol === 'https:' ? https : http;
    const options = {
      method,
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || undefined,
      path: parsedUrl.pathname + parsedUrl.search,
      timeout: timeoutMs,
      headers: {
        'User-Agent': 'GoodMeasureGiving-LinkValidator/1.0',
        Accept: '*/*',
      },
    };

    const req = lib.request(options, (res) => {
      // Follow redirects (up to 5)
      if (res.statusCode && [301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        const redirectUrl = res.headers.location.startsWith('http')
          ? res.headers.location
          : new URL(res.headers.location, url).href;
        res.resume();
        httpRequest(redirectUrl, method, timeoutMs).then(resolve);
        return;
      }
      res.resume();
      resolve({ status: res.statusCode ?? 0 });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ status: 0, error: 'timeout' });
    });

    req.on('error', (err: Error) => {
      resolve({ status: 0, error: err.message });
    });

    req.end();
  });
}

async function checkUrl(
  url: string,
  requestTimeout: number,
): Promise<{ status: number; error?: string; isTimeout: boolean }> {
  // Try HEAD first with a shorter timeout
  const headResult = await httpRequest(url, 'HEAD', HEAD_TIMEOUT);

  if (headResult.status >= 200 && headResult.status < 400) {
    return { status: headResult.status, isTimeout: false };
  }

  // Fall back to GET on 405 (Method Not Allowed) or HEAD timeout
  if (headResult.status === 405 || headResult.error === 'timeout') {
    const getResult = await httpRequest(url, 'GET', requestTimeout);
    if (getResult.error === 'timeout') {
      return { status: 0, error: 'timeout', isTimeout: true };
    }
    return { status: getResult.status, error: getResult.error, isTimeout: false };
  }

  if (headResult.error === 'timeout') {
    return { status: 0, error: 'timeout', isTimeout: true };
  }

  return { status: headResult.status, error: headResult.error, isTimeout: false };
}

async function checkUrlWithRetry(
  url: string,
  requestTimeout: number,
): Promise<{ status: number; error?: string; isTimeout: boolean }> {
  let lastResult = await checkUrl(url, requestTimeout);

  // Retry on transient errors (429, 503)
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    if (lastResult.status !== 429 && lastResult.status !== 503) break;
    const backoff = Math.pow(2, attempt + 1) * 1000; // 2s, 4s
    await sleep(backoff);
    lastResult = await checkUrl(url, requestTimeout);
  }

  return lastResult;
}

// ---------------------------------------------------------------------------
// Rate-limited domain queue
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface DomainQueue {
  active: number;
  queue: Array<() => void>;
}

class RateLimiter {
  private domains = new Map<string, DomainQueue>();
  private lastRequestTime = new Map<string, number>();

  async acquire(domain: string): Promise<void> {
    let dq = this.domains.get(domain);
    if (!dq) {
      dq = { active: 0, queue: [] };
      this.domains.set(domain, dq);
    }

    if (dq.active >= MAX_CONCURRENT_PER_DOMAIN) {
      await new Promise<void>((resolve) => dq!.queue.push(resolve));
    }

    dq.active++;

    // Enforce per-domain delay
    const delay = getDelayForDomain(domain);
    if (delay > 0) {
      const last = this.lastRequestTime.get(domain) ?? 0;
      const elapsed = Date.now() - last;
      if (elapsed < delay) {
        await sleep(delay - elapsed);
      }
    }

    this.lastRequestTime.set(domain, Date.now());
  }

  release(domain: string): void {
    const dq = this.domains.get(domain);
    if (!dq) return;
    dq.active--;
    if (dq.queue.length > 0) {
      const next = dq.queue.shift()!;
      next();
    }
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const { categories, timeout } = parseArgs();

  console.log(`Extracting URLs from ${CHARITIES_DIR} ...`);
  const rawEntries = extractUrls(CHARITIES_DIR, categories);
  console.log(`Found ${rawEntries.length} total URL entries (before dedup)`);

  const entries = deduplicateUrls(rawEntries);
  console.log(`${entries.length} unique URLs to check\n`);

  const report: Report = {
    timestamp: new Date().toISOString(),
    total_urls_checked: entries.length,
    results: { ok: [], broken: [], blocked: [], timeout: [] },
    summary: { ok: 0, broken: 0, blocked: 0, timeout: 0 },
  };

  // Separate blocked URLs (no HTTP requests needed)
  const blocked: UrlEntry[] = [];
  const toCheck: UrlEntry[] = [];

  for (const entry of entries) {
    if (isBlockedDomain(entry.url)) {
      blocked.push(entry);
    } else {
      toCheck.push(entry);
    }
  }

  for (const entry of blocked) {
    report.results.blocked.push({
      url: entry.url,
      category: entry.category,
      charity_ein: entry.charity_ein,
      reason: 'blocked domain',
    });
  }
  report.summary.blocked = blocked.length;

  if (blocked.length > 0) {
    console.log(`Flagged ${blocked.length} URL(s) from blocked domains\n`);
  }

  const total = entries.length;
  let processed = blocked.length;

  const limiter = new RateLimiter();

  // Process URLs with concurrency limited per domain
  const GLOBAL_CONCURRENCY = 20;
  let globalActive = 0;
  const globalQueue: Array<() => void> = [];

  async function processEntry(entry: UrlEntry): Promise<void> {
    // Global concurrency gate
    if (globalActive >= GLOBAL_CONCURRENCY) {
      await new Promise<void>((resolve) => globalQueue.push(resolve));
    }
    globalActive++;

    const domain = getDomain(entry.url);

    try {
      await limiter.acquire(domain);
      const result = await checkUrlWithRetry(entry.url, timeout);
      processed++;

      if (result.isTimeout) {
        report.results.timeout.push({
          url: entry.url,
          category: entry.category,
          charity_ein: entry.charity_ein,
        });
        report.summary.timeout++;
        console.log(`[${processed}/${total}] T ${entry.url} (timeout)`);
      } else if (result.status >= 200 && result.status < 400) {
        report.results.ok.push({
          url: entry.url,
          status: result.status,
          category: entry.category,
          charity_ein: entry.charity_ein,
        });
        report.summary.ok++;
        console.log(`[${processed}/${total}] \u2713 ${entry.url} (${result.status})`);
      } else {
        report.results.broken.push({
          url: entry.url,
          status: result.status,
          category: entry.category,
          charity_ein: entry.charity_ein,
          error: result.error || `HTTP ${result.status}`,
        });
        report.summary.broken++;
        console.log(`[${processed}/${total}] \u2717 ${entry.url} (${result.status || result.error})`);
      }
    } finally {
      limiter.release(domain);
      globalActive--;
      if (globalQueue.length > 0) {
        const next = globalQueue.shift()!;
        next();
      }
    }
  }

  // Launch all checks (concurrency managed by rate limiter + global cap)
  await Promise.all(toCheck.map((entry) => processEntry(entry)));

  // Write JSON report
  fs.writeFileSync(REPORT_JSON, JSON.stringify(report, null, 2));
  console.log(`\nJSON report: ${REPORT_JSON}`);

  // Write Markdown report
  const md = generateMarkdown(report);
  fs.writeFileSync(REPORT_MD, md);
  console.log(`Markdown report: ${REPORT_MD}`);

  // Print summary
  console.log('\n--- Summary ---');
  console.log(`OK:      ${report.summary.ok}`);
  console.log(`Broken:  ${report.summary.broken}`);
  console.log(`Blocked: ${report.summary.blocked}`);
  console.log(`Timeout: ${report.summary.timeout}`);
  console.log(`Total:   ${total}`);

  // Exit with error code if there are broken links
  if (report.summary.broken > 0) {
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Markdown report
// ---------------------------------------------------------------------------

function generateMarkdown(report: Report): string {
  const lines: string[] = [];

  lines.push('# Link Validation Report');
  lines.push('');
  lines.push(`Generated: ${report.timestamp}`);
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push('| Status | Count |');
  lines.push('|--------|-------|');
  lines.push(`| OK | ${report.summary.ok} |`);
  lines.push(`| Broken | ${report.summary.broken} |`);
  lines.push(`| Blocked | ${report.summary.blocked} |`);
  lines.push(`| Timeout | ${report.summary.timeout} |`);
  lines.push(`| **Total** | **${report.total_urls_checked}** |`);
  lines.push('');

  if (report.results.broken.length > 0) {
    lines.push('## Broken Links');
    lines.push('');

    // Group by category
    const byCategory = new Map<string, ResultEntry[]>();
    for (const entry of report.results.broken) {
      const list = byCategory.get(entry.category) ?? [];
      list.push(entry);
      byCategory.set(entry.category, list);
    }

    for (const [category, entries] of Array.from(byCategory.entries())) {
      lines.push(`### ${category}`);
      lines.push('');
      lines.push('| URL | Status | EIN | Error |');
      lines.push('|-----|--------|-----|-------|');
      for (const e of entries) {
        lines.push(`| ${e.url} | ${e.status ?? ''} | ${e.charity_ein} | ${e.error ?? ''} |`);
      }
      lines.push('');
    }
  }

  if (report.results.blocked.length > 0) {
    lines.push('## Blocked Domain URLs');
    lines.push('');
    lines.push('| URL | Category | EIN | Reason |');
    lines.push('|-----|----------|-----|--------|');
    for (const e of report.results.blocked) {
      lines.push(`| ${e.url} | ${e.category} | ${e.charity_ein} | ${e.reason ?? ''} |`);
    }
    lines.push('');
  }

  if (report.results.timeout.length > 0) {
    lines.push('## Timed Out URLs');
    lines.push('');
    lines.push('| URL | Category | EIN |');
    lines.push('|-----|----------|-----|');
    for (const e of report.results.timeout) {
      lines.push(`| ${e.url} | ${e.category} | ${e.charity_ein} |`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(2);
});

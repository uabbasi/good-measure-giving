import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dataPath = path.join(__dirname, '../../data/charities.json');
const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
const charities: Array<{ id: string; name: string }> = data.charities;

// Pick every 10th charity for sampling
const sampledCharities = charities.filter((_, i) => i % 10 === 0);

const STATIC_PAGES = [
  { name: 'Home', path: '/' },
  { name: 'Browse', path: '/browse' },
  { name: 'Methodology', path: '/methodology' },
  { name: 'FAQ', path: '/faq' },
  { name: 'About', path: '/about' },
  { name: 'Prompts', path: '/prompts' },
  { name: 'Compare', path: '/compare' },
];

interface PageError {
  page: string;
  jsErrors: string[];
  consoleErrors: string[];
  failedRequests: string[];
}

async function auditPage(
  page: import('@playwright/test').Page,
  url: string,
): Promise<{ jsErrors: string[]; consoleErrors: string[]; failedRequests: string[] }> {
  const jsErrors: string[] = [];
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];

  page.on('pageerror', (err) => jsErrors.push(err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('response', (resp) => {
    const reqUrl = resp.url();
    if (resp.status() >= 400 && reqUrl.includes('localhost')) {
      failedRequests.push(`${resp.status()} ${reqUrl}`);
    }
  });

  await page.goto(url);
  await page.waitForLoadState('domcontentloaded');
  // Give the page time to render and settle after DOM load
  await page.waitForTimeout(3000);

  return { jsErrors, consoleErrors, failedRequests };
}

test.describe('Console error sweep — static pages', () => {
  for (const staticPage of STATIC_PAGES) {
    test(`${staticPage.name} (${staticPage.path}) — no JS errors`, async ({ page }) => {
      test.setTimeout(30_000);

      const result = await auditPage(page, staticPage.path);

      expect(result.jsErrors, `JS errors on ${staticPage.path}`).toEqual([]);
      expect(result.failedRequests, `Failed requests on ${staticPage.path}`).toEqual([]);
    });
  }
});

test.describe('Console error sweep — charity detail pages (sampled)', () => {
  for (const charity of sampledCharities) {
    test(`charity ${charity.id} - ${charity.name} — no JS errors`, async ({ page }) => {
      test.setTimeout(30_000);

      const result = await auditPage(page, `/charity/${charity.id}`);

      expect(result.jsErrors, `JS errors on /charity/${charity.id}`).toEqual([]);
      expect(result.failedRequests, `Failed requests on /charity/${charity.id}`).toEqual([]);
    });
  }
});

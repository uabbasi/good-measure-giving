/**
 * Track 0 schema verification.
 *
 * Reads prerendered HTML from dist/ and asserts that the expected Schema.org
 * JSON-LD blocks were injected. Does NOT launch a browser — the dev server
 * does not render prerendered schema; only the build output does.
 *
 * Requires `npm run build` to have been run before these tests execute.
 */

import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DIST_DIR = path.resolve(__dirname, '../../dist');

function extractJsonLdBlocks(html: string): unknown[] {
  const matches = [...html.matchAll(/<script\s+type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
  return matches.map((m) => JSON.parse(m[1]));
}

function topLevelTypes(blocks: unknown[]): string[] {
  return blocks
    .filter((b): b is { '@type': string } => typeof b === 'object' && b !== null && '@type' in b)
    .map((b) => b['@type']);
}

test.describe('SEO schema injection (Track 0)', () => {
  test('/faq has FAQPage schema', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'faq', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('FAQPage');
  });

  test('/methodology has TechArticle and BreadcrumbList schemas', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'methodology', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('TechArticle');
    expect(types).toContain('BreadcrumbList');
  });

  test('/about has Organization schema', () => {
    const html = fs.readFileSync(path.join(DIST_DIR, 'about', 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('Organization');
  });

  test('a sample /prompts/:id page has TechArticle and BreadcrumbList schemas', () => {
    const promptsDir = path.join(DIST_DIR, 'prompts');
    const entries = fs.readdirSync(promptsDir, { withFileTypes: true });
    const promptDirs = entries.filter((e) => e.isDirectory()).map((e) => e.name);
    expect(promptDirs.length).toBeGreaterThan(0);

    const sample = promptDirs[0];
    const html = fs.readFileSync(path.join(promptsDir, sample, 'index.html'), 'utf-8');
    const types = topLevelTypes(extractJsonLdBlocks(html));
    expect(types).toContain('TechArticle');
    expect(types).toContain('BreadcrumbList');
  });

  test('sitemap includes /prompts URLs', () => {
    const xml = fs.readFileSync(path.join(DIST_DIR, 'sitemap.xml'), 'utf-8');
    expect(xml).toMatch(/\/prompts\//);
  });

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

  test('charity page title uses new template (either Zakat Eligible question or Review suffix)', () => {
    const charityDir = path.join(DIST_DIR, 'charity');
    const dirs = fs.readdirSync(charityDir, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name);

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
});

// @vitest-environment node
//
// Phase 2C task 7: the six donor-question sections are individually tested,
// but the only proof that assembling them into GmgCharityDetail didn't blank
// the live page is rendering through the actual server path prerender.ts
// uses. scripts/prerender.ts wraps each route in try/catch and silently
// degrades to a meta-only shell on any render error — a section that throws
// during SSR would blank all 166 charity pages with a green build and
// passing CI, so this has to render for real rather than mock the sections.
//
// International Rescue Committee (13-5660870) is used because it has content
// for all six sections, a non-empty grantFlows.topRecipients, and a non-null
// capacity.ceoCompensation — the combination needed to prove both "real
// content renders" and "gated content does not leak" in one pass.

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { render } from './entry-server';

const DATA_DIR = path.resolve(__dirname, 'data/charities');
const IRC_EIN = '13-5660870';

const loadRaw = (ein: string): unknown =>
  JSON.parse(fs.readFileSync(path.join(DATA_DIR, `charity-${ein}.json`), 'utf8'));

// Mirrors scripts/prerender.ts's seedFor() for the /charity/:ein route: seed
// the charity detail under ['charity', ein] exactly as the real prerender
// does, so this test exercises the same query-cache path production uses.
const renderCharity = (ein: string): Promise<string> =>
  render(`/charity/${ein}`, [
    { queryKey: ['charities'], data: { summaries: [], charities: [] } },
    { queryKey: ['charity', ein], data: loadRaw(ein) },
  ]);

const SECTION_IDS = ['what-they-do', 'money', 'trust', 'run-well', 'right-for-you', 'compares'];

describe('GmgCharityDetail SSR (entry-server, real charity data)', () => {
  it('renders real text from all six sections, gates member-only figures, and includes required structure', async () => {
    const html = await renderCharity(IRC_EIN);

    // 1. Real content from each of the six sections — strings that only that
    // section renders, so this fails if a section silently returns nothing.
    expect(html).toContain('interactive Outcomes and Evidence Framework'); // WhatTheyDo: c.theoryOfChange
    expect(html).toContain('Sub-Saharan Africa'); // WhereMoneyGoes: grantFlows.byRegion
    expect(html).toContain('sourced claims from'); // TrustTheNumbers: citation count line
    expect(html).toContain('40+ countries'); // RunWell: capacity.geographicReach
    expect(html).toContain('large-scale, zakat-eligible international relief'); // RightForYou: bestForSummary
    expect(html).toContain('International Humanitarian Organizations'); // HowItCompares: peers.peerGroup

    // 2. Gated content is structurally absent. There is no FirebaseProvider
    // in the server tree (AppProviders omits it), so useCommunityMember() is
    // false for every SSR pass regardless of who requests the page — this
    // charity's named grant recipient and CEO comp figures must never leak.
    expect(html).not.toContain('Church World Service Inc'); // top named grant recipient
    expect(html).not.toContain('$3.9M'); // CEO compensation (usd-compact)
    expect(html).not.toContain('0.26%'); // CEO compensation, % of revenue
    // The gate's fallback rendered instead of silently omitting the block.
    // (React HTML-escapes the apostrophe in "it's" to `&#x27;`, so match
    // around it rather than the literal source string.)
    expect(html).toContain('Sign in to see this');

    // 3. Required structure: a real <h1> and all six section wrappers, which
    // is what SectionRail queries and what proves the spine actually mounted.
    expect(html).toMatch(/<h1[ >]/);
    for (const id of SECTION_IDS) {
      expect(html).toContain(`data-section="${id}"`);
    }
  }, 20000);
});

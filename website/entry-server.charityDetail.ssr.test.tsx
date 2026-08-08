// @vitest-environment node
//
// scripts/prerender.ts wraps each route in try/catch and silently degrades
// to a meta-only shell on any render error — a throw here would blank all
// 166 charity pages with a green build and passing CI, so this has to
// render for real through the actual server path (entry-server's render())
// rather than mock GmgCharityDetail or its sections.
//
// There is no FirebaseProvider anywhere in the server tree (AppProviders
// omits it), so useCommunityMember() is false for every SSR pass regardless
// of who requests the page — every prerendered charity page is, and must
// stay, the anonymous view: identity + the wall + similar charities. Nothing
// evaluative (scores, financials, the six donor-question sections,
// methodology) may reach that HTML. See GmgCharityDetail.anonWall.test.tsx
// for the signed-in path, which can only be exercised client-side.
//
// International Rescue Committee (13-5660870) and Doctors Without Borders
// (13-3433452) are both used so the wall's counts (concerns, citations,
// grants) are proven to come from each charity's own data rather than a
// hardcoded copy — see AnonWall.test.tsx for the same proof at the unit level.

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { render } from './entry-server';

const DATA_DIR = path.resolve(__dirname, 'data/charities');
const IRC_EIN = '13-5660870';
const DWB_EIN = '13-3433452';

const loadRaw = (ein: string): unknown =>
  JSON.parse(fs.readFileSync(path.join(DATA_DIR, `charity-${ein}.json`), 'utf8'));

// Both fixtures share the raw primaryCategory "HUMANITARIAN"; a peer with
// matching category AND zakat status is required for selectSimilarCharities
// to return anything (see scripts/lib/charity-seo.ts). Real prerender.ts
// seeds this from the actual charities index — a hand-built pool here of at
// least one same-category/same-zakat-status peer stands in for that so the
// similar-charities block has something to render.
const CHARITIES_INDEX = {
  summaries: [
    { ein: IRC_EIN, name: 'International Rescue Committee', primaryCategory: 'HUMANITARIAN', walletTag: 'ZAKAT-ELIGIBLE', amalScore: 78 },
    { ein: '11-1111111', name: 'Zakat-Eligible Peer One', primaryCategory: 'HUMANITARIAN', walletTag: 'ZAKAT-ELIGIBLE', amalScore: 70 },
    { ein: '33-3333333', name: 'Zakat-Eligible Peer Two', primaryCategory: 'HUMANITARIAN', walletTag: 'ZAKAT-ELIGIBLE', amalScore: 68 },
    { ein: DWB_EIN, name: 'Doctors Without Borders', primaryCategory: 'HUMANITARIAN', walletTag: 'SADAQAH-ELIGIBLE', amalScore: 65 },
    { ein: '22-2222222', name: 'Sadaqah-Only Peer One', primaryCategory: 'HUMANITARIAN', walletTag: 'SADAQAH-ELIGIBLE', amalScore: 60 },
    { ein: '44-4444444', name: 'Sadaqah-Only Peer Two', primaryCategory: 'HUMANITARIAN', walletTag: 'SADAQAH-ELIGIBLE', amalScore: 58 },
  ],
  charities: [],
};

// Mirrors scripts/prerender.ts's seedFor() for the /charity/:ein route: seed
// the charity detail under ['charity', ein] exactly as the real prerender
// does, so this test exercises the same query-cache path production uses.
const renderCharity = (ein: string): Promise<string> =>
  render(`/charity/${ein}`, [
    { queryKey: ['charities'], data: CHARITIES_INDEX },
    { queryKey: ['charity', ein], data: loadRaw(ein) },
  ]);

const SECTION_IDS = ['what-they-do', 'money', 'trust', 'run-well', 'right-for-you', 'compares'];
const SECTION_HEADINGS = [
  'What they do, and is it real?',
  'Where your money goes',
  'Can you trust these numbers?',
  'Is it run well?',
  'Is it right for you?',
  'How it compares',
];

describe('GmgCharityDetail SSR (entry-server, real charity data) — anonymous wall', () => {
  it('renders identity, the zakat status, and the wall for International Rescue Committee', async () => {
    const html = await renderCharity(IRC_EIN);

    // 1. Identity — the minimum a signed-out visitor and a crawler both get.
    expect(html).toMatch(/<h1[^>]*>International Rescue Committee<\/h1>/);
    expect(html).toContain('EIN 13-5660870');
    expect(html).toContain('Humanitarian Relief'); // primary category
    expect(html).toContain('Accepts Zakat'); // wallet/zakat status
    expect(html).toContain('Fuqara'); // asnaf tag

    // 2. The wall's call to action and sign-in control.
    expect(html).toContain('is free');
    expect(html).toContain('See Full Evaluations');

    // 3. The wall's counts, computed from this charity's own data (see
    // AnonWall.test.tsx for the pure-function version of this same proof).
    expect(html).toContain('1 identified concern');
    expect(html).toContain('6 cited claims from 6 sources');
    expect(html).toContain('Grant flow analysis across 703 grants');

    // 4. The index-derived similar-charities block stays public — its LINKS
    // are the point (crawlable /charity/<ein>/ hrefs). Its peers' SCORES are
    // not: every charity appears in ~23 peers' similar-lists, so rendering
    // scores here would republish every score we just hid, on pages we do not
    // control the gating of. Peer names visible, peer scores absent.
    expect(html).toContain('Similar charities');
    expect(html).toContain('Zakat-Eligible Peer One');
    // React emits `70<!-- -->/100` for adjacent text expressions during SSR, so
    // a plain toContain('70/100') can never match and would pass no matter what
    // this code did. Match the comment optionally. (The prerenderer strips those
    // comments, which is what makes the built HTML look like plain `70/100`.)
    expect(html).not.toMatch(/70(<!-- -->)?\/100/); // peer amalScore
    expect(html).not.toMatch(/68(<!-- -->)?\/100/); // peer amalScore

    // 5. Nothing evaluative leaked: no scores, no financial figures, no
    // conviction/quality tags, no section headings, no data-section
    // wrapper, and no summary/headline prose.
    expect(html).not.toContain('37 / 50'); // Impact score/max
    expect(html).not.toContain('41 / 50'); // Alignment score/max
    expect(html).not.toContain('$4,088'); // cost per beneficiary
    expect(html).not.toContain('88%'); // program ratio
    expect(html).not.toContain('2.4 mo'); // reserves
    expect(html).not.toContain('Strong Match'); // GMG recommendation cue
    expect(html).not.toContain('High Conviction'); // assessment_label
    expect(html).not.toContain('Frontline Relief'); // archetype_label
    expect(html).not.toContain('Verified'); // evidence_stage
    expect(html).not.toContain('Founded in 1933, the International Rescue Committee provides'); // summary prose
    expect(html).not.toContain('Methodology details');
    for (const heading of SECTION_HEADINGS) expect(html).not.toContain(heading);
    for (const id of SECTION_IDS) expect(html).not.toContain(`data-section="${id}"`);
  }, 20000);

  it('renders different wall counts for a second charity, proving the counts are not hardcoded', async () => {
    const html = await renderCharity(DWB_EIN);

    expect(html).toMatch(/<h1[^>]*>Doctors Without Borders<\/h1>/);
    expect(html).toContain('EIN 13-3433452');
    expect(html).toContain('2 identified concerns');
    expect(html).toContain('5 cited claims from 5 sources');
    expect(html).toContain('Grant flow analysis across 11 grants');

    // Same evaluative figures must stay absent for this charity too.
    expect(html).not.toContain('Methodology details');
    for (const id of SECTION_IDS) expect(html).not.toContain(`data-section="${id}"`);
  }, 20000);
});

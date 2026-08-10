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
// stay, the anonymous view. That view is the BASELINE tier: identity, the
// quality bands, the hard financials, the baseline narrative, strengths,
// growth areas, concerns, citations, the six donor-question sections, the
// wall prompt and similar charities.
//
// Two things must never reach that HTML:
//   1. Raw score numerals (dimension score/max, peer X/100). /browse
//      publishes qualitative bands anonymously but no numbers, so numbers
//      are the consistent member-only line across every surface.
//   2. Rich-tier prose — anything charityAdapter sources from `rn` rather
//      than from the shared rich-or-baseline `narrative`.
// See GmgCharityDetail.anonWall.test.tsx for the signed-in path, which can
// only be exercised client-side.
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

describe('GmgCharityDetail SSR (entry-server, real charity data) — anonymous baseline tier', () => {
  it('renders identity, the baseline evaluation, and the prompt for International Rescue Committee', async () => {
    const html = await renderCharity(IRC_EIN);

    // 1. Identity — the minimum a signed-out visitor and a crawler both get.
    expect(html).toMatch(/<h1[^>]*>International Rescue Committee<\/h1>/);
    expect(html).toContain('EIN 13-5660870');
    expect(html).toContain('Humanitarian Relief'); // primary category
    expect(html).toContain('Accepts Zakat'); // wallet/zakat status
    expect(html).toContain('Fuqara'); // asnaf tag

    // 1b. The baseline tier itself. This is what makes the page worth
    // indexing, and each item below is sourced from the shared
    // rich-or-baseline `narrative` or from ui_signals_v1 — never from `rn`.
    // Summary prose. Asserted from just past the "1933" citation, because
    // CitedText renders that citation as a superscript mid-sentence and the
    // sentence is therefore never contiguous in the HTML.
    expect(html).toContain('the International Rescue Committee provides vital emergency relief');
    expect(html).toContain('Methodology details');
    expect(html).toContain('$4,088'); // cost per beneficiary
    expect(html).toContain('88%'); // program ratio
    expect(html).toContain('2.4 mo'); // reserves
    expect(html).toContain('High Conviction'); // assessment_label (ui_signals_v1)
    expect(html).toContain('Frontline Relief'); // archetype_label (ui_signals_v1)
    expect(html).toContain('Verified'); // evidence_stage (ui_signals_v1, as on /browse)
    for (const heading of SECTION_HEADINGS) expect(html).toContain(heading);
    for (const id of SECTION_IDS) expect(html).toContain(`data-section="${id}"`);

    // 2. The signed-out prompt follows the baseline rather than replacing it.
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

    // 5. The member-only line holds. Raw score numerals stay out (the
    // qualitative bands beside them are public), and so does every string
    // the adapter sources from `rn`.
    // `{dim.score} / {dim.max}` are adjacent text expressions, so React SSR
    // emits `37<!-- --> / <!-- -->50` and a plain toContain('37 / 50') can
    // never match — it would pass no matter what this code did. Same trap the
    // peer-score assertion below documents. Verified by mutation: forcing
    // showScore/showScores true turns both of these red.
    expect(html).not.toMatch(/37(<!-- -->)?\s*\/\s*(<!-- -->)?50/); // Impact score/max
    expect(html).not.toMatch(/41(<!-- -->)?\s*\/\s*(<!-- -->)?50/); // Alignment score/max
    expect(html).not.toContain('David Miliband'); // rn.organizational_capacity.ceo_name
    expect(html).not.toContain('Extensive program tracking backed by external impact evaluations'); // rn.impact_evidence
    expect(html).not.toContain('Expanding global humanitarian crises'); // rn.long_term_outlook
  }, 20000);

  it('renders different wall counts for a second charity, proving the counts are not hardcoded', async () => {
    const html = await renderCharity(DWB_EIN);

    expect(html).toMatch(/<h1[^>]*>Doctors Without Borders<\/h1>/);
    expect(html).toContain('EIN 13-3433452');
    expect(html).toContain('2 identified concerns');
    expect(html).toContain('5 cited claims from 5 sources');
    expect(html).toContain('Grant flow analysis across 11 grants');

    // The baseline tier renders for this charity too...
    expect(html).toContain('Methodology details');
    for (const id of SECTION_IDS) expect(html).toContain(`data-section="${id}"`);

    // ...and the raw score numerals still do not.
    expect(html).not.toMatch(/\d+ \/ 50/);
  }, 20000);
});

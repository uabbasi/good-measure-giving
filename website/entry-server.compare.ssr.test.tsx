// @vitest-environment node
//
// /compare?eins=a,b loads the FULL per-charity files — the same rich payload
// the detail page gates — and until this test existed it rendered all of it to
// anonymous visitors. The route was reachable in two clicks: tick two boxes on
// /browse, press Compare. That routed straight around the detail page's sign-in
// wall, and it leaked rich_narrative.ideal_donor_profile ("Best for") verbatim,
// not a derived summary.
//
// SSR is structurally anonymous here — AppProviders contains no FirebaseProvider,
// so useCommunityMember() is false for every server render regardless of who
// asks. That makes this the right place to pin the anonymous boundary.
//
// Nothing crawlable is lost by gating: scripts/prerender.ts emits only the empty
// /compare/, so the ?eins= state has no prerendered content to forfeit.

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { render } from './entry-server';

const DATA_DIR = path.resolve(__dirname, 'data/charities');
const IRC_EIN = '13-5660870';
const DWB_EIN = '13-3433452';

const loadRaw = (ein: string): unknown =>
  JSON.parse(fs.readFileSync(path.join(DATA_DIR, `charity-${ein}.json`), 'utf8'));

const renderCompare = (eins: string[]): Promise<string> =>
  render(`/compare/?eins=${eins.join(',')}`, [
    { queryKey: ['charities'], data: { summaries: [], charities: [] } },
    ...eins.map((ein) => ({ queryKey: ['charity', ein], data: loadRaw(ein) })),
  ]);

// Bare /compare/ with no query string is a real entry point — it is the footer
// nav link, so it takes zero interaction to reach — and it falls back to the
// top 4 charities by score rather than rendering nothing. Gating has to hold on
// that path too, and it resolves its EINs by a different code path.
const renderBareCompare = (eins: string[]): Promise<string> =>
  render('/compare/', [
    {
      queryKey: ['charities'],
      data: {
        summaries: [],
        charities: eins.map((ein) => loadRaw(ein)),
      },
    },
    ...eins.map((ein) => ({ queryKey: ['charity', ein], data: loadRaw(ein) })),
  ]);

describe('GmgCompare SSR — anonymous visitors get identity, not the evaluation', () => {
  it('shows which charities are being compared, and a sign-in prompt instead of the analysis', async () => {
    const html = await renderCompare([IRC_EIN, DWB_EIN]);

    // Identity stays: the page is still a real comparison of real charities.
    expect(html).toContain('International Rescue Committee');
    expect(html).toContain('Doctors Without Borders');
    expect(html).toContain('Humanitarian Relief'); // cause
    expect(html).toContain('Accepts Zakat'); // wallet

    // One prompt, in place of the evaluative rows.
    expect(html).toContain('Full comparison');
    expect(html).toContain('sign in to see them');
  }, 20000);

  it('does not leak any evaluative content to an anonymous visitor', async () => {
    const html = await renderCompare([IRC_EIN, DWB_EIN]);

    // Row labels — their presence would mean the gated block rendered at all.
    for (const label of [
      'GMG rating',
      'Donor fit',
      'Program efficiency',
      'Reserves',
      'Cost / beneficiary',
      'Best for',
      'CRITERION BY CRITERION',
    ]) {
      expect(html).not.toContain(label);
    }

    // The per-criterion breakdown, which is the bulk of what leaked.
    for (const criterion of ['Financial Health', 'Theory of Change', 'Track Record']) {
      expect(html).not.toContain(criterion);
    }

    // And the narrative itself. `bestForSummary` is rich_narrative's
    // ideal_donor_profile — the exact text the detail page hides — so a
    // substring of the real value is the sharpest possible assertion.
    const irc = loadRaw(IRC_EIN) as {
      amalEvaluation?: { rich_narrative?: { ideal_donor_profile?: { best_for_summary?: string } } };
    };
    const bestFor = irc.amalEvaluation?.rich_narrative?.ideal_donor_profile?.best_for_summary;
    if (bestFor && bestFor.length > 40) {
      expect(html).not.toContain(bestFor.slice(0, 40));
    }
  }, 20000);

  it('holds on bare /compare/ too, which the footer links to and which auto-picks 4 charities', async () => {
    const html = await renderBareCompare([IRC_EIN, DWB_EIN]);

    // It did resolve subjects (otherwise the absence assertions below would
    // pass vacuously on an empty page).
    expect(html).toContain('International Rescue Committee');
    expect(html).toContain('Full comparison');

    for (const label of ['GMG rating', 'Cost / beneficiary', 'Best for', 'CRITERION BY CRITERION']) {
      expect(html).not.toContain(label);
    }
  }, 20000);
});

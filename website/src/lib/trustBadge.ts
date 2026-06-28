// Builders for the SEO "link engine": self-contained, copy-paste HTML snippets
// that rated charities (and peers) can paste onto their own sites to link back
// to Good Measure Giving with descriptive, dofollow anchor text.
//
// These strings are embedded on THIRD-PARTY sites, so they cannot rely on our
// CSS, fonts, or React. Everything is inline-styled with the GMG "sage on bone"
// palette (see src/components/gmg/tokens.ts) so the badge stays on-brand wherever
// it lands. Links are plain <a> (dofollow by default) — the whole point is to
// pass link equity back to us.

export const SITE_URL = 'https://goodmeasuregiving.org';

// Sage-on-bone palette, hard-coded so the snippet is portable (mirrors the
// light palette in src/components/gmg/tokens.ts).
const BADGE_COLORS = {
  bone: '#f4efde',
  card: '#ebe4cc',
  ink: '#13160e',
  sub: '#5e6356',
  sub2: '#8a8e80',
  rule: '#dfdac7',
  rule2: '#c9c2a8',
  sage: '#3d4a30',
} as const;

const SERIF = "Georgia, 'Times New Roman', serif";

export interface BadgeCharity {
  ein: string;
  name: string;
  /** GMG Score = impact + alignment − risk (0–100). NOT Charity Navigator's rating. */
  score: number;
}

/** Trailing-slash charity URL — matches our canonical/sitemap convention. */
export const charityUrl = (ein: string): string => `${SITE_URL}/charity/${ein}/`;

/**
 * The embeddable trust badge: an inline-styled <a> that shows
 * "Independently rated by Good Measure Giving" plus the charity's GMG score,
 * linking (dofollow) to that charity's detail page. Self-contained, no external
 * CSS. Returned as a single trimmed HTML string ready to paste.
 */
export function buildTrustBadgeSnippet(charity: BadgeCharity): string {
  const url = charityUrl(charity.ein);
  const c = BADGE_COLORS;
  return `<a href="${url}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:12px;max-width:330px;padding:10px 14px;border:1px solid ${c.rule2};border-radius:10px;background:${c.bone};color:${c.ink};font-family:${SERIF};line-height:1.25;text-decoration:none;">
  <span style="display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;flex-shrink:0;border-radius:8px;background:${c.sage};color:${c.bone};font-weight:700;font-size:13px;letter-spacing:.02em;">GMG</span>
  <span style="display:flex;flex-direction:column;gap:1px;">
    <span style="font-size:11px;color:${c.sub};letter-spacing:.02em;">Independently rated by</span>
    <span style="font-size:14px;font-weight:700;color:${c.ink};">Good Measure Giving</span>
  </span>
  <span style="display:flex;flex-direction:column;align-items:flex-end;margin-left:auto;padding-left:10px;border-left:1px solid ${c.rule};">
    <span style="font-size:19px;font-weight:700;color:${c.sage};">${charity.score}<span style="font-size:11px;font-weight:400;color:${c.sub2};">/100</span></span>
    <span style="font-size:9px;color:${c.sub2};letter-spacing:.06em;text-transform:uppercase;">GMG Score</span>
  </span>
</a>`;
}

/**
 * Plain descriptive text-link snippets for partners who want a simple backlink
 * rather than the visual badge. Anchor text is keyword-rich on purpose.
 */
export function buildTextLinkSnippets(): { label: string; html: string }[] {
  return [
    {
      label: 'Link to our homepage',
      html: `<a href="${SITE_URL}/">Good Measure Giving — independent Muslim charity evaluations</a>`,
    },
    {
      label: 'Link to our methodology',
      html: `<a href="${SITE_URL}/methodology/">See how Good Measure Giving rates charities</a>`,
    },
    {
      label: 'Link to the best Muslim charities ranking',
      html: `<a href="${SITE_URL}/best-muslim-charities-in-usa/">Best Muslim charities in the USA, independently rated</a>`,
    },
  ];
}

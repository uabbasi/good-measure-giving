// Good Measure Giving — "Modern" motif "Link to Us" page (/link-to-us).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.
// The trust-badge HTML snippets + dofollow links come verbatim from src/lib/trustBadge.ts
// and must NOT be altered here — only the surrounding page chrome is restyled.

import React, { useState } from 'react';
import {
  GmgContentFrame,
  ContentHero,
  Em,
  Section,
  P,
  UL,
  ALink,
  Callout,
  CtaLink,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FONT_MONO } from '../src/components/gmg/tokens';
import type { GmgPalette } from '../src/components/gmg/tokens';
import {
  buildTrustBadgeSnippet,
  buildTextLinkSnippets,
  type BadgeCharity,
} from '../src/lib/trustBadge';

// A real, high-scoring charity used purely as the worked example so the badge
// preview links somewhere live. Partners swap the EIN + score for their own.
const EXAMPLE_CHARITY: BadgeCharity = {
  ein: '41-2046295',
  name: 'The Citizens Foundation USA',
  score: 87,
};

// Small copy-to-clipboard control, palette-styled.
const CopyButton: React.FC<{ p: GmgPalette; text: string }> = ({ p, text }) => {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  return (
    <button
      type="button"
      onClick={onCopy}
      style={{
        padding: '5px 12px',
        borderRadius: 99,
        border: `1px solid ${copied ? p.accent : p.rule2}`,
        background: copied ? p.accent : 'transparent',
        color: copied ? p.bg : p.sub,
        fontSize: 12,
        fontWeight: 500,
        cursor: 'pointer',
        fontFamily: FONT_MONO,
      }}
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
};

// A labelled, copyable code block holding an HTML snippet (verbatim).
const SnippetBlock: React.FC<{ p: GmgPalette; title: string; snippet: string }> = ({ p, title, snippet }) => (
  <div style={{ borderRadius: 12, border: `1px solid ${p.rule}`, background: p.bg2, overflow: 'hidden' }}>
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 14px',
        borderBottom: `1px solid ${p.rule}`,
      }}
    >
      <span style={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: '0.04em', color: p.sub }}>{title}</span>
      <CopyButton p={p} text={snippet} />
    </div>
    <pre
      style={{
        margin: 0,
        padding: '12px 14px',
        fontFamily: FONT_MONO,
        fontSize: 12,
        lineHeight: 1.6,
        color: p.sub,
        overflowX: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
      }}
    >
      <code>{snippet}</code>
    </pre>
  </div>
);

export const LinkToUsPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  React.useEffect(() => {
    document.title = 'Link to Us | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const badgeSnippet = buildTrustBadgeSnippet(EXAMPLE_CHARITY);
  const textLinks = buildTextLinkSnippets();

  return (
    <GmgContentFrame isDark={isDark} maxWidth={760}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <ContentHero
              ctx={ctx}
              kicker="For Charities"
              title={
                <>
                  Link to <Em p={p}>us.</Em>
                </>
              }
              lead="Rated by Good Measure Giving? Show it. Copy a badge or link below to point your supporters to your independent evaluation — and help donors find trustworthy charities."
            />

            <Section ctx={ctx} title="Why link to your evaluation" first>
              <P p={p}>
                Good Measure Giving is an independent evaluator. We don't take money from the charities we rate, which
                means a link to your evaluation is a third-party signal of transparency — the kind of trust marker
                donors look for before they give.
              </P>
              <UL
                p={p}
                items={[
                  "Show supporters you've been independently reviewed on impact, alignment, and transparency.",
                  'Give donors a one-click path to the evidence behind your work.',
                ]}
              />
              <P p={p} muted>
                These badges and links are free to use. We just ask that the link points to your live evaluation and
                isn't altered to misrepresent your score.
              </P>
            </Section>

            <Section ctx={ctx} title="The trust badge">
              <P p={p} muted>
                Paste this badge onto your site. It shows your GMG score and links back to your full evaluation. Here's
                how it looks for{' '}
                <ALink p={p} to={`/charity/${EXAMPLE_CHARITY.ein}`}>
                  {EXAMPLE_CHARITY.name}
                </ALink>
                :
              </P>

              {/* Live preview — rendered from the exact same string that gets copied. */}
              <div
                style={{
                  borderRadius: 12,
                  border: `1px solid ${p.rule}`,
                  background: p.bg3,
                  padding: 28,
                  marginBottom: 14,
                  display: 'flex',
                  justifyContent: 'center',
                }}
              >
                <div dangerouslySetInnerHTML={{ __html: badgeSnippet }} />
              </div>

              <SnippetBlock p={p} title="Trust badge HTML" snippet={badgeSnippet} />

              <div style={{ marginTop: 14 }}>
                <Callout p={p} tone="info">
                  <strong>Using it on your own page?</strong> Swap two things for your charity: the URL's EIN (
                  <code style={{ fontFamily: FONT_MONO }}>{EXAMPLE_CHARITY.ein}</code>) and the score number (
                  <code style={{ fontFamily: FONT_MONO }}>{EXAMPLE_CHARITY.score}</code>). Both appear on your evaluation
                  page. Not sure of your numbers?{' '}
                  <a href="mailto:hello@goodmeasuregiving.org" style={{ color: p.accent, fontWeight: 500 }}>
                    Email us
                  </a>{' '}
                  and we'll send a ready-made snippet.
                </Callout>
              </div>
            </Section>

            <Section ctx={ctx} title="Plain text links">
              <P p={p} muted>Prefer a simple link? Drop any of these into a blog post, footer, or transparency page.</P>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {textLinks.map((link) => (
                  <SnippetBlock key={link.label} p={p} title={link.label} snippet={link.html} />
                ))}
              </div>
            </Section>

            <Section ctx={ctx} title="Brand assets">
              <P p={p} muted>
                Need our logo for a partners page or press mention? Use these. Please don't alter the colors or stretch
                the mark.
              </P>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 14 }}>
                {[
                  { src: '/favicon.svg', label: 'Logo mark (SVG)', cta: 'Download SVG', rounded: false },
                  { src: '/apple-touch-icon.png', label: 'App icon (PNG)', cta: 'Download PNG', rounded: true },
                ].map((asset) => (
                  <div
                    key={asset.src}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 16,
                      padding: '18px 20px',
                      borderRadius: 12,
                      border: `1px solid ${p.rule}`,
                      background: p.card,
                    }}
                  >
                    <img
                      src={asset.src}
                      alt={`Good Measure Giving ${asset.label}`}
                      width={48}
                      height={48}
                      style={asset.rounded ? { borderRadius: 10 } : undefined}
                    />
                    <div>
                      <p style={{ margin: 0, fontWeight: 600, color: p.fg }}>{asset.label}</p>
                      <a
                        href={asset.src}
                        download
                        style={{ display: 'inline-block', marginTop: 4, fontSize: 14, color: p.accent, fontWeight: 500 }}
                      >
                        {asset.cta}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </Section>

            <Section ctx={ctx}>
              <div style={{ textAlign: 'center', paddingTop: 8 }}>
                <P p={p} muted>Read how we score charities, or get in touch and we'll help you set up the badge.</P>
                <CtaLink p={p} to="/methodology">
                  See our methodology →
                </CtaLink>
              </div>
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

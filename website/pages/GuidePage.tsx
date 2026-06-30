// Good Measure Giving — "Modern" motif Guide article page (/guides/:slug).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useEffect } from 'react';
import { useParams, Navigate, Link } from 'react-router-dom';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Section,
  P,
  Callout,
  CardGrid,
  LinkCard,
  FaqList,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FONT_MONO } from '../src/components/gmg/tokens';
import { useGuide } from '../src/hooks/useGuides';

export const GuidePage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { slug } = useParams<{ slug: string }>();
  const { guide, loading, notFound } = useGuide(slug || '');

  useEffect(() => {
    if (guide) document.title = guide.metaTitle;
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [guide]);

  if (notFound) return <Navigate to="/guides" replace />;

  return (
    <GmgContentFrame isDark={isDark} maxWidth={760}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;

        if (loading || !guide) {
          return <P p={p} muted>Loading guide…</P>;
        }

        const updated = new Date(guide.updatedOn).toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        });

        return (
          <>
            <Breadcrumb
              p={p}
              trail={[{ label: 'Home', to: '/' }, { label: 'Guides', to: '/guides' }, { label: guide.title }]}
            />

            <ContentHero
              ctx={ctx}
              kicker={`${guide.readingTimeMinutes} min read · Updated ${updated}`}
              title={guide.title}
            />

            <Callout p={p} tone="info" title="TL;DR">
              {guide.tldr}
            </Callout>

            {guide.sections.map((section, i) => (
              <Section key={i} ctx={ctx} title={section.heading} first={i === 0}>
                {section.paragraphs.map((para, j) => (
                  <P key={j} p={p}>{para}</P>
                ))}
              </Section>
            ))}

            {guide.featuredCharities && guide.featuredCharities.length > 0 && (
              <Section ctx={ctx} title="Charities featured in this guide">
                <CardGrid min={260}>
                  {guide.featuredCharities.map((fc) => (
                    <LinkCard key={fc.ein} p={p} to={`/charity/${fc.ein}`} title={fc.name} desc={fc.blurb} />
                  ))}
                </CardGrid>
              </Section>
            )}

            {guide.callouts && guide.callouts.length > 0 && (
              <Section ctx={ctx}>
                {guide.callouts.map((c, i) => (
                  <Callout key={i} p={p} tone="caution" title={c.label}>
                    {c.text}
                  </Callout>
                ))}
              </Section>
            )}

            <Section ctx={ctx} title="Frequently asked questions">
              <FaqList p={p} items={guide.faq.map((f) => ({ q: f.q, a: f.a }))} />
            </Section>

            {guide.sources && guide.sources.length > 0 && (
              <Section ctx={ctx} title="Sources & further reading">
                <P p={p} muted>
                  This guide presents broadly held positions in Sunni fiqh and names the schools where they differ. The
                  references below are where we drew them from — read each position in its own words. None of this is a
                  fatwa.
                </P>
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {guide.sources.map((s, i) => (
                    <li key={i} style={{ fontSize: 15, lineHeight: 1.6, color: p.fg }}>
                      {s.url ? (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: p.accent, fontWeight: 500, textDecoration: 'none' }}
                        >
                          {s.title}
                        </a>
                      ) : (
                        <span style={{ fontWeight: 500 }}>{s.title}</span>
                      )}
                      <span style={{ color: p.sub }}> — {s.publisher}</span>
                      {s.note && <div style={{ color: p.sub2, fontSize: 13.5, marginTop: 2 }}>{s.note}</div>}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {guide.relatedCauses && guide.relatedCauses.length > 0 && (
              <Section ctx={ctx} title="Related cause areas">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {guide.relatedCauses.map((rc) => (
                    <Link
                      key={rc}
                      to={`/causes/${rc}`}
                      style={{
                        display: 'inline-block',
                        padding: '6px 14px',
                        borderRadius: 99,
                        border: `1px solid ${p.rule2}`,
                        background: p.bg2,
                        color: p.sub,
                        fontSize: 13.5,
                        textDecoration: 'none',
                        textTransform: 'capitalize',
                        fontFamily: FONT_MONO,
                        letterSpacing: '0.02em',
                      }}
                    >
                      {rc.replace(/-/g, ' ')}
                    </Link>
                  ))}
                </div>
              </Section>
            )}
          </>
        );
      }}
    </GmgContentFrame>
  );
};

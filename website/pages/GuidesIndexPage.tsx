// Good Measure Giving — "Modern" motif Guides index page (/guides).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useEffect } from 'react';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Em,
  P,
  CardGrid,
  LinkCard,
  type ContentCtx,
} from '../src/components/gmg/content';
import { useGuides } from '../src/hooks/useGuides';

export const GuidesIndexPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { guides, loading } = useGuides();

  useEffect(() => {
    document.title = 'Guides | Good Measure Giving';
    return () => {
      document.title = 'Good Measure Giving | Muslim Charity Evaluator';
    };
  }, []);

  return (
    <GmgContentFrame isDark={isDark} maxWidth={760}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <Breadcrumb p={p} trail={[{ label: 'Home', to: '/' }, { label: 'Guides' }]} />

            <ContentHero
              ctx={ctx}
              kicker="Guides"
              title={
                <>
                  Evergreen <Em p={p}>guides.</Em>
                </>
              }
              lead="Evergreen guides to evaluating Muslim charities, planning zakat, and thinking about impact."
            />

            {loading ? (
              <P p={p} muted>
                Loading guides…
              </P>
            ) : guides.length === 0 ? (
              <P p={p} muted>
                No guides published yet.
              </P>
            ) : (
              <CardGrid min={260}>
                {guides.map((g) => (
                  <LinkCard
                    key={g.slug}
                    p={p}
                    to={`/guides/${g.slug}`}
                    title={g.title}
                    desc={g.description}
                    meta={`${g.readingTimeMinutes} min read`}
                  />
                ))}
              </CardGrid>
            )}
          </>
        );
      }}
    </GmgContentFrame>
  );
};

export default GuidesIndexPage;

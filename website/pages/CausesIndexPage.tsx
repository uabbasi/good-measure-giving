// Good Measure Giving — "Modern" motif Causes index page (/causes).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useEffect } from 'react';
import { causePath } from '../src/lib/paths';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Em,
  P,
  ALink,
  CardGrid,
  LinkCard,
  type ContentCtx,
} from '../src/components/gmg/content';
import causesData from '../data/causes/causes.json';

interface CauseData {
  slug: string;
  category: string;
  displayName: string;
  intro: string;
}

const CAUSES: CauseData[] = causesData.causes as CauseData[];

export const CausesIndexPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  useEffect(() => {
    document.title = 'Causes | Good Measure Giving';
    return () => {
      document.title = 'Good Measure Giving | Muslim Charity Evaluator';
    };
  }, []);

  return (
    <GmgContentFrame isDark={isDark} maxWidth={960}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <Breadcrumb p={p} trail={[{ label: 'Home', to: '/' }, { label: 'Causes' }]} />

            <ContentHero
              ctx={ctx}
              kicker="Causes"
              title={
                <>
                  Browse charities by <Em p={p}>cause.</Em>
                </>
              }
              lead={`Explore ${CAUSES.length} cause areas in the Muslim charity ecosystem, each evaluated by Good Measure Giving on impact, alignment, and financial transparency.`}
            />

            <P p={p}>
              <ALink p={p} to="/best-muslim-charities-in-usa/">
                See the best Muslim charities in the USA, ranked by GMG score →
              </ALink>
            </P>

            <div style={{ marginTop: 28 }}>
              <CardGrid min={260}>
                {CAUSES.map((c) => (
                  <LinkCard key={c.slug} p={p} to={causePath(c.slug)} title={c.displayName} desc={c.intro} />
                ))}
              </CardGrid>
            </div>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

export default CausesIndexPage;

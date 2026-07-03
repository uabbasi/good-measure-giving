// Good Measure Giving — "Modern" motif Zakat Calculator hub (/zakat-calculator).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useEffect } from 'react';
import { zakatCalculatorPath } from '../src/lib/paths';
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
import { Tag } from '../src/components/gmg/primitives';
import { KNOWN_ASSET_SLUGS } from '../scripts/lib/calculator-seo';
import { useCalculatorData } from '../src/hooks/useCalculatorData';

const SLUG_TO_LABEL: Record<string, string> = {
  'cash-savings': 'Cash & Savings',
  'gold-silver': 'Gold & Silver',
  stocks: 'Stocks & Investments',
  '401k-retirement': '401(k) & Retirement',
  crypto: 'Cryptocurrency',
  'business-assets': 'Business Assets',
  'real-estate': 'Real Estate',
};

export const ZakatCalculatorHubPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { data, loading } = useCalculatorData();

  useEffect(() => {
    document.title = 'Zakat Calculator 2026 | Good Measure Giving';
    return () => {
      document.title = 'Good Measure Giving | Muslim Charity Evaluator';
    };
  }, []);

  const availableSlugs = new Set((data?.assets || []).map((a) => a.slug));

  return (
    <GmgContentFrame isDark={isDark} maxWidth={760}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <Breadcrumb p={p} trail={[{ label: 'Home', to: '/' }, { label: 'Zakat Calculator' }]} />

            <ContentHero
              ctx={ctx}
              kicker="Zakat Calculator"
              title={
                <>
                  Zakat Calculator <Em p={p}>2026.</Em>
                </>
              }
              lead={
                data?.hub.heroText ??
                'Calculate the zakat owed on your assets. Start with the asset type most relevant to you.'
              }
            />

            {loading ? (
              <P p={p} muted>
                Loading…
              </P>
            ) : (
              <CardGrid min={260}>
                {KNOWN_ASSET_SLUGS.map((slug) => {
                  const available = availableSlugs.has(slug);
                  const label = SLUG_TO_LABEL[slug] ?? slug.replace(/-/g, ' ');
                  return (
                    <LinkCard
                      key={slug}
                      p={p}
                      to={zakatCalculatorPath(slug)}
                      title={`Zakat on ${label}`}
                      meta={
                        available ? undefined : (
                          <Tag p={p} tone="muted">
                            Coming soon
                          </Tag>
                        )
                      }
                    />
                  );
                })}
              </CardGrid>
            )}
          </>
        );
      }}
    </GmgContentFrame>
  );
};

export default ZakatCalculatorHubPage;

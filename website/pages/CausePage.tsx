// Good Measure Giving — "Modern" motif Cause hub page (/causes/:slug).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useEffect, useMemo } from 'react';
import { useParams, Navigate } from 'react-router-dom';
import { charityPath, paths } from '../src/lib/paths';
import { useCharities } from '../src/hooks/useCharities';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Section,
  P,
  CardGrid,
  LinkCard,
  FaqList,
  type ContentCtx,
} from '../src/components/gmg/content';
import { slugToCategory, filterCharitiesByCategory, isCuratedMuslimCharity, type HubCharity } from '../scripts/lib/cause-seo';
import causesData from '../data/causes/causes.json';

interface CauseData {
  slug: string;
  category: string;
  displayName: string;
  intro: string;
  faq: Array<{ q: string; a: string }>;
}

const CAUSES: CauseData[] = (causesData.causes as CauseData[]);

export const CausePage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { slug } = useParams<{ slug: string }>();
  const { summaries, loading } = useCharities();

  const cause = useMemo(() => CAUSES.find((c) => c.slug === slug), [slug]);
  const category = slug ? slugToCategory(slug) : null;

  useEffect(() => {
    if (cause) {
      document.title = `Best Muslim ${cause.displayName} Charities | Good Measure Giving`;
    }
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [cause]);

  // These pages are titled "Best Muslim {Cause} Charities" — list only Muslim
  // orgs, not every charity that happens to share the cause category. Filtering
  // logic is preserved exactly so the count matches the prerender ItemList JSON-LD.
  const charities = useMemo(() => {
    if (!category) return [] as HubCharity[];
    const pool: HubCharity[] = (summaries ?? []).map((c) => ({
      ein: c.ein,
      name: c.name,
      primaryCategory: c.primaryCategory ?? null,
      amalScore: c.amalScore ?? null,
      walletTag: c.walletTag ?? null,
      isMuslimCharity: c.isMuslimCharity,
      hideFromCurated: c.hideFromCurated,
    }));
    return filterCharitiesByCategory(pool.filter(isCuratedMuslimCharity), category);
  }, [summaries, category]);

  if (!slug || !cause || !category) {
    return <Navigate to="/causes" replace />;
  }

  return (
    <GmgContentFrame isDark={isDark} maxWidth={960}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <Breadcrumb
              p={p}
              trail={[{ label: 'Home', to: '/' }, { label: 'Causes', to: paths.causes }, { label: cause.displayName }]}
            />

            <ContentHero
              ctx={ctx}
              kicker="Cause"
              title={`Best Muslim ${cause.displayName} Charities`}
              lead={cause.intro}
            />

            <Section ctx={ctx} title="Evaluated charities" first>
              {loading ? (
                <P p={p} muted>Loading charities…</P>
              ) : charities.length === 0 ? (
                <P p={p} muted>No charities evaluated in this category yet.</P>
              ) : (
                <CardGrid min={260}>
                  {charities.map((c) => (
                    <LinkCard
                      key={c.ein}
                      p={p}
                      to={charityPath(c.ein)}
                      title={c.name}
                      meta={c.amalScore != null ? `${c.amalScore}/100` : undefined}
                    />
                  ))}
                </CardGrid>
              )}
            </Section>

            <Section ctx={ctx} title="Frequently asked questions">
              <FaqList p={p} items={cause.faq.map((f) => ({ q: f.q, a: f.a }))} />
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

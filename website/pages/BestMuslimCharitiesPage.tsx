// Good Measure Giving — "Modern" motif ranked hub (/best-muslim-charities-in-usa).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { charityPath } from '../src/lib/paths';
import { useCharities } from '../src/hooks/useCharities';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Section,
  P,
  ALink,
  CardGrid,
  LinkCard,
  FaqList,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FONT_DISPLAY, FONT_MONO } from '../src/components/gmg/tokens';
import type { GmgPalette } from '../src/components/gmg/tokens';
import { filterMuslimCharities, type HubCharity } from '../scripts/lib/muslim-hub';
import hubData from '../data/best-muslim-charities.json';

interface HubCopy {
  intro: string;
  introSecondary: string;
  faq: Array<{ q: string; a: string }>;
}

const COPY = hubData as HubCopy;
const TOP_N = 20;

const isZakatEligible = (c: HubCharity) => c.walletTag === 'ZAKAT-ELIGIBLE';

// "Accepts Zakat" pill — sage "positive" semantic palette. Label matches the
// site-wide walletLabel wording used on browse/compare/detail.
const ZakatPill: React.FC<{ p: GmgPalette }> = ({ p }) => (
  <span
    style={{
      display: 'inline-block',
      fontFamily: FONT_MONO,
      fontSize: 10,
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      padding: '2px 8px',
      borderRadius: 99,
      background: p.posBg,
      color: p.pos,
    }}
  >
    Accepts Zakat
  </span>
);

// Ranked row for the top-N list — rank numeral + name (+ zakat pill) + score.
const RankedRow: React.FC<{ p: GmgPalette; rank: number; c: HubCharity }> = ({ p, rank, c }) => (
  <li>
    <Link
      to={charityPath(c.ein)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '14px 18px',
        borderRadius: 12,
        border: `1px solid ${p.rule}`,
        background: p.card,
        textDecoration: 'none',
        color: p.fg,
      }}
    >
      <span
        style={{
          fontFamily: FONT_DISPLAY,
          fontSize: 20,
          color: p.sub2,
          width: 30,
          flexShrink: 0,
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {rank}
      </span>
      <span style={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {c.name}
        </span>
        {isZakatEligible(c) && <span><ZakatPill p={p} /></span>}
      </span>
      <span
        style={{
          fontFamily: FONT_MONO,
          fontSize: 14,
          fontWeight: 600,
          color: p.sub,
          flexShrink: 0,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {c.amalScore}/100
      </span>
    </Link>
  </li>
);

export const BestMuslimCharitiesPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { summaries, loading } = useCharities();
  const year = new Date().getFullYear();

  useEffect(() => {
    document.title = `Best Muslim Charities in the USA (${year}) | Good Measure Giving`;
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [year]);

  // Ranking + filtering preserved byte-identical so the prerender ItemList JSON-LD
  // (top-20 by GMG score) still matches the rendered list.
  const { ranked, pending } = useMemo(() => {
    const pool: HubCharity[] = (summaries ?? []).map((c) => ({
      ein: c.ein,
      name: c.name,
      primaryCategory: c.primaryCategory ?? null,
      amalScore: c.amalScore ?? null,
      walletTag: c.walletTag ?? null,
      isMuslimCharity: c.isMuslimCharity,
      hideFromCurated: c.hideFromCurated,
    }));
    const all = filterMuslimCharities(pool);
    return {
      ranked: all.filter((c) => c.amalScore != null),
      pending: all.filter((c) => c.amalScore == null),
    };
  }, [summaries]);

  const topRanked = ranked.slice(0, TOP_N);
  const remainingRanked = ranked.slice(TOP_N);

  return (
    <GmgContentFrame isDark={isDark} maxWidth={960}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        return (
          <>
            <Breadcrumb p={p} trail={[{ label: 'Home', to: '/' }, { label: 'Best Muslim Charities' }]} />

            <ContentHero
              ctx={ctx}
              kicker="Ranked Hub"
              title={`Best Muslim Charities in the USA (${year}, Independently Rated)`}
            />

            <P p={p}>{COPY.intro}</P>
            <P p={p}>{COPY.introSecondary}</P>

            {loading ? (
              <P p={p} muted>Loading charities…</P>
            ) : (
              <>
                <Section ctx={ctx} title={`Top ${Math.min(TOP_N, topRanked.length)} by GMG Score`}>
                  {topRanked.length === 0 ? (
                    <P p={p} muted>No ranked charities yet.</P>
                  ) : (
                    <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {topRanked.map((c, i) => (
                        <RankedRow key={c.ein} p={p} rank={i + 1} c={c} />
                      ))}
                    </ol>
                  )}
                </Section>

                {remainingRanked.length > 0 && (
                  <Section ctx={ctx} title="More Rated Muslim Charities">
                    <CardGrid min={260}>
                      {remainingRanked.map((c, i) => (
                        <LinkCard
                          key={c.ein}
                          p={p}
                          to={charityPath(c.ein)}
                          title={`${TOP_N + i + 1}. ${c.name}`}
                          meta={isZakatEligible(c) ? `Accepts Zakat · ${c.amalScore}/100` : `${c.amalScore}/100`}
                        />
                      ))}
                    </CardGrid>
                  </Section>
                )}

                {pending.length > 0 && (
                  <Section ctx={ctx} title="Evaluated — Score Pending">
                    <P p={p} muted>
                      These Muslim charities have been evaluated and published, but their GMG score is not yet finalized.
                      They are not ranked.
                    </P>
                    <CardGrid min={260}>
                      {pending.map((c) => (
                        <LinkCard
                          key={c.ein}
                          p={p}
                          to={charityPath(c.ein)}
                          title={c.name}
                          meta={isZakatEligible(c) ? 'Accepts Zakat' : undefined}
                        />
                      ))}
                    </CardGrid>
                  </Section>
                )}

                <Section ctx={ctx}>
                  <ALink p={p} to="/browse/">
                    Browse all evaluated charities →
                  </ALink>
                </Section>
              </>
            )}

            <Section ctx={ctx} title="Frequently asked questions">
              <FaqList p={p} items={COPY.faq.map((f) => ({ q: f.q, a: f.a }))} />
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

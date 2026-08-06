// Good Measure Giving — "Modern" motif charity detail.
// Reachable via /charity/:id. Renders real charity data in the
// sage-on-bone, Harvey-ball design from the claude.ai handoff.

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { charityPath } from '../../lib/paths';
import { EDITION } from '../../config/siteVersion';
import { useCharities } from '../../hooks/useCharities';
import {
  selectSimilarCharities,
  classifyZakatStatus,
  type SimilarCharityCandidate,
} from '../../../scripts/lib/charity-seo';
import {
  GmgPalette,
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEMES,
  resolveFontVariant,
  type FontVariant,
} from './tokens';
import { ratingColor, riskTone } from './rating';
import {
  HarveyBall,
  RatingLabel,
  Tag,
  Kicker,
  Bismillah,
  Figure,
} from './primitives';
import { GmgNav } from './chrome';
import { GmgFooter } from './content';
import { useIsMobile } from './useIsMobile';
import { adaptCharity, GmgDimension } from './charityAdapter';
import { dataVintage } from './sections/dataVintage';
import { WhatTheyDo } from './sections/WhatTheyDo';
import { WhereMoneyGoes } from './sections/WhereMoneyGoes';
import { TrustTheNumbers } from './sections/TrustTheNumbers';
import { RunWell } from './sections/RunWell';
import { RightForYou } from './sections/RightForYou';
import { HowItCompares } from './sections/HowItCompares';
import { SectionRail, type RailSection } from './SectionRail';
import { CitedText, SourceList, collectCitations } from './CitedText';

const usd = (n: number | null): string => {
  if (n == null) return '—';
  const compact = Math.abs(n) >= 1_000_000;
  // For currency, leaving maximumFractionDigits at 1 forces the default
  // minimumFractionDigits (2) down to 1, so whole-dollar figures render as
  // "$851,150.0". Pin the minimum to 0 and only allow a decimal for the
  // compact "$1.5M" form.
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: compact ? 'compact' : 'standard',
    minimumFractionDigits: 0,
    maximumFractionDigits: compact ? 1 : 0,
  }).format(n);
};

const usdFull = (n: number | null): string =>
  n == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

// The six donor-question sections, in spine order — shared between the
// section list below and the SectionRail so the two can never drift apart.
const RAIL_SECTIONS: RailSection[] = [
  { id: 'what-they-do', label: 'What they do' },
  { id: 'money', label: 'Where money goes' },
  { id: 'trust', label: 'Trust the numbers' },
  { id: 'run-well', label: 'Run well' },
  { id: 'right-for-you', label: 'Right for you' },
  { id: 'compares', label: 'How it compares' },
];

// Module-scope cards — kept out of the render body so they keep a stable
// identity across renders (p + sectionBorder come in as props).

const DimensionCard: React.FC<{
  label: string;
  blurb: string;
  dim: GmgDimension;
  p: GmgPalette;
  sectionBorder: string;
}> = ({ label, blurb, dim, p, sectionBorder }) => (
  <div
    style={{
      border: sectionBorder,
      borderRadius: 6,
      padding: 14,
      background: p.bg2,
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
    }}
  >
    <Kicker p={p}>{label}</Kicker>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
      <HarveyBall rating={dim.overall} p={p} size={36} />
      <div>
        <Figure size={28} color={p.fg} italic>
          {dim.overall}
        </Figure>
        <div style={{ fontFamily: FONT_MONO, fontSize: 10, color: p.sub2, marginTop: 2 }}>
          {dim.score} / {dim.max}
        </div>
      </div>
    </div>
    <div style={{ fontSize: 11, color: p.sub2, lineHeight: 1.4 }}>{blurb}</div>
  </div>
);

const DimensionDetail: React.FC<{
  title: string;
  dim: GmgDimension;
  color: string;
  p: GmgPalette;
  sectionBorder: string;
}> = ({ title, dim, color, p, sectionBorder }) => (
  <div style={{ border: sectionBorder, borderRadius: 6, padding: 16, background: p.bg }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
      <Figure size={26} color={color} italic>
        {title}
      </Figure>
      <RatingLabel rating={dim.overall} p={p} size={14} />
    </div>
    <div style={{ borderTop: sectionBorder, marginTop: 8 }}>
      {dim.criteria.map((cr) => (
        <div
          key={cr.name}
          style={{
            display: 'grid',
            gridTemplateColumns: '20px 1fr auto',
            gap: 12,
            padding: '10px 0',
            borderBottom: sectionBorder,
            alignItems: 'start',
          }}
        >
          <HarveyBall rating={cr.rating} p={p} size={14} />
          <div>
            <div style={{ fontSize: 13, color: p.fg, fontWeight: 500 }}>
              {cr.name}
              <span style={{ fontFamily: FONT_MONO, fontSize: 10, color: p.sub2, marginLeft: 8 }}>
                {cr.scored}/{cr.possible}
              </span>
            </div>
            <div style={{ fontSize: 11, color: p.sub, marginTop: 2, lineHeight: 1.45 }}>{cr.note}</div>
          </div>
          <span style={{ fontSize: 11.5, color: ratingColor(cr.rating, p), fontWeight: 500 }}>
            {cr.rating}
          </span>
        </div>
      ))}
    </div>
    {dim.flag && (
      <div
        style={{
          marginTop: 12,
          padding: '10px 12px',
          background: p.cautionBg,
          borderRadius: 4,
          fontSize: 11.5,
          color: p.caution,
          lineHeight: 1.5,
        }}
      >
        <span style={{ marginRight: 6 }}>↗</span>
        {dim.flag}
      </div>
    )}
  </div>
);

export const GmgCharityDetail: React.FC<{ charity: any; isDark: boolean }> = ({
  charity,
  isDark,
}) => {
  const p = gmgPalette(isDark);
  const c = adaptCharity(charity);
  const isMobile = useIsMobile();
  const { summaries } = useCharities();

  // Select up to 5 same-category/same-zakatStatus charities, sorted by score.
  // Uses the canonical selector from scripts/lib/charity-seo so logic is shared
  // with the SSG prerender and the SimilarCharities component.
  const similarCharities = useMemo((): SimilarCharityCandidate[] => {
    if (!summaries || summaries.length === 0) return [];
    const currentEin = charity?.ein ?? '';
    const category = charity?.primaryCategory ?? charity?.category ?? '';
    const zakatStatus = classifyZakatStatus({
      walletTag: charity?.amalEvaluation?.wallet_tag ?? null,
      zakatClassification: charity?.amalEvaluation?.zakat_classification ?? null,
    });
    const pool: SimilarCharityCandidate[] = summaries.map((s) => ({
      ein: s.ein,
      name: s.name,
      category: s.primaryCategory ?? s.category ?? '',
      amalScore: s.amalScore ?? null,
      zakatStatus: classifyZakatStatus({
        walletTag: s.walletTag ?? null,
        zakatClassification: s.zakatClassification ?? null,
      }),
    }));
    return selectSimilarCharities({ currentEin, category, zakatStatus, pool, limit: 5 });
  }, [summaries, charity]);
  const padX = isMobile ? 16 : 24;

  const variant: FontVariant = resolveFontVariant(
    typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('type') : null,
  );
  const ft = FONT_THEMES[variant];

  const sectionBorder = `1px solid ${p.rule}`;
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  };

  // Data vintage: 990 filings run ~2 years behind; older than that is a
  // mild red flag worth surfacing to donors. See dataVintage.ts for why age
  // comes from the pipeline rather than the wall clock. Only `fyDated` is
  // needed here — the stat strip's "· dated" note is the only consumer left
  // on this page; TrustTheNumbers computes its own copy for the full badge.
  const { fyDated } = dataVintage(c);

  const statCells: [string, string, string][] = [
    ['Cost / benef.', c.costPerBeneficiary != null ? usdFull(c.costPerBeneficiary) : '—', c.costPerBeneficiary != null ? 'per person' : 'not reported'],
    ['Program ratio', c.programRatioPct != null ? `${c.programRatioPct}%` : '—', 'of expense'],
    ['Reserves', c.reserveMonths != null ? `${c.reserveMonths} mo` : '—', 'working capital'],
    ['Revenue', usd(c.totalRevenue), c.fiscalYear ? `FY${c.fiscalYear}${fyDated ? ' · dated' : ''}` : 'IRS 990'],
    ['Track record', c.trackRecordYears != null ? `${c.trackRecordYears} yr` : '—', c.founded ? `est. ${c.founded}` : ''],
    ['Risk', c.riskLevel, 'overall'],
  ];

  return (
    <div style={{ background: p.bg, color: p.fg, fontFamily: FONT_TEXT, minHeight: '100vh', ...fontVars }}>
      {/* Motif nav — self-contained (app chrome is suppressed for this view) */}
      <GmgNav p={p} isMobile={isMobile} />

      {/* Utility row — research metadata + live type switcher */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: `6px ${padX}px`,
          gap: 14,
          flexWrap: 'wrap',
          background: p.bg2,
          borderBottom: sectionBorder,
          color: p.sub,
          fontFamily: FONT_MONO,
          fontSize: 10.5,
          letterSpacing: '0.06em',
        }}
      >
        <span>EDITION {EDITION}</span>
        {c.updatedOn && <span>· UPDATED {c.updatedOn}</span>}
      </div>

      <Bismillah p={p} />

      {/* Header */}
      <section style={{ padding: `22px ${padX}px 18px`, borderBottom: sectionBorder }}>
        <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 460px', minWidth: 300 }}>
            <h1 style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: isMobile ? 34 : 56, lineHeight: 1.0, letterSpacing: ft.displayTracking, margin: 0 }}>
              {c.name}
            </h1>
            <div style={{ fontFamily: FONT_MONO, fontSize: 11, color: p.sub2, marginTop: 8, letterSpacing: '0.03em' }}>
              {[c.address, c.region, c.ein && `EIN ${c.ein}`, c.founded && `Founded ${c.founded}`].filter(Boolean).join(' · ')}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
              <Tag tone="accent" p={p}>{c.wallet}</Tag>
              {c.concerns.highest === 'high' && <Tag tone="neg" p={p}>High-severity concern</Tag>}
              {c.assessmentLabel && <Tag p={p}>{c.assessmentLabel}</Tag>}
              {c.archetypeLabel && <Tag p={p}>{c.archetypeLabel}</Tag>}
              {c.evidenceStage && <Tag p={p}>{c.evidenceStage}</Tag>}
              {c.category && <Tag p={p}>{c.category}</Tag>}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 16 }}>
              {c.donateUrl && (
                <a
                  href={c.donateUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ padding: '10px 16px', borderRadius: 99, background: p.chip, color: p.chipFg, fontSize: 12, fontWeight: 500, textDecoration: 'none' }}
                >
                  Donate ↗
                </a>
              )}
              <Link
                to={`/compare/?eins=${c.ein}`}
                style={{ padding: '10px 16px', borderRadius: 99, background: 'transparent', border: `1px solid ${p.rule}`, color: p.fg, fontSize: 12, textDecoration: 'none' }}
              >
                Compare
              </Link>
            </div>
          </div>

          {/* Rating cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, flex: isMobile ? '1 1 100%' : '0 1 400px', minWidth: isMobile ? 0 : 320 }}>
            <DimensionCard label="Impact" blurb="Indicators of effective programs" dim={c.impact} p={p} sectionBorder={sectionBorder} />
            <DimensionCard label="Alignment" blurb="Fit with Muslim donor priorities" dim={c.alignment} p={p} sectionBorder={sectionBorder} />
            <div
              style={{
                gridColumn: '1 / span 2',
                display: 'flex',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 8,
                padding: '8px 12px',
                border: sectionBorder,
                borderRadius: 6,
                background: p.bg2,
                fontSize: 11,
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: p.sub }}>
                <Kicker p={p}>GMG</Kicker>
                {c.overall ? (
                  <>
                    <HarveyBall rating={c.overall} p={p} size={14} />
                    <span style={{ color: ratingColor(c.overall, p), fontWeight: 500 }}>{c.overall}</span>
                  </>
                ) : (
                  <span style={{ color: p.sub2 }}>—</span>
                )}
              </span>
              {c.recommendationCue && (
                <span style={{ color: p.sub }}>
                  <Kicker p={p}>Fit</Kicker> {c.recommendationCue}
                </span>
              )}
              <span style={{ color: p.sub }}>
                <Kicker p={p}>Wallet</Kicker> {c.wallet}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Stat strip */}
      <section style={{ borderBottom: sectionBorder, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', background: p.bg2 }}>
        {statCells.map(([l, v, sub], i) => (
          <div key={l} style={{ padding: '12px 14px', borderRight: i < statCells.length - 1 ? sectionBorder : 'none', borderTop: i >= 7 ? sectionBorder : 'none' }}>
            <Kicker p={p}>{l}</Kicker>
            <div style={{ marginTop: 4 }}>
              <Figure size={24} color={l === 'Risk' ? (p[riskTone(c.riskLevel)] as string) : p.fg}>{v}</Figure>
            </div>
            <div style={{ fontSize: 10.5, color: p.sub2, marginTop: 2 }}>{sub}</div>
          </div>
        ))}
      </section>

      {/* The six donor-question sections, with a scroll-spy rail on desktop
          and a sticky jump menu on mobile (SectionRail switches on isMobile). */}
      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '160px 1fr', gap: isMobile ? 0 : 24 }}>
        {!isMobile && (
          <div style={{ paddingLeft: padX, paddingTop: 24 }}>
            <SectionRail sections={RAIL_SECTIONS} p={p} isMobile={false} />
          </div>
        )}
        <div style={{ minWidth: 0 }}>
          {isMobile && <SectionRail sections={RAIL_SECTIONS} p={p} isMobile />}
          <WhatTheyDo c={c} p={p} isMobile={isMobile} padX={padX} />
          <WhereMoneyGoes c={c} p={p} isMobile={isMobile} padX={padX} />
          <TrustTheNumbers c={c} p={p} isMobile={isMobile} padX={padX} />
          <RunWell c={c} p={p} isMobile={isMobile} padX={padX} />
          <RightForYou c={c} p={p} isMobile={isMobile} padX={padX} />
          <HowItCompares c={c} p={p} isMobile={isMobile} padX={padX} />
        </div>
      </div>

      {/* Methodology details */}
      <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder }}>
        <Kicker p={p}>Methodology details · edition {EDITION}</Kicker>
        {c.strengths.length > 0 && (
          <div style={{ marginTop: 8, marginBottom: 14, border: sectionBorder, borderRadius: 6, padding: 16, background: p.bg2 }}>
            <Kicker p={p}>How we evaluate</Kicker>
            <p style={{ fontSize: 13, lineHeight: 1.55, color: p.sub, margin: '8px 0 12px' }}>
              <em style={{ color: p.fg, fontStyle: 'normal', fontWeight: 500 }}>Impact</em> assesses organizational
              indicators associated with effective programs.{' '}
              <em style={{ color: p.fg, fontStyle: 'normal', fontWeight: 500 }}>Alignment</em> reflects fit with Muslim
              donor priorities.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
              {c.strengths.map((s) => (
                <div key={s.point} style={{ padding: 12, border: sectionBorder, borderRadius: 4, background: p.bg }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <HarveyBall rating="Strong" p={p} size={12} />
                    <span style={{ fontSize: 11.5, color: p.fg, fontWeight: 500 }}>{s.point}</span>
                  </div>
                  {s.detail && <div style={{ fontSize: 11, color: p.sub, lineHeight: 1.5 }}>{s.detail}</div>}
                </div>
              ))}
            </div>
          </div>
        )}
        {/* Independent of the strengths block above — a charity can have
            growth areas without strengths, or vice versa. */}
        {c.growthAreas.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <Kicker p={p}>Growth areas</Kicker>
            <div style={{ display: 'grid', gap: 4, marginTop: 6 }}>
              {c.growthAreas.map((s) => (
                <div key={s} style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '4px 0', fontSize: 12.5, color: p.fg }}>
                  <span style={{ color: p.caution }}>−</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
          <DimensionDetail title="Impact" dim={c.impact} color={p.accent} p={p} sectionBorder={sectionBorder} />
          <DimensionDetail title="Alignment" dim={c.alignment} color={p.accent2} p={p} sectionBorder={sectionBorder} />
        </div>
        {/* Credibility has no numeric score in the export (unlike Impact/Alignment),
            so it gets a plain cited explanation rather than a HarveyBall card. */}
        {c.cited.dimensionExplanations.credibility.length > 0 && (
          <div style={{ marginTop: 14, border: sectionBorder, borderRadius: 6, padding: 16, background: p.bg }}>
            <Kicker p={p}>Credibility</Kicker>
            <div style={{ marginTop: 8 }}>
              <CitedText segments={c.cited.dimensionExplanations.credibility} p={p} size={13} />
            </div>
            <SourceList citations={collectCitations(c.cited.dimensionExplanations.credibility)} p={p} />
          </div>
        )}
      </section>

      {/* Similar charities — ungated, SSR-crawlable: links render for every visitor
          including Googlebot so the prerendered HTML carries real /charity/<ein>/ hrefs. */}
      {similarCharities.length >= 2 && (
        <section
          aria-labelledby="gmg-similar-heading"
          style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder }}
        >
          <Kicker p={p}>Similar charities</Kicker>
          <h2
            id="gmg-similar-heading"
            style={{ fontFamily: FONT_DISPLAY, fontSize: 22, margin: '6px 0 12px', letterSpacing: '-0.02em', color: p.fg }}
          >
            Similar charities
          </h2>
          <ul
            style={{
              listStyle: 'none',
              margin: 0,
              padding: 0,
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 8,
            }}
          >
            {similarCharities.map((sc) => (
              <li key={sc.ein}>
                <Link
                  to={charityPath(sc.ein)}
                  style={{
                    display: 'block',
                    padding: '10px 12px',
                    borderRadius: 6,
                    border: sectionBorder,
                    background: p.bg2,
                    color: p.fg,
                    textDecoration: 'none',
                    fontSize: 13,
                    fontWeight: 500,
                    lineHeight: 1.4,
                  }}
                >
                  {sc.name}
                  {sc.amalScore != null && (
                    <div style={{ fontFamily: FONT_MONO, fontSize: 10.5, color: p.sub2, marginTop: 4 }}>
                      {sc.amalScore}/100
                    </div>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer style={{ padding: `14px ${padX}px`, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, color: p.sub2, fontSize: 10.5, fontFamily: FONT_MONO, letterSpacing: '0.06em' }}>
        <span>GOOD MEASURE GIVING · {c.ein && `EIN ${c.ein}`} · EDITION {EDITION}</span>
        <span>HARVEY-BALL MOTIF</span>
      </footer>

      <GmgFooter p={p} isMobile={isMobile} />
    </div>
  );
};

export default GmgCharityDetail;

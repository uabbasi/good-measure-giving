// Good Measure Giving — "Modern" motif charity detail.
// Reachable via /charity/:id. Renders real charity data in the
// sage-on-bone, Harvey-ball design from the claude.ai handoff.

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { charityPath } from '../../lib/paths';
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
  Star8,
  Bar,
  Stacked,
  Bismillah,
  Figure,
} from './primitives';
import { GmgNav } from './chrome';
import { GmgFooter } from './content';
import { useIsMobile } from './useIsMobile';
import { adaptCharity, GmgDimension } from './charityAdapter';

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

  const statCells: [string, string, string][] = [
    ['Cost / benef.', c.costPerBeneficiary != null ? usdFull(c.costPerBeneficiary) : '—', c.costPerBeneficiary != null ? 'per person' : 'not reported'],
    ['Program ratio', c.programRatioPct != null ? `${c.programRatioPct}%` : '—', 'of expense'],
    ['Reserves', c.reserveMonths != null ? `${c.reserveMonths} mo` : '—', 'working capital'],
    ['Revenue', usd(c.totalRevenue), c.fiscalYear ? `FY${c.fiscalYear}` : 'IRS 990'],
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
        {c.rubricVersion && <span>RUBRIC v{c.rubricVersion}</span>}
        {c.evaluatedOn && <span>· EVALUATED {c.evaluatedOn}</span>}
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
              {[c.address, c.ein && `EIN ${c.ein}`, c.founded && `Founded ${c.founded}`].filter(Boolean).join(' · ')}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
              <Tag tone="accent" p={p}>{c.wallet}</Tag>
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
                to={charityPath(c.ein)}
                style={{ padding: '10px 16px', borderRadius: 99, background: 'transparent', border: `1px solid ${p.rule}`, color: p.fg, fontSize: 12, textDecoration: 'none' }}
              >
                Standard view
              </Link>
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

      {/* About + Quick facts */}
      <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder, display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1.6fr) minmax(0, 1fr)', gap: 20 }}>
        <div>
          <Kicker p={p}>About</Kicker>
          <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: 28, lineHeight: 1.15, margin: '8px 0 12px', letterSpacing: '-0.02em' }}>
            {c.headline}
          </h2>
          {c.summary && <p style={{ fontSize: 13.5, lineHeight: 1.65, color: p.sub, margin: 0 }}>{c.summary}</p>}
        </div>
        <div style={{ border: sectionBorder, borderRadius: 6, padding: 14, background: p.bg2 }}>
          <Kicker p={p}>Quick facts</Kicker>
          <div style={{ marginTop: 10, fontSize: 12 }}>
            {([
              ['Category', c.category],
              ['Region', c.region],
              ['Programs', c.programs.join(', ')],
              ['Populations', c.populations.join(', ')],
              ['Founded', c.founded ? `${c.founded}${c.trackRecordYears ? ` · ${c.trackRecordYears} yrs` : ''}` : ''],
              ['Wallet', c.wallet],
              ['Asnaf', c.asnaf || (c.claimsZakat ? 'Claims zakat' : '')],
              ['Risk level', c.riskLevel],
            ] as [string, string][])
              .filter(([, v]) => v)
              .map(([k, v], i, arr) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: i < arr.length - 1 ? sectionBorder : 'none' }}>
                  <span style={{ color: p.sub, flexShrink: 0 }}>{k}</span>
                  <span style={{ color: k === 'Risk level' ? (p[riskTone(c.riskLevel)] as string) : p.fg, fontWeight: k === 'Risk level' ? 600 : 400, fontFamily: FONT_MONO, fontSize: 11, textAlign: 'right' }}>{v}</span>
                </div>
              ))}
          </div>
        </div>
      </section>

      {/* Methodology details */}
      <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder }}>
        <Kicker p={p}>Methodology details {c.rubricVersion && `· rubric v${c.rubricVersion}`}</Kicker>
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
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
          <DimensionDetail title="Impact" dim={c.impact} color={p.accent} p={p} sectionBorder={sectionBorder} />
          <DimensionDetail title="Alignment" dim={c.alignment} color={p.accent2} p={p} sectionBorder={sectionBorder} />
        </div>
      </section>

      {/* Best for */}
      {(c.bestForSummary || c.idealFor.length > 0 || c.considerations.length > 0) && (
        <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder }}>
          <Kicker p={p}>Best for</Kicker>
          {c.bestForSummary && (
            <p style={{ fontFamily: FONT_DISPLAY, fontSize: 22, color: p.fg, lineHeight: 1.35, margin: '8px 0 16px', letterSpacing: '-0.01em', maxWidth: 1000 }}>
              {c.bestForSummary}
            </p>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            {c.idealFor.length > 0 && (
              <div style={{ border: `1px solid ${p.pos}`, borderRadius: 6, padding: 14, background: p.posBg }}>
                <div style={{ fontSize: 12, color: p.pos, fontWeight: 600, marginBottom: 8 }}>✓ Ideal for donors who:</div>
                {c.idealFor.map((t) => (
                  <div key={t} style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '5px 0', fontSize: 12.5, color: p.fg, lineHeight: 1.5 }}>
                    <span style={{ color: p.pos }}>+</span>
                    <span>{t}</span>
                  </div>
                ))}
              </div>
            )}
            {c.considerations.length > 0 && (
              <div style={{ border: `1px solid ${p.caution}`, borderRadius: 6, padding: 14, background: p.cautionBg }}>
                <div style={{ fontSize: 12, color: p.caution, fontWeight: 600, marginBottom: 8 }}>! Consider:</div>
                {c.considerations.map((t) => (
                  <div key={t} style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '5px 0', fontSize: 12.5, color: p.fg, lineHeight: 1.5 }}>
                    <span style={{ color: p.caution }}>−</span>
                    <span>{t}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          {c.caseAgainst && (
            <div style={{ marginTop: 14, padding: '10px 14px', background: p.negBg, borderRadius: 4, fontSize: 12.5, color: p.neg, lineHeight: 1.5 }}>
              <span style={{ fontWeight: 600 }}>⊘ May not fit: </span>
              {c.caseAgainst}
            </div>
          )}
        </section>
      )}

      {/* Balanced view */}
      {(c.strengths.length > 0 || c.growthAreas.length > 0) && (
        <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder }}>
          <Kicker p={p}>Balanced view</Kicker>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginTop: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: p.pos, fontWeight: 600, marginBottom: 6 }}>Strengths</div>
              {c.strengths.map((s) => (
                <div key={s.point} style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '4px 0', fontSize: 12.5, color: p.fg }}>
                  <span style={{ color: p.pos }}>+</span>
                  <span>{s.point}</span>
                </div>
              ))}
            </div>
            {c.growthAreas.length > 0 && (
              <div>
                <div style={{ fontSize: 12, color: p.caution, fontWeight: 600, marginBottom: 6 }}>Growth areas</div>
                {c.growthAreas.map((s) => (
                  <div key={s} style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '4px 0', fontSize: 12.5, color: p.fg }}>
                    <span style={{ color: p.caution }}>−</span>
                    <span>{s}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Financials + Zakat */}
      <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
        <div style={{ border: sectionBorder, borderRadius: 6, padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
            <h3 style={{ fontFamily: FONT_DISPLAY, fontSize: 22, margin: 0, letterSpacing: '-0.02em' }}>Financials</h3>
            <Kicker p={p}>{c.fiscalYear ? `FY${c.fiscalYear} · IRS 990` : 'IRS 990'}</Kicker>
          </div>
          {c.programRatioPct != null && (() => {
            // Derive the split from the real filed expense figures when available
            // (so the bar matches the dollar amounts shown below it); fall back to
            // the program ratio alone otherwise. Remainder math prevents >100%.
            const prog = c.programExpenses ?? 0;
            const admin = c.adminExpenses ?? 0;
            const fund = c.fundraisingExpenses ?? 0;
            const denom = prog + admin + fund;
            const hasBreakdown = denom > 0;
            const progPct = hasBreakdown ? Math.round((prog / denom) * 100) : c.programRatioPct;
            const adminPct = hasBreakdown ? Math.round((admin / denom) * 100) : Math.max(0, 100 - c.programRatioPct);
            const fundPct = Math.max(0, 100 - progPct - adminPct);
            return (
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: p.sub2, marginBottom: 4 }}>
                  <span>Expense allocation</span>
                  <span>{usd(c.totalRevenue)} revenue</span>
                </div>
                <Stacked
                  h={10}
                  segs={[
                    { pct: progPct, color: p.accent },
                    { pct: adminPct, color: p.accent2 },
                    { pct: fundPct, color: p.warn },
                  ]}
                />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8, fontSize: 11 }}>
                  <span><span style={{ color: p.accent }}>■</span> Programs {progPct}%</span>
                  <span><span style={{ color: p.accent2 }}>■</span> Admin {adminPct}%</span>
                  <span><span style={{ color: p.warn }}>■</span> Fundraising {fundPct}%</span>
                </div>
              </div>
            );
          })()}
          <div style={{ borderTop: sectionBorder, marginTop: 10, paddingTop: 8, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 4, fontSize: 11.5 }}>
            {([
              ['Total revenue', usdFull(c.totalRevenue)],
              ['Program expenses', usdFull(c.programExpenses)],
              ['Admin expenses', usdFull(c.adminExpenses)],
              ['Fundraising', usdFull(c.fundraisingExpenses)],
              ['Net assets', usdFull(c.netAssets)],
              ['Reserves', c.reserveMonths != null ? `${c.reserveMonths} mo` : '—'],
            ] as [string, string][]).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '4px 0' }}>
                <span style={{ color: p.sub }}>{k}</span>
                <span style={{ color: p.fg, fontFamily: FONT_MONO, fontSize: 10.5 }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ border: sectionBorder, borderRadius: 6, padding: 14, background: p.bg2 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
            <h3 style={{ fontFamily: FONT_DISPLAY, fontSize: 22, margin: 0, letterSpacing: '-0.02em' }}>Zakat verification</h3>
            <Tag tone={c.claimsZakat ? 'accent' : 'muted'} p={p}>{c.claimsZakat ? 'Pass' : 'Sadaqah'}</Tag>
          </div>
          {c.zakatEvidence && (
            <p style={{ fontFamily: FONT_DISPLAY, fontStyle: 'italic', fontSize: 14, color: p.fg, lineHeight: 1.5, margin: 0 }}>
              “{c.zakatEvidence}”
            </p>
          )}
          {c.asnaf && (
            <div style={{ marginTop: 12, paddingTop: 10, borderTop: sectionBorder }}>
              <Kicker p={p}>Asnaf category</Kicker>
              <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                <Tag tone="accent" p={p}>{c.asnaf}</Tag>
              </div>
            </div>
          )}
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: sectionBorder }}>
            <Kicker p={p}>Third-party verification</Kicker>
            <div style={{ marginTop: 6 }}>
              {([
                ['Charity Navigator', c.awards.cn],
                ['Candid Seal', c.awards.candid],
                ['BBB Wise Giving', c.awards.bbb],
              ] as [string, string | null][])
                .filter(([, v]) => v)
                .map(([k, v], i, arr) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < arr.length - 1 ? sectionBorder : 'none', fontSize: 11.5 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: p.fg }}>
                      <Star8 size={9} color={p.accent} fill={p.accent} strokeWidth={0} />
                      {k}
                    </span>
                    <span style={{ fontFamily: FONT_MONO, color: p.sub2, fontSize: 10.5 }}>{v}</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
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
        <span>GOOD MEASURE GIVING · {c.ein && `EIN ${c.ein}`} {c.rubricVersion && `· RUBRIC v${c.rubricVersion}`}</span>
        <span>HARVEY-BALL MOTIF</span>
      </footer>

      <GmgFooter p={p} isMobile={isMobile} />
    </div>
  );
};

export default GmgCharityDetail;

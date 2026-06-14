// Good Measure Giving — "Modern" motif Landing (proof surface #3).
// Reachable via /?design=gmg. Hero + featured evaluation + top-of-index teaser
// + methodology strip + cause distribution, all on real data.

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useCharities } from '../../hooks/useCharities';
import {
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEMES,
  resolveFontVariant,
  type FontVariant,
} from './tokens';
import { Rating, ratingColor, riskTone } from './rating';
import { HarveyBall, Tag, Kicker, Figure, Bar } from './primitives';
import { GmgNav, TypeSwitcher } from './chrome';
import { useIsMobile } from './useIsMobile';
import { adaptCharity, adaptRow, GmgRow } from './charityAdapter';

const RANK: Record<Rating, number> = { Strong: 5, Good: 4, Moderate: 3, Fair: 2, Weak: 1 };
const ratingFromAvg = (avg: number): Rating =>
  avg >= 4.5 ? 'Strong' : avg >= 3.5 ? 'Good' : avg >= 2.5 ? 'Moderate' : avg >= 1.5 ? 'Fair' : 'Weak';

export const GmgLanding: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const padX = isMobile ? 16 : 24;
  const { charities, loading } = useCharities();

  const variant: FontVariant = resolveFontVariant(
    typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('type') : null,
  );
  const ft = FONT_THEMES[variant];
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  };
  const sectionBorder = `1px solid ${p.rule}`;

  const sorted = useMemo(
    () => [...(charities || [])].filter((c) => c?.ein).sort((a, b) => (b?.amalEvaluation?.amal_score ?? 0) - (a?.amalEvaluation?.amal_score ?? 0)),
    [charities],
  );
  const rows: GmgRow[] = useMemo(() => sorted.map(adaptRow), [sorted]);
  const featured = useMemo(() => (sorted.length ? adaptCharity(sorted[0]) : null), [sorted]);

  const count = rows.length;
  const zakatCount = rows.filter((r) => r.walletIsZakat).length;
  const causeCount = useMemo(() => new Set(rows.map((r) => r.cause)).size, [rows]);

  const dist = useMemo(() => {
    const m = new Map<string, { count: number; sum: number }>();
    rows.forEach((r) => {
      const e = m.get(r.cause) ?? { count: 0, sum: 0 };
      e.count += 1;
      e.sum += RANK[r.impact];
      m.set(r.cause, e);
    });
    return [...m.entries()]
      .map(([cause, e]) => ({ cause, count: e.count, avg: e.sum / e.count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [rows]);
  const distMax = Math.max(1, ...dist.map((d) => d.count));

  const shell = (children: React.ReactNode) => (
    <div style={{ background: p.bg, color: p.fg, fontFamily: FONT_TEXT, minHeight: '100vh', ...fontVars }}>
      <GmgNav p={p} isMobile={isMobile} active="Home" />
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexWrap: 'wrap',
          padding: `6px ${padX}px`,
          background: p.bg2,
          borderBottom: sectionBorder,
          color: p.sub,
          fontFamily: FONT_MONO,
          fontSize: 10.5,
          letterSpacing: '0.06em',
        }}
      >
        <span>GOOD MEASURE GIVING · EVIDENCE-BASED CHARITY EVALUATION</span>
        <span style={{ flex: 1 }} />
        <TypeSwitcher p={p} variant={variant} basePath="/" />
      </div>
      {children}
    </div>
  );

  if (loading || !featured) {
    return shell(
      <div style={{ padding: 48, textAlign: 'center', color: p.sub, fontFamily: FONT_MONO, fontSize: 12 }}>
        Loading…
      </div>,
    );
  }

  const RatingCell: React.FC<{ rating: Rating; size?: number }> = ({ rating, size = 14 }) => (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <HarveyBall rating={rating} p={p} size={size} />
      <span style={{ fontSize: 11.5, color: ratingColor(rating, p) }}>{rating}</span>
    </span>
  );

  const MiniRating: React.FC<{ label: string; rating: Rating; score: number; blurb: string }> = ({
    label,
    rating,
    score,
    blurb,
  }) => (
    <div style={{ padding: '10px 12px', border: sectionBorder, borderRadius: 6, background: p.bg, display: 'flex', alignItems: 'center', gap: 10 }}>
      <HarveyBall rating={rating} p={p} size={28} />
      <div>
        <Kicker p={p}>{label}</Kicker>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <Figure size={20} color={p.fg} italic>{rating}</Figure>
          <span style={{ fontFamily: FONT_MONO, fontSize: 9.5, color: p.sub2 }}>{score}/50</span>
        </div>
        <div style={{ fontSize: 10, color: p.sub2, marginTop: 1 }}>{blurb}</div>
      </div>
    </div>
  );

  return shell(
    <>
      {/* Hero */}
      <section style={{ padding: `32px ${padX}px`, borderBottom: sectionBorder }}>
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1.35fr) minmax(0, 1fr)', gap: isMobile ? 24 : 32, alignItems: 'stretch' }}>
          <div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
              <Tag tone="solid" p={p}>{count} charities</Tag>
              <Tag p={p}>Zakat-eligible {zakatCount}</Tag>
              <Tag p={p}>Always free</Tag>
              <Tag p={p}>Independent research</Tag>
            </div>
            <h1 style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: isMobile ? 40 : 72, lineHeight: 0.98, letterSpacing: ft.displayTracking, margin: 0 }}>
              Know where your <em style={{ color: p.accent }}>charity dollar</em> actually goes.
            </h1>
            <p style={{ fontSize: 15, lineHeight: 1.55, color: p.sub, marginTop: 18, maxWidth: 600 }}>
              Real research on {count}+ Muslim charities — audited financials, impact evidence, governance, and
              zakat eligibility. Researched and published in the open so you can give with confidence.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 20 }}>
              <Link to="/browse?design=gmg" style={{ padding: '11px 18px', borderRadius: 99, background: p.chip, color: p.chipFg, fontSize: 13, fontWeight: 500, textDecoration: 'none' }}>
                Browse the index →
              </Link>
              <Link to="/methodology" style={{ padding: '11px 18px', borderRadius: 99, background: 'transparent', border: `1px solid ${p.fg}`, color: p.fg, fontSize: 13, textDecoration: 'none' }}>
                How we evaluate
              </Link>
            </div>

            {/* Mini stat row */}
            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)', marginTop: 28, border: sectionBorder, borderRadius: 4, background: p.bg2 }}>
              {([
                ['Charities evaluated', String(count), `across ${causeCount} causes`],
                ['Zakat-eligible', String(zakatCount), `${Math.round((zakatCount / Math.max(1, count)) * 100)}% of index`],
                ['Cause areas', String(causeCount), 'health, education…'],
                ['Methodology', `v${featured.rubricVersion || '—'}`, 'current rubric'],
              ] as [string, string, string][]).map(([l, v, sub], i) => (
                <div key={l} style={{ padding: '12px 14px', borderRight: !isMobile && i < 3 ? sectionBorder : 'none', borderBottom: isMobile && i < 2 ? sectionBorder : 'none' }}>
                  <Kicker p={p}>{l}</Kicker>
                  <div style={{ marginTop: 4 }}><Figure size={26} color={p.fg}>{v}</Figure></div>
                  <div style={{ fontSize: 11, color: p.accent, marginTop: 2 }}>{sub}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Featured evaluation card */}
          <div style={{ background: p.bg2, border: sectionBorder, borderRadius: 6, padding: 18, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
              <Kicker p={p}>★ Top of the index</Kicker>
              <span style={{ flex: 1 }} />
              <Tag tone={featured.wallet.toLowerCase().includes('zakat') ? 'accent' : 'muted'} p={p}>{featured.wallet}</Tag>
              {featured.category && <Tag p={p}>{featured.category}</Tag>}
            </div>
            <div style={{ fontFamily: FONT_DISPLAY, fontSize: 30, lineHeight: 1.05, letterSpacing: ft.displayTracking }}>{featured.name}</div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 10, color: p.sub2, marginTop: 4 }}>
              EIN {featured.ein}{featured.founded ? ` · Founded ${featured.founded}` : ''}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 14 }}>
              <MiniRating label="Impact" rating={featured.impact.overall} score={featured.impact.score} blurb="Effective programs" />
              <MiniRating label="Alignment" rating={featured.alignment.overall} score={featured.alignment.score} blurb="Muslim donor fit" />
              <div style={{ gridColumn: '1 / span 2', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 4 }}>
                {([
                  ['GMG', String(featured.amalScore)],
                  ['Risk', featured.riskLevel],
                  ['Reserves', featured.reserveMonths != null ? `${featured.reserveMonths}mo` : '—'],
                  ['Prog.', featured.programRatioPct != null ? `${featured.programRatioPct}%` : '—'],
                ] as [string, string][]).map(([k, v]) => (
                  <div key={k} style={{ padding: '6px 8px', background: p.bg, borderRadius: 4 }}>
                    <div style={{ fontFamily: FONT_MONO, fontSize: 8.5, color: p.sub2, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{k}</div>
                    <div style={{ fontSize: 12, color: k === 'Risk' ? (p[riskTone(featured.riskLevel)] as string) : p.fg, fontWeight: 500 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginTop: 14, paddingTop: 12, borderTop: sectionBorder }}>
              <Kicker p={p}>Why it leads</Kicker>
              <p style={{ fontSize: 12, color: p.sub, lineHeight: 1.5, margin: '6px 0 0' }}>{featured.headline}</p>
            </div>

            <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
              <Link to={`/charity/${featured.ein}?design=gmg`} style={{ flex: 1, padding: '10px', borderRadius: 99, background: p.fg, color: p.bg, fontSize: 12, fontWeight: 500, textAlign: 'center', textDecoration: 'none' }}>
                Open evaluation →
              </Link>
              <Link to="/browse?design=gmg" style={{ padding: '10px 14px', borderRadius: 99, background: 'transparent', border: sectionBorder, color: p.fg, fontSize: 12, textDecoration: 'none' }}>
                View all
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Top of index teaser */}
      <section style={{ padding: `20px ${padX}px 24px`, borderBottom: sectionBorder }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
            <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: isMobile ? 26 : 30, lineHeight: 1, margin: 0, letterSpacing: ft.displayTracking }}>Top of the index</h2>
            <Kicker p={p}>8 of {count} · sorted by GMG score</Kicker>
          </div>
          <Link to="/browse?design=gmg" style={{ textDecoration: 'none' }}><Tag p={p}>View all →</Tag></Link>
        </div>
        <div style={{ display: 'grid', gap: isMobile ? 8 : 0 }}>
          {!isMobile && (
            <div style={{ display: 'grid', gridTemplateColumns: '32px 1fr 140px 90px 110px 110px 56px', gap: 8, padding: '8px 6px', borderBottom: sectionBorder, fontFamily: FONT_MONO, fontSize: 9.5, letterSpacing: '0.12em', textTransform: 'uppercase', color: p.sub2 }}>
              <span>№</span><span>Charity</span><span>Cause</span><span>Wallet</span><span>Impact</span><span>Alignment</span><span>GMG</span>
            </div>
          )}
          {rows.slice(0, 8).map((r, i) => (
            <Link
              key={r.ein}
              to={`/charity/${r.ein}?design=gmg`}
              style={
                isMobile
                  ? { textDecoration: 'none', color: 'inherit', border: sectionBorder, borderRadius: 8, padding: 12, background: p.bg2, display: 'block' }
                  : { textDecoration: 'none', color: 'inherit', display: 'grid', gridTemplateColumns: '32px 1fr 140px 90px 110px 110px 56px', gap: 8, padding: '10px 6px', borderBottom: sectionBorder, alignItems: 'center' }
              }
            >
              {isMobile ? (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: FONT_MONO, fontSize: 10, color: p.sub2 }}>{String(i + 1).padStart(2, '0')}</span>
                    <Tag tone={r.walletIsZakat ? 'accent' : 'muted'} p={p}>{r.wallet}</Tag>
                  </div>
                  <div style={{ fontFamily: FONT_DISPLAY, fontSize: 19, marginTop: 2, letterSpacing: ft.displayTracking }}>{r.name}</div>
                  <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                    <RatingCell rating={r.impact} />
                    <RatingCell rating={r.alignment} />
                    <Figure size={15} color={p.accent}>{r.amalScore}</Figure>
                  </div>
                </>
              ) : (
                <>
                  <span style={{ fontFamily: FONT_MONO, fontSize: 11, color: p.sub }}>{String(i + 1).padStart(2, '0')}</span>
                  <span style={{ fontFamily: FONT_DISPLAY, fontSize: 17, letterSpacing: ft.displayTracking }}>{r.name}</span>
                  <span style={{ color: p.sub, fontSize: 12 }}>{r.cause}</span>
                  <Tag tone={r.walletIsZakat ? 'accent' : 'muted'} p={p}>{r.wallet}</Tag>
                  <RatingCell rating={r.impact} />
                  <RatingCell rating={r.alignment} />
                  <Figure size={16} color={p.accent}>{r.amalScore}</Figure>
                </>
              )}
            </Link>
          ))}
        </div>
      </section>

      {/* Methodology strip */}
      <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder, background: p.bg2 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: isMobile ? 24 : 28, lineHeight: 1, margin: 0, letterSpacing: ft.displayTracking }}>Two dimensions, scored in the open</h2>
          <Kicker p={p}>Harvey-ball rated · rubric v{featured.rubricVersion}</Kicker>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 0, border: sectionBorder, background: p.bg }}>
          {[
            { dim: 'Impact', blurb: 'Indicators of effective programs.', color: p.accent, crits: featured.impact.criteria },
            { dim: 'Alignment', blurb: 'Fit with Muslim donor priorities.', color: p.accent2, crits: featured.alignment.criteria },
          ].map((d, i) => (
            <div key={d.dim} style={{ padding: '14px 16px', borderRight: !isMobile && i < 1 ? sectionBorder : 'none', borderBottom: isMobile && i < 1 ? sectionBorder : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <Figure size={24} color={d.color} italic>{d.dim}</Figure>
                <span style={{ marginLeft: 'auto', fontFamily: FONT_MONO, fontSize: 9.5, color: p.sub2, letterSpacing: '0.1em' }}>{d.crits.length} CRITERIA</span>
              </div>
              <div style={{ fontSize: 12, color: p.sub, marginTop: 4, marginBottom: 10 }}>{d.blurb}</div>
              <div style={{ display: 'grid', rowGap: 6 }}>
                {d.crits.map((cr) => (
                  <div key={cr.name} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                    <HarveyBall rating={cr.rating} p={p} size={12} />
                    <span style={{ color: p.fg }}>{cr.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Distribution by cause */}
      <section style={{ padding: `20px ${padX}px`, borderBottom: sectionBorder }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
          <h3 style={{ fontFamily: FONT_DISPLAY, fontSize: 22, margin: 0, letterSpacing: ft.displayTracking }}>Distribution by cause</h3>
          <Kicker p={p}>{count} charities · avg impact rating</Kicker>
        </div>
        {dist.map((d) => {
          const avgRating = ratingFromAvg(d.avg);
          return (
            <div key={d.cause} style={{ display: 'grid', gridTemplateColumns: isMobile ? '110px 1fr 64px' : '160px 1fr 70px 110px', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: sectionBorder, fontSize: 12 }}>
              <span style={{ color: p.fg, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.cause}</span>
              <Bar value={d.count} max={distMax} color={ratingColor(avgRating, p)} bg={p.rule} h={5} />
              <span style={{ fontFamily: FONT_MONO, color: p.sub2, fontSize: 11 }}>{d.count}</span>
              {!isMobile && (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                  <HarveyBall rating={avgRating} p={p} size={12} />
                  <span style={{ fontSize: 11, color: ratingColor(avgRating, p) }}>{avgRating}</span>
                </span>
              )}
            </div>
          );
        })}
      </section>

      <footer style={{ padding: `16px ${padX}px`, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, color: p.sub2, fontSize: 10.5, fontFamily: FONT_MONO, letterSpacing: '0.06em' }}>
        <span>GOOD MEASURE GIVING · {count} CHARITIES · RUBRIC v{featured.rubricVersion}</span>
        <span>HARVEY-BALL MOTIF · PREVIEW</span>
      </footer>
    </>,
  );
};

export default GmgLanding;

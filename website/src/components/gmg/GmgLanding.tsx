// Good Measure Giving — "Modern" motif Landing (/).
// Calm, plain-language front door for everyday donors. The dense, data-rich
// treatment lives on the index + detail pages; this page reassures and invites.

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Coins, HeartHandshake, Moon } from 'lucide-react';
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
import { Rating, ratingColor } from './rating';
import { HarveyBall, Bismillah } from './primitives';
import { GmgNav } from './chrome';
import { GmgFooter } from './content';
import { useIsMobile } from './useIsMobile';
import { adaptCharity } from './charityAdapter';
import { CauseAreaMatrix } from '../../../components/CauseAreaMatrix';

const RANK: Record<Rating, number> = { Strong: 5, Good: 4, Moderate: 3, Fair: 2, Weak: 1 };
const ratingFromAvg = (avg: number): Rating =>
  avg >= 4.5 ? 'Strong' : avg >= 3.5 ? 'Good' : avg >= 2.5 ? 'Moderate' : avg >= 1.5 ? 'Fair' : 'Weak';

export const GmgLanding: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const padX = isMobile ? 20 : 24;
  const { charities, summaries } = useCharities();

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

  const sorted = useMemo(
    () =>
      [...(charities || [])]
        .filter((c) => c?.ein)
        .sort((a, b) => (b?.amalEvaluation?.amal_score ?? 0) - (a?.amalEvaluation?.amal_score ?? 0)),
    [charities],
  );
  const count = sorted.length;
  const featured = useMemo(() => (sorted.length ? adaptCharity(sorted[0]) : null), [sorted]);
  const featuredOverall: Rating | null = featured
    ? ratingFromAvg((RANK[featured.impact.overall] + RANK[featured.alignment.overall]) / 2)
    : null;

  // Data for the interactive cause-area map (needs pillar scores).
  const insightsData = useMemo(
    () =>
      (summaries || [])
        .filter((s: any) => s.pillarScores && s.amalScore != null)
        .map((s: any) => ({
          id: s.id,
          name: s.name,
          amalScore: s.amalScore as number,
          walletTag: s.walletTag || '',
          pillarScores: s.pillarScores,
          category: s.primaryCategory || 'OTHER',
          totalRevenue: s.totalRevenue,
        })),
    [summaries],
  );

  const center: React.CSSProperties = { maxWidth: 980, margin: '0 auto' };

  const reassurances = [
    {
      Icon: Coins,
      title: 'Honest with money',
      body: "We read every charity's tax filings and audited financials — so you know your gift is in responsible hands.",
    },
    {
      Icon: HeartHandshake,
      title: 'Real impact',
      body: 'We look for solid evidence that a charity actually changes lives — not just heartfelt stories.',
    },
    {
      Icon: Moon,
      title: 'Zakat, checked',
      body: 'We verify which charities are eligible for your zakat, and show you the reasoning behind it.',
    },
  ];

  return (
    <div style={{ background: p.bg, color: p.fg, fontFamily: FONT_TEXT, minHeight: '100vh', ...fontVars }}>
      <GmgNav p={p} isMobile={isMobile} active="Home" />
      <Bismillah p={p} />

      {/* Hero — calm, centered, generous air */}
      <section style={{ padding: isMobile ? `56px ${padX}px 48px` : `96px ${padX}px 80px`, textAlign: 'center' }}>
        <div style={{ ...center }}>
          <div style={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase', color: p.accent2, marginBottom: 22 }}>
            Independent research · {count > 0 ? count : '150+'} charities rigorously vetted · for Muslim donors
          </div>
          <h1 style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: isMobile ? 46 : 78, lineHeight: 1.02, letterSpacing: ft.displayTracking, margin: 0, maxWidth: 840, marginInline: 'auto' }}>
            Give with <em style={{ color: p.accent }}>confidence.</em>
          </h1>
          <p style={{ fontSize: isMobile ? 16 : 18, lineHeight: 1.6, color: p.sub, margin: '24px auto 0', maxWidth: 580 }}>
            Choosing a charity shouldn't be a leap of faith. We do the homework on Muslim charities —
            their honesty with money, their real impact, and their zakat eligibility — so you can give
            with peace of mind.
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginTop: 32 }}>
            <Link
              to="/browse"
              style={{ padding: '13px 24px', borderRadius: 99, background: p.accent, color: p.bg, fontSize: 15, fontWeight: 500, textDecoration: 'none' }}
            >
              Browse charities
            </Link>
            <Link
              to="/methodology"
              style={{ padding: '13px 22px', borderRadius: 99, background: 'transparent', border: `1px solid ${p.rule2}`, color: p.fg, fontSize: 15, textDecoration: 'none' }}
            >
              How it works
            </Link>
          </div>
        </div>
      </section>

      {/* Three plain-language reassurances */}
      <section style={{ padding: isMobile ? `8px ${padX}px 48px` : `8px ${padX}px 72px`, borderTop: `1px solid ${p.rule}`, paddingTop: isMobile ? 48 : 64 }}>
        <div style={{ ...center, display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)', gap: isMobile ? 32 : 40 }}>
          {reassurances.map(({ Icon, title, body }) => (
            <div key={title} style={{ textAlign: isMobile ? 'center' : 'left' }}>
              <div style={{ display: 'inline-flex', width: 46, height: 46, borderRadius: 12, background: p.bg2, border: `1px solid ${p.rule}`, alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                <Icon size={22} color={p.accent} strokeWidth={1.6} aria-hidden="true" />
              </div>
              <h3 style={{ fontFamily: FONT_DISPLAY, fontSize: 23, margin: '0 0 8px', letterSpacing: ft.displayTracking }}>{title}</h3>
              <p style={{ fontSize: 14.5, lineHeight: 1.6, color: p.sub, margin: 0, maxWidth: 320, marginInline: isMobile ? 'auto' : undefined }}>{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Interactive cause-area map — the whole field at a glance */}
      {insightsData.length > 0 && (
        <section style={{ padding: isMobile ? `44px ${padX}px` : `72px ${padX}px`, borderTop: `1px solid ${p.rule}` }}>
          <div style={{ ...center, maxWidth: 920 }}>
            <div style={{ textAlign: 'center', marginBottom: isMobile ? 24 : 34 }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: p.accent2, marginBottom: 14 }}>
                The whole field
              </div>
              <h2 style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: isMobile ? 30 : 44, lineHeight: 1.06, letterSpacing: ft.displayTracking, margin: 0 }}>
                Every cause, <em style={{ color: p.accent }}>weighed.</em>
              </h2>
              <p style={{ fontSize: isMobile ? 15 : 17, lineHeight: 1.6, color: p.sub, margin: '16px auto 0', maxWidth: 520 }}>
                Impact against donor fit, across every cause area we cover — tap a bubble to explore the charities inside it.
              </p>
            </div>
            <CauseAreaMatrix charities={insightsData} />
          </div>
        </section>
      )}

      {/* One calm, human featured example */}
      {featured && featuredOverall && (
        <section style={{ padding: isMobile ? `40px ${padX}px` : `56px ${padX}px`, background: p.bg2, borderTop: `1px solid ${p.rule}`, borderBottom: `1px solid ${p.rule}` }}>
          <div style={{ ...center, maxWidth: 720, textAlign: 'center' }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: p.sub2, marginBottom: 14 }}>
              A charity we rate highly
            </div>
            <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: isMobile ? 32 : 40, lineHeight: 1.06, letterSpacing: ft.displayTracking, margin: 0 }}>
              {featured.name}
            </h2>
            <p style={{ fontSize: 16, lineHeight: 1.6, color: p.sub, margin: '16px auto 0', maxWidth: 560 }}>
              {featured.headline}
            </p>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 20, padding: '7px 16px', borderRadius: 99, background: p.bg, border: `1px solid ${p.rule}` }}>
              <HarveyBall rating={featuredOverall} p={p} size={16} />
              <span style={{ fontSize: 13.5, color: ratingColor(featuredOverall, p), fontWeight: 500 }}>{featuredOverall} overall</span>
            </div>
            <div style={{ marginTop: 22 }}>
              <Link to={`/charity/${featured.ein}`} style={{ fontSize: 15, color: p.accent, textDecoration: 'none', fontWeight: 500 }}>
                Read the review →
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Closing reassurance + single CTA */}
      <section style={{ padding: isMobile ? `56px ${padX}px` : `80px ${padX}px`, textAlign: 'center' }}>
        <div style={{ ...center, maxWidth: 680 }}>
          <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: isMobile ? 30 : 40, lineHeight: 1.1, letterSpacing: ft.displayTracking, margin: 0 }}>
            Independent — and no charity ever pays to be here.
          </h2>
          <p style={{ fontSize: 15.5, lineHeight: 1.6, color: p.sub, margin: '16px auto 28px', maxWidth: 520 }}>
            Our only goal is to help you give well — to {count}+ charities, researched in the open.
          </p>
          <Link
            to="/browse"
            style={{ display: 'inline-block', padding: '14px 28px', borderRadius: 99, background: p.chip, color: p.chipFg, fontSize: 15, fontWeight: 500, textDecoration: 'none' }}
          >
            Browse all {count} charities →
          </Link>
        </div>
      </section>

      <GmgFooter p={p} isMobile={isMobile} />
    </div>
  );
};

export default GmgLanding;

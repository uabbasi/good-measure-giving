// Good Measure Giving — "Modern" motif Compare (proof surface #4).
// Reachable via /compare?eins=a,b,c (falls back to the top 4).
// Charities side-by-side across every criterion. Horizontally scrollable on
// narrow screens so the comparison stays intact.

import React, { useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { charityPath } from '../../lib/paths';
import { useQueries } from '@tanstack/react-query';
import { useCharities } from '../../hooks/useCharities';
import {
  GmgPalette,
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEME,
} from './tokens';
import { Rating, ratingColor } from './rating';
import { HarveyBall, Tag, Kicker, Figure } from './primitives';
import { GmgNav } from './chrome';
import { GmgFooter } from './content';
import { useIsMobile } from './useIsMobile';
import { useCommunityMember } from '../../auth/useAuth';
import { SignInButton } from '../../auth/SignInButton';
import { adaptCharity, GmgCharity } from './charityAdapter';
import { usd, usdCompact } from './money';


// Module-scope table pieces — kept out of the render body so they retain a
// stable identity across renders (no remount of the table as queries resolve).

const RatingMini: React.FC<{ rating?: Rating | null; p: GmgPalette }> = ({ rating, p }) =>
  rating ? (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <HarveyBall rating={rating} p={p} size={13} />
      <span style={{ fontSize: 11.5, color: ratingColor(rating, p) }}>{rating}</span>
    </span>
  ) : (
    <span style={{ color: p.sub2 }}>—</span>
  );

const Row: React.FC<{
  label: string;
  kicker?: string;
  render: (s: GmgCharity, i: number) => React.ReactNode;
  subjects: GmgCharity[];
  p: GmgPalette;
  labelW: number;
  colW: number;
  sectionBorder: string;
}> = ({ label, kicker, render, subjects, p, labelW, colW, sectionBorder }) => (
  <tr style={{ borderBottom: sectionBorder }}>
    <td style={{ padding: '10px 14px', verticalAlign: 'top', width: labelW, minWidth: labelW, position: 'sticky', left: 0, background: p.bg, zIndex: 1 }}>
      <div style={{ fontSize: 12.5, color: p.fg }}>{label}</div>
      {kicker && (
        <div style={{ fontFamily: FONT_MONO, fontSize: 9, color: p.sub2, letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 2 }}>
          {kicker}
        </div>
      )}
    </td>
    {subjects.map((s, i) => (
      <td key={s.ein} style={{ padding: '10px 14px', verticalAlign: 'top', borderLeft: sectionBorder, minWidth: colW }}>
        {render(s, i)}
      </td>
    ))}
  </tr>
);

const SectionRow: React.FC<{
  title: string;
  color: string;
  subjects: GmgCharity[];
  p: GmgPalette;
  sectionBorder: string;
}> = ({ title, color, subjects, p, sectionBorder }) => (
  <tr style={{ background: p.bg2, borderBottom: sectionBorder }}>
    <td style={{ padding: '10px 14px', position: 'sticky', left: 0, background: p.bg2, zIndex: 1 }}>
      <Figure size={18} color={color} italic>{title}</Figure>
    </td>
    <td colSpan={subjects.length} style={{ padding: '10px 14px', borderLeft: sectionBorder, fontFamily: FONT_MONO, fontSize: 9.5, color: p.sub2, letterSpacing: '0.1em' }}>
      CRITERION BY CRITERION
    </td>
  </tr>
);

export const GmgCompare: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const isMember = useCommunityMember();
  const padX = isMobile ? 16 : 24;
  const { charities, loading: indexLoading } = useCharities();
  const location = useLocation();

  const ft = FONT_THEME;
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  };
  const sectionBorder = `1px solid ${p.rule}`;

  const requestedEins = useMemo(() => {
    const raw = new URLSearchParams(location.search).get('eins');
    if (!raw) return [];
    // Dedupe so ?eins=a,a,b doesn't render duplicate columns / collide React keys.
    return Array.from(new Set(raw.split(',').map((s) => s.trim()).filter(Boolean))).slice(0, 4);
  }, [location.search]);

  // Resolve the ≤4 target EINs: explicit ?eins=, else top 4 by GMG score from the index.
  const targetEins: string[] = useMemo(() => {
    if (requestedEins.length) return requestedEins;
    return [...(charities || [])]
      .filter((c) => c?.ein)
      .sort((a, b) => (b?.amalEvaluation?.amal_score ?? 0) - (a?.amalEvaluation?.amal_score ?? 0))
      .slice(0, 4)
      .map((c) => c.ein!)
      .filter(Boolean);
  }, [charities, requestedEins]);

  // The slim index omits per-criterion breakdowns, risk, reserves, cost/beneficiary,
  // and narratives. Load the full per-charity files (shared cache with the detail
  // page) so the comparison is complete rather than a grid of dashes.
  const fullQueries = useQueries({
    queries: targetEins.map((ein) => ({
      queryKey: ['charity', ein],
      queryFn: async () => {
        const r = await fetch(`/data/charities/charity-${ein}.json`);
        if (!r.ok) throw new Error(`Charity not found: ${ein}`);
        return r.json();
      },
      enabled: !!ein,
      staleTime: Infinity,
    })),
  });

  const subjects: GmgCharity[] = useMemo(
    () => fullQueries.map((q) => q.data).filter(Boolean).map(adaptCharity),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fullQueries.map((q) => q.dataUpdatedAt).join(',')],
  );

  const loading = indexLoading || (targetEins.length > 0 && fullQueries.some((q) => q.isLoading));

  // Union of criterion names (preserve first-seen order), plus per-subject lookup.
  const buildCriteria = (key: 'impact' | 'alignment') => {
    const names: string[] = [];
    const seen = new Set<string>();
    subjects.forEach((s) =>
      s[key].criteria.forEach((cr) => {
        if (!seen.has(cr.name)) {
          seen.add(cr.name);
          names.push(cr.name);
        }
      }),
    );
    const maps = subjects.map(
      (s) => new Map(s[key].criteria.map((cr) => [cr.name, cr.rating] as [string, Rating])),
    );
    return { names, maps };
  };
  const impactC = useMemo(() => buildCriteria('impact'), [subjects]);
  const alignC = useMemo(() => buildCriteria('alignment'), [subjects]);

  const labelW = isMobile ? 150 : 200;
  const colW = isMobile ? 180 : 220;
  // Shared props for the module-scope table pieces, bundled to keep call sites terse.
  const rowProps = { subjects, p, labelW, colW, sectionBorder };
  const sectionProps = { subjects, p, sectionBorder };

  const shell = (children: React.ReactNode) => (
    <div style={{ background: p.bg, color: p.fg, fontFamily: FONT_TEXT, minHeight: '100vh', ...fontVars }}>
      <GmgNav p={p} isMobile={isMobile} active="Compare" />
      {children}
      <GmgFooter p={p} isMobile={isMobile} />
    </div>
  );

  if (loading) {
    return shell(
      <div style={{ padding: 48, textAlign: 'center', color: p.sub, fontFamily: FONT_MONO, fontSize: 12 }}>Loading…</div>,
    );
  }

  if (subjects.length < 2) {
    return shell(
      <section style={{ padding: `40px ${padX}px`, textAlign: 'center' }}>
        <h1 style={{ fontFamily: FONT_DISPLAY, fontSize: 36, letterSpacing: ft.displayTracking, margin: 0 }}>
          Nothing to compare yet
        </h1>
        <p style={{ color: p.sub, marginTop: 12 }}>
          Pick two or more charities from the index to compare them side by side.
        </p>
        <Link to="/browse/" style={{ display: 'inline-block', marginTop: 16, padding: '11px 20px', borderRadius: 99, background: p.chip, color: p.chipFg, fontSize: 13, textDecoration: 'none' }}>
          Browse the index →
        </Link>
      </section>,
    );
  }

  return shell(
    <>
      <section style={{ padding: `20px ${padX}px 14px`, borderBottom: sectionBorder }}>
        <Kicker p={p}>Compare · {subjects.length} charities</Kicker>
        <h1 style={{ fontFamily: FONT_DISPLAY, fontSize: isMobile ? 34 : 46, margin: '4px 0 0', lineHeight: 1, letterSpacing: ft.displayTracking }}>
          Side by side, <em style={{ color: p.accent }}>weighed.</em>
        </h1>
      </section>

      {isMobile && subjects.length > 1 && (
        <div style={{ padding: `6px ${padX}px 0`, fontSize: 11, color: p.sub2 }}>Swipe to see more →</div>
      )}

      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: labelW + subjects.length * colW }}>
          <thead>
            <tr style={{ borderBottom: sectionBorder }}>
              <th style={{ padding: '14px', textAlign: 'left', width: labelW, minWidth: labelW, position: 'sticky', left: 0, background: p.bg, zIndex: 2 }}>
                <Kicker p={p}>Comparing {subjects.length}</Kicker>
              </th>
              {subjects.map((s) => (
                <th key={s.ein} style={{ padding: '14px', textAlign: 'left', verticalAlign: 'top', borderLeft: sectionBorder, minWidth: colW }}>
                  <Link to={charityPath(s.ein)} className="tap-link" style={{ textDecoration: 'none', color: 'inherit' }}>
                    <div style={{ fontFamily: FONT_DISPLAY, fontSize: 20, lineHeight: 1.05, letterSpacing: ft.displayTracking }}>{s.name}</div>
                  </Link>
                  <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                    <Tag tone={s.wallet.toLowerCase().includes('zakat') ? 'accent' : 'muted'} p={p}>{s.wallet}</Tag>
                    {s.category && <Tag p={p}>{s.category}</Tag>}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {/* Signed-out visitors get identity plus the same six signals /browse
                already publishes to everyone. This route loads the FULL per-charity
                files, so everything richer (reserves, cost per beneficiary, the
                per-criterion breakdown, and `bestForSummary`, which is
                rich_narrative.ideal_donor_profile verbatim) stays member-only:
                leaving it open would let anyone read a complete evaluation by
                ticking two boxes on /browse, around the detail page's sign-in wall.
                Wallet and cause are already tags in each column header. */}
            <Row {...rowProps} label="Founded" render={(s) => <span style={{ color: p.sub }}>{s.founded ?? '—'}{s.trackRecordYears ? ` · ${s.trackRecordYears} yrs` : ''}</span>} />

            {/* The same signals /browse already publishes to everyone. */}
            <Row {...rowProps} label="GMG rating" render={(s) => <RatingMini rating={s.overall ?? undefined} p={p} />} />
            <Row {...rowProps} label="Finances" render={(s) => <RatingMini rating={s.financialHealth} p={p} />} />
            <Row {...rowProps} label="Governance" render={(s) => <RatingMini rating={s.risk} p={p} />} />
            <Row {...rowProps} label="Donor fit" render={(s) => <RatingMini rating={s.donorFit} p={p} />} />
            <Row {...rowProps} label="Evidence" render={(s) => <span style={{ color: p.fg }}>{s.evidenceStage ?? '—'}</span>} />
            <Row {...rowProps} label="Size" kicker="annual revenue" render={(s) => <span style={{ fontFamily: FONT_MONO, color: p.fg }}>{usdCompact(s.totalRevenue)}</span>} />
            <Row {...rowProps} label="Program efficiency" kicker="% to programs" render={(s) => <span style={{ fontFamily: FONT_MONO, color: p.fg }}>{s.programRatioPct != null ? `${s.programRatioPct}%` : '—'}</span>} />

            {!isMember && (
              <tr>
                <td
                  colSpan={subjects.length + 1}
                  style={{ padding: '20px 14px', borderTop: sectionBorder, background: p.bg2 }}
                >
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 14 }}>
                    <span style={{ fontFamily: FONT_MONO, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: p.sub2 }}>
                      Full comparison
                    </span>
                    <span style={{ fontSize: 12.5, color: p.sub, flex: '1 1 260px' }}>
                      The reserves, cost per beneficiary, per-criterion breakdown and who each of these{' '}
                      {subjects.length} charities suits are free — sign in to see them.
                    </span>
                    <SignInButton variant="button" />
                  </div>
                </td>
              </tr>
            )}

            {isMember && (
              <>
                <Row {...rowProps} label="Reserves" render={(s) => <span style={{ fontFamily: FONT_MONO, color: p.fg }}>{s.reserveMonths != null ? `${s.reserveMonths} mo` : '—'}</span>} />
                <Row {...rowProps} label="Cost / beneficiary" render={(s) => <span style={{ fontFamily: FONT_MONO, color: p.fg }}>{usd(s.costPerBeneficiary)}</span>} />

                <SectionRow {...sectionProps} title="Impact" color={p.accent} />
                {impactC.names.map((name) => (
                  <Row {...rowProps} key={`i-${name}`} label={name} render={(_, i) => <RatingMini rating={impactC.maps[i].get(name)} p={p} />} />
                ))}

                <SectionRow {...sectionProps} title="Alignment" color={p.accent2} />
                {alignC.names.map((name) => (
                  <Row {...rowProps} key={`a-${name}`} label={name} render={(_, i) => <RatingMini rating={alignC.maps[i].get(name)} p={p} />} />
                ))}

                <Row {...rowProps} label="Best for" render={(s) => <span style={{ color: p.sub, fontFamily: FONT_DISPLAY, fontStyle: 'italic', fontSize: 13, lineHeight: 1.4 }}>{s.bestForSummary || '—'}</span>} />
              </>
            )}

            <Row {...rowProps} label="" render={(s) => (
              <Link to={charityPath(s.ein)} className="tap-link" style={{ fontSize: 12, color: p.accent, textDecoration: 'none' }}>Open evaluation →</Link>
            )} />
          </tbody>
        </table>
      </div>
    </>,
  );
};

export default GmgCompare;

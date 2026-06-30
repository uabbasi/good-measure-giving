// Good Measure Giving — "Modern" motif Methodology page (/methodology).
// Motif-only (no legacy variant): renders its own GmgNav + footer via the content kit.

import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useCharities } from '../src/hooks/useCharities';
import { useCalibrationReport } from '../src/hooks/useCalibrationReport';
import { getEvidenceStageLabel } from '../src/utils/scoreConstants';
import { MethodologyInsights } from '../components/MethodologyInsights';
import { CauseAreaMatrix } from '../components/CauseAreaMatrix';
import { SHOW_AMAL_SCORE } from '../src/featureFlags';
import { RUBRIC_VERSION } from '../src/config/siteVersion';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Em,
  Section,
  P,
  H3,
  UL,
  Callout,
  CtaLink,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FONT_MONO, FONT_DISPLAY, type GmgPalette } from '../src/components/gmg/tokens';

// Get top performing charities for the showcase
const getTopCharities = (charities: any[]) => {
  return charities
    .filter(c => c.amalEvaluation?.amal_score != null && c.amalEvaluation.amal_score >= 70)
    .sort((a, b) => (b.amalEvaluation?.amal_score || 0) - (a.amalEvaluation?.amal_score || 0))
    .slice(0, 12);
};

const CUE_DISPLAY_LABELS: Record<string, string> = {
  'Strong Match': 'Maximum Alignment',
  'Good Match': 'Strong Alignment',
  'Mixed Signals': 'Mixed Signals',
  'Limited Match': 'Needs Verification',
};

// Citability stamps. RUBRIC_VERSION is centralized in src/config/siteVersion.ts
// (mirrored from data-pipeline/src/scorers/v2_scorers.py); both this page and the
// site-wide version strip import it so they can't drift.
const METHODOLOGY_LAST_UPDATED = 'June 2026';
const METHODOLOGY_URL = 'https://goodmeasuregiving.org/methodology/';
const CITATION_TEXT = `Good Measure Giving. (2026). How We Evaluate Charities — Methodology (Rubric v${RUBRIC_VERSION}). Retrieved from ${METHODOLOGY_URL}`;

// ── Local motif building blocks ────────────────────────────────────────

const Card: React.FC<{ p: GmgPalette; children: React.ReactNode; style?: React.CSSProperties }> = ({ p, children, style }) => (
  <div style={{ background: p.card, border: `1px solid ${p.rule}`, borderRadius: 12, padding: 22, ...style }}>{children}</div>
);

const Grid: React.FC<{ isMobile: boolean; cols?: number; align?: React.CSSProperties['alignItems']; children: React.ReactNode }> = ({ isMobile, cols = 2, align, children }) => (
  <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : `repeat(${cols}, 1fr)`, gap: 14, alignItems: align }}>
    {children}
  </div>
);

const Kicker: React.FC<{ p: GmgPalette; children: React.ReactNode }> = ({ p, children }) => (
  <div
    style={{
      fontFamily: FONT_MONO,
      fontSize: 10,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      color: p.sub2,
      marginBottom: 8,
    }}
  >
    {children}
  </div>
);

const Pill: React.FC<{ p: GmgPalette; children: React.ReactNode; bg: string; fg: string }> = ({ p, children, bg, fg }) => (
  <span
    style={{
      fontFamily: FONT_MONO,
      fontSize: 11,
      padding: '3px 8px',
      borderRadius: 6,
      background: bg,
      color: fg,
      whiteSpace: 'nowrap',
    }}
  >
    {children}
  </span>
);

// Risk-flag row: mono deduction chip + description.
const Flag: React.FC<{ p: GmgPalette; pts: string; tone: 'neg' | 'caution' | 'sub'; children: React.ReactNode }> = ({ p, pts, tone, children }) => {
  const tones = {
    neg: { bg: p.negBg, fg: p.neg },
    caution: { bg: p.cautionBg, fg: p.caution },
    sub: { bg: p.bg3, fg: p.sub },
  } as const;
  const t = tones[tone];
  return (
    <li style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8 }}>
      <Pill p={p} bg={t.bg} fg={t.fg}>{pts}</Pill>
      <span style={{ fontSize: 14, lineHeight: 1.55, color: p.sub }}>{children}</span>
    </li>
  );
};

// "Don't" row — a muted ✕ marker + body.
const DontRow: React.FC<{ p: GmgPalette; children: React.ReactNode }> = ({ p, children }) => (
  <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 14 }}>
    <span aria-hidden="true" style={{ color: p.sub2, fontSize: 15, lineHeight: 1.6, flexShrink: 0 }}>✕</span>
    <p style={{ fontSize: 15, lineHeight: 1.6, color: p.fg, margin: 0 }}>{children}</p>
  </div>
);

export const MethodologyPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  React.useEffect(() => {
    document.title = 'Our Methodology | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);
  const { charities, summaries, loading } = useCharities();
  const { report: calibrationReport } = useCalibrationReport();

  // Get top-performing charities for showcase (pre-existing helper; kept for parity).
  const topCharities = useMemo(() => getTopCharities(charities), [charities]);

  const [citationCopied, setCitationCopied] = useState(false);
  const copyCitation = async () => {
    try {
      await navigator.clipboard.writeText(CITATION_TEXT);
      setCitationCopied(true);
      setTimeout(() => setCitationCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy citation:', err);
    }
  };

  // Score distribution buckets for visualization (aligned with scoreConstants.ts thresholds)
  const scoreBuckets = useMemo(() => {
    const buckets = { exceptional: 0, good: 0, developing: 0, emerging: 0 };
    charities.forEach(c => {
      const score = c.amalEvaluation?.amal_score;
      if (score == null) return;
      if (score >= 75) buckets.exceptional++;
      else if (score >= 60) buckets.good++;
      else if (score >= 30) buckets.developing++;
      else buckets.emerging++;
    });
    return buckets;
  }, [charities]);

  // Prepare data for insights visualization (needs pillar scores)
  const insightsData = useMemo(() => {
    return summaries
      .filter(s => s.pillarScores && s.amalScore != null)
      .map(s => ({
        id: s.id,
        name: s.name,
        amalScore: s.amalScore as number,
        walletTag: s.walletTag || '',
        pillarScores: s.pillarScores!,
        category: s.primaryCategory || 'OTHER',
        totalRevenue: s.totalRevenue,
      }));
  }, [summaries]);

  return (
    <GmgContentFrame isDark={isDark} active="Methodology" maxWidth={980}>
      {(ctx: ContentCtx) => {
        const { p, isMobile } = ctx;
        return (
          <>
            <Breadcrumb p={p} trail={[{ label: 'Home', to: '/' }, { label: 'Methodology' }]} />

            <ContentHero
              ctx={ctx}
              kicker="Methodology"
              title={<>How We <Em p={p}>Evaluate Charities</Em></>}
              lead={
                <>
                  A 100-point framework measuring what matters: how effectively each charity is set up to deliver
                  results, and whether it’s the right fit for Muslim donors. No jargon, full transparency.
                </>
              }
            />

            <Callout p={p} tone="info" title="TL;DR">
              We aggregate data from <strong>6 independent sources</strong>: IRS Form 990 filings (via ProPublica API),
              Charity Navigator ratings, Candid transparency seals, BBB accreditation status, charity websites, and
              web-discovered information (awards, third-party evaluations, zakat claims). We score on two dimensions:{' '}
              <strong>Impact</strong> (how effectively is the charity set up to deliver results?) and{' '}
              <strong>Alignment</strong> (is this the right fit for Muslim donors?), with up to 10 points deducted for
              serious risks. A separate <strong>Data Confidence</strong> signal tells you how much data we had to work
              with. Scores above 75 are exceptional, and most organizations cluster in the middle score bands.
            </Callout>

            {/* The Big Picture */}
            <Section ctx={ctx} title="The Big Picture" first>
              <P p={p}>
                Most charity ratings focus on overhead ratios — how much goes to “programs” vs “admin.” But an
                organization can be highly efficient at doing something that doesn’t work.
              </P>
              <P p={p}>We ask two questions that matter more:</P>
              <UL
                p={p}
                items={[
                  <><strong>Impact:</strong> How effectively is this charity set up to deliver results? (cost efficiency, evidence practices, financial health, governance)</>,
                  <><strong>Alignment:</strong> Is this the right charity for Muslim donors? (cause urgency, donor fit, funding gap, track record)</>,
                ]}
              />
              <P p={p}>
                Each dimension is worth 50 points, with up to 10 points deducted for red flags. A separate Data
                Confidence signal shows how robust our data is. Then we help you route your donation based on whether
                the charity publicly says it accepts Zakat or is better treated as Sadaqah.
              </P>

              <div style={{ marginTop: 22 }}>
                <Grid isMobile={isMobile} cols={isMobile ? 1 : 4}>
                  {[
                    ['01', 'Gather Data', 'We pull from IRS filings, rating agencies, and charity websites'],
                    ['02', 'Extract & Score', 'AI extracts data; deterministic code calculates scores'],
                    ['03', 'Validate', 'Automated checks flag conflicts; citations enable verification'],
                    ['04', 'Publish', 'Clear scores and guidance you can act on'],
                  ].map(([n, h, d]) => (
                    <Card key={n} p={p}>
                      <div style={{ fontFamily: FONT_MONO, fontSize: 12, color: p.accent2, marginBottom: 10 }}>{n}</div>
                      <H3 p={p}>{h}</H3>
                      <P p={p} muted>{d}</P>
                    </Card>
                  ))}
                </Grid>
              </div>
            </Section>

            {/* Our Perspective */}
            <Section ctx={ctx} title="Our Perspective">
              <Callout p={p} tone="pos" title="Philosophy">
                We evaluate from the perspective of Muslim donors seeking to increase safety, dignity, representation,
                and resilience for Muslim communities worldwide. We focus on charities that either serve Muslim
                communities directly or demonstrate alignment with donor values.
              </Callout>
            </Section>

            {/* The Two Dimensions */}
            <Section ctx={ctx} title="The Two Dimensions">
              <P p={p} muted>
                Every charity receives a score from 0–100, built from two dimensions (50 points each) minus any risk
                deductions (up to −10 points).
              </P>
              <Callout p={p} tone="neutral" title="How to read scores">
                Scores above 75 are exceptional, and most organizations cluster in the middle score bands. A score
                below 50 doesn’t mean “bad” — it usually means we don’t have enough data yet, or the charity is newer
                and still building its track record.
              </Callout>

              <div style={{ marginTop: 18 }}>
                {/* align=start so the shorter Alignment card doesn't stretch to
                    match Impact's extra callouts, which left a tall empty column. */}
                <Grid isMobile={isMobile} align="start">
                  {/* Impact */}
                  <Card p={p} style={{ padding: 0, overflow: 'hidden' }}>
                    <div style={{ padding: '16px 22px', background: p.bg2, borderBottom: `1px solid ${p.rule}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                        <span style={{ fontFamily: FONT_DISPLAY, fontSize: 20, color: p.fg }}>Impact</span>
                        <span style={{ fontFamily: FONT_MONO, fontSize: 12, color: p.accent2 }}>50 pts</span>
                      </div>
                      <p style={{ fontSize: 13, color: p.sub, margin: '4px 0 0' }}>How effectively is this charity set up to deliver results?</p>
                    </div>
                    <div style={{ padding: 22 }}>
                      <P p={p} muted>
                        Impact assesses organizational health indicators — cost efficiency, financial stewardship,
                        evidence practices, and governance — that research associates with effective programs. Most
                        sub-components are structural proxies, not direct outcome measurements.
                      </P>
                      <Kicker p={p}>What We Measure (50 points total)</Kicker>
                      <UL
                        p={p}
                        items={[
                          <><strong>Cost per beneficiary</strong> (6–13 pts): Cause-adjusted benchmarks with smooth interpolation</>,
                          <><strong>Directness</strong> (3–5 pts): Direct service vs indirect approaches</>,
                          <><strong>Financial health</strong> (7 pts): Working capital ratio (resilient range is generally ~3–12 months)</>,
                          <><strong>Program ratio</strong> (5–7 pts): Percentage of spending on actual programs</>,
                          <><strong>Evidence & outcomes</strong> (5–10 pts): Verified → Tracked → Measured → Reported → Unverified</>,
                          <><strong>Theory of change</strong> (5–7 pts): Has a documented logic model?</>,
                          <><strong>Governance</strong> (10 pts): Board size and oversight</>,
                        ]}
                      />
                      <P p={p} muted>
                        Impact always totals 50 points, but these component weights are rebalanced by archetype (for
                        example direct-service vs systemic-change organizations).
                      </P>
                      <Kicker p={p}>Cause-Adjusted Benchmarks</Kicker>
                      <UL
                        p={p}
                        items={[
                          <><strong>Food:</strong> &lt;$0.25/meal excellent, $0.25–0.50 good</>,
                          <><strong>Education:</strong> &lt;$100/student/yr excellent, $100–300 good</>,
                          <><strong>Healthcare:</strong> &lt;$25/patient (primary), &lt;$500 (surgical)</>,
                          <><strong>Humanitarian:</strong> &lt;$25/beneficiary excellent, $25–75 good (with conflict-zone adjustment)</>,
                        ]}
                      />
                      <Callout p={p} tone="caution" title="The overhead myth">
                        Low overhead isn’t always good. A legal advocacy org might have higher admin costs because
                        lawyers are expensive — but win cases protecting millions of Muslims. We consider context, not
                        just ratios.
                      </Callout>
                      <Callout p={p} tone="info" title="What’s a “Theory of Change”?">
                        It’s the charity’s explanation of <em>why</em> their approach should work — the logical steps
                        from “what we do” to “lives improved.” Charities that have written this down tend to be more
                        thoughtful about whether their programs actually work.
                      </Callout>
                      <Callout p={p} tone="neutral" title="A note on what Impact measures">
                        Most Impact sub-components (financial health, governance, program ratio) are organizational
                        health indicators, not measurements of direct outcomes. They tell us whether a charity is
                        well-positioned to deliver results, not whether it has definitively achieved them. Where
                        charities provide verified outcome data, we weight it accordingly.
                      </Callout>
                    </div>
                  </Card>

                  {/* Alignment — header styled symmetrically with Impact (sage, not green-tinted). */}
                  <Card p={p} style={{ padding: 0, overflow: 'hidden' }}>
                    <div style={{ padding: '16px 22px', background: p.bg2, borderBottom: `1px solid ${p.rule}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                        <span style={{ fontFamily: FONT_DISPLAY, fontSize: 20, color: p.fg }}>Alignment</span>
                        <span style={{ fontFamily: FONT_MONO, fontSize: 12, color: p.accent2 }}>50 pts</span>
                      </div>
                      <p style={{ fontSize: 13, color: p.sub, margin: '4px 0 0' }}>Is this the right charity for Muslim donors?</p>
                    </div>
                    <div style={{ padding: 22 }}>
                      <P p={p} muted>
                        Alignment measures whether your donation would make more difference here than elsewhere, and
                        whether the charity is a natural fit for Muslim donors. It rewards charities working in urgent,
                        underserved spaces.
                      </P>
                      <Kicker p={p}>What We Measure (50 points total)</Kicker>
                      <UL
                        p={p}
                        items={[
                          <><strong>Muslim donor fit</strong> (19 pts): Zakat clarity, asnaf categories, Muslim-focused mission</>,
                          <><strong>Cause urgency</strong> (13 pts): Humanitarian crises and extreme poverty score highest</>,
                          <><strong>Underserved space</strong> (7 pts): Niche causes and underserved populations</>,
                          <><strong>Track record</strong> (6 pts): Years of operation and demonstrated reliability</>,
                          <><strong>Funding gap</strong> (5 pts): Smaller orgs where your dollar goes further</>,
                        ]}
                      />
                      <Callout p={p} tone="neutral" title="Why Muslim-focused charities often score higher">
                        Many serve communities overlooked by mainstream philanthropy. Your Zakat dollar may go further
                        at a charity serving Muslim refugees than at a massive international org with thousands of
                        donors.
                      </Callout>
                      <Kicker p={p}>Size-Adjusted Expectations</Kicker>
                      <UL
                        p={p}
                        items={[
                          <><strong>Emerging</strong> (&lt;$1M): We reward hustle, not formal rigor</>,
                          <><strong>Growing</strong> ($1–10M): Standard expectations, building systems</>,
                          <><strong>Established</strong> (&gt;$10M): Full accountability expected</>,
                        ]}
                      />
                    </div>
                  </Card>
                </Grid>
              </div>

              {/* Data Confidence Signal */}
              <div style={{ marginTop: 14 }}>
                <Card p={p}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                    <H3 p={p}>Data Confidence Signal</H3>
                    <Pill p={p} bg={p.bg3} fg={p.sub}>Outside the score</Pill>
                  </div>
                  <P p={p} muted>
                    Separate from the 100-point score, we compute a Data Confidence signal (0.0–1.0) that tells you how
                    much data we had to work with. This considers third-party verification, transparency seals, and how
                    many independent sources corroborate the same facts.
                  </P>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
                    <Pill p={p} bg={p.posBg} fg={p.pos}>HIGH (≥0.7): 2+ strong ratings, verified data</Pill>
                    <Pill p={p} bg={p.cautionBg} fg={p.caution}>MEDIUM (0.4–0.7): Some verification</Pill>
                    <Pill p={p} bg={p.negBg} fg={p.neg}>LOW (&lt;0.4): Limited third-party data</Pill>
                  </div>
                </Card>
              </div>
            </Section>

            {/* Risk Assessment */}
            <Section ctx={ctx} title="Risk Assessment">
              <P p={p} muted>
                Even strong charities can have red flags. We identify concerns and apply point deductions (up to −10
                points total) when we find issues that could affect your donation’s impact. Deductions are
                size-adjusted: emerging organizations (&lt;$1M) get lighter penalties for missing formal systems, while
                established organizations (&gt;$10M) are held to higher standards.
              </P>
              <Grid isMobile={isMobile}>
                <Card p={p}>
                  <H3 p={p}>Red Flags We Check</H3>
                  <ul style={{ listStyle: 'none', margin: '12px 0 0', padding: 0 }}>
                    <Flag p={p} pts="-5" tone="neg">Program ratio under 50% (most money not reaching programs)</Flag>
                    <Flag p={p} pts="-5" tone="neg">Board under 3 members (governance concerns)</Flag>
                    <Flag p={p} pts="-5" tone="neg">Noncash/gift-in-kind inflation (≥50% of revenue is noncash contributions)</Flag>
                    <Flag p={p} pts="-5" tone="neg">High domestic burn rate (≥70% spent domestically for international-focused orgs)</Flag>
                    <Flag p={p} pts="-3" tone="caution">Charity Navigator advisory flag</Flag>
                    <Flag p={p} pts="-3" tone="caution">Related party transactions</Flag>
                    <Flag p={p} pts="-3" tone="caution">Zakat reserve hoarding (≥3 years reserves for zakat-accepting charities)</Flag>
                    <Flag p={p} pts="-2" tone="caution">Less than 1 month operating reserves</Flag>
                    <Flag p={p} pts="-2" tone="caution">No outcome tracking (size-adjusted)</Flag>
                    <Flag p={p} pts="-1" tone="sub">No theory of change documented (size-adjusted)</Flag>
                  </ul>
                  <P p={p} muted>
                    Total deductions are capped at −10 points. Some flags have moderate variants (e.g., −2 for 25–50%
                    noncash ratio).
                  </P>
                </Card>
                <Card p={p}>
                  <H3 p={p}>What We DON’T Penalize</H3>
                  <div style={{ marginTop: 12 }}>
                    <DontRow p={p}><strong>Conflict zone operations</strong> — Higher costs in Gaza, Syria, Yemen are legitimate</DontRow>
                    <DontRow p={p}><strong>Newer organizations</strong> — Less data doesn’t mean worse; emerging orgs get lighter risk expectations</DontRow>
                    <DontRow p={p}><strong>Non-Muslim-focused work</strong> — We evaluate all charities fairly</DontRow>
                  </div>
                </Card>
              </Grid>
            </Section>

            {/* How We Verify Our Work */}
            <Section ctx={ctx} title="How We Verify Our Work">
              <P p={p} muted>
                We know trust must be earned. Here’s what happens behind the scenes to make sure our evaluations are
                accurate and fair.
              </P>
              <Grid isMobile={isMobile}>
                <Card p={p}>
                  <H3 p={p}>Every Claim Has a Source</H3>
                  <P p={p} muted>
                    When we say a charity has a 92% program expense ratio, that number comes from their IRS Form 990.
                    When we mention a Charity Navigator rating, that links to their actual profile. You can verify any
                    factual claim we make by following the citation to the original source.
                  </P>
                </Card>
                <Card p={p}>
                  <H3 p={p}>When Sources Disagree</H3>
                  <P p={p} muted>
                    Sometimes Charity Navigator reports different revenue than the IRS filing. When this happens, we log
                    the conflict and follow a clear priority: official IRS filings beat rating agency data, which beats
                    self-reported information from charity websites. You see the winning value; we keep records of what
                    was overridden.
                  </P>
                </Card>
                <Card p={p}>
                  <H3 p={p}>Apples to Apples</H3>
                  <P p={p} muted>
                    A legal advocacy organization has different cost structures than a food bank. We use cause-adjusted
                    benchmarks — different scales for food, education, healthcare, humanitarian, and other cause areas.
                    This means a humanitarian relief org is compared against humanitarian benchmarks, not education
                    benchmarks.
                  </P>
                </Card>
                <Card p={p}>
                  <H3 p={p}>The “Case Against”</H3>
                  <P p={p} muted>
                    Every evaluation includes structured risk checks and any applicable point deductions. Some profiles
                    also include expanded narrative limitations. If a charity lacks rigorous impact studies or has
                    governance concerns, we flag that in the evaluation data.
                  </P>
                </Card>
              </Grid>
              <div style={{ marginTop: 14 }}>
                <Callout p={p} tone="pos" title="Special Consideration: Conflict Zones">
                  Charities operating in active conflict zones (Gaza, Syria, Yemen, Sudan, Afghanistan, Somalia,
                  Ukraine) face legitimately higher costs — security, logistics, and staff safety all cost more in war
                  zones. Our cause-adjusted benchmarks for humanitarian work account for this context rather than
                  penalizing organizations for circumstances beyond their control.
                </Callout>
              </div>
            </Section>

            {/* See It In Action */}
            <Section ctx={ctx} title="See It In Action">
              <P p={p} muted>
                We’ve evaluated {summaries.filter(s => s.amalScore != null).length} charities using this framework.
                Here’s what the data reveals.
              </P>

              {SHOW_AMAL_SCORE && (
                <Grid isMobile={isMobile} cols={isMobile ? 2 : 4}>
                  {[
                    [scoreBuckets.exceptional, '75+ Exceptional', p.pos],
                    [scoreBuckets.good, '60–74 Good', p.accent2],
                    [scoreBuckets.developing, '30–59 Developing', p.caution],
                    [scoreBuckets.emerging, '<30 Emerging', p.sub2],
                  ].map(([n, label, color], i) => (
                    <Card key={i} p={p} style={{ textAlign: 'center', padding: 16 }}>
                      <div style={{ fontFamily: FONT_DISPLAY, fontSize: 28, color: color as string, fontVariantNumeric: 'tabular-nums' }}>{n as number}</div>
                      <div style={{ fontSize: 12, color: p.sub }}>{label as string}</div>
                    </Card>
                  ))}
                </Grid>
              )}

              {/* Calibration Snapshot */}
              {calibrationReport && (
                <div style={{ marginTop: 14 }}>
                  <Card p={p}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <H3 p={p}>Calibration Snapshot</H3>
                      <span style={{ fontSize: 11, color: p.sub2 }}>
                        {new Date(calibrationReport.metadata.generated_at).toLocaleDateString()} · config {calibrationReport.metadata.config_version}
                      </span>
                    </div>
                    {calibrationReport.warnings.length > 0 && (
                      <Callout p={p} tone="caution" title="Calibration warnings">
                        <ul style={{ margin: 0, paddingLeft: 18 }}>
                          {calibrationReport.warnings.map((warning, idx) => (
                            <li key={idx} style={{ marginBottom: 2 }}>{warning}</li>
                          ))}
                        </ul>
                      </Callout>
                    )}
                    <Grid isMobile={isMobile} cols={isMobile ? 2 : 4}>
                      {[
                        ['Fallback', `${calibrationReport.fallback.rate_pct}%`],
                        ['Near Threshold', `${calibrationReport.near_threshold.rate_pct}%`],
                        ['Top Cue', CUE_DISPLAY_LABELS[Object.entries(calibrationReport.distributions.recommendation_cue).sort((a, b) => b[1] - a[1])[0]?.[0] || ''] || '—'],
                        ['Top Stage', getEvidenceStageLabel(Object.entries(calibrationReport.distributions.evidence_stage).sort((a, b) => b[1] - a[1])[0]?.[0] || '') || '—'],
                      ].map(([label, val]) => (
                        <div key={label}>
                          <Kicker p={p}>{label}</Kicker>
                          <div style={{ fontFamily: FONT_DISPLAY, fontSize: 18, color: p.fg }}>{val}</div>
                        </div>
                      ))}
                    </Grid>
                  </Card>
                </div>
              )}

              {/* Insights Visualization — interactive viz panels keep their own internals */}
              <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 16 }}>
                {loading ? (
                  <Card p={p}>
                    <div style={{ height: 240, borderRadius: 8, background: p.bg2 }} />
                  </Card>
                ) : (
                  <>
                    <CauseAreaMatrix charities={insightsData} />
                    <MethodologyInsights charities={insightsData} />
                  </>
                )}
              </div>
            </Section>

            {/* Zakat Routing */}
            <Section ctx={ctx} title="Zakat Routing">
              <P p={p} muted>
                Beyond the score, we show whether a charity publicly says it accepts Zakat on its website. This is a
                binary routing cue based on the charity’s own public claim, not a GMG judgment about fiqh compliance or
                donor permissibility — a Sadaqah-only charity can still have an excellent score.
              </P>
              <Grid isMobile={isMobile}>
                <Card p={p} style={{ borderColor: p.pos }}>
                  <H3 p={p}>Accepts Zakat</H3>
                  <P p={p} muted>
                    The charity explicitly says on its website that it accepts Zakat donations. This does not mean Good
                    Measure Giving has independently verified fund segregation, fiqh compliance, or whether your
                    donation definitely counts as valid Zakat.
                  </P>
                  <p style={{ fontSize: 12.5, color: p.sub2, margin: 0 }}>
                    <strong>How we detect:</strong> We scan the charity’s website for an explicit public statement that
                    it accepts Zakat
                  </p>
                </Card>
                <Card p={p}>
                  <H3 p={p}>Sadaqah</H3>
                  <P p={p} muted>
                    The charity does not explicitly claim to accept Zakat on their website. These charities are suitable
                    for general Sadaqah donations but may or may not serve Zakat-relevant beneficiary groups.
                  </P>
                  <p style={{ fontSize: 12.5, color: p.sub2, margin: 0 }}>
                    <strong>Note:</strong> Some charities may accept Zakat but not advertise it
                  </p>
                </Card>
              </Grid>

              <div style={{ marginTop: 14 }}>
                <Card p={p}>
                  <H3 p={p}>The Eight Zakat Categories (Asnaf)</H3>
                  <P p={p} muted>
                    When a charity publicly says it accepts Zakat, we note which Quranic categories (9:60) its work
                    serves:
                  </P>
                  <Grid isMobile={isMobile}>
                    <UL
                      p={p}
                      items={[
                        <><strong>1. Al-Fuqara</strong> — The poor (below nisab)</>,
                        <><strong>2. Al-Masakin</strong> — The destitute</>,
                        <><strong>3. Al-Amileen</strong> — Zakat administrators</>,
                        <><strong>4. Al-Muallafatul Quloob</strong> — New Muslims</>,
                      ]}
                    />
                    <UL
                      p={p}
                      items={[
                        <><strong>5. Ar-Riqab</strong> — Freeing captives (refugees, trafficking victims)</>,
                        <><strong>6. Al-Gharimeen</strong> — Those in debt</>,
                        <><strong>7. Fi Sabilillah</strong> — In Allah’s path (education, humanitarian, dawah)</>,
                        <><strong>8. Ibnus-Sabil</strong> — Stranded travelers (displaced persons)</>,
                      ]}
                    />
                  </Grid>
                </Card>
              </div>

              <div style={{ marginTop: 14 }}>
                <Callout p={p} tone="caution" title="Important">
                  Our Zakat classifications are informational only and do not constitute religious rulings. They are
                  based on what charities claim on their own websites. Please consult a qualified scholar for definitive
                  guidance on your specific situation.
                </Callout>
              </div>
            </Section>

            {/* Data Sources */}
            <Section ctx={ctx} title="Our Data Sources">
              <P p={p} muted>
                We aggregate data from multiple trusted sources and reconcile conflicts automatically. When sources
                disagree, we favor official filings and verified data.
              </P>
              <Grid isMobile={isMobile}>
                <Card p={p}>
                  <H3 p={p}>Data Sources</H3>
                  <UL
                    p={p}
                    items={[
                      <><strong>IRS Form 990</strong> — Official financial filings (via ProPublica API)</>,
                      <><strong>Charity Navigator</strong> — Ratings, financial health, accountability scores</>,
                      <><strong>Candid (GuideStar)</strong> — Transparency seals, outcome tracking data</>,
                      <><strong>BBB Wise Giving Alliance</strong> — Governance standards</>,
                      <><strong>Charity Websites</strong> — Programs, mission, Zakat policies</>,
                      <><strong>Web Search</strong> — Zakat claims, third-party evaluations, awards discovered across the web</>,
                    ]}
                  />
                  <H3 p={p}>Cost Benchmarks</H3>
                  <P p={p} muted>
                    We use cause-adjusted benchmarks informed by evidence-based giving research to compare
                    cost-effectiveness across different types of charities (food, healthcare, education, etc.)
                  </P>
                </Card>
                <Card p={p}>
                  <H3 p={p}>What We Extract</H3>
                  <UL
                    p={p}
                    items={[
                      'Revenue, expenses, program expense ratios',
                      'Board size, working capital ratios',
                      'Outcome measurement and years of tracking',
                      'Zakat claims from charity websites',
                      'Third-party ratings and transparency seals',
                      'Theory of change and program descriptions',
                    ]}
                  />
                </Card>
              </Grid>
            </Section>

            {/* Human + AI */}
            <Section ctx={ctx} title="How We Use AI">
              <P p={p} muted>
                We use AI to process large amounts of data consistently. The AI extracts and structures data from
                websites, PDFs, and filings. The scoring itself uses deterministic code — the AI never decides point
                values or makes scoring judgments.
              </P>
              <P p={p} muted>
                We’re transparent about this because we believe it produces more scalable and consistent analysis.
              </P>
              <Grid isMobile={isMobile}>
                <Card p={p}>
                  <H3 p={p}>What AI Does</H3>
                  <UL
                    p={p}
                    items={[
                      'Extracts structured data from Form 990s and charity websites',
                      'Parses rating agency pages (CN, Candid, BBB)',
                      'Detects Zakat claims on charity websites',
                      'Generates narrative summaries citing specific sources',
                      'Searches for theory of change documents',
                    ]}
                  />
                </Card>
                <Card p={p}>
                  <H3 p={p}>What Code Does (Not AI)</H3>
                  <UL
                    p={p}
                    items={[
                      <><strong>All scoring math</strong> — deterministic Python functions</>,
                      <><strong>Wallet tag assignment</strong> — rule-based on Zakat claims</>,
                      <><strong>Risk deductions</strong> — formula-based on red flags</>,
                      <><strong>Tier classification</strong> — threshold-based scoring</>,
                    ]}
                  />
                </Card>
              </Grid>

              <div style={{ marginTop: 14 }}>
                <Card p={p}>
                  <H3 p={p}>Quality Controls</H3>
                  <Grid isMobile={isMobile}>
                    <UL
                      p={p}
                      items={[
                        <><strong>Cited sources</strong> — every claim references specific data</>,
                        <><strong>Reproducible scores</strong> — same data = same score every time</>,
                      ]}
                    />
                    <UL
                      p={p}
                      items={[
                        <><strong>Community feedback</strong> — report errors and we’ll investigate</>,
                        <><strong>Open methodology</strong> — our scoring rubric is documented</>,
                      ]}
                    />
                  </Grid>
                  <Callout p={p} tone="caution" title="Limitation">
                    This is an automated system. AI can misinterpret website content or miss information that requires
                    human context. We do not manually review every evaluation before publishing. If you notice an error
                    in a charity’s evaluation, please let us know and we’ll investigate.
                  </Callout>
                </Card>
              </div>

              <div style={{ marginTop: 14 }}>
                <Callout p={p} tone="pos" title="Full Transparency: View Our AI Prompts">
                  We publish core prompts and prompt annotations — from data extraction to narrative generation to
                  quality validation. See how we instruct models and where we continue expanding prompt-level
                  transparency.{' '}
                  <Link to="/prompts" style={{ color: p.accent, fontWeight: 500, textDecoration: 'none' }}>
                    View all prompts →
                  </Link>
                </Callout>
              </div>
            </Section>

            {/* What We Don't Do */}
            <Section ctx={ctx} title="What We Don’t Do">
              <Card p={p}>
                <DontRow p={p}>
                  <strong>We don’t penalize conflict-zone charities unfairly.</strong> Operating in places like Gaza or
                  Syria costs more due to security and logistics. We account for this.
                </DontRow>
                <DontRow p={p}>
                  <strong>We don’t issue religious rulings.</strong> Our Zakat classifications are informational.
                  Consult a scholar for your specific situation.
                </DontRow>
                <DontRow p={p}>
                  <strong>We don’t take money from charities we rate.</strong> Our evaluations are independent. We’re
                  funded by donors who share our mission.
                </DontRow>
                <DontRow p={p}>
                  <strong>We don’t manually review every evaluation.</strong> This is an automated system that
                  prioritizes consistency and citation. We verify through sources, not human judgment — which means we
                  may miss nuance that a human expert would catch.
                </DontRow>
              </Card>
            </Section>

            {/* Reference & Citation — makes this page a citable methodology reference */}
            <Section ctx={ctx} title="Reference & Citation">
              <P p={p} muted>
                The exact formula, current rubric version, and source data behind every score — so you can reference
                our methodology directly.
              </P>
              <Grid isMobile={isMobile}>
                <Card p={p}>
                  <H3 p={p}>The Scoring Formula</H3>
                  <div
                    style={{
                      fontFamily: FONT_MONO,
                      fontSize: 14,
                      background: p.bg2,
                      border: `1px solid ${p.rule}`,
                      borderRadius: 8,
                      padding: '12px 14px',
                      color: p.fg,
                      margin: '0 0 12px',
                    }}
                  >
                    GMG Score = Impact + Alignment − Risk
                  </div>
                  <UL
                    p={p}
                    items={[
                      <><strong>Impact</strong>: 0 to 50 points</>,
                      <><strong>Alignment</strong>: 0 to 50 points</>,
                      <><strong>Risk</strong>: 0 to −10 points (deductions)</>,
                      <><strong>Total</strong>: 0 to 100</>,
                    ]}
                  />
                  <p style={{ fontSize: 12.5, color: p.sub2, margin: 0 }}>
                    Data Confidence (0.0–1.0) is reported separately and does not change the score.
                  </p>
                </Card>
                <Card p={p}>
                  <H3 p={p}>Version & Sources</H3>
                  <dl style={{ margin: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                      <dt style={{ fontSize: 14, color: p.sub }}>Rubric version</dt>
                      <dd style={{ margin: 0 }}>
                        <Pill p={p} bg={p.posBg} fg={p.pos}>v{RUBRIC_VERSION}</Pill>
                      </dd>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                      <dt style={{ fontSize: 14, color: p.sub }}>Last updated</dt>
                      <dd style={{ margin: 0, fontSize: 14, color: p.fg }}>{METHODOLOGY_LAST_UPDATED}</dd>
                    </div>
                    <div>
                      <dt style={{ fontSize: 14, color: p.sub, marginBottom: 4 }}>Data sources</dt>
                      <dd style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: p.fg }}>
                        IRS Form 990 (via ProPublica), Charity Navigator, Candid (GuideStar), BBB Wise Giving Alliance,
                        charity websites, and web search.
                      </dd>
                    </div>
                  </dl>
                </Card>
              </Grid>

              <div style={{ marginTop: 14 }}>
                <Card p={p}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                    <H3 p={p}>Cite This Page</H3>
                    <button
                      type="button"
                      onClick={copyCitation}
                      style={{
                        fontFamily: FONT_MONO,
                        fontSize: 11,
                        padding: '6px 12px',
                        borderRadius: 8,
                        background: p.bg3,
                        color: p.sub,
                        border: `1px solid ${p.rule}`,
                        cursor: 'pointer',
                      }}
                    >
                      {citationCopied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <P p={p} muted>Referencing our scoring in research, a grant report, or an article? Use this citation:</P>
                  <p
                    style={{
                      fontSize: 13,
                      lineHeight: 1.6,
                      background: p.bg2,
                      border: `1px solid ${p.rule}`,
                      borderRadius: 8,
                      padding: '12px 14px',
                      color: p.fg,
                      margin: '0 0 12px',
                    }}
                  >
                    {CITATION_TEXT}
                  </p>
                  <p style={{ fontSize: 12.5, color: p.sub2, margin: 0 }}>
                    Run a charity yourself? Add our trust badge or a backlink from our{' '}
                    <Link to="/link-to-us" style={{ color: p.accent, textDecoration: 'none' }}>Link to Us</Link> page.
                  </p>
                </Card>
              </div>
            </Section>

            {/* CTA */}
            <Section ctx={ctx}>
              <Card p={p} style={{ textAlign: 'center', padding: isMobile ? 28 : 40 }}>
                <h2 style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: isMobile ? 26 : 32, margin: '0 0 12px', color: p.fg }}>
                  Ready to explore?
                </h2>
                <p style={{ fontSize: 16, lineHeight: 1.6, color: p.sub, maxWidth: 480, margin: '0 auto 24px' }}>
                  Browse our directory of evaluated charities and find organizations that match your giving goals.
                </p>
                <CtaLink p={p} to="/browse">Browse Charities →</CtaLink>
              </Card>
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};

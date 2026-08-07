// "Where your money goes" — the expense split (computed once, in
// `expenseSplit`, so it can never disagree with the Financials card), the
// multi-year revenue/expense trend, how grants flow out the door, and the
// gift-in-kind/burn-rate signals that flag when those figures might be
// padded or inflated.
//
// Grant totals, the domestic/foreign split, and the regional breakdown are
// public. Individual named recipients sit behind the community gate. Every
// foreign grant (Schedule F, Part II) has no identifiable recipient at
// all — the IRS's own instructions tell filers to leave the name and EIN
// columns blank there, for every grant regardless of size, so this is IRS
// form design rather than a gap in the charity's disclosure. Named
// recipients and the unattributed foreign total are rendered together,
// whenever each is non-empty: a charity can have both (named domestic
// grants alongside anonymous foreign ones), and hiding either would either
// disappear real money from the page or wrongly imply named recipients
// exist but are just hidden.
//
// GIK signals (noncashRatio, cashAdjustedProgramRatio, domesticBurnRate) are
// sparse (71/166 charities have at least one) and each is guarded
// independently — a charity can have one without the others. Each is shown
// as a label plus a plain-language gloss, not a bare ratio, since "noncash
// ratio: 0.43" means nothing to a non-expert donor.

import React from 'react';
import { Section } from './Section';
import { ConcernList } from './ConcernList';
import { SeriesChart } from '../SeriesChart';
import { GatedBlock } from '../GatedBlock';
import { Kicker, Stacked } from '../primitives';
import { GmgPalette, FONT_MONO } from '../tokens';
import type { GmgCharity } from '../charityAdapter';
import { expenseSplit } from './expenseSplit';

const usd = (n: number | null): string => {
  if (n == null) return '—';
  const compact = Math.abs(n) >= 1_000_000;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: compact ? 'compact' : 'standard',
    minimumFractionDigits: 0,
    maximumFractionDigits: compact ? 1 : 0,
  }).format(n);
};

// Full, non-compacted dollar figures — distinct from the compact `usd` above
// (used for the grant totals). Only ever called on an already-guarded,
// non-null value: see `figures` below, which omits a row entirely rather
// than calling this with null.
const usdFull = (n: number): string =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const pct = (n: number): string => `${Math.round(n * 100)}%`;

const GikFact: React.FC<{ label: string; value: string; gloss: string; p: GmgPalette }> = ({
  label,
  value,
  gloss,
  p,
}) => (
  <div style={{ border: `1px solid ${p.rule}`, borderRadius: 6, padding: 12, background: p.bg2 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
      <Kicker p={p}>{label}</Kicker>
      <span style={{ fontFamily: FONT_MONO, fontSize: 13, color: p.fg }}>{value}</span>
    </div>
    <p style={{ fontSize: 12, color: p.sub, lineHeight: 1.5, margin: '6px 0 0' }}>{gloss}</p>
  </div>
);

export const WhereMoneyGoes: React.FC<{
  c: GmgCharity;
  p: GmgPalette;
  isMobile: boolean;
  padX: number;
}> = ({ c, p, isMobile, padX }) => {
  const split = expenseSplit(c);
  const gf = c.grantFlows;

  // The exact dollar figures behind the percentages above. Each is guarded
  // independently and the row is omitted entirely when null — these fields
  // are legitimately absent for some charities, and a blank cell or a
  // fabricated "$0" would misstate a fact this page's premise (traceable
  // claims) depends on.
  const figures: [string, string][] = [];
  if (c.totalRevenue != null) figures.push(['Total revenue', usdFull(c.totalRevenue)]);
  if (c.programExpenses != null) figures.push(['Program expenses', usdFull(c.programExpenses)]);
  if (c.adminExpenses != null) figures.push(['Admin expenses', usdFull(c.adminExpenses)]);
  if (c.fundraisingExpenses != null) figures.push(['Fundraising', usdFull(c.fundraisingExpenses)]);
  if (c.netAssets != null) figures.push(['Net assets', usdFull(c.netAssets)]);
  if (c.reserveMonths != null) figures.push(['Reserves', `${c.reserveMonths} mo`]);

  const gikFacts: { label: string; value: string; gloss: string }[] = [];
  if (c.noncashRatio != null) {
    gikFacts.push({
      label: 'Non-cash share of revenue',
      value: pct(c.noncashRatio),
      gloss: `${pct(c.noncashRatio)} of contributions came as donated goods or services (gifts-in-kind), not cash.`,
    });
  }
  if (c.cashAdjustedProgramRatio != null) {
    gikFacts.push({
      label: 'Program ratio, cash only',
      value: pct(c.cashAdjustedProgramRatio),
      gloss: `With donated goods stripped out, ${pct(c.cashAdjustedProgramRatio)} of the charity's actual cash spending went to programs.`,
    });
  }
  if (c.domesticBurnRate != null) {
    gikFacts.push({
      label: 'Domestic spending share',
      value: pct(c.domesticBurnRate),
      gloss: `${pct(c.domesticBurnRate)} of spending stayed in the US rather than going out as grants to foreign organizations.`,
    });
  }

  return (
    <Section id="money" title="Where your money goes" p={p} padX={padX}>
      {split && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: p.sub2, marginBottom: 4 }}>
            <span>Expense allocation</span>
            <span>{usd(c.totalRevenue)} revenue</span>
          </div>
          <Stacked
            h={10}
            segs={[
              { pct: split.progPct, color: p.accent },
              { pct: split.adminPct, color: p.accent2 },
              { pct: split.fundPct, color: p.warn },
            ]}
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8, fontSize: 11 }}>
            <span>
              <span style={{ color: p.accent }}>■</span> Programs {split.progPct}%
            </span>
            <span>
              <span style={{ color: p.accent2 }}>■</span> Admin {split.adminPct}%
            </span>
            <span>
              <span style={{ color: p.warn }}>■</span> Fundraising {split.fundPct}%
            </span>
          </div>

          {figures.length > 0 && (
            <div
              style={{
                borderTop: `1px solid ${p.rule}`,
                marginTop: 10,
                paddingTop: 8,
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: 4,
                fontSize: 11.5,
              }}
            >
              {figures.map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '4px 0' }}>
                  <span style={{ color: p.sub }}>{k}</span>
                  <span style={{ color: p.fg, fontFamily: FONT_MONO, fontSize: 10.5 }}>{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {gikFacts.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <Kicker p={p}>Gift-in-kind &amp; overhead signals</Kicker>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 10,
              marginTop: 8,
            }}
          >
            {gikFacts.map((f) => (
              <GikFact key={f.label} label={f.label} value={f.value} gloss={f.gloss} p={p} />
            ))}
          </div>
        </div>
      )}

      {c.financialSeries.length >= 2 && (
        <div style={{ marginBottom: 20 }}>
          <Kicker p={p}>Multi-year trend</Kicker>
          <div style={{ marginTop: 8 }}>
            <SeriesChart series={c.financialSeries} p={p} />
          </div>
        </div>
      )}

      {gf && (
        <div style={{ marginBottom: 20 }}>
          <Kicker p={p}>Grants{gf.taxYear ? ` · tax year ${gf.taxYear}` : ''}</Kicker>
          <div
            style={{
              display: 'flex',
              flexDirection: isMobile ? 'column' : 'row',
              flexWrap: 'wrap',
              gap: isMobile ? 6 : 16,
              marginTop: 8,
              fontSize: 12.5,
            }}
          >
            <span>
              <span style={{ color: p.sub }}>Total granted</span>{' '}
              <strong style={{ color: p.fg }}>{usd(gf.totalAmount)}</strong>
            </span>
            <span>
              <span style={{ color: p.sub }}>Domestic</span>{' '}
              <strong style={{ color: p.fg }}>{usd(gf.domestic.amount)}</strong> ({gf.domestic.count})
            </span>
            <span>
              <span style={{ color: p.sub }}>Foreign</span>{' '}
              <strong style={{ color: p.fg }}>{usd(gf.foreign.amount)}</strong> ({gf.foreign.count})
            </span>
          </div>

          {gf.byRegion.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Kicker p={p}>By region</Kicker>
              <div style={{ display: 'grid', gap: 4, marginTop: 6, fontSize: 12 }}>
                {gf.byRegion.map((r) => (
                  <div key={r.region} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ color: p.sub }}>{r.region}</span>
                    <span style={{ fontFamily: FONT_MONO, color: p.fg }}>
                      {usd(r.amount)} ({r.count})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ marginTop: 12, display: 'grid', gap: 12 }}>
            {gf.topRecipients.length > 0 && (
              <GatedBlock label="Grant recipients" p={p}>
                <div style={{ display: 'grid', gap: 6 }}>
                  {gf.topRecipients.map((r, i) => (
                    <div
                      key={`${r.ein ?? r.name}-${i}`}
                      style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12 }}
                    >
                      <span style={{ color: p.fg }}>
                        {r.name}
                        {r.isForeign ? ' (foreign)' : ''}
                      </span>
                      <span style={{ fontFamily: FONT_MONO, color: p.sub }}>{usd(r.amount)}</span>
                    </div>
                  ))}
                </div>
              </GatedBlock>
            )}

            {gf.unattributed.amount > 0 && (
              <div>
                <div style={{ fontSize: 12.5, color: p.sub, lineHeight: 1.5 }}>
                  {usd(gf.unattributed.amount)} across {gf.unattributed.count} grants made outside the
                  US, with no recipient named. Form 990's foreign-grants schedule (Schedule F) reports
                  these by region and purpose rather than by name — that's how the IRS collects this
                  data, not a gap in what the charity disclosed.
                </div>
                {gf.unattributedByPurpose.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <Kicker p={p}>By purpose</Kicker>
                    <div style={{ display: 'grid', gap: 4, marginTop: 6, fontSize: 12 }}>
                      {gf.unattributedByPurpose.map((u) => (
                        <div key={u.purpose} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                          <span style={{ color: p.sub }}>{u.purpose}</span>
                          <span style={{ fontFamily: FONT_MONO, color: p.fg }}>
                            {usd(u.amount)} ({u.count})
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <ConcernList concerns={[...c.concerns.byAnchor.money, ...c.concerns.byAnchor.reserves]} p={p} />
    </Section>
  );
};

export default WhereMoneyGoes;

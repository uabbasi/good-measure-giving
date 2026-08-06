// "Where your money goes" — the expense split (computed once, in
// `expenseSplit`, so it can never disagree with the Financials card), the
// multi-year revenue/expense trend, and how grants flow out the door.
//
// Grant totals, the domestic/foreign split, and the regional breakdown are
// public. Individual named recipients sit behind the community gate. Some
// charities report large batches of grants with no identifiable recipient
// (Schedule I/F omits both name and EIN for e.g. disaster relief paid
// directly to households) — when that leaves `topRecipients` empty, the
// unattributed total is stated plainly instead of rendering an empty gated
// list, which would wrongly imply named recipients exist but are just hidden.
//
// GIK signals (noncashRatio, cashAdjustedProgramRatio, domesticBurnRate) are
// NOT rendered here: they live on the raw `financials` object but `adaptCharity`
// (frozen) does not expose them on `GmgCharity`. See task-4-report.md.

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

export const WhereMoneyGoes: React.FC<{
  c: GmgCharity;
  p: GmgPalette;
  isMobile: boolean;
  padX: number;
}> = ({ c, p, isMobile, padX }) => {
  const split = expenseSplit(c);
  const gf = c.grantFlows;

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

          <div style={{ marginTop: 12 }}>
            {gf.topRecipients.length > 0 ? (
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
            ) : (
              gf.unattributed.amount > 0 && (
                <div style={{ fontSize: 12.5, color: p.sub, lineHeight: 1.5 }}>
                  {usd(gf.unattributed.amount)} across {gf.unattributed.count} grants with no reported
                  recipient — common for disaster relief and other payments made directly to individual
                  households.
                </div>
              )
            )}
          </div>
        </div>
      )}

      <ConcernList concerns={[...c.concerns.byAnchor.money, ...c.concerns.byAnchor.reserves]} p={p} />
    </Section>
  );
};

export default WhereMoneyGoes;

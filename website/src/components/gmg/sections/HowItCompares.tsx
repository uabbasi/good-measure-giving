// "How it compares" — this charity's peer group and its program-ratio
// standing against the peer median and industry benchmark are public; the
// raw comparison figures (CN score, transparency score, peer count, 3yr
// revenue growth) sit behind the community gate, and the strengths deep dive
// is gated too. `similarOrganizations` carries no EIN and can't be resolved
// to a charity page, so it renders as unlinked context — visually distinct
// from the linkable "Similar charities" block elsewhere on the page, which
// this section does not touch.

import React from 'react';
import { Section } from './Section';
import { GatedBlock } from '../GatedBlock';
import { CitedText, SourceList, collectCitations } from '../CitedText';
import { Bar, Tag, Kicker } from '../primitives';
import { GmgPalette, FONT_MONO } from '../tokens';
import type { GmgCharity } from '../charityAdapter';

// peers.programRatioMedian / peers.industryProgramRatio are stored as
// fractions (0.75), unlike c.programRatioPct which the adapter already
// converts to a whole percent — put all three on the same scale before
// comparing, the same "fraction or percent" normalization expenseSplit.ts
// and the adapter itself apply elsewhere.
const asPct = (n: number): number => Math.round(n <= 1 ? n * 100 : n);

export const HowItCompares: React.FC<{
  c: GmgCharity;
  p: GmgPalette;
  isMobile: boolean;
  padX: number;
}> = ({ c, p, isMobile, padX }) => {
  const peers = c.peers;
  const outlook = c.outlook;

  const compareRows: { label: string; value: number; color: string }[] = [];
  if (c.programRatioPct != null) {
    compareRows.push({ label: 'This charity', value: c.programRatioPct, color: p.accent });
  }
  if (peers.programRatioMedian != null) {
    compareRows.push({ label: 'Peer median', value: asPct(peers.programRatioMedian), color: p.accent2 });
  }
  if (peers.industryProgramRatio != null) {
    compareRows.push({ label: 'Industry', value: asPct(peers.industryProgramRatio), color: p.warn });
  }

  const hasBenchmarks =
    peers.cnOverallScore != null ||
    peers.transparencyScore != null ||
    peers.peerCount != null ||
    outlook.revenueGrowth3yr != null;

  const hasOutlook = !!outlook.maturityStage || !!outlook.roomForFunding || outlook.strategicPriorities.length > 0;

  return (
    <Section id="compares" title="How it compares" p={p} padX={padX}>
      {peers.peerGroup && (
        <div style={{ marginBottom: 16 }}>
          <Kicker p={p}>Peer group</Kicker>
          <div style={{ fontSize: 14, color: p.fg, marginTop: 4 }}>{peers.peerGroup}</div>
        </div>
      )}

      {c.cited.peerDifferentiator.length > 0 && (
        <div style={{ marginBottom: 20, maxWidth: '75ch' }}>
          <CitedText segments={c.cited.peerDifferentiator} p={p} size={13.5} />
          <SourceList citations={collectCitations(c.cited.peerDifferentiator)} p={p} />
        </div>
      )}

      {compareRows.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <Kicker p={p}>Program ratio vs. peers</Kicker>
          <div style={{ display: 'grid', gap: 10, marginTop: 8 }}>
            {compareRows.map((row) => (
              <div key={row.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, color: p.sub, marginBottom: 4 }}>
                  <span>{row.label}</span>
                  <span style={{ fontFamily: FONT_MONO, color: p.fg }}>{row.value}%</span>
                </div>
                <Bar value={row.value} color={row.color} bg={p.bg3} h={8} />
              </div>
            ))}
          </div>
        </div>
      )}

      {hasBenchmarks && (
        <div style={{ marginBottom: 20 }}>
          <GatedBlock label="Peer benchmarks" p={p}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: 12.5 }}>
              {peers.cnOverallScore != null && (
                <span>
                  <span style={{ color: p.sub }}>Charity Navigator score</span>{' '}
                  <strong style={{ color: p.fg }}>{peers.cnOverallScore}</strong>
                </span>
              )}
              {peers.transparencyScore != null && (
                <span>
                  <span style={{ color: p.sub }}>Transparency score</span>{' '}
                  <strong style={{ color: p.fg }}>{peers.transparencyScore}</strong>
                </span>
              )}
              {peers.peerCount != null && (
                <span>
                  <span style={{ color: p.sub }}>Peers compared</span>{' '}
                  <strong style={{ color: p.fg }}>{peers.peerCount}</strong>
                </span>
              )}
              {outlook.revenueGrowth3yr != null && (
                <span>
                  <span style={{ color: p.sub }}>3yr revenue growth</span>{' '}
                  <strong style={{ color: p.fg }}>{outlook.revenueGrowth3yr}%</strong>
                </span>
              )}
            </div>
          </GatedBlock>
        </div>
      )}

      {peers.similarOrganizations.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <Kicker p={p}>Also worth knowing about</Kicker>
          <p style={{ fontSize: 11.5, color: p.sub2, margin: '4px 0 10px', lineHeight: 1.5 }}>
            Named for context, not linked — these carry no verified profile on Good Measure Giving.
          </p>
          <div style={{ display: 'grid', gap: isMobile ? 10 : 6 }}>
            {peers.similarOrganizations.map((org, i) => (
              <div key={`${org.name}-${i}`} style={{ padding: '8px 0', borderTop: i > 0 ? `1px solid ${p.rule}` : 'none' }}>
                <div style={{ fontSize: 12.5, color: p.sub, fontStyle: 'italic' }}>{org.name}</div>
                {org.differentiator && (
                  <div style={{ fontSize: 11.5, color: p.sub2, marginTop: 2, lineHeight: 1.5 }}>{org.differentiator}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {hasOutlook && (
        <div style={{ marginBottom: 20 }}>
          <Kicker p={p}>Long-term outlook</Kicker>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 14,
              marginTop: 8,
            }}
          >
            {outlook.maturityStage && (
              <div>
                <Kicker p={p}>Maturity</Kicker>
                <div style={{ fontSize: 13, color: p.fg, marginTop: 4 }}>{outlook.maturityStage}</div>
              </div>
            )}
            {outlook.roomForFunding && (
              <div>
                <Kicker p={p}>Room for funding</Kicker>
                <div style={{ marginTop: 4 }}>
                  <Tag tone="accent" p={p}>
                    {outlook.roomForFunding}
                  </Tag>
                </div>
              </div>
            )}
          </div>
          {outlook.roomForFundingExplanation && (
            <p style={{ fontSize: 12.5, color: p.sub, lineHeight: 1.6, margin: '10px 0 0', maxWidth: '75ch' }}>
              {outlook.roomForFundingExplanation}
            </p>
          )}
          {outlook.strategicPriorities.length > 0 && (
            <div style={{ marginTop: 12, maxWidth: '75ch' }}>
              <Kicker p={p}>Strategic priorities</Kicker>
              <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12.5, color: p.sub, lineHeight: 1.6 }}>
                {outlook.strategicPriorities.map((sp, i) => (
                  <li key={i}>{sp}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {c.cited.strengthsDeepDive.length > 0 && (
        <div>
          <GatedBlock label="Strengths in depth" p={p}>
            <div style={{ display: 'grid', gap: 12, maxWidth: '75ch' }}>
              {c.cited.strengthsDeepDive.map((segs, i) => (
                <div key={i}>
                  <CitedText segments={segs} p={p} size={13} />
                </div>
              ))}
            </div>
            <SourceList citations={collectCitations(...c.cited.strengthsDeepDive)} p={p} />
          </GatedBlock>
        </div>
      )}
    </Section>
  );
};

export default HowItCompares;

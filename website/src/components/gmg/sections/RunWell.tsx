// "Is it run well?" — organizational capacity (CEO name, board size and
// independence, conflict/audit policy, staff and volunteer counts,
// geographic reach) is entirely rich_narrative-only and sits behind ONE
// community gate, CEO compensation included. Risks (score_details, not the
// narrative) and their anchored concerns are public, since "is this org
// well-run" is a question a donor should be able to answer without signing
// in even when the deeper capacity facts are gated.

import React from 'react';
import { Section } from './Section';
import { ConcernList } from './ConcernList';
import { GatedBlock } from '../GatedBlock';
import { Kicker } from '../primitives';
import { GmgPalette, FONT_MONO } from '../tokens';
import type { GmgCharity } from '../charityAdapter';

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

const RISK_TONE: Record<string, { fg: keyof GmgPalette; bg: keyof GmgPalette }> = {
  high: { fg: 'neg', bg: 'negBg' },
  medium: { fg: 'caution', bg: 'cautionBg' },
  low: { fg: 'pos', bg: 'posBg' },
};

const Fact: React.FC<{ label: string; value: React.ReactNode; p: GmgPalette }> = ({ label, value, p }) => (
  <div>
    <Kicker p={p}>{label}</Kicker>
    <div style={{ fontSize: 14, color: p.fg, marginTop: 4 }}>{value}</div>
  </div>
);

export const RunWell: React.FC<{
  c: GmgCharity;
  p: GmgPalette;
  isMobile: boolean;
  padX: number;
}> = ({ c, p, isMobile, padX }) => {
  const cap = c.capacity;
  const hasCeoComp = cap.ceoCompensation != null || cap.ceoCompensationPctRevenue != null;

  const facts: { label: string; value: React.ReactNode }[] = [];
  if (cap.ceoName) facts.push({ label: 'CEO', value: cap.ceoName });
  if (cap.boardSize != null) facts.push({ label: 'Board size', value: cap.boardSize.toLocaleString() });
  if (cap.independentBoardPct != null) {
    facts.push({ label: 'Independent board', value: `${Math.round(cap.independentBoardPct * 100)}%` });
  }
  if (cap.hasConflictPolicy != null) {
    facts.push({ label: 'Conflict-of-interest policy', value: cap.hasConflictPolicy ? 'Yes' : 'No' });
  }
  if (cap.hasFinancialAudit != null) {
    facts.push({ label: 'Independent financial audit', value: cap.hasFinancialAudit ? 'Yes' : 'No' });
  }
  if (cap.employeesCount != null) facts.push({ label: 'Employees', value: cap.employeesCount.toLocaleString() });
  if (cap.volunteersCount != null) facts.push({ label: 'Volunteers', value: cap.volunteersCount.toLocaleString() });
  if (cap.programsCount != null) facts.push({ label: 'Programs', value: cap.programsCount.toLocaleString() });
  if (cap.geographicReach) facts.push({ label: 'Geographic reach', value: cap.geographicReach });

  const hasCapacity = facts.length > 0 || hasCeoComp;

  return (
    <Section id="run-well" title="Is it run well?" p={p} padX={padX}>
      {hasCapacity && (
        <div style={{ marginBottom: 20 }}>
          <GatedBlock label="Organizational capacity" p={p}>
            {facts.length > 0 && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: 14,
                  marginBottom: hasCeoComp ? 16 : 0,
                }}
              >
                {facts.map((f) => (
                  <Fact key={f.label} label={f.label} value={f.value} p={p} />
                ))}
              </div>
            )}

            {hasCeoComp && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: 12.5 }}>
                {cap.ceoCompensation != null && (
                  <span>
                    <span style={{ color: p.sub }}>Compensation</span>{' '}
                    <strong style={{ color: p.fg }}>{usd(cap.ceoCompensation)}</strong>
                  </span>
                )}
                {cap.ceoCompensationPctRevenue != null && (
                  <span>
                    <span style={{ color: p.sub }}>% of revenue</span>{' '}
                    <strong style={{ color: p.fg }}>{cap.ceoCompensationPctRevenue}%</strong>
                  </span>
                )}
              </div>
            )}
          </GatedBlock>
        </div>
      )}

      {c.risks.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <Kicker p={p}>Risks on file</Kicker>
          <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
            {c.risks.map((risk, i) => {
              const tone = RISK_TONE[risk.severity] ?? RISK_TONE.medium;
              return (
                <div
                  key={i}
                  style={{
                    border: `1px solid ${p[tone.bg]}`,
                    background: p[tone.bg],
                    borderRadius: 6,
                    padding: '10px 12px',
                  }}
                >
                  <div
                    style={{
                      fontFamily: FONT_MONO,
                      fontSize: 10,
                      letterSpacing: '0.04em',
                      textTransform: 'uppercase',
                      color: p[tone.fg],
                      fontWeight: 600,
                    }}
                  >
                    {risk.category}
                  </div>
                  <div style={{ fontSize: 12, color: p.sub, marginTop: 4, lineHeight: 1.5, maxWidth: '75ch' }}>
                    {risk.description}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <ConcernList concerns={[...c.concerns.byAnchor.governance, ...c.concerns.byAnchor.risks]} p={p} />
    </Section>
  );
};

export default RunWell;

// "Is it right for you?" — zakat verification (score_details.zakat: pass/
// fail, asnaf category, quoted evidence) is public; it is a hard fact, not a
// narrative judgment. Everything else on this page is rich_narrative-only
// and sits behind the community gate, one gate per coherent rn block:
// `donor_fit_matrix`, `ideal_donor_profile` (best-for/ideal-for/considerations/
// not-ideal-for), and `case_against` (summary + risk factors + mitigation,
// now shown together rather than splitting the summary out as public).

import React from 'react';
import { Section } from './Section';
import { ConcernList } from './ConcernList';
import { GatedBlock } from '../GatedBlock';
import { CitedText, SourceList, collectCitations } from '../CitedText';
import { Tag, Kicker } from '../primitives';
import { GmgPalette } from '../tokens';
import type { GmgCharity } from '../charityAdapter';

const Fact: React.FC<{ label: string; value: string; p: GmgPalette }> = ({ label, value, p }) => (
  <div>
    <Kicker p={p}>{label}</Kicker>
    <div style={{ fontSize: 13, color: p.fg, marginTop: 4 }}>{value}</div>
  </div>
);

export const RightForYou: React.FC<{
  c: GmgCharity;
  p: GmgPalette;
  isMobile: boolean;
  padX: number;
}> = ({ c, p, isMobile, padX }) => {
  const dfm = c.donorFitMatrix;
  const asnafServed = dfm.zakatAsnafServed;

  const facts: { label: string; value: string }[] = [];
  if (dfm.causeArea) facts.push({ label: 'Cause area', value: dfm.causeArea });
  if (dfm.givingStyle) facts.push({ label: 'Giving style', value: dfm.givingStyle });
  if (dfm.evidenceRigor) facts.push({ label: 'Evidence rigor', value: dfm.evidenceRigor });
  if (dfm.geographicFocus) facts.push({ label: 'Geographic focus', value: dfm.geographicFocus });
  if (dfm.zakatStatus) facts.push({ label: 'Zakat status', value: dfm.zakatStatus });
  if (asnafServed.length > 0) facts.push({ label: 'Asnaf served', value: asnafServed.join(', ') });

  const hasFitNotes =
    c.bestForSummary || c.idealFor.length > 0 || c.considerations.length > 0 || c.notIdealFor.length > 0;
  const hasCaseAgainst =
    c.cited.caseAgainstSummary.length > 0 || c.caseAgainstFactors.length > 0 || !!c.caseAgainstMitigation;

  return (
    <Section id="right-for-you" title="Is it right for you?" p={p} padX={padX}>
      <div
        style={{
          marginBottom: 20,
          border: `1px solid ${p.rule}`,
          borderRadius: 6,
          padding: 14,
          background: p.bg2,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
          <Kicker p={p}>Zakat verification</Kicker>
          <Tag tone={c.claimsZakat ? 'accent' : 'muted'} p={p}>
            {c.claimsZakat ? 'Pass' : 'Sadaqah'}
          </Tag>
        </div>
        {c.zakatEvidence && (
          <p style={{ fontSize: 13, color: p.fg, lineHeight: 1.55, margin: 0, fontStyle: 'italic' }}>
            &ldquo;{c.zakatEvidence}&rdquo;
          </p>
        )}
        {c.asnaf && (
          <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            <Tag tone="accent" p={p}>
              {c.asnaf}
            </Tag>
          </div>
        )}
      </div>

      {facts.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <GatedBlock label="Donor fit" p={p}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: 14,
              }}
            >
              {facts.map((f) => (
                <Fact key={f.label} label={f.label} value={f.value} p={p} />
              ))}
            </div>
          </GatedBlock>
        </div>
      )}

      {hasFitNotes && (
        <div style={{ marginBottom: 20 }}>
          <GatedBlock label="Ideal donor profile" p={p}>
            {c.bestForSummary && (
              <p style={{ fontSize: 15, color: p.fg, lineHeight: 1.5, margin: '0 0 14px', maxWidth: 760 }}>
                {c.bestForSummary}
              </p>
            )}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 14,
              }}
            >
              {c.idealFor.length > 0 && (
                <div style={{ border: `1px solid ${p.pos}`, borderRadius: 6, padding: 14, background: p.posBg }}>
                  <div style={{ fontSize: 12, color: p.pos, fontWeight: 600, marginBottom: 8 }}>
                    ✓ Ideal for donors who:
                  </div>
                  {c.idealFor.map((t) => (
                    <div
                      key={t}
                      style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '5px 0', fontSize: 12.5, color: p.fg, lineHeight: 1.5 }}
                    >
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
                    <div
                      key={t}
                      style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '5px 0', fontSize: 12.5, color: p.fg, lineHeight: 1.5 }}
                    >
                      <span style={{ color: p.caution }}>−</span>
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              )}
              {c.notIdealFor.length > 0 && (
                <div style={{ border: `1px solid ${p.neg}`, borderRadius: 6, padding: 14, background: p.negBg }}>
                  <div style={{ fontSize: 12, color: p.neg, fontWeight: 600, marginBottom: 8 }}>⊘ Not ideal for:</div>
                  {c.notIdealFor.map((t) => (
                    <div
                      key={t}
                      style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 8, padding: '5px 0', fontSize: 12.5, color: p.fg, lineHeight: 1.5 }}
                    >
                      <span style={{ color: p.neg }}>−</span>
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </GatedBlock>
        </div>
      )}

      {hasCaseAgainst && (
        <div style={{ marginBottom: 20 }}>
          <GatedBlock label="The case against" p={p}>
            {c.cited.caseAgainstSummary.length > 0 && (
              <div style={{ marginBottom: 12, maxWidth: '75ch' }}>
                <Kicker p={p}>The case against</Kicker>
                <div style={{ marginTop: 6 }}>
                  <CitedText segments={c.cited.caseAgainstSummary} p={p} size={13.5} />
                </div>
                <SourceList citations={collectCitations(c.cited.caseAgainstSummary)} p={p} />
              </div>
            )}
            <div style={{ display: 'grid', gap: 10, maxWidth: '75ch' }}>
              {c.caseAgainstFactors.length > 0 && (
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: p.sub, lineHeight: 1.6 }}>
                  {c.caseAgainstFactors.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              )}
              {c.caseAgainstMitigation && (
                <p style={{ fontSize: 12.5, color: p.sub, lineHeight: 1.6, margin: 0 }}>{c.caseAgainstMitigation}</p>
              )}
            </div>
          </GatedBlock>
        </div>
      )}

      <ConcernList concerns={c.concerns.byAnchor.zakat} p={p} />
    </Section>
  );
};

export default RightForYou;

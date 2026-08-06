// "What they do, and is it real?" — the cited narrative summary, the
// evaluator's evidence grade, theory of change, external evaluations, and the
// program/population/geography facts, plus any concerns anchored to what the
// org actually does.
//
// `evidence.theoryOfChange` (the evaluator's framing) and the root-level
// `theoryOfChange` (the charity's own words, present on a smaller share of
// the corpus) are different fields from different sources and are rendered
// separately rather than merged — they can disagree.

import React from 'react';
import { Section } from './Section';
import { ConcernList } from './ConcernList';
import { CitedText, SourceList, collectCitations } from '../CitedText';
import { Tag, Kicker } from '../primitives';
import { GmgPalette, FONT_DISPLAY, FONT_MONO } from '../tokens';
import { riskTone } from '../rating';
import type { GmgCharity } from '../charityAdapter';

const TagRow: React.FC<{ label: string; items: string[]; p: GmgPalette }> = ({ label, items, p }) => {
  if (items.length === 0) return null;
  return (
    <div>
      <Kicker p={p}>{label}</Kicker>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
        {items.map((item) => (
          <Tag key={item} p={p}>
            {item}
          </Tag>
        ))}
      </div>
    </div>
  );
};

export const WhatTheyDo: React.FC<{
  c: GmgCharity;
  p: GmgPalette;
  isMobile: boolean;
  padX: number;
}> = ({ c, p, isMobile, padX }) => {
  const sectionBorder = `1px solid ${p.rule}`;
  return (
  <Section id="what-they-do" title="What they do, and is it real?" p={p} padX={padX}>
    {/* About + Quick facts — the two-column opener from the original design.
        `c.headline` is a one-sentence editorial statement; the cited summary
        below is the fuller narrative. They are different content and both
        render, deliberately. */}
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1.6fr) minmax(0, 1fr)',
        gap: 20,
        marginBottom: 20,
        paddingBottom: 20,
        borderBottom: sectionBorder,
      }}
    >
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
            ['Category', c.category], ['Region', c.region],
            ['Programs', c.programs.join(', ')], ['Populations', c.populations.join(', ')],
            ['Founded', c.founded ? `${c.founded}${c.trackRecordYears ? ` · ${c.trackRecordYears} yrs` : ''}` : ''],
            ['Wallet', c.wallet], ['Asnaf', c.asnaf || (c.claimsZakat ? 'Claims zakat' : '')],
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
    </div>

    {c.cited.summary.length > 0 && (
      <div style={{ marginBottom: 16 }}>
        <CitedText segments={c.cited.summary} p={p} size={14} />
        <SourceList citations={collectCitations(c.cited.summary)} p={p} />
      </div>
    )}

    {c.evidence.grade && (
      <div style={{ marginBottom: 16 }}>
        <Tag tone="accent" p={p}>
          Evidence grade {c.evidence.grade}
        </Tag>
        {c.evidence.gradeExplanation && (
          <p style={{ fontSize: 12.5, color: p.sub, lineHeight: 1.55, margin: '8px 0 0' }}>
            {c.evidence.gradeExplanation}
          </p>
        )}
      </div>
    )}

    {c.evidence.theoryOfChange && (
      <div style={{ marginBottom: 16 }}>
        <Kicker p={p}>Theory of change</Kicker>
        <p style={{ fontSize: 13, color: p.sub, lineHeight: 1.6, margin: '6px 0 0' }}>{c.evidence.theoryOfChange}</p>
      </div>
    )}

    {c.theoryOfChange && (
      <div style={{ marginBottom: 16 }}>
        <Kicker p={p}>In the charity's own words</Kicker>
        <p style={{ fontSize: 13, color: p.sub, lineHeight: 1.6, margin: '6px 0 0' }}>{c.theoryOfChange}</p>
      </div>
    )}

    {c.evidence.externalEvaluations.length > 0 && (
      <div style={{ marginBottom: 16 }}>
        <Kicker p={p}>External evaluations</Kicker>
        <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12.5, color: p.sub, lineHeight: 1.6 }}>
          {c.evidence.externalEvaluations.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </div>
    )}

    {(c.programs.length > 0 || c.populations.length > 0 || c.geography.length > 0) && (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <TagRow label="Programs" items={c.programs} p={p} />
        <TagRow label="Populations served" items={c.populations} p={p} />
        <TagRow label="Geography" items={c.geography} p={p} />
      </div>
    )}

    <ConcernList concerns={c.concerns.byAnchor.whatTheyDo} p={p} />
  </Section>
  );
};

export default WhatTheyDo;

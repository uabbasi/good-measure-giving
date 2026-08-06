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
import { GmgPalette } from '../tokens';
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
}> = ({ c, p, isMobile, padX }) => (
  <Section id="what-they-do" title="What they do, and is it real?" p={p} padX={padX}>
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

export default WhatTheyDo;

// "What they do, and is it real?" — the cited narrative summary (shared
// narrative field, public) and the program/population/geography facts, plus
// any concerns anchored to what the org actually does, are public. The
// evaluator's own `impact_evidence` assessment — grade, theory-of-change
// status + summary, external evaluations — is rich-only and sits behind the
// community gate as one block.
//
// `evidence.theoryOfChange` is a status enum (DOCUMENTED/IMPLICIT/PUBLISHED/
// DEVELOPING/ABSENT/STRONG), not prose — it renders as a badge, never as the
// explanation itself. The actual prose comes from two different sources:
// `evidence.theoryOfChangeSummary` (the evaluator's gloss, gated with the
// rest of `impact_evidence`) and the root-level `theoryOfChange` (the
// charity's own longer-form words, sourced independently of the rich/
// baseline narrative split, so it stays public even when the evaluator's own
// assessment is gated). The two can disagree, so neither is merged into the
// other.

import React from 'react';
import { Section } from './Section';
import { ConcernList } from './ConcernList';
import { GatedBlock } from '../GatedBlock';
import { CitedText, SourceList, collectCitations } from '../CitedText';
import { Tag, Kicker } from '../primitives';
import { GmgPalette, FONT_DISPLAY, FONT_MONO } from '../tokens';
import { riskTone } from '../rating';
import { useIsMobile } from '../useIsMobile';
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
  // The 1.6fr/1fr split gets cramped well before the 768px mobile
  // breakpoint — the Quick facts column runs comma-joined lists (Programs,
  // Populations) in ~35% of the width. Collapse to one column earlier.
  const isNarrow = useIsMobile('(max-width: 1100px)');
  return (
  <Section id="what-they-do" title="What they do, and is it real?" p={p} padX={padX}>
    {/* About + Quick facts — the two-column opener from the original design.
        `c.headline` is a one-sentence editorial statement and the ONLY prose
        this block renders. `c.summary` is the same underlying narrative as
        the cited version below (adaptCharity builds `cited.summary` from
        that same field) — rendering both here would show the identical
        paragraph twice, once plain and once with citations. */}
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: isNarrow ? '1fr' : 'minmax(0, 1.6fr) minmax(0, 1fr)',
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

    {/* Running prose reads badly at full container width (~180 characters
        per line on a wide screen) — cap it to a readable measure. Tag
        grids and cards below this cluster are left alone; they're already
        column-constrained. */}
    <div style={{ maxWidth: '75ch' }}>
    {c.cited.summary.length > 0 && (
      <div style={{ marginBottom: 16 }}>
        <CitedText segments={c.cited.summary} p={p} size={14} />
        <SourceList citations={collectCitations(c.cited.summary)} p={p} />
      </div>
    )}

    {(c.evidence.grade || c.evidence.theoryOfChange || c.evidence.theoryOfChangeSummary
      || c.evidence.externalEvaluations.length > 0) && (
      <div style={{ marginBottom: 16 }}>
        <GatedBlock label="Impact evidence" p={p}>
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

          {(c.evidence.theoryOfChange || c.evidence.theoryOfChangeSummary) && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <Kicker p={p}>Theory of change</Kicker>
                {c.evidence.theoryOfChange && <Tag p={p}>{c.evidence.theoryOfChange}</Tag>}
              </div>
              {c.evidence.theoryOfChangeSummary && (
                <p style={{ fontSize: 13, color: p.sub, lineHeight: 1.6, margin: '8px 0 0' }}>
                  {c.evidence.theoryOfChangeSummary}
                </p>
              )}
            </div>
          )}

          {c.evidence.externalEvaluations.length > 0 && (
            <div>
              <Kicker p={p}>External evaluations</Kicker>
              <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12.5, color: p.sub, lineHeight: 1.6 }}>
                {c.evidence.externalEvaluations.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
        </GatedBlock>
      </div>
    )}

    {/* Root-level theoryOfChange — sourced independently of the rich/baseline
        narrative split (see file header), so it stays public even when the
        evaluator's own impact-evidence assessment above is gated. */}
    {c.theoryOfChange && (
      <p style={{ fontSize: 12.5, color: p.sub, lineHeight: 1.6, margin: '0 0 16px' }}>
        <span style={{ color: p.sub2, fontWeight: 500 }}>In the charity&rsquo;s own words: </span>
        {c.theoryOfChange}
      </p>
    )}
    </div>

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

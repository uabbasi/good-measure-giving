// Renders narrative prose that carries inline citations, plus the Sources block
// that goes beneath it. The adapter has already parsed the pipeline's
// <cite id="N"> markup into segments; this only draws them.

import React from 'react';
import type { Citation, CitedSegment } from './adapters/citations';
import { GmgPalette, FONT_MONO } from './tokens';

export const CitedText: React.FC<{
  segments: CitedSegment[];
  p: GmgPalette;
  size?: number;
}> = ({ segments, p, size = 13.5 }) => {
  if (segments.length === 0) return null;
  return (
    <span style={{ fontSize: size, lineHeight: 1.65, color: p.sub }}>
      {segments.map((seg, i) =>
        seg.kind === 'text' ? (
          <span key={i}>{seg.text}</span>
        ) : (
          <span key={i}>
            {seg.text}
            <sup
              aria-label={`Source ${seg.citation.n}: ${seg.citation.sourceName}`}
              style={{
                fontFamily: FONT_MONO,
                fontSize: size * 0.62,
                color: p.accent,
                // A marker directly against a digit (e.g. "1933⁶") reads as
                // an exponent rather than a citation — enough gap to read
                // as a separate mark, always, not just after digits.
                marginLeft: '0.2em',
                verticalAlign: 'super',
                lineHeight: 0,
              }}
            >
              {seg.citation.n}
            </sup>
          </span>
        ),
      )}
    </span>
  );
};

/** Deduplicated, number-ordered citations across any number of segment arrays. */
export const collectCitations = (...segmentArrays: CitedSegment[][]): Citation[] => {
  const byN = new Map<number, Citation>();
  for (const segs of segmentArrays) {
    for (const seg of segs) {
      if (seg.kind === 'cited' && !byN.has(seg.citation.n)) byN.set(seg.citation.n, seg.citation);
    }
  }
  return [...byN.values()].sort((a, b) => a.n - b.n);
};

export const SourceList: React.FC<{ citations: Citation[]; p: GmgPalette }> = ({ citations, p }) => {
  if (citations.length === 0) return null;
  return (
    <div style={{ marginTop: 14, paddingTop: 10, borderTop: `1px solid ${p.rule}` }}>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 9.5,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: p.sub2,
          marginBottom: 6,
        }}
      >
        Sources
      </div>
      <ol style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {citations.map((c) => (
          <li
            key={c.n}
            style={{ display: 'flex', gap: 8, fontSize: 11.5, color: p.sub2, padding: '3px 0' }}
          >
            <span style={{ fontFamily: FONT_MONO, color: p.accent, flexShrink: 0 }}>{c.n}.</span>
            {c.sourceUrl ? (
              <a
                href={c.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: p.sub, textDecoration: 'none', borderBottom: `1px solid ${p.rule2}` }}
              >
                {c.sourceName} ↗
              </a>
            ) : (
              <span>{c.sourceName}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
};

export default CitedText;

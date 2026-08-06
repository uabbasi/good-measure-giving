// Renders keyConcerns anchored to a section, colour-coded by severity with
// the same pos/caution/neg triad used for ratings and risk elsewhere on the
// page — a low-severity concern shouldn't read as alarming as a high one.
// Shared across sections rather than duplicated per-anchor.

import React from 'react';
import type { Concern, ConcernSeverity } from '../adapters/concerns';
import { GmgPalette, FONT_MONO } from '../tokens';

const TONE: Record<ConcernSeverity, { fg: keyof GmgPalette; bg: keyof GmgPalette }> = {
  high: { fg: 'neg', bg: 'negBg' },
  medium: { fg: 'caution', bg: 'cautionBg' },
  low: { fg: 'pos', bg: 'posBg' },
};

export const ConcernList: React.FC<{ concerns: Concern[]; p: GmgPalette }> = ({ concerns, p }) => {
  if (concerns.length === 0) return null;
  return (
    <div style={{ display: 'grid', gap: 8, marginTop: 14 }}>
      {concerns.map((concern, i) => {
        const tone = TONE[concern.severity];
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
              {concern.headline}
            </div>
            {concern.detail && (
              <div style={{ fontSize: 12, color: p.sub, marginTop: 4, lineHeight: 1.5 }}>{concern.detail}</div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default ConcernList;

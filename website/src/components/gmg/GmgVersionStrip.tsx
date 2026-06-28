// Good Measure Giving — site-wide "version strip".
// A thin, non-sticky editorial status bar that sits directly above GmgNav on
// every motif surface. Frames GMG as a continuously-updated, versioned index:
// the left cluster is auto-computed from the loaded charity data, the right
// cluster links to the changelog and the raw open data.

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { GmgPalette, FONT_MONO } from './tokens';
import { useCharities } from '../../hooks/useCharities';
import { RUBRIC_VERSION } from '../../config/siteVersion';
import { computeVersionStripStats } from './versionStripData';

const DOT = '·'; // ·

export const GmgVersionStrip: React.FC<{ p: GmgPalette; isMobile: boolean }> = ({ p, isMobile }) => {
  const { summaries } = useCharities();
  const stats = useMemo(() => computeVersionStripStats(summaries), [summaries]);

  // Counts/dates derive from the charity index. When it isn't loaded yet (SSR of
  // a route without the seeded index, or pre-hydration), show placeholders for
  // the data-derived values and let them hydrate; the static labels + links and
  // the rubric version (a constant) are always present in the static HTML.
  const hasData = summaries.length > 0;
  const ratedTxt = hasData ? String(stats.ratedCount) : '—';
  const zakatTxt = hasData ? String(stats.zakatCount) : '—';
  const releaseTxt = stats.release ?? '—';
  const updatedTxt = stats.updated ?? '—';

  // Mobile keeps only the essentials; desktop carries the full release line.
  const leftSegments = isMobile
    ? ['GMG INDEX', `${ratedTxt} rated`, `v${RUBRIC_VERSION}`]
    : [
        'GMG INDEX',
        `RELEASE ${releaseTxt}`,
        `${ratedTxt} rated`,
        `${zakatTxt} zakat-eligible`,
        `Rubric v${RUBRIC_VERSION}`,
        `updated ${updatedTxt}`,
      ];

  const linkStyle: React.CSSProperties = {
    color: p.sub,
    textDecoration: 'none',
    letterSpacing: '0.06em',
    whiteSpace: 'nowrap',
  };

  return (
    <div
      style={{
        background: p.bg2,
        borderBottom: `1px solid ${p.rule}`,
        color: p.sub2,
        fontFamily: FONT_MONO,
        fontSize: 10.5,
        letterSpacing: '0.06em',
        lineHeight: 1.2,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          padding: `5px ${isMobile ? 16 : 24}px`,
        }}
      >
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {leftSegments.join(` ${DOT} `)}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <Link to="/changelog" style={linkStyle}>
            CHANGELOG
          </Link>
          <span aria-hidden="true" style={{ color: p.rule2 }}>
            {DOT}
          </span>
          <a href="/data/charities.json" style={linkStyle}>
            OPEN DATA {'↓'}
          </a>
        </span>
      </div>
    </div>
  );
};

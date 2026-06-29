// Good Measure Giving — site-wide "version strip".
// A thin, non-sticky editorial masthead that sits directly above GmgNav on every
// motif surface. Frames GMG as a periodical: an issue/edition dateline + the
// scope of the index + the rubric version, with a single link to the changelog
// (the "back issues" record). Counts/dates are auto-computed from the loaded
// charity index.

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { GmgPalette, FONT_MONO } from './tokens';
import { useCharities } from '../../hooks/useCharities';
import { RUBRIC_VERSION } from '../../config/siteVersion';
import { computeVersionStripStats } from './versionStripData';

const DOT = '·';
const BAR = '|';

export const GmgVersionStrip: React.FC<{ p: GmgPalette; isMobile: boolean }> = ({ p, isMobile }) => {
  const { summaries } = useCharities();
  const stats = useMemo(() => computeVersionStripStats(summaries), [summaries]);

  // When the index isn't loaded yet (SSR of an unseeded route, or pre-hydration)
  // fall back to a minimal masthead; the full dateline hydrates client-side.
  const hasData = summaries.length > 0;
  const issueLabel = stats.issueNo != null ? `ISSUE ${String(stats.issueNo).padStart(2, '0')}` : null;
  const edition = stats.edition ? stats.edition.toUpperCase() : null;
  const hijri = stats.hijriYear != null ? `${stats.hijriYear} AH` : null;
  const dateline = [hijri, edition].filter(Boolean).join(' / '); // "1447 AH / JUNE 2026"

  // Grouped like a masthead: edition · scope · version, separated by faint bars.
  const editionGroup = [issueLabel, dateline || null].filter(Boolean).join(` ${DOT} `);
  const scopeGroup = hasData
    ? `${stats.ratedCount} CHARITIES ${DOT} IMPACT + ALIGNMENT`
    : 'IMPACT + ALIGNMENT';
  const versionGroup =
    hasData && stats.updated
      ? `RUBRIC v${RUBRIC_VERSION} ${DOT} UPDATED ${stats.updated}`
      : `RUBRIC v${RUBRIC_VERSION}`;

  const desktopGroups = [editionGroup, scopeGroup, versionGroup].filter(Boolean);
  const mobileLine = [issueLabel ?? 'GOOD MEASURE GIVING', edition, hasData ? `${stats.ratedCount} CHARITIES` : null]
    .filter(Boolean)
    .join(` ${DOT} `);

  const linkStyle: React.CSSProperties = {
    color: p.sub,
    textDecoration: 'none',
    letterSpacing: '0.1em',
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
        letterSpacing: '0.08em',
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
          {isMobile
            ? mobileLine
            : desktopGroups.map((g, i) => (
                <React.Fragment key={g}>
                  {i > 0 && <span style={{ margin: '0 12px', color: p.rule2 }}>{BAR}</span>}
                  {g}
                </React.Fragment>
              ))}
        </span>
        <Link to="/changelog" style={linkStyle}>
          BACK ISSUES
        </Link>
      </div>
    </div>
  );
};

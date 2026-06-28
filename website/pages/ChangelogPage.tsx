// Good Measure Giving — "Modern" motif Changelog (/changelog).
// A simple, credible, reverse-chronological log of what changed on the index.
// SEO/trust asset: every entry is real. To add one, prepend to CHANGELOG below.

import React from 'react';
import { Link } from 'react-router-dom';
import {
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEMES,
  resolveFontVariant,
  type FontVariant,
} from '../src/components/gmg/tokens';
import { GmgNav } from '../src/components/gmg/chrome';
import { useIsMobile } from '../src/components/gmg/useIsMobile';

interface ChangelogEntry {
  date: string; // YYYY-MM or YYYY-MM-DD
  summary: string;
}

// Reverse-chronological. Newest first. Keep entries factual and human-readable.
const CHANGELOG: ChangelogEntry[] = [
  {
    date: '2026-06-28',
    summary:
      'Published 7 new zakat and charity-evaluation guides. Launched "Link to Us" with an embeddable trust badge. Rolled out the new Modern design site-wide.',
  },
  {
    date: '2026-06-27',
    summary:
      'Added the "Best Muslim Charities in the USA" ranked hub. Corrected Muslim-organization classification — now 124 rated organizations.',
  },
  {
    date: '2026-06-22',
    summary:
      'Build-time server-side rendering for every page, fixing how search engines index the site.',
  },
  {
    date: '2026-06',
    summary:
      'Added a gold & silver zakat chart to the calculator. Hardened the methodology with a citable scoring formula (Rubric v5.2.0).',
  },
];

const formatDate = (raw: string): string => {
  // 'YYYY-MM-DD' -> 'June 28, 2026'; 'YYYY-MM' -> 'June 2026'.
  const parts = raw.split('-').map(Number);
  const [y, m, d] = parts;
  const month = new Date(Date.UTC(y, (m ?? 1) - 1, 1)).toLocaleString('en-US', {
    month: 'long',
    timeZone: 'UTC',
  });
  return d ? `${month} ${d}, ${y}` : `${month} ${y}`;
};

export const ChangelogPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const padX = isMobile ? 20 : 24;

  React.useEffect(() => {
    document.title = 'Changelog — Good Measure Giving';
    return () => {
      document.title = 'Good Measure Giving | Muslim Charity Evaluator';
    };
  }, []);

  const variant: FontVariant = resolveFontVariant(
    typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('type') : null,
  );
  const ft = FONT_THEMES[variant];
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  };

  return (
    <div style={{ background: p.bg, color: p.fg, fontFamily: FONT_TEXT, minHeight: '100vh', ...fontVars }}>
      <GmgNav p={p} isMobile={isMobile} />

      <section style={{ maxWidth: 760, margin: '0 auto', padding: isMobile ? `48px ${padX}px 72px` : `72px ${padX}px 96px` }}>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 11,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            color: p.accent2,
            marginBottom: 18,
          }}
        >
          Changelog
        </div>
        <h1
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 400,
            fontSize: isMobile ? 38 : 52,
            lineHeight: 1.05,
            letterSpacing: ft.displayTracking,
            margin: 0,
          }}
        >
          What's <em style={{ color: p.accent }}>changed.</em>
        </h1>
        <p style={{ fontSize: isMobile ? 16 : 18, lineHeight: 1.6, color: p.sub, margin: '20px 0 0', maxWidth: 600 }}>
          Good Measure Giving is a continuously-updated index. Scores, data, and the site itself improve
          as filings, methodology, and coverage evolve. Here's the running record of the bigger changes.
        </p>

        <ol style={{ listStyle: 'none', margin: '44px 0 0', padding: 0 }}>
          {CHANGELOG.map((entry) => (
            <li
              key={entry.date}
              style={{
                display: 'flex',
                gap: isMobile ? 12 : 28,
                flexDirection: isMobile ? 'column' : 'row',
                padding: '20px 0',
                borderTop: `1px solid ${p.rule}`,
              }}
            >
              <time
                dateTime={entry.date}
                style={{
                  fontFamily: FONT_MONO,
                  fontSize: 12,
                  letterSpacing: '0.04em',
                  color: p.sub2,
                  flexShrink: 0,
                  minWidth: isMobile ? undefined : 150,
                  paddingTop: 2,
                }}
              >
                {formatDate(entry.date)}
              </time>
              <p style={{ margin: 0, fontSize: isMobile ? 15 : 16, lineHeight: 1.6, color: p.fg }}>
                {entry.summary}
              </p>
            </li>
          ))}
        </ol>

        <div style={{ marginTop: 48, fontSize: 14, color: p.sub }}>
          <Link to="/methodology" style={{ color: p.accent, textDecoration: 'none' }}>
            Read the methodology →
          </Link>
        </div>
      </section>
    </div>
  );
};

export default ChangelogPage;

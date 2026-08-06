// "Can you trust these numbers?" — entirely public. Hiding a charity's
// problems or the sourcing of its figures behind a sign-in is the wrong
// trade, and this is the most SEO-valuable content on the page. No
// GatedBlock appears anywhere in this section.
//
// Concerns here are `byAnchor.trust` only — data-quality caveats with no
// other home (7 of 343 fleet-wide) — not the full `concerns.all`. Every
// other caveat already renders beside the figure it qualifies (that's what
// the Phase 1 anchoring work is for); repeating the full list here would
// duplicate ~98% of concerns fleet-wide and read as the same warning
// appearing twice. A one-line pointer below the trust concerns (rendered
// only when other caveats exist) tells the reader they're elsewhere on the
// page without restating them.

import React from 'react';
import { Section } from './Section';
import { ConcernList } from './ConcernList';
import { Tag, Kicker } from '../primitives';
import { GmgPalette, FONT_MONO } from '../tokens';
import type { GmgCharity } from '../charityAdapter';
import { dataVintage } from './dataVintage';

const fieldLabel = (field: string): string =>
  field.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

const AWARD_LINKS: { key: 'cn' | 'candid' | 'bbb'; urlKey: 'cnUrl' | 'candidUrl' | 'bbbUrl'; name: string }[] = [
  { key: 'cn', urlKey: 'cnUrl', name: 'Charity Navigator' },
  { key: 'candid', urlKey: 'candidUrl', name: 'Candid' },
  { key: 'bbb', urlKey: 'bbbUrl', name: 'BBB Wise Giving Alliance' },
];

export const TrustTheNumbers: React.FC<{
  c: GmgCharity;
  p: GmgPalette;
  isMobile: boolean;
  padX: number;
}> = ({ c, p, isMobile, padX }) => {
  const { fyAge, fyDated } = dataVintage(c);
  const sourceNames = new Set(c.citations.ordered.map((ci) => ci.sourceName).filter(Boolean));
  const trustConcerns = c.concerns.byAnchor.trust;
  const otherConcernsCount = c.concerns.all.length - trustConcerns.length;

  return (
    <Section id="trust" title="Can you trust these numbers?" p={p} padX={padX}>
      <div style={{ marginBottom: 20 }}>
        <Kicker p={p}>Data vintage</Kicker>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <Tag tone={fyDated ? 'caution' : 'muted'} p={p}>
            {c.fiscalYear ? `FY${c.fiscalYear} · IRS 990` : 'IRS 990'}
            {fyDated ? ' · Dated data' : ''}
          </Tag>
        </div>
        {fyDated && (
          <p style={{ fontSize: 12, color: p.sub2, marginTop: 6, lineHeight: 1.5 }}>
            {c.form990Exempt
              ? 'Not required to file — exempt from IRS 990.'
              : `${fyAge} years since last filed 990.`}
          </p>
        )}
      </div>

      {c.citations.ordered.length > 0 && (
        <div style={{ marginBottom: 20, fontSize: 12.5, color: p.sub }}>
          <strong style={{ color: p.fg }}>{c.citations.ordered.length}</strong> sourced claims from{' '}
          <strong style={{ color: p.fg }}>{sourceNames.size}</strong> sources
        </div>
      )}

      <ConcernList concerns={trustConcerns} p={p} />
      {otherConcernsCount > 0 && (
        <p style={{ fontSize: 12, color: p.sub2, marginTop: 10, lineHeight: 1.5 }}>
          {otherConcernsCount} further {otherConcernsCount === 1 ? 'caveat appears' : 'caveats appear'} beside
          the specific figures they affect, elsewhere on this page.
        </p>
      )}

      {c.provenance.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Kicker p={p}>Where each figure comes from</Kicker>
          <div style={{ display: 'grid', gap: isMobile ? 10 : 6, marginTop: 8 }}>
            {!isMobile && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.1fr 1.3fr 0.5fr',
                  gap: 8,
                  fontSize: 10,
                  fontFamily: FONT_MONO,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  color: p.sub2,
                  paddingBottom: 4,
                  borderBottom: `1px solid ${p.rule}`,
                }}
              >
                <span>Field</span>
                <span>Source</span>
                <span>Fiscal year</span>
              </div>
            )}
            {c.provenance.map((row, i) =>
              isMobile ? (
                <div
                  key={`${row.field}-${i}`}
                  style={{ border: `1px solid ${p.rule}`, borderRadius: 6, padding: '8px 10px', fontSize: 12 }}
                >
                  <div style={{ color: p.fg, fontWeight: 600 }}>{fieldLabel(row.field)}</div>
                  <div style={{ color: p.sub, marginTop: 2 }}>
                    {row.sourceUrl ? (
                      <a
                        href={row.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: p.sub, borderBottom: `1px solid ${p.rule2}` }}
                      >
                        {row.sourceName} ↗
                      </a>
                    ) : (
                      row.sourceName
                    )}
                  </div>
                  {row.fiscalYear != null && (
                    <div style={{ color: p.sub2, fontSize: 11, marginTop: 2 }}>FY{row.fiscalYear}</div>
                  )}
                </div>
              ) : (
                <div
                  key={`${row.field}-${i}`}
                  style={{ display: 'grid', gridTemplateColumns: '1.1fr 1.3fr 0.5fr', gap: 8, fontSize: 12 }}
                >
                  <span style={{ color: p.fg }}>{fieldLabel(row.field)}</span>
                  <span style={{ color: p.sub }}>
                    {row.sourceUrl ? (
                      <a
                        href={row.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: p.sub, borderBottom: `1px solid ${p.rule2}` }}
                      >
                        {row.sourceName} ↗
                      </a>
                    ) : (
                      row.sourceName
                    )}
                  </span>
                  <span style={{ color: p.sub2, fontFamily: FONT_MONO }}>
                    {row.fiscalYear != null ? `FY${row.fiscalYear}` : '—'}
                  </span>
                </div>
              ),
            )}
          </div>
        </div>
      )}

      {c.bbb.summary && (
        <div style={{ marginTop: 20 }}>
          <Kicker p={p}>BBB Wise Giving Alliance</Kicker>
          <p style={{ fontSize: 12.5, color: p.sub, lineHeight: 1.6, margin: '6px 0 10px' }}>{c.bbb.summary}</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {c.bbb.effectivenessStatus && <Tag p={p}>Effectiveness: {c.bbb.effectivenessStatus}</Tag>}
            {c.bbb.financesStatus && <Tag p={p}>Finances: {c.bbb.financesStatus}</Tag>}
            {c.bbb.governanceStatus && <Tag p={p}>Governance: {c.bbb.governanceStatus}</Tag>}
            {c.bbb.standardsMet != null && <Tag p={p}>{c.bbb.standardsMet} standards met</Tag>}
          </div>
          {c.bbb.reviewUrl && (
            <a
              href={c.bbb.reviewUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: 'inline-block', marginTop: 8, fontSize: 12, color: p.sub, borderBottom: `1px solid ${p.rule2}` }}
            >
              Read the BBB review ↗
            </a>
          )}
        </div>
      )}

      {AWARD_LINKS.some((a) => c.awards[a.urlKey]) && (
        <div style={{ marginTop: 20 }}>
          <Kicker p={p}>Verification badges</Kicker>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 8 }}>
            {AWARD_LINKS.filter((a) => c.awards[a.urlKey]).map((a) => (
              <a
                key={a.key}
                href={c.awards[a.urlKey] as string}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 12, color: p.sub, borderBottom: `1px solid ${p.rule2}` }}
              >
                {c.awards[a.key] ? `${a.name}: ${c.awards[a.key]}` : a.name} ↗
              </a>
            ))}
          </div>
        </div>
      )}
    </Section>
  );
};

export default TrustTheNumbers;

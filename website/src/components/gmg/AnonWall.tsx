// The anonymous wall. A signed-out visitor gets the identity header, this
// one panel, and the similar-charities block — nothing else. It replaces
// eleven scattered "Sign in to see this" boxes (one per gated sub-block,
// see GatedBlock) with a single deliberate panel between the header and
// the similar-charities block.
//
// Every count and every named area below is computed from THIS charity's
// own data, using the same content-presence checks each of the six
// sections already applies to decide whether its own GatedBlock has
// anything to show. A charity with zero concerns, no grants, or a single
// year of financials simply omits that line — nothing here is hardcoded
// copy, and nothing overclaims what signing in actually unlocks.

import React from 'react';
import { SignInButton } from '../../auth/SignInButton';
import { GmgPalette, FONT_DISPLAY, FONT_MONO } from './tokens';
import { Kicker } from './primitives';
import type { GmgCharity } from './charityAdapter';

// Named analysis blocks, listed only when this charity has content for
// them. Each condition mirrors the presence guard the corresponding
// section/GatedBlock already uses (WhatTheyDo's impact-evidence gate,
// WhereMoneyGoes' trend/recipients gates, RunWell's capacity gate,
// RightForYou's donor-fit/ideal-donor/case-against gates, HowItCompares'
// peer/outlook/strengths gates, TrustTheNumbers' BBB gate) so the wall can
// never promise an area that the gated page wouldn't actually show once
// unlocked.
export const computeAnalysisAreas = (c: GmgCharity): string[] => {
  const areas: string[] = [];

  if (
    c.evidence.grade
    || c.evidence.theoryOfChange
    || c.evidence.theoryOfChangeSummary
    || c.evidence.externalEvaluations.length > 0
  ) {
    areas.push('Impact evidence');
  }

  if (c.financialSeries.length >= 2) areas.push('Multi-year financial trend');
  if (c.grantFlows && c.grantFlows.topRecipients.length > 0) areas.push('Named grant recipients');

  const cap = c.capacity;
  const hasCapacity =
    !!cap.ceoName
    || cap.boardSize != null
    || cap.independentBoardPct != null
    || cap.hasConflictPolicy != null
    || cap.hasFinancialAudit != null
    || cap.employeesCount != null
    || cap.volunteersCount != null
    || cap.programsCount != null
    || !!cap.geographicReach
    || cap.ceoCompensation != null
    || cap.ceoCompensationPctRevenue != null;
  if (hasCapacity) areas.push('Organizational capacity');

  const dfm = c.donorFitMatrix;
  const hasDonorFit =
    !!dfm.causeArea
    || !!dfm.givingStyle
    || !!dfm.evidenceRigor
    || !!dfm.geographicFocus
    || !!dfm.zakatStatus
    || dfm.zakatAsnafServed.length > 0;
  if (hasDonorFit) areas.push('Donor fit');

  const hasFitNotes =
    !!c.bestForSummary || c.idealFor.length > 0 || c.considerations.length > 0 || c.notIdealFor.length > 0;
  if (hasFitNotes) areas.push('Ideal donor profile');

  const hasCaseAgainst =
    c.cited.caseAgainstSummary.length > 0 || c.caseAgainstFactors.length > 0 || !!c.caseAgainstMitigation;
  if (hasCaseAgainst) areas.push('The case against');

  const peers = c.peers;
  const hasPeerComparison =
    !!peers.peerGroup
    || c.cited.peerDifferentiator.length > 0
    || peers.programRatioMedian != null
    || peers.industryProgramRatio != null
    || peers.cnOverallScore != null
    || peers.transparencyScore != null
    || peers.peerCount != null
    || peers.similarOrganizations.length > 0;
  if (hasPeerComparison) areas.push('Peer comparison');

  const hasOutlook =
    !!c.outlook.maturityStage || !!c.outlook.roomForFunding || c.outlook.strategicPriorities.length > 0;
  if (hasOutlook) areas.push('Long-term outlook');

  if (c.cited.strengthsDeepDive.length > 0) areas.push('Strengths in depth');
  if (c.bbb.summary) areas.push('BBB Wise Giving Alliance assessment');

  return areas;
};

// The wall's bullet list. Each line is guarded independently and omitted
// when its count is zero, rather than showing a fabricated "0 concerns".
export const computeWallItems = (c: GmgCharity): string[] => {
  const items: string[] = [];

  const concernCount = c.concerns.all.length;
  if (concernCount > 0) {
    items.push(`${concernCount} identified ${concernCount === 1 ? 'concern' : 'concerns'}`);
  }

  const citationCount = c.citations.ordered.length;
  if (citationCount > 0) {
    const sourceCount = new Set(c.citations.ordered.map((ci) => ci.sourceName).filter(Boolean)).size;
    items.push(
      `${citationCount} cited ${citationCount === 1 ? 'claim' : 'claims'} from ${sourceCount} ${sourceCount === 1 ? 'source' : 'sources'}`,
    );
  }

  const yearCount = c.financialSeries.length;
  if (yearCount > 0) {
    items.push(`${yearCount} ${yearCount === 1 ? 'year' : 'years'} of financial history`);
  }

  if (c.grantFlows) {
    items.push(`Grant flow analysis across ${c.grantFlows.grantCount} grants`);
  }

  const areas = computeAnalysisAreas(c);
  if (areas.length > 0) items.push(`In-depth analysis: ${areas.join(', ')}`);

  return items;
};

export const AnonWall: React.FC<{ c: GmgCharity; p: GmgPalette; padX: number }> = ({ c, p, padX }) => {
  const items = computeWallItems(c);

  return (
    <section style={{ padding: `28px ${padX}px 32px`, borderBottom: `1px solid ${p.rule}`, background: p.bg2 }}>
      <div style={{ maxWidth: 620 }}>
        <Kicker p={p}>Full evaluation</Kicker>
        <h2
          style={{
            fontFamily: FONT_DISPLAY,
            fontSize: 26,
            lineHeight: 1.2,
            margin: '8px 0 10px',
            letterSpacing: '-0.02em',
            color: p.fg,
          }}
        >
          The full evaluation of {c.name} is free — sign in to see it.
        </h2>
        <p style={{ fontSize: 13.5, color: p.sub, lineHeight: 1.55, margin: '0 0 16px' }}>
          Good Measure Giving members see the complete, cited analysis behind every charity. Here&rsquo;s what&rsquo;s
          behind the sign-in for this one:
        </p>

        {items.length > 0 && (
          <ul style={{ margin: '0 0 20px', padding: 0, listStyle: 'none', display: 'grid', gap: 8 }}>
            {items.map((item) => (
              <li key={item} style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 10, fontSize: 13, color: p.fg, lineHeight: 1.5 }}>
                <span style={{ color: p.accent }}>✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}

        <SignInButton variant="button" />

        <p style={{ fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: '0.06em', textTransform: 'uppercase', color: p.sub2, marginTop: 10 }}>
          Free · No credit card · Takes 10 seconds
        </p>
      </div>
    </section>
  );
};

export default AnonWall;

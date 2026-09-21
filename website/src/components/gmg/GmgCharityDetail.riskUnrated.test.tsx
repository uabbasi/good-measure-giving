/**
 * The two places a donor reads the risk level: the hero stat strip and
 * Quick Facts.
 *
 * A charity with no Form 990 has nothing for the risk checks to run against,
 * and the empty result used to print as a green "LOW / overall" in both —
 * the reading a reader queried on the Islamic Society of Greater Houston.
 * Unrated has to look unrated, and say why: "overall" under an UNRATED
 * figure would still imply a verdict we don't have.
 */

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GmgCharityDetail from './GmgCharityDetail';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: [], loading: false, charities: [] }),
}));

const emptyRegister = { risks: [], overall_risk_level: 'LOW', risk_summary: '', total_deduction: 0 };

const unassessable = {
  ein: '23-7065716',
  name: 'Islamic Society of Greater Houston',
  lastUpdated: '2026-08-02',
  noFilings: true,
  financials: { totalRevenue: null, programExpenseRatio: null, workingCapitalMonths: null },
  amalEvaluation: { amal_score: 58, score_details: { risks: emptyRegister } },
};

const audited = {
  ...unassessable,
  ein: '12-3456789',
  name: 'Audited Charity',
  noFilings: false,
  financials: { fiscalYear: 2024, totalRevenue: 5_000_000, programExpenseRatio: 0.88 },
};

const textOf = (charity: unknown): string => {
  const { container } = render(
    <MemoryRouter>
      <GmgCharityDetail charity={charity} isDark={false} />
    </MemoryRouter>,
  );
  return container.textContent ?? '';
};

describe('GmgCharityDetail risk cell', () => {
  it('reads UNRATED, not LOW, when nothing was checkable', () => {
    const text = textOf(unassessable);

    expect(text).toContain('UNRATED');
    expect(text).not.toContain('LOW');
  });

  it('says why, rather than labelling the absence "overall"', () => {
    expect(textOf(unassessable)).toContain('insufficient data');
  });

  it('spells the reason out in Quick facts, which has no sub-label', () => {
    expect(textOf(unassessable)).toContain('UNRATED · INSUFFICIENT DATA');
  });

  it('still reports LOW for a charity whose checks ran clean', () => {
    const text = textOf(audited);

    expect(text).toContain('LOW');
    expect(text).not.toContain('UNRATED');
  });
});

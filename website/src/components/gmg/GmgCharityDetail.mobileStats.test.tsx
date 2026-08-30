/**
 * GmgCharityDetail — the stat strip on a phone.
 *
 * The strip fits three cells across at 393px, and the first of them is
 * cost-per-beneficiary, which is also the figure most often missing: for
 * those charities the strip opened with "— / not reported", spending a third
 * of the first screen on the absence of a number.
 *
 * Desktop keeps the full set on purpose. There the strip is one row with room
 * to spare, and a blank cell reads as "we looked and it isn't filed" rather
 * than as clutter. The rule under test is the difference, not the filtering.
 */

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GmgCharityDetail from './GmgCharityDetail';

let mobile = false;

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => mobile }));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: [], loading: false, charities: [] }),
}));

// No beneficiary count and no reserves — two of the six cells have nothing to
// say. Revenue and the program ratio do.
const charity = {
  ein: '12-3456789',
  name: 'Test Charity',
  lastUpdated: '2026-08-02',
  financials: { fiscalYear: 2024, totalRevenue: 1_000_000, programExpenseRatio: 0.88 },
  amalEvaluation: { amal_score: 60, score_details: { data_confidence: { data_age_years: 1 } } },
};

const renderAt = (isMobile: boolean): string => {
  mobile = isMobile;
  const { container } = render(
    <MemoryRouter>
      <GmgCharityDetail charity={charity} isDark={false} />
    </MemoryRouter>,
  );
  return container.textContent ?? '';
};

describe('GmgCharityDetail stat strip', () => {
  it('drops cells with no figure on a phone', () => {
    const text = renderAt(true);

    expect(text).not.toContain('Cost / benef.');
    expect(text).not.toContain('not reported');
  });

  it('keeps every cell with a figure on a phone', () => {
    const text = renderAt(true);

    expect(text).toContain('Program ratio');
    expect(text).toContain('88%');
    expect(text).toContain('Revenue');
  });

  it('keeps the full set on desktop, blanks included', () => {
    const text = renderAt(false);

    expect(text).toContain('Cost / benef.');
    expect(text).toContain('not reported');
  });
});

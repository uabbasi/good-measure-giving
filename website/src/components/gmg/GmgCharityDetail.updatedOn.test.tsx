/**
 * GmgCharityDetail — utility row date
 *
 * `amalEvaluation.evaluation_date` is stamped once, at scoring time, and goes
 * stale whenever the pipeline re-exports a charity without re-running the
 * rubric (true fleet-wide as of 2026-08: 166/166 charities have a
 * `lastUpdated` newer than `evaluation_date`). The utility row must show
 * `lastUpdated`, not the stale scoring date.
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GmgCharityDetail from './GmgCharityDetail';

vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: [], loading: false, charities: [] }),
}));

const charity = {
  ein: '12-3456789',
  name: 'Test Charity',
  lastUpdated: '2026-08-02 11:30:57',
  financials: { fiscalYear: 2024, totalRevenue: 1000000 },
  amalEvaluation: {
    amal_score: 60,
    evaluation_date: '2026-01-25 20:33:19',
    score_details: { data_confidence: { data_age_years: 1 } },
  },
};

describe('GmgCharityDetail — utility row date', () => {
  it('shows the lastUpdated date, not the stale evaluation_date', () => {
    render(
      <MemoryRouter>
        <GmgCharityDetail charity={charity} isDark={false} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/UPDATED 2026-08-02/)).toBeInTheDocument();
    expect(screen.queryByText(/2026-01-25/)).not.toBeInTheDocument();
    expect(screen.queryByText(/EVALUATED/)).not.toBeInTheDocument();
  });
});

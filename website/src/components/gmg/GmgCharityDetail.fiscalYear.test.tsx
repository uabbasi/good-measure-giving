/**
 * GmgCharityDetail — fiscal-year / data-vintage badge
 *
 * The badge must use the pipeline-published `data_age_years` (stable at
 * prerender + hydration) instead of recomputing age from the wall clock,
 * which would flip ~124 FY2024 charities against a stale SSR the moment the
 * calendar rolls onto the next "age >= 3" year with no pipeline run behind
 * it. Form-990-exempt orgs (churches/mosques the scorer already exempts
 * from filing-currency penalties) get exempt context alongside the badge,
 * not suppression of it.
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GmgCharityDetail from './GmgCharityDetail';

// Suppress sub-components with their own context/auth deps and the real
// charities-index fetch, matching the pattern in GmgCharityDetail.similar.test.tsx.
vi.mock('./chrome', () => ({ GmgNav: () => null }));
vi.mock('./content', () => ({ GmgFooter: () => null }));
vi.mock('./useIsMobile', () => ({ useIsMobile: () => false }));
vi.mock('../../hooks/useCharities', () => ({
  useCharities: () => ({ summaries: [], loading: false, charities: [] }),
}));

const base = {
  ein: '12-3456789',
  name: 'Test Charity',
  financials: { fiscalYear: 2024, totalRevenue: 1000000 },
  amalEvaluation: { amal_score: 60, score_details: { data_confidence: { data_age_years: 1 } } },
};

const renderDetail = (charity: any) =>
  render(
    <MemoryRouter>
      <GmgCharityDetail charity={charity} isDark={false} />
    </MemoryRouter>,
  );

describe('GmgCharityDetail — fiscal year badge', () => {
  it('uses the published data_age_years, not the wall clock', () => {
    renderDetail({
      ...base,
      amalEvaluation: { ...base.amalEvaluation, score_details: { data_confidence: { data_age_years: 5 } } },
    });
    expect(screen.getByText(/DATED DATA/i)).toBeInTheDocument();
  });

  it('shows the source attribution when the data is current', () => {
    renderDetail(base);
    expect(screen.queryByText(/DATED DATA/i)).not.toBeInTheDocument();
    expect(screen.getByText(/IRS 990/i)).toBeInTheDocument();
  });

  it('renders nothing age-related when fiscalYear is null', () => {
    renderDetail({
      ...base,
      financials: { fiscalYear: null },
      amalEvaluation: { ...base.amalEvaluation, score_details: { data_confidence: { data_age_years: null } } },
    });
    expect(screen.queryByText(/DATED DATA/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/years old/i)).not.toBeInTheDocument();
  });

  it('keeps the badge but adds exempt context for a form-990-exempt org', () => {
    renderDetail({
      ...base,
      form990Exempt: 1,
      financials: { fiscalYear: 2022 },
      amalEvaluation: { ...base.amalEvaluation, score_details: { data_confidence: { data_age_years: 4 } } },
    });
    expect(screen.getByText(/DATED DATA/i)).toBeInTheDocument();
    expect(screen.getByText(/not required to file/i)).toBeInTheDocument();
  });
});

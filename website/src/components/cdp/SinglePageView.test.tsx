import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SinglePageView } from './SinglePageView';

vi.mock('../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));
vi.mock('../../hooks/useCharities', () => ({ useCharities: () => ({ charities: [] }) }));
vi.mock('../../hooks/useGivingHistory', () => ({ useGivingHistory: () => ({ addDonation: vi.fn(), getPaymentSources: () => [] }) }));

// The slim header lifts a handful of interactive children that depend on auth,
// firebase, analytics and user-feature contexts. Stub them so the composition
// renders in isolation.
vi.mock('../../auth/SignInButton', () => ({ SignInButton: ({ children }: { children?: React.ReactNode }) => <>{children}</> }));
vi.mock('../BookmarkButton', () => ({ BookmarkButton: () => <button type="button">Save</button> }));
vi.mock('../CompareButton', () => ({ CompareButton: () => <button type="button">Compare</button> }));
vi.mock('../ShareButton', () => ({ ShareButton: () => <button type="button">Share</button> }));
vi.mock('../ReportIssueButton', () => ({ ReportIssueButton: () => <button type="button">Report issue</button> }));
vi.mock('../OrganizationEngagement', () => ({ OrganizationEngagement: () => null }));
vi.mock('../giving/AddDonationModal', () => ({ AddDonationModal: () => null }));

const charity = {
  name: 'Verdict Org',
  category: 'relief',
  rawData: {},
  amalEvaluation: {
    charity_ein: '1',
    charity_name: 'Verdict Org',
    amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE',
    evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    baseline_narrative: {
      summary: 's',
      headline: 'h',
      strengths: [],
      areas_for_improvement: [],
      amal_score_rationale: 'r',
    },
  },
} as any;

describe('SinglePageView', () => {
  it('renders the verdict score and charity name, with no tab buttons', () => {
    render(
      <MemoryRouter>
        <SinglePageView charity={charity} canViewRich />
      </MemoryRouter>
    );
    expect(screen.getByText('Verdict Org')).toBeTruthy();
    // The score 82 appears in both VerdictHero and the MobileScoreBar.
    expect(screen.getAllByText('82').length).toBeGreaterThan(0);
    expect(screen.queryByRole('tab')).toBeNull();
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TrustAwardsSection } from './TrustAwardsSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'T', category: 'relief', ein: '1', rawData: {},
  awards: {
    cnBeacons: ['4-Star Rating'],
    cnUrl: 'https://charitynavigator.org/test',
    candidSeal: 'platinum',
    bbbStatus: 'Meets Standards',
    bbbReviewUrl: 'https://give.org/test',
  },
  amalEvaluation: {
    charity_ein: '1', charity_name: 'T', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    rich_narrative: {
      bbb_assessment: {
        meets_all_standards: true,
        standards_met: 20,
        governance_status: 'pass',
        effectiveness_status: 'pass',
        finances_status: 'pass',
        audit_type: 'Independent Audit',
        summary: 'This organization meets all BBB standards for charity accountability.',
        standards_not_met: [],
        review_url: 'https://give.org/test',
      },
      all_citations: [],
    },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
} as any;

describe('TrustAwardsSection', () => {
  it('renders #trust-awards anchor for a rich charity with awards + bbb data', () => {
    const { container } = render(<TrustAwardsSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#trust-awards')).toBeTruthy();
  });

  it('renders awards block content when rich (CN beacon)', () => {
    render(<TrustAwardsSection data={buildCdpData(charity, true)} />);
    expect(screen.getByText('4-Star Rating')).toBeTruthy();
  });

  it('renders the BBB assessment summary when rich', () => {
    render(<TrustAwardsSection data={buildCdpData(charity, true)} />);
    expect(screen.getByText(/meets all BBB standards/i)).toBeTruthy();
  });

  it('shows ContentPreview gates and hides rich detail when anonymous', () => {
    const { container } = render(<TrustAwardsSection data={buildCdpData(charity, false)} />);
    expect(container.querySelector('#trust-awards')).toBeTruthy();
    expect(screen.getByText('Recognition & Awards')).toBeTruthy();
    expect(screen.getByText('BBB Assessment')).toBeTruthy();
    expect(screen.queryByText('4-Star Rating')).toBeNull();
    expect(screen.queryByText(/meets all BBB standards/i)).toBeNull();
  });
});

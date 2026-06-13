import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WhyThisScoreSection } from './WhyThisScoreSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const baseCharity = {
  name: 'Test Org', category: 'relief', ein: '12-3456789', rawData: {},
  amalEvaluation: {
    charity_ein: '12-3456789', charity_name: 'Test Org', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
    rich_narrative: { impact_evidence: { evidence_grade: 'A' }, all_citations: [] },
  },
} as any;

describe('WhyThisScoreSection', () => {
  it('renders #why-this-score anchor for a scored charity', () => {
    const { container } = render(<WhyThisScoreSection data={buildCdpData(baseCharity, true)} />);
    expect(container.querySelector('#why-this-score')).toBeTruthy();
  });

  it('renders the NEW_ORG non-numeric message instead of the score breakdown', () => {
    const newOrg = { ...baseCharity, evaluationTrack: 'NEW_ORG' } as any;
    render(<WhyThisScoreSection data={buildCdpData(newOrg, true)} />);
    expect(screen.getByText(/too early to rate numerically/i)).toBeTruthy();
  });
});

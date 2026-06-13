import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DonorFitSection } from './DonorFitSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'T', category: 'relief', ein: '1', rawData: {},
  amalEvaluation: {
    charity_ein: '1', charity_name: 'T', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    rich_narrative: {
      all_citations: [],
      ideal_donor_profile: {
        best_for_summary: 'Best for evidence-driven donors.',
        donor_motivations: ['Want measurable impact'],
        giving_considerations: ['Long time horizon'],
        not_ideal_for: 'donors seeking instant results',
      },
      donor_fit_matrix: {
        cause_area: 'global-health',
        giving_style: 'Systematic',
        evidence_rigor: 'High - RCT-backed',
        geographic_focus: ['Kenya', 'Uganda'],
      },
    },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
} as any;

describe('DonorFitSection', () => {
  it('renders #donor-fit anchor with rich content when signed in', () => {
    const { container } = render(<DonorFitSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#donor-fit')).toBeTruthy();
    expect(screen.getByText(/Best for evidence-driven donors/)).toBeTruthy();
    expect(screen.getByText('Systematic')).toBeTruthy();
  });

  it('shows ContentPreview gates and hides rich detail when anonymous', () => {
    const { container } = render(<DonorFitSection data={buildCdpData(charity, false)} />);
    expect(container.querySelector('#donor-fit')).toBeTruthy();
    expect(screen.getByText('Best For')).toBeTruthy();
    expect(screen.queryByText('Systematic')).toBeNull();
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StrengthsConcernsSection } from './StrengthsConcernsSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const base = {
  name: 'T', category: 'relief', ein: '1', rawData: {},
  amalEvaluation: {
    charity_ein: '1', charity_name: 'T', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    baseline_narrative: {
      summary: 's', headline: 'h',
      strengths: ['Strong program ratio'],
      areas_for_improvement: ['More transparency'],
      amal_score_rationale: 'r',
    },
  },
};

const richCharity = {
  ...base,
  amalEvaluation: {
    ...base.amalEvaluation,
    rich_narrative: {
      all_citations: [],
      strengths: ['Strong program ratio'],
      areas_for_improvement: ['More transparency'],
      case_against: { summary: 'Some caveats apply here.', risk_factors: ['Reserve volatility'], mitigation_notes: 'Watched closely.' },
    },
  },
} as any;

describe('StrengthsConcernsSection', () => {
  it('renders #strengths-concerns anchor with strengths when signed in', () => {
    const { container } = render(<StrengthsConcernsSection data={buildCdpData(richCharity, true)} />);
    expect(container.querySelector('#strengths-concerns')).toBeTruthy();
    expect(screen.getByText(/Strong program ratio/)).toBeTruthy();
    expect(screen.getByText(/Some caveats apply here/)).toBeTruthy();
  });

  it('shows ContentPreview gate when anonymous and a case_against exists', () => {
    const { container } = render(<StrengthsConcernsSection data={buildCdpData(richCharity, false)} />);
    expect(container.querySelector('#strengths-concerns')).toBeTruthy();
    expect(screen.getByText('Balanced View')).toBeTruthy();
    expect(screen.queryByText(/Some caveats apply here/)).toBeNull();
  });

  it('shows the real card for anonymous baseline charities (no case_against)', () => {
    const { container } = render(<StrengthsConcernsSection data={buildCdpData(base as any, false)} />);
    expect(container.querySelector('#strengths-concerns')).toBeTruthy();
    expect(screen.getByText(/Strong program ratio/)).toBeTruthy();
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ZakatSection } from './ZakatSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'T', category: 'relief', ein: '1', rawData: {},
  zakatClaimEvidence: ['Charity publishes a zakat policy. (Source: https://example.org/zakat)'],
  amalEvaluation: {
    charity_ein: '1', charity_name: 'T', amal_score: 82,
    wallet_tag: 'ZAKAT-ELIGIBLE', evaluation_date: 'x',
    confidence_scores: { impact: 44, alignment: 41 },
    score_details: { risks: {}, risk_deduction: 3 },
    baseline_narrative: { summary: 's', headline: 'h', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
} as any;

describe('ZakatSection', () => {
  it('renders #zakat anchor when zakat-eligible with evidence', () => {
    const { container } = render(<ZakatSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#zakat')).toBeTruthy();
  });

  it('renders for anonymous users too (not gated)', () => {
    render(<ZakatSection data={buildCdpData(charity, false)} />);
    expect(screen.getByText(/Charity publishes a zakat policy/)).toBeTruthy();
    expect(screen.getByText(/View policy/)).toBeTruthy();
  });

  it('renders nothing when not zakat-eligible', () => {
    const sadaqah = { ...charity, amalEvaluation: { ...charity.amalEvaluation, wallet_tag: 'SADAQAH-ELIGIBLE' } } as any;
    const { container } = render(<ZakatSection data={buildCdpData(sadaqah, true)} />);
    expect(container.querySelector('#zakat')).toBeFalsy();
  });
});

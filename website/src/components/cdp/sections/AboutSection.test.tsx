import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { AboutSection } from './AboutSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'Test Org', category: 'relief', ein: '12-3456789', rawData: {},
  amalEvaluation: {
    charity_ein: '12-3456789', charity_name: 'Test Org', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    baseline_narrative: { summary: 'A summary.', headline: 'A headline', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
  },
} as any;

describe('AboutSection', () => {
  it('renders a #about section anchor', () => {
    const { container } = render(<AboutSection data={buildCdpData(charity, true)} />);
    expect(container.querySelector('#about')).toBeTruthy();
  });

  it('renders the headline and summary text', () => {
    const { getByText } = render(<AboutSection data={buildCdpData(charity, true)} />);
    expect(getByText('A headline')).toBeTruthy();
    expect(getByText('A summary.')).toBeTruthy();
  });
});

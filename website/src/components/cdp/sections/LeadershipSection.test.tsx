import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LeadershipSection } from './LeadershipSection';
import { buildCdpData } from '../useCdpData';

vi.mock('../../../../contexts/LandingThemeContext', () => ({ useLandingTheme: () => ({ isDark: false }) }));

const charity = {
  name: 'Test Org', category: 'relief', ein: '12-3456789', rawData: {},
  amalEvaluation: {
    charity_ein: '12-3456789', charity_name: 'Test Org', amal_score: 82,
    wallet_tag: 'SADAQAH-ELIGIBLE', evaluation_date: 'x',
    baseline_narrative: { summary: 'A summary.', headline: 'A headline', strengths: [], areas_for_improvement: [], amal_score_rationale: 'r' },
    rich_narrative: {
      headline: 'rich-h',
      organizational_capacity: { ceo_name: 'Jane Doe', board_size: 9 },
      long_term_outlook: { years_operating: 12, maturity_stage: 'Mature', room_for_funding: 'Moderate' },
    },
  },
} as any;

describe('LeadershipSection', () => {
  it('renders a #leadership section anchor', () => {
    const { container } = render(
      <MemoryRouter><LeadershipSection data={buildCdpData(charity, true)} /></MemoryRouter>
    );
    expect(container.querySelector('#leadership')).toBeTruthy();
  });

  it('renders the CEO name when rich data is available', () => {
    const { getByText } = render(
      <MemoryRouter><LeadershipSection data={buildCdpData(charity, true)} /></MemoryRouter>
    );
    expect(getByText('Jane Doe')).toBeTruthy();
  });
});
